# Handoff — Etapa 2 após Task 6 (Eventos + base de Push)

| Campo | Estado |
|---|---|
| Data | 2026-09-27 |
| Repositório ativo | `/home/ciro/dev/prog/alertamaritimoAPI` |
| Branch | `feat/api-bootstrap` |
| Plano | `docs/superpowers/plans/2026-09-27-maneuver-events-webpush-api-pwa.md` |
| SPEC local | `specs/021-maneuver-events-webpush.md` |
| Design canônico Desktop | `/home/ciro/dev/prog/alertamaritimo/docs/superpowers/specs/2026-09-27-ciclo-manobras-eventos-push-design.md` |
| Próxima task | **Task 7 — API de instalação, preferências e heartbeat** |
| Push real | **Ainda não implementado** |
| Commit/push | este arquivo pertence ao checkpoint local solicitado; não fazer push sem autorização explícita |

## 1. Estado executivo

A Etapa 2 chegou a um checkpoint seguro após a **Task 6**.

Concluído no código local:

1. Task 1 — contrato ManeuverEvent cross-repo;
2. Task 2 — persistência/idempotência/ordem de eventos;
3. Task 3 — POST Desktop + GET feed mobile;
4. Task 4 — EventProvider + polling mobile por cursor;
5. Task 5 — Alertas por event_id + Histórico por maneuver_id;
6. Task 6 — repository/schema de push installations + push deliveries.

A próxima task correta é a **Task 7**. Não iniciar Task 8/WebPush provider antes de estabilizar os endpoints/config da Task 7.

## 2. Estado Git esperado após este checkpoint

Repositório:

`/home/ciro/dev/prog/alertamaritimoAPI`

Branch:

`feat/api-bootstrap`

O checkpoint será o commit local com assunto:

`feat: consolidar eventos e base de push da etapa 2`

Na nova sessão, confirmar o hash real com:

```bash
cd /home/ciro/dev/prog/alertamaritimoAPI
git status --short --branch
git log -3 --oneline --decorate
```

Estado esperado:
- working tree limpa;
- branch à frente de `origin/feat/api-bootstrap` pelo checkpoint local;
- nenhum push realizado.

Se houver working tree suja, parar e inspecionar antes de continuar.

## 3. Dependência Desktop já concluída

Repositório Desktop:

`/home/ciro/dev/prog/alertamaritimo`

Etapa 1 do Desktop concluída nos commits:
- `95efb1e feat: estruturar ciclo de manobras e runtime persistente`
- `cf80473 feat: integrar eventos de manobra e outbox confiável`

O Desktop é a autoridade semântica. A API não deve comparar snapshots para redetectar CONFIRMED, UPDATED, COMPLETED ou CANCELLED.

Fluxo correto:

```text
Desktop ManeuverEvent
      ↓
POST API idempotente
      ↓
maneuver_events
      ↓
feed mobile
      ↓
PWA
```

Snapshots continuam canal separado/latest-only.

## 4. Documentos a ler primeiro

Na nova sessão, ler nesta ordem:

1. `/home/ciro/dev/prog/alertamaritimoAPI/docs/superpowers/handoffs/2026-09-27-etapa2-task6-checkpoint-handoff.md`
2. `/home/ciro/dev/prog/alertamaritimoAPI/specs/021-maneuver-events-webpush.md`
3. `/home/ciro/dev/prog/alertamaritimoAPI/docs/superpowers/plans/2026-09-27-maneuver-events-webpush-api-pwa.md`
4. `/home/ciro/dev/prog/alertamaritimo/docs/superpowers/specs/2026-09-27-ciclo-manobras-eventos-push-design.md`

A SPEC 020 continua referência do shell PWA, mas Alertas/Histórico já migraram para ManeuverEvent.

## 5. Task 1 — contrato ManeuverEvent

Arquivos principais:
- `api/app/models/maneuver_event.py`
- `api/tests/fixtures/maneuver_event_v1.json`
- `api/tests/unit/test_maneuver_event_model.py`
- `api/tests/contract/test_desktop_maneuver_event_contract.py`
- `frontend/src/api/contract.ts`
- `frontend/src/api/contract.test.ts`

A fixture foi gerada pelo próprio `ManeuverEvent.to_dict()` do Desktop.

Contrato:
- UUID válido;
- timestamp timezone-aware;
- tipos fechados;
- extra fields proibidos;
- UPDATED exige `changes`;
- outros eventos exigem `changes=null`;
- changes só aceita `pob` e `berth`.

## 6. Task 2 — persistência de eventos

Arquivos principais:
- `api/app/repositories/events.py`
- `api/app/repositories/memory.py`
- `api/app/repositories/postgres.py`
- `api/app/repositories/supabase.py`
- `api/app/repositories/factory.py`
- `api/supabase/migrations/004_maneuver_events.sql`

Tipos:
- `AcceptEventStatus`
- `StoredManeuverEvent`
- `AcceptEventResult`
- `EventPage`
- `ManeuverEventsRepository`
- `AlertaRepository`

Semântica:
- novo event_id → ACCEPTED;
- retry mesmo payload → IDEMPOTENT;
- mesmo event_id + payload diferente → PAYLOAD_MISMATCH;
- device inexistente → DEVICE_NOT_FOUND;
- ordem é `ingestion_id`, nunca UUID ou occurred_at.

Feed:
- initial/before escolhe janela recente/antiga;
- resposta normalizada crescente;
- after retorna próximos itens crescentes;
- limit máximo 100.

## 7. Migration 004

`api/supabase/migrations/004_maneuver_events.sql`

Cria `maneuver_events`, `ingestion_id bigint identity`, unique event_id, FK device, índices e RPC `accept_maneuver_event`.

### Limitação

Nesta sessão **não havia `TEST_POSTGRES_DSN`**.

Logo:
- testes PostgreSQL reais da migration 004 ficaram skip;
- Memory e Supabase MockTransport passaram;
- validar 004 em Postgres/Supabase real antes da conclusão final da Etapa 2.

Não tratar skip como aprovação.

## 8. Task 3 — endpoints de evento/feed

Arquivos:
- `api/app/api/v1/maneuver_events.py`
- `api/app/api/v1/mobile_events.py`
- `api/app/api/v1/mobile_auth.py`
- `api/app/services/maneuver_event_service.py`
- `api/app/services/event_feed_service.py`
- `api/app/api/v1/router.py`
- `api/app/core/errors.py`

Desktop POST:

`POST /api/v1/devices/{device_id}/maneuver-events`

Auth:

`Authorization: Device <DEVICE_SECRET>`

Accepted/idempotent retornam ACK com status, ingestion_id e received_at.

Mismatch retorna 409 `event_id_payload_mismatch`.

O hook `dispatch_event` roda em ACCEPTED e IDEMPOTENT. Falha do hook é logada e não muda o ACK do evento persistido.

Mobile feed:

`GET /api/v1/mobile/maneuver-events`

Query:
- after;
- before;
- limit.

Auth:
- somente cookie HttpOnly `alertam_mobile_session`;
- device_id vem da sessão;
- cliente não escolhe device.

## 9. Task 4 — EventProvider/Polling

Arquivos:
- `frontend/src/api/maneuverEventClient.ts`
- `frontend/src/features/events/useEventPolling.ts`
- `frontend/src/features/events/EventProvider.tsx`
- testes correspondentes;
- mudanças em `PairingGate.tsx` e `App.tsx`.

Decisão crítica: `PairingGate` possui `sessionReady`.

O feed só inicia quando o cookie mobile está realmente pronto. Isso evita interpretar 401 transitório do bootstrap como revogação.

Polling:
- 30 s visible;
- pause hidden;
- fetch imediato no retorno;
- initial load não gera toast/newEvent retroativo;
- after=newest_cursor;
- burst cheio é drenado;
- dedupe por event_id.

Não remover `sessionReady`.

## 10. Task 5 — Alertas/Histórico

Arquivos:
- `frontend/src/features/events/projections.ts`
- `frontend/src/pages/AlertsPage.tsx`
- `frontend/src/pages/HistoryPage.tsx`
- `frontend/src/pages/pages.test.tsx`
- `frontend/src/styles/app.css`
- `frontend/src/features/demo/DemoMode.tsx`

Alertas:
- origem = ManeuverEvent;
- newest-first;
- deep-link `/alertas?event=<event_id>`;
- carrega páginas antigas enquanto houver hasMore;
- destaca/rola até o evento alvo.

Histórico:
- agrupa por `maneuver_id`;
- mantém ingestion order;
- shift permanece dois ciclos.

Mapa/footer continuam usando snapshot.

Não reintroduzir `recent_maneuvers` como fonte de Alertas/Histórico.

## 11. Task 6 — schema/repository de Push

Arquivos:
- `api/app/repositories/events.py`
- adapters Memory/Postgres/Supabase;
- `api/supabase/migrations/005_push_installations_deliveries.sql`
- `api/tests/unit/test_push_repository_contract.py`
- `api/tests/unit/test_supabase_push_repository.py`
- `api/tests/integration/test_push_repository.py`

Modelos:
- `PushPreferences`
- `PushInstallation`
- `PushDeliveryStatus`
- `PushDelivery`
- `PushRepository`

Preferências independentes:
- confirmed;
- updated;
- completed;
- cancelled.

Defaults: todas true.

Uma installation_id não pode ser tomada por outro device_id.

Reativação:
- instalação ativa preserva `push_enabled_at`;
- instalação desativada e reativada ganha novo `push_enabled_at`.

Isso impede replay do período desligado.

## 12. Migration 005

`api/supabase/migrations/005_push_installations_deliveries.sql`

Cria:
- `push_installations`;
- `push_deliveries`;
- RLS/revokes;
- índices;
- RPCs upsert/preferências/foreground/deactivate;
- claim/status de delivery;
- substitui `rotate_device_view_secret` para desativar instalações do device.

Claim:
- lease = 8 s;
- primeira claim → SENDING;
- SENDING <8 s não retoma;
- SENDING >=8 s pode retomar;
- RETRY_PENDING retoma;
- terminal não gera nova claim normal.

O WebPushGateway futuro terá timeout de 5 s (Task 8).

Rotação VIEW_SECRET:
- atualiza hash;
- desativa todas as instalações do device;
- limpa endpoint/p256dh/auth;
- não afeta outros devices.

### Limitação

O teste PostgreSQL real da migration 005 também ficou skip por falta de `TEST_POSTGRES_DSN`.

Validar 004 + 005 em Postgres/Supabase real posteriormente.

## 13. Gates verificados

Baseline inicial:
- API full suite exit 0;
- frontend 92/92.

Task 1:
- contrato focado verde;
- frontend passou a 95 testes.

Ledger anterior:
- Task 3: 13 testes focados verdes;
- Task 4: 21 focados; frontend 106/106; build exit 0;
- Task 5: 24 focados; frontend 115/115; build exit 0.

Checkpoint atual:
- API full suite: exit 0;
- frontend full suite: **115/115**;
- Task 6 focused: **21 pass, 1 skip**;
- `npm run build`: exit 0;
- build PWA ainda em `generateSW` por design; `injectManifest` pertence à Task 11;
- `git diff --check`: limpo.

Não validado:
- migrations 004/005 em Postgres real;
- deploy Supabase real;
- Push API real;
- VAPID;
- injectManifest;
- Playwright final da SPEC 021;
- retention 30d;
- smoke Web Push em browser/aparelho.

## 14. Próxima ação — Task 7

Task 7: **API de instalação, preferências e heartbeat**.

Criar/modificar:
- `api/app/models/push.py`
- `api/app/services/push_installation_service.py`
- `api/app/api/v1/push.py`
- `api/app/api/v1/router.py`
- `api/app/core/config.py`
- `api/app/main.py`
- `api/.env.example`
- `api/.env.prod.example`
- `api/tests/unit/test_push_installation_service.py`
- `api/tests/integration/test_push_installations.py`
- `api/tests/unit/test_config.py`

Endpoints:
- `GET /api/v1/mobile/push/vapid-public-key`
- `GET /api/v1/mobile/push/installations/{installation_id}`
- `PUT /api/v1/mobile/push/installations/{installation_id}`
- `PATCH /api/v1/mobile/push/installations/{installation_id}/preferences`
- `POST /api/v1/mobile/push/installations/{installation_id}/foreground`
- `DELETE /api/v1/mobile/push/installations/{installation_id}`

Todos:
- cookie session;
- device_id vem da sessão;
- body não escolhe device;
- installation de outro device → 404 genérico.

Settings:
- `web_push_enabled=false`;
- `vapid_public_key`;
- secret `vapid_private_key`;
- `vapid_subject`;
- `push_foreground_fresh_seconds=75`.

Private key nunca pode aparecer em repr/log/response.

## 15. Ordem segura de retomada

1. Ler este handoff.
2. Rodar:
   ```bash
   cd /home/ciro/dev/prog/alertamaritimoAPI
   git status --short --branch
   git log -3 --oneline --decorate
   ```
3. Confirmar working tree limpa.
4. Ler SPEC 021 + plano.
5. Usar Superpowers executing-plans + TDD + verification-before-completion.
6. Retomar exatamente na Task 7.
7. RED primeiro.
8. Não começar Task 8 até Task 7 passar focados + API full suite + diff-check.
9. Não fazer commit/push sem autorização explícita do Ciro.

## 16. Regras que não podem regredir

- Desktop decide o evento.
- API não redetecta eventos.
- event_id retry é idempotente.
- ingestion_id define ordem.
- push failure não apaga evento.
- cookie expirado normalmente não desativa instalação push.
- VIEW_SECRET rotacionado desativa todas as instalações do device.
- forget/desativar notificação afeta uma instalação.
- installation body nunca seleciona device_id.
- push_enabled_at impede replay.
- foreground suppression será best-effort.
- não cachear respostas autenticadas da API.
- nunca logar DEVICE_SECRET, VIEW_SECRET, cookie, VAPID private, subscription endpoint completo ou chaves push.
- sem Firebase/OneSignal.
- sem Redis/worker obrigatório no MVP.
- sem commit/push automático.

## 17. Prompt curto para nova sessão

```text
Chat, quero continuar a Etapa 2 do Projeto AlertaM usando o Desktop Commander Remote e o Superpowers.

Repositório API/PWA:
/home/ciro/dev/prog/alertamaritimoAPI

Repositório Desktop de referência:
/home/ciro/dev/prog/alertamaritimo

Leia primeiro, integralmente:
/home/ciro/dev/prog/alertamaritimoAPI/docs/superpowers/handoffs/2026-09-27-etapa2-task6-checkpoint-handoff.md

Depois confira:
/home/ciro/dev/prog/alertamaritimoAPI/specs/021-maneuver-events-webpush.md
/home/ciro/dev/prog/alertamaritimoAPI/docs/superpowers/plans/2026-09-27-maneuver-events-webpush-api-pwa.md
/home/ciro/dev/prog/alertamaritimo/docs/superpowers/specs/2026-09-27-ciclo-manobras-eventos-push-design.md

Antes de alterar qualquer arquivo, confirme git status/log e o estado descrito no handoff.

Retome exatamente da Task 7 — API de instalação, preferências e heartbeat — usando TDD RED→GREEN→REFACTOR.

Não faça commit nem push sem minha autorização explícita.
Se TEST_POSTGRES_DSN continuar ausente, registre os testes PostgreSQL como skip/limitação e não os considere validados.
```

## 18. Contexto resumido

**Tasks 1–6 já constroem o canal ManeuverEvent do Desktop até o PWA e a persistência-base de instalações/deliveries. A próxima sessão deve expor essa base pela API mobile de push antes de implementar o envio Web Push real.**
