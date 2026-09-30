# Handoff — SPEC 026 Plano 1 concluído: API/Supabase

**Data:** 2026-09-30  
**Branch:** `feat/api-bootstrap`  
**Base remota no início:** `9390422 feat: refinar duração e acompanhamento no mobile`  
**HEAD ao fechar o ciclo funcional:** `c03bc1b fix: endurece replay da troca de sessão mobile`  
**Push:** não realizado por decisão do usuário.

## Objetivo entregue

O Plano 1 tornou a API a autoridade do ciclo de vida de `mobile_installations`, adicionando:

- plataforma simples (`ios | android | other`);
- código humano `display_code` de 6 caracteres;
- revogação individual completa;
- listagem administrativa por Desktop;
- histórico visível de revogados por 30 dias;
- heartbeat de atividade;
- validação de QR sem efeito colateral;
- sessão mobile enriquecida;
- switch A→B transacional e idempotente por `switch_id`;
- proteção contra reativação de instalação revogada;
- proteção contra replay para destino já revogado.

## Commits do Plano 1

1. `73a73da feat: define ciclo de vida de instalações mobile`
2. `9dea3e0 feat: persiste metadados e revogação mobile`
3. `0c2339f feat: estende sessão e validação mobile`
4. `48fbd42 fix: preserva data original de revogação mobile`
5. `fbcac83 feat: adiciona gestão administrativa de aparelhos`
6. `ed07e06 feat: adiciona troca segura de sessão mobile`
7. `c03bc1b fix: endurece replay da troca de sessão mobile`

A quantidade acima excede o mínimo de 2 commits autorizado pelo usuário. Nenhum push foi feito.

## Migration 013 — gestão das instalações

Arquivo:

`api/supabase/migrations/013_mobile_installation_management.sql`

Principais contratos:

- adiciona `platform` e `display_code`;
- backfill de linhas legadas;
- `display_code` único e validado;
- `ensure_mobile_installation` não reativa instalação revogada;
- `touch_mobile_installation` atualiza atividade sem reativar;
- `list_mobile_installations` retorna ativos + revogados recentes;
- `revoke_mobile_installation` encerra tracking e desativa Push;
- `rotate_device_view_secret` mantém revogação global de instalação, tracking e Push.

A janela de histórico usa `revoked_at >= now - 30 days`; inatividade não revoga.

## Migration 014 — switch de sessão

Arquivo:

`api/supabase/migrations/014_mobile_session_switch.sql`

A RPC de switch:

- recebe identidade A, identidade B, novo `installation_id`, plataforma, código e `switch_id`;
- cria/promove B e revoga A na mesma operação lógica;
- encerra trackings de A;
- desativa Push de A;
- persiste o `switch_id` para reconciliação;
- retry com mesmo `switch_id` + mesmo payload retorna a mesma B;
- mesmo `switch_id` + payload divergente falha;
- replay só retorna B se a instalação B ainda estiver ativa;
- após espera pelo lock da origem, reconsulta o `switch_id` antes de desistir por A já estar inativa.

A migration 014 é separada da 013 para não reescrever uma migration que já possa ter sido aplicada.

## Sessão mobile

### POST /api/v1/mobile/session

Request atual:

```json
{
  "device_id": "pecem-...",
  "installation_id": "uuid",
  "platform": "ios"
}
```

`platform` é opcional para compatibilidade; ausência vira `other`.

Response adiciona aos campos existentes:

```json
{
  "device_id": "pecem-...",
  "installation_id": "uuid",
  "display_code": "K7M4Q2",
  "platform": "ios"
}
```

Cookie continua HttpOnly, SameSite=strict e Secure em produção.

### GET /api/v1/mobile/session

Recupera a sessão e devolve os mesmos metadados de instalação.

### POST /api/v1/mobile/session/heartbeat

Autenticado pelo cookie atual.

Atualiza `last_seen_at`. A plataforma só preenche uma instalação ainda `other`; não fica alternando uma plataforma já conhecida.

Instalação revogada recebe 401.

## Validação de QR sem efeitos colaterais

### POST /api/v1/mobile/pairing/validate

Autenticação:

`Authorization: Bearer <VIEW_SECRET>`

Body:

```json
{"device_id":"pecem-..."}
```

O endpoint valida `device_id + VIEW_SECRET` e retorna apenas o `device_id`.

Não cria instalação, não troca cookie, não mexe em Push, Tracking ou pairing persistido.

Esse endpoint deve ser usado pelo Plano 2 para validar um QR candidato antes de mostrar a confirmação de troca.

## API administrativa do Desktop

Autenticação exclusiva com `DEVICE_SECRET`.

### GET /api/v1/devices/{device_id}/mobile-installations

Retorna:

- `active_count`;
- `active`;
- `recently_revoked`.

A consulta é restrita ao próprio Desktop autenticado.

### DELETE /api/v1/devices/{device_id}/mobile-installations/{installation_id}

Revoga apenas a instalação pertencente ao Desktop autenticado.

Semântica:

- idempotente para instalação própria;
- não revela instalação pertencente a outro Desktop;
- encerra Tracking;
- desativa/limpa Push;
- invalida sessão na próxima resolução.

## Switch seguro A → B

### POST /api/v1/mobile/session/switch

Autenticação simultânea:

- cookie assinado representa A;
- Bearer VIEW_SECRET representa B.

Body inclui:

- `device_id` de B;
- novo `installation_id`;
- `platform`;
- `switch_id`.

O primeiro request exige cookie de A assinado e não expirado.

Para retry de resposta perdida, a camada HTTP consegue extrair a identidade assinada de A mesmo que a instalação já tenha sido revogada pelo primeiro switch; a RPC decide se o `switch_id` já concluído corresponde exatamente ao mesmo payload.

Isso é necessário para reconciliação e não reativa A.

## Invariantes validados

- um `installation_id` não migra entre Desktops;
- instalação revogada nunca volta a ativa;
- revogação repetida preserva `revoked_at` original;
- rotação global não renova artificialmente a data de revogados antigos;
- `display_code` não autentica;
- `platform` não autentica;
- colisão de código curto é retentável;
- serviço limita retry de colisão a 8 tentativas para evitar loop infinito;
- Push e Tracking são encerrados na revogação;
- QR validation não cria estado;
- switch não deixa A revogado sem B válida em falha transacional;
- replay divergente é rejeitado;
- replay não cria sessão para B posteriormente revogada.

## Auto-revisão intermediária

Executada após a Task 3, como solicitado.

Finding importante encontrado:

Memory sobrescrevia `revoked_at` e `last_seen_at` em revogação repetida/rotação global, enquanto SQL preservava a data original. Isso poderia prolongar indevidamente a presença do aparelho no histórico de 30 dias.

Correção:

`48fbd42 fix: preserva data original de revogação mobile`

Cobertura RED→GREEN:

- `test_repeated_revoke_preserves_original_revocation_timestamp`;
- `test_global_rotation_preserves_already_revoked_timestamp`.

## Revisão posterior do switch

Foi encontrado outro edge case durante a revisão final da Task 5:

um `switch_id` concluído poderia ser repetido depois que a instalação B já tivesse sido revogada.

Correção:

`c03bc1b fix: endurece replay da troca de sessão mobile`

Agora replay exige B ativa e a RPC revalida o switch depois de aguardar lock concorrente da origem.

## Verificação

### Suites focadas

- Task 1 lifecycle: PASS
- Task 2 persistence: 16 passed, 3 skipped no checkpoint
- Task 3 mobile session: 17 passed
- Task 4 admin API: 4 passed
- Task 5 switch/persistence: 32 passed, 4 skipped no checkpoint
- revisão pós-Task 5: 18 passed

### Gate completo

`make test` executado ao final em 2026-09-30: **exit 0**.

`git diff --check`: **PASS**.

Revisão de padrões de segredo não encontrou credencial real. O único match foi fixture sintética:

`VIEW_SECRET = "V" * 43`

## Gate Postgres/Supabase ainda pendente

`TEST_POSTGRES_DSN` não estava configurado no ambiente desta execução.

Consequência:

`api/tests/integration/test_mobile_installation_postgres.py` executou como **4 skipped**.

Portanto, migrations 013 e 014 ainda precisam ser aplicadas/validadas em Postgres/Supabase real antes do deploy final. Esse gate está explicitamente documentado em `api/DEPLOY_VERCEL.md`.

Não declarar as migrations como validadas externamente até esse passo ocorrer.

## Ordem de rollout

1. aplicar migrations 013 e 014;
2. validar Postgres/Supabase real;
3. publicar API;
4. executar Plano 2 e publicar PWA;
5. executar Plano 3 e publicar Desktop;
6. smoke real iOS e, quando disponível, Android.

A API nova deve existir antes de PWA/Desktop consumirem os novos contratos.

## Próximo trabalho

Próximo plano:

`docs/superpowers/plans/2026-09-30-spec026-plan2-pwa-safe-pairing-switch.md`

O Plano 2 deve consumir os contratos deste handoff sem redesenhar o lifecycle da instalação.

Focos principais:

- detectar `ios | android | other`;
- persistir metadata local de instalação;
- Config. exibir `plataforma · display_code`;
- PairingGate separar pairing ativo de QR candidato;
- validar QR via `/mobile/pairing/validate`;
- pedir confirmação para A→B;
- chamar `/mobile/session/switch`;
- reconciliar retry com mesmo `switch_id`;
- remontar providers por `installationId`;
- heartbeat;
- reaplicar Push sem migrar Tracking.

## Estado dos repositórios

API/PWA permanece na branch `feat/api-bootstrap`.

Desktop não foi alterado pelo Plano 1.

Existe trabalho Desktop anterior independente da SPEC 026 que deve permanecer separado até o Plano 3.

## Regra de versionamento

Commits locais estão autorizados.

**Push não está autorizado e não foi executado.**
