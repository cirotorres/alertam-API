# SPEC 025 — Implementation Plan Overview

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement these plans task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Implementar a Fundação WebPilot e provar o collector HTTP em shadow antes de liberar a SPEC 027 — AlertaM Cloud, preservando Selenium como fonte oficial do Desktop durante toda a SPEC 025.

**Architecture:** A trilha crítica separa autenticação WebPilot, transporte HTTP e meteorologia (Plans 1–2), depois prova o mesmo núcleo em shadow com evidência operacional (Plans 4–5). O MobileSnapshot v2 (Plan 3) permanece uma trilha lateral compatível, não um bloqueio para Shadow/Cloud. A refatoração ampla do Desktop fica deliberadamente para depois do Cloud.

**Tech Stack:** Python 3.12+, Tkinter, Selenium, urllib/html.parser da stdlib, pytest, FastAPI/Pydantic, Supabase/Postgres existente, React/Vite/TypeScript, Zod, Vitest.

**Spec:** specs/025-webpilot-http-observed-weather-shadow-migration.md
**Roadmap:** docs/superpowers/strategy/2026-10-02-alertam-cloud-evolution-roadmap.md

## Global Constraints

- Nenhum plano realiza cutover das movimentações para HTTP.
- Selenium permanece fonte oficial operacional durante toda a SPEC 025.
- WebPilot observado é a fonte atmosférica prioritária quando saudável.
- Open-Meteo Forecast permanece fallback/complemento identificado.
- Open-Meteo Marine permanece fonte marítima.
- Não misturar silenciosamente campos WebPilot e Open-Meteo.
- observed_at governa a idade da observação; consulted_at é apenas horário de consulta.
- Freshness é calculado no Desktop; API/PWA apenas transportam/apresentam.
- Estados meteorológicos: fresh, stale e unavailable.
- Sessões são coordenadas por realm/origem autenticada, não por consumidor.
- WebPilotAuthCoordinator depende de WebPilotSessionProvider e não conhece Selenium/Controller.
- No Desktop, Selenium é apenas o provider concreto e publica a mesma sessão já autenticada para HTTP.
- SessionLease preserva expires_at quando disponível; expiry é advisory e não substitui validação semântica.
- Renovação WebPilot é reativa; não criar timer fixo de relogin na SPEC 025.
- Uma recuperação de sessão por vez e no máximo um retry por operação HTTP.
- Toda rede/recuperação fica fora da Tk main thread.
- Usar urllib e html.parser; não adicionar requests/httpx ao Desktop.
- Fixtures devem ser sanitizadas e nunca conter cookies/headers/credenciais reais.
- TDD obrigatório: RED -> GREEN -> REFACTOR.
- A extração deve produzir componentes headless reutilizáveis, sem refatoração ampla do núcleo legado.
- Não implementar Cloud dentro da SPEC 025; o gate apenas libera planejamento/execução da SPEC 027.
- Não fazer commit nem push durante execução sem autorização explícita do usuário.
- Quando houver autorização para commit, respeitar os checkpoints dos planos; push continua exigindo autorização explícita.

## Ordem obrigatória

### Trilha crítica A→B→C

1. Plan 1 — Base HTTP e autenticação coordenada.
2. Plan 2 — Meteorologia observada e coordinator.
3. Plan 4 — Shadow HTTP de movimentações usando a fundação validada.
4. Plan 5 — Gate, relatório e operação de evidência.
5. Gate humano aprovado → SPEC 027 — AlertaM Cloud.

### Trilha lateral

Plan 3 — MobileSnapshot v2, API e PWA — pode ser executado após Plan 2 ou em paralelo à preparação do shadow. Ele mantém seu rollout interno obrigatório API→PWA→Desktop, mas não bloqueia Plan 4/5 nem, por si só, a SPEC 027.

## Dependências

Plan 1 produz:
- WebPilotSessionProvider + DesktopSeleniumSessionProvider;
- WebPilotAuthCoordinator por realm;
- SessionLease com generation/cookies/expires_at opcional;
- WebPilotHttpClient;
- publicação segura da mesma sessão autenticada pelo worker Selenium, sem segundo login HTTP.

Plan 2 consome Plan 1 e produz:
- ObservedWeather;
- WebPilotWeatherService;
- WeatherCoordinator;
- WeatherComposite/estado meteorológico usado por Desktop e MobileSnapshot.

Plan 3 consome Plan 2 e produz:
- contrato MobileSnapshot v2 no Desktop;
- união v1/v2 na API;
- união v1/v2 na PWA;
- renderização mobile das fontes e estados.

Plan 4 depende tecnicamente de Plan 1 e do parser atual de navios; pelo roadmap, só começa depois de Plan 2 estar concluído/revisado. Produz:
- GridHtmlExtractor;
- ManeuverShadowComparator;
- ManeuverShadowService;
- ShadowMetricsStore/evidência sanitizada.

Plan 5 consome Plan 4 e produz:
- ShadowGateEvaluator;
- relatório de equivalência;
- runbook operacional para 24h + 500 ciclos + últimos 100 limpos.

## Gates entre planos

### Gate após Plan 1

- Suítes focadas de auth/HTTP verdes.
- Concorrência de recuperação coberta.
- Coordinator testado com provider falso, sem dependência de Selenium/Controller.
- Sessão inicial Selenium é publicada uma única vez para HTTP, sem segundo login.
- expiry conhecido vira expires_at UTC aware, mas não substitui detecção semântica de login.
- Nenhum broker Cloud/multi-Desktop foi implementado ainda.
- Nenhum consumidor meteorológico ou shadow ativado ainda.
- Nenhuma regressão no fluxo Selenium atual.

### Gate após Plan 2

- Meteorologia WebPilot funciona com fixtures e transporte falso.
- Fallback WebPilot/Open-Meteo respeita dois ciclos problemáticos.
- HUD/tooltip distinguem fonte e estado.
- Falha meteorológica não altera monitoramento de navios.

### Gate especial dentro do Plan 3

A ordem de rollout é parte do plano e não pode ser invertida:
- API aceita v1+v2;
- PWA aceita/renderiza v1+v2;
- smoke/deploy do consumidor é validado;
- somente então o Desktop passa a publicar schema_version 2.

### Gate após Plan 4

- Shadow desligado por padrão.
- Resultado HTTP nunca entra no pipeline operacional.
- Comparação e métricas estão prontas para observação real.
- Nenhum cutover é permitido.

### Gate final do Plan 5

O resultado técnico pode ser:
- atendido; ou
- não atendido.

Mesmo quando atendido:
- HTTP principal do Desktop continua NÃO autorizado;
- Cloud não é ativado automaticamente;
- a próxima ação da trilha principal é revisão humana e desbloqueio da SPEC 027;
- eventual cutover local Selenium→HTTP permanece uma decisão/spec separada.

## Documentos dos planos

- docs/superpowers/plans/2026-09-29-spec025-plan1-webpilot-http-auth.md
- docs/superpowers/plans/2026-09-29-spec025-plan2-observed-weather.md
- docs/superpowers/plans/2026-09-29-spec025-plan3-mobile-snapshot-v2.md
- docs/superpowers/plans/2026-09-29-spec025-plan4-maneuver-shadow.md
- docs/superpowers/plans/2026-09-29-spec025-plan5-shadow-evidence-gate.md

## Spec coverage map

- SPEC 025 §§1–5 (contexto, objetivos, não objetivos, princípios, arquitetura): overview + Global Constraints dos cinco planos.
- §6 (coordenação de sessão): Plan 1 Tasks 1–2.
- §7 (cliente HTTP): Plan 1 Task 3.
- §§8–9 (modelo observado e parser): Plan 2 Task 1.
- §10 (cadência/freshness WebPilot): Plan 2 Task 2.
- §§11–14 (cache, fallback, fontes, estados, WeatherCoordinator): Plan 2 Task 3.
- §15 (UX Desktop): Plan 2 Tasks 4–5.
- §§16–18 (MobileSnapshot v2, rollout e PWA): Plan 3 Tasks 1–7.
- §§19–21 (shadow, comparação e isolamento): Plan 4 Tasks 1–5.
- §§22–24 (métricas, gate e relatório): Plan 4 Task 3 + Plan 5 Tasks 1–3.
- §25 (TDD): todos os planos, com testes RED/GREEN por task.
- §26 (ordem): trilha crítica Plan 1→2→4→5, com Plan 3 lateral e SPEC 027 após gate humano.
- §27 (riscos): Review Focus + testes específicos em cada plano.
- §28 (arquivos): blocos Files de cada task.
- §29 (aceite de implementação): gates finais de Plans 1–4.
- §30 (gate operacional): Plan 5 Tasks 1, 4 e 5.
- §31 (encerramento/pós-implementação): Plan 5 Task 6 + transição documental para SPEC 027 quando gate aprovado.
- §32 (decisões explícitas): Global Constraints + hard STOP antes de Cloud/cutover + refatoração ampla somente após Cloud.

## Execution rule

Estes documentos são apenas planejamento. Não iniciar nenhum passo de implementação até o usuário aprovar explicitamente os planos e escolher/confirmar o método de execução.
