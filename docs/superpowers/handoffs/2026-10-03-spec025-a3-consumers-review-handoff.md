# Handoff de revisão independente — SPEC 025 A3 — Consumidores MobileSnapshot v2

**Data:** 2026-10-03  
**Repositório:** `/home/ciro/dev/prog/alertamaritimoAPI`  
**Branch:** `feat/spec025-a3-mobile-snapshot-v2`  
**Base:** `755eaa2 fix: ajusta interface mobile`  
**Estado:** Tasks 1–4 + Task 5 Step 1 implementadas localmente; sem commit/push; sem deploy; Desktop v2 não iniciado.

## 1. Missão do Revisor

Realizar revisão independente, inicialmente somente leitura, da parte consumidora do Plan 3.

Ler integralmente:
1. `docs/superpowers/plans/2026-10-03-spec025-a3-mobile-snapshot-v2-execution.md`;
2. `docs/superpowers/plans/2026-09-29-spec025-plan3-mobile-snapshot-v2.md`;
3. `specs/025-webpilot-http-observed-weather-shadow-migration.md`.

Registrar findings como nova entrada sequencial no **Controle de checkpoints** do documento de
execução A3. Não criar documento paralelo para findings.

## 2. Limite da revisão

Revisar:
- API Pydantic v1+v2;
- POST/GET/roundtrip v1+v2;
- erro de schema não suportado;
- Zod/TypeScript v1+v2;
- consumidores operacionais compartilhados;
- WeatherPage v1/v2;
- testes/build;
- segurança do snapshot.

Não revisar como implementado nesta rodada:
- Desktop produtor v2;
- MobileSync Desktop v2;
- sequence do builder Desktop v2;
- deploy real;
- smoke de produção;
- Plan 4 / Shadow.

Esses itens ainda não foram iniciados por causa do hard rollout gate.

## 3. Arquivos A3 principais

### API
- `api/app/models/mobile_snapshot.py`
- `api/app/models/read_snapshot.py`
- `api/app/api/v1/snapshots.py`
- `api/app/services/snapshot_service.py`
- `api/app/main.py`

### Testes/fixtures API
- `api/tests/fixtures/mobile_snapshot_v2_webpilot.json`
- `api/tests/fixtures/mobile_snapshot_v2_fallback.json`
- `api/tests/unit/test_mobile_snapshot_model.py`
- `api/tests/unit/test_snapshot_service.py`
- `api/tests/contract/test_desktop_snapshot_contract.py`
- `api/tests/contract/test_desktop_to_mobile_roundtrip.py`
- `api/tests/integration/test_post_snapshot.py`
- `api/tests/integration/test_get_snapshot.py`

### Frontend
- `frontend/src/api/contract.ts`
- `frontend/src/api/contract.test.ts`
- `frontend/src/pages/WeatherPage.tsx`
- `frontend/src/pages/pages.test.tsx`
- `frontend/src/pages/MapPage.tsx`
- `frontend/src/features/vessels/projections.ts`
- `frontend/src/features/map/berthMap.ts`
- `frontend/src/features/map/PortMap.tsx`

### Fixtures frontend
- `frontend/src/test/fixtures/mobile_snapshot_v2_webpilot.json`
- `frontend/src/test/fixtures/mobile_snapshot_v2_fallback.json`

## 4. Review focus obrigatório do Plan 3

### Compatibilidade v1

Conferir explicitamente:
- `MobileSnapshotV1` continua válido;
- v1 com `weather={}` e `marine={}` continua válido;
- WeatherPage v1 continua renderizando o contrato legado;
- endpoints continuam aceitando e devolvendo v1.

### Contrato v2 estrito

Conferir:
- unavailable aceita somente `{"status":"unavailable"}`;
- extras são rejeitados;
- WebPilot só pode ser `source=webpilot/mode=observed`;
- Open-Meteo primary só pode ser `source=open_meteo/mode=fallback`;
- Open-Meteo primary exige complementary unavailable;
- timestamps WebPilot obrigatórios são aware;
- números não aceitam strings numéricas;
- Marine v2 é explicitamente Open-Meteo ou unavailable.

### Persistência/roundtrip

Conferir:
- API não converte v1 para v2 nem v2 para v1;
- GET devolve a mesma versão persistida;
- idempotência/ordering continuam por boot_id/sequence;
- schema 3 continua retornando `unsupported_snapshot_schema`.

### Segurança

Procurar no payload v2:
- cookies;
- Authorization;
- session_generation;
- headers;
- HTML;
- credenciais/tokens WebPilot.

Nenhum desses itens pode existir.

### PWA

Conferir:
- `MobileSnapshot = MobileSnapshotV1 | MobileSnapshotV2`;
- mapas/projeções usam a união somente em campos compartilhados;
- não existem casts inseguros para fingir v1;
- WeatherPage branch v2 não recalcula freshness;
- fresh/stale/unavailable vêm diretamente do payload;
- WebPilot mostra atual/médio/máximo;
- fallback Open-Meteo usa rajada, não “máximo da estação”;
- complementary separado;
- Marine separado;
- unavailable não fabrica zeros;
- texto v2 não afirma que toda meteorologia vem apenas de Open-Meteo.

## 5. Ruling a revisar

O Executor alterou `api/app/main.py`, embora ele não apareça no bloco Files da Task 2.

Motivo:
- antes da união discriminada, schema inválido gerava `literal_error`;
- depois da união, Pydantic gera `union_tag_invalid`;
- sem adaptar o handler, schema 3 perderia o código público
  `unsupported_snapshot_schema`.

Revisor deve validar se essa é a menor correção coerente com o contrato.

## 6. Evidências disponíveis

Focados:
- Task 1: 30 testes API/model/contract pass;
- Task 2: 59 testes API/service/roundtrip pass;
- Task 3: 23 testes frontend contract/projeções pass;
- Task 4: 46 testes WeatherPage + contract pass.

Gates completos mais recentes:
- API `make test`: PASS, exit 0;
- frontend: **48 test files / 273 tests passed**;
- `npm run build`: PASS;
- `git diff --check`: exit 0.

Há um warning React `act(...)` preexistente em `AppShell.test.tsx`; não é failure e não foi
tratado nesta A3.

## 7. Pre-existing dirty work

Antes da A3 já estavam modificados/não rastreados:
- documentos dos planos SPEC 025;
- handoff de provisioning;
- SPEC 025 e README de specs;
- `docs/superpowers/strategy/`;
- `specs/027-alertam-cloud-continuity.md`.

Não atribuir automaticamente esses itens à implementação A3. Não limpar/resetar.

## 8. Hard rollout gate

Mesmo que a revisão técnica seja liberada:

**NÃO autorizar Desktop Task 6 apenas por revisão de código.**

Ainda é obrigatório:
1. autorização explícita do usuário para deploy/smoke;
2. deploy API/PWA consumidores v1+v2;
3. smoke provando v1 atual e v2 sintético;
4. confirmação humana de que consumidores estão prontos.

Somente depois:
- Desktop pode começar a produzir v2.

## 9. Formato esperado do parecer

Findings primeiro:
- Critical;
- Important;
- Minor.

Para cada finding:
- arquivo/linha;
- cenário;
- impacto;
- critério violado;
- prova/teste exigido.

Depois:
- gates;
- ruling;
- limites;
- resultado técnico da revisão de consumidores.

Acrescentar o parecer ao documento:

`docs/superpowers/plans/2026-10-03-spec025-a3-mobile-snapshot-v2-execution.md`

como nova rodada, preservando histórico.

## 10. Prompt curto para sessão do Revisor

> Faça uma revisão independente, inicialmente somente leitura, da SPEC 025 A3/Plan 3 no repositório
> `/home/ciro/dev/prog/alertamaritimoAPI`, branch
> `feat/spec025-a3-mobile-snapshot-v2`.
> Leia integralmente
> `docs/superpowers/handoffs/2026-10-03-spec025-a3-consumers-review-handoff.md`,
> `docs/superpowers/plans/2026-10-03-spec025-a3-mobile-snapshot-v2-execution.md`,
> o Plan 3 e a SPEC 025.
> Revise somente os consumidores implementados (Tasks 1–4 e Task 5 Step 1): compatibilidade v1,
> contrato v2 estrito, invariantes source/mode/status, persistência/roundtrip, segurança,
> TypeScript/Zod e WeatherPage.
> Não altere código na primeira passagem.
> Registre findings no Controle de checkpoints do documento A3.
> Não autorize Task 6 sem deploy/smoke + confirmação humana e não inicie Plan 4/Shadow.

## 11. STOP

Sem commit/push.  
Sem deploy.  
Sem Desktop schema v2.  
Sem Plan 4/Shadow.
