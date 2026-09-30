# SPEC 025 Plan 1 — WebPilot HTTP/Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Criar a base compartilhada de sessão autenticada WebPilot e o cliente HTTP reutilizável, sem ativar ainda meteorologia WebPilot nem shadow de movimentações.

**Architecture:** BrowserSession/Selenium continua sendo o único dono do login e do WebDriver. Um WebPilotAuthCoordinator thread-safe publica snapshots imutáveis de cookies com geração monotônica, coordena uma única recuperação por vez e expõe a sessão ao WebPilotHttpClient. O cliente usa urllib, detecta login/timeout/HTTP error e repete no máximo uma vez depois de uma geração mais nova.

**Tech Stack:** Python 3.12+, Selenium, threading.Condition/Event, urllib da stdlib, pytest.

**Spec:** specs/025-webpilot-http-observed-weather-shadow-migration.md

## Global Constraints

- Selenium continua oficial para movimentações.
- Nenhum consumidor implementa login.
- Sessão coordenada por origem WebPilot.
- Renovação reativa, sem timer fixo.
- Uma recuperação concorrente por vez.
- No máximo um retry HTTP após nova geração.
- Não registrar cookies, headers ou credenciais.
- Nenhum I/O novo na Tk main thread.
- TDD RED -> GREEN -> REFACTOR.
- Não commit/push sem autorização explícita.

## Review Focus

- Expiração reportada por uma geração antiga depois que uma geração nova já existe não pode disparar nova recuperação.
- Dois consumidores simultâneos devem compartilhar exatamente uma recuperação.
- HTTP 200 contendo página de login deve ser SESSION_EXPIRED, não OK.
- Falha/timeout da recuperação não pode deixar waiters bloqueados.
- Cookies malformados ou vazios não podem aparecer em log nem quebrar o processo; a operação deve falhar de forma segura.

---

### Task 1: Criar o coordenador thread-safe de sessão WebPilot

**Files:**
- Create: /home/ciro/dev/prog/alertamaritimo/src/alertam/application/webpilot_auth.py
- Create: /home/ciro/dev/prog/alertamaritimo/tests/unit/test_webpilot_auth.py

**Interfaces:**
- Produces: SessionLease(generation: int, cookies: tuple[Mapping[str, object], ...])
- Produces: AuthState enum com AUTHENTICATED, RECOVERING, UNAVAILABLE
- Produces: WebPilotAuthCoordinator.publish(cookies) -> SessionLease
- Produces: WebPilotAuthCoordinator.current() -> SessionLease | None
- Produces: WebPilotAuthCoordinator.report_expired(generation: int) -> bool
- Produces: WebPilotAuthCoordinator.wait_for_newer(generation: int, timeout: float | None = None) -> SessionLease | None
- Produces: WebPilotAuthCoordinator.mark_recovery_failed() -> None
- Consumes: request_recovery: Callable[[], None] injetado no construtor.

- [ ] **Step 1: Write failing tests for publish/current/generation**

Test names:
- test_publish_creates_immutable_lease_and_increments_generation
- test_current_returns_none_before_first_publish
- test_published_cookies_are_defensively_copied

Assertions:
- first publish => generation 1;
- second publish => generation 2;
- changing caller-owned dict after publish does not mutate lease.

- [ ] **Step 2: Run focused tests and verify RED**

Run:
    cd /home/ciro/dev/prog/alertamaritimo
    uv run pytest tests/unit/test_webpilot_auth.py -q

Expected: FAIL because alertam.application.webpilot_auth does not exist.

- [ ] **Step 3: Implement SessionLease/AuthState/WebPilotAuthCoordinator minimal publish/current behavior**

Use a threading.Condition around state, generation and current lease. Do not expose mutable cookie dictionaries directly.

- [ ] **Step 4: Write failing concurrency tests**

Test names:
- test_two_expirations_same_generation_request_one_recovery
- test_expiration_from_old_generation_is_ignored
- test_wait_for_newer_returns_new_generation
- test_mark_recovery_failed_releases_waiters_with_none

Use two threads/barriers; assert request_recovery is called once.

- [ ] **Step 5: Implement recovery coordination**

report_expired(generation):
- return False without recovery when current generation is already newer;
- first current-generation caller switches state to RECOVERING and invokes request_recovery once;
- concurrent callers return False and share the same recovery;
- publish() releases waiters and returns AUTHENTICATED;
- mark_recovery_failed() releases waiters and sets UNAVAILABLE without deleting a previously published lease object from history.

- [ ] **Step 6: Run focused tests GREEN**

Run:
    uv run pytest tests/unit/test_webpilot_auth.py -q

Expected: PASS.

- [ ] **Step 7: Checkpoint/commit only if explicitly authorized**

Suggested message:
    feat: coordena sessao compartilhada do WebPilot

---

### Task 2: Exportar cookies autenticados somente pelo SeleniumWorker

**Files:**
- Modify: /home/ciro/dev/prog/alertamaritimo/src/alertam/infrastructure/browser.py
- Modify: /home/ciro/dev/prog/alertamaritimo/src/alertam/application/messages.py
- Modify: /home/ciro/dev/prog/alertamaritimo/src/alertam/bootstrap.py
- Modify: /home/ciro/dev/prog/alertamaritimo/src/alertam/application/controller.py
- Modify/Test: /home/ciro/dev/prog/alertamaritimo/tests/unit/test_controller_pipeline.py
- Create/Test: /home/ciro/dev/prog/alertamaritimo/tests/unit/test_webpilot_session_bootstrap.py

**Interfaces:**
- Produces: BrowserSession.export_cookies() -> tuple[dict[str, object], ...]
- Produces: CommandType.EXPORT_WEBPILOT_SESSION
- Produces: ResultType.WEBPILOT_SESSION_EXPORTED
- Produces: cmd_export_webpilot_session() -> WorkerCommand
- Produces: result_webpilot_session_exported(cookies) -> WorkerResult
- Controller constructor gains optional on_webpilot_session: Callable[[tuple[dict[str, object], ...]], None] | None
- Controller produces request_webpilot_recovery() -> bool

- [ ] **Step 1: Write failing BrowserSession export tests**

Add a fake driver returning cookies and assert export_cookies:
- requires a driver;
- returns copies, not the driver's list object;
- never writes the cookies to log.

- [ ] **Step 2: Implement BrowserSession.export_cookies**

It may call driver.get_cookies only on the Selenium worker thread. It must return an empty tuple on missing driver/error and log only a safe message without cookie values.

- [ ] **Step 3: Write failing message/worker tests**

Assert:
- EXPORT_WEBPILOT_SESSION command exists;
- SeleniumWorker handles it by calling browser.export_cookies;
- WEBPILOT_SESSION_EXPORTED payload carries the in-memory tuple;
- WorkerResult repr/logging is never intentionally emitted with this payload.

- [ ] **Step 4: Implement worker message plumbing**

Add enum values/helpers and a SeleniumWorker branch. Do not persist the exported cookies.

- [ ] **Step 5: Write failing Controller tests for publish and recovery**

Scenarios:
- SESSION_VALID while monitoring requests EXPORT_WEBPILOT_SESSION;
- WEBPILOT_SESSION_EXPORTED invokes on_webpilot_session;
- request_webpilot_recovery while MONITORING sends VALIDATE_SESSION without opening a second browser;
- SESSION_INVALID keeps existing login flow;
- recovery request outside MONITORING returns False.

- [ ] **Step 6: Implement Controller hooks**

Keep current login UX unchanged. A valid hidden session should cause export. A manual login that returns to a valid hidden session should also export before/when monitoring resumes.

- [ ] **Step 7: Wire Application to WebPilotAuthCoordinator without activating consumers**

Application creates WebPilotAuthCoordinator with request_recovery=self.controller.request_webpilot_recovery after Controller exists, and publishes cookies from on_webpilot_session callback. If constructor order requires it, use a small callback closure rather than letting the coordinator know Controller internals.

- [ ] **Step 8: Run focused regression tests**

Run:
    uv run pytest tests/unit/test_webpilot_auth.py tests/unit/test_controller_pipeline.py tests/unit/test_webpilot_session_bootstrap.py -q

Expected: PASS and existing login tests remain green.

- [ ] **Step 9: Checkpoint/commit only if explicitly authorized**

Suggested message:
    feat: publica sessao WebPilot para consumidores HTTP

---

### Task 3: Implementar o WebPilotHttpClient com retry único

**Files:**
- Create: /home/ciro/dev/prog/alertamaritimo/src/alertam/infrastructure/webpilot_http.py
- Create: /home/ciro/dev/prog/alertamaritimo/tests/unit/test_webpilot_http.py
- Modify: /home/ciro/dev/prog/alertamaritimo/src/alertam/settings.py

**Interfaces:**
- Produces: WebPilotHttpStatus enum: OK, SESSION_EXPIRED, TIMEOUT, HTTP_ERROR
- Produces: RawHttpResponse(status_code: int, final_url: str, body: bytes)
- Produces: WebPilotHttpResult(status: WebPilotHttpStatus, body: bytes, final_url: str | None, generation: int | None, error: str | None)
- Produces: WebPilotHttpClient.__init__(auth: WebPilotAuthCoordinator, timeout: float, transport: Callable | None = None, user_agent: str = HTTP_USER_AGENT, recovery_wait_seconds: float = 10.0)
- Produces: WebPilotHttpClient.get(url: str) -> WebPilotHttpResult
- Settings gains webpilot_http_timeout_seconds from ALERTAM_WEBPILOT_HTTP_TIMEOUT_SECONDS, default equal to current page timeout or explicit 10 seconds.

- [ ] **Step 1: Write failing transport classification tests**

Use injected fake transport. Cover:
- authenticated 200 => OK/body preserved;
- final_url contains WEBPILOT_LOGIN_PATH => SESSION_EXPIRED;
- 200 body with login password field/id => SESSION_EXPIRED;
- TimeoutError/socket timeout => TIMEOUT;
- urllib HTTPError/5xx => HTTP_ERROR;
- empty authenticated body => OK at transport layer; content validation belongs to consumer.

- [ ] **Step 2: Implement default urllib transport and classification**

Build Cookie header only from non-empty name/value pairs in SessionLease. Do not put Cookie/header values in result.error or logs.

- [ ] **Step 3: Write failing retry tests**

Scenarios:
- generation 1 returns SESSION_EXPIRED, report_expired triggers recovery, generation 2 published, second transport call returns OK;
- only two transport calls maximum;
- second SESSION_EXPIRED returns SESSION_EXPIRED without a new nested retry;
- no current lease returns SESSION_EXPIRED safely;
- old-generation failure after generation 2 does not call recovery callback again.

- [ ] **Step 4: Implement one-retry flow**

Algorithm:
1. read current lease;
2. execute once;
3. if not SESSION_EXPIRED, return;
4. report expiration for the used generation;
5. wait for a newer generation up to recovery_wait_seconds;
6. when available, execute exactly once more;
7. return second result without recursively retrying.

- [ ] **Step 5: Add secret-safety regression test**

Capture logs and raised errors. Assert literal fake cookie value "TOP-SECRET-COOKIE" never appears. Add a case with empty/malformed cookie dictionaries: unusable entries are ignored safely, no secret value is logged, and an empty usable-cookie set does not crash header construction.

- [ ] **Step 6: Run focused tests GREEN**

Run:
    uv run pytest tests/unit/test_webpilot_auth.py tests/unit/test_webpilot_http.py tests/unit/test_webpilot_session_bootstrap.py tests/unit/test_controller_pipeline.py -q

Expected: PASS.

- [ ] **Step 7: Checkpoint/commit only if explicitly authorized**

Suggested message:
    feat: adiciona cliente HTTP autenticado do WebPilot

---

### Task 4: Fechar a fase com regressão completa sem consumidor ativo

**Files:**
- Modify: /home/ciro/dev/prog/alertamaritimo/README.md only if runtime/configuration variable needs documentation.
- Test only: existing Desktop suite.

**Interfaces:**
- Consumes all Plan 1 interfaces.
- Produces a stable base for Plan 2 and Plan 4.

- [ ] **Step 1: Document ALERTAM_WEBPILOT_HTTP_TIMEOUT_SECONDS only if exposed to operators/support**

Do not document cookies or session internals as values the user should configure.

- [ ] **Step 2: Run full Desktop suite**

Run:
    cd /home/ciro/dev/prog/alertamaritimo
    uv run pytest

Expected: complete suite PASS, except existing intentional skips.

- [ ] **Step 3: Verify no HTTP consumer has been started**

Search/bootstrap assertion:
- no WebPilotWeatherService yet;
- no ManeuverShadowService yet;
- no behavioral change to official collection.

- [ ] **Step 4: Run diff/security checks**

Run:
    git diff --check
    git status --short --branch

Inspect added lines for cookie/credential literals. No real session value may exist in tests/docs.

- [ ] **Step 5: Human review gate**

Stop here. Plan 2 may begin only after review of Plan 1 implementation. Do not start Plan 2 automatically.

- [ ] **Step 6: Checkpoint/commit only if explicitly authorized**

Suggested message:
    feat: conclui base HTTP e autenticacao WebPilot
