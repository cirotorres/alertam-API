# 022 - Detalhes de Alertas e linha do tempo da manobra

| Campo | Valor |
|---|---|
| Status | Implementação local concluída e validada — incluindo gate Tk/Xephyr (511 passed) |
| Criado em | 2026-09-28 |
| Atualizado em | 2026-09-28 |
| Escopo | AlertaM Desktop + FastAPI/Supabase + PWA React/Vite |
| Repositórios | `/home/ciro/dev/prog/alertamaritimo` + `/home/ciro/dev/prog/alertamaritimoAPI` |
| Dependências | SPEC 021 + design canônico de ManeuverEvent |
| Origem semântica | AlertaM Desktop continua sendo a única autoridade sobre a manobra |

## Objetivo

Transformar cada alerta operacional em um objeto consultável, e não apenas em uma linha curta ou push.

Na página **Alertas** do PWA, cada `ManeuverEvent` será clicável. O clique abre uma gaveta inferior
própria de detalhes, com o mesmo padrão de interação da ficha do navio, mas conteúdo voltado à
manobra: POB vigente, horário em que a mudança foi observada/confirmada pelo AlertaM, diferenças
antes → depois e a linha do tempo completa daquele `maneuver_id`.

O Desktop deve oferecer o mesmo contexto operacional por meio de uma janela de detalhes da
manobra aberta a partir do histórico local, sem depender da API para reconstruir o ciclo.

## Intenção e critérios de sucesso

O usuário deve conseguir responder, a partir de um alerta:

- qual navio e qual tipo de manobra estão envolvidos;
- qual POB estava vigente;
- quando o AlertaM confirmou a mudança;
- quanto a conclusão observada diferiu do POB, quando isso puder ser calculado com segurança;
- quais atualizações de POB e/ou berço ocorreram antes da conclusão;
- qual foi a sequência completa de CONFIRMED → UPDATED → COMPLETED/CANCELLED;
- se o horário exibido é uma observação do sistema ou um horário físico exato.

O push continua curto. O detalhe fica disponível após o toque.

## Princípios

1. O Desktop continua sendo a única autoridade semântica de `ManeuverEvent`.
2. A API não redetecta manobras a partir de snapshots.
3. Eventos permanecem imutáveis.
4. A gaveta é uma projeção de eventos já existentes, não um novo detector.
5. `occurred_at` significa **instante em que a mudança foi confirmada pelo AlertaM**, após a proteção
   anti-oscilação. Não significa necessariamente o segundo físico exato da manobra.
6. Quando houver uma primeira observação candidata anterior ao debounce, ela pode ser preservada em
   `first_observed_at` para transparência.
7. A interface deve usar linguagem como **“conclusão observada”**, **“horário aproximado”** ou
   **“confirmado pelo AlertaM”**; nunca afirmar precisão física que a planilha não fornece.

## Extensão do contrato ManeuverEvent

O contrato atual continua válido. Esta spec adiciona dois campos opcionais a novos eventos:

```text
pob_at: ISO-8601 aware | null
first_observed_at: ISO-8601 aware | null
```

### pob_at

`pob` continua sendo o texto original apresentado pelo WebPilot, por exemplo:

```text
28/09 12:00
```

`pob_at` é a forma temporal normalizada pelo Desktop, por exemplo:

```text
2026-09-28T12:00:00-03:00
```

O Desktop é responsável pela normalização porque possui o contexto da coleta e do fuso operacional.

Regra para virada de ano: ao converter `DD/MM HH:MM`, escolher a ocorrência de calendário
coerente/mais próxima da coleta que originou o estado, evitando interpretar dezembro como futuro de
quase um ano ou janeiro como passado de quase um ano.

Se o POB não puder ser interpretado com segurança:
- manter `pob`;
- enviar `pob_at = null`;
- a UI exibe o texto, mas não calcula diferença temporal.

### first_observed_at

Quando um candidato de CONFIRMED, UPDATED, COMPLETED ou CANCELLED é visto pela primeira vez antes
do debounce, registrar esse instante.

Quando o evento é confirmado:
- `first_observed_at` = primeira coleta em que a mudança candidata apareceu;
- `occurred_at` = coleta que tornou a mudança semanticamente confirmada.

Quando a regra de intervalo longo permite confirmação direta, os dois podem ser iguais.

Eventos históricos já armazenados sem esses campos continuam válidos.

## Diferença POB × conclusão observada

Para COMPLETED, a gaveta usa:
- `pob_at` do evento terminal, que representa o último POB vigente conhecido;
- `occurred_at` como horário em que a conclusão foi confirmada pelo AlertaM.

Exemplo:

```text
POB vigente:                  12:00
Conclusão observada:          12:50
Diferença para o POB:         50 min depois
Primeira observação:          12:49   (quando disponível)
```

A interface não escreve “o navio saiu às 12:50”. Deve escrever algo como:

```text
Conclusão observada pelo AlertaM: 12:50
```

e, em texto auxiliar:

```text
Horário aproximado baseado na atualização da planilha.
```

A mesma regra vale para atracação concluída.

Quando `pob_at` for nulo, omitir a diferença em vez de tentar interpretar o texto no frontend.

## Atualizações antes → depois

`UPDATED.changes` continua sendo a fonte canônica.

Exemplo POB:

```text
POB
Antes: 12:00
Agora: 13:30
Diferença: 1h30 depois
```

Exemplo berço:

```text
Berço
Antes: 7
Agora: 8
```

Se POB e berço mudarem na mesma confirmação, exibir ambos no mesmo alerta.

O cálculo temporal de uma atualização usa `pob_at` do evento atual e o `pob_at` do evento anterior
do mesmo ciclo quando ambos existirem. Se o evento anterior já tiver expirado ou não possuir forma
temporal canônica, a diferença é omitida. A string `changes.pob` continua sendo a evidência visual
antes → depois.

## API de detalhe

Adicionar uma leitura session-scoped por evento:

```http
GET /api/v1/mobile/events/{event_id}/detail
```

A resposta contém somente eventos do mesmo `device_id` da sessão:

```text
selected_event_id
maneuver_id
events[]
```

`events[]` é a sequência completa ainda retida daquele `maneuver_id`, ordenada por
`ingestion_id` crescente.

A API não calcula “atraso”, “adiantamento” ou conclusão física. Ela apenas devolve os dados canônicos.

### Evento ausente

Retenção cloud continua em 30 dias.

Se:
- o event_id expirou;
- pertence a outro device;
- nunca existiu;

a API responde como recurso não encontrado sem revelar existência em outro device.

A PWA mostra:

```text
Este alerta não está mais disponível no histórico recente.
```

## PWA — lista de Alertas clicável

Cada item da timeline deixa de ser apenas `<li>` passivo e passa a oferecer uma área de toque
acessível equivalente a botão.

Requisitos:
- toda a área útil do alerta é clicável;
- teclado/ARIA continuam funcionais;
- não criar um pequeno alvo de toque somente sobre o título;
- o clique atualiza a URL para `/alertas?event=<event_id>`;
- o query param passa a representar o alerta aberto, não apenas destaque visual.

Fechar a gaveta remove o `event` da URL sem sair de Alertas.

## PWA — AlertDetailSheet

Criar uma gaveta própria, separada de `VesselSheet`, mas reutilizando o padrão de:
- backdrop;
- drag handle;
- gesto para baixo para fechar;
- resistência elástica para cima;
- rolagem interna quando o conteúdo exceder a altura;
- safe-area do iOS.

Não acoplar conteúdo de alerta dentro de `VesselSheet`.

### Conteúdo mínimo

Cabeçalho:
- tipo da manobra;
- estado do evento;
- nome do navio;
- IMO quando disponível.

Resumo:
- berço vigente;
- POB vigente;
- horário observado/confirmado pelo AlertaM;
- primeira observação candidata, quando disponível;
- diferença para POB quando calculável;
- nota de horário aproximado para terminal.

Para UPDATED:
- blocos antes → depois;
- diferença temporal do POB quando calculável.

Linha do tempo:
- CONFIRMED;
- todos os UPDATED;
- COMPLETED ou CANCELLED;
- horário de cada evento;
- detalhes relevantes de cada passo.

O evento selecionado é visualmente destacado dentro da linha do tempo.

## Deep link de push

O payload continua apontando para:

```text
/alertas?event=<event_id>
```

Ao tocar no push:
1. focar/abrir o PWA como hoje;
2. abrir Alertas;
3. buscar diretamente o detalhe do event_id;
4. subir a gaveta automaticamente;
5. destacar o evento selecionado na timeline interna.

Não depender de paginar dezenas de alertas antigos para conseguir abrir o deep link.

## Foreground

O aviso interno de evento novo usa o mesmo destino.

Tocar no banner/toast em foreground:
- abre `/alertas?event=<event_id>`;
- sobe a mesma `AlertDetailSheet`.

Não criar uma segunda experiência de detalhe exclusiva para foreground.

## Histórico PWA

A página Histórico pode reutilizar a mesma gaveta.

Ao tocar em um evento dentro de um ciclo:
- abrir `AlertDetailSheet`;
- usar o event_id selecionado;
- não duplicar um segundo componente de detalhe.

## Desktop — ledger local de eventos

O outbox não pode ser usado como histórico, pois eventos enviados são removidos após ACK.

O runtime local passa a preservar um ledger recente separado do outbox:

```text
event_history: ManeuverEvent[]
```

Regras:
- acrescentar evento no ledger na mesma transição atômica que atualiza state + outbox;
- ACK remoto remove somente do outbox, nunca do ledger;
- retenção local: 30 dias;
- eventos já existentes em runtime antigo migram sem inventar histórico;
- nenhuma dependência de rede para abrir detalhes.

O ledger pode viver no mesmo `maneuver_runtime.json` desde que a escrita continue atômica.

## Desktop — Detalhes da manobra

No painel **Manobras Confirmadas/Histórico**, duplo clique em uma linha abre uma janela não modal
**Detalhes da manobra**.

Conteúdo:
- navio/IMO;
- tipo;
- estado atual/final;
- berço;
- POB vigente;
- confirmação observada;
- atualizações antes → depois;
- conclusão/cancelamento observado;
- diferença para POB;
- timeline local do mesmo `maneuver_id`.

Para uma manobra que nasceu como baseline e não possui CONFIRMED no ledger, mostrar explicitamente:

```text
Esta manobra já estava em andamento quando o AlertaM iniciou.
```

Não fabricar um CONFIRMED retroativo.

## Áudio Desktop

Esta spec não altera as regras da Fase 3:
- CONFIRMED/UPDATED → voz;
- COMPLETED/CANCELLED → chime + voz;
- mute/repeat permanecem iguais.

O novo detalhe é visual e histórico.

## Persistência cloud

`maneuver_events` continua com retenção de 30 dias.

A migration desta spec somente precisa acomodar os campos opcionais adicionais no payload; o modelo
continua imutável e idempotente por `event_id`.

Nenhuma tabela nova é obrigatória para a SPEC 022.

## Compatibilidade

Clientes/eventos antigos:
- sem `pob_at` → mostrar POB textual, sem cálculo;
- sem `first_observed_at` → mostrar somente `occurred_at`;
- sem CONFIRMED por baseline → timeline começa no primeiro evento real disponível.

A evolução deve ser coordenada Desktop → API → frontend para que `extra=forbid`/Zod strict não
quebrem o contrato durante deploy.

## Segurança

- endpoint de detalhe usa a sessão mobile existente;
- event_id de outro device não pode vazar metadados;
- nenhum DEVICE_SECRET/VIEW_SECRET entra no detalhe;
- não armazenar HTML bruto/WebPilot bruto no evento;
- não expor endpoint/chaves de push.

## Tratamento de falhas

### API offline
Desktop continua gravando ledger + outbox localmente.

### Evento ainda na outbox
Desktop consegue abrir detalhes localmente; PWA só verá após ingestão.

### Detail endpoint falha temporariamente
A lista Alertas permanece utilizável e a gaveta mostra erro recuperável com opção de tentar novamente.

### Retenção expirou
Mostrar estado de indisponibilidade histórica, sem loop de paginação.

### POB inválido
Mostrar string original e omitir diferença temporal.

## Fora do escopo

- AIS/GPS;
- estimar posição física do navio;
- alterar retenção cloud acima de 30 dias;
- editar manobra pelo PWA;
- substituir ManeuverEvent;
- novos tipos de push;
- exportação de timeline;
- anexos/fotos dentro da gaveta de alerta.

## Cobertura mínima TDD

### Desktop
- `pob_at` normaliza POB no fuso de Fortaleza;
- virada de ano é resolvida sem salto absurdo;
- POB inválido mantém texto e `pob_at=null`;
- `first_observed_at` preserva a primeira coleta candidata;
- ledger é gravado atomicamente com state/outbox;
- ACK não remove ledger;
- retenção local remove apenas eventos expirados;
- baseline não cria CONFIRMED;
- janela de detalhe monta timeline na ordem correta.

### API
- contrato aceita os campos opcionais novos;
- evento antigo continua válido;
- detail por event_id retorna somente mesmo device;
- eventos do ciclo vêm por ingestion_id;
- event_id inexistente/outro device não vaza informação;
- idempotência existente continua intacta.

### PWA
- item de Alertas é clicável;
- click escreve `?event=`;
- deep link abre sheet mesmo sem evento na primeira página do feed;
- fechar sheet remove query param;
- terminal mostra POB + conclusão observada + diferença;
- POB sem forma canônica não mostra diferença;
- UPDATED mostra from → to;
- timeline destaca evento selecionado;
- drag/scroll do AlertDetailSheet preserva comportamento mobile;
- evento expirado mostra estado amigável.

## Critérios de aceite

- [ ] Alertas é clicável em toda a área útil de cada item.
- [ ] Push abre diretamente a gaveta do alerta.
- [ ] Gaveta mostra timeline completa retida do maneuver_id.
- [ ] COMPLETED mostra POB vigente e conclusão observada.
- [ ] Diferença POB × observado só aparece quando temporalmente segura.
- [ ] UPDATED mostra antes → depois.
- [ ] Linguagem não afirma horário físico exato.
- [ ] Desktop abre detalhes da manobra sem depender da API.
- [ ] Ledger local sobrevive a ACK e reinício.
- [ ] Baseline não ganha confirmação inventada.
- [ ] Retenção cloud/local permanece limitada a 30 dias.
- [ ] Nenhuma regra de voz/push atual é quebrada.

## Decisões fechadas

- O detalhe é uma gaveta própria no PWA.
- O deep link de push abre a gaveta automaticamente.
- O Desktop oferece detalhe equivalente por janela local.
- `occurred_at` é observação confirmada pelo AlertaM, não verdade física absoluta.
- A diferença de horário usa POB temporal normalizado, nunca parsing oportunista no frontend.
- Não há pergunta de produto bloqueante para o writing-plans.
