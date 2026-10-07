# SPEC 027 — AlertaM Cloud: continuidade vinculada ao Desktop

**Status:** Arquitetura aprovada; implementação operacional bloqueada até o gate humano da SPEC 025; preparação isolada de infraestrutura pré-gate permitida
**Data:** 2026-10-02
**Escopo:** AlertaM Cloud + API/Supabase + integração Desktop + compatibilidade Mobile
**Pré-requisito obrigatório:** SPEC 025 Etapas A/B concluídas e gate shadow aprovado por decisão humana

## 1. Contexto

O AlertaM Mobile hoje depende indiretamente da disponibilidade do AlertaM Desktop para receber novos
estados do Porto do Pecém. O objetivo do AlertaM Cloud é eliminar a indisponibilidade causada por um
Desktop local desligado ou temporariamente offline sem retirar do Desktop a propriedade lógica do
ambiente e a administração dos aparelhos mobile.

O Cloud não é uma versão hospedada da GUI Tk. É um serviço headless de continuidade.

## 2. Decisão de produto

Cada AlertaM Cloud é vinculado a um Desktop lógico existente.

O device_id continua representando o AlertaM ao qual os celulares foram pareados. O failover entre
Desktop e Cloud não cria novo pareamento e não muda o device_id percebido pelo Mobile.

O Desktop permanece a autoridade administrativa.

## 3. Responsabilidades do Desktop

O Desktop continua responsável por:

- provisionamento da identidade device_id;
- vínculo inicial/desvínculo com o Cloud;
- pareamento QR/código;
- listagem e revogação de instalações mobile;
- preferências administrativas locais;
- apresentação de status do vínculo Cloud quando essa UX for implementada.

O Cloud não terá, no primeiro escopo, interface para controlar dispositivos mobile.

## 4. Responsabilidades do Cloud

O Cloud deve:

- executar o collector WebPilot headless validado pela SPEC 025;
- consumir/manter uma SessionLease válida do WebPilotAuthRealm associado, recebida de Desktops autorizados;
- coletar estado com a mesma semântica de domínio validada no shadow;
- manter heartbeat/health próprios;
- publicar continuidade somente para o device_id autorizado;
- assumir quando o Desktop for considerado offline/stale;
- devolver a preferência ao Desktop após retorno estável;
- respeitar o estado administrativo do `device_id`: `enabled=false` impede coleta/publicação de continuidade e nunca é tratado como simples Desktop offline;
- registrar observabilidade sanitizada.

## 5. Reutilização obrigatória do collector

A implementação Cloud não deve recriar parser, autenticação ou semântica de movimentações em uma
segunda base de código conceitualmente divergente.

A intenção é reutilizar o núcleo obtido na SPEC 025:

    WebPilotSessionProvider
           │
    WebPilotAuthCoordinator
           │
        SessionLease
           │
    WebPilot HTTP Client
           │
           ├── Weather Collector
           └── Maneuver Collector / parser normalizado

No Desktop esse núcleo foi primeiro provado como shadow. No Cloud ele passa a operar como serviço
de continuidade após o gate.

## 6. Modelo de identidade

Conceitualmente:

    DesktopIdentity
      device_id = pecem-...

    CloudBinding
      device_id = pecem-...
      cloud_binding_id
      credential_hash / referência segura
      status
      created_at
      revoked_at

Um CloudBinding pertence a um Desktop lógico e não a uma instalação mobile.

A credencial de vínculo/publicação Cloud deve ser própria, revogável e rotacionável. Ela autentica o Desktop perante o serviço AlertaM Cloud e não é uma credencial WebPilot.

## 7. Arbitragem de fonte

Toda publicação relevante deve identificar sua origem técnica:

    desktop
    cloud

A API é responsável por arbitrar qual origem está efetiva para o device_id.

Invariantes:

1. Desktop saudável tem preferência.
2. Cloud não pode sobrescrever arbitrariamente um Desktop saudável.
3. Cloud assume somente após política explícita de stale/offline.
4. Failback exige hysteresis/estabilidade.
5. Nunca há duas fontes efetivas simultâneas.
6. Flapping não pode produzir alternância rápida.
7. Pareamento mobile é independente da origem efetiva.
8. `enabled=false` tem precedência sobre failover: Cloud não assume para contornar uma desativação administrativa do device.
9. Indisponibilidade temporária ao validar autorização deve seguir política fail-closed/grace explicitamente definida; não converter erro de autorização em `enabled=true`.

Os valores exatos de timeout, número de amostras saudáveis e lease pertencem ao plano de
implementação da SPEC.

## 8. Publicação e split-brain

A implementação deverá usar mecanismo explícito de lease/epoch/fencing ou equivalente para impedir
que uma fonte atrasada volte a escrever como se ainda fosse autoridade.

Somente comparar timestamps recebidos não é suficiente.

A solução deve suportar:

- perda de rede do Desktop;
- Desktop que volta com fila atrasada;
- Cloud temporariamente degradado;
- relógios com pequeno desvio;
- reinício da API/worker sem perder a noção de autoridade.

## 9. Escopo inicial de continuidade

A primeira versão do Cloud deve priorizar continuidade de snapshot/estado.

Eventos de manobra, Push e outros efeitos com risco de duplicação não devem ser ativados no Cloud
até existir idempotência cross-source comprovada.

Isso permite entregar valor cedo:

    Desktop offline
        ↓
    Mobile continua vendo estado atualizado

sem duplicar alertas ou eventos.

## 10. Eventos e Push — evolução controlada

Quando forem incorporados ao Cloud:

- maneuver_id/identidade semântica precisa ser estável entre fontes;
- eventos devem ser idempotentes na API;
- troca de source não pode recriar o mesmo evento;
- Push deve ocorrer uma única vez;
- retorno do Desktop não pode repetir eventos produzidos durante failover.

Esta etapa exige plano e testes próprios.

## 11. WebPilotAuthRealm e federação de sessão

O Cloud v1 usa autenticação federada por origem, sem exigir que usuário/senha WebPilot permanentes
sejam cadastrados no servidor.

Conceitualmente:

    WebPilotAuthRealm: webpilot-pecem
              │
       ┌──────┼──────┐
       │      │      │
    Desktop1 Desktop2 Desktop3
       │      │      │
       └── SessionLease ──┘
              │
        Auth Broker Cloud
              │
      WebPilotAuthCoordinator
              │
       WebPilotHttpClient

Quando um operador autentica ou renova normalmente no Desktop, esse Desktop pode publicar ao Cloud
uma SessionLease mais nova do mesmo realm. O Cloud não recebe a senha do operador; recebe apenas
material de sessão temporário necessário à consulta autenticada.

Regras obrigatórias:

- somente Desktops explicitamente autorizados podem publicar sessão para um realm;
- a associação device_id↔CloudBinding continua separada do WebPilotAuthRealm;
- um realm pode atender vários CloudBindings apenas quando todos foram autorizados para aquela origem;
- cookies/sessões são segredos de alto valor e nunca aparecem em PWA, snapshots, URLs, logs ou relatórios;
- transporte Desktop→Cloud deve ser autenticado e cifrado;
- armazenamento remoto, se necessário, deve ser mínimo, protegido e limitado ao ciclo de vida da sessão;
- SessionLease preserva generation local do provider e expires_at quando disponível;
- generation de providers diferentes nunca é comparada diretamente;
- o broker autentica o publisher, rejeita replay/regressão da generation daquele mesmo provider e atribui um realm_epoch monotônico server-side a cada sessão aceita;
- received_at/realm_epoch do broker definem a ordem entre providers, sem confiar no relógio local do Desktop;
- expires_at é validade nominal/advisory; resposta semanticamente identificada como login invalida a sessão imediatamente;
- o broker prefere a sessão aceita mais recente que permaneça válida e não cria ping-pong de renovação;
- uma recuperação/seleção concorrente por realm;
- no máximo um retry HTTP por operação após mudança de generation.

A premissa atual é que as contas WebPilot dos operadores possuem permissões equivalentes. Antes de
permitir federação entre contas/providers diferentes, o Cloud deve validar ou registrar que o escopo
operacional é compatível.

Se todos os Desktops autorizados de um realm estiverem offline e a última SessionLease deixar de ser
válida, o Cloud v1 pode ficar temporariamente sem coleta WebPilot até que algum Desktop volte e
publique uma sessão válida. Esse comportamento é aceitável no primeiro escopo.

## 12. Autonomia futura e sessões simultâneas

Provider Cloud nativo, capaz de renovar autenticação sem qualquer Desktop, é evolução futura e não
pré-requisito do Cloud v1.

Antes de introduzi-lo, deve ser validado se o WebPilot permite múltiplas sessões simultâneas para a
mesma conta e como sessões de contas diferentes coexistem. Se um novo login invalidar sessão
anterior, a política precisa evitar ping-pong.

Alternativas futuras podem incluir:

- provider Cloud nativo com credencial própria;
- conta WebPilot dedicada ao Cloud;
- coordenação de uma única sessão autenticada por realm;
- outro mecanismo oficialmente suportado pelo WebPilot.

CAPTCHA/2FA/interação humana devem produzir estado operacional explícito, nunca loop de login.

## 13. UX e observabilidade

Não é requisito criar painel administrativo Cloud completo.

O mínimo de observabilidade deve permitir distinguir:

- Desktop online/offline;
- Cloud vinculado/desvinculado;
- source efetivo atual;
- última coleta Desktop;
- última coleta Cloud;
- último failover/failback;
- falha de autenticação que exige operador.

No Mobile, a origem pode ser mostrada como informação de suporte futuramente, mas não deve alterar o
fluxo de pareamento.

## 14. Infraestrutura de execução

O collector precisa de processo persistente/worker/container adequado.

Não pressupor Vercel Functions como runtime contínuo.

O plano de implementação deverá comparar opções compatíveis com:

- processo 24/7;
- secrets;
- health checks;
- restart automático;
- logs/metrics;
- custo controlado.

## 14.1 Preparação de infraestrutura pré-gate permitida

Enquanto a janela real/evidence gate da SPEC 025 estiver em execução, é permitido adiantar **somente infraestrutura não operacional** do futuro Cloud para reduzir lead time após a aprovação humana.

Essa preparação pode:

- criar um subprojeto isolado `cloud/` no monorepo `alertamaritimoAPI`;
- produzir imagem/container headless mínimo;
- expor apenas health/readiness de infraestrutura;
- validar build, deploy, restart, logs e permanência 24/7 em plataforma de teste;
- validar injeção de configuração/secrets usando apenas valores de teste sem credenciais WebPilot;
- documentar deploy e runbook da plataforma escolhida;
- usar Northflank como alvo inicial de sandbox/validação, sem torná-lo decisão irrevogável de produção.

Antes do gate humano da SPEC 025, essa preparação **não pode**:

- executar o collector WebPilot real;
- receber, armazenar ou transportar `SessionLease`, cookies ou credenciais WebPilot reais;
- criar binding operacional com `device_id`;
- publicar snapshot como `source=cloud`;
- escrever estado operacional na API/Supabase em nome do Cloud;
- implementar ou testar failover/failback real;
- assumir autoridade de source;
- copiar/reimplementar o collector Desktop apenas para antecipar C2.

A existência de um container/deploy saudável nessa fase comprova somente a **infraestrutura de execução**, nunca a aptidão do collector ou a liberação da Etapa C.

Decisão de repositório para o spike: **não criar um terceiro repositório agora**. O shell de infraestrutura nasce em `alertamaritimoAPI/cloud/`. A estratégia definitiva de compartilhamento/reuso do núcleo validado da SPEC 025 pertence ao planejamento de C2 após o gate e não autoriza cópia de código entre repos.

## 15. Dependências e gate de entrada

Implementação operacional desta SPEC permanece bloqueada até:

- SPEC 025 Plan 1 concluído;
- SPEC 025 Plan 2 concluído;
- hotfix pré-Plan 4 do `DeviceOperationalGate` integrado e exercitado pelos consumidores WebPilot HTTP do Desktop;
- shadow Plan 4 concluído usando a mesma política administrativa sem bypass;
- Evidence Gate Plan 5 executado;
- requisitos mínimos de evidência atendidos;
- divergências críticas resolvidas;
- relatório revisado;
- aprovação humana explícita para reutilizar o collector no Cloud.

MobileSnapshot v2 não é, por si só, pré-requisito para iniciar o Cloud.

## 16. Ordem interna preliminar

Após desbloqueio:

### C1 — Binding, realm e autoridade

- modelo CloudBinding;
- credencial de vínculo/publicação Cloud, distinta de qualquer credencial WebPilot;
- associação explícita do binding a um WebPilotAuthRealm autorizado;
- endpoints administrativos Desktop-only;
- revogação/rotação;
- testes de isolamento por device_id e por realm.

### C2 — Auth Broker federado + collector headless em standby

- endpoint/canal autenticado para Desktop autorizado publicar SessionLease do realm;
- identidade do publisher + generation local para anti-replay por provider;
- realm_epoch monotônico atribuído pelo broker para ordenar sessões aceitas entre providers;
- expires_at como observabilidade/advisory, nunca única validação;
- proteção dos cookies em trânsito/repouso e logs negativos;
- empacotar/reutilizar core da SPEC 025;
- executar Cloud sem assumir source efetivo;
- comparar saúde e coleta;
- simular troca Desktop1→Desktop2 como provider do mesmo realm;
- validar comportamento quando nenhum provider possui sessão válida.

### C3 — Failover/failback de snapshot

- source metadata;
- heartbeat/freshness;
- lease/fencing;
- hysteresis;
- failover;
- failback;
- testes de split-brain.

### C4 — Observabilidade e smoke

- status para suporte;
- métricas sanitizadas;
- teste Desktop online;
- teste Desktop offline;
- retorno do Desktop;
- execução prolongada.

### C5 — Eventos/Push, somente se aprovado

Plano separado e posterior ao snapshot continuity.

## 17. Não objetivos

Esta SPEC não deve:

- substituir a gestão mobile do Desktop;
- criar novo device_id para o Cloud;
- exigir novo QR quando ocorre failover;
- fazer refatoração ampla do Desktop;
- remover Selenium local automaticamente;
- promover HTTP local a fonte oficial do Desktop automaticamente;
- usar Cloud como bypass de `enabled=false` ou de autorização administrativa fail-closed;
- reescrever collector já validado;
- habilitar eventos/push duplicáveis sem idempotência cross-source;
- exigir usuário/senha WebPilot permanente no Cloud v1;
- misturar autenticação de origens distintas em um auth global único.

## 18. Relação com a refatoração do Desktop

A refatoração ampla é deliberadamente posterior ao Cloud.

O Cloud cria uma camada de continuidade operacional que reduz o risco de mudanças estruturais no
Desktop. Depois que a continuidade estiver estável, uma nova SPEC de modernização/refatoração poderá
revisar bootstrap, controller, UI/domínio e legado de forma incremental.

## 19. Critérios de aceite arquitetural

A primeira versão operacional do Cloud só pode ser considerada concluída quando:

- existe vínculo explícito Cloud↔Desktop;
- Cloud não administra celulares;
- mesmo device_id permanece válido durante failover;
- Desktop saudável é preferido;
- Cloud assume somente quando autorizado pela política;
- failback não flapa;
- split-brain é tecnicamente impedido;
- Mobile continua recebendo estado quando Desktop está offline;
- retorno do Desktop não exige re-pareamento;
- pelo menos dois providers Desktop simulados conseguem renovar/substituir a SessionLease do mesmo realm sem alterar device_id, e o broker ordena as aceitações por realm_epoch em vez de comparar generations locais;
- perda de todos os providers expõe estado de autenticação indisponível sem loop de login;
- expires_at é observado sem substituir validação semântica;
- usuário/senha WebPilot não são requisito armazenado no Cloud v1;
- credenciais/segredos de sessão não vazam;
- smoke prolongado foi documentado.

## 20. Relação com o roadmap

A sequência autoritativa é:

    A — Fundação HTTP + Weather (SPEC 025)
    B — Shadow + Evidence Gate (SPEC 025)
    C — Continuidade Cloud (SPEC 027)
    D — Refatoração ampla Desktop (SPEC futura)

Esta SPEC define C. Ela não autoriza pular A/B nem antecipar D.
