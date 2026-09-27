# 021 - Eventos de manobra, feed mobile e Web Push

| Campo | Valor |
|---|---|
| Status | Em implementação — Tasks 1–6 concluídas; Task 7 próxima |
| Criado em | 2026-09-27 |
| Atualizado em | 2026-09-27 |
| Escopo | FastAPI/Supabase + PWA React/Vite |
| Design canônico | `/home/ciro/dev/prog/alertamaritimo/docs/superpowers/specs/2026-09-27-ciclo-manobras-eventos-push-design.md` |
| Dependência Desktop | Etapa 1 concluída nos commits `95efb1e` e `cf80473` |

## Objetivo

Consumir de forma confiável os `ManeuverEvent` produzidos pelo AlertaM Desktop, persistir os eventos por 30 dias,
expor um feed somente leitura para o PWA e distribuir Web Push por instalação mobile com preferências independentes.

A API não interpreta snapshots para descobrir eventos. O Desktop é a única autoridade semântica.

## Decisão principal

Manter dois canais independentes:

```text
MobileSnapshot   → estado atual → latest-only
ManeuverEvent    → acontecimento → persistente/idempotente/ordenado
```

O POST de evento usa autenticação `Device <DEVICE_SECRET>`.
Leitura do feed e administração da instalação push usam a sessão mobile HttpOnly já existente.

## Dependências

- Desktop 017 continua canônico para `MobileSnapshot v1`.
- Desktop 019 continua canônico para pareamento/rotação de `VIEW_SECRET`.
- SPEC 020 continua canônica para shell PWA, mapa, navegação e pareamento.
- Esta SPEC substitui as fontes antigas de Alertas/Histórico da SPEC 020 quando o feed de eventos estiver pronto.

## Regras de negócio

### Evento

Tipos públicos:
- `CONFIRMED`
- `UPDATED`
- `COMPLETED`
- `CANCELLED`

Cada evento possui `event_id` e `maneuver_id` UUID gerados no Desktop.

O payload aceito contém:
- `event_id`
- `maneuver_id`
- `vessel_identity`
- `vessel_imo`
- `vessel_name`
- `maneuver_type`
- `event_type`
- `berth`
- `pob`
- `occurred_at`
- `changes`

Retry do mesmo `event_id` com conteúdo idêntico é sucesso idempotente.
Mesmo `event_id` com conteúdo diferente é conflito seguro.
UUID não é relógio: a API mantém uma ordem de ingestão estável.

### Feed

O feed é device-scoped pela sessão mobile.
Retenção: 30 dias.
Alertas mostra eventos individuais.
Histórico agrupa por `maneuver_id`, preservando a sequência do ciclo.

O click de push abre:

`/alertas?event=<event_id>`

A página deve localizar e destacar esse evento.

### Instalação push

Cada instalação PWA possui `installation_id` UUID persistente no próprio navegador.
Instalações diferentes do mesmo dispositivo são independentes.

Preferências por instalação:
- confirmações
- atualizações
- conclusões
- cancelamentos

Ao primeiro opt-in, as quatro começam ligadas.

A subscription é sempre vinculada ao `device_id` resolvido pela sessão; o cliente não escolhe outro dispositivo no body.

### Sem replay

Cada instalação mantém `push_enabled_at`.
Um evento só é elegível para push quando `event.occurred_at >= push_enabled_at`.

Evento antigo que chegar depois por outbox pode entrar no feed, mas não pode gerar push para uma instalação criada depois dele.

### Foreground

Enquanto o PWA estiver visível:
- registrar heartbeat leve de foreground;
- consumir o feed de eventos;
- mostrar aviso interno para evento novo;
- evitar push de sistema quando o heartbeat estiver recente.

Essa supressão é best-effort. Uma corrida pode produzir notificação extra; perder o alerta é pior.

### Background/fechado

PWA em background ou fechado recebe Web Push quando:
- instalação está ativa;
- categoria está ligada;
- evento não é anterior ao opt-in;
- subscription é válida;
- instalação não está classificada como foreground recente.

### Revogação e esquecimento

Expiração normal do cookie de 30 dias não desativa push.

Rotação/revogação do `VIEW_SECRET` pelo Desktop desativa todas as instalações push daquele `device_id`.

`Esquecer este aparelho`:
- desativa somente a instalação atual;
- cancela sua PushSubscription quando possível;
- limpa o pareamento/sessão local;
- não afeta outros celulares.

Desativar notificações em Config:
- mantém pareamento;
- desativa somente aquela instalação;
- remove/unsubscribe da subscription quando possível.

### Falhas de push

Evento persistido não depende do sucesso do push.

Falha permanente da subscription desativa somente aquela instalação.
Falha transitória registra estado de retry/diagnóstico sem apagar evento.
Não é obrigatório Redis/worker no MVP.

## Segurança

- PWA nunca cria ManeuverEvent.
- Desktop é a única origem do POST de evento.
- `DEVICE_SECRET`, `VIEW_SECRET`, cookie de sessão, endpoint completo da PushSubscription e chave privada VAPID nunca entram em logs.
- VAPID private key fica somente no backend via variável de ambiente.
- Frontend recebe somente a VAPID public key.
- Supabase continua privado atrás da API.
- Endpoint/body de instalação nunca permite selecionar outro `device_id`.

## Service Worker

Migrar `vite-plugin-pwa` de geração automática para `injectManifest`.

Preservar:
- precache do shell/assets;
- auto-update;
- API `/api/v1/*` sem cache autenticado.

Adicionar:
- handler `push`;
- handler `notificationclick`;
- foco/navegação de janela existente quando possível;
- `clients.openWindow` quando não houver janela.

## Conteúdo do push

Payload mínimo do service worker:
- `event_id`
- `title`
- `body`
- `url`

Exemplos:
- `Atracação confirmada`
- `Atracação atualizada`
- `Desatracação concluída`
- `Atracação cancelada`

POB/berço ausentes são omitidos; nunca exibir placeholder enganoso.

## Persistência cloud

### maneuver_events

Imutável, 30 dias.
Precisa de:
- ordem de ingestão;
- `event_id` único;
- associação a `device_id`;
- payload suficiente para feed/push;
- índices para device + ordem/tempo.

### push_installations

Uma linha por `installation_id`.
Precisa de:
- `device_id`;
- subscription endpoint/chaves;
- quatro preferências;
- `push_enabled_at`;
- `last_seen_at`;
- `last_foreground_at`;
- ativo/inativo;
- timestamps.

### push_deliveries

Uma linha por evento × instalação.
Precisa impedir duplicação de envio e registrar:
- entregue;
- ignorado por preferência;
- ignorado por foreground;
- ignorado por evento anterior ao opt-in;
- falha transitória;
- falha permanente.

Retenção: 30 dias.

## Fora do escopo

- Firebase/FCM como dependência da aplicação;
- OneSignal;
- WebSocket/SSE obrigatório;
- histórico cloud acima de 30 dias;
- replay de push antigo;
- push para alteração de previsão;
- edição operacional no PWA;
- múltiplos tipos de chime;
- áudio Desktop final (Etapa 3);
- Redis/worker obrigatório.

## Impacto esperado

### Backend

Novos modelos, repository contracts, migrations, endpoints de evento/feed/instalação, VAPID e dispatcher.

### Frontend

Novo contrato de evento, provider/polling de eventos, Alertas/Histórico, Config de push, installation_id,
heartbeat foreground e service worker customizado.

### Banco

Novas tabelas/RPCs/índices e ajuste da rotação do VIEW_SECRET para revogar push de todo o dispositivo.

## Riscos

1. evento aceito e resposta perdida → retry não pode duplicar evento nem push;
2. outbox entrega evento antigo após novo opt-in → feed sim, push não;
3. session cookie expira → push deve continuar;
4. rotação do VIEW_SECRET → todas as instalações precisam ser desativadas atomicamente;
5. foreground/background muda perto do evento → pode haver push extra, mas não perda do evento;
6. subscription 404/410 → desativar só aquela instalação;
7. service worker novo não pode quebrar precache/instalação existente;
8. ordem de shift COMPLETED → CONFIRMED precisa sobreviver à ingestão/feed.

## Critérios de aceite

### API/eventos

- [ ] POST aceita ManeuverEvent com Device auth.
- [ ] retry idêntico é idempotente.
- [ ] payload divergente com mesmo event_id retorna conflito.
- [ ] feed é isolado por device/session.
- [ ] ordem de ingestão é estável.
- [ ] retenção de eventos é 30 dias.
- [ ] push falhar não remove evento.

### Push

- [ ] installation_id independente por PWA.
- [ ] quatro preferências iniciam ligadas.
- [ ] preferência desligada impede push da categoria.
- [ ] push_enabled_at impede replay.
- [ ] foreground recente evita push de sistema.
- [ ] background/fechado é elegível.
- [ ] rotação do VIEW_SECRET desativa todas as instalações.
- [ ] esquecer aparelho afeta só a instalação atual.
- [ ] subscription permanentemente inválida fica inativa.
- [ ] delivery bookkeeping impede duplicação.

### PWA

- [ ] Alertas consome ManeuverEvent.
- [ ] /alertas?event=... destaca o evento.
- [ ] Histórico agrupa por maneuver_id.
- [ ] Config controla opt-in e quatro categorias.
- [ ] service worker usa injectManifest.
- [ ] notificationclick foca/navega ou abre a PWA.
- [ ] aviso interno aparece para eventos novos em foreground.
- [ ] nenhuma resposta autenticada da API é cacheada.

## Perguntas em aberto

Nenhuma pergunta de produto bloqueante. Detalhes técnicos fechados no plano de implementação devem respeitar o design canônico.

## Evidência de implementação parcial

Checkpoint após Task 6:
- contrato ManeuverEvent cross-repo implementado;
- migrations 004/005 escritas;
- POST/feed de eventos implementados;
- EventProvider, Alertas e Histórico migrados para ManeuverEvent;
- repository de push installations/deliveries implementado;
- API full suite: exit 0;
- frontend full suite: 115/115 testes;
- Task 6 focused gate: 21 pass, 1 skip;
- `git diff --check`: limpo no checkpoint;
- migrations 004/005 ainda não validadas em Postgres real nesta sessão por ausência de `TEST_POSTGRES_DSN`.

A evidência final de Web Push real, build final, E2E e retenção continua pendente para as Tasks 7–13.
