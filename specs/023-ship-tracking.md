# 023 - Ship Tracking de navios e notificações por acompanhamento

| Campo | Valor |
|---|---|
| Status | Plano 1 — Core Events concluído e validado; Plano 2 — Installations & Dispatch é o próximo |
| Criado em | 2026-09-28 |
| Atualizado em | 2026-09-28 |
| Escopo | AlertaM Desktop + FastAPI/Supabase + PWA React/Vite |
| Repositórios | `/home/ciro/dev/prog/alertamaritimo` + `/home/ciro/dev/prog/alertamaritimoAPI` |
| Dependências | SPEC 021 + SPEC 022 |
| Ciclo MVP | Acompanhamento permanece ativo até cancelamento manual, salvo revogação de segurança |

## Objetivo

Permitir que o operador escolha um navio específico e o acompanhe ao longo de suas mudanças
operacionais no WebPilot, recebendo no PWA notificações sobre movimentações e atualizações daquele
navio e mantendo uma visão consolidada do seu histórico recente.

O nome de produto da funcionalidade será **Ship Tracking** / **Acompanhamento de navio**.

No MVP, Ship Tracking significa acompanhamento das mudanças observadas pelo AlertaM na planilha
WebPilot. Não significa AIS, GPS ou rastreamento geográfico em tempo real.

## Intenção e critérios de sucesso

Ao marcar um navio como acompanhado, o usuário deve continuar recebendo contexto relevante sobre ele
mesmo fora de uma manobra específica.

Exemplos:
- PREVISTO → FUNDEADO;
- FUNDEADO → ATRACANDO;
- ATRACANDO → ATRACADO;
- ATRACADO → DESATRACANDO;
- mudança de ETA;
- mudança de ETB/ETS;
- mudança de POB;
- mudança de berço;
- mudança de bordo;
- desaparecimento da planilha;
- reaparecimento posterior;
- CONFIRMED/UPDATED/COMPLETED/CANCELLED já cobertos por ManeuverEvent.

O acompanhamento permanece ativo até o usuário escolher **Parar de acompanhar**.

Não existe expiração automática de tracking no MVP.

## Princípios arquiteturais

1. O Desktop continua sendo a autoridade sobre observações do WebPilot.
2. A API não compara snapshots para descobrir mudanças de navio.
3. `ManeuverEvent` continua sendo a fonte canônica de semântica de manobra.
4. Ship Tracking não duplica ManeuverEvent.
5. Mudanças operacionais não cobertas por ManeuverEvent usam um segundo contrato:
   `VesselTrackingEvent`.
6. Preferências de acompanhamento são individuais por instalação PWA.
7. Acompanhamento local do Desktop é independente do acompanhamento de cada celular.
8. Uma instalação que acompanha um navio não altera automaticamente as demais instalações.
9. Segurança/revogação pode encerrar tracking; fora isso, somente cancelamento manual encerra.

## O que não deve acontecer

- API não pode transformar snapshots em eventos.
- Ship Tracking não pode criar um segundo detector de manobra concorrente.
- O usuário não pode receber dois pushes equivalentes pela mesma mudança.
- Reiniciar o Desktop não pode gerar replay de todas as mudanças percebidas durante o downtime.
- Um tracking ativo não pode expirar só por o navio desaparecer da planilha.
- Nome de fallback não deve ser promovido para outro navio por aproximação/fuzzy matching.

## Identidade do navio acompanhado

Usar a mesma filosofia já aprovada para manobras.

Prioridade:
1. IMO válido;
2. nome normalizado como fallback.

Formato conceitual:

```text
IMO:9348065
NAME:MAERSK MONTE ALEGRE
```

### Tracking com IMO

Quando existe IMO válido, ele é a identidade principal.

Mudanças de nome de exibição não interrompem o acompanhamento.

### Tracking por nome

Quando não existe IMO:
- usar nome normalizado;
- trim;
- colapsar espaços;
- uppercase.

Se uma observação futura apresentar IMO válido para o mesmo nome normalizado, a API pode promover
a inscrição de tracking para esse IMO com base no dado explícito do evento recebido do Desktop.

Depois da promoção, IMO passa a ser a chave principal.

Não fazer fuzzy matching por nomes semelhantes.

Se um navio sem IMO mudar de nome e não houver evidência segura de identidade, o tracking pode deixar
de correlacionar esse navio. Essa limitação é aceita no MVP.

## Contrato VesselTrackingEvent

Contrato conceitual:

```text
event_id: UUID
vessel_identity: string
vessel_imo: string | null
vessel_name: string
occurred_at: ISO-8601 aware
first_observed_at: ISO-8601 aware | null
maneuver_id: UUID | null
changes: object
current: object
```

`event_id` nasce no Desktop antes de qualquer tentativa HTTP.

Eventos são imutáveis e idempotentes.

### changes

Campos operacionais elegíveis no MVP:

```text
presence
status
section
berth
side
eta
etb_ets
pob
```

Cada mudança usa:

```json
{
  "from": "...",
  "to": "..."
}
```

Valores podem ser nulos.

Mudanças simultâneas na mesma confirmação produzem **um único VesselTrackingEvent** com múltiplos
campos em `changes`.

### current

O evento carrega o estado resultante necessário para apresentação simples:

```text
present
status
section
berth
side
eta
etb_ets
pob
pob_at
```

Não transportar campos sem relação com operação apenas porque existem no snapshot.

Bandeira, agência, origem, rebocadores e IRIN continuam disponíveis na ficha do navio, mas não
disparam tracking no MVP.

## Presença

`presence` representa se o navio aparece ou não em uma coleta válida do WebPilot.

Exemplo:

```text
presence: true → false
```

O desaparecimento precisa respeitar debounce antes de virar evento de tracking.

Uma coleta inválida/timeout/login/offline nunca significa que todos os navios desapareceram.

Reaparecimento:

```text
presence: false → true
```

é elegível para tracking.

## Debounce

Aplicar a mesma filosofia dos ManeuverEvent:
- mudança precisa aparecer em duas coletas consecutivas;
- regra de intervalo longo pode confirmar diretamente quando já for segura;
- `first_observed_at` guarda a primeira observação;
- `occurred_at` guarda a confirmação semântica.

Mudanças transitórias não produzem evento nem push.

## Relação com ManeuverEvent

Quando uma mudança já está semanticamente representada por um ManeuverEvent, não criar um
VesselTrackingEvent duplicado para a mesma informação.

Exemplos:
- POB muda numa manobra ativa → `ManeuverEvent.UPDATED`;
- berço muda numa manobra ativa → `ManeuverEvent.UPDATED`;
- FUNDEADO/PREVISTO com POB vira ATRACANDO → `ManeuverEvent.CONFIRMED`;
- ATRACANDO → ATRACADO → `ManeuverEvent.COMPLETED`;
- ATRACADO com POB vira DESATRACANDO → `ManeuverEvent.CONFIRMED`;
- DESATRACANDO → ausente → `ManeuverEvent.COMPLETED`.

Se, na mesma coleta, além do ManeuverEvent houver mudança de ETA/ETB/ETS/bordo não representada
pela manobra, um VesselTrackingEvent pode transportar somente esses campos residuais.

A timeline de Ship Tracking é uma projeção unificada de:
- ManeuverEvent;
- VesselTrackingEvent.

## Push sem duplicação

Tracking é um canal de elegibilidade independente das quatro preferências gerais de ManeuverEvent.

Para um ManeuverEvent:
- se a categoria geral estiver habilitada, é elegível;
- OU, se aquele navio estiver sendo acompanhado naquela instalação, também é elegível;
- se as duas condições forem verdadeiras, enviar **um único push**.

A tabela/claim existente de delivery por event_id + installation_id continua impedindo duplicação
para ManeuverEvent.

Quando tracking for o motivo da entrega, a apresentação pode usar linguagem de acompanhamento:

```text
MSC GRACE · Acompanhamento
Desatracação confirmada · Berço 9 · POB 07:30
```

Para VesselTrackingEvent, somente instalações que acompanham o navio são elegíveis.

## Acompanhamento por instalação PWA

### Identidade de instalação independente do Web Push

Ship Tracking precisa continuar funcionando mesmo quando Web Push estiver desligado. Portanto,
`installation_id` não pode existir somente em `push_installations`.

A PWA já possui um UUID local estável de instalação. A sessão mobile deve passar a incorporar essa
identidade:

- ao criar a sessão, o cliente envia `device_id + installation_id`;
- a API garante uma linha de `mobile_installations` vinculada ao `device_id`;
- o cookie assinado passa a representar `device_id + installation_id + exp`;
- endpoints de tracking resolvem ambos pela sessão e nunca aceitam escolher livremente outra instalação;
- recuperar a sessão devolve a mesma instalação;
- `push_installations` usa o mesmo `installation_id`, mas continua sendo opcional;
- **Esquecer este aparelho** revoga a instalação mobile e seus trackings;
- rotação/revogação do VIEW_SECRET revoga as instalações mobile daquele acesso e desativa os trackings
  correspondentes.

`mobile_installations` é identidade de aparelho/PWA, não uma PushSubscription. Isso permite:
- tracking com push desligado;
- recriar uma PushSubscription sem perder o acompanhamento;
- manter isolamento por instalação mesmo quando a permissão de notificação nunca foi concedida.

Criar persistência cloud conceitual `tracked_vessels`.

Uma linha ativa representa:

```text
tracked_vessel_id: UUID
installation_id: UUID
device_id: string
vessel_identity: string
vessel_imo: string | null
vessel_name: string
started_at: timestamptz
active: boolean
stopped_at: timestamptz | null
last_seen_at: timestamptz | null
```

### Ciclo de vida

Ativar:
- explícito pelo usuário;
- sem replay de push anterior a `started_at`.

Continuar:
- indefinidamente no MVP;
- inclusive quando o navio some da planilha;
- inclusive após a manobra atual terminar.

Parar:
- somente quando usuário toca **Parar de acompanhar**;
- ou quando uma ação de segurança revoga a instalação.

### Exceções de segurança

Mesmo com a regra “até cancelamento manual”, devem desativar tracking:
- **Esquecer este aparelho**;
- rotação/revogação de VIEW_SECRET;
- remoção permanente da instalação push quando a sessão/dispositivo é explicitamente revogado.

Expiração normal do cookie não deve, sozinha, apagar tracking.

## Endpoints PWA

Rotas conceituais, sempre session-scoped:

```http
GET    /api/v1/mobile/tracked-vessels
POST   /api/v1/mobile/tracked-vessels
DELETE /api/v1/mobile/tracked-vessels/{tracked_vessel_id}
GET    /api/v1/mobile/tracked-vessels/{tracked_vessel_id}/events
GET    /api/v1/mobile/tracked-vessels/events?after=<cursor>
```

POST aceita somente um alvo visível/derivado de dado legítimo do PWA:

```text
vessel_identity
vessel_imo
vessel_name
```

O servidor resolve `device_id` e `installation_id` pela sessão/instalação atual; o cliente não
pode escolher outra instalação livremente.

DELETE é idempotente para o mesmo tracking já desativado.

O feed agregado `/tracked-vessels/events`:
- é session/installation-scoped;
- usa cursor de ingestão crescente;
- entrega somente `VesselTrackingEvent` de trackings ativos e posteriores ao respectivo `started_at`;
- existe para polling/aviso interno em foreground, evitando um request por navio acompanhado;
- não substitui a timeline unificada por navio;
- não duplica `ManeuverEvent`: esses continuam no feed existente, e o PWA decide o destino do aviso
  conforme preferência geral + tracking ativo.

## VesselTrackingEvent Desktop → API

Canal confiável separado:

```http
POST /api/v1/devices/{device_id}/vessel-tracking-events
Authorization: Device <DEVICE_SECRET>
```

Mesmo padrão do outbox de ManeuverEvent:
- event_id gerado antes do HTTP;
- persistir localmente antes do envio;
- FIFO;
- retry idempotente;
- API offline não bloqueia coleta;
- mesmo event_id + payload diferente é conflito seguro.

Não reutilizar `SyncPublisher` latest-only.

## Ledger local de VesselTrackingEvent

A outbox não é histórico: após ACK remoto, o evento deixa a fila de envio. Para que a timeline local
do Desktop continue disponível depois do envio e após reinício, manter um ledger recente separado:

```text
tracking_event_history: VesselTrackingEvent[]
```

Regras:
- acrescentar o evento ao ledger na mesma transição atômica que atualiza estado observado + outbox;
- ACK remoto remove somente da outbox, nunca do ledger;
- retenção local: 30 dias;
- a timeline local do navio é construída a partir desse ledger, combinada com ManeuverEvent quando aplicável;
- primeira execução sem histórico semeia baseline sem fabricar VesselTrackingEvent retroativo;
- falha/corrupção de histórico não pode bloquear coleta, UI ou envio futuro.

O ledger pode compartilhar o mesmo arquivo de runtime do detector desde que a persistência continue
atômica e independente da política de ACK da outbox.

## Persistência cloud

Adicionar conceitualmente:

### vessel_tracking_events

- event_id único;
- device_id;
- vessel_identity;
- vessel_imo;
- vessel_name;
- occurred_at;
- payload;
- ingestion_id;
- ingested_at.

Retenção: 30 dias.

### tracked_vessels

Tracking ativo não possui TTL no MVP.

Linhas desativadas podem ser limpas posteriormente; isso não faz parte do caminho crítico.

### vessel_tracking_deliveries

Bookkeeping de Web Push para VesselTrackingEvent, equivalente à disciplina já usada por
`push_deliveries`.

Estados mínimos:
- SENDING;
- DELIVERED;
- IGNORED_FOREGROUND;
- IGNORED_BEFORE_TRACKING;
- RETRY_PENDING;
- PERMANENT_FAILURE.

Preferência geral de categoria não se aplica a VesselTrackingEvent; o próprio tracking é a intenção.

## Retenção e replay

Eventos:
- ManeuverEvent: 30 dias, como hoje;
- VesselTrackingEvent: 30 dias.

Tracking:
- sem expiração automática;
- persiste até ação explícita ou revogação de segurança.

Sem replay de push:
- evento com `occurred_at < started_at` nunca gera push para aquele tracking;
- pode existir no banco por retenção, mas não é notificado retroativamente.

## Detector de tracking no Desktop

Criar um detector puro separado de ManeuverTracker.

Responsabilidade:
- manter uma projeção operacional recente por navio;
- comparar somente snapshots válidos;
- confirmar mudanças com debounce;
- produzir VesselTrackingEvent residual;
- não tomar decisões de ciclo de manobra.

O detector remoto produz eventos elegíveis para **todos os navios observados**, não apenas para os
favoritos locais do Desktop. O Desktop não conhece nem consulta a lista de tracking dos celulares;
a API é quem cruza o evento recebido com `tracked_vessels` de cada instalação. Isso mantém Desktop
e PWA desacoplados e permite preferências independentes por aparelho.

### Estado observado

Persistir o estado necessário para comparar:
- identity;
- name;
- imo;
- present;
- status;
- section;
- berth;
- side;
- eta;
- etb_ets;
- pob/pob_at;
- last_seen_at.

### Inicialização/reinício

Na primeira coleta após instalação sem estado:
- semear baseline;
- não gerar evento retroativo.

Após reinício com estado persistido:
- a primeira coleta válida reconcilia o baseline atual;
- não transformar automaticamente diferenças ocorridas durante downtime em uma enxurrada de push;
- a partir das próximas observações, tracking volta ao fluxo normal.

Isso privilegia ausência de falso replay quando o Desktop esteve desligado.

## Tracking local no Desktop

O Desktop também possui uma lista local própria de navios acompanhados.

Ela não controla as instalações PWA.

Persistência local conceitual:

```text
tracked_vessels.json
```

ou estrutura equivalente no diretório de dados.

Campos mínimos:
- vessel_identity;
- vessel_imo;
- vessel_name;
- started_at;
- active;
- last_seen_at;
- último estado conhecido.

Não expira automaticamente.

## Desktop — ficha do navio

Adicionar ação visível:

```text
☆ Acompanhar navio
```

Quando ativo:

```text
★ Acompanhando
```

A ação persiste localmente.

Se o navio não possui IMO, explicar de forma discreta que o acompanhamento usa o nome como
identidade de fallback.

## Desktop — janela Acompanhados

Adicionar um acesso discreto **⭐ Acompanhados** nas utilidades do Desktop.

Abrir janela não modal com:
- navios acompanhados;
- nome;
- IMO quando disponível;
- último status conhecido;
- último berço;
- último POB;
- visto por último;
- presente/ausente;
- botão **Parar de acompanhar**.

A janela permanece útil mesmo quando o navio não está na planilha atual.

## Desktop — indicação visual

Quando um navio acompanhado estiver presente:
- exibir ★ ao lado do nome nas listas onde couber sem quebrar layout;
- sinalizar na ficha;
- sinalizar de forma discreta no mapa/tooltip.

Não alterar as cores vermelho/verde dos estados de manobra; a estrela é um marcador adicional,
não um novo estado operacional.

## Desktop — notificações de tracking

No MVP, tracking local adicional é **visual**, não cria uma nova voz/chime para cada ETA/ETB/ETS.

ManeuverEvent continua usando a voz/chime já existente.

Mudanças de tracking aparecem:
- na janela Acompanhados;
- na timeline local do navio;
- como destaque visual recente.

Isso evita transformar alterações frequentes de previsão em áudio irritante.

## PWA — ficha do navio

Adicionar à `VesselSheet`:

```text
☆ Acompanhar navio
```

Ativo:

```text
★ Acompanhando
```

O botão:
- usa a instalação atual;
- persiste na API;
- funciona de forma idempotente;
- não depende de o PWA permanecer aberto.

## PWA — AlertDetailSheet

A SPEC 022 passa a oferecer também:

```text
☆ Acompanhar este navio
```

Isso permite iniciar tracking a partir de um alerta, inclusive quando o navio já não está mais no
snapshot atual.

## PWA — página Acompanhados

Adicionar item no drawer/sidetab:

```text
Acompanhados
```

A página lista os trackings ativos da instalação.

Cada item mostra:
- nome;
- IMO;
- último estado conhecido;
- berço/POB quando disponíveis;
- visto por último;
- presente/ausente.

Ao tocar, abrir detalhe/timeline do navio acompanhado.

## PWA — timeline unificada

A timeline de um navio acompanhado mistura:
- ManeuverEvent;
- VesselTrackingEvent.

Como os dois tipos vivem em persistências diferentes, seus `ingestion_id` não são diretamente
comparáveis. A ordem unificada é determinística por:
1. `occurred_at` crescente;
2. `ingested_at` crescente como desempate;
3. `event_id` como último desempate estável.

Exemplo:

```text
05:20  ETA alterado · 07:00 → 08:30
06:10  Fundeado
07:12  Atracação confirmada · POB 08:00 · Berço 7
07:35  POB atualizado · 08:00 → 08:45
08:57  Atracação concluída
14:20  Desatracação confirmada · POB 16:00
16:18  Desatracação concluída
```

Não criar uma timeline separada por tipo de evento.

## Push de Ship Tracking

Exemplos:

```text
MSC GRACE · Acompanhamento
ETA alterado: 07:00 → 08:30
```

```text
MSC GRACE · Acompanhamento
Status: PREVISTO → FUNDEADO
```

```text
MSC GRACE · Acompanhamento
POB alterado: 07:30 → 08:30
```

```text
MSC GRACE · Acompanhamento
Desatracação concluída · Berço 9
```

Para desaparecimento não coberto por uma manobra:

```text
MSC GRACE · Acompanhamento
Navio não aparece mais na planilha.
```

A linguagem nunca deve transformar desaparecimento genérico em “desatracou” sem ManeuverEvent que
sustente essa conclusão.

## Foreground/background

Reutilizar a política existente:
- PWA visível → aviso interno;
- background/fechado → Web Push;
- corrida de foreground é best-effort.

Tracking não cria uma segunda estratégia de service worker.

## Deep link de tracking

O destino é determinístico conforme o tipo de evento e o motivo de elegibilidade:

```text
VesselTrackingEvent
→ /acompanhados?track=<tracked_vessel_id>&event=<event_id>

ManeuverEvent elegível somente por tracking
→ /acompanhados?track=<tracked_vessel_id>&event=<event_id>

ManeuverEvent elegível pela categoria geral da SPEC 021
→ /alertas?event=<event_id>
```

Se categoria geral e tracking estiverem habilitados ao mesmo tempo para o mesmo ManeuverEvent,
continua existindo um único push e o destino canônico permanece `/alertas?event=<event_id>`.
Tracking amplia a elegibilidade, mas não substitui a experiência canônica de detalhe da SPEC 022
quando a categoria geral já tornaria aquele evento notificável.

O usuário deve chegar ao contexto correto do evento/navio, nunca apenas à home.

## Configuração de push

No MVP não adicionar filtros por campo como “só ETA” ou “só status”.

Tracking ativo significa interesse em todas as mudanças operacionais elegíveis daquele navio.

Se notificações Web Push estiverem globalmente desativadas para a instalação:
- tracking continua salvo;
- timeline continua funcionando;
- não há push até a instalação ser reativada.

## Segurança

- A sessão mobile autentica `device_id + installation_id`; o cliente não escolhe outra instalação nos endpoints de tracking.
- `mobile_installations` existe independentemente de Web Push e é revogada em **Esquecer este aparelho**/rotação de acesso.
- PWA nunca cria VesselTrackingEvent.
- Somente Desktop autenticado cria eventos de tracking.
- Tracking é installation-scoped.
- Uma instalação não consulta/altera tracking de outra.
- Rotação do VIEW_SECRET desativa tracking ligado às instalações revogadas.
- Segredos e PushSubscription não entram em logs.
- Nome/IMO de navio não são tratados como segredo.

## Falhas

### API offline no Desktop
Tracking local continua; eventos ficam em outbox e são enviados depois.

### PWA offline
Tracking permanece registrado no servidor. Ao voltar, timeline sincroniza eventos retidos.

### Push falha
Evento permanece na timeline. Falha permanente desativa somente a subscription/entrega afetada.
A intenção de tracking não é apagada por falha do provedor; se a mesma instalação recuperar uma
subscription válida, o acompanhamento continua. Somente **Parar de acompanhar**, **Esquecer aparelho**
ou revogação de segurança encerram o tracking.

### Navio desaparece
Tracking continua ativo indefinidamente até cancelamento manual.

### Navio reaparece
Mesma identidade retoma timeline.

### Desktop reinicia
Sem replay retroativo do downtime; futuras mudanças continuam sendo acompanhadas.

### Nome fallback muda
Sem IMO e sem igualdade segura de nome, não fazer adivinhação.

## Relação com a SPEC 021

A SPEC 021 marcou “push para alteração de previsão” como fora do escopo daquela etapa.
Esta SPEC 023 é a extensão aprovada que passa a cobrir alterações operacionais de previsão
**somente quando o usuário acompanha explicitamente aquele navio**.

As quatro categorias gerais da SPEC 021 continuam existindo e não são ampliadas globalmente para ETA/ETB/ETS.

## Fora do escopo

- AIS;
- GPS;
- posição geográfica em tempo real;
- MarineTraffic/VesselFinder ou serviço comercial externo;
- tracking expirando automaticamente;
- limite máximo de navios acompanhados;
- filtros por tipo de campo;
- tracking compartilhado entre celulares;
- sincronizar automaticamente tracking local do Desktop com tracking PWA;
- busca manual por navio que não apareceu em snapshot/alerta;
- alertas de voz para ETA/ETB/ETS;
- histórico cloud acima de 30 dias.

## Cobertura mínima TDD

### Desktop — detector
- primeira coleta semeia baseline sem evento;
- ETA muda e estabiliza → um VesselTrackingEvent;
- ETA oscila e volta → zero evento;
- vários campos mudam juntos → um evento;
- snapshot inválido não gera desaparecimento em massa;
- disappearance exige debounce;
- reappearance gera presença true;
- POB/berth já cobertos por ManeuverEvent não duplicam tracking;
- mudança residual junto de ManeuverEvent preserva só campos residuais;
- retry/outbox mantém FIFO/idempotência;
- evento confirmado entra no ledger local na mesma persistência atômica de estado + outbox;
- ACK remove somente da outbox e preserva o ledger;
- retenção do ledger local remove somente eventos acima de 30 dias;
- restart preserva timeline retida e não cria replay do downtime.

### Desktop — tracking local
- acompanhar persiste;
- fechar/reabrir preserva;
- ausência do navio não cancela;
- parar manualmente desativa;
- estrela não interfere nas cores de manobra;
- janela Acompanhados funciona para presente e ausente.

### API
- sessão mobile cria/recupera `mobile_installation` estável e assina `device_id + installation_id`;
- tracking continua funcionando sem `push_installation` ativa;
- uma sessão não acessa tracking de outra instalação do mesmo device;
- POST de VesselTrackingEvent exige Device auth;
- retry idêntico é idempotente;
- payload divergente conflita;
- tracking é isolado por instalação;
- started_at impede replay;
- tracking não expira automaticamente;
- delete manual desativa;
- rotação VIEW_SECRET desativa;
- nome fallback pode promover para IMO somente com match exato de nome normalizado;
- eventos retêm 30 dias.

### Dispatch
- tracking ativo torna ManeuverEvent elegível mesmo se categoria geral estiver desligada;
- categoria + tracking juntos geram um único push;
- ManeuverEvent elegível pela categoria geral mantém deep link canônico em /alertas, mesmo com tracking ativo;
- ManeuverEvent elegível somente por tracking usa /acompanhados;
- VesselTrackingEvent usa /acompanhados e só entrega para quem acompanha;
- foreground suprime push do sistema;
- tracking iniciado depois do evento não recebe replay;
- falha numa instalação não bloqueia outras.

### PWA
- botão da VesselSheet acompanha/desacompanha;
- botão da AlertDetailSheet faz o mesmo;
- página Acompanhados mostra somente trackings da instalação;
- tracking permanece depois de conclusão de manobra;
- navio ausente continua listado;
- timeline mistura ManeuverEvent + VesselTrackingEvent;
- deep link abre tracking correto;
- push off mantém tracking salvo;
- reativar push não faz replay anterior.

## Critérios de aceite

- [ ] Usuário pode acompanhar um navio pelo PWA.
- [ ] Usuário pode acompanhar um navio pelo detalhe de um alerta.
- [ ] Usuário pode acompanhar localmente no Desktop.
- [ ] Tracking persiste até cancelamento manual no MVP.
- [ ] Navio ausente não é automaticamente removido.
- [ ] Mudanças de ETA/ETB/ETS/status/presença relevantes viram tracking event.
- [ ] ManeuverEvent não é duplicado por tracking event equivalente.
- [ ] Instalação recebe no máximo um push por ocorrência semântica.
- [ ] Tracking funciona mesmo com categorias gerais de manobra desligadas.
- [ ] PWA possui página Acompanhados e timeline unificada.
- [ ] Desktop possui janela Acompanhados e marcação ★.
- [ ] Reinício não produz replay em massa.
- [ ] Ledger local preserva VesselTrackingEvent após ACK por até 30 dias.
- [ ] Deep link segue regra determinística entre /alertas e /acompanhados sem duplicar push.
- [ ] Sem AIS/GPS ou inferência geográfica.
- [ ] Retenção de eventos continua limitada a 30 dias.
- [ ] Preferências permanecem isoladas por instalação.
- [ ] Tracking funciona sem PushSubscription porque a identidade de instalação é independente do Web Push.

## Decisões fechadas

- Ship Tracking é baseado no WebPilot, não em AIS.
- Tracking PWA é individual por instalação.
- Tracking Desktop é local e independente do PWA.
- Tracking não expira automaticamente no MVP.
- Somente usuário ou revogação de segurança encerra um acompanhamento.
- ManeuverEvent continua sendo canônico para manobra.
- VesselTrackingEvent cobre somente mudanças operacionais complementares.
- Push de tracking não duplica push normal da mesma ocorrência.
- ManeuverEvent elegível pela categoria geral mantém /alertas como destino canônico; somente tracking usa /acompanhados.
- VesselTrackingEvent possui ledger local separado da outbox, com retenção de 30 dias.
- Não há pergunta de produto bloqueante para o writing-plans.
