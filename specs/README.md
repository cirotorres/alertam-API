# Specs do AlertaM API / Mobile

| ID | Documento | Status | Resumo |
|---|---|---|---|
| 020 | [Frontend mobile responsivo e PWA](020-frontend-mobile-pwa.md) | Em validação final | React/Vite read-only, pareamento por QR, polling 30 s, mapa, drawer, bottom sheet, navegação inferior e instalação PWA |
| 021 | [Eventos de manobra, feed mobile e Web Push](021-maneuver-events-webpush.md) | Implementação concluída; retenção Supabase validada, smoke Web Push real pendente | Persistência idempotente de ManeuverEvent, feed Alertas/Histórico e Web Push por instalação com preferências |
| 022 | [Detalhes de Alertas e linha do tempo da manobra](022-alert-details-maneuver-timeline.md) | Implementação local concluída e validada | Alertas clicáveis, gaveta detalhada, POB × conclusão observada, timeline por maneuver_id e detalhes equivalentes no Desktop |
| 023 | [Ship Tracking](023-ship-tracking.md) | Planos 1–3 implementados; Tk/Xephyr validado; rollout externo pendente | Acompanhamento persistente por navio/instalação, VesselTrackingEvent, push seletivo, timeline unificada e tracking local no Desktop |
| 024 | [Tempo operacional da manobra e refinamentos de UX](024-operational-maneuver-timing-ux-refinements.md) | SPEC aprovada; planos TDD preparados para revisão | Separa horário operacional de observação do AlertaM, persiste ATRAC real e corrige UX de tracking, sheets, scroll e footer |
| 025 | [WebPilot HTTP, meteorologia observada e shadow de movimentações](025-webpilot-http-observed-weather-shadow-migration.md) | Gate técnico MET (08/10); aceite humano contextual para avançar Cloud; fechamento documental/integração pendentes | 25h53m; 1501 comparáveis, 1499 equivalentes, 109 limpos, 0 falhas; 4 registros de 2 episódios explicados como hipótese temporal não comprovada; Selenium oficial, sem cutover |
| 026 | [Gestão de aparelhos mobile, revogação e troca segura de pareamento](026-mobile-installation-management-safe-pairing-switch.md) | Implementação estendida concluída; migration 016 aplicada; deploy/smoke iOS pendentes | Lista/revoga instalações, troca segura dentro do PWA por QR ou código temporário de 6 dígitos e reconexão sem reinstalar |
| 027 | [AlertaM Cloud: continuidade vinculada ao Desktop](027-alertam-cloud-continuity.md) | Gate de entrada ao desenvolvimento atendido sob aceitação de hipótese temporal; spike Northflank aprovado; planejar C1 | Próxima etapa é implementação escalonada com TDD e revisão; operação Cloud real/produção, migrações e publicação permanecem desautorizadas até gates específicos |
| 029 | [Tábua de maré DHN no Desktop e PWA + identidade discreta](029-tabua-mare-dhn-desktop-pwa.md) | Implementada e integrada; validações Windows/release tratadas no fluxo pré-Plan 4 | Dataset DHN 2026 estático/offline, Hoje+Amanhã no Desktop/PWA e identidade via `ⓘ`; sem endpoint de maré, Supabase ou MobileSnapshot novo |

## Dependências cross-repo

A SPEC 020 depende das specs do repositório AlertaM Desktop:

- 017 — snapshot mobile do Desktop;
- 018 — API FastAPI + Supabase;
- 019 — Conectar Celular e pareamento mobile.

A SPEC 021 trata o novo canal de ManeuverEvent, feed mobile e Web Push, consumindo a Etapa 1 concluída do Desktop.

A SPEC 022 evolui esse canal com detalhe/timeline por manobra e requer mudanças coordenadas em Desktop, API e PWA.
A SPEC 023 depende da 022 para reutilizar timeline/detalhes e adiciona Ship Tracking com `VesselTrackingEvent`, persistência por instalação e tracking local no Desktop.
A SPEC 024 refina a 022/023 após validação real, sem substituir seus contratos: adiciona horário operacional opcional ao ManeuverEvent e corrige UX coordenada entre Desktop e PWA.
A SPEC 025 cruza Desktop, API e PWA para separar autenticação/coleta WebPilot, introduzir meteorologia observada e provar o collector HTTP em shadow; ela não realiza cutover nem ativa Cloud.
A SPEC 026 evolui o pareamento das specs 019/020 e a identidade por instalação das specs 021/023, adicionando gestão administrativa no Desktop, revogação individual e troca segura entre Desktops.
A SPEC 027 depende do gate humano da 025 e define o Cloud como continuidade vinculada a um Desktop existente, preservando o mesmo device_id e a gestão mobile no Desktop.
A SPEC 029 é um refinamento lateral já integrado: empacota a tábua DHN 2026 diretamente no Desktop/PWA, sem alterar o transporte de snapshot, e não substitui os gates pré-Plan 4 da SPEC 025/030.
