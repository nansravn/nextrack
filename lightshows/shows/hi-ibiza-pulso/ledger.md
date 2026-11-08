# Diário do time — hi-ibiza-pulso

## 2026-11-08 — Pontes de até 16 compassos sem perder a história
Pedido: "Hï Ibiza: pontes de até 16 compassos, sem perder a história."
Tipo: retrabalho de unidades (13 mixagens) · ramo: feat/show-hi-ibiza-pulso-pontes · execução: 2026-11-08-0658
Estimativa: 1 leitura + 13 unidades × até 3 rodadas + 5 críticos × até 2 passadas + 4 comparações = até ~54 despachos, mais revisões
Diagnóstico: treze passagens passam de 16 compassos (23 avisos `bridges`), com entregas de 20 a 56 compassos e pontes de 18 a 42. Com `bridge.bars: 16`, o compilador corta cada entrega em 16 compassos e o eco copia, no resto da música que sai, a luz da que entra. Onze músicas que entram precisam de um capítulo novo entre o fim da ponte (B + 15) e o seu primeiro cue de hoje: Akan, What To Do, We Dance Again, Trippy Yeah, Baianá, Ma Tnsani, Yamore, Move, Verano, Pick Up e Dirty Cash. Em duas passagens (mix-06, mix-14) a ponte é mais curta que a entrega, e elas precisam alinhar a janela.
Contrato: `compare --keep arrivals,moments` contra o show de partida (3211f74); o aviso `signatures` continua em zero (hoje azul-espaco 86% ≥ 70% e coracao 80% ≥ 60%).
Unidades: mix-02 0/3, mix-03 0/3, mix-04 0/3, mix-05 0/3, mix-06 0/3, mix-07 0/3, mix-08 0/3, mix-09 0/3, mix-10 0/3, mix-12 0/3, mix-13 0/3, mix-14 0/3, mix-15 0/3

### Decisões
- `bridge.bars: 16` no `show.yml`, como o dono pediu; as intenções de ponte e de entrega passam a dizer "por até 16 compassos" (custo se errado: só o texto das intenções).
- A entrega termina onde a ponte termina: no relógio, o B da que entra cai sobre o G da que sai, e uma entrega de tamanho diferente da ponte mostra duas luzes no mesmo compasso, conforme o script que o SoundSwitch tocar (P1 ainda não foi testado). O `until` da entrega é G + (primeiro cue da que entra − B); com o capítulo novo em B + 16, é o padrão de 16 compassos (custo se errado: entregas mais curtas que 16 compassos em mix-06 e mix-14, sem ganho nenhum se o SoundSwitch seguir o fader).
- Andaime: com qualquer achado `show-source`, nem `build` nem `report` funcionam, e `bridge.bars: 16` sozinho deixa 22 deles em 13 unidades. Para a noite compilar entre os lotes, o diretor tirou o `until` das 11 entregas que passavam da janela e pôs um cue provisório, `capitulo-a-escrever` em B + 16, nas 11 músicas que entram, com o look da ponte: a mesma luz de antes. Cada designer substitui o seu na rodada 1, e nenhum pode ser entregue (custo se errado: um andaime esquecido zera o aviso `bridges` sem mudar a luz; o diretor confere com grep antes da entrega).
- Leitura a frio: as 12 perguntas do leitor foram respondidas no plano de luz. O eco copia tudo o que a música que entra mostra naquele trecho, chegada, breu e espiral incluídos, sem estrobo nem fita, e nunca conta no orçamento. A luz do capítulo novo tem regra: movings azul-gelo, desenho de Vorlane diferente da ponte e da chegada, lustre `dark` nos breaks em todas as fases, abaixo da chegada. As fronteiras fortes são as `sections` do mapa e os "missed" do `follows`. Os intervalos "c. a-b" incluem os dois compassos (custo se errado: designers com três regras a mais do que o pedido dizia).
- mix-14 (Pick Up → Can't Decide): o pico atravessa a janela inteira dos dois lados (entrega c. 137-152, ponte c. 20-35 do Can't Decide), e o cue `break` do Can't Decide (c. 28-35) sai. Nesses compassos o drop do Pick Up segue cheio enquanto o Can't Decide está no break, e a sala ouve o pico (custo se errado: o Can't Decide perde oito compassos de break antes do grave voltar no c. 36).
- mix-07 (Say What → Baianá): a entrega vai até o último compasso da Say What (c. 79-91, `until: end + 1`), e a ponte da Baianá vai até o c. 37, o último em que as duas tocam juntas. O capítulo novo começa no c. 38 (custo se errado: nenhum além de cinco compassos de capítulo curto).

### Para depois

### Estado
- Estado: fase 0 (entrada) concluída — 2026-11-08 06:59
- Estado: fase 1 (insumos) concluída — 2026-11-08 07:00
- Estado: fase 2 (diagnóstico) concluída — 2026-11-08 07:08
- Estado: fase 3 (leitura a frio) concluída — 2026-11-08 07:19
