# Handoff — SPEC 023 Ship Tracking — Finalização do Plano 3 e orientação de deploy/testes

Data: 2026-09-29

## Objetivo desta nova sessão

Não reimplementar o Plano 3.

Os Planos 1, 2 e 3 da SPEC 023 já foram implementados e o Plano 3 possui commit final local:

`ebdaca6 Feat: conclui Plano 3 da SPEC 023 - Desktop & PWA UX`

A nova sessão deve:

1. confirmar o estado dos dois repositórios;
2. revisar o fechamento já realizado;
3. considerar o Tk/Xephyr como validação manual do Ciro, não como bloqueio técnico;
4. orientar o Ciro, de forma prática, a:
   - aplicar as migrations necessárias no Supabase;
   - conferir/configurar variáveis de ambiente;
   - publicar/reiniciar os componentes;
   - testar manualmente todas as features de Ship Tracking;
5. se Ciro relatar algum erro manual, corrigir apenas o erro encontrado e repetir os gates relevantes;
6. não fazer push sem autorização explícita.

## Instruções explícitas do Ciro que devem ser respeitadas

### Xephyr/Tk real

Ciro instruiu explicitamente:

- o agente **não precisa executar o gate Tk real via Xephyr**;
- Ciro fará manualmente:
  `make test-ui XEPHYR_N=27`
- ele informará depois caso encontre algum erro;
- portanto não bloquear a finalização do plano por ausência de display remoto;
- também não afirmar que o Xephyr passou enquanto Ciro não confirmar.

### Orientação final obrigatória

Ciro pediu que, ao final, o agente explique:

1. como testar as novas features;
2. o que precisa configurar no banco/Supabase;
3. quais migrations precisam ser aplicadas;
4. quais variáveis de ambiente precisam existir;
5. quais variáveis são novas/específicas e quais já eram usadas;
6. o que não precisa de configuração adicional;
7. a ordem recomendada para aplicar tudo em produção.

### Git / publicação

- não fazer push sem autorização explícita;
- não resetar/rebasear ou descartar mudanças locais;
- não incluir por acidente o arquivo antigo não rastreado da SPEC 022;
- commits já existentes devem ser preservados.

## Repositórios e estado esperado

### Desktop

Repo:
`/home/ciro/dev/prog/alertamaritimo`

Branch:
`develop`

Estado no último fechamento:
`develop...origin/develop [ahead 5]`

Último commit do Plano 3 no Desktop:
`a6ce9d0 Feat: adiciona acompanhamento local e UX Desktop da SPEC 023`

Commits locais relevantes:
- `a6ce9d0 Feat: adiciona acompanhamento local e UX Desktop da SPEC 023`
- `8f50956 Feat: integra eventos de Ship Tracking ao Desktop`
- `d99b0c2 Feat: cria núcleo local do Ship Tracking`
- `a5beda2 Feat: adiciona detalhes locais ao histórico de manobras`
- `59462fc Feat: enriquece eventos e preserva histórico local de manobras`

Working tree estava limpo.

### API/PWA

Repo:
`/home/ciro/dev/prog/alertamaritimoAPI`

Branch:
`feat/api-bootstrap`

Estado no último fechamento:
`feat/api-bootstrap...origin/feat/api-bootstrap [ahead 11]`

HEAD esperado:
`ebdaca6 Feat: conclui Plano 3 da SPEC 023 - Desktop & PWA UX`

Checkpoints relevantes:
- `121463d Feat: adiciona provider e ações de acompanhamento no PWA`
- `02882a2 Feat: conclui Plano 2 da SPEC 023 - Installations & Dispatch`
- `34f273c Feat: adiciona timeline e feed de acompanhamento`
- `445e0af Feat: adiciona instalações e acompanhamentos por aparelho`

Arquivo antigo não rastreado que deve continuar preservado:
`docs/superpowers/plans/2026-09-28-alert-details-maneuver-timeline.md`

Não adicionar esse arquivo a commits da SPEC 023.

## Leia primeiro na nova sessão

1. este handoff;
2. `docs/superpowers/handoffs/2026-09-29-spec023-plan3-complete-handoff.md`;
3. `specs/023-ship-tracking.md`;
4. `docs/superpowers/plans/2026-09-28-ship-tracking-overview.md`;
5. `docs/superpowers/plans/2026-09-28-ship-tracking-ux.md`.

Antes de alterar qualquer coisa:

```bash
cd /home/ciro/dev/prog/alertamaritimo
git status --short --branch
git log -5 --oneline

cd /home/ciro/dev/prog/alertamaritimoAPI
git status --short --branch
git log -5 --oneline
```

Se o HEAD da API/PWA for `ebdaca6` e não houver mudança inesperada, tratar a implementação como concluída.

# Estado funcional já concluído

## Desktop

Implementado:
- tracking/favorito local independente da PWA;
- persistência atômica em `tracked_vessels.json`;
- sem TTL;
- stop manual;
- ausência na planilha mantém tracking ativo;
- `current.present=false` quando ausente;
- NAME → IMO apenas por nome normalizado exatamente igual;
- sem fuzzy matching;
- botão `☆ Acompanhar navio` / `★ Acompanhando`;
- janela `⭐ Acompanhados`;
- timeline local unificada ManeuverEvent + VesselTrackingEvent;
- estrela nas listas;
- estrela em tooltip/mapa sem alterar sprites;
- pulso vermelho/verde operacional preservado;
- sem nova voz/chime;
- favoritos Desktop não sincronizam com favoritos da PWA.

## PWA

Implementado:
- identidade `mobile_installation` independente de Web Push;
- tracking por instalação;
- rota `/acompanhados`;
- link `Acompanhados` no drawer;
- lista somente trackings ativos daquela instalação;
- navio ausente continua listado;
- último estado conhecido permanece visível;
- `TrackedVesselSheet` com BottomSheetFrame;
- timeline unificada MANEUVER/TRACKING;
- deep link:
  `/acompanhados?track=<tracked_vessel_id>&event=<event_id>`
- evento selecionado destacado;
- fechar sheet remove `track/event` e continua na página;
- VesselSheet e AlertDetailSheet permitem acompanhar/parar;
- target de AlertDetail funciona mesmo se o navio já estiver ausente do snapshot;
- fallback por nome é explícito;
- promoção NAME → IMO não cria segundo tracking;
- falha/offline não produz falso sucesso otimista;
- polling agregado de tracking a cada 30 s;
- baseline sem replay;
- cursor vazio corrigido para 0;
- `after=0` aceito para não perder o primeiro evento futuro.

## Foreground / Push

Regras finais:

1. VesselTrackingEvent residual:
   - aviso interno;
   - destino `/acompanhados?track=...&event=...`.

2. ManeuverEvent com categoria geral habilitada:
   - destino canônico `/alertas?event=...`.

3. ManeuverEvent com categoria geral desligada + tracking ativo:
   - destino `/acompanhados?track=...&event=...`.

4. Geral ON + tracking ativo:
   - somente um aviso;
   - prioridade canônica de `/alertas`.

5. Query com `track=` + `event=`:
   - `event` pertence à timeline de tracking;
   - AlertDetailSheet global não deve abrir.

6. Reativar Push não reproduz eventos antigos.

7. PushSubscription permanent failure não apaga tracking.

# Gates já executados

Último fechamento automatizado:

## Desktop
- `make test`: **511 passed, 63 skipped**
- `make check`: OK
- Xephyr/Tk real: **manual e pendente do Ciro**

## API
- `make test-all`: **346 passed** em Docker/PostgreSQL

## Frontend
- Vitest: **204 passed em 42 arquivos**
- production build: passou
- Playwright completo: **30 passed, 30 skips intencionais por viewport**

## Smoke cross-repo
Validado:
Desktop VesselTrackingEvent real
→ JSON serializado
→ API
→ feed/timeline
→ parser Zod real da PWA

Fixtures temporárias removidas.

# Banco / Supabase — o que orientar ao Ciro

As migrations existentes no projeto vão de `001` até `012`.

As migrations da SPEC 023 são principalmente:

- `008_vessel_tracking_events.sql`
- `009_vessel_tracking_retention.sql`
- `010_mobile_installations.sql`
- `011_tracked_vessels.sql`
- `012_vessel_tracking_deliveries.sql`

Se produção já está em `007`, o fluxo correto é **não rodar SQL manualmente uma por uma**. Usar o migrador do projeto, que aplica somente as pendentes.

No repo API/PWA:

```bash
cd /home/ciro/dev/prog/alertamaritimoAPI
make prod-migrate-check
make prod-migrate
```

O comando exige:
`api/.env.prod`

com:
`SUPABASE_DB_URL`

O migrador lê todos os arquivos em:
`api/supabase/migrations`

e aplica somente os pendentes.

Antes de produção, pode conferir:

```bash
make migrate-list
```

A lista final esperada inclui `001` ... `012`.

## Variáveis da API em produção

Arquivo de referência:
`api/.env.prod.example`

Base obrigatória:

```env
ENVIRONMENT=production
PERSISTENCE_BACKEND=supabase

SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SECRET_KEY=sb_secret_...
SUPABASE_DB_URL=postgresql://...
```

`SUPABASE_SERVICE_ROLE_KEY` é apenas fallback legado.
Se `SUPABASE_SECRET_KEY` estiver configurada, não é necessário preencher a variável legada.

Pode manter:

```env
STALE_AFTER_SECONDS=120
PUSH_FOREGROUND_FRESH_SECONDS=75
LOG_LEVEL=INFO
```

`ALLOWED_ORIGINS` pode continuar vazio se o frontend e API estiverem operando same-origin/proxy conforme a arquitetura atual.

## Web Push

**Tracking não depende de Push estar habilitado.**

É possível testar:
- acompanhar/parar;
- página Acompanhados;
- timeline;
- foreground interno;

mesmo com:

```env
WEB_PUSH_ENABLED=false
```

Para testar Web Push real, configurar na API:

```env
WEB_PUSH_ENABLED=true
VAPID_PUBLIC_KEY=<publica>
VAPID_PRIVATE_KEY=<privada>
VAPID_SUBJECT=mailto:<contato>
PUSH_FOREGROUND_FRESH_SECONDS=75
```

Importante:
- `VAPID_PRIVATE_KEY` é backend-only;
- não expor em frontend/log;
- o frontend busca a chave pública pela própria API;
- portanto **não há nova variável VAPID no frontend**.

A API valida que, com `WEB_PUSH_ENABLED=true`, as três variáveis VAPID estejam preenchidas.

## Frontend/PWA

A SPEC 023 não introduziu variável de ambiente nova obrigatória no frontend.

O PWA usa rotas same-origin:
`/api/v1/...`

A identidade `installation_id` é criada/armazenada no próprio aparelho e enviada na criação da sessão mobile.

Não configurar manualmente installation_id.

## Desktop

As variáveis existentes de sincronização continuam:

```env
ALERTAM_API_BASE_URL=<URL da API>
ALERTAM_DEVICE_ID=<device_id>
ALERTAM_DEVICE_SECRET=<segredo do device>
```

Não existe variável nova específica para os favoritos locais da SPEC 023.

O tracking local do Desktop persiste em:
`tracked_vessels.json`

na data dir normal do AlertaM.

Se o Desktop já enviava snapshots/eventos para a API, provavelmente essas três variáveis já estão configuradas e não precisam mudar.

# Ordem recomendada para aplicar em produção

Orientar o Ciro nesta ordem:

1. confirmar backup/estado do Supabase;
2. conferir `api/.env.prod`;
3. rodar:
   `make prod-migrate-check`;
4. rodar:
   `make prod-migrate`;
5. atualizar as variáveis da API/Vercel com os valores de produção;
6. se quiser Web Push real, configurar VAPID e `WEB_PUSH_ENABLED=true`;
7. publicar/redeploy da API;
8. publicar/redeploy do frontend PWA;
9. atualizar/reiniciar o Desktop com os commits locais;
10. fazer novo pareamento do aparelho se necessário;
11. validar tracking com Push desligado;
12. depois validar Web Push ligado;
13. Ciro executa `make test-ui XEPHYR_N=27`;
14. só após revisão humana satisfatória, autorizar push dos commits se desejar.

# Roteiro de teste manual que deve ser entregue ao Ciro

A nova sessão deve transformar este checklist em instruções práticas, passo a passo.

## A. Desktop — favorito local

1. abrir AlertaM Desktop;
2. abrir ficha de um navio;
3. clicar `☆ Acompanhar navio`;
4. confirmar mudança para `★ Acompanhando`;
5. abrir `⭐ Acompanhados`;
6. confirmar navio listado;
7. fechar e reabrir o programa;
8. confirmar que o favorito continua;
9. validar estrela na lista/mapa/tooltip;
10. confirmar que vermelho/verde operacional continua funcionando normalmente;
11. confirmar que acompanhar ETA/status não cria voz/chime nova;
12. clicar `Parar de acompanhar` e confirmar remoção da lista ativa.

## B. Desktop — ausência e NAME → IMO

1. acompanhar um navio;
2. simular/aguardar ele sumir da planilha;
3. confirmar que permanece em Acompanhados como ausente;
4. confirmar último estado conhecido;
5. para navio sem IMO, acompanhar por nome;
6. quando o mesmo nome exato aparecer com IMO, confirmar que continua um único favorito;
7. confirmar que nomes parecidos não são fundidos.

## C. PWA — tracking sem Web Push

Testar primeiro com:
`WEB_PUSH_ENABLED=false`

1. parear o celular;
2. abrir ficha de navio;
3. tocar `☆ Acompanhar navio`;
4. confirmar `★ Acompanhando · Parar`;
5. abrir drawer → `Acompanhados`;
6. confirmar navio listado;
7. fechar/reabrir PWA;
8. confirmar persistência do tracking;
9. desligar/reativar PWA e confirmar que o tracking continua;
10. parar tracking e confirmar remoção da lista ativa.

## D. PWA — navio ausente

1. acompanhar navio;
2. fazer o navio desaparecer de snapshot válido;
3. confirmar que ainda aparece em Acompanhados;
4. confirmar estado `Ausente`;
5. confirmar último berço/status/ETA/POB conhecido.

## E. PWA — timeline

1. acompanhar navio;
2. provocar mudança residual, por exemplo ETA;
3. confirmar entrada TRACKING na timeline;
4. provocar/usar ManeuverEvent do mesmo navio;
5. confirmar evento de manobra na mesma timeline;
6. confirmar ausência de duplicação do mesmo campo semântico;
7. validar deep link:
   `/acompanhados?track=<id>&event=<id>`;
8. confirmar evento destacado;
9. fechar sheet;
10. confirmar permanência na página `/acompanhados`.

## F. Foreground

Com PWA aberto/foreground:

1. VesselTrackingEvent residual:
   - deve aparecer um aviso interno;
   - botão deve abrir Acompanhados.

2. ManeuverEvent com preferência geral ON:
   - deve aparecer um aviso;
   - deve abrir Alertas.

3. preferência geral OFF + navio acompanhado:
   - deve abrir Acompanhados.

4. geral ON + tracking:
   - apenas um aviso;
   - destino Alertas.

## G. Web Push real

Depois configurar VAPID e habilitar Push.

Em iPhone/PWA:
1. permitir notificações;
2. acompanhar um navio;
3. colocar PWA em segundo plano;
4. provocar VesselTrackingEvent elegível;
5. validar push;
6. tocar no push e validar deep link Acompanhados;
7. provocar ManeuverEvent geral;
8. validar que não há push duplicado geral + tracking;
9. desativar Push;
10. confirmar que tracking continua existindo;
11. reativar Push;
12. confirmar que eventos antigos não são reproduzidos.

## H. Dois aparelhos

1. parear dois celulares no mesmo device;
2. acompanhar NAVIO A apenas no aparelho 1;
3. não acompanhar no aparelho 2;
4. provocar tracking event do NAVIO A;
5. confirmar que tracking/push seletivo é por instalação;
6. confirmar que o aparelho 2 não ganha o favorito automaticamente.

## I. Esquecer aparelho

1. acompanhar um navio;
2. usar `Esquecer este aparelho`;
3. parear novamente;
4. confirmar que a instalação anterior foi revogada;
5. confirmar que o tracking anterior não reaparece como ativo naquela nova instalação.

# Se o Ciro reportar erro manual

Não refazer a arquitetura.

Procedimento:
1. reproduzir o caso exato;
2. escrever RED focado;
3. corrigir mínimo necessário;
4. rodar suíte focada;
5. rodar gates relevantes;
6. se tocar API/DB, rodar `make test-all`;
7. se tocar PWA, Vitest + build + Playwright relevante;
8. se tocar Desktop, `make test`; Xephyr continua manual do Ciro;
9. só commitar se Ciro autorizar novo commit;
10. nunca push sem autorização.

# Critério de encerramento

A SPEC 023 pode ser considerada humanamente validada quando:

- Ciro rodar o Xephyr e não relatar regressão Tk;
- migrations `008–012` estiverem aplicadas em produção;
- API/PWA/Desktop estiverem usando a versão nova;
- tracking funcionar com Push desligado;
- Web Push, se habilitado, funcionar sem replay/duplicação;
- deep links de Alertas/Acompanhados estiverem corretos;
- revisão humana do Ciro estiver satisfatória.

A implementação automatizada já está concluída; o restante é validação operacional/humana e publicação.
