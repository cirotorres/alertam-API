# SPEC 023 — Ship Tracking: mapa de execução

**Spec:** `specs/023-ship-tracking.md`

A SPEC 023 será executada em três planos dependentes. A divisão evita um plano monolítico envolvendo
detector Desktop, persistência cloud, sessão por instalação, dispatch e duas UIs ao mesmo tempo.

## Ordem obrigatória

1. `2026-09-28-ship-tracking-core-events.md`
   - cria VesselTrackingEvent;
   - detector residual no Desktop;
   - runtime/outbox/ledger local;
   - canal Desktop → API;
   - persistência cloud e retenção de 30 dias.

2. `2026-09-28-ship-tracking-installations-dispatch.md`
   - identidade `mobile_installations` independente de Web Push;
   - tracked_vessels por instalação;
   - timeline cloud unificada;
   - feed agregado de tracking para foreground;
   - elegibilidade e dispatch sem push duplicado.

3. `2026-09-28-ship-tracking-ux.md`
   - tracking local Desktop;
   - ação ★ na ficha e janela Acompanhados;
   - TrackingProvider no PWA;
   - ações na VesselSheet/AlertDetailSheet;
   - página Acompanhados, timeline e deep links;
   - gates finais cross-repo.
## Gates entre planos

O Plano 2 só começa depois de o Plano 1 provar Desktop → API com idempotência e retenção.
O Plano 3 só começa depois de o Plano 2 provar isolamento por instalação e dispatch determinístico.

## Restrições globais

- ManeuverEvent continua canônico para manobras.
- VesselTrackingEvent transporta somente mudanças residuais/complementares.
- Nada de AIS/GPS ou inferência geográfica.
- Tracking não expira automaticamente no MVP.
- Tracking PWA é individual por instalação; Desktop local é independente.
- Web Push desligado não apaga tracking.
- Retenção de eventos: 30 dias.
- Sem replay retroativo após restart, início de tracking ou reativação de push.
- Nenhuma nova voz/chime para ETA/ETB/ETS.
- Não fazer commit ou push sem autorização explícita de Ciro.

## Estado de execução em 2026-09-28

- Plano 1 — Core Events: **concluído e validado**.
- Plano 2 — Installations & Dispatch: **próximo plano; ainda não iniciado**.
- Plano 3 — Desktop & PWA UX: **pendente do Plano 2**.
