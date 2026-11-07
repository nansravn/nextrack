"""show_book.py — `nextrack_show.py book <show> -o FILE`: the book of the night, one HTML page
the owner reads before playing the set, laid out like a visual-identity presentation (spec
sections A9 and A10 of docs/superpowers/specs/2026-11-07-show-team-design.md).

The book is generated, never written. Its prose comes from the show (`story`, the identity's
intents, the tracks' `story` and `budget`, the cues' `intent`) and from the team's ledger; its
numbers come from `show_analysis.analyse`, `show_views.night_summary`,
`show_report.light_unknown_s` and `show_rules.occurrences`, whose docstrings state the formulas.
The labels are pt-BR. The same inputs give the same bytes.

The page follows the Artifact page contract, so the team can publish it as a private page:
one HTML document with inline CSS and inline SVG only (no script, no external reference); a
`<title>` of the show's id in words (`book_title`); colour tokens on `:root`, redefined for
dark mode under `@media (prefers-color-scheme: dark)` guarded by
`:root:not([data-theme="light"])` and again under `:root[data-theme="dark"]`; an explicit
`body` background; one column that reads at 360 px. The palette swatches and the colour
score draw the show's real hex colours in both themes. Every text is escaped with
`html.escape`; a colour reaches a `style` or `fill` only when it is `#RRGGBB`.

Sections (`BOOK_SECTIONS`, the `id` of each `<section>`, in order):
    capa         the show, its set, the night's length, the tracks, the tempo ramp and the
                 story's first sentence
    conceito     the story, the arc's shape (the identity's `arc`, else the set's front
                 matter `arc`), the declared signatures with their intents and their `is`, and
                 the "Decisões" of the ledger's latest run (`latest_run`)
    paleta       a swatch per palette colour (name, hex, the minutes each zone shows it); per
                 zone (movings, Vorlanes, lustre) its lit time and a proportion bar, each colour
                 taking its share of the night (`night_summary`'s `colours`); and the colour
                 score: per zone one SVG ribbon, x in seconds on the set clock, with one rect per
                 compiled section clipped to its track's leg (`TrackClock.leg`; an echo, after
                 G, falls outside it; a bridge lies inside the incoming leg) in the colour the
                 zone shows (`show_views._lit_colour`): a palette hex, `UV_HEX` for UV, the
                 `unlit` token for a zone off or dark, the `auto` token for the autoscript
    assinaturas  per declared signature its intent, the share promised (`min`, `max`) against
                 the share delivered (`show_analysis.identity`) and its occurrences on a ribbon
                 of the night; then the most present undeclared value per dimension, the
                 largest share first (a top value `none`, the dimension absent, is left out)
    vocabulario  a card per look of `show.yml` (its layers in words, its minutes, how many
                 sections play it and where: `show_rules.occurrences`), the time of the looks
                 written inline, the gestures the show calls, and the aims it uses with their
                 `figure` from `room.yml` (a pending aim with the aim that plays in its place)
    arco         one SVG, x in minutes: three polylines, the owner's target energy (1-10), the
                 night's E_music and E_light (0-9), on one 0-10 scale; bands where the light is
                 unknown; the played BPM in a strip under them; then the arc's rho and headroom
    momentos     the drops ranked by salience with their light response, the arrivals and the
                 moments (the first section of a cue or handover that names one), with their
                 intents
    ritmo        the longest static runs, the variety strip (`Variety.window`, 0-9 per minute),
                 the light's changes per minute, and what each rare resource spent against its
                 budget: every `rules.budget` key, then the effect keys and gestures the show uses
                 with no budget, then the total-dark sections
    musicas      a card per track: its clock, tempo and owner energy, its story and budget prose,
                 its arrival, its peak (its best-ranked drop), its bridge in and its handover
                 (and echo) out, and its strips: E_music (track scope) and E_light per leg bar
    limites      what the tool cannot know: the autoscript's share, the pending aims and their
                 stand-ins, the room's geometry assumed or not, UV not compiled, the maps without
                 `mix`, the measures being indices with formulas, the compiler's own decisions
    avisos       the advice still open (`show-advice` findings) and the latest run's
                 "Para depois"

Per minute (the arc, the variety strip's x, the changes): minute m (0 .. ceil(total / 60) - 1)
holds the leg bars that start in `[60 m, 60 m + 60)` on the set clock. Its `music` is the mean
E_music of those bars at night scope (`TrackEnergy.music_night`), `light` the mean of their
known E_light (None when the autoscript plays them all), `bpm` the mean of their played tempo
(bar k of a leg of n bars plays at `t0 + (t1 - t0) x min((k + 0.5) / n, 1)`, set_timeline's
model), `changes` the sum of their `X(b)` and `target` the owner's energy at the minute's middle
(`show_brief.target_at` over `Arc.target`).

The ledger (spec A10, `lightshows/shows/<id>/ledger.md`) is read by `latest_run`: the last `## `
heading is the latest run; its list items (`- ` or `* ` at column 0, an indented line continuing
the item) under `### Decisões` and `### Para depois` (matched without case or accents) are its
decisions and what is left for later. Without a ledger the book leaves both out.

Python API: `BOOK_SECTIONS`, `LedgerRun`, `latest_run`, `book_title`, `render_book`.
"""
from __future__ import annotations

import html
import math
import re
import unicodedata
from dataclasses import dataclass

import lightshow
import show_analysis
import show_brief
import show_report
import show_rules
import show_views
from show_gestures import GESTURES
from show_language import CompiledShow, ShowFinding, flatten_looks, layer_word
from show_views import COLOUR_GROUPS, clock_text

BOOK_SECTIONS = ("capa", "conceito", "paleta", "assinaturas", "vocabulario", "arco", "momentos", "ritmo",
                 "musicas", "limites", "avisos")
HEADINGS = {"capa": "Capa", "conceito": "Conceito", "paleta": "Paleta", "assinaturas": "Assinaturas",
            "vocabulario": "Vocabulário", "arco": "Arco", "momentos": "Momentos", "ritmo": "Ritmo e variedade",
            "musicas": "Música por música", "limites": "O que a ferramenta não sabe", "avisos": "Avisos"}
TITLE_WORDS = 4
UV_HEX = "#7B2FFF"
ZONES = {"movers": "Movings", "matrix": "Vorlanes", "hue": "Lustre"}
ZONE_PLACES = {"movers": "leste", "matrix": "oeste", "hue": "centro"}
LAYER_NAMES = {"movers": "Movings", "matrix": "Vorlanes", "white": "Fita branca", "uv": "UV",
               "strobe": "Estrobo", "hue": "Lustre"}
ARC_WORDS = {"single-peak": "um pico só", "waves": "em ondas", "slow-burn": "queima lenta"}
RARE_NAMES = {"white-accent": "fita branca, acento", "white-flash": "fita branca, flash", "strobe": "estrobo",
              "uv": "UV", "spiral": "espiral"}
PIPS_MAX = 12            # a budget above it prints as numbers only
LABEL_GAP = 0.04         # the least share of the night between two track numbers under a ribbon

_HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}")
_SENTENCE_RE = re.compile(r"(.+?[.!?])(?:\s|$)", re.S)
_WORDS = {"off": "apagado", "auto": "autoscript", "on": "ligado", "dark": "escuro"}
_FLAGS = {"mirror": "espelhado", "pingpong": "vai e volta", "with_white": "com branco"}
_HEADS = ("move", "draw", "state")


# ------------------------------------------------------------------ ledger --


@dataclass
class LedgerRun:
    title: str
    decisions: list[str]
    later: list[str]


def _plain(text: str) -> str:
    """Lower case without accents: `Decisões` -> `decisoes`."""
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))


def latest_run(ledger: str) -> LedgerRun | None:
    """The ledger's latest run (module docstring): the last `## ` heading's title, and the list
    items under its `### Decisões` and `### Para depois`. None without a `## ` heading."""
    lines = ledger.splitlines()
    start = max((i for i, line in enumerate(lines) if line.startswith("## ")), default=None)
    if start is None:
        return None
    run = LedgerRun(lines[start][3:].strip(), [], [])
    items: list[str] | None = None
    for line in lines[start + 1:]:
        if line.startswith("### "):
            key = _plain(line[4:].strip())
            items = run.decisions if key == "decisoes" else run.later if key == "para depois" else None
        elif items is None:
            continue
        elif line.startswith(("- ", "* ")):
            items.append(line[2:].strip())
        elif items and line[:1] in (" ", "\t") and line.strip():
            items[-1] += " " + line.strip()
    return run


# ----------------------------------------------------------------- helpers --


def book_title(show_id: str) -> str:
    """The show's id in words, each capitalised, at most `TITLE_WORDS`: `hi-ibiza-pulso` ->
    `Hi Ibiza Pulso`."""
    return " ".join([w.capitalize() for w in show_id.split("-") if w][:TITLE_WORDS])


def _e(value: object) -> str:
    return html.escape(str(value))


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _paragraphs(text: str, cls: str = "") -> str:
    attr = f' class="{cls}"' if cls else ""
    return "".join(f"<p{attr}>{_e(' '.join(p.split()))}</p>" for p in text.split("\n\n") if p.strip())


def _title(track: str) -> str:
    return track.split(" — ", 1)[-1]


def _artist(track: str) -> str:
    return track.split(" — ", 1)[0] if " — " in track else ""


def _pct(share: float | None) -> str:
    return "—" if share is None else f"{round(100 * share)}%"


def _fixed(value: float | None, digits: int = 2) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def _bars(a: int, b: int) -> str:
    return f"c. {a}" if a == b else f"c. {a}–{b}"


def _hex(value: object) -> str | None:
    return value.upper() if isinstance(value, str) and _HEX_RE.fullmatch(value) else None


def _section(sid: str, inner: str) -> str:
    number = BOOK_SECTIONS.index(sid)
    return (f'<section id="{sid}"><header class="sh"><span class="num">{number:02d}</span>'
            f"<h2>{_e(HEADINGS[sid])}</h2></header>{inner}</section>\n")


def _list(items: list[str], cls: str = "plain") -> str:
    """A `<ul>` of items already in HTML."""
    return f'<ul class="{cls}">' + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


@dataclass
class _Minute:
    music: float | None
    light: float | None
    bpm: float | None
    changes: int
    target: float | None


@dataclass
class _Book:
    show: CompiledShow
    a: show_analysis.Analysis
    summary: dict
    palette: dict[str, str]        # name -> #RRGGBB
    names: dict[str, str]          # #RRGGBB -> name
    minutes: list[_Minute]
    run: LedgerRun | None
    advice: list[ShowFinding]
    set_arc: str | None

    @property
    def total(self) -> float:
        return self.a.clock.total_s


def _minutes(a: show_analysis.Analysis) -> list[_Minute]:
    """The per-minute series of the module docstring."""
    total = a.clock.total_s
    n = math.ceil(total / 60) if total > 0 else 0
    music: list[list[int]] = [[] for _ in range(n)]
    light: list[list[int]] = [[] for _ in range(n)]
    bpm: list[list[float]] = [[] for _ in range(n)]
    changes = [0] * n
    for tc, te in zip(a.clock.tracks, a.energy):
        t0, t1 = tc.tempo
        for b in range(tc.leg[0], tc.leg[1] + 1):
            m = min(int(tc.at(b) // 60), n - 1)
            if (v := te.at("music_night", b)) is not None:
                music[m].append(v)
            if (v := te.at("light", b)) is not None:
                light[m].append(v)
            bpm[m].append(t0 + (t1 - t0) * min((b - tc.leg[0] + 0.5) / tc.played, 1.0))
            changes[m] += te.at("changes", b) or 0

    def mean(values):
        return sum(values) / len(values) if values else None

    points = a.arc.target
    return [_Minute(mean(music[m]), mean(light[m]), mean(bpm[m]), changes[m],
                    show_brief.target_at(points, 60 * m + 30) if points else None) for m in range(n)]


def _colour_hex(colour: str, b: _Book) -> str | None:
    """The hex a colour name shows: the palette's, the hex itself, `UV_HEX` for `uv`; None for
    the autoscript's colour."""
    return b.palette.get(colour) or _hex(colour) or (UV_HEX if colour == "uv" else None)


def _fill(colour: str | None, b: _Book) -> str:
    """The fill of a zone showing `colour` (`show_views._lit_colour`, None when not lit): a hex
    attribute, or the class of a token."""
    if colour is None:
        return 'class="unlit"'
    hexa = _colour_hex(colour, b)
    return f'fill="{hexa}"' if hexa else 'class="auto"'


def _chip(name: str, b: _Book) -> str:
    """A dot of the colour and its name."""
    hexa = _colour_hex(name, b)
    dot = f'<i class="dot" style="background:{hexa}"></i>' if hexa else '<i class="dot auto"></i>'
    return f'<span class="chipname">{dot}{_e(name)}</span>'


def _x(seconds: float) -> str:
    return f"{seconds:.2f}"


def _at_pct(seconds: float, total: float) -> str:
    return f"{100 * seconds / total:.2f}%" if total > 0 else "0%"


def _track_labels(b: _Book) -> str:
    """The tracks' numbers under a ribbon, at their legs' starts; a number closer than
    `LABEL_GAP` of the night to the last one printed is left out, so they never overlap."""
    spans, last = [], None
    for i, tc in enumerate(b.a.clock.tracks):
        at = tc.start_s / b.total if b.total > 0 else 0.0
        if last is None or at - last >= LABEL_GAP:
            spans.append(f'<span style="left:{100 * at:.2f}%">{i + 1}</span>')
            last = at
    return f'<div class="lbls" aria-hidden="true">{"".join(spans)}</div>'


def _clock_labels(n: int) -> str:
    """Clock labels under a per-minute chart of `n` minutes: every 10 minutes up to an hour,
    every 15 up to two, else every 30."""
    step = 10 if n <= 60 else 15 if n <= 120 else 30
    spans = "".join(f'<span style="left:{100 * m / n:.2f}%">{clock_text(60 * m)}</span>'
                    for m in range(0, n, step))
    return f'<div class="lbls" aria-hidden="true">{spans}</div>'


# -------------------------------------------------------------------- capa --


def _capa(b: _Book) -> str:
    show = b.show
    story = _text(show.data.get("story"))
    found = _SENTENCE_RE.match(story)
    lead = " ".join((found.group(1) if found else story).split())
    tracks = b.a.clock.tracks
    tempo = f"{tracks[0].tempo[0]:g} → {tracks[-1].tempo[1]:g} BPM" if tracks else "—"
    meta = [("Set", f"<code>{_e(show.data.get('set') or '—')}</code>"), ("Duração", _e(clock_text(b.total))),
            ("Músicas", str(len(show.tracks))), ("Andamento", _e(tempo))]
    cells = "".join(f"<div><b>{k}</b>{v}</div>" for k, v in meta)
    return (f'<section id="capa" class="cover"><p class="eyebrow">Livro da noite · <code>{_e(show.show_id)}</code></p>'
            f"<h1>{_e(book_title(show.show_id))}</h1><h2 class=\"vh\">{HEADINGS['capa']}</h2>"
            + (f'<p class="lead">{_e(lead)}</p>' if lead else "") + f'<div class="meta">{cells}</div></section>\n')


# ---------------------------------------------------------------- conceito --


def _arc_name(b: _Book) -> str:
    if b.a.identity.arc is not None:
        arc, source = b.a.identity.arc, "da identidade"
    elif b.set_arc:
        arc, source = b.set_arc, "do set"
    else:
        return '<span class="muted">não declarado</span>'
    words = ARC_WORDS.get(arc)
    return f"<code>{_e(arc)}</code>" + (f" — {_e(words)}" if words else "") + f' <span class="muted">({source})</span>'


def _declared(show: CompiledShow) -> dict[str, dict]:
    """The signatures of `identity` by name."""
    block = show.data.get("identity") if isinstance(show.data, dict) else None
    sigs = block.get("signatures") if isinstance(block, dict) else None
    return {s["name"]: s for s in sigs or [] if isinstance(s, dict) and isinstance(s.get("name"), str)}


def _is_text(spec: object, b: _Book) -> str:
    """A signature's `is`: each dimension and its values, colours as chips."""
    if not isinstance(spec, dict):
        return ""
    parts = []
    for dim, values in spec.items():
        values = values if isinstance(values, list) else [values]
        shown = ", ".join(_chip(str(v), b) if dim.endswith("colour") else f"<code>{_e(v)}</code>" for v in values)
        parts.append(f"<code>{_e(dim)}</code>: {shown}")
    return " · ".join(parts)


def _conceito(b: _Book) -> str:
    out = [_paragraphs(_text(b.show.data.get("story")), "story"),
           f'<p class="fact"><b>Arco</b> {_arc_name(b)}</p>']
    declared = _declared(b.show)
    if b.a.identity.signatures:
        out.append("<h3>Assinaturas declaradas</h3>")
        items = []
        for sig in b.a.identity.signatures:
            spec = declared.get(sig.name, {}).get("is")
            items.append(f"<b>{_e(sig.name)}</b><p>{_e(sig.intent)}</p>"
                         f'<p class="small muted">{_is_text(spec, b)}</p>')
        out.append(_list(items))
    else:
        out.append('<p class="muted">Nenhuma assinatura declarada em <code>identity</code>.</p>')
    if b.run is not None:
        out.append(f'<h3>Decisões do diretor</h3><p class="small muted">Última rodada: {_e(b.run.title)}</p>')
        out.append(_list([_e(d) for d in b.run.decisions]) if b.run.decisions
                   else '<p class="muted">Nenhuma decisão registrada nesta rodada.</p>')
    return _section("conceito", "".join(out))


# ------------------------------------------------------------------ paleta --


def _ribbon(b: _Book, group: str) -> str:
    """The colour score of one zone (module docstring)."""
    rects = []
    for i, (track, tc) in enumerate(zip(b.show.tracks, b.a.clock.tracks)):
        for sec in track.sections:
            lo, hi = max(sec.bars[0], tc.leg[0]), min(sec.bars[1], tc.leg[1])
            if lo > hi:
                continue
            x0, x1 = tc.at(lo), tc.at(hi + 1)
            colour = show_views._lit_colour(group, sec.layers.get(group), b.names)
            tip = (f"{i + 1}. {_title(track.track)} · {sec.name} · {_bars(lo, hi)} · "
                   f"{clock_text(x0)}–{clock_text(x1)} · {colour or 'apagado'}")
            rects.append(f'<rect x="{_x(x0)}" y="0" width="{_x(x1 - x0)}" height="10" {_fill(colour, b)}>'
                         f"<title>{_e(tip)}</title></rect>")
    return (f'<svg class="ribbon" viewBox="0 0 {_x(max(b.total, 1))} 10" preserveAspectRatio="none" role="img" '
            f'aria-label="{_e(ZONES[group])}"><rect class="auto" x="0" y="0" width="{_x(b.total)}" height="10"/>'
            + "".join(rects) + "</svg>")


def _paleta(b: _Book) -> str:
    s = b.summary
    swatches = []
    for name, hexa in b.palette.items():
        used = " · ".join(f"{ZONES[g]} {clock_text(s['colours'][g][name])}" for g in COLOUR_GROUPS
                          if s["colours"][g].get(name, 0) > 0) or "não usada"
        swatches.append(f'<div class="swatch"><i class="chip" style="background:{hexa}"></i>'
                        f"<b>{_e(name)}</b><code>{hexa}</code><span class=\"small muted\">{_e(used)}</span></div>")
    out = [f'<div class="swatches">{"".join(swatches)}</div>', "<h3>Minutos por zona</h3>"]
    for g in COLOUR_GROUPS:
        ranked = sorted(s["colours"][g].items(), key=lambda kv: (-kv[1], kv[0]))
        segs = "".join(f'<span style="width:{_at_pct(sec, b.total)};background:{hexa}" title="{_e(c)} '
                       f'{clock_text(sec)}"></span>' if (hexa := _colour_hex(c, b))
                       else f'<span class="auto" style="width:{_at_pct(sec, b.total)}" title="{_e(c)} '
                       f'{clock_text(sec)}"></span>' for c, sec in ranked if sec > 0)
        keys = " · ".join(f"{_chip(c, b)} {clock_text(sec)} ({_pct(sec / b.total if b.total else None)})"
                          for c, sec in ranked if sec > 0) or '<span class="muted">nunca acesa</span>'
        lit = s["zones"][g]
        out.append(f'<div class="zone"><p><b>{ZONES[g]}</b> <span class="muted">({ZONE_PLACES[g]}) · acesa '
                   f"{clock_text(lit)}, {_pct(lit / b.total if b.total else None)} da noite</span></p>"
                   f'<div class="bar">{segs}</div><p class="small">{keys}</p></div>')
    out.append('<h3>Partitura de cor</h3><p class="small muted">A noite inteira, seção por seção, na cor que cada '
               "zona mostra. Cinza claro: zona apagada; cinza médio: o autoscript decide.</p>")
    for g in COLOUR_GROUPS:
        out.append(f'<p class="rl">{ZONES[g]}</p>{_ribbon(b, g)}')
    out.append(_track_labels(b))
    return _section("paleta", "".join(out))


# ------------------------------------------------------------- assinaturas --


def _promise(sig: show_analysis.SignatureCheck) -> str:
    lo = sig.min if sig.min is not None else 0.0
    hi = sig.max if sig.max is not None else 1.0
    where = ("dentro do prometido" if sig.ok else "abaixo do mínimo" if sig.min is not None and sig.share < sig.min
             else "acima do máximo")
    wanted = " · ".join(x for x in (f"mín {_pct(sig.min)}" if sig.min is not None else "",
                                    f"máx {_pct(sig.max)}" if sig.max is not None else "") if x) or "sem faixa"
    return (f'<div class="promise"><i class="range" style="left:{100 * lo:.1f}%;'
            f'width:{100 * max(hi - lo, 0):.1f}%"></i>'
            f'<i class="mark" style="left:{100 * min(max(sig.share, 0), 1):.1f}%"></i></div>'
            f'<p class="small">prometido: {wanted} · entregue: <b>{_pct(sig.share)}</b> · {where}</p>')


def _assinaturas(b: _Book) -> str:
    ident = b.a.identity
    out = []
    if not ident.signatures:
        out.append('<p class="muted">Nenhuma assinatura declarada: a noite não prometeu uma repetição consciente.</p>')
    for sig in ident.signatures:
        rects = "".join(f'<rect class="sig" x="{_x(b.a.clock.at(i, lo))}" y="0" width="{_x(sec)}" height="10">'
                        f"<title>{_e(f'{_title(track)} {_bars(lo, hi)} · {clock_text(sec)}')}</title></rect>"
                        for i, track, (lo, hi), sec in sig.occurrences)
        out.append(f'<div class="card"><h3>{_e(sig.name)}</h3><p>{_e(sig.intent)}</p>{_promise(sig)}'
                   f'<p class="rl">{len(sig.occurrences)} ocorrência(s) na noite</p>'
                   f'<svg class="ribbon thin" viewBox="0 0 {_x(max(b.total, 1))} 10" preserveAspectRatio="none" '
                   f'role="img" aria-label="{_e(sig.name)}"><rect class="bg" x="0" y="0" width="{_x(b.total)}" '
                   f'height="10"/>{rects}</svg>{_track_labels(b)}</div>')
    ranked = sorted(((dim, top) for dim, top in ident.undeclared.items() if top[0] != "none"),
                    key=lambda kv: -kv[1][1])
    if ranked:
        out.append("<h3>O mais repetido sem declarar</h3>")
        out.append(_list([f"<code>{_e(dim)}</code>: <b>{_e(value)}</b> {_pct(share)} da noite"
                          for dim, (value, share) in ranked]))
    return _section("assinaturas", "".join(out))


# ------------------------------------------------------------- vocabulario --


def _value_words(key: str, item: object, b: _Book) -> str:
    if key == "colour":
        colours = item if isinstance(item, list) else [item]
        return " → ".join(_chip(str(c), b) for c in colours)
    if key in ("every", "rate"):
        return f"a cada {_e(item)}"
    if key in ("position", "positions"):
        return "em " + _e(", ".join(str(p) for p in item) if isinstance(item, list) else item)
    if key == "level" and isinstance(item, (int, float)):
        return f"nível {round(100 * item)}%"
    if item is True:
        return _e(_FLAGS.get(key, key))
    shown = ", ".join(str(i) for i in item) if isinstance(item, list) else str(item)
    return f"{_e(key)} {_e(shown)}"


def _layer_words(value: object, b: _Book) -> str:
    """A layer in words: its move, draw or state, its rate, colours, positions, level, flags."""
    value = layer_word(value)
    if not isinstance(value, dict):
        return _e(_WORDS.get(str(value), str(value)))
    parts = [_e(_WORDS.get(str(value[k]), str(value[k]))) for k in _HEADS if value.get(k) is not None]
    parts += [_value_words(k, v, b) for k, v in value.items() if k not in _HEADS and v is not None and v is not False]
    return ", ".join(parts)


def _where(found: list[show_rules.Occurrence]) -> str:
    return ", ".join(f"{_title(o.track)} c. {o.bar}" for o in found)


def _vocabulario(b: _Book) -> str:
    looks, _ = flatten_looks(b.show.data.get("looks") or {})
    timed = b.summary["looks"]
    cards = []
    for name, layers in looks.items():
        found = show_rules.occurrences(b.show, name)
        rows = "".join(f"<dt>{LAYER_NAMES[k]}</dt><dd>{_layer_words(layers[k], b)}</dd>"
                       for k in lightshow.LAYERS if k in layers)
        played = timed.get(name, 0.0)
        use = (f"{clock_text(played)} · {len(found)} vez(es)" if found or played > 0 else "não usado")
        cards.append(f'<div class="card"><h3>{_e(name)}</h3><dl>{rows}</dl><p class="small"><b>{_e(use)}</b></p>'
                     + (f'<p class="small muted">{_e(_where(found))}</p>' if found else "") + "</div>")
    out = [f'<div class="cards">{"".join(cards)}</div>' if cards else '<p class="muted">O show não tem looks.</p>']
    inline = timed.get("inline", 0.0)
    if inline > 0:
        out.append(f'<p class="small">Looks escritos na própria deixa: {clock_text(inline)} '
                   f"({_pct(inline / b.total if b.total else None)} da noite).</p>")
    gestures = [(g, show_rules.occurrences(b.show, g)) for g in GESTURES]
    gestures = [(g, found) for g, found in gestures if found]
    out.append("<h3>Gestos</h3>")
    out.append(_list([f"<b>{_e(g)}</b> · {len(found)} vez(es) · {clock_text(timed.get(g, 0.0))}"
                      f'<p class="small muted">{_e(_where(found))}</p>' for g, found in gestures])
               if gestures else '<p class="muted">Nenhum gesto.</p>')
    out.append("<h3>Miras</h3>")
    room = b.show.room
    pending = dict(b.summary["pending_aims"])
    aims = []
    for aim, sec in sorted(b.summary["aims"].items(), key=lambda kv: (-kv[1], kv[0])):
        known = room.aims.get(aim) if room is not None else None
        figure = f"<p>{_e(known.figure)}</p>" if known is not None else ""
        mark = (f' <span class="tag">pendente: toca {_e(pending[aim] or "sem substituta")}</span>'
                if aim in pending else "")
        aims.append(f"<b>{_e(aim)}</b> · {clock_text(sec)}{mark}{figure}")
    out.append(_list(aims) if aims else '<p class="muted">Nenhuma mira nomeada.</p>')
    return _section("vocabulario", "".join(out))


# -------------------------------------------------------------------- arco --


def _polyline(cls: str, rows: list[_Minute], value, y) -> str:
    points = " ".join(f"{m + 0.5:.1f},{y(v):.2f}" for m, r in enumerate(rows) if (v := value(r)) is not None)
    return f'<polyline class="{cls}" points="{points}"/>'


def _arco(b: _Book) -> str:
    rows = b.minutes
    n = len(rows)
    if n == 0:
        return _section("arco", '<p class="muted">A noite não tem relógio.</p>')

    def energy_y(v: float) -> float:          # 0-10 on y 95..5
        return 95 - 9 * v

    tempi = [r.bpm for r in rows if r.bpm is not None]
    lo, hi = (min(tempi), max(tempi)) if tempi else (0.0, 0.0)

    def bpm_y(v: float) -> float:             # the strip under the chart, y 128..108
        return 118.0 if hi - lo < 1e-9 else 128 - 20 * (v - lo) / (hi - lo)

    parts = [f'<line class="grid" x1="0" x2="{n}" y1="{energy_y(v):.0f}" y2="{energy_y(v):.0f}"/>' for v in (0, 5, 10)]
    parts += [f'<line class="tick" x1="{tc.start_s / 60:.2f}" x2="{tc.start_s / 60:.2f}" y1="5" y2="128"/>'
              for tc in b.a.clock.tracks[1:]]
    parts += [f'<rect class="unknown" x="{m}" y="5" width="1" height="90"/>' for m, r in enumerate(rows)
              if r.light is None]
    parts.append(_polyline("target", rows, lambda r: r.target, energy_y))
    parts.append(_polyline("music", rows, lambda r: r.music, energy_y))
    parts.append(_polyline("light", rows, lambda r: r.light, energy_y))
    bpm = " ".join(f"{'M' if k == 0 else 'L'}{m + 0.5:.1f},{bpm_y(r.bpm):.2f}"
                   for k, (m, r) in enumerate((m, r) for m, r in enumerate(rows) if r.bpm is not None))
    parts.append(f'<path class="bpm" d="{bpm}"/>')
    for m, r in enumerate(rows):
        tip = (f"{clock_text(60 * m)}–{clock_text(60 * m + 60)} · alvo {_fixed(r.target, 1)} · música "
               f"{_fixed(r.music, 1)} · luz {_fixed(r.light, 1) if r.light is not None else 'autoscript'} · "
               f"{_fixed(r.bpm, 0)} BPM")
        parts.append(f'<rect class="hit" x="{m}" y="0" width="1" height="130"><title>{_e(tip)}</title></rect>')
    ylabels = "".join(f'<span style="top:{100 * energy_y(v) / 130:.2f}%">{v}</span>' for v in (10, 5, 0))
    legend = ('<div class="legend"><span><i class="key target"></i>alvo: a energia do dono (1-10)</span>'
              '<span><i class="key music"></i>música: E_music da noite (0-9)</span>'
              '<span><i class="key light"></i>luz: E_light (0-9)</span>'
              f'<span><i class="key bpm"></i>BPM, faixa de baixo: {lo:g} a {hi:g}</span>'
              '<span><i class="key unknown"></i>luz desconhecida (autoscript)</span></div>')
    chart = (f'<div class="chart">{legend}<div class="plot"><div class="ylbls" aria-hidden="true">{ylabels}</div>'
             f'<svg class="arc" viewBox="0 0 {n} 130" preserveAspectRatio="none" role="img" '
             f'aria-label="Arco: alvo, música e luz por minuto">{"".join(parts)}</svg></div>{_clock_labels(n)}</div>')
    arc = b.a.arc
    facts = (f'<p class="small">Por música, a energia do dono contra a luz: rho {_fixed(arc.rho)} (média) e '
             f"{_fixed(arc.rho90)} (p90). Folga antes do pico: {_fixed(arc.headroom)} (a luz mais forte antes da "
             "primeira música no topo de energia, sobre a mais forte da noite).</p>")
    table = "".join(f"<tr><td>{clock_text(60 * m)}</td><td>{_fixed(r.target, 1)}</td><td>{_fixed(r.music, 1)}</td>"
                    f"<td>{_fixed(r.light, 1)}</td><td>{_fixed(r.bpm, 0)}</td></tr>" for m, r in enumerate(rows))
    details = ('<details><summary>Tabela por minuto</summary><table><thead><tr><th>minuto</th><th>alvo</th>'
               f"<th>música</th><th>luz</th><th>BPM</th></tr></thead><tbody>{table}</tbody></table></details>")
    return _section("arco", chart + facts + details)


# ---------------------------------------------------------------- momentos --


def _meter(value: float | None) -> str:
    width = 0 if value is None else round(100 * min(max(value, 0.0), 1.0))
    return f'<i class="meter"><i style="width:{width}%"></i></i>'


def _momentos(b: _Book) -> str:
    a = b.a
    drops = []
    for d in a.drops:
        holder = f" · {_e(d.holder.name)}" if d.holder is not None else ""
        main = ' <span class="tag">principal da música</span>' if d.main else ""
        drops.append(f'<span class="rank">{d.rank}</span><div><b>{_e(_title(d.track))}</b> <span class="muted">'
                     f"{_bars(d.bar, d.bar)} · {clock_text(d.clock_s)}{holder}</span>{main}"
                     f'<div class="row small"><span>saliência {_meter(d.salience)} {d.salience:.2f}</span>'
                     f"<span>resposta {_meter(d.response)} {_fixed(d.response)}</span></div></div>")
    out = ["<h3>Drops, do mais saliente ao menos</h3>",
           '<p class="small muted">Saliência: o quanto a música sobe (volume, grave, densidade). Resposta: o quanto '
           "a luz responde (contraste, dimensões que mudam, frescor).</p>",
           _list(drops, "plain drops") if drops else '<p class="muted">Nenhum drop soa na noite.</p>']
    arrivals, moments, seen = [], [], set()
    for i, track in enumerate(b.show.tracks):
        for sec in track.sections:
            o = sec.origin
            if o.kind in ("bridge", "echo"):
                continue
            when = f"{_bars(sec.bars[0], sec.bars[0])} · {clock_text(a.clock.at(i, sec.bars[0]))}"
            intent = f"<p>{_e(sec.intent)}</p>" if sec.intent else ""
            if o.role == "arrival":
                arrivals.append(f"<b>{_e(_title(track.track))}</b> <span class=\"muted\">{when} · {_e(sec.name)}</span>"
                                f"{intent}")
            if o.moment and (i, o.moment) not in seen:
                seen.add((i, o.moment))
                moments.append(f"<b>{_e(o.moment)}</b> <span class=\"muted\">{_e(_title(track.track))} {when}</span>"
                               f"{intent}")
    out += ["<h3>Chegadas</h3>", _list(arrivals) if arrivals else '<p class="muted">Nenhuma chegada.</p>',
            "<h3>Momentos</h3>", _list(moments) if moments else '<p class="muted">Nenhum momento nomeado.</p>']
    return _section("momentos", "".join(out))


# ------------------------------------------------------------------- ritmo --


def _columns(cls: str, values: list[float | None], top: float, label: str) -> str:
    """A per-minute column chart: one rect per minute, height `value / top`; a minute with
    None gets a low band."""
    rects = []
    for m, v in enumerate(values):
        if v is None:
            rects.append(f'<rect class="unknown" x="{m + 0.1:.1f}" y="18" width="0.8" height="2"><title>'
                         f"{clock_text(60 * m)} · —</title></rect>")
            continue
        h = 18 * v / top if top > 0 else 0
        rects.append(f'<rect class="{cls}" x="{m + 0.1:.1f}" y="{20 - h:.2f}" width="0.8" height="{h:.2f}">'
                     f"<title>{clock_text(60 * m)} · {v:g}</title></rect>")
    return (f'<svg class="cols" viewBox="0 0 {max(len(values), 1)} 20" preserveAspectRatio="none" role="img" '
            f'aria-label="{_e(label)}"><line class="grid" x1="0" x2="{len(values)}" y1="20" y2="20"/>'
            + "".join(rects) + "</svg>")


def _pips(used: int, top: int | None) -> str:
    if top is None:
        return f"{used} · <span class=\"muted\">sem orçamento</span>"
    text = f"{used} de {top}" + (' · <span class="tag over">acima do orçamento</span>' if used > top else "")
    if max(used, top) > PIPS_MAX:
        return text
    pips = ('<i class="on"></i>' * min(used, top) + '<i class="over"></i>' * max(used - top, 0)
            + "<i></i>" * max(top - used, 0))
    return f'<span class="pips" aria-hidden="true">{pips}</span> {text}'


def _rare(b: _Book) -> str:
    rules = b.show.data.get("rules") if isinstance(b.show.data, dict) else None
    budget = rules.get("budget") if isinstance(rules, dict) else None
    budget = budget if isinstance(budget, dict) else {}
    keys = [str(k) for k in budget]
    keys += [k for k in (*show_rules.EFFECT_KEYS, *GESTURES) if k not in budget and show_rules.occurrences(b.show, k)]
    rows = []
    for key in keys:
        found = show_rules.occurrences(b.show, key)
        limits = budget.get(key)
        top = limits.get("max") if isinstance(limits, dict) else None
        top = top if isinstance(top, int) and not isinstance(top, bool) else None
        name = RARE_NAMES.get(key)
        label = f"<b>{_e(name)}</b> <code>{_e(key)}</code>" if name else f"<b>{_e(key)}</b>"
        rows.append(f"{label} · {_pips(len(found), top)}" + (f'<p class="small muted">{_e(_where(found))}</p>'
                                                             if found else ""))
    dark = b.summary["total_dark"]
    rows.append(f"<b>breu total</b> <span class=\"muted\">(seções com tudo apagado)</span> · {dark['count']} · "
                f"{clock_text(dark['s'])}")
    return _list(rows)


def _ritmo(b: _Book) -> str:
    a = b.a
    runs = []
    for run in a.variety.static_runs:
        start = a.clock.at(run.index, run.bars[0])
        runs.append(f"<b>{clock_text(start)} → {clock_text(start + run.seconds)}</b> · {clock_text(run.seconds)} · "
                    f"a partir de {_e(_title(run.track))} c. {run.bars[0]}"
                    + (f' <span class="muted">· música {_e(run.music)}</span>' if run.music else ""))
    out = ["<h3>Os trechos parados mais longos</h3>",
           '<p class="small muted">A mesma luz em todas as dimensões, sem mudar.</p>',
           _list(runs) if runs else '<p class="muted">Nenhum.</p>']
    n = len(b.minutes)
    if n:
        window = list(a.variety.window[:n]) + [None] * max(n - len(a.variety.window), 0)
        changes = [float(r.changes) for r in b.minutes]
        out += ['<h3>Variedade por minuto</h3><p class="small muted">0-9: quantas luzes diferentes tocam nos 4 minutos '
                "em volta (a entropia das assinaturas).</p>",
                f'<div class="chart">{_columns("var", window, 9, "Variedade por minuto")}{_clock_labels(n)}</div>',
                '<h3>Mudanças por minuto</h3><p class="small muted">Quantas dimensões da luz mudam de um compasso '
                f"para o seguinte, somadas no minuto (máximo {max(changes):g}).</p>",
                f'<div class="chart">{_columns("chg", changes, max(changes), "Mudanças por minuto")}'
                f"{_clock_labels(n)}</div>"]
    out += ["<h3>Recursos raros contra o orçamento</h3>", _rare(b)]
    return _section("ritmo", "".join(out))


# ----------------------------------------------------------------- musicas --


def _path(values: list[int | None], y) -> str:
    """An SVG path through the known values (x = index + 0.5), with a gap where one is None."""
    out, pen = [], "M"
    for k, v in enumerate(values):
        if v is None:
            pen = "M"
            continue
        out.append(f"{pen}{k + 0.5:.1f},{y(v):.2f}")
        pen = "L"
    return " ".join(out)


def _span(sections) -> tuple[int, int] | None:
    return (min(s.bars[0] for s in sections), max(s.bars[1] for s in sections)) if sections else None


def _track_card(b: _Book, i: int) -> str:
    a, track, tc, te = b.a, b.show.tracks[i], b.a.clock.tracks[i], b.a.energy[i]
    energy = b.show.energies.get(track.track)
    head = [f"entra {clock_text(tc.start_s)}", f"{tc.span_s(*tc.leg) / 60:.1f} min",
            f"{tc.tempo[0]:g} → {tc.tempo[1]:g} BPM" if tc.tempo[0] != tc.tempo[1] else f"{tc.tempo[0]:g} BPM",
            f"e{energy}" if energy is not None else "sem energia"]
    if te.interim:
        head.append("E_music provisório")
    rows = []
    arrival = next((s for s in track.sections if s.origin.role == "arrival"), None)
    if arrival is not None:
        rows.append(("Chegada", f"{_bars(arrival.bars[0], arrival.bars[0])} · "
                                f"{clock_text(tc.at(arrival.bars[0]))} · {_e(arrival.name)}"
                     + (f"<br><span class=\"muted\">{_e(arrival.intent)}</span>" if arrival.intent else "")))
    peak = min((d for d in a.drops if d.index == i), key=lambda d: d.rank, default=None)
    if peak is not None:
        rows.append(("Pico", f"{_bars(peak.bar, peak.bar)} · {clock_text(peak.clock_s)} · {peak.rank}º drop da noite · "
                             f"resposta {_fixed(peak.response)}"))
    bridge = [s for s in track.sections if s.origin.kind == "bridge"]
    span = _span(bridge)
    rows.append(("Ponte de entrada", "sem ponte" if span is None else
                 f"{_bars(*span)} ({span[1] - span[0] + 1} compassos), a luz de "
                 f"<code>{_e(bridge[0].origin.look or 'inline')}</code> da anterior"))
    handover = [s for s in track.sections if s.origin.kind == "handover"]
    span = _span(handover)
    out_text = "sem entrega" if span is None else (f"{_bars(*span)}, <code>{_e(handover[0].origin.look or 'inline')}"
                                                     "</code>")
    echo = _span([s for s in track.sections if s.origin.kind == "echo"])
    if echo is not None:
        out_text += f" · eco {_bars(*echo)}"
    rows.append(("Entrega", out_text))
    budget = _text(track.choreography.get("budget"))
    if budget:
        rows.append(("Orçamento", _e(" ".join(budget.split()))))
    played = list(range(tc.leg[0], tc.leg[1] + 1))
    y = lambda v: 95 - 10 * v  # noqa: E731  (digits 0-9 on y 95..5)
    strip = (f'<svg class="strip" viewBox="0 0 {max(len(played), 1)} 100" preserveAspectRatio="none" role="img" '
             f'aria-label="E_music e E_light por compasso">'
             f'<line class="grid" x1="0" x2="{len(played)}" y1="95" y2="95"/>'
             f'<path class="music" d="{_path([te.at("music", x) for x in played], y)}"/>'
             f'<path class="light" d="{_path([te.at("light", x) for x in played], y)}"/></svg>'
             f'<p class="small muted">{_bars(tc.leg[0], tc.leg[1])} · <i class="key music"></i>música, na escala '
             'da faixa · <i class="key light"></i>luz</p>')
    dl = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows)
    artist = _artist(track.track)
    return (f'<article class="card track"><p class="num">{i + 1:02d}</p><h3>{_e(_title(track.track))}</h3>'
            + (f'<p class="muted">{_e(artist)}</p>' if artist else "")
            + f'<p class="small">{_e(" · ".join(head))}</p>{_paragraphs(_text(track.choreography.get("story")))}'
            f"<dl>{dl}</dl>{strip}</article>")


def _musicas(b: _Book) -> str:
    return _section("musicas", '<div class="cards">' + "".join(_track_card(b, i) for i in range(len(b.show.tracks)))
                    + "</div>")


# ----------------------------------------------------------------- limites --


def _limites(b: _Book) -> str:
    s, room = b.summary, b.show.room
    unknown = show_report.light_unknown_s(b.a.clock, b.a.energy)
    items = [f"O autoscript decide a luz de {clock_text(unknown)} ({_pct(unknown / b.total if b.total else None)} da "
             "noite): a ferramenta não sabe o que ele acende." if unknown > 0 else
             "Nenhum trecho fica com o autoscript: toda a luz das pernas é a que o compilador escreve."]
    for aim, fallback in s["pending_aims"]:
        known = room.aims.get(aim) if room is not None else None
        figure = f" ({known.figure})" if known is not None else ""
        items.append(f"A mira {aim}{figure} ainda não é um preset do SoundSwitch: toca "
                     f"{fallback or 'nenhuma mira'} no lugar.")
    if not s["pending_aims"]:
        items.append("Nenhuma mira pendente: as miras que o show usa existem no SoundSwitch.")
    if room is None:
        items.append("Sem um room.yml válido: as miras não têm figura nem alvo.")
    elif room.assumed:
        items.append("A geometria da sala (room.yml) é presumida: os alvos das movings não foram medidos.")
    else:
        items.append("A geometria da sala (room.yml) foi medida.")
    uv = len(show_rules.occurrences(b.show, "uv"))
    items.append(f"O UV não é compilado: uv: on e move: uv ficam como deixas manuais no SoundSwitch ({uv} no show).")
    interim = [_title(te.track) for te in b.a.energy if te.interim]
    if interim:
        items.append("Mapas sem mix (versão 1), com E_music provisório: " + ", ".join(interim) + ".")
    items.append("E_music, E_light, saliência, resposta e variedade são índices com fórmula (lightshows/shows/"
                 "README.md, The critic's views): medem o que o mapa ouve e o que o compilador escreve, não o que a "
                 "sala vê.")
    items.append(f"O compilador decidiu {len(b.show.decisions)} coisa(s) sozinho (pontes, fins de deixa, miras, ecos): "
                 "nextrack_show.py report --section decided lista cada uma.")
    return _section("limites", _list([_e(i) for i in items]))


# ------------------------------------------------------------------ avisos --


def _avisos(b: _Book) -> str:
    out = [_list([f"{_e(f.message)}<p class=\"small muted\"><code>{_e(f'{f.path}:{f.line}')}</code></p>"
                  for f in b.advice]) if b.advice else '<p class="muted">Nenhum aviso em aberto.</p>']
    if b.run is not None:
        out.append(f'<h3>Para depois</h3><p class="small muted">Da última rodada: {_e(b.run.title)}</p>')
        out.append(_list([_e(x) for x in b.run.later]) if b.run.later else '<p class="muted">Nada.</p>')
    return _section("avisos", "".join(out))


# -------------------------------------------------------------------- page --


_CSS = """\
:root {
  color-scheme: light;
  --bg: #f6f4ef; --surface: #fffdf8; --ink: #16161a; --ink-2: #4a4944; --ink-3: #6f6d66;
  --rule: #dcd8cd; --grid: #e7e3d9; --unlit: #e4e0d6; --auto: #b9b4a7; --ring: rgba(0, 0, 0, .12);
  --hover: rgba(0, 0, 0, .06); --music: #2a78d6; --light: #eb6834; --target: #1baf7a; --over: #d03b3b;
  --display: "Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif;
  --sans: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --bg: #121214; --surface: #1a1a1d; --ink: #f0efec; --ink-2: #c3c2b7; --ink-3: #9a988f;
    --rule: #2f2f34; --grid: #2a2a2f; --unlit: #26262a; --auto: #4a4a50; --ring: rgba(255, 255, 255, .18);
    --hover: rgba(255, 255, 255, .08); --music: #3987e5; --light: #d95926; --target: #199e70; --over: #e66767;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --bg: #121214; --surface: #1a1a1d; --ink: #f0efec; --ink-2: #c3c2b7; --ink-3: #9a988f;
  --rule: #2f2f34; --grid: #2a2a2f; --unlit: #26262a; --auto: #4a4a50; --ring: rgba(255, 255, 255, .18);
  --hover: rgba(255, 255, 255, .08); --music: #3987e5; --light: #d95926; --target: #199e70; --over: #e66767;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 16px/1.55 var(--sans); overflow-wrap: anywhere; }
main { max-width: 880px; margin: 0 auto; padding: 0 16px 64px; }
section { padding: 48px 0; border-top: 1px solid var(--rule); }
section.cover { border-top: 0; padding: 72px 0 48px; }
.sh { display: flex; align-items: baseline; gap: 12px; margin-bottom: 24px; }
.num { font: 600 13px/1 var(--mono); color: var(--ink-3); letter-spacing: .08em; margin: 0; }
h1, h2, h3 { font-family: var(--display); font-weight: 500; margin: 0; letter-spacing: -.01em; }
h1 { font-size: clamp(44px, 11vw, 88px); line-height: 1; margin: 16px 0 24px; }
h2 { font-size: clamp(26px, 5vw, 36px); line-height: 1.15; }
h3 { font-size: 20px; margin: 32px 0 10px; }
.card h3 { margin-top: 0; }
p { margin: 0 0 12px; }
dl { margin: 12px 0; display: grid; grid-template-columns: minmax(96px, max-content) 1fr; gap: 6px 12px; }
dt { color: var(--ink-3); font-size: 14px; }
dd { margin: 0; }
code { font: 13px var(--mono); }
details { margin-top: 16px; font-size: 14px; }
summary { cursor: pointer; color: var(--ink-2); }
table { border-collapse: collapse; margin-top: 8px; font-variant-numeric: tabular-nums; }
th, td { text-align: right; padding: 2px 10px 2px 0; border-bottom: 1px solid var(--rule); }
th:first-child, td:first-child { text-align: left; }
.vh { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
.eyebrow { text-transform: uppercase; letter-spacing: .14em; font-size: 12px; color: var(--ink-3); margin: 0; }
.lead, .story { font-family: var(--display); font-size: clamp(20px, 4.4vw, 26px); line-height: 1.4; }
.meta { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 16px; margin-top: 40px; }
.meta div { border-top: 1px solid var(--ink); padding-top: 8px; }
.meta b { display: block; font-size: 12px; font-weight: 500; color: var(--ink-3); text-transform: uppercase;
  letter-spacing: .08em; }
.fact b { font-weight: 600; margin-right: 8px; }
.muted { color: var(--ink-3); }
.small { font-size: 14px; }
.tag { display: inline-block; font-size: 12px; padding: 1px 8px; border: 1px solid var(--rule); border-radius: 999px;
  color: var(--ink-2); }
.tag.over { border-color: var(--over); }
ul.plain { list-style: none; padding: 0; margin: 0; }
ul.plain > li { padding: 10px 0; border-top: 1px solid var(--rule); }
ul.plain > li p { margin: 4px 0 0; }
.drops > li { display: flex; gap: 12px; }
.rank { font: 600 20px/1.2 var(--display); min-width: 28px; color: var(--ink-3); }
.row { display: flex; flex-wrap: wrap; gap: 4px 16px; align-items: center; }
.meter { display: inline-block; width: 64px; height: 6px; background: var(--grid); border-radius: 3px;
  vertical-align: middle; overflow: hidden; }
.meter i { display: block; height: 100%; background: var(--ink-2); }
.swatches { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 16px; }
.swatch .chip { display: block; height: 96px; border-radius: 8px; box-shadow: inset 0 0 0 1px var(--ring); }
.swatch b { display: block; margin-top: 8px; }
.swatch code, .swatch span { display: block; }
.dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px;
  box-shadow: inset 0 0 0 1px var(--ring); }
.dot.auto { background: var(--auto); }
.chipname { white-space: nowrap; }
.zone { margin-bottom: 16px; }
.zone p { margin-bottom: 6px; }
.bar { display: flex; height: 16px; border-radius: 4px; overflow: hidden; background: var(--unlit); gap: 2px; }
.bar span { display: block; height: 100%; }
.bar span.auto { background: var(--auto); }
.rl { font-size: 13px; color: var(--ink-2); margin: 12px 0 4px; }
svg { display: block; width: 100%; }
svg * { vector-effect: non-scaling-stroke; }
.ribbon { height: 28px; border-radius: 3px; }
.ribbon.thin { height: 16px; }
.cols { height: 64px; }
.strip { height: 64px; margin-top: 8px; }
.lbls { position: relative; height: 18px; font-size: 11px; color: var(--ink-3); overflow: hidden; }
.lbls span { position: absolute; top: 2px; }
.chart { margin: 8px 0 16px; }
.plot { position: relative; padding-left: 22px; }
.ylbls { position: absolute; left: 0; top: 0; bottom: 0; width: 20px; font-size: 11px; color: var(--ink-3); }
.ylbls span { position: absolute; transform: translateY(-50%); }
.plot + .lbls { margin-left: 22px; }
.arc { height: 260px; }
.legend { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 13px; color: var(--ink-2); margin: 8px 0; }
.key { display: inline-block; width: 18px; height: 0; border-top: 2px solid var(--ink-3); vertical-align: middle;
  margin-right: 6px; }
.key.music { border-color: var(--music); }
.key.light { border-color: var(--light); }
.key.target { border-top-style: dashed; border-color: var(--target); }
.key.unknown { height: 10px; border: 0; background: var(--grid); }
.grid { stroke: var(--grid); stroke-width: 1; }
.tick { stroke: var(--rule); stroke-width: 1; }
polyline, path { fill: none; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
.music { stroke: var(--music); }
.light { stroke: var(--light); }
.target { stroke: var(--target); stroke-dasharray: 6 4; }
.bpm { stroke: var(--ink-3); stroke-width: 1.5; }
.unknown { fill: var(--grid); }
.hit { fill: transparent; }
.hit:hover { fill: var(--hover); }
.unlit { fill: var(--unlit); }
.auto { fill: var(--auto); }
.bg { fill: var(--grid); }
.sig { fill: var(--ink-2); }
.var { fill: var(--music); }
.chg { fill: var(--ink-2); }
.promise { position: relative; height: 12px; background: var(--grid); border-radius: 6px; margin: 12px 0 6px; }
.promise .range { position: absolute; top: 0; bottom: 0; background: var(--auto); border-radius: 6px; }
.promise .mark { position: absolute; top: -4px; width: 3px; height: 20px; margin-left: -1px; background: var(--ink); }
.pips i { display: inline-block; width: 10px; height: 10px; border-radius: 50%; border: 1px solid var(--ink-3);
  margin-right: 3px; vertical-align: middle; }
.pips i.on { background: var(--ink); border-color: var(--ink); }
.pips i.over { background: var(--over); border-color: var(--over); }
.cards { display: grid; gap: 16px; }
.card { background: var(--surface); border: 1px solid var(--rule); border-radius: 10px; padding: 16px;
  margin-bottom: 16px; }
.cards .card { margin-bottom: 0; }
.track .num { margin-bottom: 8px; }
footer { padding: 24px 0 0; border-top: 1px solid var(--rule); font-size: 13px; color: var(--ink-3); }
"""


def render_book(show: CompiledShow, advice: list[ShowFinding], ledger: str | None, *,
                set_arc: str | None = None) -> str:
    """The book of the night as one HTML page (module docstring). `advice` are the show's
    `show-advice` findings, `ledger` the text of its `ledger.md` (None without one) and `set_arc`
    the `arc` of the set's front matter, printed when the identity declares none."""
    a = show_analysis.analyse(show)
    palette = {str(k): h for k, v in (show.data.get("palette") or {}).items() if (h := _hex(v))}
    b = _Book(show, a, show_views.night_summary(show, a.clock, show.room), palette,
              {h: n for n, h in palette.items()}, _minutes(a), latest_run(ledger) if ledger else None,
              list(advice), set_arc)
    sections = [_capa, _conceito, _paleta, _assinaturas, _vocabulario, _arco, _momentos, _ritmo, _musicas,
                _limites, _avisos]
    footer = (f"<footer>Gerado por nextrack_show.py book a partir de <code>{_e(show.folder)}/</code>. Não edite: "
              "mude o show e gere de novo.</footer>")
    return ("<!doctype html>\n<html lang=\"pt-BR\">\n<head>\n<meta charset=\"utf-8\">\n"
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '<meta name="color-scheme" content="light dark">\n'
            f"<title>{_e(book_title(show.show_id))}</title>\n<style>\n{_CSS}</style>\n</head>\n<body>\n<main>\n"
            + "".join(render(b) for render in sections) + footer + "\n</main>\n</body>\n</html>\n")
