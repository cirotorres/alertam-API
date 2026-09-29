# Handoff — SPEC 023 Plano 1 concluído → Plano 2

Data: 2026-09-28

## Objetivo da próxima sessão

Continuar a SPEC 023 **Ship Tracking** a partir do Plano 2 — Installations & Dispatch.
O Plano 1 — Core Events está concluído, testado e deve ser tratado como baseline.

Repositórios:
- Desktop: `/home/ciro/dev/prog/alertamaritimo`
- API/PWA: `/home/ciro/dev/prog/alertamaritimoAPI`

Leia primeiro:
1. este handoff;
2. `specs/023-ship-tracking.md`;
3. `docs/superpowers/plans/2026-09-28-ship-tracking-overview.md`;
4. `docs/superpowers/plans/2026-09-28-ship-tracking-installations-dispatch.md`.

Use Remote Desktop Commander + Superpowers. Execute o Plano 2 em Native/TDD.
Não faça push. Commits locais somente conforme autorização de Ciro.
## Estado Git esperado

Desktop:
- branch `develop`;
- HEAD do código do Plano 1: `8f50956 Feat: integra eventos de Ship Tracking ao Desktop`;
- commit anterior do Plano 1: `d99b0c2 Feat: cria núcleo local do Ship Tracking`;
- árvore deve estar limpa;
- nenhum push dos commits da SPEC 023 foi feito.

API/PWA:
- branch `feat/api-bootstrap`;
- `042648d Feat: recebe eventos de Ship Tracking na API` é o checkpoint Tasks 3-4;
- o HEAD posterior deve ter assunto **Feat: conclui Plano 1 da SPEC 023 - Core Events**;
- nenhum push da SPEC 023 foi feito.

Antes de alterar qualquer código:
- rode `git status --short --branch` nos dois repos;
- não faça reset/rebase;
- preserve qualquer arquivo documental não rastreado;
- confirme que o Plano 2 ainda não foi iniciado.
## O que o Plano 1 entregou no Desktop

Contrato novo:
- `VesselTrackingCurrent`;
- `VesselObservation`;
- `VesselTrackingEvent`;
- `VesselTrackingState`;
- `VesselTrackingResult`.

Detector:
- `VesselTrackingDetector.observe(snapshot, maneuver_events=())`;
- separado de `ManeuverTracker`;
- baseline inicial sem evento;
- primeira coleta após restart reconcilia sem replay;
- debounce e confirmação direta após intervalo longo;
- disappearance/reappearance;
- múltiplos campos viram um evento;
- promoção NAME→IMO somente por nome normalizado exato;
- promoção NAME→IMO não reinicia debounce operacional.

Campos observados:
`presence,status,section,berth,side,eta,etb_ets,pob`.
POB canônico continua sendo normalizado no Desktop.
## Supressão de duplicidade semântica

A ordem no Controller é obrigatória:
1. `ManeuverCoordinator.handle(snapshot)`;
2. pegar os `ManeuverEvent` daquela mesma coleta;
3. `VesselTrackingCoordinator.handle(snapshot, tuple(maneuver_events))`.

Regras:
- `ManeuverEvent` continua canônico para manobra;
- UPDATED cobre os campos presentes em `changes`;
- CONFIRMED/COMPLETED/CANCELLED cobrem semântica de manobra;
- `VesselTrackingEvent` mantém somente o residual;
- exemplo: POB + berço + ETA mudam, ManeuverEvent cobre POB/berço e tracking leva só ETA.

Não mover essa lógica para a API e não criar outro detector de manobra.
## Runtime e canal Desktop → API

Runtime separado:
- arquivo `vessel_tracking_runtime.json`;
- state + outbox + `event_history` em escrita atômica;
- ACK remove somente outbox;
- ledger local retém 30 dias;
- evento pendente nunca é apagado pela retenção;
- restart também persiste a poda física do ledger;
- corrupção/falha de persistência não bloqueia coleta;
- coordinator mantém eventos pendentes em memória para retry.

Publisher:
- FIFO próprio;
- não reutiliza SyncPublisher latest-only;
- POST:
  `/api/v1/devices/{device_id}/vessel-tracking-events`;
- `Authorization: Device <DEVICE_SECRET>`;
- retry idempotente.
## API entregue no Plano 1

Modelo strict:
- `VesselTrackingEventIn`;
- timestamps aware;
- changes somente nos campos permitidos;
- current strict;
- payload extra proibido.

Persistência:
- Memory, PostgreSQL e Supabase;
- idempotência por `event_id`;
- mesmo ID + mesmo payload → idempotent;
- mesmo ID + payload diferente → 409;
- Device auth obrigatório.

Migrations:
- `008_vessel_tracking_events.sql`;
- `009_vessel_tracking_retention.sql`.

Retenção:
- `cleanup_vessel_tracking_retention(p_now)`;
- remove somente `vessel_tracking_events` com `ingested_at < p_now - 30 days`;
- não toca em ManeuverEvent nem preferências futuras de tracking.
## Verificações concluídas

Desktop final:
- `make test`: **484 passed, 61 skipped**;
- `git diff --check`: clean.

API:
- unit: exit 0;
- contract: exit 0;
- integration local: exit 0;
- Docker/PostgreSQL `make test-all`: **282 passed**;
- `git diff --check`: clean.

Smoke cross-repo:
- objeto real `VesselTrackingEvent` criado no Desktop;
- `to_dict()` serializado sem adaptação;
- `VesselTrackingEventIn.model_validate` aceitou o mesmo JSON;
- Memory repository: accepted → idempotent com mesmo stored event.

Nenhuma UI de tracking, voz adicional ou dispatch Web Push de tracking foi implementado no Plano 1.
## Bugs encontrados e corrigidos durante auto-revisão

1. Retenção local após restart:
   o ledger expirado era podado em memória, mas podia permanecer fisicamente no JSON.
   Foi criado RED específico e agora o arquivo é reescrito sem tocar na outbox.

2. Promoção NAME→IMO durante mudança operacional:
   a troca da chave de identidade podia reiniciar o debounce de ETA/status.
   Foi criado RED específico e o candidate pendente agora migra para a identidade IMO.

3. Teste concorrente PostgreSQL:
   sequence identity pode consumir números em INSERT concorrente com ON CONFLICT.
   A garantia correta é ambos os retries apontarem para o mesmo ingestion_id, não ingestion_id=1.
## Próximo plano — Installations & Dispatch

Arquivo:
`docs/superpowers/plans/2026-09-28-ship-tracking-installations-dispatch.md`

São 6 tasks:
1. mobile_installation como identidade de sessão;
2. tracked_vessels e lifecycle installation-scoped;
3. projeção atual + timeline cloud unificada;
4. feed agregado VesselTrackingEvent para foreground;
5. elegibilidade de ManeuverEvent via tracking sem duplicação;
6. dispatch de VesselTrackingEvent + deliveries + revogação.

Decisão arquitetural já fechada:
`installation_id` existe independentemente de PushSubscription.
Tracking deve funcionar mesmo com Web Push desligado.
## Regras críticas do Plano 2

- sessão mobile passa a representar `device_id + installation_id`;
- endpoints de tracking nunca aceitam escolher outra instalação;
- migration de mobile_installations deve backfillar UUIDs de push_installations existentes;
- tracking permanece até cancelamento manual ou revogação de segurança;
- cookie expirado não apaga tracking;
- `occurred_at < started_at` nunca gera replay; igualdade é elegível;
- timeline cloud une ManeuverEvent + VesselTrackingEvent por:
  1. occurred_at;
  2. ingested_at;
  3. event_id;
- feed agregado de tracking usa cursor da tabela vessel_tracking_events;
- categoria geral + tracking = um push;
- categoria geral elegível mantém `/alertas?event=`;
- somente tracking usa `/acompanhados?track=...&event=...`;
- não iniciar UX do Plano 3 antes de fechar os gates do Plano 2.
