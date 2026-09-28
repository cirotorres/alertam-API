# Handoff final — Etapa 2 Maneuver Events + Web Push

Data: 2026-09-27
Branch: `feat/api-bootstrap`
Checkpoint base: `d87b834 feat: consolidar eventos e base de push da etapa 2`

## Estado

A Etapa 2 está concluída no código local e pronta para revisão/migração manual.
Nenhum commit ou push adicional foi realizado após o checkpoint.

A SPEC canônica desta etapa é:
- `specs/021-maneuver-events-webpush.md`
- `docs/superpowers/plans/2026-09-27-maneuver-events-webpush-api-pwa.md`

## Gates finais executados

- API: `uv run pytest -q -ra` → exit 0.
- API: 245 testes coletados; 229 pass + 16 skip.
- Os 16 skips são exclusivamente por `TEST_POSTGRES_DSN` ausente.
- Frontend: `npm test -- --run` → 140/140 pass.
- Build: `npm run build` → exit 0.
- PWA: `injectManifest`, `dist/sw.js` gerado.
- Playwright: `npm run e2e` → 26 pass + 18 skips intencionais, zero falhas.
- `git diff --check` → limpo.
- Scan de placeholders/whitespace → limpo.

## O que foi fechado

- ManeuverEvent cross-repo e roundtrip Desktop → API → feed.
- Persistência idempotente com ordem por `ingestion_id`.
- Alertas por `event_id` e Histórico agrupado por `maneuver_id`.
- Caso shift preservando ordem `COMPLETED → CONFIRMED` quando `occurred_at` é igual.
- Instalações Web Push independentes por PWA.
- Quatro preferências por instalação.
- `push_enabled_at` impedindo replay antigo.
- Heartbeat foreground + supressão best-effort de push de sistema.
- VAPID/`pywebpush` e classificação permanente/transitória.
- Delivery bookkeeping/claim para dedupe.
- `injectManifest`, handler `push` e `notificationclick`.
- Config de opt-in/disable/forget local-first.
- Retenção de 30 dias via migration 006.
- Hardening final contra vazamento de subscription/chaves e endpoint HTTP não seguro.

## Limitações externas deliberadamente abertas

1. Migrations 004, 005 e 006 ainda não foram executadas/validadas em Postgres/Supabase real nesta sessão.
2. Os 16 testes PostgreSQL ficaram skip porque `TEST_POSTGRES_DSN` não foi configurado.
3. Supabase Cron de retenção ainda não foi habilitado.
4. Não houve smoke Web Push real em browser/aparelho com VAPID real.
5. Deploy final e smoke Desktop → API → PWA ainda são gates manuais.

## Próximos passos manuais do Ciro

### 1. Validar Postgres antes de produção

Preferir banco/branch de teste descartável. Nunca apontar `TEST_POSTGRES_DSN` para produção.

Na raiz do projeto:

```bash
make test-all
```

Depois, em um Postgres/Supabase de teste com migrations aplicadas:

```bash
cd api
export TEST_POSTGRES_DSN='postgresql://...'
uv run pytest tests/integration -q -ra
```

O objetivo é transformar os 16 skips atuais em testes executados e verdes.

### 2. Aplicar migrations no Supabase alvo

Preencher `api/.env.prod` com `SUPABASE_DB_URL` correto e executar da raiz:

```bash
make prod-migrate-check
make prod-migrate
```

A ordem esperada termina em:
- `004_maneuver_events.sql`
- `005_push_installations_deliveries.sql`
- `006_event_retention.sql`

Confirmar tabelas/RPCs, idempotência do evento, installations/deliveries e a função
`public.cleanup_event_retention(timestamptz)`.

### 3. Validar retenção antes de ativar Cron

No banco de teste, criar dados antigos e recentes e executar:

```sql
select * from public.cleanup_event_retention();
```

Confirmar:
- deliveries de eventos com mais de 30 dias são removidos primeiro;
- eventos com mais de 30 dias são removidos;
- eventos recentes permanecem;
- `push_installations` permanecem intactas.

Somente depois disso habilitar o Supabase Cron para executar periodicamente:

```sql
select public.cleanup_event_retention();
```

### 4. Configurar VAPID real

O utilitário instalado pelo projeto pode gerar um par:

```bash
cd api
uv run vapid --gen
```

Isso gera `private_key.pem` e `public_key.pem`. Não versionar a chave privada.
Configurar no backend/deploy:

```env
WEB_PUSH_ENABLED=true
VAPID_PUBLIC_KEY=<application-server-key>
VAPID_PRIVATE_KEY=<private-key ou formato aceito pelo pywebpush>
VAPID_SUBJECT=mailto:<contato-do-projeto>
PUSH_FOREGROUND_FRESH_SECONDS=75
```

A chave privada deve existir somente no backend.

Para obter a chave pública no formato usado pelo browser:

```bash
uv run vapid --private-key private_key.pem --applicationServerKey
```

Se o deploy exigir a private key como string em vez de arquivo, converter o valor
privado para base64url/RAW de 32 bytes e armazená-lo diretamente no secret
`VAPID_PRIVATE_KEY`. Não copiar a PEM para o repositório.

### 5. Smoke real após deploy

1. `GET /api/v1/health` deve retornar `{"ok": true}`.
2. Configurar Desktop com URL pública, `DEVICE_ID` e `DEVICE_SECRET`.
3. Parear o PWA normalmente e confirmar sessão mobile.
4. Em Config, ativar notificações por gesto explícito do usuário.
5. Confirmar que a instalação ficou ativa e com as quatro preferências ligadas.
6. Com PWA visível, gerar evento real: deve aparecer aviso interno; push de sistema é suprimido best-effort.
7. Com PWA em background/fechado, gerar novo evento: deve surgir Web Push.
8. Tocar na notificação: deve abrir/focar `/alertas?event=<event_id>` e destacar o evento.
9. Desligar uma categoria e confirmar que somente ela deixa de notificar.
10. Testar duas instalações do mesmo device e confirmar preferências independentes.
11. Usar “Esquecer este aparelho” e confirmar que só a instalação atual é desativada.
12. Testar rotação de `VIEW_SECRET`: todas as installations daquele device devem ser desativadas.
13. Confirmar que nenhum endpoint/chave/cookie/VAPID private aparece nos logs.

### 6. Somente após os gates externos

Se migrations, Cron e smoke real estiverem verdes, a Etapa 2 pode ser tratada
como validada também em produção. Até lá, o status correto permanece:
“implementação local concluída; validação externa pendente”.

## Working tree

O working tree foi deixado intencionalmente para revisão do Ciro.
Não fazer commit/push automaticamente a partir deste handoff.
