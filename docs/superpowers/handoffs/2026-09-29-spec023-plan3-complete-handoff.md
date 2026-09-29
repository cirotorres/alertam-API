# Handoff — SPEC 023 Ship Tracking — Planos 1–3 implementados

Data: 2026-09-29

## Estado

A implementação planejada da SPEC 023 está concluída nos dois repositórios.

Resta apenas a validação manual Tk/Xephyr do Desktop, explicitamente delegada por Ciro para depois da implementação. Não afirmar que esse gate gráfico passou até Ciro executá-lo.

Nenhum push foi realizado nesta sessão.

Repos:
- Desktop: `/home/ciro/dev/prog/alertamaritimo`
- API/PWA: `/home/ciro/dev/prog/alertamaritimoAPI`

## Commits do Plano 3

Desktop Tasks 1–2:
`a6ce9d0 Feat: adiciona acompanhamento local e UX Desktop da SPEC 023`

API/PWA Tasks 3–4:
`121463d Feat: adiciona provider e ações de acompanhamento no PWA`

O commit final de Tasks 5–6 deve ter assunto:
`Feat: conclui Plano 3 da SPEC 023 - Desktop & PWA UX`

## Entregas finais Tasks 5–6

PWA:
- rota `/acompanhados`
- link Acompanhados no drawer
- lista somente trackings ativos da instalação atual
- navio ausente permanece listado com último estado conhecido
- `TrackedVesselSheet` reutiliza `BottomSheetFrame`
- timeline unificada MANEUVER/TRACKING na ordem da API
- deep link `?track=<tracked_vessel_id>&event=<event_id>`
- event selecionado destacado
- fechar remove track/event e mantém a página
- conflito SPEC 022/023 resolvido: com `track=`, o `event=` pertence à timeline de tracking e não abre AlertDetailSheet global
- DemoMode possui TrackingProvider vazio local e não chama API real

Foreground:
- VesselTrackingEvent -> um aviso interno -> `/acompanhados`
- ManeuverEvent com categoria geral ON -> um aviso -> `/alertas`
- ManeuverEvent com categoria geral OFF + tracking ativo -> um aviso -> `/acompanhados`
- nunca dois avisos simultâneos equivalentes
- baseline do TrackingProvider não produz replay
- novo tracking event refaz a lista usando projeção autoritativa da API para atualizar ETA/status/presença sem regressão local

## Correções descobertas em revisão

1. Baseline vazio do tracking feed agora usa cursor 0 e aceita `after=0`, evitando perder o primeiro evento futuro.
2. Timeline ManeuverEvent não inventa `ingestion_id/ingested_at` para usar formatter de feed; possui projeção própria.
3. Mock E2E de mobile session foi atualizado para o contrato com `installation_id`.
4. `track + event` não abre duas sheets.
5. DemoMode não quebra ao abrir Acompanhados.
6. A lista Acompanhados refaz a projeção autoritativa após tracking event novo.

## Gates finais automatizados

Desktop:
- `make test`: 511 passed, 63 skipped
- Xephyr: manual, pendente de Ciro

API:
- `make test-all`: 346 passed em Docker/PostgreSQL

Frontend:
- Vitest completo: 204 passed em 42 arquivos
- production build: passou
- Playwright completo: 30 passed, 30 skips intencionais por viewport

Cross-repo smoke:
- Desktop serializou VesselTrackingEvent real
- API validou o JSON
- evento apareceu em feed/timeline
- resposta passou pelo parser Zod real da PWA
- fixtures temporárias removidas

## Próxima ação humana

1. Aplicar migrations pendentes da API/Supabase em produção.
2. Publicar API e frontend quando desejado.
3. Atualizar/reiniciar Desktop com os commits locais.
4. Executar `make test-ui XEPHYR_N=27` no Desktop.
5. Realizar o roteiro manual de Ship Tracking descrito na conversa de fechamento.
6. Só depois autorizar push se a revisão humana estiver satisfatória.

## Arquivo que deve continuar preservado

Existe um plano antigo da SPEC 022 não rastreado:
`docs/superpowers/plans/2026-09-28-alert-details-maneuver-timeline.md`

Não adicionar por acidente a commits da SPEC 023.
