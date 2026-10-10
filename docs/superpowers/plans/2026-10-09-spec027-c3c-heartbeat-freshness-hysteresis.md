# SPEC 027 — C3-C: heartbeat, freshness, hysteresis e authority renewal

**Data:** 2026-10-09
**Checkpoint:** C3-C
**Gate independente:** R12
**Base funcional aprovada:** API/PWA/Cloud `feat/spec027-cloud@4691c2476d70311a60ecb392c858bfa1cac3699b`
**Base Desktop preservada:** `feat/spec027-cloud@c8191bfea696368a7698a08bea727811412c05fd`
**Produção:** proibida neste checkpoint
**Próximo checkpoint:** C3-D, somente após R12 aprovado, commit exato C3-C e autorização explícita

---

## 1. Objetivo

C3-C materializa a policy temporal que C3-B deliberadamente deixou fail-closed.

Ao final deste checkpoint, API/PostgreSQL deve conseguir determinar, de forma persistente e por `device_id`:

- liveness/process health de Desktop e Cloud;
- collection health;
- authoritative snapshot freshness;
- hysteresis;
- renew eligibility do current holder;
- failover eligibility Desktop → Cloud;
- failback eligibility Cloud → Desktop;
- same-source restart/reacquisition eligibility;
- reason/status tipados;
- continuidade dos timers após restart da API.

C3-C **não cria ainda um writer Cloud operacional**.

O sistema pode calcular e persistir que uma transição seria elegível, mas nenhum runtime Cloud real publica snapshot e nenhum Desktop real começa a enviar authority headers neste checkpoint.

---

## 2. Documentos autoritativos

Antes de qualquer edição funcional, ler integralmente nesta ordem:

1. `docs/superpowers/handoffs/2026-10-08-spec027-controle-checkpoints-executor-revisor.md`
2. `docs/superpowers/plans/2026-10-09-spec027-c3-source-authority-snapshots.md`
3. `docs/superpowers/plans/2026-10-09-spec027-c3b-authority-lease-fencing.md`
4. este documento
5. `specs/027-alertam-cloud-continuity.md`
6. migration 021 e testes C3-B atuais.

Decisões R9/R9.1/R9.2/R10/R10.1/R10.2/R11/R11.1/R11.2 prevalecem sobre texto antigo incompatível.

---

## 3. Gate de entrada

Antes da primeira alteração:

- confirmar branch `feat/spec027-cloud`;
- confirmar API/Cloud HEAD exatamente em `4691c2476d70311a60ecb392c858bfa1cac3699b` ou sucessor documental explicitamente autorizado;
- confirmar `4691c24` como commit C3-B aprovado em R11.2;
- confirmar working tree sem diff funcional inesperado;
- confirmar Desktop limpo em `c8191bfea696368a7698a08bea727811412c05fd`;
- confirmar Shadow original ainda ativo;
- registrar SHA real de entrada no handoff.

Se houver alteração funcional inesperada, **STOP**.

---

## 4. Fronteira do checkpoint

### C3-C faz

- heartbeat HTTP server-side;
- persistência de health;
- classifications;
- authoritative snapshot freshness;
- hysteresis;
- authority renewal;
- failover/failback eligibility;
- same-source reacquisition eligibility;
- restart-safe temporal state;
- testes reais PostgreSQL e clock-boundary.

### C3-C não faz

- Desktop heartbeat adapter no programa real;
- authority metadata no `SnapshotHttpClient` Desktop real;
- Cloud snapshot endpoint operacional;
- Cloud snapshot writer;
- persistent Cloud state volume;
- Northflank operacional;
- WebPilot real no Cloud;
- failover/failback real;
- eventos/push;
- deployment;
- migration 021 em produção.

Esses itens permanecem para C3-D/C3-E/C3-F e gate humano posterior.

---

## 5. Invariantes herdados

### 5.1 Auth e source continuam separados

`realm_epoch` continua exclusivo de SessionLease/auth.

`authority_epoch` continua exclusivo de source fencing por `device_id`.

Mudança de `realm_epoch` não cria source transition.

### 5.2 Heartbeat não é authority

Um source não-holder pode enviar heartbeat.

Heartbeat de standby não cria grant.

O client nunca envia `failover_granted`, `failback_granted` ou qualquer decisão de arbitragem como verdade confiável.

**Reason/gate de authority é calculado server-side.**

### 5.3 Heartbeat não é snapshot freshness

Heartbeat saudável não atualiza `last_authoritative_snapshot_at`.

Somente snapshot autoritativo aceito pelo RPC C3-B atualiza essa referência.

### 5.4 Write eligibility continua diferente de renew eligibility

Snapshot stale pode tornar o grant não renovável.

O holder ainda pode recuperar via current-grant write enquanto epoch/lease/instance forem correntes e a lease não tiver expirado.

C3-C não deve quebrar a decisão R9.2.

---

## 6. Endpoints C3-C

### 6.1 Desktop heartbeat

Implementar:

`POST /api/v1/devices/{device_id}/source-heartbeat`

Autenticação:
- Device auth existente;
- source = Desktop implícito;
- nenhuma query secret.

Payload mínimo deve representar:

- `instance_id`;
- collection state/health;
- último `generated_at` coletado apenas como diagnóstico.

O payload **não pode aceitar authority reason como decisão confiável do client**.

O servidor define `last_heartbeat_at` com clock server-side.

### 6.2 Cloud heartbeat

Implementar:

`POST /api/v1/cloud-bindings/{cloud_binding_id}/source-heartbeat`

Autenticação:
- CloudBinding auth existente;
- binding deve mapear para um único `device_id`;
- source = Cloud implícito;
- nenhuma query secret.

Payload mínimo deve representar:

- `instance_id`;
- process/collection/cycle health;
- `last_candidate_generated_at` diagnóstico/freshness de standby;
- `persistent_state_ready`.

Não confiar em boolean client-side do tipo `auth_ready` como substituto da revalidação server-side de:
- binding;
- realm;
- owner membership;
- SessionLease;
- provider scope.

### 6.3 Resposta de heartbeat

A resposta deve ser sanitizada e suficiente para o futuro adapter C3-D.

Para current holder, pode confirmar:

- status/reason;
- current `authority_epoch`;
- current `authority_lease_id`;
- current `holder_instance_id`;
- `lease_expires_at`;
- renew result.

Para non-holder/standby:

- status/reason;
- health/eligibility sanitizada;
- **nunca inventar ou devolver futuro epoch/lease**.

PWA não consome heartbeat.

---

## 7. Persistência de heartbeat

Usar `device_source_heartbeats` da migration 021.

### 7.1 Upsert server-side

Chave:
- `device_id + source`.

Persistir:

- `instance_id`;
- `last_heartbeat_at` server-side;
- process health;
- collection health;
- `healthy_since`;
- `consecutive_healthy`;
- `last_collection_ok_at`;
- `last_reported_generated_at`;
- `last_candidate_generated_at`;
- server-computed `last_reason_code`;
- `persistent_state_ready` Cloud-only;
- `updated_at`.

### 7.2 Continuidade saudável

Para o mesmo `instance_id`:

- heartbeat saudável consecutivo incrementa `consecutive_healthy`;
- preserva `healthy_since`;
- collection OK atualiza `last_collection_ok_at`.

Novo `instance_id`:

- inicia nova continuidade;
- `healthy_since = now` se saudável;
- `consecutive_healthy = 1` se saudável;
- nunca herda continuidade do processo anterior.

Heartbeat unhealthy/degraded:

- quebra a continuidade exigida para failback/reacquire;
- reset de `healthy_since/consecutive_healthy` deve ser determinístico e testado.

---

## 8. Clock e thresholds

Toda arbitragem temporal usa clock server-side.

Em testes de policy/service, usar clock injetável ou mecanismo determinístico equivalente.

Defaults aprovados:

- Desktop heartbeat target: 60 s;
- Desktop healthy: age < 90 s;
- Desktop degraded: 90 s <= age < 120 s, ou collection degradada;
- Desktop stale: age >= 120 s;
- Desktop offline: age >= 300 s, apenas classificação operacional;
- Cloud heartbeat stale: age >= 60 s;
- Desktop authoritative snapshot stale: age >= 120 s;
- Cloud authoritative snapshot stale: age >= 90 s;
- source/snapshot hysteresis: 60 s;
- authority lease TTL: 180 s;
- Desktop failback: >=3 heartbeats saudáveis e >=120 s de continuidade;
- Cloud ativo antes de failback: >=120 s;
- candidate future skew: >60 s rejeitado;
- candidate max age: >300 s rejeitado.

Boundaries devem cobrir exatamente:
- 89/90;
- 119/120;
- 179/180;
- 299/300;
- Cloud 59/60;
- snapshot Cloud 89/90.

Não usar sleeps longos para testar policy pura.

---

## 9. Liveness Desktop

Classificação:

### HEALTHY

- heartbeat age <90 s;
- process healthy;
- collection healthy.

Reason:
- `desktop_healthy`.

### DEGRADED

- 90 <= age <120; ou
- heartbeat recente mas collection/process degradado de forma recuperável.

Reason:
- `desktop_degraded`.

### STALE

- age >=120 s.

Reason:
- `desktop_stale`.

### OFFLINE

- age >=300 s.

Reason:
- `desktop_offline`.

OFFLINE é observabilidade. A authority policy já deve ter reagido à condição STALE/hysteresis antes disso.

---

## 10. Authoritative snapshot freshness

### 10.1 Desktop holder

Fresh:
- `now - last_authoritative_snapshot_at < 120 s`.

Ao cruzar 120 s:
- reason `desktop_snapshot_stale`;
- grant deixa de ser renew-eligible;
- `authoritative_snapshot_stale_since` deve refletir o início real da condição.

Importante:
- não definir stale_since simplesmente como “momento em que algum request percebeu” se isso fizer API restart/polling atrasar hysteresis;
- preferir timestamp determinístico derivado do threshold ou persistência equivalente que sobreviva restart.

Somente snapshot Desktop autoritativo aceito limpa o marker.

Heartbeat saudável não limpa.

### 10.2 Cloud holder

Fresh:
- `now - last_authoritative_snapshot_at < 90 s`.

Ao cruzar 90 s:
- reason `cloud_snapshot_stale`;
- não renovar;
- recovery current-grant ainda permitido enquanto lease/grant válidos.

Somente snapshot Cloud autoritativo aceito limpa.

---

## 11. Authority renewal

Implementar renewal como operação **do current holder**, nunca aquisição.

Renew preserva:

- `authority_epoch`;
- `authority_lease_id`;
- `holder_instance_id`.

Renew bem-sucedido apenas estende:
- `lease_expires_at = server_now + 180 s`;
- `last_renewed_at`;
- metadata diagnóstica aplicável.

### 11.1 Requisitos comuns

Sob lock/transação e clock pós-lock:

- device enabled;
- mode managed;
- source atual igual ao caller;
- instance atual igual ao caller;
- lease ainda não expirada;
- grant não fenced/replaced;
- process/liveness válido;
- collection health aplicável;
- authoritative snapshot fresh.

### 11.2 Desktop

Renew bloqueado quando:
- liveness não saudável;
- collection degradada;
- snapshot >=120 s.

### 11.3 Cloud

Além dos gates comuns:
- CloudBinding usable;
- realm ativo;
- owner membership ativa;
- SessionLease atual elegível;
- provider scope compatível;
- persistent state ready;
- snapshot Cloud <90 s.

Auth indisponível:
- Cloud não renova;
- não mudar `authority_epoch`;
- uma nova SessionLease elegível pode restaurar renew no mesmo source authority epoch enquanto a authority lease ainda estiver corrente.

### 11.4 Expiry

Request iniciada antes do expiry mas processada depois não pode renovar.

Clock deve ser lido depois dos locks, preservando R11-F4.

Grant expirado nunca é ressuscitado por renewal.

---

## 12. Failover eligibility Desktop → Cloud

C3-C calcula/persiste eligibility. Não executa Cloud writer real.

Failover pode ser considerado elegível somente se, na mesma avaliação:

1. mode managed;
2. device enabled;
3. current holder = Desktop;
4. Desktop tornou-se não renovável por:
   - liveness stale persistente; ou
   - authoritative snapshot stale persistente;
5. hysteresis correspondente completou 60 s;
6. Cloud standby health válido;
7. Cloud heartbeat age <60 s;
8. Cloud candidate/cycle health recente <=90 s;
9. persistent state ready;
10. CloudBinding usable;
11. realm ativo;
12. owner membership ativa;
13. SessionLease/provider scope elegíveis;
14. candidate temporalmente plausível.

### 12.1 Liveness path

Desktop STALE começa em age 120 s.

Com hysteresis 60 s:
- antes de 180 s => `failover_wait_hysteresis`;
- a partir de 180 s, com Cloud verde => `failover_granted`.

### 12.2 Snapshot-stale path

Desktop snapshot stale começa aos 120 s.

Com 60 s contínuos:
- antes de 180 s => wait;
- >=180 s, Cloud verde => grant eligibility.

A primeira condição que completa hysteresis pode liberar eligibility.

### 12.3 Uma falha isolada não concede failover

Perda breve de heartbeat ou um POST de snapshot perdido não pode imediatamente gerar `failover_granted`.

---

## 13. Failback eligibility Cloud → Desktop

C3-C calcula/persiste eligibility. Não faz Desktop real publicar transition candidate ainda.

Requisitos:

- mode managed;
- current holder = Cloud;
- device enabled;
- Desktop candidate instance coerente;
- Desktop process/collection saudável;
- pelo menos 3 heartbeats saudáveis consecutivos;
- continuidade saudável >=120 s;
- Cloud ativo há >=120 s;
- candidate Desktop fresh;
- DB disponível.

Antes disso:
- `failback_wait_stable`.

Quando tudo estiver verde:
- `failback_granted`.

Um único heartbeat Desktop não concede failback.

Heartbeat degradado ou troca de instance zera a continuidade.

---

## 14. Same-source restart/reacquisition

Este checkpoint deve fechar explicitamente a lacuna deixada fail-closed no R11.1.

### 14.1 Desktop restart

Novo processo => novo `boot_id/instance_id`.

Política inicial aprovada no C3-P:

- holder Desktop anterior sem heartbeat saudável por >=90 s pode tornar-se elegível a same-source reacquisition;
- novo Desktop precisa estar autenticado e saudável;
- novo candidate precisa ser válido/fresh;
- DB cria novo epoch/lease;
- old holder fica fenced.

Antes de 90 s:
- same-source candidate permanece bloqueado.

Se durante implementação ficar evidente que 90 s é inseguro com a cadência real, **STOP arquitetura**. Não alterar silenciosamente.

### 14.2 Cloud restart

Novo processo Cloud => nova instance.

Novo Cloud só pode same-source reacquire quando:

- old Cloud holder heartbeat age >=60 s;
- auth/binding/realm/membership verdes;
- persistent state ready;
- candidate válido;
- policy de restart explicitamente satisfeita.

Antes disso:
- bloqueado.

### 14.3 Reason codes

Não reutilizar `failover_granted` ou `failback_granted` para same-source.

Se forem necessários reason codes específicos de reacquisition, defini-los explicitamente no domínio C3-C e testá-los.

A nomenclatura deve distinguir:
- cross-source transition;
- same-source restart/reacquisition.

---

## 15. Hysteresis e restart safety

Nenhum timer crítico pode viver apenas em memória FastAPI.

API restart não pode:

- zerar `healthy_since`;
- zerar `consecutive_healthy`;
- esquecer snapshot stale;
- reiniciar hysteresis;
- renovar authority;
- mudar source.

Quando um estado puder ser derivado deterministicamente de timestamps persistidos, preferir derivação server-side.

Quando precisar de marker persistido, usar 021 se o schema já suportar.

### Migration

Preferir **nenhuma migration nova**.

Migration 021 ainda não foi aplicada em produção e pode receber funções/ajustes C3-C estritamente necessários se compatível com a estratégia do projeto.

Se surgir necessidade real de nova coluna/tabela que 021 não comporte:
- **STOP arquitetura**;
- documentar;
- não criar 022 automaticamente.

---

## 16. Policy server-side e anti-spoofing

Client heartbeat nunca escolhe:

- `last_reason_code=failover_granted`;
- `last_reason_code=failback_granted`;
- reacquire grant reason;
- renew_allowed;
- authority epoch/lease.

Essas decisões pertencem à API/PostgreSQL.

Adicionar testes adversariais garantindo que payload manipulado não concede authority.

---

## 17. Repository/service boundary

Manter invariantes temporais/authority que precisam ser cross-process no PostgreSQL.

Python pode:

- validar payload/auth;
- mapear contratos;
- expor service/policy pura para unit tests;
- chamar RPCs.

Não implementar check-then-write em Python para:

- renew;
- failover eligibility persistida;
- failback eligibility persistida;
- same-source reacquisition gate.

A decisão usada pelo futuro `transition_candidate` precisa estar baseada em state server-side serializado.

---

## 18. C3-B transition RPC integration

C3-B deixou:

- cross-source dependente de gate explícito;
- same-source totalmente fail-closed.

C3-C deve integrar a policy de forma que:

### Cross-source

- Desktop→Cloud só seja liberado por gate server-computed `failover_granted`;
- Cloud→Desktop só seja liberado por `failback_granted`.

### Same-source

- Desktop→Desktop só seja liberado por gate específico de Desktop reacquire;
- Cloud→Cloud só seja liberado por gate específico de Cloud reacquire.

O gate deve ser:
- ligado à instance candidate;
- recente;
- posterior ao authority state relevante;
- não reutilizável indefinidamente;
- revalidado na transação C3-B.

Nenhum reason de heartbeat antigo deve continuar autorizando transition após state relevante mudar.

---

## 19. Testes RED obrigatórios

Começar por RED.

### 19.1 Liveness boundaries

Desktop:
- 89 s healthy;
- 90 s degraded;
- 119 s degraded;
- 120 s stale;
- 179 s ainda sem failover se hysteresis incompleta;
- 180 s elegível, desde que Cloud esteja verde;
- 300 s offline classification.

Cloud:
- 59 s fresh;
- 60 s stale/ineligible conforme contexto.

### 19.2 Snapshot freshness

Desktop:
- 119 s fresh;
- 120 s snapshot stale;
- 179 s sem hysteresis completa;
- 180 s eligibility possível;
- heartbeat healthy não mascara snapshot stale.

Cloud holder:
- 89 s fresh;
- 90 s stale/nonrenewable.

### 19.3 Recovery

- Desktop stale aos 120;
- recovery snapshot aceito aos 150 sob mesmo epoch/lease;
- stale marker limpo;
- renew volta a ser elegível;
- zero failover.

Equivalente Cloud holder.

### 19.4 Renewal

- current healthy/fresh renova sem trocar epoch/lease;
- snapshot stale não renova;
- collection degraded não renova;
- wrong instance não renova;
- expired lease não renova;
- Cloud auth absent não renova;
- nova SessionLease elegível restaura Cloud renew no mesmo authority epoch se source lease ainda válida;
- request bloqueada até expiry revalida clock pós-lock.

### 19.5 Failover

- brief heartbeat loss => no grant;
- liveness stale sem hysteresis => wait;
- snapshot stale com heartbeat healthy => wait/grant nos boundaries;
- Cloud standby stale => no grant;
- persistent state false => no grant;
- auth absent => no grant;
- all gates green => `failover_granted`;
- two devices isolados.

### 19.6 Failback

- 1 heartbeat => wait;
- 2 heartbeats => wait;
- 3 heartbeats mas <120 s => wait;
- >=3 + >=120 s + Cloud active >=120 => `failback_granted`;
- instance change resets;
- degraded heartbeat resets;
- API restart preserves continuity.

### 19.7 Same-source reacquisition

Desktop:
- new boot before 90 s => blocked;
- boundary 90 s com novo Desktop saudável/candidate válido => eligibility conforme policy;
- old holder write depois do novo grant => fenced.

Cloud:
- new instance before 60 s => blocked;
- >=60 s + gates verdes => eligibility;
- old Cloud holder depois do novo grant => fenced.

Se o boundary Desktop 90 s mostrar risco estrutural, STOP arquitetura.

### 19.8 Anti-spoof

- client tentando enviar `failover_granted` não ganha gate;
- client tentando enviar `failback_granted` não ganha gate;
- non-holder heartbeat nunca recebe future grant token.

---

## 20. PostgreSQL real

Rodar os cenários temporais e de concorrência relevantes em PostgreSQL efêmero.

Cobertura mínima:

- heartbeat upsert concorrente;
- renewal × expiry;
- renewal × administrative fencing;
- policy evaluation × snapshot recovery;
- failover gate × recovery current-grant;
- failback gate × Cloud write/authority state;
- same-source reacquire × old holder current-grant;
- API connections independentes;
- cross-device isolation.

Resultado:
- sem deadlock;
- authority epoch monotônico;
- nenhum stale reason concede transition depois de state incompatível;
- loser não sobrescreve winner.

---

## 21. PWA e compatibilidade

GET atual permanece exatamente:

`{snapshot, meta}`

Nenhum campo C3 novo no envelope PWA.

Não criar MobileSnapshot v3.

Nenhuma página PWA precisa consumir source heartbeat/status em C3-C.

Frontend contract deve continuar verde.

---

## 22. Segurança

Auditar:

- Device auth no Desktop heartbeat;
- CloudBinding auth no Cloud heartbeat;
- nenhum secret em query;
- nenhum cookie/SessionLease plaintext em heartbeat;
- reason de arbitration não controlado pelo client;
- no authority token para non-holder;
- RLS/privileges das funções novas;
- `SECURITY DEFINER` com `search_path` seguro;
- execute revogado de PUBLIC/anon/authenticated quando aplicável.

---

## 23. TDD e sequência recomendada

1. contratos de heartbeat/policy;
2. heartbeat persistence;
3. classification boundaries;
4. snapshot freshness;
5. renewal;
6. hysteresis;
7. failover eligibility;
8. failback eligibility;
9. same-source reacquisition;
10. API endpoints/auth;
11. PostgreSQL concurrency;
12. security;
13. regressões.

Registrar RED→GREEN real no handoff.

---

## 24. Gates obrigatórios

No mínimo:

- unit tests C3-C/policy;
- endpoint auth/contract tests;
- repository/RPC tests;
- PostgreSQL real;
- C3-B regressions;
- SessionLease/CloudBinding regressions relevantes;
- `make test-all`;
- frontend snapshot contract;
- migration chain 001→021 se 021 for alterada;
- `git diff --check`;
- untracked diff check;
- security grep;
- staged files = 0;
- Desktop worktree limpo;
- Shadow intacto.

Se 021 não for alterada, ainda provar que C3-C usa a migration já versionada sem criar 022.

---

## 25. Restrições absolutas

Não autorizado:

- Desktop real começar a enviar heartbeat;
- Desktop SnapshotHttpClient real enviar authority headers;
- Cloud snapshot endpoint operacional;
- Cloud writer;
- WebPilot real no Cloud;
- persistent volume Northflank;
- alteração remota Northflank;
- managed mode real;
- failover/failback real;
- migration 021 produção;
- deploy;
- push;
- merge;
- cutover;
- eventos/push;
- C3-D.

---

## 26. Entrega ao R12

Ao terminar:

- não fazer commit;
- não fazer stage;
- não iniciar C3-D;
- atualizar handoff central.

Registrar:

- SHA de entrada `4691c24`;
- arquivos alterados;
- RED→GREEN;
- endpoint contracts;
- classification boundaries;
- clock strategy;
- renewal semantics;
- snapshot stale persistence;
- failover/failback eligibility;
- same-source reacquisition policy;
- PostgreSQL races;
- auth/security;
- PWA compatibility;
- `make test-all`;
- migration evidence;
- `git diff --check`;
- staged=0;
- Shadow intacto;
- confirmação de nenhuma ação de produção.

Finalizar exatamente:

**C3-C PRONTO PARA R12 INDEPENDENTE**

e parar.

---

## 27. Critério de aprovação R12

R12 deve revisar independentemente:

- boundaries temporais;
- clock pós-lock;
- persistência/restart safety;
- heartbeat anti-spoof;
- renewal sem resurrect;
- recovery snapshot sem failover;
- failover hysteresis;
- failback 3 heartbeats/120 s;
- same-source reacquisition Desktop/Cloud;
- auth/source separation;
- cross-device isolation;
- ausência de Cloud writer real;
- ausência de produção/C3-D.

Somente após R12 APROVADO poderá existir commit exato C3-C.

C3-D não começa automaticamente após esse commit.


---

## 28. R12-F1 — proposta arquitetural SOMENTE DOCUMENTAL para R12.1 (2026-10-09)

**Situação:** R12-F1 ABERTO, STOP arquitetura. Este bloco é uma **proposta sujeita a R12.1 independente**; não autoriza implementar SQL, código, testes executáveis, migration 022, commit nem C3-D. Até aprovação, o C3-C funcional existente permanece não aprovado. Em caso de divergência, este adendo de proposta substitui os pressupostos de linha única por source descritos nas §§7, 14, 17, 18, 19 e no C3-P §5.2, *somente após aprovação de R12.1*.

### 28.1 Falha, raízes e separação conceitual

R12 demonstrou em PostgreSQL real: (a) Desktop holder A heartbeat 181 s stale + snapshot fresh, mas heartbeat de candidate B substitui A na PK `(device_id,source)`, mascarando o failover Desktop→Cloud; (b) após gate de B e write de A, o gate é invalidado, mas o heartbeat A desaparecido impede nova avaliação após 91 s; Cloud→Cloud reproduz o caso com 61 s. Os 801 testes verdes não exercitavam a sequência A→B→A write→B→tempo→B.

**Representação proposta:** usar as colunas já existentes de `public.device_source_heartbeats`, porém com **chave composta `(device_id, source, instance_id)`**. Uma linha corresponde a uma identidade imutável de processo (não a um cargo de holder) e guarda sua própria recepção server-side, collection health, `healthy_since`, contagem, candidate freshness, persistent state, `updated_at` e reason meramente diagnóstico. `instance_id` não é atualizado em conflito. Manter `device_source_authority(device_id)` como única fonte da **identidade atual de holder**, incluindo `active_source`, `holder_instance_id`, `authority_epoch`, `authority_lease_id`, `last_authoritative_snapshot_at`, `updated_at`. Nenhum campo `is_holder` manipulável pelo cliente.

- **Holder record:** somente a heartbeat row identificada por `(authority.device_id, authority.active_source, authority.holder_instance_id)`, resolvida a partir da authority atual **da mesma transação**.
- **Candidate record:** heartbeat row `(device_id, p_source, p_instance_id)`; inclusive standby da outra source, sem herdar contagem/saúde do holder.
- **Mesmo source:** A e B mantêm linhas distintas ao mesmo tempo. B pode ter heartbeat quando A está healthy ou stale, sem sobrescrever A nem receber grant.
- **Troca de authority:** o identificador de holder muda exclusivamente na transação de transition winner; os registros por instance permanecem históricos/consultáveis. Após winner B, consultar liveness de B; A não é mais holder, ainda que seus heartbeats cheguem.
- **Sem evidência autoritativa inequívoca:** não substituir holder por "linha mais recente" ou qualquer candidate; não inferir liveness saudável/stale a partir do source agregado. Para same-source reacquire, ausência/inconsistência da linha do holder é bloqueio tipado fail-closed; não tratar NULL como "já está stale". Para cross-source, caminho de snapshot-stale mantém sua condição **independente** e exige seus próprios gates.
- **API restart:** a identidade do holder vive em authority persistente; ambas as heartbeat rows, continuity e markers vivem no PostgreSQL; nenhum timer decisório em FastAPI.

**Estratégia de schema (proposta, não executada):** 021 ainda não está em produção. Depois de R12.1, adaptar **a definição local da migration 021** para a PK composta, sem 022, e reexecutar do zero migrations 001→021 em banco descartável. Não aplicar mudança de PK por `ALTER` num banco compartilhado existente nem presumir migration 021 já aplicada automaticamente; ensaios efêmeros devem recriar schema limpo. Uma necessidade real de nova coluna/tabela, migração incremental de ambiente já aplicado ou mudança operacional não coberta exigirá **novo STOP arquitetura**, não criação tácita de 022. R12.1 deve aprovar explicitamente essa fronteira.

### 28.2 Invariantes de identidade, tempo, elegibilidade e anti-spoof

1. **Fonte exclusiva de holder:** `device_source_authority`; nenhuma heartbeat candidate, mesmo auth válida, troca epoch/lease/holder. `source_candidate_reason` é cálculo interno sob estado serializado, não autoridade do client.
2. **Identidades não intercambiáveis:** cada upsert modifica somente `(device_id, source, instance_id)`; duas instâncias do mesmo source não se sobrescrevem. `healthy_since/consecutive_healthy` pertencem somente à mesma instance e resetam em unhealthy ou gap temporal. Uma instance B não herda continuidade A.
3. **Liveness para failover:** ler **apenas** heartbeat do holder atual Desktop A. Desktop A age >=120 s é STALE e age >=180 s completa hysteresis de 60 s, inclusive com snapshot A recente; heartbeat de B non-holder nunca posterga a janela. Snapshot stale do holder (120+60 s Desktop) continua caminho independente. Cloud standby fresh/health/auth gates são exigidos.
4. **Renewal:** só request da instance que coincide com holder; checa linha de saúde dessa instance, snapshot autoritativo fresh, lease atual não expirada e gates admin/auth sob lock. Candidate B nunca estende lease A e nunca recebe grant. `write eligibility != renew eligibility` preservado; recovery snapshot de A, ainda não fenced/expired, pode ser aceito sem heartbeat de B alterar a decisão.
5. **Same-source restart:** exigir `p_instance_id != holder_instance_id`, candidate row válida, fresh e saudável, e **silêncio efetivo do holder** por pelo menos **90 s Desktop / 60 s Cloud**, com thresholds inclusivos exatamente em 90/60 e rejection estrita antes. Para proteger o retorno tardio, o silêncio efetivo é medido contra `max(holder.last_heartbeat_at, authority.last_authoritative_snapshot_at)` **da authority/grant corrente**, pois um current-grant snapshot aceito de A é evidência server-side de atividade do writer A, mesmo sem heartbeat. Isto **não** mistura os três sinais: cross-source failover continua avaliando heartbeat e snapshot freshness separadamente; `max` é somente um guarda adicional contra takeover **same-source** durante atividade do holder.
6. **Atividade do holder invalida gate antigo:** current-grant write/renew/heartbeat do holder posterior à decisão de B atualiza o estado serializado relevante; uma decisão de B anterior não é portável nem permanente. Depois de completo novo período de silêncio do holder, com B ainda healthy/fresh, o gate volta a ser elegível. Atualização de `authority.updated_at` continua servindo a version/fence, nunca deve ser a única lembrança do heartbeat A.
7. **Gate temporário, não token de cliente:** reason diagnóstico `desktop_reacquire_granted/cloud_reacquire_granted` pode ser derivado no heartbeat ou retorno de status, mas o `transition_candidate` **recalcula** `holder + candidate + authority + now` sob locks. Nenhuma autorização decorre exclusivamente de `last_reason_code`, `candidate.updated_at > authority.updated_at` ou expiry. Checar candidate freshness, boot/instance, grant/epoch atual, policy time, admin/auth no momento do winner. Não reutilizar gate após mudança de authority.
8. **Epoch e lease:** só transação winner incrementa epoch e gera lease, antiga fica fenced; renewal preserva ambos. Side effects existentes e `realm_epoch` separado não mudam. Cloud auth, binding, realm/membership e `persistent_state_ready` são gates independentes do candidate.
9. **Falhas seguras:** ausência/duplicidade inconsistente do holder, falta de candidate, candidate stale, absence de auth, source errada, device disabled, clock incoerente, grant já substituído => deny tipado, sem alterar snapshot/authority. Nenhum fallback para heartbeat de outra instance ou "mais recente".
10. **Observabilidade:** classificador HEALTHY/DEGRADED/STALE/OFFLINE por instance; status agregado do holder usa pointer da authority. Não devolver future authority metadata a non-holder, não expor segredos em logs/response.

**Ponto de decisão explícito para R12.1:** validar que o guarda de **última atividade autoritativa do holder** (heartbeat ou snapshot aceito) é compatível com a preference/reacquisition aprovada de 90/60. É intencionalmente mais conservador do que decidir por heartbeat isolado; **não alterar silenciosamente os thresholds**. Se o revisor discordar, manter STOP e decidir separadamente como invalidar gate após snapshot do holder sem violar R12-F1b.

### 28.3 Lock order canônico e revalidação depois do lock

**Transações mutadoras por device (heartbeat, bootstrap, current write, transition):**

1. `public.devices[device_id] FOR UPDATE` primeiro; essa linha funciona como serializador entre requests para o mesmo device. Não usar pre-read sem lock como decisão.
2. Se Cloud: CloudBinding exato do device → realm → owner membership, sob locks existentes e auth/session revalidadas; não promover `realm_epoch` a fencing token.
3. Com device já travado, pode-se ler authority **sem lock apenas para descobrir** `active_source/holder_instance_id/epoch` e as duas chaves heartbeat relevantes. Essa leitura **não autoriza** grant.
4. Bloquear heartbeat rows de holder e candidate usando chave **`(device_id, source, instance_id)`**, sem nunca usar `WHERE source=...` isolado. Quando forem duas linhas, lock em ordem determinística **`source ASC, instance_id ASC`**; se uma não existe, o `devices` lock deve serializar seu futuro INSERT. Upsert apenas no registro da instance emissora. Um read de holder não pode selecionar B por conveniência.
5. Bloquear `device_source_authority[device_id] FOR UPDATE` **depois** das heartbeat rows, preservando a ordem já documentada em C3-B: `devices → [Cloud auth] → heartbeat(s) → authority`. Revalidar `mode, source, instance/holder, epoch, lease, updated_at` contra os identificadores usados para selecionar as rows. Se authority mudou fora do serializador ou a seleção ficou obsoleta, **rejeitar/reiniciar a transação inteira** em ordem, nunca capturar uma nova heartbeat row depois de travar authority (evita inversão/deadlock).
6. Obter `clock_timestamp()` fresco **após todos os locks**; classificar e decidir. Aplicar renew ou novo grant somente dentro dessa transação; recalcular gate no `transition_candidate` vencedor, não confiar em retorno anterior de heartbeat.
7. Atualizar authority e metadata de snapshot/histórico quando cabível; realizar write/return atômicos. Todas as RPCs C3-B que consultam heartbeat — inclusive bootstrap — devem selecionar a **instance exata** (legacy snapshot `boot_id`), não `source` genérico.

**Contratos e adaptação obrigatórios após R12.1:** `SourceHeartbeatRepository.get_source_heartbeat(device_id,source)`, Postgres/Supabase adapters, status/diagnostics e fixtures de testes devem tornar a identidade explícita (por `instance_id` ou seleção de holder baseada em authority); nunca trocar por `ORDER BY last_heartbeat_at DESC LIMIT 1` para arbitragem. C3-B bootstrap passa a usar o `boot_id` do snapshot legado e heartbeat da mesma instance. Cloud auth permanece revalidada na transação antes de conceder eligibility ou renewal. Verificar triggers administrativos que travam authority sem bloquear heartbeat para ausência de deadlock e revalidação pós-lock.

### 28.4 Matriz de RED PostgreSQL obrigatória (depois de R12.1, antes do GREEN)

Todos os testes devem ser **RED contra o C3-C atual** e guardar estados SQL/linhas para provar a causa, não somente uma string reason. Usar PG efêmero real e clocks server-side injetados/ages controlados; nenhuma espera real de 90/60/180 s.

| Caso | Preparação e transição | Asserção determinística obrigatória |
| --- | --- | --- |
| **F1a Desktop + failover** | A Desktop holder; heartbeat A age 181 s, snapshot A fresh, Cloud standby todos gates verdes; B Desktop same-source heartbeat fresh e candidate não-holder | A row **preservada** (181 s), B row distinta; Cloud `failover_granted` apesar de B; autoridade e snapshot só mudam com transition winner, não por B heartbeat |
| **F1a sem Cloud gate** | Mesmo A/B, Cloud persistent state false ou auth inválida | Failover não concedido; B ainda não mascara o tempo de A |
| **F1b Desktop** | A holder; heartbeat A age 91 s **e último snapshot autoritativo age 100 s (ainda <120 s, mas sem atividade A há >=90 s)**; B recebe initial eligibility; A aceita current-grant snapshot; B heartbeat após A write; avançar 89→90→91 s sem atividade A mantendo B fresh | Gate B antigo invalidado após A write; antes de 90 s `authority_fenced`; aos 90 s nova eligibility; B vence com epoch+1; A writer antigo fenced; linhas A/B intactas |
| **F1b Cloud** | A Cloud holder; heartbeat A age 61 s **e snapshot autoritativo age 70 s (ainda <90 s)**; B candidate com binding/realm/membership/SessionLease/persistent gates; B obtém elegibilidade inicial, A current write válido; avançar 59→60→61 s sem A activity | B antigo gate invalidado; <60 blocked, >=60 eligible, B novo grant; A fenced, rows não sobrescritas |
| **Candidate repeated** | A holder health fresh, B heartbeats repetidos ao longo de >180 s; snapshot holder não perde freshness | Liveness A preservada, B nunca incrementa contagem/health A; sem same-source reacquire antes threshold; cross-source decide pelo heartbeat A, não B |
| **Holder recovery × transition** | A snapshot aceito sob grant válido em paralelo com B same-source `transition_candidate`; duas conexões PG | Único winner serializado: se recovery A vence, B gate anterior invalida e não assume cedo; se B vence, A fenced e snapshot A não sobrescreve |
| **Holder heartbeat × gate** | B candidate já eligible; A heartbeat chega antes da transition B no mesmo device | B ineligible após A activity; nenhuma authority/snapshot alteração por B |
| **Duplo B/C** | A holder stale, candidates B/C simultâneos, cada um com sua heartbeat row | No máximo um grant novo, epoch monotônico, loser fenced/ineligible; identities B/C não se sobrescrevem |
| **Missing holder/late gate** | Forçar ausência de heartbeat **da instance holder** (sem substituir por B); heartbeat B fresh | fail-closed na via reacquisition; não há inferência de A a partir de B nem reuso de reason antigo |
| **Bootstrap antigo** | legacy snapshot boot A, heartbeat A válido, heartbeat B mais recente | Só A pode bootstrap; B não "ganha" por ser último; ausência de A => bootstrap ineligible |
| **API restart** | Persistir A holder stale, B candidate fresh, marcador invalidado por A write, retomar com repo/API novo | Mesmos holder/candidate records, mesmo epoch/lease/updated_at; mesma decisão temporal para clocks iguais; reeligibilidade no threshold |
| **Interdevice / admin / TTL** | Duas devices, device disabled, Cloud auth revogada, expiry de lease; candidate de outro device | Não cruzar identidades; admin vence; expiry não concede grant sozinho; sem resurrection; zero secret leak |
| **Query e privilégio** | Repetir migration 001→021/contract de schema, RLS e permission checks | PK per-instance aprovada; funções privileged somente backend; Postgres/Supabase lookups explicitamente por instance; 021 idempotente em DB limpo |
| **Regressões** | Suite C1+C2+C3-B+C3-C, PWA contract, `make test-all` | Manter fencing, recovery write!=renew, side effect baseline e GET `{snapshot,meta}`; nenhum skip indevido de teste PostgreSQL |

**Obrigatório:** RED que reproduz exatamente R12-F1a/F1b para **Desktop e Cloud**, incluindo regressão de não mascarar failover com snapshot fresh e teste da reeligibilidade após gate invalidado. Não enfraquecer asserts apenas para fazer o GREEN. Executar primeiro os RED e registrar outputs no handoff; nenhuma implementação até R12.1 aprovar esta proposta.

### 28.5 R12.1 — critérios de aprovação deste desenho (sem execução funcional)

Revisor deve verificar no plano/handoff, no mínimo: identidade holder/candidate separável; proveniência de liveness preservada sob heartbeat do non-holder; dupla fonte de atividade do holder usada **somente em reacquisition**, sem mascarar snapshot freshness/failover; gate invalidado e reeligível; lock order compatível com C3-B e triggers; PostgreSQL test matrix reproduzível; estratégia migration 021 sem 022; nenhuma alteração funcional desta etapa documental. Se houver incongruência, devolver achados `R12.1-Fn` documentais; **não autorizar implementação/commit/C3-D** até gate formal.
