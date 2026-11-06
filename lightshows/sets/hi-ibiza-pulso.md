---
set: sets/hi-ibiza-pulso.md
budget:                    # onde cada efeito raro pode aparecer: os nomes da seção "Momentos"
  white-accent: [abertura, yamore, virada, pick-up, final]   # uma batida em cada chegada escolhida
  white: [final]           # a fita em flash: só nos últimos compassos do Dirty Cash
  strobe: [virada, pick-up, cant-decide, dirty-cash, final]  # só do TOO COOL em diante
---

# Plano de luz — Hï Ibiza (Pulso)

O guia para coreografar o [set Hï Ibiza](../../sets/hi-ibiza-pulso.md) faixa a faixa. As 15
faixas estão no bloco [Hï Ibiza — Pulso](../../blocks/hi-ibiza-pulso.md). Os compassos vêm dos
mapas musicais (`uv run scripts/nextrack_map.py show "<faixa>"`) e as passagens, de
`nextrack_map.py timeline --playlist 1-hi-ibiza-lightshow --block blocks/hi-ibiza-pulso.md`.
As 15 coreografias deste plano são o **rascunho v1**, para o dono ver no simulador e revisar, e
são **geradas** pelo show [`lightshows/shows/hi-ibiza-pulso/`](../shows/hi-ibiza-pulso/show.yml)
com `uv run scripts/nextrack_show.py build hi-ibiza-pulso`: muda-se o show, nunca a coreografia
gerada.

## A história da noite: Pulso
A noite é um corpo. O azul é o espaço: a noite funda e os feixes das movings cortando a neblina
fina que fica a noite toda, como no Hï: sala escura, pouca luz geral, muito feixe. O vermelho é
o coração, e mora no centro da sala, no lustre. O BPM do set é o batimento: começa em repouso, a
120 na Rapture, e termina acelerado, a 132 no Dirty Cash. Quanto mais a noite anda, mais rápido
e mais vermelho o coração bate.

1. **Despertar** (The Rapture Pt.III): a noite começa no breu, só a neblina; entra um feixe
   azul; o coração dá o primeiro batimento com o kick, em carmim.
2. **Transe** (The Akan até Yamore, 120-122): azul quase o tempo todo; movings lentas, Vorlanes
   respirando; o vermelho é só o coração. Breu antes de alguns drops, sem estrobo.
3. **Aceleração** (Move, 122 → 125): o revezamento acelera com o pitch; o violeta entra nas
   Vorlanes e o coração passa a vermelho vivo.
4. **Virada** (TOO COOL TO BE CARELESS): espiral, um compasso de breu e o primeiro estrobo da
   noite no drop do c. 49. O vermelho toma a sala.
5. **Pico** (Verano en NY até Dirty Cash, 128-132): vermelho e azul dividem a sala, estrobo nos
   drops principais; o Dirty Cash gasta o que sobrou e, no fim, só o coração fica aceso.

## Ponte e chegada
- **Ponte:** enquanto duas músicas tocam juntas, os dois scripts mostram a mesma luz. A música
  que sai termina, do G dela até o fim, no seu **look de entrega**; a que entra começa, do B
  dela até a chegada, com esse mesmo look, copiado camada por camada. Em qualquer compasso que o
  SoundSwitch troque de script, a sala não vê corte.
- **Chegada:** o drop que mostra a música nova. Toda chegada troca o desenho principal e a cor
  ou o lado. A coluna "chegada" da tabela das faixas é a escolhida para a luz; onde a anterior
  ainda toca muito tempo depois do G, a chegada é o primeiro drop depois de um break da nova.
- **Antes do B:** ninguém ouve neste set; fica no autoscript (com a neblina no nível do rig).

Os três looks de entrega:

| look | quando | movings | Vorlanes | lustre |
|---|---|---|---|---|
| respiração azul | transe (Rapture → Yamore) | `sweep` a cada `2bar` entre Dance Floor Centre e Crossed Over, azul-gelo, 0.7 | `rows-up` em `1bar`, azul-profundo, `mirror` | `pulse` carmim |
| aceleração | Yamore → Move → TOO COOL | `pingpong` em 1/2, violeta | `rows-up` em 1/2, azul-profundo, `mirror` | `pulse` carmim |
| pulso vermelho | TOO COOL → Verano → Pick Up | `pingpong` em 1/4, azul-gelo | `rows-up` em 1/4, vermelho, `mirror` | `pulse` vermelho |

Pick Up The Phone e Can't Decide entregam o próprio drop final (o pico) e a música seguinte
herda esse look: `blink` vermelho nas movings e as Vorlanes a 1/16 (`rows-down` no Pick Up,
`centre-out` no Can't Decide).

## Momentos
Os nomes do `budget` e os gestos raros. Nenhum repete o anterior.

- `abertura` — The Rapture Pt.III, c. 145 (~4:48 do set): depois do break de mais de um minuto
  sem grave, a subida com o kick filtrado, um compasso de breu (c. 144) e o drop: o vermelho
  acende no centro pela primeira vez, o desenho sai do meio pras bordas e a fita branca bate uma
  vez.
- `yamore` — Yamore, c. 65 (~27:15): o grave volta depois de oito compassos de silêncio, com as
  vozes; oito compassos enchendo as Vorlanes e a seta sobe em ciano com a fita branca. O kick só
  volta no c. 88. Sem breu: aqui a subida basta.
- `virada` — TOO COOL TO BE CARELESS, c. 49 (~32:20): espiral nos c. 41-47, breu no c. 48 e o
  drop com o primeiro estrobo da noite, a fita branca e as Vorlanes inteiras batendo em vermelho
  a cada 1/8. A única música com espiral, breu e estrobo.
- `pick-up` — PICK UP THE PHONE, c. 137 (~39:30, o G dele): depois da contraluz do Nate Dogg e da terceira
  espiral, o drop final com estrobo e fita branca; é o look que ele entrega ao Can't Decide.
- `cant-decide` — Can't Decide, c. 69 (~41:00): o último breu (c. 68) e o drop com estrobo, que
  é também o G: o Dirty Cash entra por baixo desse pico.
- `dirty-cash` — Dirty Cash, c. 57: o drop maior da música, estrobo no 1.
- `final` — Dirty Cash, c. 113-119: rolo de estrobo (c. 113-114), a fita branca no 1 e a fita em
  `flash` nos últimos compassos, a única vez da noite. Na última nota, só o lustre fica aceso, em
  carmim.

Os outros gestos contados:

| gesto | quantos | onde |
|---|---|---|
| breu (um compasso, tudo apagado) | 5 | Rapture 144 · Trippy Yeah 32 · Baianá 88 · TOO COOL 48 · Can't Decide 68 |
| espiral (v1) | 3 | Move 25-28 · TOO COOL 41-47 · Pick Up 128-136 |
| contraluz | 3 | Rapture 113-132 · What To Do 163-172 · Pick Up 104-127 |
| fita branca (acento) | 5 | Rapture 145 · Yamore 65 · TOO COOL 49 · Pick Up 137 · Dirty Cash 113 |
| estrobo | 5 | TOO COOL 49 · Pick Up 137 · Can't Decide 69 · Dirty Cash 57 · Dirty Cash 113-114 (rolo) |

**A espiral na versão 1.** O vocabulário de hoje não faz a luz andar pela sala em círculo. A
espiral v1 é um revezamento que acelera: as Vorlanes alternam NW e SW (`columns` com
`pingpong`) e as movings alternam NE e SE, na mesma velocidade, seção a seção (1/2, 1/4, 1/8,
1/16), do azul ao violeta ao vermelho, com o centro escuro, até o drop acender o lustre. A
espiral de verdade, cada luz da sala acendendo em volta até fechar no centro, é vocabulário novo
(projeto B).

**Contraluz.** Vorlanes `off`, lustre `dark` e só os dois feixes, azul-gelo, baixos e cruzados
(`hold` em Crossed Over, 0.35), cortando a neblina: o momento mais Hï da sala.

## Gramática dos feixes
Os feixes na neblina são o visual da noite, então **nenhuma seção escrita deixa a mira com o
autoscript**: sem posição, ele troca de preset a cada 2 compassos, em ordem aleatória, sempre com
o mesmo balanço. Toda seção de movings tem a sua mira:

| momento | mira |
|---|---|
| grooves | `sweep` lento entre dois presets (Dance Floor Centre e Crossed Over, ou Stage Left e Stage Right) |
| drops e chegadas | `pingpong` ou `blink` numa mira por seção, alternando Dance Floor Centre (os feixes convergem no centro da pista) e Crossed Over (os feixes se cruzam) de uma seção para a seguinte |
| subidas | `Up`: os feixes sobem para a neblina enquanto a música sobe |
| breaks e contraluz | `hold` baixo (Crossed Over, Down, Up ou DJ Booth) |
| ponte da aceleração | `pingpong` saltando entre Dance Floor Centre, Crossed Over e Up a cada meio compasso |
| ponte do pico | `pingpong` em Crossed Over |
| picos entregues (Pick Up, Can't Decide) | `blink` no centro da pista |
| espirais | a 1/2 e 1/4, a mira salta entre Crossed Over, Up e Dance Floor Centre; a 1/8 e 1/16 fecha no centro da pista |

Onde cada preset aponta na sala ainda é palpite (os cantos do rig não foram confirmados): confira
Dance Floor Centre, Crossed Over, Up e Down na sala antes de afinar esta tabela (experimento P2
em [experiments.md](../../docs/soundswitch/experiments.md#playback-in-the-room-p)).

Com toda seção mirando, o movimento do autoscript que uma borda de seção corta nunca aparece
neste set, e o compilador não pede nenhum cue manual por isso: ele só avisa quando o movimento
removido apareceria de verdade.

## Paleta
| nome | cor | papel |
|---|---|---|
| azul-profundo | `#0A2CFF` | o espaço: as Vorlanes a noite toda |
| azul-gelo | `#3A6BFF` | os feixes das movings na neblina; a contraluz |
| ciano | `#00B8FF` | a água: só em chegadas e drops do transe |
| violeta | `#6A1CFF` | a mistura do azul com o vermelho: aceleração e espirais |
| carmim | `#B0001E` | o coração em repouso, no lustre |
| vermelho | `#FF0A2A` | o coração acelerado: do Move em diante no lustre, da virada em diante nas Vorlanes |

## Papéis
| aparelho | papel | transe (1-9) | aceleração e virada (10-11) | pico (12-15) |
|---|---|---|---|---|
| lustre (Hue) | o coração | `pulse` carmim nos grooves, `dark` nos breaks e subidas | `pulse` vermelho | `pulse` vermelho; `dark` nas subidas; aceso em carmim no fim |
| movings | os feixes na neblina | `sweep` lento ou `hold` numa posição; `pingpong` nos drops | `pingpong` acelerando | `pingpong` e `blink` nos drops |
| Vorlanes | os instrumentos | desenhos lentos e azuis; ciano nas chegadas | violeta; `solid` vermelho na virada | vermelho a 1/8 e 1/16 |
| fita branca | pontuação | abertura e Yamore | a virada | Pick Up e o final (`flash` só no fim) |
| strobe | exclamação | nunca | a virada | drops principais |

## As faixas
O relógio é o do set nos BPMs tocados (B → G de cada faixa). "Chegada" é o drop escolhido para a
música nova; "gesto" é o que a faixa gasta.

| # | faixa | B → G | entra em | chegada | desenho da chegada | gesto |
|---|---|---|---|---|---|---|
| 1 | The Rapture Pt.III | 1 → 169 | 0:00 | 145 | `centre-out` azul + vermelho no centro | breu 144, contraluz, fita branca |
| 2 | The Akan | 57 → 137 | 5:36 | 105 | `columns` ciano | — |
| 3 | What To Do (&ME Remix) | 129 → 201 | 8:15 | 177 | `rows-down` azul | contraluz 163-172 |
| 4 | We Dance Again | 21 → 121 | 10:37 | 56 (o grave entra de vez; o kick nunca para) | `solid` azul alternando lados: o batimento | — |
| 5 | Trippy Yeah | 5 → 101 | 13:54 | 33 | `zigzag` azul | breu 32 |
| 6 | Say What | 26 → 79 | 17:03 | 41 | `columns` alternando NW/SW | — |
| 7 | Baianá (Pablo Fierro Edit) | 25 → 146 | 18:47 | 47 | `centre-out` ciano | breu 88 |
| 8 | Ma Tnsani (Yalla Habibi) | 2 → 84 | 22:45 | 33 | `rows-down` alternando NW/SW | — |
| 9 | Yamore | 9 → 98 | 25:26 | 65 (o grave; o kick no 88) | `arrow-up` ciano | fita branca |
| 10 | Move | 1 → 76 | 28:21 | 29 | `columns` violeta | espiral 25-28 |
| 11 | TOO COOL TO BE CARELESS | 1 → 89 | 30:47 | 25; virada 49 | `solid` vermelho a 1/8 | espiral, breu, estrobo, fita branca |
| 12 | Verano en NY | 9 → 90 | 33:33 | 58 | `zigzag` vermelho | — |
| 13 | PICK UP THE PHONE | 27 → 137 | 36:05 | 73; pico 137 | `rows-up` vermelho alternando | contraluz, espiral, estrobo, fita branca |
| 14 | Can't Decide | 20 → 69 | 39:30 | 44 (o grave no 36); pico 69 | `centre-out` vermelho a 1/16 | breu 68, estrobo |
| 15 | Dirty Cash (Money Talks) | 17 → fim | 41:00 | 45 | `arrow-up` vermelho | estrobo, rolo, fita branca, flash |

O set dura cerca de 44 minutos.

## Regras da noite
1. **Escuro primeiro.** A sala começa no breu e passa o transe com pouca luz geral: o lustre só
   bate nos grooves; nas subidas e nos breaks fica `dark`.
2. **Breu é raro:** cinco na noite, nos compassos da tabela. Nenhuma outra seção apaga tudo.
3. **Espiral ou breu, nunca os dois**, exceto a virada (TOO COOL).
4. **Estrobo só do TOO COOL em diante**, `hit` no 1 do drop; `roll` só no final.
5. **A fita branca é acento:** `off` em toda seção escrita (todas desenham ou apagam as
   Vorlanes), uma batida nas cinco chegadas do budget, `flash` só nos últimos compassos.
6. **Duas faixas seguidas não repetem o desenho da chegada.**
7. **As Vorlanes conversam:** NW e SW nunca são clones (`mirror` ou `pingpong`; o `solid` da
   virada e do final é a exceção: o coração inteiro bate junto).
8. **Movings: uma acesa, a outra no escuro** nos drops (`pingpong`); nos grooves, `sweep` ou
   `hold`. Toda seção tem mira própria, pela gramática dos feixes; a mira muda com a seção.
9. **Ponte é cópia exata.** A seção `entrega` de uma faixa e a seção `ponte` da seguinte têm as
   mesmas camadas com os mesmos valores (os acentos de um compasso só, estrobo e fita, ficam na
   faixa que sai).
10. **Sem UV:** a noite não é de Halloween.
11. **A ponte é ágil:** 16 compassos, nunca mais de 32. Entrega e ponte usam a mesma janela.

## O que fica para a próxima versão
- **Espiral de verdade**, **coração com decaimento** (um "tum-tum" duplo, o pulso que some antes
  do próximo), **feixe que respira com a voz**, **Vorlanes como equalizador** (uma faixa de
  linhas por instrumento) e **estéreo vira sala**: vocabulário novo, projeto B, com os dados que
  os mapas musicais já guardam (vozes por passo, batidas, registro, estéreo).
- **Quando o SoundSwitch troca de script na mixagem** ainda não foi testado. A ponte foi feita
  para funcionar em qualquer compasso; o teste (P1) entra junto com o X1b, e o do lustre
  acompanhando o pulso (P3) também.
