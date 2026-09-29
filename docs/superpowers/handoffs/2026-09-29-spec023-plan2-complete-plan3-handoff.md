# Handoff — SPEC 023 Plano 2 concluído → Plano 3

Data: 2026-09-29

## Objetivo da próxima sessão

Continuar a SPEC 023 **Ship Tracking** a partir do **Plano 3 — Desktop & PWA UX**.

Os Planos 1 e 2 estão concluídos e validados. O Plano 3 ainda não foi iniciado.

Repositórios:
- Desktop: `/home/ciro/dev/prog/alertamaritimo`
- API/PWA: `/home/ciro/dev/prog/alertamaritimoAPI`

Leia primeiro:
1. este handoff;
2. `specs/023-ship-tracking.md`;
3. `docs/superpowers/plans/2026-09-28-ship-tracking-overview.md`;
4. `docs/superpowers/plans/2026-09-28-ship-tracking-ux.md`.

Use Remote Desktop Commander + Superpowers.
Execução esperada: Native/TDD, seguindo a mesma estratégia dos Planos 1 e 2.
Não faça push.
Commits locais somente conforme autorização explícita de Ciro.

## Estado Git esperado

### API/PWA
Branch:
`feat/api-bootstrap`

Checkpoints do Plano 2:
- `445e0af Feat: adiciona instalações e acompanhamentos por aparelho`
- `34f273c Feat: adiciona timeline e feed de acompanhamento`

Após o fechamento desta sessão, o HEAD deve ter o assunto:
`Feat: conclui Plano 2 da SPEC 023 - Installations & Dispatch`

Não houve push dos commits do Plano 2.

Existe um arquivo documental antigo da SPEC 022 que deve ser preservado e não incluído por acidente:
`docs/superpowers/plans/2026-09-28-alert-details-maneuver-timeline.md`

### Desktop
Branch esperada:
`develop`

O Plano 2 não exigiu mudanças no Desktop.
Não fazer reset/rebase nem descartar mudanças locais caso o estado observado seja diferente.

Antes de alterar código:
- rodar `git status --short --branch` nos dois repos;
- confirmar que o Plano 3 ainda não foi iniciado;
- preservar qualquer arquivo não rastreado que não pertença à SPEC 023.

## O que o Plano 2 entregou

### 1. Identidade de instalação mobile independente do Web Push

A sessão mobile agora representa:
`device_id + installation_id`

`installation_id` é estável e existe mesmo se o usuário nunca habilitar notificações.

Migration:
`010_mobile_installations.sql`

Garantias:
- mesma instalação não pode migrar entre devices;
- cookies antigos sem installation_id são rejeitados;
- pairing/frontend cria ou restaura installation_id;
- `Esquecer aparelho` revoga a instalação;
- rotação de VIEW_SECRET revoga instalações;
- mobile_installations existentes são backfilled a partir de push_installations.

### 2. tracked_vessels por instalação

Migration:
`011_tracked_vessels.sql`

Endpoints:
- `GET /api/v1/mobile/tracked-vessels`
- `POST /api/v1/mobile/tracked-vessels`
- `DELETE /api/v1/mobile/tracked-vessels/{tracked_vessel_id}`
- `GET /api/v1/mobile/tracked-vessels/{tracked_vessel_id}/events`

Regras:
- o cliente nunca escolhe installation_id; vem da sessão;
- start é idempotente por instalação/navio;
- alvo precisa existir no snapshot atual ou em evento retido;
- GET lista somente trackings ativos;
- stop não apaga registro histórico;
- tracking parado pode continuar servindo timeline histórica;
- NAME→IMO promove o mesmo tracking apenas por nome normalizado exatamente igual;
- sem fuzzy matching;
- rotação de VIEW_SECRET e revogação da instalação desativam trackings ativos.

### 3. Projeção atual e timeline unificada

`VesselTrackingEvent` substitui a projeção operacional completa do tracking.

`ManeuverEvent` atualiza de forma conservadora apenas os campos que conhece com segurança:
- berth;
- pob;
- pob_at.

Evento antigo nunca pode regredir `current` ou `last_seen_at`.

Timeline unificada mistura:
- ManeuverEvent;
- VesselTrackingEvent.

Ordenação:
1. occurred_at;
2. ingested_at;
3. event_id.

Eventos anteriores ao início do tracking podem aparecer como contexto na timeline, mas não geram replay de push.

### 4. Feed agregado foreground

Endpoint:
`GET /api/v1/mobile/tracked-vessels/events`

Características:
- installation-scoped;
- somente VesselTrackingEvent;
- cursor de ingestão crescente;
- montagem inicial retorna baseline sem replay;
- elegibilidade: `occurred_at >= started_at`;
- tracking parado não recebe eventos novos;
- eventos irrelevantes podem avançar o cursor sem aparecer na lista;
- Postgres/Supabase usam caminho agregado sem N requests por tracking.

O Plano 3 deve consumir esse feed via polling de 30 s no TrackingProvider.

## ManeuverEvent + tracking sem push duplicado

Tracking amplia elegibilidade de ManeuverEvent.

Para cada PushInstallation:
- categoria geral ON → elegível;
- categoria geral OFF + tracking ativo → elegível;
- categoria geral ON + tracking ativo → **um único push**.

Deep link:
- categoria geral elegível → `/alertas?event=<event_id>`;
- elegível apenas por tracking → `/acompanhados?track=<tracked_vessel_id>&event=<event_id>`.

Importante:
o caminho de categoria geral foi mantido independente do lookup de tracking.
Uma falha/ausência no tracking lookup não deve quebrar o comportamento Web Push já existente da SPEC 021.

Fronteira temporal:
- `occurred_at < started_at` não torna tracking elegível;
- `occurred_at == started_at` é elegível.

## Web Push de VesselTrackingEvent

Migration:
`012_vessel_tracking_deliveries.sql`

Tabela separada:
`vessel_tracking_deliveries`

Chave:
`event_id + installation_id`

Estados:
- SENDING
- DELIVERED
- IGNORED_FOREGROUND
- IGNORED_BEFORE_TRACKING
- RETRY_PENDING
- PERMANENT_FAILURE

Dispatcher separado:
`TrackingPushDispatchService`

Regras:
- somente instalações com PushSubscription ativa **e** tracking ativo do navio são candidatas;
- preferências gerais de ManeuverEvent não se aplicam;
- foreground recente suprime Web Push do sistema;
- falha de uma instalação não bloqueia outra;
- permanent push error desativa apenas PushInstallation, não tracked_vessel;
- reativar push não reenvia evento antigo;
- disappearance usa linguagem observacional: o navio “não aparece mais na planilha”; nunca inferir “desatracou”;
- deep link sempre `/acompanhados?track=...&event=...`.

O dispatch do VesselTrackingEvent ocorre apenas quando o ingest retorna **accepted**.
Retry idempotente do Desktop retorna `idempotent` e não redispara o push.

## Revogação e segurança

`installation_id` continua existindo independentemente de PushSubscription.

Quando PushSubscription falha permanentemente:
- push fica inativo;
- tracking permanece salvo;
- timeline continua disponível.

Quando usuário usa **Esquecer aparelho** ou ocorre rotação do VIEW_SECRET:
- mobile_installation é revogada;
- tracked_vessels ativos daquela instalação são desativados;
- deliveries futuros deixam de ser candidatos.

Uma instalação nunca pode consultar/alterar tracking de outra.

## Auto-revisões e bugs corrigidos no Plano 2

1. Contrato aceitava vessel_identity contraditório com IMO/nome.
   Foi criado validator strict.

2. Promoção NAME→IMO no SQL tratava whitespace incorretamente.
   Regex foi corrigida para classe POSIX e validada em PostgreSQL real.

3. Busca de evidência tinha janela arbitrária de últimos 100 eventos.
   Limite foi removido para não rejeitar alvo legítimo retido.

4. DELETE da sessão mascarava erro de persistência.
   Agora somente sessão já inválida/expirada permite limpar cookie sem nova revogação; erro real retorna 503.

5. Timeline Memory tinha reentrada em Lock simples e deadlock.
   Consulta interna foi ajustada para lock único.

6. Cursor foreground foi revisado para não perder eventos ao paginar páginas cheias.

7. Lookup temporal Postgres de tracking usava parâmetros ambíguos em IS NOT NULL.
   Query foi separada em caminho com IMO e sem IMO.

8. Compatibilidade SPEC 021:
   categoria geral já habilitada não faz lookup de tracking; caminho antigo continua independente.

## Gates finais do Plano 2

Em 2026-09-29:

API/Docker/PostgreSQL:
- `make test-all`: **345 passed**;
- `python -m compileall -q app`: exit 0;
- `git diff --check`: clean.

Frontend/PWA:
- Vitest completo: **177 passed**;
- production build: passou.

Ruff:
- `ruff` não está instalado/disponível no ambiente uv atual;
- portanto não declarar gate Ruff como executado.

Testes específicos em PostgreSQL real provaram:
- promoção NAME→IMO;
- isolamento por instalação;
- fronteira `started_at == occurred_at`;
- claim/retry/terminal dedupe de vessel_tracking_deliveries;
- rejeição de delivery para PushInstallation inativa.

## Próximo plano — Plano 3: Desktop & PWA UX

Arquivo:
`docs/superpowers/plans/2026-09-28-ship-tracking-ux.md`

São 6 Tasks:

1. **Tracking local Desktop e persistência de favoritos**
   - LocalTrackedVessel;
   - store atômico independente da PWA;
   - ausência não desativa;
   - NAME→IMO exato;
   - sem TTL.

2. **Desktop — ficha, janela Acompanhados, estrela e timeline local**
   - ☆/★ na ShipInfoWindow;
   - Toplevel Acompanhados;
   - timeline local ManeuverEvent + VesselTrackingEvent;
   - estrela não altera vermelho/verde operacional;
   - sem nova voz/chime.

3. **Tracking client/provider PWA**
   - trackingClient;
   - TrackingProvider;
   - polling agregado 30 s;
   - Zod strict;
   - push OFF não impede acompanhar/parar.

4. **Ações acompanhar na VesselSheet e AlertDetailSheet**
   - acompanhar/parar;
   - navio ausente por evento;
   - fallback por nome explícito;
   - sem falso sucesso otimista offline.

5. **Página Acompanhados, timeline e deep links**
   - route `/acompanhados`;
   - TrackedVesselSheet;
   - timeline unificada;
   - deep link track/event;
   - BottomSheetFrame e scroll iOS.

6. **Foreground, destino de ManeuverEvent e gates cross-repo**
   - avisos foreground sem duplicação;
   - destino /alertas vs /acompanhados;
   - Vitest/build/Playwright;
   - Desktop make test + Xephyr;
   - API make test-all;
   - smoke Desktop → API → feed/timeline → Zod PWA.

## Estratégia sugerida para Plano 3

Seguir o mesmo padrão:
- Tasks 1–2 → auto-revisão → checkpoint;
- Tasks 3–4 → auto-revisão → checkpoint;
- Tasks 5–6 → auto-revisão final → commit de conclusão;
- nenhum push sem autorização.

A Task 1 do Plano 3 começa no **Desktop**, não na API/PWA.
Não sincronizar favoritos Desktop com tracked_vessels PWA.

## Restrições que não devem ser quebradas no Plano 3

- ManeuverEvent continua canônico para manobra.
- VesselTrackingEvent continua residual/complementar.
- Nenhuma inferência AIS/GPS.
- Tracking Desktop e PWA são independentes.
- Sem nova voz/chime para ETA/ETB/ETS.
- PWA continua read-only operacionalmente; só cria/remove preferência de tracking.
- Navio ausente continua na lista de acompanhados.
- NAME fallback nunca usa fuzzy matching.
- Foreground não deve criar dois avisos equivalentes.
- Deep links seguem as regras já consolidadas no Plano 2.
