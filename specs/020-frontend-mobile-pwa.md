# 020 - Frontend mobile responsivo e PWA do AlertaM

| Campo | Valor |
|---|---|
| Status | Proposto |
| Criado em | 2026-09-26 |
| Atualizado em | 2026-09-26 |
| Evidência de conclusão | — |

## Objetivo

Criar o frontend web mobile do AlertaM como PWA somente leitura, consumindo a API já existente e o
pareamento definido pela spec 019 do Desktop.

A interface deve traduzir a experiência operacional do AlertaM para celular sem tentar reproduzir a
janela desktop. O foco é consulta rápida: situação do porto, mapa dos berços, previsões, fundeados,
manobras confirmadas, alertas recentes, histórico e ficha do navio.

O resultado deve ser:

- mobile-first e responsivo;
- instalável como PWA;
- same-origin com a API;
- autenticado somente por `VIEW_SECRET`;
- tolerante a perda temporária de conexão;
- somente leitura;
- visualmente alinhado às referências aprovadas e aos assets do AlertaM Desktop.

## Dependências já concluídas

Esta spec depende de:

- **017** — Desktop produz e publica `MobileSnapshot v1`;
- **018** — FastAPI/Supabase recebe e serve o último snapshot;
- **019** — Desktop gera `VIEW_SECRET` e QR/link no formato de pareamento.

Contrato de leitura:

```http
GET /api/v1/devices/{device_id}/snapshot
Authorization: Bearer <VIEW_SECRET>
```

Resposta:

```json
{
  "snapshot": { "...": "MobileSnapshot v1" },
  "meta": {
    "received_at": "...",
    "age_seconds": 12,
    "collector_online": true,
    "stale_after_seconds": 120
  }
}
```

Contrato de pareamento recebido do Desktop:

```text
/#/pair/{device_id}?token={VIEW_SECRET}
```

O segredo fica no fragmento e não é enviado ao servidor na navegação inicial.

## Decisões principais

### Stack

Frontend:

- React;
- TypeScript;
- Vite;
- CSS responsivo próprio;
- PWA via manifest + service worker;
- Vitest + React Testing Library;
- Playwright para fluxos responsivos/E2E.

Não usar Next.js/SSR. O produto é uma interface autenticada de leitura e não precisa de rendering no
servidor, SEO ou backend React.

### Origem e deploy

Frontend e API permanecem no mesmo projeto/domínio Vercel.

Semântica pública:

```text
/                    -> frontend
/mapa                -> frontend
/alertas             -> frontend
/historico           -> frontend
/config               -> frontend
/api/v1/*             -> FastAPI
```

A regra `/api/v1/*` sempre tem precedência sobre o catch-all do frontend.

O frontend chama somente paths relativos:

```ts
fetch("/api/v1/devices/...")
```

Não hardcodar o domínio público em componentes.

### Somente leitura

O PWA não cria, altera ou exclui navios, previsões, manobras ou dados do Desktop.

A única mutação local permitida é estado do próprio cliente:

- pareamento;
- preferências de UI;
- instalação PWA;
- futuro opt-in de notificações.

## Fora do escopo

- Web Push real;
- VAPID/subscriptions;
- push de confirmação marítima;
- alertas por mudança de previsão;
- alterações no `MobileSnapshot v1`;
- endpoint de foto do navio;
- consultas diretas a Wikidata/Wikimedia;
- login/senha por usuário;
- múltiplos dispositivos AlertaM simultâneos no mesmo navegador;
- edição operacional;
- WebSocket/SSE;
- geolocalização real/AIS;
- mapa geográfico interativo;
- cache persistente de respostas autenticadas da API;
- suporte offline com snapshot histórico após recarregar a página.

Web Push será uma futura **SPEC 021**. Mudanças de previsão ficam reservadas para uma decisão posterior,
pois ainda não existe regra semântica para definir qual alteração merece notificação.

## Design visual aprovado

As três referências fornecidas pelo Ciro são a direção visual, não screenshots a serem copiadas pixel a
pixel.

A hierarquia principal é:

```text
┌────────────────────────────────┐
│ ☰  Alerta de Movimentações     │
│ ● Sessão válida · Última ...   │
├────────────────────────────────┤
│                                │
│             MAPA               │
│          ~45–50 svh            │
│                                │
├────────────────────────────────┤
│ Última leitura                 │
│ Estado do sistema              │
│                                │
│ Conteúdo da aba atual          │
│                                │
├────────────────────────────────┤
│ Manobras | ATR | DES | Fund.   │
└────────────────────────────────┘
```

Princípios:

- visual claro, operacional e marítimo;
- fundo predominantemente claro;
- azul como cor principal;
- verde para estado operacional positivo/atracação;
- vermelho para desatracação/estado crítico quando aplicável;
- amarelo/âmbar para dados desatualizados;
- cards discretos, sem excesso de sombras;
- áreas de toque de no mínimo 44×44 CSS px;
- `env(safe-area-inset-*)` para iPhone/PWA;
- respeito a `prefers-reduced-motion`.

## Responsividade

O produto é mobile-first, mas deve funcionar em celular, tablet e navegador desktop.

### Celular

- viewport principal alvo: 320–480 px;
- header compacto;
- mapa ocupa aproximadamente 45–50% da altura útil quando possível;
- conteúdo rola verticalmente;
- footer fica fixo/sticky na parte inferior;
- drawer cobre parte da tela;
- ficha do navio usa bottom sheet.

### Tablet

- preservar a mesma hierarquia;
- aumentar espaçamentos e largura do drawer;
- bottom sheet pode crescer horizontalmente;
- mapa continua acima do conteúdo.

### Desktop/web largo

Não criar um segundo dashboard desktop nesta spec.

- centralizar a aplicação;
- limitar largura operacional para preservar leitura mobile;
- permitir mapa e conteúdo maiores;
- footer continua a mesma navegação;
- não tentar reproduzir a UI Tkinter.

## Assets

Na implementação, copiar os assets necessários do repositório AlertaM Desktop para o frontend.

Fonte atual:

```text
/home/ciro/dev/prog/alertamaritimo/assets/
```

Assets reutilizáveis:

- `piers.png` — mapa base do porto;
- `navio.png` — navio normal/atracado;
- `navio_green.png` — atracando;
- `navio_red.png` — desatracando;
- `navio_gray.png` — estado neutro quando necessário;
- `navio_icon.ico` / `navio.png` — origem para ícones PWA;
- `time.png` / `time2.png` — somente se forem visualmente úteis após validação.

Os arquivos devem ser copiados para o frontend no build/repositório; o deploy não depende do caminho do
repositório Desktop.

Não inventar uma fotografia de navio nem usar foto externa no MVP.

## Arquitetura do frontend

Estrutura proposta:

```text
frontend/
├── public/
│   ├── icons/
│   └── assets/
├── src/
│   ├── app/
│   │   ├── App.tsx
│   │   ├── router.tsx
│   │   └── providers.tsx
│   ├── api/
│   │   ├── snapshotClient.ts
│   │   └── contract.ts
│   ├── features/
│   │   ├── pairing/
│   │   ├── snapshot/
│   │   ├── map/
│   │   ├── vessels/
│   │   ├── alerts/
│   │   ├── history/
│   │   └── install/
│   ├── components/
│   ├── pages/
│   ├── styles/
│   └── main.tsx
├── index.html
├── package.json
└── vite.config.ts
```

Cada feature deve conhecer apenas seu próprio estado e contratos públicos.

Não concentrar API, parsing de pareamento, polling, mapa e UI em um único componente.

## Pareamento

### Entrada

Ao abrir:

```text
/#/pair/{device_id}?token={VIEW_SECRET}
```

o bootstrap do frontend:

1. lê `device_id` e `VIEW_SECRET` do fragmento;
2. mantém o segredo somente em memória durante a validação inicial;
3. remove imediatamente o fragmento sensível da barra de endereço com `history.replaceState`;
4. testa o acesso pela API;
5. somente depois de confirmação salva o novo pareamento local;
6. navega para a tela principal.

Um novo QR pode substituir um pareamento anterior somente depois que o novo acesso for aceito.

### Resultado da validação

- HTTP 200: pareamento válido e snapshot disponível;
- HTTP 404: pareamento válido, ainda sem snapshot; o serviço atual autentica o `VIEW_SECRET` antes de verificar se existe snapshot;
- HTTP 401: acesso inválido/revogado;
- erro de rede/5xx: resultado temporariamente inconclusivo, oferecer retry/rescan.

### Persistência

MVP suporta um único pareamento.

Chave versionada sugerida:

```text
alertam.mobile.pairing.v1
```

Conteúdo:

```json
{
  "device_id": "pecem-01",
  "view_secret": "<bearer>",
  "paired_at": "..."
}
```

Pode usar `localStorage` no MVP. IndexedDB não fornece proteção adicional relevante contra XSS para um
segredo consumido pelo próprio JavaScript.

Regras:

- nunca logar o valor;
- nunca renderizar o token;
- nunca incluir em telemetry/analytics;
- nunca enviar para domínio externo;
- não persistir o link completo;
- **Esquecer este aparelho** remove todo o pareamento local.

## Segurança frontend

1. O frontend conhece somente `VIEW_SECRET`, nunca `DEVICE_SECRET`.
2. O token só vai no header `Authorization: Bearer ...`.
3. Nenhum terceiro recebe o token.
4. Sem scripts de analytics/ads no MVP.
5. Service worker não armazena respostas de `/api/`.
6. Fetch autenticado usa `cache: "no-store"`.
7. API client não inclui Authorization em requests externos.
8. Fragmento de pareamento é removido da URL assim que lido.
9. Erros exibidos/logados nunca incluem header ou token.
10. Evitar `dangerouslySetInnerHTML`.
11. Usar CSP compatível com Vite/PWA e assets locais quando o deploy permitir.
12. Dependências externas devem ser mínimas e versionadas.

## Leitura e polling

Após pareado:

```text
GET /api/v1/devices/{device_id}/snapshot
Authorization: Bearer <VIEW_SECRET>
```

Política:

- GET imediato ao abrir;
- polling a cada **30 segundos** enquanto `document.visibilityState === "visible"`;
- suspender polling quando a página ficar hidden;
- GET imediato no evento de retorno a visible;
- apenas um request em voo;
- abortar request obsoleto com `AbortController`;
- falha não apaga o último snapshot ainda presente em memória;
- backoff agressivo não é necessário no MVP porque o intervalo já é baixo e o browser pausa em
  background.

O service worker não faz polling.

## Estados globais

### Pareado e online

- header: **Sessão válida**;
- mostrar hora da última leitura;
- se `meta.collector_online === true`, card **Sistema ativo**.

### Dados desatualizados

Quando `meta.collector_online === false`:

- manter último snapshot visível;
- mostrar estado âmbar **Dados desatualizados**;
- informar há quanto tempo não há atualização;
- não apagar navios/listas.

O backend é a fonte de verdade da regra de freshness; não recalcular outro threshold incompatível.

### Sem snapshot

Pareamento válido, mas GET 404:

- tela **Aguardando primeira leitura**;
- mapa base pode aparecer sem navios;
- polling continua.

### Sem rede / 5xx

- manter dados em memória se existirem;
- banner **Sem conexão com o servidor**;
- retry no próximo ciclo e opção manual;
- se a página foi recarregada offline, mostrar shell PWA + estado sem dados, porque API autenticada não é
  persistida pelo service worker nesta spec.

### Acesso revogado

HTTP 401:

- indicar **Acesso expirado ou revogado**;
- não continuar polling com a credencial inválida;
- remover o pareamento local;
- orientar a escanear novo QR no AlertaM Desktop.

## Header

Conteúdo:

- botão hambúrguer;
- identificação **Alerta de Movimentações Marítimas** ou versão curta adequada à largura;
- indicador de sessão;
- última leitura.

Fonte da última leitura:

```text
snapshot.collector.last_collection_at
```

Não usar relógio fictício.

Formatar data/hora no timezone do navegador.

## Drawer lateral

Itens MVP:

```text
Mapa
Alertas
Histórico
Config.

────────────
Instalar aplicativo
Sobre
```

O drawer:

- abre pelo hambúrguer;
- fecha por overlay, Esc ou navegação;
- não fica aberto junto da ficha do navio;
- ao abrir drawer, fechar bottom sheet;
- ao abrir ficha, fechar drawer.

### Mapa

Retorna à tela principal/mapa e mantém a aba inferior atual quando fizer sentido.

### Alertas

Lista curta de ocorrências operacionais recentes vindas do snapshot.

Não é Web Push nesta spec.

### Histórico

Timeline completa do histórico recente disponível no snapshot.

### Config.

Mostrar:

- status do pareamento;
- `device_id` (não secreto);
- última sincronização;
- versão do frontend;
- estado de instalação PWA;
- botão **Esquecer este aparelho** com confirmação.

Reservar área futura para preferências de push, mas não exibir toggles inoperantes.

### Instalar aplicativo

Comportamento adaptativo:

- PWA já instalada/standalone: indicar **Aplicativo instalado**;
- Chromium com `beforeinstallprompt`: botão chama prompt após gesto do usuário;
- iOS/iPadOS Safari: abrir instrução curta **Compartilhar → Adicionar à Tela de Início**;
- navegador sem suporte: explicar que a instalação não está disponível;
- nunca mostrar uma falsa confirmação de instalação.

## PWA

Manifest deve definir pelo menos:

- `name`: Alerta de Movimentações Marítimas;
- `short_name`: AlertaM;
- `display: standalone`;
- `start_url: /`;
- cores coerentes com a UI;
- ícones 192×192 e 512×512;
- `apple-touch-icon`.

Os ícones podem ser derivados dos assets já existentes do AlertaM.

Service worker:

- precacheia shell e assets estáticos;
- permite abrir a interface instalada sem rede;
- **não** cacheia `/api/v1/*`;
- não armazena Authorization;
- prepara a base técnica para futura SPEC 021, mas não registra Web Push ainda.

## Tela principal / Mapa

O mapa é uma composição 2D sobre `piers.png`, não um mapa geográfico.

Usar o mesmo modelo lógico do Desktop:

```text
BERÇO 1  -> (175, 350)
BERÇO 2  -> (205, 320)
BERÇO 3  -> (230, 300)
BERÇO 4  -> (260, 280)
BERÇO 5  -> (295, 250)
BERÇO 6  -> (255, 210)
BERÇO 7  -> (215, 170)
BERÇO 8  -> (180, 130)
BERÇO 9  -> (145, 90)
BERÇO 10 -> (110, 50)
```

Essas coordenadas são relativas ao mapa base 500×500 do Desktop.

No frontend, converter para percentuais/escala responsiva em vez de manter pixels absolutos da viewport.

### Navio a desenhar por berço

Mesmo critério do Desktop:

```text
DESATRACANDO > ATRACANDO > ATRACADO
```

Somente navios com berço conhecido e nesses estados são desenhados.

Sprites:

- `DESATRACANDO` -> `navio_red.png`;
- `ATRACANDO` -> `navio_green.png`;
- `ATRACADO` -> `navio.png`.

Pulso CSS pode ser usado em atracando/desatracando, respeitando `prefers-reduced-motion`.

Exibir número do berço junto ao sprite.

Tocar/clicar no navio abre ficha do navio.

## Bottom sheet — ficha do navio

Abrir sobre o mapa, com o drawer fechado.

A sheet:

- arrasta/rola verticalmente;
- possui botão fechar;
- preserva o mapa ao fundo;
- não navega para outra página;
- deve funcionar com touch e teclado.

Dados disponíveis no `MobileSnapshot v1`:

- nome;
- IMO;
- bandeira;
- situação;
- POB;
- berço / bordo;
- ETA;
- ETB/ETS;
- porto de origem;
- agência;
- rebocadores;
- indicativo/IRIN.

Campos nulos são omitidos ou mostram `—`, conforme contexto; nunca inventar informação.

### Imagem do navio

MVP **não consulta foto externa**.

A área visual superior da ficha pode:

- usar composição marítima neutra com assets locais;
- mostrar ícone do navio + nome;
- ou ser omitida em viewports menores.

Não mostrar fotografia genérica fingindo ser o navio real.

O componente deve aceitar futuramente `image_url?: string` sem reestruturar toda a ficha.

## Footer fixo

Quatro destinos:

1. **Manobras confirmadas**
2. **Prev. atracação**
3. **Prev. desatracação**
4. **Fundeados**

Uma aba ativa por vez.

O footer permanece visível em todas as telas principais de mapa/lista. Pode ficar oculto em telas de
pareamento inicial e modais que exijam foco.

### Manobras confirmadas

Fonte:

`snapshot.recent_maneuvers.active`.

Representa manobras atualmente confirmadas/ativas.

Cada item:

- tipo ATR/DES;
- nome do navio;
- POB quando disponível;
- berço;
- hora de detecção.

Se não houver ativa, mostrar estado vazio claro.

### Previsão de atracação

Replicar a regra do Desktop:

- navios de seção `FUNDEADO` ou `PREVISTO`;
- precisam de `etb_ets`;
- deduplicar pelo primeiro navio de mesmo nome;
- ordenar cronologicamente pela previsão quando parseável.

Mostrar:

- navio;
- ETB;
- berço.

### Previsão de desatracação

Replicar a regra do Desktop:

- seção `ATRACADO`;
- precisa de `etb_ets`;
- deduplicar pelo primeiro navio de mesmo nome;
- preservar ordem de origem do snapshot.

Mostrar:

- navio;
- ETS;
- berço.

### Fundeados

Replicar a regra do Desktop:

- seção `FUNDEADO`;
- deduplicar pelo primeiro navio de mesmo nome.

Mostrar:

- navio;
- ETA;
- berço previsto;
- situação especial `ATRACANDO` quando aplicável.

## Alertas

A tela **Alertas** é um feed curto, não um sistema de push.

Fonte única nesta spec:

`snapshot.recent_maneuvers`.

Composição:

- todas as manobras `active` primeiro;
- depois as `completed` mais recentes;
- máximo visual inicial sugerido: 10 itens;
- ordenar por evento mais recente;
- textos humanizados, sem inventar campos.

Exemplos:

```text
ATR · BOLKAR (F)
Atracação confirmada · Berço 6

DES · MSC ADELE
Desatracação concluída · Berço 9
```

Não gerar notificações do sistema operacional nesta spec.

## Histórico

A tela **Histórico** mostra toda a timeline recente fornecida por:

- `recent_maneuvers.active`;
- `recent_maneuvers.completed`.

Ordenar por tempo relevante e agrupar por data quando útil.

O frontend não cria histórico adicional permanente.

A retenção continua sendo responsabilidade do Desktop/API. O contrato atual pode fornecer todas as
ativas e até 50 finalizadas.

Diferença de produto:

- **Manobras confirmadas:** operações ativas agora;
- **Alertas:** resumo curto das ocorrências mais recentes;
- **Histórico:** timeline completa disponível.

## Cards de estado

Abaixo do mapa, antes da lista ativa:

### Última leitura

Exibir:

- hora;
- data;
- ícone temporal;
- valor real de `collector.last_collection_at`.

### Sistema

Se `meta.collector_online`:

```text
● Sistema ativo
Monitorando movimentações marítimas.
```

Se stale:

```text
● Dados desatualizados
Última atualização há ...
```

Cor nunca é a única indicação de estado.

## Sobre

Tela simples:

- nome AlertaM;
- versão frontend;
- Porto do Pecém;
- descrição somente leitura;
- atribuições necessárias de assets/dados, incluindo Open-Meteo quando dados meteorológicos forem
  exibidos.

Não expor detalhes de infraestrutura/segredos.

## Meteorologia e mar

Os blocos `weather` e `marine` já existem no snapshot.

MVP pode exibir resumo discreto no mapa/header quando os blocos estiverem completos:

- temperatura;
- vento;
- visibilidade;
- onda/período quando disponível.

Se o bloco vier `{}`, ocultar sem erro.

Não transformar meteorologia numa tela principal nesta spec.

## Navegação e rotas

Rotas de UI:

```text
/             -> mapa
/alertas      -> alertas
/historico    -> histórico
/config       -> configurações
/sobre        -> sobre
```

O fragmento `#/pair/...` é processado pelo bootstrap de pareamento antes da navegação normal.

Após ler o fragmento, removê-lo com `history.replaceState`.

A navegação normal não precisa expor segredo no hash.

## Estado da aplicação

Separar:

- `pairing` — credencial/local device;
- `snapshot` — último payload em memória;
- `connection` — loading/online/stale/error;
- `navigation` — rota/drawer/bottom sheet/footer tab;
- `install` — estado PWA.

Evitar store global pesada no MVP. React state/context ou hooks focados são suficientes.

## Tratamento do contrato

Criar tipos TypeScript explícitos equivalentes ao `MobileSnapshot v1`.

O frontend deve falhar de maneira segura se:

- `schema_version !== 1`;
- resposta não tiver a forma esperada.

Não tentar interpretar versões desconhecidas.

Mostrar mensagem:

```text
Esta versão do AlertaM Mobile precisa ser atualizada.
```

Não usar campos extras não documentados.

## Loading e transições

- skeleton/discreto durante primeira leitura;
- não piscar toda a tela a cada polling;
- atualizar listas/mapa de forma estável;
- preservar aba selecionada entre polls;
- preservar ficha aberta se o navio ainda existir;
- se o navio desaparecer do snapshot, fechar a ficha com aviso discreto.

## Acessibilidade

- navegação por teclado em desktop;
- labels/aria nos ícones;
- drawer e bottom sheet com foco controlado;
- contraste suficiente;
- status com texto + cor;
- suporte a zoom do navegador;
- não bloquear orientação;
- respeitar reduced motion.

## Testes previstos

### Unitários

- parser do fragmento de pareamento;
- remoção do token da URL;
- persistência/remoção do pareamento;
- API client monta Authorization sem expor segredo;
- 200/401/404/5xx;
- polling 30 s;
- pause/resume por Visibility API;
- single in-flight / AbortController;
- projeções das quatro abas iguais às regras do Desktop;
- prioridade do navio por berço;
- transformação das coordenadas 500×500;
- Alertas x Histórico;
- formatação de datas;
- estados online/stale/offline;
- detecção de install/standalone;
- schema incompatível.

### Componentes

- header;
- drawer;
- footer;
- lista das quatro abas;
- cards de estado;
- mapa;
- vessel bottom sheet;
- Alertas;
- Histórico;
- Config.;
- estados vazios/erro.

### E2E / Playwright

Viewports mínimos:

- iPhone compacto;
- iPhone/Android moderno;
- tablet;
- desktop responsivo.

Fluxos:

1. abrir sem pareamento;
2. consumir link `/#/pair/...`;
3. token some da URL;
4. snapshot aparece;
5. alternar as quatro tabs;
6. abrir navio no mapa;
7. bottom sheet abre com drawer fechado;
8. abrir drawer fecha sheet;
9. Alertas/Histórico;
10. estado stale;
11. 401 exige novo QR;
12. background/foreground pausa e retoma polling;
13. esquecer aparelho;
14. instalar PWA quando evento de instalação estiver disponível.

Nenhum teste automatizado depende da API de produção.

## Docker/local

Substituir o placeholder atual de `frontend/` pelo app Vite real.

Dev:

- Vite com hot reload;
- proxy `/api` para API local;
- Compose continua oferecendo frontend em `:5173`.

Prod-like Docker:

- build estático do Vite;
- Nginx serve SPA;
- `/api/` continua proxy para serviço API no compose local.

O Docker não define o deploy Vercel; serve desenvolvimento e validação local.

## Vercel

Adicionar frontend como segundo service do mesmo projeto.

Requisitos:

- API continua isolada em `api/`;
- frontend em `frontend/`;
- `/api/v1/*` resolve para FastAPI antes de qualquer catch-all;
- demais rotas resolvem para a SPA;
- recarregar `/alertas`, `/historico`, etc. não pode retornar 404;
- frontend não recebe `SUPABASE_SECRET_KEY`, `SUPABASE_DB_URL` ou `DEVICE_SECRET`.

O frontend não precisa de variável pública com URL da API quando estiver same-origin.

## Handoff para SPEC 021 — Web Push

A arquitetura desta spec deve deixar espaço para Web Push sem implementá-lo.

Primeiro tipo de notificação planejado:

```text
maneuver_confirmed
```

Exemplos futuros:

- atracação confirmada;
- desatracação confirmada.

A SPEC 021 deverá cobrir:

- Service Worker Push API;
- permissão por gesto do usuário;
- PushSubscription;
- VAPID;
- persistência de subscriptions no backend;
- múltiplos celulares para o mesmo `device_id`;
- idempotência do evento;
- cleanup de subscriptions inválidas;
- preferências do usuário.

`forecast_changed` fica reservado para uma spec posterior até existir regra semântica de mudança
relevante.

## Riscos

- **Token em storage do browser:** mitigar com zero scripts de terceiros, CSP e remoção imediata do hash.
- **Service worker cachear API autenticada:** regra explícita de nunca cachear `/api/v1/*`.
- **Frontend divergir das projeções Desktop:** testes de fixtures compartilhadas e regras documentadas.
- **Mapa perder alinhamento responsivo:** coordenadas relativas ao mapa 500×500, não viewport.
- **iOS não oferecer prompt automático:** fluxo específico com instrução de Adicionar à Tela de Início.
- **Bottom sheet e drawer simultâneos:** estado de navegação mutuamente exclusivo.
- **Polling duplicado após rerender:** hook único com cleanup/AbortController.
- **401 após rotação no Desktop:** remover pareamento e pedir novo QR.
- **Schema futuro:** rejeitar versão desconhecida em vez de renderizar parcialmente.
- **Foto de navio ausente:** não usar placeholder enganoso; extensão futura por IMO.

## Critérios de aceite

- [ ] React + TypeScript + Vite substituem o placeholder atual.
- [ ] Frontend é mobile-first e responsivo nos viewports definidos.
- [ ] Pareamento v1 é consumido sem enviar token ao servidor na URL.
- [ ] Token é removido da barra de endereço imediatamente.
- [ ] Pareamento válido é persistido localmente; 401 remove/revoga sessão local.
- [ ] Frontend chama somente `/api/v1/*` same-origin com Bearer.
- [ ] Polling é 30 s somente enquanto visible e GET é imediato no retorno.
- [ ] Só existe um GET em voo.
- [ ] Último snapshot em memória continua visível em falha temporária.
- [ ] `collector_online` controla estado ativo/stale.
- [ ] Mapa usa `piers.png` e coordenadas/projeção equivalentes ao Desktop.
- [ ] Estados de navio usam sprites corretos e prioridade DES > ATR > atracado.
- [ ] Navio abre bottom sheet; drawer e sheet nunca ficam abertos juntos.
- [ ] Ficha usa apenas dados reais do snapshot e não inventa foto.
- [ ] Footer possui Manobras confirmadas, Prev. atracação, Prev. desatracação e Fundeados.
- [ ] Regras das quatro listas reproduzem o comportamento do Desktop.
- [ ] Alertas é feed curto de ocorrências recentes, sem Web Push.
- [ ] Histórico é timeline completa disponível no snapshot.
- [ ] Drawer possui Mapa, Alertas, Histórico, Config., Instalar aplicativo e Sobre.
- [ ] Config. permite esquecer o aparelho com confirmação.
- [ ] Manifest/service worker tornam o app instalável.
- [ ] iOS recebe instrução específica de instalação quando necessário.
- [ ] Service worker nunca cacheia respostas autenticadas de `/api/`.
- [ ] PWA abre shell sem rede.
- [ ] Schema incompatível produz erro explícito.
- [ ] Assets do Desktop necessários são copiados para o frontend.
- [ ] Nenhum segredo administrativo é empacotado no frontend.
- [ ] Unitários, componentes e Playwright ficam verdes.
- [ ] Deploy Vercel serve frontend e API no mesmo domínio sem quebrar `/api/v1/*`.
- [ ] Fluxo real Desktop QR -> PWA -> GET autenticado é validado antes de concluir a spec.

## Perguntas em aberto

Nenhuma pergunta bloqueante para produzir o plano de implementação.

Web Push e mudança de previsão permanecem deliberadamente fora desta spec.
