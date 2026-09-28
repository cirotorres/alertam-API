# Handoff seguro — SPECs 022 e 023

**Data:** 2026-09-28  
**Objetivo:** permitir retomada em nova sessão sem perder decisões, misturar branches ou iniciar implementação cedo demais.

## Estado geral

Nenhuma implementação das SPECs 022/023 foi iniciada.

Foram produzidos somente documentos de design e atualização do índice de specs no repositório API/PWA.

O próximo gate é **revisão humana das duas specs escritas**.  
Somente depois de aprovação explícita deve ser usado `superpowers:writing-plans`.

## Repositórios

### AlertaM Desktop

- caminho: `/home/ciro/dev/prog/alertamaritimo`
- branch: `develop`
- HEAD no handoff: `15dfe5c Feat: Alerta desktop informa conclsão de manobra e modificações.`
- árvore: limpa

### AlertaM API/PWA

- caminho: `/home/ciro/dev/prog/alertamaritimoAPI`
- branch: `feat/api-bootstrap`
- HEAD no handoff: `06c87a0 Fix: bug fixes imagens PWA`
- alterações documentais não commitadas:
  - `M specs/README.md`
  - `?? specs/022-alert-details-maneuver-timeline.md`
  - `?? specs/023-ship-tracking.md`
  - este handoff também será não commitado

Não resetar, rebasear ou descartar essas alterações.

## Documentos novos

### SPEC 022

`/home/ciro/dev/prog/alertamaritimoAPI/specs/022-alert-details-maneuver-timeline.md`

Tema:
- Alertas clicáveis;
- `AlertDetailSheet`;
- deep link de push abrindo diretamente o detalhe;
- timeline por `maneuver_id`;
- POB vigente × conclusão observada;
- diferenças antes → depois;
- detalhe equivalente no Desktop;
- ledger local de ManeuverEvent separado do outbox.

### SPEC 023

`/home/ciro/dev/prog/alertamaritimoAPI/specs/023-ship-tracking.md`

Tema:
- Ship Tracking baseado no WebPilot;
- `VesselTrackingEvent`;
- tracking individual por instalação PWA;
- tracking local independente no Desktop;
- push seletivo;
- página Acompanhados;
- timeline unificada.
## Dependências canônicas

Ler antes de planejar:

- `specs/021-maneuver-events-webpush.md`
- `specs/022-alert-details-maneuver-timeline.md`
- `specs/023-ship-tracking.md`
- Desktop:
  `/home/ciro/dev/prog/alertamaritimo/docs/superpowers/specs/2026-09-27-ciclo-manobras-eventos-push-design.md`

A SPEC 023 depende conceitualmente da 022, porque reutiliza timeline, detalhes e apresentação de eventos.

Ordem recomendada de implementação:
1. SPEC 022;
2. validação;
3. SPEC 023.

## Decisões fechadas — SPEC 022

Cada item de Alertas no PWA será clicável em toda a área útil.

O clique abre uma gaveta própria de alerta, separada da `VesselSheet`, mas reutilizando:
- backdrop;
- drag handle;
- swipe para baixo;
- elasticidade para cima;
- scroll interno;
- safe-area do iOS.

A URL continuará usando:
`/alertas?event=<event_id>`.

O query param passa a representar o alerta aberto, não apenas um destaque visual.
Push e aviso interno de foreground devem abrir a mesma gaveta automaticamente.

O detalhe deve exibir:
- navio/IMO;
- tipo da manobra;
- evento selecionado;
- berço;
- POB vigente;
- horário observado/confirmado;
- primeira observação candidata quando disponível;
- diferença temporal segura;
- timeline completa retida daquele `maneuver_id`.

Para COMPLETED, usar linguagem como:
- “Conclusão observada pelo AlertaM”;
- “Horário aproximado baseado na atualização da planilha”.

Nunca afirmar que `occurred_at` é o segundo físico exato da manobra.

Extensão proposta de `ManeuverEvent`:
- `pob_at: ISO-8601 aware | null`;
- `first_observed_at: ISO-8601 aware | null`.

`pob` textual continua preservado.

Se o POB não puder ser convertido com segurança:
- manter texto;
- `pob_at=null`;
- não calcular diferença no frontend.
O Desktop deve manter um ledger local recente de ManeuverEvent separado do outbox.

ACK remoto:
- remove do outbox;
- não remove do ledger.

Retenção local e cloud de eventos:
- 30 dias.

Baseline não ganha CONFIRMED retroativo.

No Desktop, duplo clique em manobra/histórico abre janela “Detalhes da manobra”.

A SPEC 022 não altera regras de voz/chime/push existentes.

## Decisões fechadas — SPEC 023

Ship Tracking significa acompanhar alterações observadas no WebPilot.

Não é:
- AIS;
- GPS;
- posição geográfica em tempo real;
- MarineTraffic/VesselFinder.

O tracking permanece ativo no MVP até o usuário cancelar manualmente.

Exceções:
- Esquecer este aparelho;
- rotação/revogação de VIEW_SECRET;
- revogação explícita de segurança da instalação.

Expiração normal do cookie não cancela tracking.
Tracking PWA é individual por instalação.

Um celular acompanhar um navio não ativa tracking nos outros celulares.

Tracking local do Desktop é independente das preferências dos celulares.

Identidade:
1. IMO válido;
2. fallback por nome normalizado.

Não usar fuzzy matching.

Se um navio inicialmente acompanhado por nome ganhar IMO válido com match exato do nome normalizado,
a identidade pode ser promovida para IMO.

## VesselTrackingEvent

Novo contrato complementar ao `ManeuverEvent`.

Campos conceituais:
- `event_id`;
- `vessel_identity`;
- `vessel_imo`;
- `vessel_name`;
- `occurred_at`;
- `first_observed_at`;
- `maneuver_id | null`;
- `changes`;
- `current`.

Campos operacionais elegíveis no MVP:
- presence;
- status;
- section;
- berth;
- side;
- eta;
- etb_ets;
- pob.
Mudanças simultâneas confirmadas produzem um único VesselTrackingEvent com múltiplos campos.

O detector remoto do Desktop produz eventos elegíveis para **todos os navios observados**.

Ele não consulta favoritos dos celulares.

A API cruza cada evento com `tracked_vessels` por instalação.

Isso mantém Desktop e PWA desacoplados.

## Ledger local de tracking

VesselTrackingEvent deve possuir ledger local recente separado da outbox:
- inserir no ledger junto da mesma persistência atômica de estado + outbox;
- ACK remoto remove somente da outbox;
- retenção local de 30 dias;
- timeline Desktop usa o ledger mesmo depois do envio bem-sucedido;
- baseline/restart não inventam eventos retroativos.

## Anti-duplicação

ManeuverEvent continua sendo a autoridade semântica para manobras.

Se uma mudança já está coberta por ManeuverEvent, não criar VesselTrackingEvent equivalente.

Exemplos já cobertos por ManeuverEvent:
- POB/berço durante manobra ativa;
- confirmação de atracação/desatracação;
- conclusão;
- cancelamento.

Mudanças residuais simultâneas, como ETA/ETB/ETS/bordo, podem gerar VesselTrackingEvent somente com os campos não cobertos.

Timeline do tracking mistura:
- ManeuverEvent;
- VesselTrackingEvent.

Não criar timelines separadas.
## Push de tracking

Tracking é uma intenção de notificação separada das quatro categorias gerais da SPEC 021.

Para ManeuverEvent:
- categoria geral ligada torna elegível;
- OU tracking ativo daquele navio torna elegível;
- se ambos forem verdadeiros, enviar somente **um** push.

Se Web Push estiver globalmente desativado para a instalação:
- tracking permanece salvo;
- timeline continua disponível;
- nenhum push é enviado.

Para VesselTrackingEvent:
- somente instalações que acompanham aquele navio são elegíveis.

Deep link determinístico:
- VesselTrackingEvent → /acompanhados?track=<tracked_vessel_id>&event=<event_id>;
- ManeuverEvent elegível somente por tracking → /acompanhados?track=<tracked_vessel_id>&event=<event_id>;
- ManeuverEvent elegível pela categoria geral → /alertas?event=<event_id>;
- categoria geral + tracking simultâneos → um único push, mantendo /alertas como destino canônico.

Sem replay:
- `occurred_at < started_at` não gera push.

Tracking não expira automaticamente.

## Relação com SPEC 021

A SPEC 021 deixou “push para alteração de previsão” fora do escopo.

A SPEC 023 passa a permitir ETA/ETB/ETS e outras mudanças de previsão **somente para navio explicitamente acompanhado**.

As quatro categorias gerais da SPEC 021 não passam a notificar ETA/ETB/ETS globalmente.
## Desktop — Ship Tracking

Adicionar à ficha:
- ☆ Acompanhar navio;
- ★ Acompanhando.

Adicionar acesso discreto:
- ⭐ Acompanhados.

Janela local deve mostrar:
- nome;
- IMO;
- último status;
- berço;
- POB;
- visto por último;
- presente/ausente;
- Parar de acompanhar.

A estrela é marcador adicional e não substitui vermelho/verde das manobras.

Mudanças comuns de ETA/ETB/ETS no Desktop ficam visuais no MVP.

Não adicionar voz/chime para cada atualização de tracking.

## PWA — Ship Tracking

Adicionar botão de acompanhar:
- na `VesselSheet`;
- na `AlertDetailSheet` da SPEC 022.

Adicionar página:
- Acompanhados.

Navio ausente continua listado e acompanhado.

Deep link de tracking deve levar ao contexto/timeline do navio.
## Reinício e baseline

Primeira coleta sem estado:
- semear baseline;
- zero evento retroativo.

Após restart com estado persistido:
- reconciliar a primeira coleta válida;
- não produzir enxurrada de eventos pelo período de downtime;
- continuar a partir das mudanças seguintes.

Snapshot inválido, timeout, login expirado ou falha de coleta nunca significa desaparecimento em massa.

Presence false/true exige observação válida e debounce.

## Retenção

- ManeuverEvent: 30 dias;
- VesselTrackingEvent: 30 dias;
- tracking ativo: sem TTL no MVP.

Falha permanente do provedor push não apaga a intenção de tracking.

Se a instalação recuperar subscription válida, tracking continua.

## Estado de produção relevante

O Web Push real já foi confirmado pelo usuário como funcionando normalmente antes deste brainstorm.

Um incidente anterior de “sem push” foi diagnosticado como Desktop antigo ainda em execução,
carregado antes do pipeline de ManeuverEvent. Não era falha do PWA/provedor.

Não usar os antigos contadores de banco daquele diagnóstico como estado atual de produção.
## QR/configuração Desktop

Houve também um problema de desenvolvimento em que o Desktop iniciou sem carregar o `.env`
e desabilitou a sincronização mobile/QR.

O fluxo foi corrigido no Desktop para carregar o `.env` do checkout em execução não-frozen,
sem sobrescrever variáveis já exportadas.

Nunca colocar no handoff ou logs:
- valores de `ALERTAM_DEVICE_SECRET`;
- `VIEW_SECRET`;
- cookies;
- endpoint completo de PushSubscription;
- VAPID private key;
- conteúdo de arquivos `.env`.

Se precisar diagnosticar configuração, verificar apenas presença/ausência.

## Auto-revisão das specs

Executada em 2026-09-28.

Resultado:
- sem headings H2 duplicados;
- sem placeholders reais TBD/FIXME;
- o scanner encontrou “TODO” apenas dentro de palavras portuguesas como “todos”;
- `git diff --check` limpo;
- relação 021 → 023 explicitada;
- detector remoto desacoplado dos favoritos locais;
- comportamento de falha de push não apaga tracking;
- diferença temporal da SPEC 022 é omitida quando dado anterior não é confiável.
## Gate obrigatório da próxima sessão

Não começar implementação imediatamente.

Sequência:

1. conectar Remote Desktop;
2. executar `git status --short --branch` nos dois repositórios;
3. confirmar que os arquivos não commitados das specs continuam presentes;
4. ler integralmente SPEC 022;
5. ler integralmente SPEC 023;
6. reler SPEC 021 e o design canônico cross-repo;
7. pedir ao usuário revisão/aprovação das **specs escritas**;
8. somente após aprovação, invocar `superpowers:writing-plans`.

A aprovação anterior foi do **design conversacional**.

Pelo fluxo do Superpowers, ela permitiu escrever as specs, mas não permite pular o gate de revisão dos documentos escritos.

## Writing-plans

Criar planos separados.

Primeiro:
`docs/superpowers/plans/2026-09-28-alert-details-maneuver-timeline.md`

Depois, somente quando apropriado:
`docs/superpowers/plans/2026-09-28-ship-tracking.md`

SPEC 023 deve assumir interfaces entregues pela SPEC 022, não duplicá-las.
## Regras de execução futuras

Toda implementação:
- TDD RED → GREEN → REFACTOR;
- revisão após tarefas/fases;
- gates completos Desktop/API/frontend conforme impacto;
- UI Desktop com Xephyr quando aplicável;
- Playwright para PWA quando aplicável;
- `git diff --check`;
- auto-revisão final.

Não fazer commit/push automaticamente.

Obter autorização explícita do usuário antes de commit/push, preservando o padrão atual do projeto.

Não resetar/rebasear mudanças existentes sem consentimento.

Se o estado da branch divergir do handoff, parar e reconciliar antes de escrever código.

## Segurança cross-repo

Desktop continua sendo autoridade semântica.

API:
- persiste;
- autentica;
- filtra por instalação/device;
- despacha push;
- não redetecta WebPilot.

PWA:
- read-only operacional;
- nunca cria ManeuverEvent;
- nunca cria VesselTrackingEvent.

Nenhum segredo deve entrar em payload de feed, timeline ou UI.
## Ponto exato de retomada

As specs foram escritas e auto-revisadas.

Ainda falta:
- revisão/aprovação humana das SPECs 022 e 023;
- writing-plans;
- escolha do método de execução;
- implementação.

Não há código de SPEC 022/023 para continuar.

A árvore Desktop estava limpa neste handoff.

A árvore API/PWA contém somente documentos desta etapa.

## Comandos seguros iniciais

Desktop:

```bash
cd /home/ciro/dev/prog/alertamaritimo
git status --short --branch
git log -1 --oneline
```

API/PWA:

```bash
cd /home/ciro/dev/prog/alertamaritimoAPI
git status --short --branch
git log -1 --oneline
```

Não executar comandos que mostrem `.env` ou segredos.
