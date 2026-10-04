# SPEC 025 — WebPilot HTTP, meteorologia observada e shadow de movimentações

**Status:** Estratégia reordenada e aprovada; implementação não iniciada
**Data:** 2026-10-02
**Escopo:** AlertaM Desktop + API FastAPI/Supabase + PWA React/Vite
**Origem:** meteorologia observada do Porto do Pecém, coleta WebPilot HTTP e fundação validável para o futuro AlertaM Cloud

## 1. Contexto

O AlertaM Desktop hoje depende do WebPilot como fonte operacional das movimentações do
Porto do Pecém. A autenticação e a coleta oficial das movimentações usam Selenium e o
programa foi desenhado para permanecer ligado por longos períodos.

Durante a evolução da meteorologia foi identificada, no mesmo acesso autenticado do
WebPilot, a página da estação meteorológica do Pecém:

    /WebPilot/movimentos/grEstacaoMeteorologica.aspx?chave=4&popup=1

O HTML autenticado dessa página contém o bloco `#lblDados`, com dados observados como
horário da observação, vento atual/médio/máximo, direção, temperatura, sensação térmica,
umidade, pressão e precipitação quando disponível.

Também foi validado que requests HTTP autenticados, reutilizando a sessão do WebPilot,
conseguem obter esse HTML diretamente. Não foi encontrada API JSON interna adequada;
as páginas relevantes permanecem em ASP.NET clássico/DevExpress.

Essa necessidade real de meteorologia observada será usada para introduzir uma
arquitetura WebPilot mais robusta, separando:

- autenticação e renovação de sessão;
- transporte HTTP;
- parsing de HTML;
- domínio meteorológico;
- coleta oficial de movimentações;
- coleta HTTP em modo shadow.

A migração das movimentações será gradual. O Selenium continua sendo a fonte oficial
durante toda esta SPEC.

Esta SPEC passa a representar formalmente as Etapas A e B do roadmap arquitetural:
**Fundação HTTP/Weather** e **Shadow/Evidence Gate**. O coletor HTTP validado aqui será a base
obrigatória da futura SPEC 027 — AlertaM Cloud, sem antecipar o Cloud nem a refatoração ampla do
Desktop dentro desta SPEC.

## 2. Objetivos

1. Criar uma infraestrutura HTTP autenticada reutilizável para consumidores WebPilot.
2. Centralizar autenticação e renovação por origem autenticada, sem duplicar login por serviço.
3. Tornar a estação WebPilot Pecém a fonte atmosférica observada prioritária do Desktop.
4. Preservar Open-Meteo Forecast como fallback/complemento e Open-Meteo Marine como fonte marítima.
5. Representar freshness e indisponibilidade de forma explícita no domínio e no MobileSnapshot.
6. Evoluir o MobileSnapshot para schema v2 com rollout compatível entre Desktop, API e PWA.
7. Criar um caminho HTTP de movimentações em shadow, sem impacto operacional.
8. Comparar Selenium × HTTP no domínio normalizado e persistir evidência sanitizada.
9. Implementar um gate técnico objetivo para decidir se o collector HTTP está apto a ser reutilizado pelo AlertaM Cloud e, separadamente, sustentar futuras decisões de cutover.
10. Manter toda a nova coleta e recuperação fora da Tk main thread.
11. Extrair apenas a estrutura necessária para um collector headless reutilizável, sem antecipar uma refatoração ampla do Desktop.

## 3. Não objetivos

Esta SPEC não deve:

- remover Selenium;
- promover HTTP a fonte oficial das movimentações;
- reescrever o mecanismo de login WebPilot sem necessidade;
- alterar a semântica de `ManeuverTracker`;
- alterar regras de debounce/confirmação de manobras;
- alterar áudio/chime;
- alterar regras de Web Push;
- implementar WeatherLink;
- implementar AIS;
- misturar silenciosamente dados WebPilot e Open-Meteo como se fossem uma única fonte;
- criar um novo parser semântico de manobras em paralelo ao parser atual;
- fazer grande refatoração visual sem relação com meteorologia/fontes;
- enviar cookies, sessão ou credenciais WebPilot para API/PWA;
- executar cutover automático quando o gate técnico for atendido;
- implementar o AlertaM Cloud;
- transformar Cloud em autoridade de gestão mobile;
- realizar refatoração ampla de bootstrap/controller/UI além do mínimo necessário à extração do collector.

A promoção do HTTP para fonte oficial das movimentações permanece uma decisão posterior. O uso do
collector validado como serviço de continuidade Cloud pertence à SPEC 027 e só pode ser planejado
para execução após o gate humano desta SPEC.

## 4. Princípios obrigatórios

### 4.1 Autenticação pertence à origem, não ao consumidor

Weather HTTP, shadow de movimentações e consumidores WebPilot futuros compartilham a
mesma origem autenticada. Nenhum consumidor implementa login ou refresh diretamente.

Conceitualmente:

    WebPilot Auth Session
      ├── Weather HTTP
      ├── Maneuver Shadow HTTP
      └── futuros consumidores WebPilot

Se futuramente existir outra fonte autenticada, ela terá seu próprio coordenador de
sessão. Não se deve criar uma super-sessão global para origens distintas.

### 4.2 Falha meteorológica não derruba o monitoramento operacional

Weather WebPilot, Open-Meteo Forecast e Open-Meteo Marine podem falhar ou ficar stale
sem interromper:

- coleta oficial de navios;
- alertas;
- histórico;
- eventos;
- push;
- envio de snapshots operacionais;
- UI principal.

### 4.3 Selenium permanece referência das movimentações

Enquanto esta SPEC estiver em vigor, somente a coleta Selenium alimenta o pipeline
operacional de manobras.

O shadow HTTP é observador e comparador, nunca produtor operacional.

### 4.4 Separação mínima agora; refatoração ampla depois do Cloud

A extração de autenticação, transporte HTTP, parsing e serviços de coleta deve produzir componentes
headless e reutilizáveis. Essa separação é obrigatória porque será exercitada no shadow e poderá ser
reutilizada pela SPEC 027.

Ela não autoriza uma reorganização ampla do núcleo legado. MainWindow, controller, bootstrap e
outros acoplamentos só devem ser alterados na medida necessária para integrar com segurança os novos
serviços. A modernização estrutural extensa pertence à Etapa D do roadmap, posterior ao Cloud.

## 5. Arquitetura alvo

O desenho conceitual é:

    AlertaM Desktop
       │
       ├── WebPilotSessionProvider (contrato)
       │       │
       │       └── DesktopSeleniumSessionProvider
       │               └── BrowserSession / Selenium
       │                       └── login, validação e renovação
       │
       ├── WebPilotAuthCoordinator (um por realm)
       │       └── SessionLease
       │             ├── generation
       │             ├── cookies
       │             └── expires_at opcional/advisory
       │
       └── WebPilotHttpClient
               ├── Weather HTTP
               │      └── WebPilotWeatherParser
               │              └── ObservedWeather
               │
               └── Maneuver HTTP shadow
                      └── GridHtmlExtractor
                              └── list[list[str]]
                                      └── parse_grid_rows()
                                              └── domínio atual

Separadamente:

    Open-Meteo Forecast
      └── WeatherService atual / equivalente

    Open-Meteo Marine
      └── serviço marítimo atual / equivalente

Acima das fontes atmosféricas deve existir um coordenador pequeno, responsável por
escolher a fonte primária e aplicar a política de freshness/fallback sem fundir
semanticamente observação e previsão.

Os nomes concretos das classes podem ser ajustados no plano de implementação para
seguir as convenções do projeto. A separação de responsabilidades desta seção é
obrigatória.

## 6. Coordenação da sessão WebPilot

### 6.1 Provider de sessão e responsável concreto pelo login

O coordenador de autenticação não conhece Selenium, Controller, Tk nem WebDriver. Ele depende de um
contrato pequeno, conceitualmente `WebPilotSessionProvider`, capaz de solicitar aquisição/renovação
de uma sessão.

Na implementação Desktop desta SPEC, o provider concreto usa o fluxo Selenium já existente:

    WebPilotSessionProvider
              │
              └── DesktopSeleniumSessionProvider
                        │
                        └── BrowserSession / Selenium

`BrowserSession`/Selenium continua sendo o mecanismo concreto que sabe:

- abrir/validar a sessão;
- autenticar;
- renovar a sessão;
- obter os cookies autenticados.

A autenticação inicial do HTTP acompanha a autenticação normal do Desktop: quando Selenium confirma
uma sessão válida, a sessão é exportada e publicada no coordenador. Não existe um segundo login HTTP
paralelo apenas para os consumidores.

Os consumidores HTTP não abrem navegador, não manipulam Tk e não executam login.

A abstração do provider é obrigatória porque o futuro Cloud poderá obter sessões por outro mecanismo
sem alterar `WebPilotAuthCoordinator` ou `WebPilotHttpClient`.

### 6.2 Estados conceituais

O coordenador de sessão deve suportar pelo menos:

    authenticated
    recovering
    unavailable

O estado interno pode possuir outros detalhes desde que esses significados sejam
preservados.

### 6.3 Geração da sessão

Cada publicação de uma sessão autenticada válida deve possuir uma geração monotônica
interna:

    generation 1
    generation 2
    generation 3
    ...

A geração permite a um consumidor saber que a requisição que falhou usou uma sessão
antiga e que uma recuperação já publicou cookies mais novos.

A geração é interna ao processo/realm autenticado; não pertence ao MobileSnapshot.

Cada `SessionLease` também deve preservar `expires_at` quando os cookies exportados fornecerem
expiração explícita. Para esta SPEC:

- `expires_at` é opcional;
- quando houver múltiplos cookies utilizáveis com expiração explícita, usar uma estimativa
  conservadora baseada na expiração mais próxima;
- ausência de `expiry` produz `expires_at=None`;
- a data é metadado de observabilidade/renovação, não prova de validade;
- uma resposta semanticamente identificada como login invalida a sessão mesmo antes de
  `expires_at`;
- estar antes de `expires_at` nunca transforma uma resposta de login em sessão válida.

### 6.4 Recuperação única

Quando um consumidor detectar `SESSION_EXPIRED`:

1. sinaliza a expiração ao coordenador;
2. se não houver recuperação em andamento, solicita uma única recuperação ao `WebPilotSessionProvider`;
3. no Desktop atual, o provider delega ao fluxo Selenium existente, sem abrir autenticação paralela;
4. se outra recuperação já estiver em andamento, aguarda/acompanha o mesmo resultado;
5. após sucesso, a nova sessão/cookies é publicada com nova geração e novo `expires_at` quando disponível;
6. o consumidor pode repetir a operação uma vez;
7. se a repetição também indicar sessão expirada, o ciclo termina como falha.

Clima e shadow detectando expiração simultaneamente não podem iniciar logins concorrentes.

### 6.5 Renovação reativa

Não haverá relogin periódico baseado apenas em timer.

A renovação deve ocorrer por evidência real de sessão inválida/expirada ou por validação
real do mecanismo de sessão já existente.

Expiração de sessão é parte normal do ciclo de vida do programa e não deve ser tratada
como falha fatal.

### 6.6 Concorrência

Recuperação, espera de sessão e requests HTTP não podem bloquear a Tk main thread.

Nenhum consumidor pode depender de polling ocupado/busy wait na UI.

### 6.7 Preparação para federação futura do realm WebPilot

Nesta SPEC existe apenas um provider concreto local por processo Desktop. Não implementar broker
multi-Desktop, transporte de sessão para Cloud nem armazenamento remoto de cookies.

Mesmo assim, a fronteira deve preservar a separação necessária para a SPEC 027:

    WebPilotAuthRealm
          │
          ├── SessionProvider A
          ├── SessionProvider B
          └── futuro provider Cloud nativo, se necessário
                    ↓
             WebPilotAuthCoordinator
                    ↓
               SessionLease

O objetivo futuro é permitir que qualquer Desktop autorizado no mesmo realm WebPilot forneça uma
sessão mais nova para continuidade Cloud. Isso não significa compartilhar device_id nem gestão
Mobile entre Desktops; compartilha-se apenas a capacidade autenticada de consultar a mesma origem.

A premissa operacional atual é que as contas WebPilot usadas pelos operadores possuem escopo
equivalente no sistema. A SPEC 027 deverá validar essa premissa e impedir federação automática entre
providers com permissões divergentes caso isso mude.

## 7. WebPilotHttpClient

### 7.1 Responsabilidades

O cliente HTTP deve:

- usar a sessão/cookies publicados pelo coordenador WebPilot;
- conhecer os endpoints WebPilot necessários;
- possuir timeout explícito;
- reconhecer redirects/login;
- reconhecer HTML de login retornado com HTTP 200;
- classificar falhas de transporte;
- nunca interpretar semântica meteorológica ou de manobras;
- nunca abrir UI;
- nunca manipular Tk.

### 7.2 Biblioteca

A implementação deve usar a biblioteca padrão Python, preferencialmente `urllib`.
Não adicionar `requests` ou `httpx` ao Desktop apenas para este fluxo.

### 7.3 Estados de transporte

O transporte deve distinguir, no mínimo:

    OK
    SESSION_EXPIRED
    TIMEOUT
    HTTP_ERROR

HTML inesperado, grid ausente e conteúdo meteorológico inválido são erros de
conteúdo/parser e não devem ser confundidos com estado de transporte.

### 7.4 Detecção de login

A classificação deve reutilizar o conhecimento já existente no projeto, incluindo
`WEBPILOT_LOGIN_PATH` e os sinais usados por `BrowserSession`, em vez de duplicar
regras arbitrárias por consumidor.

### 7.5 Segurança

O cliente e o coordenador nunca devem:

- registrar cookies em log;
- incluir cookies em exceptions;
- incluir headers de autenticação em logs;
- gravar HTML autenticado bruto em fixtures;
- enviar cookies para API/PWA;
- incluir credenciais em métricas shadow.

## 8. Modelo meteorológico observado

### 8.1 Separação de domínio

Não forçar WebPilot observado dentro do `DadosTempo` atual se isso apagar a diferença
entre observação física e modelo/previsão.

Criar um modelo observado próprio, conceitualmente `ObservedWeather` ou equivalente.

### 8.2 Campos

O modelo deve suportar pelo menos:

    observed_at
    consulted_at
    wind_direction_deg
    wind_direction_cardinal
    wind_speed_current_kn
    wind_speed_mean_kn
    wind_speed_max_kn
    air_temperature_c
    apparent_temperature_c
    humidity_pct
    pressure_hpa
    pressure_6h_hpa
    precipitation

`observed_at` representa o timestamp declarado pela estação.

`consulted_at` representa quando o Desktop consultou/processou a página.

A idade mostrada ao usuário deve ser derivada de `observed_at`, nunca de
`consulted_at`.

### 8.3 Campos obrigatórios e opcionais

`observed_at` é obrigatório para uma leitura WebPilot ser considerada válida.

Os demais campos são opcionais individualmente. Campo ausente, vazio ou inválido deve
virar `None`/null, nunca zero.

A ausência de um campo opcional não invalida toda a observação.

## 9. WebPilotWeatherParser

### 9.1 Fonte de parsing

O parser deve receber HTML e não conhecer:

- HTTP;
- cookies;
- Selenium;
- Tk;
- API;
- PWA.

### 9.2 Estratégia

O parser deve localizar `#lblDados` e interpretar rótulos semanticamente.

Não depender de:

- coordenadas;
- posição visual;
- CSS específico;
- número fixo da linha;
- ordem imutável de todos os campos.

A ausência de `#lblDados` é conteúdo inválido.

A ausência ou impossibilidade de interpretar `observed_at` é conteúdo inválido.

### 9.3 Números PT-BR

O parser deve normalizar corretamente valores como:

    20,53    -> 20.53
    1.008,64 -> 1008.64

Unidades conhecidas devem ser removidas/interpretadas sem converter texto inválido em zero.

### 9.4 Direção do vento

Quando disponíveis, preservar:

- graus normalizados;
- cardinal textual informado/normalizado.

Não derivar um valor inventado quando a fonte não fornecer informação suficiente.

## 10. Cadência e freshness WebPilot

### 10.1 Evidência observada

A página faz refresh visual aproximadamente a cada minuto, mas observações reais
mostraram novos `observed_at` aproximadamente a cada 15 minutos.

Refresh da página não equivale a nova medição.

### 10.2 Polling

Após a autenticação inicial estar disponível:

1. fazer uma consulta meteorológica inicial imediatamente;
2. depois, não consultar WebPilot weather mais frequentemente que a cadência de 15 minutos,
   salvo ação de recuperação/teste explicitamente controlada;
3. não gerar novo estado/snapshot meteorológico apenas porque o GET ocorreu;
4. tratar `observed_at` como identidade temporal da observação.

Open-Meteo mantém sua cadência independente atual, aproximadamente 10 minutos.

### 10.3 Ciclo problemático

Para a fonte WebPilot, um ciclo é problemático quando ocorrer, por exemplo:

- timeout;
- erro HTTP;
- sessão que não se recupera naquele ciclo;
- `#lblDados` ausente;
- parser inválido;
- `observed_at` ausente/inválido;
- mesmo `observed_at` repetido quando já era esperada nova observação.

A classificação final deve ser baseada no comportamento observado e testável, não em
simples idade do horário do GET.

## 11. Política de cache e fallback atmosférico

### 11.1 Último valor válido

O Desktop mantém em memória o último valor WebPilot válido.

Uma falha transitória não transforma campos em zero nem apaga imediatamente o último
valor útil.

### 11.2 Primeiro ciclo problemático consecutivo

Se já houver uma leitura WebPilot válida em memória:

- manter o último valor WebPilot;
- marcar o estado como `stale`;
- ainda não trocar a fonte primária para Open-Meteo.

### 11.3 Segundo ciclo problemático consecutivo

No segundo ciclo problemático consecutivo:

- WebPilot deixa de ser a fonte atmosférica primária;
- Open-Meteo Forecast passa a ser `primary` em modo `fallback`.

### 11.4 Startup sem WebPilot válido

Se a primeira tentativa WebPilot falhar e ainda não houver leitura válida em memória:

- não esperar dois ciclos;
- usar Open-Meteo como fallback imediatamente, se disponível.

### 11.5 Recuperação

A primeira leitura WebPilot válida com novo `observed_at` após o fallback:

- encerra a sequência problemática;
- restaura WebPilot como fonte atmosférica primária;
- volta ao modo observado.

### 11.6 Falha do Open-Meteo durante fallback

Se o sistema já estiver em fallback Open-Meteo e Open-Meteo falhar:

- não ressuscitar silenciosamente um WebPilot antigo apenas porque o fallback falhou;
- manter o último Open-Meteo como `stale` quando existir;
- usar `unavailable` quando não existir valor válido apresentável.

## 12. Hierarquia das fontes meteorológicas

### 12.1 WebPilot — Estação Pecém

Fonte prioritária para condições atmosféricas observadas:

- vento atual;
- vento médio;
- vento máximo;
- direção;
- temperatura;
- sensação térmica;
- umidade;
- pressão;
- precipitação quando utilizável.

### 12.2 Open-Meteo Forecast

Permanece responsável por:

- previsão/modelo;
- fallback atmosférico;
- campos complementares não pertencentes à observação WebPilot.

Quando WebPilot for primário, Open-Meteo não pode preencher silenciosamente um campo
WebPilot ausente e fazê-lo parecer parte da estação.

Campos complementares devem permanecer em bloco/fonte identificável.

### 12.3 Open-Meteo Marine

Continua responsável por condições marítimas como:

- ondas;
- swell/mar de fundo;
- período;
- direção de ondas;
- corrente quando disponível no contrato atual;
- temperatura da superfície do mar;
- demais métricas marítimas atuais suportadas.

Esta SPEC não remove nem substitui Open-Meteo Marine.

## 13. Estados de disponibilidade

Cada bloco meteorológico relevante deve suportar explicitamente:

    fresh
    stale
    unavailable

Semântica:

- `fresh`: existe valor válido e atual segundo a política do Desktop;
- `stale`: existe último valor válido, mas ele não é mais considerado atual;
- `unavailable`: não existe valor válido que possa ser apresentado.

`unavailable` deve ser um estado discriminado, não um objeto preenchido artificialmente
com dezenas de campos null.

Exemplo conceitual:

    {
      "status": "unavailable"
    }

Quando houver dados, fonte, modo e payload devem ser coerentes com o estado.

O Desktop calcula freshness. API e PWA não devem inferir freshness novamente usando
seu próprio relógio.

## 14. WeatherCoordinator

Deve existir uma camada pequena acima dos serviços meteorológicos para:

- observar o estado WebPilot;
- contar ciclos problemáticos consecutivos;
- decidir WebPilot observado × Open-Meteo fallback;
- restaurar WebPilot quando houver nova observação válida;
- compor apenas blocos explicitamente separados por fonte;
- expor estado coerente ao Desktop e MobileSnapshot.

Ela não deve:

- fazer parsing HTML;
- executar HTTP diretamente;
- fazer login;
- manipular Tk;
- fundir silenciosamente campos de fontes diferentes.

## 15. UX do Desktop

### 15.1 HUD compacto

O HUD atual continua compacto e passa a refletir a fonte atmosférica ativa.

Com WebPilot primário, priorizar visualmente métricas como:

- vento atual;
- direção;
- vento médio;
- vento máximo;
- temperatura.

Não é obrigatório exibir todas as métricas observadas simultaneamente no HUD.

### 15.2 Tooltip/detalhamento

O detalhamento deve expor o conjunto mais completo e identificar as fontes.

Exemplo conceitual:

    Estação Pecém · WebPilot
    Observado em ...
    Vento atual
    Vento médio
    Vento máximo
    Direção
    Temperatura
    Sensação térmica
    Umidade
    Pressão
    Precipitação

    Complementar · Open-Meteo
    ...

    Mar · Open-Meteo Marine
    ...

### 15.3 Fallback

Quando Open-Meteo for o fallback primário, a UI deve usar os conceitos reais dessa
fonte. Não renomear `rajada` como se fosse `vento máximo da estação`.

### 15.4 Stale/unavailable

O usuário deve conseguir distinguir dados atuais, desatualizados e indisponíveis sem
que o HUD se torne excessivamente carregado.

## 16. MobileSnapshot schema v2

### 16.1 Evolução explícita

O contrato meteorológico atual não deve ser estendido silenciosamente dentro de
`schema_version: 1`.

A evolução será `schema_version: 2`.

### 16.2 Estrutura conceitual

Quando disponível:

    {
      "schema_version": 2,
      "atmosphere": {
        "primary": {
          "status": "fresh|stale",
          "source": "webpilot|open_meteo",
          "mode": "observed|fallback",
          "...": "payload da fonte"
        },
        "complementary": {
          "status": "fresh|stale",
          "source": "open_meteo",
          "...": "somente campos complementares"
        }
      },
      "marine": {
        "status": "fresh|stale",
        "source": "open_meteo",
        "...": "payload marítimo"
      }
    }

Quando um bloco não possuir qualquer valor válido:

    {
      "status": "unavailable"
    }

A modelagem concreta Pydantic/Zod deve usar união discriminada ou estrutura equivalente
que impeça combinações inválidas.

### 16.3 Segurança

O snapshot v2 nunca contém:

- cookies;
- headers WebPilot;
- token de sessão;
- credencial WebPilot;
- geração interna da sessão;
- HTML bruto.

## 17. Rollout do MobileSnapshot v2

A ordem obrigatória é:

1. API passa a aceitar e devolver v1 + v2;
2. PWA passa a interpretar v1 + v2;
3. validar deploy/API/PWA sem alterar o Desktop produtor;
4. somente depois o Desktop começa a publicar v2;
5. v1 permanece legível durante a janela de migração.

Não publicar v2 pelo Desktop antes que API e PWA estejam prontas.

O momento de remoção de suporte a v1 não pertence a esta SPEC.

## 18. UX meteorológica da PWA

A PWA deve apresentar as fontes de forma mais completa que o HUD Desktop.

Estrutura conceitual:

    Estação Pecém · observação
    WebPilot

    Complementar / previsão
    Open-Meteo

    Condições marítimas
    Open-Meteo Marine

Quando Open-Meteo estiver como fallback atmosférico, isso deve ficar explícito.

Estados `fresh`, `stale` e `unavailable` devem ser representados sem fazer a PWA
recalcular a política de freshness.

O texto existente que sugere que toda meteorologia é recebida apenas via Open-Meteo
deve ser ajustado.

## 19. Caminho HTTP de movimentações

### 19.1 Modo shadow

Adicionar configuração booleana conceitualmente equivalente a:

    ALERTAM_WEBPILOT_SHADOW_MODE

Default: `false`.

Não criar controle visual obrigatório na UI para este modo nesta SPEC.

### 19.2 Disparo

Quando habilitado, cada ciclo oficial Selenium deve poder disparar uma coleta HTTP shadow
correspondente.

O shadow:

- roda de forma assíncrona;
- não bloqueia a coleta Selenium;
- não bloqueia Tk;
- não atrasa alertas/eventos;
- falha isoladamente.

### 19.3 Extração da grid

O HTTP recebe o HTML da página de movimentações e deve extrair especificamente:

    #ASPxGridView1

Usar `html.parser.HTMLParser` ou equivalente da biblioteca padrão.

O extrator produz:

    list[list[str]]

e entrega essas linhas ao parser semântico existente:

    parse_grid_rows()

Não criar outro parser semântico de Navio/manobra.

Grid ausente ou impossível de extrair deve ser classificado como erro de conteúdo,
por exemplo `HTML_INVALID`, e não como lista vazia válida.

## 20. Comparação Selenium × HTTP

### 20.1 Nível de comparação

Comparar o resultado normalizado de domínio, não HTML bruto.

Cobrir pelo menos os campos realmente usados operacionalmente, incluindo quando
presentes no domínio atual:

- seção;
- situação/status;
- nome;
- IMO;
- POB;
- berço/bordo;
- ETA;
- ETB/ETS;
- agência;
- origem;
- rebocadores;
- demais campos consumidos pelo parser/pipeline atual.

### 20.2 Matching de identidade

A associação entre navios deve seguir esta ordem:

1. IMO válido normalizado e exatamente igual;
2. apenas entre remanescentes, nome normalizado e exatamente igual.

Não usar fuzzy matching.

Não identificar navio por:

- posição da linha;
- berço;
- POB;
- ETA;
- status/situação.

Ambiguidade deve gerar divergência `IDENTITY_AMBIGUOUS`.

### 20.3 Divergências

Tipar pelo menos:

    VESSEL_COUNT_MISMATCH
    MISSING_VESSEL
    EXTRA_VESSEL
    IDENTITY_AMBIGUOUS
    SECTION_MISMATCH
    STATUS_MISMATCH
    FIELD_MISMATCH
    HTTP_ERROR
    SESSION_EXPIRED
    HTML_INVALID
    PARSER_ERROR

Os nomes finais podem seguir o padrão de enums do projeto, preservando essas categorias.

### 20.4 Timing não é explicação automática

Uma divergência não pode ser automaticamente descartada como “diferença de timing”.

Ela permanece registrada até haver evidência suficiente para classificá-la como
explicada.

## 21. Isolamento operacional do shadow

Resultado HTTP shadow nunca pode alimentar:

- `ManeuverTracker`;
- alertas;
- histórico operacional;
- eventos de manobra;
- Web Push;
- snapshot operacional publicado;
- PWA;
- áudio/chime;
- estado oficial da coleta.

Uma falha no shadow não altera o comportamento oficial do Desktop.

## 22. Métricas e evidência local do shadow

Enquanto shadow estiver habilitado, manter persistência local sanitizada contendo:

- tempo/período observado;
- contadores acumulados;
- quantidade de ciclos comparáveis;
- quantidade de ciclos equivalentes;
- contagem por tipo de divergência;
- última comparação;
- últimas 10 divergências sanitizadas.

A persistência deve seguir a convenção de dados/logs do Desktop e ficar fora do
repositório-fonte.

Não persistir:

- cookies;
- headers;
- credenciais;
- HTML bruto autenticado;
- dumps completos de sessão.

O arquivo deve permanecer pequeno e adequado a um programa ligado 24/7.

## 23. Gate técnico de equivalência

### 23.1 Requisitos mínimos

O gate técnico inicial exige simultaneamente:

- pelo menos 24 horas de observação shadow;
- pelo menos 500 ciclos comparáveis;
- cobertura operacional mínima representativa;
- últimos 100 ciclos comparáveis consecutivos sem divergência semântica aberta.

### 23.2 Ciclo comparável

Um ciclo é comparável quando Selenium e HTTP produziram resultados de domínio válidos
suficientes para comparação.

Falhas HTTP/session/parser devem ser contabilizadas, mas não podem ser maquiadas como
ciclos equivalentes.

### 23.3 Cobertura mínima

A janela deve conter, quando disponíveis na operação:

- atracados;
- fundeados;
- previstos;
- pelo menos um POB;
- entrada/saída de navio;
- campos vazios reais.

Mudança de berço, shift e situações menos frequentes devem ser avaliados se ocorrerem
na janela. A ausência de um shift durante as 24 horas não bloqueia indefinidamente o
gate; deve ser registrada como cenário não observado.

### 23.4 Divergências abertas

Divergência semântica crítica deve ser entendida antes de ser encerrada.

Exemplos críticos:

- navio ausente/extra;
- identidade divergente/ambígua;
- seção/situação divergente;
- POB divergente;
- berço/bordo divergente;
- ETA/ETB/ETS divergente;
- diferença capaz de alterar comportamento operacional.

Diferenças puramente informativas podem ser registradas separadamente desde que não
participem do domínio operacional.

### 23.5 Aprovação humana

Atender o gate técnico não promove HTTP automaticamente.

O resultado deve ser algo equivalente a:

    Gate técnico: atendido
    Cutover: aguardando aprovação humana

A futura promoção requer análise explícita e nova SPEC/decisão.

## 24. Relatório de equivalência

Ao final da janela de evidência, produzir resumo contendo pelo menos:

- início/fim da janela;
- duração;
- ciclos totais;
- ciclos comparáveis;
- ciclos equivalentes;
- falhas técnicas;
- divergências por tipo;
- divergências críticas abertas;
- divergências explicadas;
- cobertura observada;
- cenários não observados;
- resultado dos últimos 100 ciclos;
- estado do gate técnico.

Não incluir segredos ou HTML bruto no relatório.

## 25. Estratégia de testes — TDD obrigatório

Toda implementação segue:

    RED -> GREEN -> REFACTOR

### 25.1 Sessão/autenticação

Cobrir:

- sessão autenticada publicada;
- geração aumenta após renovação;
- dois consumidores detectam expiração simultaneamente;
- somente uma recuperação é iniciada;
- consumidor reaproveita recuperação já em andamento;
- retry único após renovação;
- segunda expiração encerra o ciclo;
- falha de renovação não trava UI;
- nenhum cookie/segredo aparece em logs/exceptions.

### 25.2 HTTP

Cobrir:

- HTTP 200 autenticado;
- redirect para login;
- HTML de login com HTTP 200;
- timeout;
- 4xx/5xx;
- resposta vazia;
- sessão renovada;
- cliente não interpreta domínio.

### 25.3 Meteorologia

Usar fixture HTML sanitizada e realista com `#lblDados`.

Cobrir:

- `observed_at`;
- vírgula decimal;
- ponto de milhar;
- direção em graus/cardinal;
- vento atual;
- vento médio;
- vento máximo;
- temperatura;
- sensação;
- umidade;
- pressão atual;
- pressão 6h;
- precipitação quando utilizável;
- campo opcional ausente -> None;
- HTML parcial;
- `#lblDados` ausente;
- timestamp ausente/inválido;
- timestamp repetido;
- timestamp novo.

### 25.4 Cache/fallback

Cobrir:

- primeira leitura válida;
- primeiro ciclo problemático -> WebPilot stale preservado;
- segundo ciclo problemático -> Open-Meteo fallback;
- startup WebPilot inválido -> fallback imediato;
- recuperação no primeiro novo `observed_at`;
- Open-Meteo falha durante fallback sem ressuscitar WebPilot velho;
- `unavailable` quando não existe leitura utilizável.

### 25.5 MobileSnapshot/API/PWA

Cobrir:

- v1 continua válido;
- v2 válido;
- união discriminada de fresh/stale/unavailable;
- combinações inválidas rejeitadas;
- API aceita v1 + v2;
- PWA interpreta v1 + v2;
- PWA não recalcula freshness;
- nenhuma informação de sessão aparece no payload;
- rollout API/PWA antes do Desktop v2.

### 25.6 Desktop UX

Cobrir:

- HUD usa conceitos coerentes com WebPilot;
- fallback usa conceitos coerentes com Open-Meteo;
- tooltip identifica fontes;
- stale/unavailable são distinguíveis;
- falha meteorológica não interrompe ciclo operacional.

### 25.7 Movimentações shadow

Usar fixtures sanitizadas.

Cobrir:

- `#ASPxGridView1` extraído;
- ausência da grid -> HTML_INVALID;
- linhas HTTP alimentam `parse_grid_rows()`;
- resultado HTTP equivalente ao Selenium;
- quantidade divergente;
- navio faltante/extra;
- matching por IMO;
- fallback exato por nome;
- ambiguidade;
- field/status/section mismatch;
- erros HTTP/session/parser;
- shadow não toca `ManeuverTracker`;
- shadow não cria eventos artificiais;
- métricas não armazenam segredos/HTML bruto.

### 25.8 Concorrência

Testar que:

- HTTP/weather/shadow não executam trabalho bloqueante na Tk main thread;
- recuperação compartilhada não produz deadlock;
- falha em um consumidor não cancela consumidores independentes.

## 26. Rollout e ordem de implementação

A sequência passa a ser organizada pelo roadmap A→B→C→D. Dentro desta SPEC, a **trilha crítica para
o Cloud** é:

    Plan 1 → Plan 2 → Plan 4 → Plan 5 → gate humano → SPEC 027

O Plan 3 permanece válido, mas é uma trilha lateral de contrato Mobile e não bloqueia o início do
shadow quando Plans 1 e 2 já estiverem validados.

### Etapa A1 — Base WebPilot HTTP + autenticação coordenada (Plan 1)

- coordenador por origem WebPilot;
- publicação segura da sessão/cookies;
- `session_generation`;
- `WebPilotHttpClient`;
- estados de transporte;
- recuperação única;
- retry único;
- testes de concorrência e segurança.

### Etapa A2 — Meteorologia observada (Plan 2)

- modelo observado;
- parser `#lblDados`;
- serviço WebPilot weather;
- cache/freshness;
- `WeatherCoordinator`;
- fallback Open-Meteo;
- HUD compacto;
- tooltip/detalhamento;
- testes completos da meteorologia.

### Trilha lateral — MobileSnapshot v2 + API/PWA (Plan 3)

- contrato v2 no Desktop;
- API aceitando v1 + v2;
- PWA aceitando v1 + v2;
- UX de fontes/estados;
- deploy/validação API/PWA;
- somente depois Desktop publica v2.

Pode ocorrer após a Etapa A ou em paralelo à preparação do shadow. Não é pré-requisito conceitual
da SPEC 027, salvo se o plano Cloud posterior decidir consumir algum metadado específico do v2.

### Etapa B1 — Shadow HTTP de movimentações (Plan 4)

- extrator da grid;
- reutilização de `parse_grid_rows()`;
- collector headless reutilizando a Fundação A;
- comparator;
- matching conservador;
- divergências tipadas;
- persistência local sanitizada;
- isolamento operacional.

### Etapa B2 — Operação e evidência (Plan 5)

- habilitar shadow de forma controlada;
- coletar 24h / 500+ ciclos comparáveis;
- observar cobertura;
- analisar divergências;
- verificar últimos 100 ciclos;
- produzir relatório;
- registrar estado do gate;
- decidir humanamente se o collector está apto a ser reutilizado no Cloud.

A Etapa B2 não inclui cutover nem ativa Cloud. Se o gate for aprovado, o próximo trabalho da trilha
principal é a SPEC 027. A refatoração ampla do Desktop permanece posterior ao Cloud.

## 27. Riscos de regressão e proteções

### 27.1 Login concorrente

Risco: Weather e shadow tentarem renovar simultaneamente.

Proteção: coordenador único por origem e recuperação compartilhada.

### 27.2 Travamento da UI

Risco: request, espera ou renovação bloquearem Tk.

Proteção: todo trabalho de I/O/recuperação fora da main thread.

### 27.3 Vazamento de sessão

Risco: cookies em logs, fixture, snapshot ou relatório.

Proteção: sanitização obrigatória e testes negativos.

### 27.4 HTML meteorológico parcial

Risco: layout/campos mudarem.

Proteção: parsing por `#lblDados` + rótulos; campos opcionais viram None;
`observed_at` obrigatório.

### 27.5 Mistura de fontes

Risco: Open-Meteo preencher campo WebPilot sem transparência.

Proteção: blocos separados, source/mode explícitos e coordinator sem merge silencioso.

### 27.6 WebPilot congelado

Risco: HTTP 200 continuar retornando a mesma observação.

Proteção: `observed_at` repetido participa da política de ciclo problemático.

### 27.7 Fallback incorreto

Risco: Open-Meteo falhar e sistema voltar para WebPilot antigo.

Proteção: não ressuscitar fonte stale apenas por falha do fallback.

### 27.8 Quebra do mobile durante rollout

Risco: Desktop publicar v2 antes de consumidores estarem preparados.

Proteção: API/PWA v1+v2 primeiro; Desktop v2 depois.

### 27.9 Shadow gerar comportamento real

Risco: novo coletor alimentar pipeline por engano.

Proteção: interfaces/testes garantindo caminho somente observacional.

### 27.10 Falso matching

Risco: parear navios por posição/berço/status.

Proteção: IMO exato, depois nome exato; ambiguidade explícita; sem fuzzy.

### 27.11 Divergência descartada como timing

Risco: esconder diferença operacional real.

Proteção: toda divergência permanece aberta até evidência/explicação.

### 27.12 Crescimento de métricas

Risco: arquivo shadow crescer indefinidamente.

Proteção: contadores + última comparação + últimas 10 divergências sanitizadas.

### 27.13 Cutover prematuro

Risco: alguns ciclos verdes criarem falsa confiança.

Proteção: 24h + 500 comparáveis + cobertura + últimos 100 limpos + aprovação humana.

## 28. Arquivos/áreas que o plano deve revisar

### Desktop

Pelo menos:

- `src/alertam/settings.py`;
- `src/alertam/infrastructure/browser.py`;
- `src/alertam/infrastructure/driver_manager.py`;
- `src/alertam/infrastructure/session_store.py`;
- `src/alertam/infrastructure/weather.py`;
- `src/alertam/domain/models.py`;
- `src/alertam/domain/meteo.py`;
- `src/alertam/domain/parser.py`;
- `src/alertam/application/controller.py`;
- `src/alertam/application/mobile_snapshot.py`;
- `src/alertam/application/mobile_sync.py`;
- `src/alertam/ui/renderers.py`;
- `src/alertam/bootstrap.py`;
- fixtures/testes relacionados.

### API

Pelo menos:

- modelo/validação do MobileSnapshot;
- endpoints/repository que persistem/devolvem snapshot;
- testes de contrato v1/v2.

O plano deve confirmar os caminhos concretos antes de editar.

### PWA

Pelo menos:

- `frontend/src/api/contract.ts`;
- página/componente de meteorologia;
- componentes de status/fonte;
- testes de contrato/renderização.

## 29. Critérios de aceite da implementação

A implementação de código estará pronta para a etapa operacional quando:

- autenticação WebPilot estiver centralizada por origem;
- recuperação concorrente estiver protegida;
- retry for limitado a uma vez por operação após renovação;
- cliente HTTP estiver separado de parsing/domínio/UI;
- meteorologia WebPilot estiver parseada e exibida com fonte explícita;
- `observed_at` governar idade/freshness;
- fresh/stale/unavailable estiverem representados;
- fallback WebPilot/Open-Meteo obedecer à política desta SPEC;
- falha meteorológica não afetar navios/manobras;
- MobileSnapshot v2 possuir rollout compatível v1+v2;
- Desktop/PWA diferenciarem WebPilot, Open-Meteo e Marine;
- shadow estiver desligado por padrão;
- shadow reutilizar `parse_grid_rows()`;
- matching/divergências estiverem implementados;
- shadow não alimentar nenhum efeito operacional;
- métricas locais estiverem sanitizadas;
- suítes focadas e completas passarem;
- validações manuais necessárias de Tk/PWA forem executadas.

## 30. Critérios do gate operacional

O gate técnico de equivalência só pode ser marcado como atendido quando:

- houver pelo menos 24h de evidência;
- houver pelo menos 500 ciclos comparáveis;
- houver cobertura operacional mínima;
- divergências críticas abertas forem zero;
- os últimos 100 ciclos comparáveis consecutivos estiverem semanticamente limpos;
- relatório de equivalência estiver produzido e revisado.

Mesmo assim:

    HTTP principal = NÃO autorizado por esta SPEC

## 31. Encerramento e pós-implementação

Ao encerrar a SPEC, atualizar a documentação afetada e registrar explicitamente três
grupos.

### 31.1 Concluído nesta SPEC

- infraestrutura HTTP WebPilot;
- coordenação da sessão WebPilot;
- meteorologia observada;
- cache/fallback/freshness;
- MobileSnapshot v2 e compatibilidade;
- UX Desktop/PWA por fonte;
- shadow HTTP;
- comparator/métricas;
- gate técnico implementado.

### 31.2 Dependente de operação real

- janela de 24 horas;
- 500+ ciclos comparáveis;
- cobertura observada;
- análise das divergências;
- últimos 100 ciclos;
- relatório de equivalência;
- decisão humana sobre suficiência da evidência.

### 31.3 Trabalho futuro

Na trilha principal aprovada:

1. SPEC 027 — AlertaM Cloud, somente após gate humano da evidência shadow;
2. operação/observação da continuidade Cloud vinculada ao Desktop;
3. SPEC futura de refatoração ampla do núcleo Desktop.

Separadamente, continuam possíveis:

- SPEC de eventual cutover HTTP das movimentações no Desktop local;
- política de fallback operacional Selenium após eventual cutover;
- período de convivência pós-cutover;
- eventual redução do papel do Selenium;
- WeatherLink como redundância/segunda estação;
- outras fontes autenticadas usando coordenadores próprios.

A aprovação do shadow não obriga cutover local. O Cloud pode reutilizar o collector validado como
continuidade enquanto o Desktop local continua com Selenium como fonte preferencial.

## 32. Decisões explícitas

1. WebPilot observado é a fonte atmosférica prioritária quando saudável.
2. Open-Meteo Forecast permanece fallback e complemento identificado.
3. Open-Meteo Marine permanece fonte marítima.
4. Não existe merge silencioso de campos entre fontes.
5. `observed_at` é o relógio da observação; horário do GET não é horário da medição.
6. Freshness é calculado no Desktop.
7. `unavailable` é estado explícito, não coleção de zeros/nulls arbitrários.
8. Sessões são coordenadas por origem autenticada, não por consumidor.
9. Renovação de WebPilot é reativa, sem timer fixo de relogin.
10. Uma recuperação de sessão por vez; um retry por operação.
11. Selenium continua oficial para movimentações nesta SPEC.
12. HTTP de movimentações permanece shadow.
13. Shadow nunca gera efeitos operacionais.
14. Equivalência é medida no domínio normalizado.
15. Gate técnico não realiza cutover.
16. Qualquer promoção de HTTP exige decisão humana e SPEC posterior.
17. Plans 1 e 2 formam a Fundação A; Plans 4 e 5 formam a Prova B.
18. Plan 3 é evolução lateral do MobileSnapshot e não bloqueia o shadow nem, por si só, o Cloud.
19. Collector validado no shadow é a base obrigatória da SPEC 027; não criar implementação Cloud paralela.
20. Cloud permanece vinculado à identidade de um Desktop e não assume gestão mobile.
21. Refatoração ampla de bootstrap/controller/UI ocorre somente após a Etapa C Cloud estar operacional e observada.
22. WebPilotAuthCoordinator não depende diretamente de Selenium; depende de WebPilotSessionProvider.
23. No Desktop, a autenticação HTTP reutiliza a sessão já autenticada pelo Selenium, sem login paralelo.
24. SessionLease preserva expires_at quando disponível, mas expiry é apenas validade nominal/advisory.
25. Federação multi-Desktop por WebPilotAuthRealm é preparação para a SPEC 027 e não é implementada na SPEC 025.
26. Autenticações de fontes futuras devem possuir realms/providers próprios; não criar auth global único do AlertaM.
