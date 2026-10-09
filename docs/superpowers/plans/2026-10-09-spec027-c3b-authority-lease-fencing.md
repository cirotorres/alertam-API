# SPEC 027 — C3-B: Authority lease, fencing e migration 021

**Data:** 2026-10-09
**Checkpoint:** C3-B
**Gate independente:** R11
**Base funcional aprovada:** API/PWA/Cloud `feat/spec027-cloud@6806c4ae3a4f2c505c2e7eb8b774c7823e3ce4c7`
**Base Desktop preservada:** `feat/spec027-cloud@c8191bfea696368a7698a08bea727811412c05fd`
**Produção:** proibida neste checkpoint
**Próximo checkpoint:** C3-C, somente após R11 aprovado, commit exato C3-B e autorização explícita

---

## 1. Objetivo

C3-B materializa no PostgreSQL os contratos de domínio aprovados em C3-A.

Ao final deste checkpoint, o sistema deve possuir infraestrutura local/efêmera capaz de representar e arbitrar, de forma transacional e por `device_id`:

- `legacy | managed`;
- source atual `desktop | cloud`;
- `authority_epoch` monotônico;
- authority lease;
- holder instance;
- current snapshot metadata;
- bootstrap inicial `legacy -> managed`;
- write sob grant corrente;
- candidate de transição;
- fencing administrativo;
- concorrência entre writers;
- side-effect policy decidida pela transação vencedora.

C3-B **não liga o Cloud operacionalmente** e **não decide ainda quando failover/failback deve ocorrer com base em tempo**.

O objetivo é construir a camada de consistência e exclusão mútua que C3-C/C3-D/C3-E usarão depois.

---

## 2. Documentos autoritativos

Antes de implementar, ler integralmente e nesta ordem:

1. `docs/superpowers/handoffs/2026-10-08-spec027-controle-checkpoints-executor-revisor.md`
2. `docs/superpowers/plans/2026-10-09-spec027-c3-source-authority-snapshots.md`
3. este documento
4. `specs/027-alertam-cloud-continuity.md`
5. migrations 019 e 020 e seus testes PostgreSQL correspondentes, para preservar convenções de segurança, RLS, locking e migrations.

Se houver conflito, o handoff central e as decisões R9/R9.1/R9.2/R10/R10.1/R10.2 prevalecem sobre formulações antigas.

---

## 3. Gate de entrada

Antes da primeira edição funcional:

- confirmar branch `feat/spec027-cloud`;
- confirmar API/Cloud HEAD exatamente no commit C3-A aprovado ou sucessor documental explicitamente autorizado;
- confirmar `6806c4ae3a4f2c505c2e7eb8b774c7823e3ce4c7` como commit C3-A aprovado;
- confirmar working tree limpo, exceto eventual commit/documentação C3-B explicitamente autorizada;
- confirmar Desktop em `c8191bfea696368a7698a08bea727811412c05fd` e limpo;
- confirmar Shadow original ativo;
- registrar SHA real de entrada no handoff.

Se aparecer diff funcional não explicado, **STOP**.

Não reconciliar automaticamente com `feat/api-bootstrap`, `develop`, production ou outro worktree.

---

## 4. Invariantes herdados do C3-P/C3-A

Estas regras são não negociáveis em C3-B.

### 4.1 Epochs independentes

`realm_epoch`:
- pertence ao Session Broker / auth availability;
- é por realm;
- pode mudar sem source transition;
- nunca é fencing token de snapshot.

`authority_epoch`:
- pertence à source authority;
- é monotônico por `device_id`;
- é fencing token do snapshot managed;
- só é incrementado server-side.

Nenhum client escolhe ou deriva o próximo `authority_epoch`.

### 4.2 Authority é por device

Dois devices no mesmo WebPilotAuthRealm possuem authority independente.

Nenhum Desktop, CloudBinding, SessionLease ou realm compartilhado concede authority de snapshot de device A ao device B.

### 4.3 API/PostgreSQL é o árbitro

Nenhum writer pode:
- assumir authority localmente;
- renovar lease localmente;
- criar novo grant por inferência;
- escolher epoch;
- escolher lease id;
- sobrescrever snapshot após ser fenced.

### 4.4 Operações managed continuam distintas

`PublishUnderCurrentGrant`:
- só holder atual;
- exige epoch + lease + instance;
- não cria authority nova.

`TransitionCandidate`:
- candidate ainda sem novo grant;
- não envia novo epoch/lease;
- PostgreSQL decide se vence e cria o grant.

### 4.5 Write eligibility != renew eligibility

Snapshot autoritativo stale pode tornar um grant não renovável sem bloquear um recovery write do holder ainda corrente.

C3-B deve preservar essa possibilidade estrutural. Os timers e thresholds reais pertencem ao C3-C.

---

## 5. Migration 021

Criar:

`api/supabase/migrations/021_source_authority_snapshots.sql`

A migration é **additive**.

Ela só pode ser aplicada a PostgreSQL local/efêmero durante C3-B.

### 5.1 `device_source_authority`

Uma linha por `device_id`.

Campos esperados:

- `device_id text PK/FK devices`;
- `mode text not null default 'legacy'`;
- `active_source text null`;
- `authority_epoch bigint not null default 0`;
- `authority_lease_id uuid null`;
- `holder_instance_id uuid null`;
- `lease_expires_at timestamptz null`;
- `granted_at timestamptz null`;
- `last_renewed_at timestamptz null`;
- `last_transition_at timestamptz null`;
- `transition_reason text null`;
- `last_authoritative_snapshot_at timestamptz null`;
- `authoritative_snapshot_stale_since timestamptz null`;
- `cloud_binding_id uuid null`;
- `realm_id text null`;
- `observed_realm_epoch bigint null`;
- `updated_at timestamptz not null default clock_timestamp()`.

Constraints devem impedir combinações inválidas, incluindo:

- mode apenas `legacy|managed`;
- source apenas `desktop|cloud|null`;
- epoch nunca negativo;
- legacy não possui grant managed ativo;
- bootstrap managed v1 não nasce sem holder;
- grant managed exige epoch positivo, lease, instance e expiry;
- source Cloud exige `cloud_binding_id + realm_id`;
- source Desktop não carrega associação Cloud;
- `observed_realm_epoch` é diagnóstico e nunca integra fencing.

Não introduzir `realm_epoch` como coluna de source fencing.

### 5.2 `device_source_heartbeats`

Criar somente a persistência estrutural necessária para C3-C posterior.

Chave lógica:
- `device_id + source`.

Campos alinhados ao C3-P/C3-A:

- `device_id`;
- `source`;
- `instance_id`;
- `last_heartbeat_at`;
- `process_healthy`;
- `collection_healthy`;
- `healthy_since`;
- `consecutive_healthy`;
- `last_collection_ok_at`;
- `last_reported_generated_at`;
- `last_candidate_generated_at`;
- `last_reason_code`;
- `persistent_state_ready`;
- `updated_at`.

Constraint:
- `persistent_state_ready` só é aplicável a Cloud.

Não implementar endpoint de heartbeat nem policy temporal neste checkpoint.

### 5.3 `device_source_authority_transitions`

Histórico sanitizado, append-only ou equivalente.

Campos mínimos:

- id;
- device_id;
- authority_epoch;
- previous_source;
- new_source;
- previous_instance_id;
- new_instance_id;
- reason_code;
- transitioned_at.

Nunca armazenar:
- snapshot body;
- vessel data;
- cookies;
- Authorization;
- CloudBinding raw credential;
- SessionLease plaintext/ciphertext;
- raw WebPilot HTML.

### 5.4 Metadata do snapshot corrente em `devices`

Adicionar apenas metadata backend:

- `snapshot_source`;
- `snapshot_authority_epoch`;
- `snapshot_authority_lease_id`;
- `snapshot_writer_instance_id`.

Esses campos não entram no JSON do PWA.

O GET atual continua exatamente no contrato existente.

---

## 6. Compatibilidade legacy

A migration 021 sozinha não pode mudar comportamento operacional.

Após aplicar 021:

- devices existentes continuam em `legacy`;
- Desktop POST atual continua funcionando pelo caminho legacy;
- `accept_device_snapshot` atual continua válido para legacy;
- PWA continua lendo o mesmo snapshot;
- Cloud managed write permanece proibido;
- nenhum failover/failback é ligado;
- nenhum device migra automaticamente para managed.

Adicionar testes que provem a ausência de mudança de comportamento.

---

## 7. Bootstrap `legacy -> managed`

Implementar operação admin/backend transacional para ativar managed somente quando todos os requisitos aprovados estiverem satisfeitos.

O primeiro holder v1 é obrigatoriamente Desktop.

Sob uma única transação:

1. lockar `devices` e source authority na ordem canônica;
2. confirmar device existente e `enabled=true`;
3. confirmar state necessário para considerar Desktop elegível sem inventar C3-C;
4. confirmar snapshot Desktop legacy atual;
5. confirmar `devices.boot_id` compatível com a instância/candidate;
6. confirmar que não existe activation concorrente vencedora;
7. criar `authority_epoch=1`;
8. gerar `authority_lease_id` server-side;
9. definir `active_source=desktop`;
10. definir holder instance;
11. definir lease expiry com clock server-side;
12. copiar metadata do snapshot corrente para a nova authority;
13. marcar metadata backend em `devices`;
14. gravar transition/audit adequada;
15. retornar grant completo;
16. commit.

Se qualquer pré-condição falhar:

- permanecer legacy;
- não criar managed parcial;
- não criar holder vazio;
- não alterar snapshot;
- retornar resultado tipado.

Não inventar heartbeat/timer C3-C para satisfazer bootstrap. Se o contrato atual não permitir uma decisão segura, registrar o gap e **STOP arquitetura**, em vez de antecipar C3-C silenciosamente.

---

## 8. Current-grant write

Materializar o caminho de `PublishUnderCurrentGrant`.

A operação deve revalidar sob lock:

- device correto;
- mode managed;
- current source;
- authority epoch;
- authority lease id;
- holder instance;
- lease ainda não expirada;
- grant não fenced/substituído;
- device enabled;
- gates administrativos aplicáveis;
- candidate canonical;
- boot/instance;
- sequence/order/idempotência;
- generated_at/skew permitido pelo contrato atual.

### 8.1 Recovery write

Preservar decisão R9.2:

- snapshot anterior stale pode bloquear renewal;
- isso não torna o grant automaticamente write-ineligible;
- se epoch/lease/instance ainda forem correntes e lease não tiver expirado, recovery snapshot válido pode ser aceito;
- a transação atualiza `last_authoritative_snapshot_at`;
- limpa stale marker quando aplicável;
- não troca epoch/lease.

Após expiry, fencing ou replacement:
- current-grant antigo não recupera;
- nova aquisição é apenas por transition candidate quando policy futura permitir.

---

## 9. Transition candidate

Materializar `TransitionCandidate` como operação separada.

O request fornece:
- source;
- holder/source instance;
- snapshot candidate;
- contexto autenticado.

O request **não fornece**:
- próximo authority epoch;
- nova authority lease.

A transação:

1. adquire locks na ordem canônica;
2. revalida state atual;
3. revalida eligibility administrativa disponível em C3-B;
4. revalida candidate;
5. decide winner/loser;
6. se winner:
   - incrementa epoch server-side;
   - cria nova lease;
   - troca holder;
   - aceita snapshot;
   - atualiza metadata em `devices`;
   - grava transition history;
   - retorna grant completo e side-effect context;
7. se loser:
   - não altera authority;
   - não altera snapshot;
   - não grava side effect;
   - retorna status/reason tipado.

C3-B não deve embutir a policy temporal completa de failover/failback.

Quando a decisão depender de liveness/freshness/hysteresis do C3-C, manter o caminho bloqueado por gate explícito/test double/input de policy, sem criar timers aqui.

---

## 10. Idempotência e ordering

Preservar compatibilidade com semântica atual de snapshot.

Testes obrigatórios:

- same boot/grant + same sequence + mesmo payload => idempotent;
- same sequence + payload diferente => conflito tipado;
- sequence menor/out-of-order => rejeitado;
- writer antigo após epoch novo => fenced;
- lease errada => fenced;
- instance errada => fenced;
- boot restart não reutiliza grant antigo.

O fingerprint/canonicalização deve usar os padrões existentes do projeto; não criar um segundo esquema de hash se o repository atual já possui semântica apropriada.

---

## 11. Side-effect context transacional

O resultado do write managed deve nascer da mesma transação que aceita o snapshot.

Retornar conforme C3-A:

- `previous_source`;
- `source_transition`;
- `side_effect_policy`;
- `previous_snapshot_for_side_effects` somente quando `desktop_continuity`.

Regras:

- qualquer Cloud accepted => `none`;
- Cloud→Desktop accepted => `baseline`;
- primeiro Desktop accepted de qualquer source transition => `baseline`;
- Desktop→Desktop contínuo pode retornar `desktop_continuity`;
- loser => nenhum side effect;
- retry idempotente => nenhum side effect.

O managed path não pode depender de pre-read externo para decidir side effects.

O caminho legacy pode permanecer como está neste checkpoint.

---

## 12. Fencing administrativo

### 12.1 Device disable

`device.enabled=false` vence tudo.

Deve fencear current authority do device independentemente de source.

Write concorrente não pode escapar depois do disable vencedor.

### 12.2 CloudBinding revoke

Fenceia somente grant Cloud que referencia exatamente:
- binding;
- device.

Nunca fenceia Desktop.

### 12.3 Realm inactive

Torna Cloud inelegível e fenceia current Cloud grant ligado ao realm.

Não fenceia Desktop authority.

### 12.4 Owner membership revoke

Revogação da membership do device dono do CloudBinding fenceia somente o Cloud grant correspondente.

### 12.5 SessionLease publisher lifecycle

Não criar trigger amplo que fenceie source authority por mudança em:
- `webpilot_session_publishers`;
- `webpilot_session_leases`;
- publisher membership não relacionada.

Auth availability continua separado.

Se outra SessionLease elegível existir, Cloud pode continuar no mesmo authority epoch.

Se auth estiver totalmente indisponível, Cloud write/renew fica bloqueado, mas essa avaliação deve usar os contratos C2 existentes e não converter `realm_epoch` em fencing token.

---

## 13. Lock order obrigatório

Definir uma única ordem e usá-la em todos os RPCs/transações C3-B.

A implementação deve documentar a ordem real adotada.

A ordem deve ser compatível com objetos já existentes e evitar inversões entre:

- `devices`;
- source authority;
- CloudBinding/realm/membership quando necessários;
- snapshot metadata;
- transition history.

Antes de fechar C3-B, testes concorrentes devem demonstrar ausência de deadlock nos cenários do gate.

Não espalhar `FOR UPDATE` ad-hoc com ordens diferentes entre funções.

---

## 14. PostgreSQL security

Seguir o padrão das migrations 019/020:

- RLS ligado nos novos tables;
- nenhuma policy pública desnecessária;
- revoke para `anon` e `authenticated`;
- funções sensíveis `SECURITY DEFINER` somente quando necessário;
- `set search_path = pg_catalog, public`;
- referências a objetos qualificadas;
- EXECUTE revogado de PUBLIC/anon/authenticated quando aplicável;
- grant somente para backend/service role necessário;
- não vazar secret em return/log/error.

Migration deve passar auditoria de privilégios nos testes.

---

## 15. Repository/adapters

C3-B pode implementar os adapters necessários para os Protocols C3-A:

- Memory, quando útil para unit tests e compatibilidade;
- PostgreSQL/Supabase conforme arquitetura já existente.

Evitar duplicar lógica de arbitragem em Python e SQL.

Regra de consistência:
- invariantes que precisam ser atômicas entre processos ficam no PostgreSQL/RPC;
- Python mapeia comandos/resultados tipados e autenticação;
- não confiar em check-then-write feito fora da transação.

---

## 16. Concorrência PostgreSQL real

Executar contra PostgreSQL real efêmero.

Cobertura mínima:

1. dois current writers simultâneos;
2. Desktop candidate × Cloud candidate simultâneos;
3. dois transition candidates concorrentes;
4. current-grant write × transition candidate;
5. recovery current-grant × transition candidate;
6. stale epoch após novo winner;
7. wrong lease;
8. wrong instance;
9. boot restart;
10. device disable × snapshot write;
11. CloudBinding revoke × Cloud write;
12. realm deactivate × Cloud write;
13. owner membership revoke × Cloud write;
14. publisher SessionLease revoke com outra lease elegível;
15. auth totalmente indisponível bloqueando Cloud write;
16. cross-device isolation;
17. concorrência por dois processos/API connections independentes;
18. pre-read stale não promovendo side effect cross-source.

Resultado invariável:

- exatamente um authority state corrente;
- exatamente um snapshot current;
- epoch monotônico;
- loser tipado;
- loser não sobrescreve winner;
- nenhum deadlock.

---

## 17. TDD

C3-B começa por RED.

Sequência recomendada:

1. migration/schema contract;
2. legacy compatibility;
3. repository mapping;
4. bootstrap legacy→managed;
5. current-grant fencing;
6. transition candidate;
7. idempotência/ordering;
8. side-effect context;
9. administrative fencing;
10. PostgreSQL concurrency;
11. privilege/security tests;
12. regressões.

Registrar RED e GREEN reais no handoff.

Não escrever uma bateria de testes depois de implementar tudo.

---

## 18. Gates

No mínimo:

### 18.1 Migration

- migrations 001→021 em PostgreSQL efêmero;
- schema/constraint tests;
- reexecução/idempotência conforme padrão do projeto;
- rollback operacional = permanecer/retornar legacy, não down migration destrutiva.

### 18.2 API/domain

- C3-A unit contracts;
- C3-B repository tests;
- snapshot integration tests;
- auth/binding/realm regressions relevantes.

### 18.3 PostgreSQL real

- todos os cenários da seção 16;
- zero skip por falta de DB quando o target dedicado estiver rodando.

### 18.4 PWA

- GET permanece `{snapshot, meta}`;
- v1/v2 continuam aceitos;
- nenhum source/authority metadata no envelope;
- frontend contract tests;
- nenhuma v3.

### 18.5 Projeto

Preferir targets existentes:
- `make test-all`;
- targets/migration scripts oficiais;
- infraestrutura PostgreSQL efêmera já usada no C2.

Se um target dedicado C3-B for criado, mantê-lo pequeno e documentado no Makefile.

### 18.6 Hygiene

- `git diff --check`;
- check também nos untracked;
- security grep;
- staged files = 0;
- Shadow intacto;
- Desktop sem mudança indevida.

---

## 19. Produção e migration 021

Durante C3-B é proibido:

- `make prod-migrate`;
- Supabase produção migration;
- Vercel deploy;
- Northflank operacional;
- alterar managed mode de device real;
- usar WebPilot real no Cloud;
- usar Cloud como source real.

021 é validada apenas localmente/efemeramente.

---

## 20. Fora de escopo

Não implementar em C3-B:

- endpoint/runtime de heartbeat C3-C;
- scheduler de renewal;
- timers de liveness;
- thresholds 90/120/180/300 em runtime;
- hysteresis operacional;
- failover real;
- failback real;
- Cloud snapshot writer operacional;
- persistent Cloud state mount;
- Northflank runtime;
- cutover;
- eventos/push C5.

Se uma dessas coisas parecer necessária para o C3-B funcionar, **STOP e documentar**, em vez de ampliar o checkpoint.

---

## 21. Rollback

Até production migration 021, rollback = descartar/reverter commits locais aprovados.

Depois de uma futura migration 021, mas antes de managed mode:
- schema é additive;
- devices continuam legacy;
- aplicação antiga continua lendo snapshot atual.

Rollback emergencial managed→legacy é tema já definido no C3-P, mas não deve ser executado em produção neste checkpoint.

Não criar down migration destrutiva.

---

## 22. Entrega ao R11

Ao terminar:

- não fazer commit;
- não fazer stage;
- não iniciar C3-C;
- atualizar o handoff central.

Registrar:

- SHA de entrada;
- arquivos alterados;
- migration 021;
- RED→GREEN;
- lock order real;
- schema/constraints;
- RPCs/functions criados;
- bootstrap;
- fencing;
- idempotência;
- side effects;
- administrative fencing;
- testes PostgreSQL real;
- concorrência;
- privilege/security evidence;
- migration 001→021;
- API regressions;
- PWA regressions;
- `git diff --check`;
- staged=0;
- Shadow intacto;
- confirmação explícita de nenhuma ação de produção.

Finalizar exatamente:

**C3-B PRONTO PARA R11 INDEPENDENTE**

e parar.

---

## 23. Critério de aprovação R11

R11 deve revisar independentemente, no mínimo:

- schema 021;
- invariantes DB;
- lock order;
- monotonicidade de epoch;
- grant creation;
- fencing;
- races;
- legacy default;
- privilege/RLS;
- side-effect context;
- isolamento cross-device;
- auth/source lifecycle separation;
- ausência de produção/runtime C3-C.

Somente após **R11 APROVADO** poderá existir commit exato C3-B.

C3-C não começa automaticamente após esse commit.
