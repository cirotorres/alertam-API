# Specs do AlertaM API / Mobile

| ID | Documento | Status | Resumo |
|---|---|---|---|
| 020 | [Frontend mobile responsivo e PWA](020-frontend-mobile-pwa.md) | Em validação final | React/Vite read-only, pareamento por QR, polling 30 s, mapa, drawer, bottom sheet, navegação inferior e instalação PWA |
| 021 | [Eventos de manobra, feed mobile e Web Push](021-maneuver-events-webpush.md) | Implementação local concluída; validação externa pendente | Persistência idempotente de ManeuverEvent, feed Alertas/Histórico e Web Push por instalação com preferências |
| 022 | [Detalhes de Alertas e linha do tempo da manobra](022-alert-details-maneuver-timeline.md) | Implementação local concluída e validada | Alertas clicáveis, gaveta detalhada, POB × conclusão observada, timeline por maneuver_id e detalhes equivalentes no Desktop |
| 023 | [Ship Tracking](023-ship-tracking.md) | Planos 1–3 implementados; validação Tk/Xephyr manual pendente | Acompanhamento persistente por navio/instalação, VesselTrackingEvent, push seletivo, timeline unificada e tracking local no Desktop |

## Dependências cross-repo

A SPEC 020 depende das specs do repositório AlertaM Desktop:

- 017 — snapshot mobile do Desktop;
- 018 — API FastAPI + Supabase;
- 019 — Conectar Celular e pareamento mobile.

A SPEC 021 trata o novo canal de ManeuverEvent, feed mobile e Web Push, consumindo a Etapa 1 concluída do Desktop.

A SPEC 022 evolui esse canal com detalhe/timeline por manobra e requer mudanças coordenadas em Desktop, API e PWA.
A SPEC 023 depende da 022 para reutilizar timeline/detalhes e adiciona Ship Tracking com `VesselTrackingEvent`, persistência por instalação e tracking local no Desktop.
