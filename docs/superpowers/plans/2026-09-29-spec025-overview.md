# SPEC 025 — Implementation Plan Overview

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement these plans task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Implementar a SPEC 025 em cinco fases independentes e revisáveis, preservando Selenium como fonte oficial das movimentações até uma SPEC futura de cutover.

**Architecture:** A implementação separa autenticação WebPilot, transporte HTTP, meteorologia observada, contrato MobileSnapshot v2, shadow de movimentações e avaliação operacional. Cada fase produz software testável por si só e fixa interfaces consumidas pela fase seguinte.

**Tech Stack:** Python 3.12+, Tkinter, Selenium, urllib/html.parser da stdlib, pytest, FastAPI/Pydantic, Supabase/Postgres existente, React/Vite/TypeScript, Zod, Vitest.

**Spec:** specs/025-webpilot-http-observed-weather-shadow-migration.md

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
- Sessões são coordenadas por origem autenticada, não por consumidor.
- Renovação WebPilot é reativa; não criar timer fixo de relogin.
- Uma recuperação de sessão por vez e no máximo um retry por operação HTTP.
- Toda rede/recuperação fica fora da Tk main thread.
- Usar urllib e html.parser; não adicionar requests/httpx ao Desktop.
- Fixtures devem ser sanitizadas e nunca conter cookies/headers/credenciais reais.
- TDD obrigatório: RED -> GREEN -> REFACTOR.
- Não fazer commit nem push durante execução sem autorização explícita do usuário.
- Quando houver autorização para commit, respeitar os checkpoints dos planos; push continua exigindo autorização explícita.

## Ordem obrigatória

1. Plan 1 — Base HTTP e autenticação coordenada.
2. Plan 2 — Meteorologia observada e coordinator.
3. Plan 3 — MobileSnapshot v2, API e PWA, com API/PWA preparados antes do Desktop publicar v2.
4. Plan 4 — Shadow HTTP de movimentações.
5. Plan 5 — Gate, relatório e operação de evidência.

## Dependências

Plan 1 produz:
- WebPilotAuthCoordinator;
- SessionLease;
- WebPilotHttpClient;
- publicação segura de sessão/cookies pelo worker Selenium.

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

Plan 4 consome Plan 1 e o parser atual de navios e produz:
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
- HTTP principal continua NÃO autorizado;
- a próxima ação é análise humana e uma SPEC posterior de cutover.

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
- §26 (cinco fases): esta divisão de Plan 1–5.
- §27 (riscos): Review Focus + testes específicos em cada plano.
- §28 (arquivos): blocos Files de cada task.
- §29 (aceite de implementação): gates finais de Plans 1–4.
- §30 (gate operacional): Plan 5 Tasks 1, 4 e 5.
- §31 (encerramento/pós-implementação): Plan 5 Task 6.
- §32 (decisões explícitas): Global Constraints + hard STOP antes de qualquer cutover.

## Execution rule

Estes documentos são apenas planejamento. Não iniciar nenhum passo de implementação até o usuário aprovar explicitamente os planos e escolher/confirmar o método de execução.
