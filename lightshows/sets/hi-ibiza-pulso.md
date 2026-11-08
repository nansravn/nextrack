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
  que sai toca, do G dela, por no máximo 16 compassos (`bridge.bars: 16`), o seu **look de
  entrega**; a que entra começa, do B dela, com esse mesmo look, copiado camada por camada. No
  relógio o B da que entra cai sobre o G da que sai, então **a entrega termina onde a ponte
  termina**: o `until` da entrega é G + (primeiro cue da que entra − B), e com o capítulo novo
  em B + 16 é o padrão. Em qualquer compasso que o SoundSwitch troque de script, a sala não vê
  corte.
- **Capítulo novo e eco:** quando a mixagem dura mais que a janela, a música que entra abre,
  logo depois da ponte, um **capítulo novo** que vai até o seu primeiro cue de antes: a luz dela
  naquele trecho da música, nem a ponte esticada nem um corte. O compilador copia esse capítulo
  no fim da música que sai (o **eco**), e a sala vê uma luz só até a que sai acabar. O capítulo
  pode começar antes de B + 16, numa fronteira forte dentro da janela (veja "Fronteiras"), por
  escolha do designer; num break longo ele tem que começar antes (veja "A janela segue a música
  que entra"). Nos dois casos a entrega encurta junto. Uma ponte curta (3 compassos, na Yamore)
  é válida e continua cópia exata. Um cue que a música que entra já tem dentro da janela também
  acaba a ponte (o `break` da Say What no c. 39).
- **O capítulo novo não é uma chegada.** A chegada de cada música fica onde está. O capítulo
  não usa o desenho nem a cor de Vorlane da chegada da própria música e não leva momento, acento
  ou efeito raro (breu, espiral, contraluz, fita e estrobo já estão com o orçamento gasto). Cada
  seção mira pela gramática dos feixes. As duas assinaturas da noite seguem dentro do limite:
  movings em azul-gelo ou azul-profundo em pelo menos 70% da noite e o lustre em carmim ou
  vermelho em pelo menos 60% (hoje 86% e 80%). Nos breaks e subidas o lustre fica `dark`, pela
  regra 1. Prefira começar cada seção numa linha de frase do mapa (o início de uma das
  `sections` do mapa, ou um múltiplo de 4 compassos depois dele).
- **A luz do capítulo.** As movings ficam em azul-gelo (a assinatura `azul-espaco`) e seguem a
  gramática dos feixes: `sweep` nos grooves, `pingpong` nos drops, `hold` nos breaks. No Move
  elas podem seguir violeta, a cor da aceleração. As Vorlanes usam um desenho diferente do da
  ponte que acaba (`rows-up` nas três entregas; `rows-down` ou `centre-out` nos picos entregues)
  e do da chegada da própria faixa, na cor da fase (tabela "Papéis"); no Move, sem o violeta,
  que é da chegada. O lustre fica em `pulse` nos grooves e drops (carmim até a Yamore, vermelho
  do Move em diante) e `dark` nos breaks e subidas, em todas as fases. A luz do capítulo não
  passa a da chegada da faixa, seção a seção: o dígito da linha `light` do `report` em cada
  compasso do capítulo fica igual ou abaixo do da chegada. O capítulo prepara a chegada, não
  a antecipa.
- **Fronteiras.** O capítulo pode ter mais de uma seção. Uma fronteira forte da música dentro
  dele pede uma seção nova nesse compasso, com outro desenho, nível ou mira. Conta como forte
  o início de uma das `sections` do mapa, ou um compasso que o `follows` do `report` lista em
  "missed": Ma Tnsani 24, Pick Up 65 e Dirty Cash 39 caem dentro dos capítulos.
- **O eco é do compilador.** Ninguém escreve o eco. Ele copia, no fim da música que sai, tudo
  o que a que entra mostra naquele trecho: o capítulo novo e o que vier depois (a chegada, uma
  contraluz, um breu, os passos de uma espiral), até a que sai acabar. Copia os estados, não os
  eventos: estrobo e fita ficam só na faixa que os toca. O orçamento conta cada gesto onde ele
  foi escrito; o eco nunca conta, e as regras de seção (`total-dark`, `movers-aim`,
  `matrix-not-cloned`) não o leem. Quem desenha a abertura da que entra desenha também o fim da
  que sai.
- **A janela segue a música que entra.** No relógio do set, a música que entra toca desde o B
  dela: dali em diante os compassos são a perna dela, e todas as views do `report` (follows,
  drops, arc, identity, variety) leem a perna de cada faixa. No trecho do eco, a faixa que sai
  já está fora da perna dela e não é medida ali. Por isso uma entrega não atravessa um break da
  que entra que dure 4 compassos ou mais e comece dentro da janela (uma seção `break` do mapa
  que comece entre B e B + 15). A ponte acaba onde ele começa, a luz da própria música entra ali
  (um capítulo novo, ou o cue que ela já tem), e a entrega acaba junto. Hoje isso vale para:
  - a Trippy Yeah: break do mapa nos c. 12-30, e o capítulo vai do c. 12 até a `subida` do
    c. 28, que fica;
  - a Yamore: c. 12-16;
  - o Can't Decide: break do mapa nos c. 28-43; os cues `break` (c. 28) e `o-grave-volta`
    (c. 36), que já existem, ficam.

  Os breaks de 2 compassos (Pick Up c. 33-34 e 41-42) e os que começam
  depois da janela ficam como estão; o do Dirty Cash (c. 31-32) abre o capítulo dele, uma escolha do designer que a regra "Fronteiras" permite. Um drop dentro da janela não encurta a entrega: o c. 25 do
  Dirty Cash fica dentro da ponte, por decisão do diretor.
- **Compassos.** "c. a-b" inclui os dois compassos; o `until` de um cue ou de uma entrega é o
  primeiro compasso depois dela.
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
| lustre (Hue) | o coração | `pulse` carmim nos grooves, `dark` nos breaks e subidas | `pulse` vermelho | `pulse` vermelho; `dark` nas subidas e nos breaks; aceso em carmim no fim |
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
11. **A ponte é ágil:** no máximo 16 compassos (`bridge.bars: 16`). Entrega e ponte usam a
    mesma janela; o resto da mixagem é o capítulo novo da que entra, e o eco dele na que sai.

## Cartões
Um cartão por faixa. A linha `Entrega` cobre a mixagem com a faixa seguinte: o look do G e o
que a seguinte faz no resto da mixagem. Os compassos vêm do `report` e dos mapas: "c. 73 dela"
é um compasso da música que entra. A mixagem que leva à faixa N chama-se `mix-NN` (`mix-02` é
Rapture → Akan; `mix-12` é TOO COOL → Verano) e é descrita no cartão da faixa N − 1. Uma
mixagem é a entrega da que sai (do G ao fim do mapa dela) e a abertura da que entra (do B ao
compasso antes da chegada); o eco cobre a parte da abertura que toca antes da que sai acabar.

### 1. &ME, Black Coffee — The Rapture Pt.III
- Energia: e6; a luz acorda do zero (breu, um feixe, o coração) e só passa da metade na abertura.
- Papel no arco: Despertar. A noite nasce no breu e o coração dá o primeiro batimento.
- Chegada: `abertura`, c. 145 (drop, +5.8 dB), depois do breu do c. 144: `centre-out`, lustre vermelho, fita branca.
- Pico: o drop do c. 161 (+13.5 dB), `groove-final`, Vorlanes a 1/8.
- Família de looks: `breu-inicial`, o feixe azul-gelo, `respiracao-azul`, `contraluz` (c. 113-132); Vorlanes azul-profundo; lustre carmim, vermelho só na abertura.
- Entrega: `respiracao-azul` do G (c. 169) por 16 compassos (c. 169-184), copiada na ponte da Akan (c. 57-72 dela). A Akan abre então um capítulo novo, c. 73-96 dela: o groove cheio (kick, grave e percussão a 9; a voz aparece nos c. 77-79 e volta nos c. 94-96, antes do break do c. 97). É a Akan tomando a sala com o seu groove, azul e com o coração carmim, sem o ciano, que é da chegada do c. 105. O eco leva esse capítulo para a Rapture nos c. 185-208, e o c. 209, o último dela, copia o primeiro compasso do break da Akan (c. 97).

### 2. Caiiro — The Akan
- Energia: e6 (o mapa mede aqui a música mais forte da noite); a luz segura o transe, sem efeito raro.
- Papel no arco: abre o Transe: azul quase o tempo todo, o vermelho só no coração.
- Chegada: c. 105 (drop, +11.3 dB, o 2º drop da noite em saliência): `columns` ciano a 1/8, `pingpong` no centro.
- Pico: a própria chegada, c. 105-120.
- Família de looks: `respiracao-azul` na ponte; o groove em `sweep` azul-gelo (`groove-tribal`, c. 121-136, entre os lados); Vorlanes azul-profundo, ciano só na chegada; lustre carmim, `dark` no break (c. 97-100) e na subida (c. 101-104).
- Entrega: `respiracao-azul` do G (c. 137) por 16 compassos (c. 137-152), copiada na ponte da What To Do (c. 129-144 dela). A What To Do abre então um capítulo novo, c. 145-162 dela: o drop sem voz (o kick cai de 8 para 7 no c. 153; a voz volta nos c. 161-162, logo antes da contraluz do c. 163). É o groove da What To Do, azul, que passa a vez à contraluz `a-voz-no-escuro` sem gastar o escuro dela. O eco leva o capítulo e o que vem depois para a Akan nos c. 153-194.

### 3. Guy Gerber — What To Do (&ME Remix)
- Energia: e6; o transe com a voz no escuro e um drop forte na chegada.
- Papel no arco: o transe se aprofunda; a voz aparece no escuro e a chegada acende tudo.
- Chegada: c. 177 (drop, +18.9 dB): `rows-down` azul-profundo a 1/8, `pingpong` no centro.
- Pico: a chegada, c. 177-192.
- Família de looks: `contraluz` (`a-voz-no-escuro`, c. 163-172), subida em `fill-up` (c. 173-176), `rows-down`, ciano no groove (c. 193-200); lustre carmim.
- Entrega: `respiracao-azul` do G (c. 201) por 16 compassos (c. 201-216), copiada na ponte da We Dance Again (c. 21-36 dela). A We Dance Again abre então um capítulo novo, c. 37-55 dela: a voz da Nakhana sobre o kick, sem o grave desde o c. 39. É a voz sem o grave, contida, que guarda para a chegada do c. 56 o batimento do `solid`, quando o grave volta. O eco leva o capítulo e o que vem depois para a What To Do nos c. 217-257.

### 4. Black Coffee, Nakhana — We Dance Again
- Energia: e6; o kick nunca para, e a luz é a mais ativa do começo do transe.
- Papel no arco: o batimento: o transe ganha corpo.
- Chegada: c. 56, quando o grave entra de vez: `solid` azul-profundo com `pingpong`, os feixes parados no centro (0.8).
- Pico: `brilho`, c. 104-120: `columns` ciano, `pingpong` a 1/2.
- Família de looks: `solid`, `rows-up` a 1/4 (`a-voz`, c. 72-103), `columns` ciano; lustre carmim.
- Entrega: `respiracao-azul` do G (c. 121) até o fim da ponte da Trippy Yeah, c. 121-127 (`until: 128`), copiada na ponte da Trippy (c. 5-11 dela, o groove). A música da Trippy cai no break no c. 12 (c. 12-27), e a janela segue a música que entra: a Trippy abre então um capítulo novo no break, c. 12-27 dela (o grave sai no c. 22, o kick baixa para 4-6 e a voz entra no c. 24), escrito por esta mixagem. É o break da Trippy, recolhido, antes da `subida` (c. 28-31), do breu (c. 32) e da chegada (c. 33), que são da própria Trippy e ficam como estão; o capítulo não rouba o escuro do breu. O eco leva o capítulo para a We Dance Again nos c. 128-143.

### 5. Jimi Jules, Black Coffee — Trippy Yeah
- Energia: e7, a primeira da noite; a luz contrasta mais: breu e dois drops fortes.
- Papel no arco: o transe acelera e gasta o segundo breu da noite.
- Chegada: c. 33 (drop, +24.9 dB, o 3º da noite), depois do breu do c. 32: `zigzag` azul-profundo a 1/8.
- Pico: `drop-2`, c. 93 (+30.1 dB): `zigzag` a 1/16.
- Família de looks: `zigzag`, `rows-up`, ciano em `a-voz` (c. 48-63), `fill-up` nas subidas, `hold` na poça no break (c. 82-89); lustre carmim.
- Entrega: `respiracao-azul` do G (c. 101). A ponte da Say What tem 13 compassos (c. 26-38 dela: o break dela começa no c. 39 e a chegada no c. 41), então a entrega termina junto, c. 101-113 (`until: 114`). A Say What não precisa de capítulo novo. O eco leva o break e a chegada dela para a Trippy nos c. 114-122.

### 6. Rampa, Adam Port, &ME, chuala, Keinemusik — Say What
- Energia: e7; transe vocal, dois drops.
- Papel no arco: o transe canta.
- Chegada: c. 41 (drop, +21.4 dB): `columns` azul-profundo com `pingpong` a 1/8.
- Pico: `drop-2`, c. 73 (+26.2 dB, o drop principal do mapa): `columns` ciano.
- Família de looks: `columns`, `hold` nos breaks, `fill-up` na subida; lustre carmim.
- Entrega: `respiracao-azul` do G (c. 79) até o último compasso da música, c. 79-91 (`until: end + 1`, 13 compassos), copiada na ponte da Baianá, c. 25-37 dela: o c. 91 da Say What é o c. 37 da Baianá, o último em que as duas tocam juntas. A Baianá abre então um capítulo novo, c. 38-42 dela, na intro com a voz e as palmas, sem o grave, e o break do c. 43 (c. 43-46) fica onde está; o designer pode juntar os dois num capítulo só, c. 38-46, se a música pedir. A chegada continua no c. 47. Não há eco: a entrega cobre a Say What até o fim.

### 7. Barbatuques — Baianá (Pablo Fierro Edit)
- Energia: e7; a luz mais ativa do transe.
- Papel no arco: o corpo: a percussão vocal acende a sala.
- Chegada: c. 47 (drop, +16.6 dB): `centre-out` ciano a 1/8.
- Pico: `drop-do-corpo`, c. 89-122, depois do breu do c. 88: `centre-out` a 1/16; o drop final do mapa é o do c. 134.
- Família de looks: `centre-out`, `fill-up` no break, `breu` (c. 88); lustre carmim.
- Entrega: `respiracao-azul` do G (c. 146) por 16 compassos (c. 146-161), copiada na ponte da Ma Tnsani (c. 2-17 dela). A Ma Tnsani abre então um capítulo novo, c. 18-32 dela: o groove até o c. 23 e, do c. 24, o break (o grave some, o kick cai para 4-5, a voz cresce de 27 a 32) que leva à chegada do c. 33. O break do c. 24 é uma fronteira forte que a luz de hoje não acompanha (o `follows` a lista em "missed"), e pede uma seção nova. O eco leva o capítulo e o começo da chegada da Ma Tnsani (c. 33-40 dela) para a Baianá nos c. 162-184, quando a Baianá já está na seção `outro` do mapa.

### 8. Vanco, Aya — Ma Tnsani (Yalla Habibi)
- Energia: e7; um respiro antes da Yamore.
- Papel no arco: o transe oriental, mais contido.
- Chegada: c. 33 (drop, +5.3 dB): `rows-down` azul-profundo com `pingpong` a 1/4.
- Pico: `o-grave-volta`, c. 76-83 (`rows-down` ciano a 1/8), e o drop do G (c. 84).
- Família de looks: `rows-down` e `rows-up`, `hold` na coluna no break cantado (c. 64-75); lustre carmim.
- Entrega: `respiracao-azul` do G (c. 84) até o fim da ponte da Yamore, c. 84-86 (`until: 87`), copiada na ponte da Yamore (c. 9-11 dela, o groove). A música da Yamore cai num break nos c. 12-16, e a janela segue a música que entra: a Yamore abre então um capítulo novo de duas seções, no mínimo: o break (c. 12-16: movings em `hold`, lustre `dark`) e o primeiro drop (c. 17-32, o principal do mapa, +16.1 dB, as vozes cheias: `pingpong` numa mira), até `as-vozes` (c. 33). O drop do c. 17 sobe acima do break. Ele não usa o `arrow-up` nem o ciano da chegada (`yamore`, c. 65), nem o `rows-up` da ponte; as Vorlanes ficam em azul-profundo. A luz dele fica em 4 ou menos na linha `light`, abaixo do momento `yamore`, que gasta a fita branca. O capítulo também não repete o que a Ma Tnsani acabou de mostrar nos breaks e no capítulo dela (feixe baixo parado com `fill-up`, `columns` espelhado, as miras coluna e cruzado). O eco leva o capítulo e o começo de `as-vozes` (c. 33-35 dela) para a Ma Tnsani nos c. 87-110.

### 9. MoBlack, Salif Keita, Cesária Evora, Benja (NL), Franc Fala — Yamore
- Energia: e7; o fim do transe: o grave volta com as vozes.
- Papel no arco: fecha o transe e passa a noite para a aceleração.
- Chegada: `yamore`, c. 65: o grave volta depois de oito compassos sem ele; `arrow-up` ciano e fita branca.
- Pico: o kick volta no c. 88 (`o-kick-volta`, `rows-up` a 1/8).
- Família de looks: `sweep` entre os lados (`as-vozes`, c. 33-56), `fill-up` nas subidas, `arrow-up` ciano; lustre carmim, `dark` nas subidas.
- Entrega: `aceleracao` do G (c. 98) por 16 compassos (c. 98-113), copiada na ponte do Move (c. 1-16 dele). O Move abre então um capítulo novo, c. 17-24 dele: o groove cheio com a voz, antes da espiral do c. 25 e da chegada do c. 29. É o revezamento que começa a acelerar com o pitch (o set vai de 122 a 125 no Move): as movings podem seguir violeta, mas as Vorlanes não usam o violeta, que é da chegada. O capítulo fica mais lento que o primeiro passo da espiral (1/2, nas movings e nas Vorlanes), para a espiral ser a aceleração; e deixa o `sweep` entre o centro da pista e o cruzado para a chegada do TOO COOL. O eco leva o capítulo e os dois primeiros passos da espiral do Move (c. 25-26 dele) para a Yamore nos c. 114-123; a espiral conta no orçamento só no Move.

### 10. Adam Port, Stryv, Keinemusik, oRSo, Malachiii — Move
- Energia: e7; a aceleração, 122 → 125.
- Papel no arco: Aceleração: o revezamento acelera, o violeta entra nas Vorlanes e o coração passa a vermelho vivo.
- Chegada: c. 29 (drop, +14.7 dB), depois da espiral (c. 25-28): `columns` violeta a 1/8, lustre vermelho.
- Pico: a chegada, mais rápida a partir do c. 45.
- Família de looks: `aceleracao`, a espiral, `columns` violeta; lustre vermelho.
- Entrega: `aceleracao` do G (c. 76) até o c. 87, copiada na ponte do TOO COOL (c. 1-15 dele). Fora desta execução: a passagem já cabe na janela.

### 11. PAWSA — Too Cool To Be Careless
- Energia: e8; a virada da noite.
- Papel no arco: Virada: espiral, breu e o primeiro estrobo; o vermelho toma a sala.
- Chegada: c. 25 (drop, +12.0 dB): `rows-up` azul-profundo.
- Pico: `virada`, c. 49 (+22.0 dB): breu no c. 48, estrobo, fita branca, `solid` vermelho a 1/8.
- Família de looks: a espiral (c. 41-47), `breu`, `pulso-vermelho`; lustre vermelho.
- Entrega: `pulso-vermelho` do G (c. 89) por 16 compassos (c. 89-104), copiada na ponte da Verano (c. 9-24 dela). A Verano abre então um capítulo novo, c. 25-41 dela: o primeiro drop segue, sem voz (o kick para no c. 40, antes do break do c. 42). É o Pico começando: a Verano assume com o seu drop, vermelho e azul dividindo a sala, sem o `zigzag` vermelho da chegada (c. 58). O eco leva o capítulo para o TOO COOL nos c. 105-118.

### 12. Toman — Verano En NY
- Energia: e8; abre o pico a 128.
- Papel no arco: Pico: vermelho e azul dividem a sala.
- Chegada: c. 58 (drop, +11.7 dB): `zigzag` vermelho a 1/8.
- Pico: a chegada, c. 58-73.
- Família de looks: `pulso-vermelho`, `zigzag`, `sweep` entre os lados no groove (c. 74-89); lustre vermelho, `dark` no break e na subida.
- Entrega: `pulso-vermelho` do G (c. 90) por 16 compassos (c. 90-105), copiada na ponte do Pick Up (c. 27-42 dele). O Pick Up abre então um capítulo novo e longo, c. 43-68 dele: o break sem kick (c. 43-64; o grave segura e a voz do Nate Dogg entra a partir do c. 49) e o drop curto dos c. 65-68 (+17.8 dB, uma fronteira forte que a luz de hoje não acompanha e que pede uma seção nova, abaixo da chegada), antes da subida do c. 69 e da chegada do c. 73. A contraluz já está gasta: a do Pick Up é a dos c. 104-127. O eco leva o capítulo para a Verano nos c. 106-130.

### 13. PAWSA, Nate Dogg — PICK UP THE PHONE (feat. Nate Dogg) (Extended)
- Energia: e8; o maior drop da noite.
- Papel no arco: o pico da noite.
- Chegada: c. 73 (drop, +30.2 dB): `rows-up` vermelho com `pingpong` a 1/8.
- Pico: `pick-up`, c. 137 (o drop nº 1 da noite em saliência): estrobo, fita branca, `blink` vermelho, Vorlanes a 1/16.
- Família de looks: `contraluz` (c. 104-127), a espiral (c. 128-136), `pico-pick-up`; lustre vermelho.
- Entrega: `pico-pick-up` do G (c. 137), o pico, copiado na ponte do Can't Decide (c. 20-27 dele, o drop dele). O Can't Decide cai no break no c. 28 (c. 28-35, kick 0), e a janela segue a música que entra: a entrega termina com a ponte, c. 137-144 (`until: 145`), e o cue `break` do Can't Decide (c. 28-35) fica onde sempre esteve: ele é a luz da própria música ali, e não há capítulo novo. O pico do Pick Up dura 8 compassos nos dois scripts, de propósito; depois dele a sala vê a luz do Can't Decide, mesmo com o Pick Up ainda no drop. O eco leva o Can't Decide do c. 28 em diante (o break, o grave que volta no c. 36, a chegada do c. 44, a subida, o breu do c. 68 e o pico do c. 69, sem o estrobo) para o Pick Up nos c. 145-193.

### 14. Max Dean, Luke Dean, LOCKY — Can't Decide
- Energia: e8; o último breu e o pico que o Dirty Cash herda.
- Papel no arco: o pico continua, curto e intenso.
- Chegada: c. 44 (o grave volta no c. 36): `centre-out` vermelho a 1/16.
- Pico: `cant-decide`, c. 69 (+45.4 dB), depois do breu do c. 68: estrobo, `blink` vermelho.
- Família de looks: `pico-pick-up` na ponte (c. 20-27); o cue `break` (c. 28-35: movings em `hold` vermelho na coluna a 0.4, Vorlanes `off`, lustre `dark`); `o-grave-volta` (c. 36-43: movings em `hold` vermelho no centro, `rows-up` vermelho); `centre-out`, `pico-cant-decide`; lustre vermelho nos drops, `dark` nos breaks.
- Entrega: `pico-cant-decide` do G (c. 69), o drop com estrobo, por 14 compassos (c. 69-82, `until: 83`), copiada na ponte do Dirty Cash (c. 17-30 dele): o Dirty Cash entra por baixo do pico, e o drop do c. 25 fica dentro da ponte. A ponte acaba no break de 2 compassos do c. 31, uma fronteira do mapa que o capítulo escolheu: o corte escuro dos c. 31-32 faz o drop do c. 33 pousar. O Dirty Cash abre então um capítulo novo, c. 31-42 dele: o corte, o drop dos c. 33-38 e o break (c. 39-42: o kick para e a voz entra), antes da subida do c. 43 e da chegada do c. 45. O estrobo do Dirty Cash é o dos c. 57 e 113 (orçamento gasto). O eco leva o capítulo para o Can't Decide nos c. 83-94. O capítulo não repete a forma da abertura do Can't Decide (break com feixe parado, depois `hold` no centro com linhas nas Vorlanes).

### 15. PAWSA, Adventures Of Stevie V — Dirty Cash (Money Talks)
- Energia: e9; o fim do pico, a 132.
- Papel no arco: gasta o que sobrou e termina só no coração.
- Chegada: c. 45 (drop, +15.7 dB): `arrow-up` vermelho.
- Pico: `dirty-cash`, c. 57 (+42.6 dB, estrobo no 1), e o `final`, c. 113-119 (rolo de estrobo, fita branca, `flash`).
- Família de looks: `blink` vermelho, `solid`, `hold` na poça e na cabine nos cortes; lustre vermelho, carmim no fim.
- Entrega: nenhuma; a última nota (c. 120-121) deixa só o lustre aceso, em carmim.

## O que fica para a próxima versão
- **Espiral de verdade**, **coração com decaimento** (um "tum-tum" duplo, o pulso que some antes
  do próximo), **feixe que respira com a voz**, **Vorlanes como equalizador** (uma faixa de
  linhas por instrumento) e **estéreo vira sala**: vocabulário novo, projeto B, com os dados que
  os mapas musicais já guardam (vozes por passo, batidas, registro, estéreo).
- **Quando o SoundSwitch troca de script na mixagem** ainda não foi testado. A ponte foi feita
  para funcionar em qualquer compasso; o teste (P1) entra junto com o X1b, e o do lustre
  acompanhando o pulso (P3) também.
