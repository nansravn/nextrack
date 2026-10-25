---
name: Halloween em Casa — EDM, Brasilidades e Funk
date: 2026-10-31
venue: Casa (festa de Halloween)
crowd: ~20 convidados, amigos, fantasiados
duration: 4h
arc: waves                 # single-peak | waves | slow-burn
default_style: hybrid      # continuous | open-format | hybrid (blocks may override)
energy: [5, 9]
---

## Brief
Festa de Halloween em casa no sábado, 31/10, para ~20 convidados. O pedido: EDM,
brasilidades e terminar com funk; os must-plays são música de Halloween e Piratas do
Caribe. Horário assumido: 21:00–01:00. O programa tem 3h40, e os 20 min de folga
cobrem as faixas da lista de compras, uma pausa e pedidos. A sala é pequena: volume
de conversa na chegada, e o lightshow é o interruptor da sala.

## Program
1. 21:00 · [Halloween — Chegada Sombria](../blocks/halloween-chegada.md)                · 40m · e5→6
2. 21:40 · [EDM Assombrado — Caça-Fantasmas](../blocks/edm-assombrado.md)              · 40m · e7→9  ← pico 1 · 🏴‍☠️ piratas entre o 5 e o 6
3. 22:20 · [Brasilidades Eletrônicas](../blocks/brasilidades-eletronicas.md)           · 30m · e6→8
4. 22:50 · [Axé Clássicos](../blocks/axe-classicos.md)                                 · 45m · e8    ← pico 2 (Festa)
5. 23:35 · [Funk Anos 2000 — Um Morto Muito Louco](../blocks/funk-anos-2000-morto-muito-louco.md) · 25m · e7→8
6. 00:00 · [Funk-Pop — Festa Brasileira](../blocks/funk-pop-festa.md)                  · 40m · e7→9  ← pico 3, fecha no mandelão

Ajustes desta festa nos blocos reaproveitados:
- **Axé Clássicos** entra pelo #1 (Voa Voa), num corte seco de Make U Sweat — Eva, e
  não pela ponte do pagodão. A Eva original (#8) vira callback do slap house de meia
  hora antes. Troca o #13 (Quero Chiclete) por Asa de Águia — Xô Satanás. Sai do #14
  (Macetando) direto pro Um Morto Muito Louco.
- **Funk-Pop — Festa Brasileira** fica como está: fecha em Pedro Sampaio — Sequência
  Feiticeira, a feiticeira que encerra o Halloween.

## Journey (off the genre graph)
deep-house → nu-disco-funk → pop-dance → rock → pop-dance → tech-house-br →
tech-house → brazilian-bass → tech-house-br → axe → funk-anos-2000 → funk-pop

Uma edge nova veio com este set: `tech-house-br → axe` (Make U Sweat — Eva → Voa
Voa), a volta da edge `axe → tech-house-br` que já existia.

## Halloween e piratas: onde estão
Do pool, já tocável:
- **Chegada:** Eurythmics — Sweet Dreams (Steve Angello Remix) · Warren Zevon — Werewolves Of London
- **EDM Assombrado:** Tony Igy — Astronomia (o meme do caixão) · Dubdogz — Ghostbusters · Dubdogz & Ten Tonne Skeleton — Psycho Killer · Chris Lake — Turn Off The Lights (a luz apaga)
- **Brasilidades:** Alok, Titãs — Epitáfio (de leve)
- **Axé:** Asa de Águia — Dança do Vampiro (#3) · Asa de Águia — Xô Satanás (troca do #13)
- **Funk:** DJ Marlboro — Um Morto Muito Louco · Pedro Sampaio — Sequência Feiticeira

Piratas: **nenhuma faixa no pool.** Billy Ocean — Caribbean Queen, na Chegada, é só
uma piscadela. Os piratas de verdade estão na lista de compras abaixo, e Thriller
também.

## Lista de compras (fora dos pools)
Ficam fora de `tracks/` até serem baixadas. Depois de baixar: entrada no pool certo
com `bpm` e `key` em `null`, `uv run scripts/nextrack_tags.py pull-bpm --root <biblioteca> --apply`,
revisão com `git diff tracks`, e aí a faixa vira linha numerada no bloco.

| # | Faixa | Prioridade | Encaixe | Por quê |
|---|---|---|---|---|
| 1 | Klaus Badelt — He's a Pirate (Tiësto Remix) | essencial | EDM Assombrado, entre o 5 e o 6 | O must-play pirata em versão de pista, do EP *Pirates Remixed* (2006). O Radio Edit (4:05) basta; o Club Mix (7:03) dá blend longo. |
| 2 | Klaus Badelt — He's a Pirate (trilha original, 2003) | essencial | Mesmo slot: 30–60 s do tema sem batida antes do drop do Tiësto | O tema que todo mundo reconhece nos primeiros compassos. |
| 3 | Michael Jackson — Thriller | essencial | Chegada, depois do 7 (Werewolves); corte pro Astronomia | O hino de Halloween que falta no pool, com a coreografia zumbi. |
| 4 | deadmau5 feat. Rob Swire — Ghosts 'n' Stuff | extra | EDM Assombrado, depois do 2 (Ghostbusters) | Clássico de EDM com tema de fantasma. |
| 5 | Rihanna — Disturbia | extra | EDM Assombrado, no lugar do 4 (Buggin') | Pop dance sombrio que todo mundo canta. |
| 6 | Rockwell — Somebody's Watching Me | extra | Chegada, entre o 5 e o 6 | Clássico de Halloween dos anos 80. |
| 7 | DJ K — álbum *Pânico no Submundo* (2023) | experimental | Funk-Pop Festa, perto de Sequência Feiticeira | Funk bruxaria: mandelão com samples de terror. É pesado, então vale ouvir antes de comprar. |

## Contingencies
- **Casa enchendo devagar:** estica a Chegada com os swaps de deep e segura o 5–7 até
  a sala encher. O uivo de Werewolves precisa de gente.
- **Pista fria pro EDM:** toca o 1 e o 2 do EDM Assombrado, faz o momento pirata logo
  depois e corta pras Brasilidades.
- **Pedido de mais brasilidade:** depois do axé entra o
  [Pagodão Anos 90](../blocks/pagodao-anos-90.md) (35m; axe → pagodao-baiano →
  funk-anos-2000), e o funk começa perto de 00:10. Corta o fim do Funk-Pop pra caber.
- **Concurso de fantasia:** entre o axé e o funk (~23:35), com fundo baixo usando os
  swaps da Chegada. Volta com Um Morto Muito Louco: o morto ressuscita a pista.
- **Saideira:** depois de Sequência Feiticeira, se ainda tiver pista, funk 150
  (MC Kevin o Chris — Medley da Gaiola · Evoluiu). Se a galera estiver indo embora,
  MC Leozinho — Tô Tranquilão de última. Termina no funk de qualquer jeito.

## After-action (preencher depois da festa)
- O que funcionou, o que não funcionou, e qual pico foi o maior.
- Reavaliar a edge nova `tech-house-br → axe`: se o corte Eva → Voa Voa funcionou,
  sobe pra `strong`; se morreu, rebaixa.
- O momento pirata e o Astronomia de abertura do EDM: funcionaram como meme ou só
  quebraram o fluxo?
