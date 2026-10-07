# Roadmap arquitetural — Fundação WebPilot → Shadow → AlertaM Cloud → Refatoração Desktop

**Status:** Estratégia aprovada e autoritativa
**Data:** 2026-10-02
**Escopo:** AlertaM Desktop + API/Supabase + AlertaM Mobile/PWA + futuro AlertaM Cloud
**Documentos vinculados:** SPEC 025, SPEC 027, SPEC 029 e obrigação administrativa da SPEC 030

## 1. Decisão central

A evolução do AlertaM seguirá quatro etapas obrigatórias, nesta ordem:

    A. Fundação HTTP + meteorologia WebPilot
                    ↓
    B. Shadow HTTP + evidência + gate humano
                    ↓
    C. AlertaM Cloud vinculado a um Desktop
                    ↓
    D. Refatoração ampla do núcleo Desktop

A ordem existe para reduzir risco operacional. O objetivo não é refatorar todo o Desktop antes de
criar o Cloud nem copiar o Selenium atual para um servidor.

## 2. Princípio de identidade

O AlertaM Mobile permanece vinculado a uma identidade lógica de Desktop (device_id).

O futuro AlertaM Cloud não cria uma identidade concorrente e não administra celulares. Ele é um
serviço de continuidade autorizado por um Desktop já provisionado.

Conceitualmente:

    Mobile
      │
      └── AlertaM lógico: device_id=pecem-...
               │
               ├── Desktop local — proprietário/administrador
               │
               └── Cloud — continuidade de estado quando o Desktop estiver offline

O Desktop continua responsável por:

- criar e possuir a identidade device_id;
- parear celulares;
- gerar QR/código temporário;
- listar/revogar instalações mobile;
- preferências e ações administrativas;
- autorizar/desautorizar o vínculo de continuidade Cloud.

O Cloud não deve possuir UI de gestão de aparelhos mobile.

## 3. Etapa A — Fundação WebPilot

Fonte normativa: SPEC 025, principalmente Plans 1 e 2.

Objetivo: extrair somente as responsabilidades necessárias para que coleta WebPilot autenticada
possa existir fora da GUI e seja reutilizável.

Entregas mínimas:

- coordenação da autenticação/sessão WebPilot;
- WebPilotHttpClient reutilizável;
- recuperação/relogin coordenados;
- parsing isolado de HTML;
- meteorologia observada WebPilot;
- freshness/cache/fallback;
- I/O fora da Tk main thread.

Nesta etapa o Selenium continua sendo a fonte oficial das movimentações.

### 3.1 O que não fazer na Etapa A

Não usar esta etapa como pretexto para refatorar amplamente:

- MainWindow;
- controller principal;
- bootstrap inteiro;
- regras históricas de manobra;
- áudio;
- notificações;
- organização geral do legado não necessária ao novo collector.

A separação aqui é funcional e dirigida por necessidade.

## 4. Etapa B — Shadow e prova operacional

Fonte normativa: SPEC 025, Plans 4 e 5.

O mesmo núcleo HTTP criado na Etapa A passa a coletar movimentações em modo shadow.

Fluxo:

    Selenium ──→ Snapshot oficial ──────┐
                                         ├── comparação no domínio normalizado
    HTTP ─────→ Snapshot shadow ─────────┘

O shadow é estritamente observador. Ele nunca:

- substitui o snapshot oficial;
- gera alerta;
- cria evento operacional;
- produz áudio;
- altera histórico;
- dispara push;
- alimenta Mobile;
- muda estado de manobra.

A evidência deve ser sanitizada e persistente.

### 4.1 Gate mínimo

Antes de liberar a Etapa C:

- pelo menos 24 horas de observação;
- pelo menos 500 ciclos comparáveis;
- cobertura mínima definida pela SPEC 025;
- últimos 100 ciclos comparáveis limpos;
- zero divergência crítica aberta;
- relatório de equivalência revisado;
- decisão humana explícita de que o coletor HTTP está apto a ser reutilizado pelo Cloud.

GateStatus=MET sozinho não inicia Cloud nem cutover.

### 4.2 Gate administrativo transversal — SPEC 030

A SPEC 030 acrescenta uma fronteira de autorização que vale para toda coleta que opere em nome de um `device_id`.

Antes do Plan 4:
- o Desktop deve possuir uma única instância reutilizável de `DeviceOperationalGate`;
- consumidores WebPilot HTTP atuais precisam respeitá-la;
- o Shadow reutiliza essa mesma instância, sem segundo status client/gate;
- `enabled=false` e `authorization_unavailable` fora do grace impedem novo GET WebPilot;
- item shadow enfileirado deve revalidar imediatamente antes do GET;
- bloqueio administrativo é skip operacional, não divergência nem falha técnica do collector.

O hotfix pré-Plan 4 que fecha o bypass atual da meteorologia WebPilot é requisito de entrada da Etapa B.

Na Etapa C, o Cloud também deverá consultar a autorização administrativa do `device_id` antes de coletar/publicar continuidade. Cloud não pode transformar Desktop desativado em fallback para contornar `enabled=false`.

## 4.3 Preparação paralela de infraestrutura Cloud — sem antecipar a Etapa C

Durante a janela operacional/evidence gate da Etapa B, é permitido executar um spike estritamente de infraestrutura para reduzir tempo de preparação da Etapa C.

Permitido antes do gate humano:

- shell headless isolado em `alertamaritimoAPI/cloud/`;
- Docker/build/deploy;
- health/readiness;
- restart automático;
- logs/observabilidade de infraestrutura;
- configuração/secrets apenas com valores de teste;
- prova de processo always-on em sandbox, inicialmente Northflank.

Continuam proibidos antes do gate humano:

- WebPilot real no Cloud;
- SessionLease/cookies reais;
- CloudBinding operacional;
- publicação `source=cloud`;
- arbitragem/failover/failback;
- qualquer efeito no Mobile ou na autoridade do Desktop.

Esse spike não altera a ordem A→B→C. Ele apenas prepara o substrato onde C poderá ser implementada se e quando a Etapa B for aprovada.

## 5. Trilha lateral — MobileSnapshot v2

O antigo Plan 3 da SPEC 025 continua válido como evolução de contrato e UX meteorológica, mas não
faz parte da trilha crítica A→B→C.

Ele pode ser executado:

- depois da Etapa A;
- em paralelo à preparação do shadow;
- ou quando a evolução do Mobile/Cloud exigir os metadados adicionais.

Regra: o Plan 3 não deve atrasar artificialmente o início do shadow se Plans 1 e 2 já estiverem
validados e o shadow não depender do schema v2.

### 5.1 Refinamento lateral concluído — SPEC 029 Tábua de maré DHN

A SPEC 029 foi implementada e integrada antes do Plan 4 por decisão operacional, sem criar dependência técnica com o Shadow.

Ela adicionou:
- dataset anual DHN 2026 do Terminal Portuário do Pecém;
- Hoje + Amanhã no Desktop e na página Tempo do PWA;
- `🌊 Maré` e `ⓘ` na linha discreta do Desktop;
- remoção do ID permanente abaixo de Modo compacto.

Restrições preservadas:
- nenhum endpoint novo de maré;
- nenhum transporte Supabase para maré;
- nenhum MobileSnapshot novo;
- nenhum acoplamento com WebPilot/Open-Meteo.

O sequenciamento atual é regido pelo gate pré-Plan 4 de 2026-10-06: hotfix do `DeviceOperationalGate`, eventuais hotfixes/UI e só então a branch Shadow.

## 6. Etapa C — AlertaM Cloud

Fonte normativa: SPEC 027.

O Cloud nasce reutilizando o collector HTTP já validado pela Etapa B. Não haverá uma segunda
implementação independente do parser/coletor WebPilot.

Responsabilidades do Cloud:

- executar o collector headless 24/7;
- manter credenciais/sessão WebPilot em ambiente seguro;
- permanecer associado a um único Desktop lógico;
- acompanhar saúde/freshness do Desktop;
- fornecer continuidade do estado quando o Desktop estiver offline;
- devolver o controle ao Desktop quando ele voltar estável;
- expor observabilidade técnica suficiente para suporte.

O primeiro escopo deve priorizar continuidade de snapshot/estado. Geração de eventos/push no Cloud
exige contrato explícito de idempotência e anti-duplicação antes de ser habilitada.

## 7. Arbitragem Desktop × Cloud

Nunca pode existir competição implícita entre duas fontes.

A API deverá conhecer a origem de cada publicação:

    source=desktop
    source=cloud

Política obrigatória:

- Desktop saudável é a fonte preferencial;
- Cloud não toma posse apenas porque publicou um snapshot mais recente por poucos segundos;
- failover ocorre somente após o Desktop ser classificado como stale/offline;
- failback exige estabilidade/histerese, evitando flapping;
- um único source é efetivo por vez para um device_id;
- a troca de source não altera o pareamento Mobile.

Os thresholds exatos pertencem ao plano da SPEC 027, mas a existência de hysteresis e proteção
contra split-brain é obrigatória.

## 8. Vínculo Desktop → Cloud

O Cloud não escolhe livremente um device_id.

O vínculo deve nascer de uma ação autenticada do Desktop/operador e produzir credencial própria de
continuidade, com escopo limitado àquele device_id.

Requisitos:

- não reutilizar DEVICE_SECRET diretamente como segredo permanente do Cloud se puder ser evitado;
- credencial de vínculo/publicação Cloud revogável e distinta da autenticação WebPilot;
- rotação independente;
- nenhum segredo Cloud em PWA, QR ou snapshot;
- Desktop pode consultar estado do vínculo;
- remover/desativar o Cloud não revoga automaticamente celulares.

### 8.1 Autenticação federada por WebPilotAuthRealm

A primeira versão do Cloud não exige armazenar usuário/senha WebPilot permanentemente no servidor.

O realm autenticado é separado da identidade dos Desktops:

    device_id 01 ─┐
    device_id 02 ─┼── usam WebPilotAuthRealm = webpilot-pecem
    device_id 03 ─┘

Qualquer Desktop autorizado naquele realm pode, ao autenticar/renovar normalmente no WebPilot,
publicar uma SessionLease mais nova para o serviço Cloud. O Cloud usa a sessão válida do realm para
coletar os mesmos dados WebPilot e atender os CloudBindings autorizados daquele realm.

Regras:

- compartilhar autenticação do realm não compartilha device_id, instalações mobile ou autoridade administrativa;
- cookies/sessões são credenciais sensíveis e exigem transporte seguro, armazenamento mínimo/protegido e ausência total em logs;
- generation é local ao provider e serve para anti-replay daquele provider; generations de Desktops diferentes não são comparáveis;
- o broker Cloud atribui realm_epoch monotônico server-side para ordenar sessões aceitas entre providers;
- expires_at do cookie ajuda a observar validade nominal e escolher/solicitar sessões mais novas;
- expires_at não garante validade server-side; resposta de login continua autoritativa;
- se todos os Desktops do realm estiverem offline e a última sessão deixar de ser válida, a coleta Cloud daquele realm pode ficar indisponível até novo Desktop autenticado publicar sessão;
- isso é aceitável no Cloud v1 e evita exigir administração manual de senha no servidor;
- provider Cloud nativo/autônomo fica como evolução futura, não pré-requisito inicial;
- se no futuro uma fonte diferente do WebPilot exigir autenticação, ela deve possuir seu próprio auth realm/provider, sem virar um auth global do AlertaM.

A hipótese operacional atual é de permissões equivalentes entre as contas WebPilot dos operadores.
A implementação Cloud deverá validar/registrar o escopo aceito antes de permitir que providers
diferentes alimentem o mesmo realm.

## 9. Etapa D — Refatoração ampla do Desktop

Somente depois de o Cloud estar operacional e observado.

Objetivo: modernizar progressivamente o núcleo legado com uma segunda infraestrutura de continuidade
já comprovada.

Candidatos:

- decomposição do bootstrap;
- redução de responsabilidades do controller;
- separação de UI e domínio;
- eliminação de caminhos Selenium redundantes quando autorizada;
- consolidação dos serviços novos;
- simplificação de estados e lifecycle;
- remoção segura de código legado coberto pela nova arquitetura.

A Etapa D deve ser incremental, com testes e sem reescrita big-bang.

## 10. Regras de não inversão

Não iniciar SPEC 027 operacional antes do gate humano da SPEC 025.

Não realizar refatoração ampla para “preparar” o Cloud antes de provar o collector shadow.

Não transformar Cloud em nova autoridade de gestão mobile.

Não acoplar WebPilotAuthCoordinator diretamente a Selenium; Selenium é apenas o provider concreto do Desktop.

Não exigir credencial WebPilot permanente no Cloud v1 se a federação de SessionLease por realm for suficiente.

Não fazer o Mobile trocar de identidade quando ocorre failover Desktop→Cloud.

Não promover HTTP local para fonte oficial do Desktop automaticamente ao aprovar o shadow.

Cloud e eventual cutover local do Selenium são decisões relacionadas, mas separadas.

## 11. Resultado arquitetural desejado

Antes:

    WebPilot → Desktop obrigatório → API → Mobile

Depois da Etapa C:

    WebPilot
       │
       ├── Desktop local (preferencial quando saudável)
       │
       └── Cloud continuity (quando Desktop offline)
                    │
                    ↓
                   API
                    ↓
                  Mobile

O usuário continua percebendo um único AlertaM lógico. A origem efetiva dos dados torna-se uma
preocupação de infraestrutura, não de pareamento.

## 12. Documentos autoritativos

- Fundação/Weather/Shadow/Gate: specs/025-webpilot-http-observed-weather-shadow-migration.md
- Continuidade Cloud: specs/027-alertam-cloud-continuity.md
- Tábua DHN/UX lateral: specs/029-tabua-mare-dhn-desktop-pwa.md
- Planos atuais da SPEC 025: docs/superpowers/plans/2026-09-29-spec025-*.md

Este roadmap prevalece sobre brainstorms/handoffs anteriores quando houver conflito de ordem,
identidade ou papel do Cloud.
