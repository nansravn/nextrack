"""The book of the night (spec A9 and A10): one self-contained HTML page, pt-BR labels, the
show's prose and the analyses' numbers, deterministic."""
import os
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

from showdata import FILE_1, FILE_2, put_show, two_track_show

import nextrack_show
import show_book
import show_room
import show_rules
from show_language import ShowFinding

VOID = {"meta", "br", "hr", "img", "input", "link", "col", "area", "base", "wbr", "source"}
SVG_EMPTY = {"rect", "line", "polyline", "path", "circle"}

LEDGER = """\
# Diário do time — teste

## 2026-11-07 — Primeira rodada
Pedido: abrir a noite.

### Decisões
- A chegada da Dançarina fica no drop 1.

### Para depois
- Rever a espiral.

## 2026-11-08 — Pontes de até 16 compassos sem perder a história
Pedido: pontes curtas.
Rodadas: 2 · versões: v1, v2 (escolhida: v2)

### Decisões
- A ponte da Dançarina para a Voa Voa termina no compasso 8:
  a chegada não muda. (custo se errado: uma ponte longa)
- O vermelho fica no lustre.

### Para depois
- Medir a sala.
"""


class _Checker(HTMLParser):
    """Collects the problems of an HTML text: a closing tag that does not match the open one,
    and tags left open at the end."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.problems: list[str] = []
        self.ids: list[str] = []
        self.text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "section":
            self.ids += [v for k, v in attrs if k == "id"]
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.problems.append(f"</{tag}> closes {self.stack[-1] if self.stack else 'nothing'}")
            return
        self.stack.pop()

    def handle_data(self, data):
        self.text.append(data)


def _check(page: str) -> _Checker:
    checker = _Checker()
    checker.feed(page)
    checker.close()
    return checker


def _compiled(src=None, inp=None):
    if src is None:
        src, inp = two_track_show()
    compiled, found, rules, advice = show_rules.evaluate_show(src, inp)
    assert compiled is not None, found
    return compiled, advice


def _book(ledger=None, **kw) -> str:
    compiled, advice = _compiled()
    return show_book.render_book(compiled, advice, ledger, **kw)


def test_book_has_every_section():
    page = _book()
    checker = _check(page)
    assert checker.problems == [] and checker.stack == []
    assert checker.ids == list(show_book.BOOK_SECTIONS)
    for heading in ("Capa", "Conceito", "Paleta", "Assinaturas", "Vocabulário", "Arco", "Momentos",
                    "Ritmo e variedade", "Música por música", "O que a ferramenta não sabe", "Avisos"):
        assert f">{heading}</h" in page
    assert page.startswith("<!doctype html>\n<html lang=\"pt-BR\">")


def test_book_carries_the_shows_prose():
    page = _book()
    assert "Uma noite de teste: o azul abre, o vermelho fecha." in page          # the show's story
    assert "Dançarina abre a noite: o azul respira" in page                       # a track's story
    assert "A virada: tudo em vermelho." in page                                  # a cue's intent


def test_book_is_deterministic(mini_repo):
    put_show(mini_repo)
    script = Path(nextrack_show.__file__)
    pages = []
    for seed in ("1", "2"):                     # two processes, two hash seeds: set order cannot leak
        out = mini_repo.root / f"book-{seed}.html"
        env = {**os.environ, "PYTHONHASHSEED": seed}
        done = subprocess.run([sys.executable, str(script), "book", "teste", "-o", str(out),
                               "--repo", str(mini_repo.root)],
                              capture_output=True, text=True, encoding="utf-8", env=env, check=False)
        assert done.returncode == 0, done.stderr
        pages.append(out.read_text(encoding="utf-8"))
    assert pages[0] == pages[1]
    assert _book() == _book()


def test_book_has_no_external_reference_and_no_script():
    page = _book(LEDGER).lower()
    for banned in ("<script", "http://", "https://", "src=", "@import", "<link", "<img", "<iframe"):
        assert banned not in page, banned


def test_book_has_theme_tokens_and_a_title():
    page = _book()
    assert "<title>Teste</title>" in page
    assert show_book.book_title("hi-ibiza-pulso") == "Hi Ibiza Pulso"
    assert show_book.book_title("uma-noite-muito-longa-demais") == "Uma Noite Muito Longa"
    style = page[page.index("<style>"):page.index("</style>")]
    assert re.search(r":root\s*\{[^}]*--bg:", style)
    assert '@media (prefers-color-scheme: dark)' in style
    assert ':root:not([data-theme="light"])' in style and ':root[data-theme="dark"]' in style
    assert re.search(r"body\s*\{[^}]*background:\s*var\(--bg\)", style)
    assert "width=device-width" in page
    body = page[page.index("</style>"):]
    for hexa in ("#0A2CFF", "#FF0A2A", "#6A1CFF"):          # the swatches: the real colours, as written
        assert f"background:{hexa}" in body


def test_book_draws_the_colour_score_and_the_arc():
    page = _book()
    score = page[page.index('<section id="paleta"'):page.index('<section id="assinaturas"')]
    ribbons = re.findall(r'<svg class="ribbon[^"]*"[^>]*>(.*?)</svg>', score, re.S)
    assert len(ribbons) == 3                                  # movers, Vorlanes, lustre
    assert all('fill="#' in r for r in ribbons)
    assert 'fill="#FF0A2A"' in score and 'fill="#0A2CFF"' in score
    arc = page[page.index('<section id="arco"'):page.index('<section id="momentos"')]
    svgs = re.findall(r"<svg[^>]*>(.*?)</svg>", arc, re.S)
    assert len(svgs) == 1 and svgs[0].count("<polyline") == 3
    for series in ("target", "music", "light"):
        assert f'<polyline class="{series}"' in svgs[0]


def test_book_escapes_text():
    src, inp = two_track_show()
    name = "&ME — <Teste> 'x'"
    src.track_files[FILE_1]["track"] = name
    src.track_files[FILE_1]["story"] = "A <b>noite</b> & o 'dia' começam aqui."
    inp.maps[FILE_1[:-4]]["track"] = name
    inp.set_tracks[0] = ("&ME", "<Teste> 'x'")
    compiled, advice = _compiled(src, inp)
    page = show_book.render_book(compiled, advice, None)
    assert "&amp;ME" in page and "&lt;Teste&gt;" in page
    assert "<Teste>" not in page and "<b>noite</b>" not in page
    assert "A &lt;b&gt;noite&lt;/b&gt; &amp; o &#x27;dia&#x27; começam aqui." in page
    checker = _check(page)
    assert checker.problems == [] and checker.stack == []
    assert checker.ids == list(show_book.BOOK_SECTIONS)


def test_latest_run_reads_decisions_and_later():
    run = show_book.latest_run(LEDGER)
    assert run == show_book.LedgerRun(
        "2026-11-08 — Pontes de até 16 compassos sem perder a história",
        ["A ponte da Dançarina para a Voa Voa termina no compasso 8: a chegada não muda. "
         "(custo se errado: uma ponte longa)", "O vermelho fica no lustre."],
        ["Medir a sala."])
    assert show_book.latest_run("# Diário do time — teste\n\nNada ainda.\n") is None
    assert show_book.latest_run("## Só o título\n") == show_book.LedgerRun("Só o título", [], [])


def test_book_prints_the_ledger_decisions():
    page = _book(LEDGER)
    concept = page[page.index('<section id="conceito"'):page.index('<section id="paleta"')]
    assert "Decisões" in concept and "Pontes de até 16 compassos sem perder a história" in concept
    assert "O vermelho fica no lustre." in concept
    assert "A chegada da Dançarina fica no drop 1." not in page          # an older run
    advice = page[page.index('<section id="avisos"'):]
    assert "Para depois" in advice and "Medir a sala." in advice


def test_book_without_a_ledger_leaves_the_decisions_out():
    page = _book(None)
    assert "Decisões" not in page and "Para depois" not in page
    assert _check(page).ids == list(show_book.BOOK_SECTIONS)


def _part(page: str, sid: str) -> str:
    start = page.index(f'<section id="{sid}"')
    end = page.find("<section id=", start + 1)
    return page[start:end if end > 0 else len(page)]


def _aim(preset, figure, status="configured", fallback=None):
    out = {"figure": figure, "preset": preset, "status": status, "targets": {"mover-ne": [1, 1, 1]}}
    return {**out, "fallback": fallback} if fallback else out


def test_book_shows_the_signatures_and_the_pending_aims():
    src, inp = two_track_show()
    inp.room = show_room.load_room({
        "size": {"x": 5.0, "y": 4.0, "z": 2.6}, "assumed": True,
        "fixtures": {"mover-ne": [5, 4, 2.3]}, "booth": [2.5, 4, 1.2],
        "aims": {"coluna": _aim("Up", "duas colunas"), "cruzado": _aim("Crossed Over", "um X"),
                 "centro-da-pista": _aim("Dance Floor Centre", "no centro"),
                 "apice": _aim("Apex", "uma tenda de luz", "pending", fallback="coluna")}})
    src.track_files[FILE_2]["cues"][1]["with"]["movers"]["positions"] = ["apice"]
    src.show["identity"] = {"arc": "waves", "signatures": [
        {"name": "azul-espaco", "intent": "O azul é o espaço.", "is": {"movers.colour": ["azul"]},
         "share": {"min": 0.2}}]}
    compiled, advice = _compiled(src, inp)
    page = show_book.render_book(compiled, advice, None, set_arc="single-peak")
    concept = _part(page, "conceito")
    assert "waves" in concept and "da identidade" in concept and "single-peak" not in page
    assert "azul-espaco" in concept and "O azul é o espaço." in concept
    signatures = _part(page, "assinaturas")
    share = compiled.cache["analysis"].identity.signatures[0].share
    assert f"prometido: mín 20% · entregue: <b>{round(100 * share)}%</b>" in signatures
    assert '<rect class="sig"' in signatures
    vocab = _part(page, "vocabulario")
    assert "uma tenda de luz" in vocab and "pendente: toca coluna" in vocab
    limits = _part(page, "limites")
    assert "A mira apice (uma tenda de luz)" in limits and "toca coluna no lugar" in limits
    assert "presumida" in limits


def test_book_prints_the_arc_and_the_advice():
    compiled, _ = _compiled()
    advice = [ShowFinding("lightshows/shows/teste/show.yml", 12, "show-advice",
                                     "bridges: the bridge of Voa Voa lasts 4 bars")]
    page = show_book.render_book(compiled, advice, None, set_arc="single-peak")
    assert "single-peak" in page and "do set" in page
    tail = page[page.index('<section id="avisos"'):]
    assert "bridges: the bridge of Voa Voa lasts 4 bars" in tail
    assert "lightshows/shows/teste/show.yml:12" in tail
