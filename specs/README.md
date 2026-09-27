# Specs do AlertaM API / Mobile

| ID | Documento | Status | Resumo |
|---|---|---|---|
| 020 | [Frontend mobile responsivo e PWA](020-frontend-mobile-pwa.md) | Em validação final | React/Vite read-only, pareamento por QR, polling 30 s, mapa, drawer, bottom sheet, navegação inferior e instalação PWA |
| 021 | [Eventos de manobra, feed mobile e Web Push](021-maneuver-events-webpush.md) | Proposto | Persistência idempotente de ManeuverEvent, feed Alertas/Histórico e Web Push por instalação com preferências |

## Dependências cross-repo

A SPEC 020 depende das specs do repositório AlertaM Desktop:

- 017 — snapshot mobile do Desktop;
- 018 — API FastAPI + Supabase;
- 019 — Conectar Celular e pareamento mobile.

A SPEC 021 trata o novo canal de ManeuverEvent, feed mobile e Web Push, consumindo a Etapa 1 concluída do Desktop.
