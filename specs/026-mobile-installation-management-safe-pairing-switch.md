# SPEC 026 — Gestão de aparelhos mobile, revogação e troca segura de pareamento

**Status:** Planos 1–3 implementados e validados localmente; migrations/deploy/smoke real pendentes
**Data:** 2026-09-30  
**Escopo:** AlertaM Desktop + API FastAPI/Supabase + PWA React/Vite  
**Repositórios:** `/home/ciro/dev/prog/alertamaritimo` + `/home/ciro/dev/prog/alertamaritimoAPI`  
**Dependências:** SPEC 019 + SPEC 020 + SPEC 021 + SPEC 023

## 1. Contexto

O AlertaM já possui pareamento mobile por QR Code, sessão PWA por cookie HttpOnly e identidade
individual de instalação via `installation_id`. Um mesmo AlertaM Desktop pode atender vários
celulares/tablets, e preferências de Push/Ship Tracking são individuais por instalação.

Hoje existem duas identidades distintas:

- `devices.device_id`: identifica uma instância do AlertaM Desktop;
- `mobile_installations.installation_id`: identifica um navegador/PWA ligado a esse Desktop.

A tabela `mobile_installations` já mantém `active`, `created_at`, `last_seen_at`,
`revoked_at` e `updated_at`. A revogação de uma instalação também encerra seus acompanhamentos,
e a rotação de `VIEW_SECRET` revoga o acesso global daquele Desktop.

Faltam, porém, duas capacidades operacionais importantes:

1. o Desktop não possui uma tela para identificar e revogar aparelhos individualmente;
2. ler um QR de outro Desktop enquanto a PWA já está pareada não executa uma troca segura.

O segundo problema foi reproduzido em aparelho real: a PWA permaneceu ligada ao Desktop anterior
até o usuário usar manualmente **Esquecer este aparelho** e escanear novamente o novo QR.

## 2. Objetivos

1. Permitir que o Desktop liste os aparelhos mobile associados ao próprio `device_id`.
2. Permitir revogação individual, sem afetar os demais aparelhos.
3. Identificar cada instalação por plataforma simples + código curto humano.
4. Mostrar a mesma identificação na PWA em Config.
5. Manter revogados visíveis no gerenciamento por 30 dias.
6. Preservar a rotação global como ação de segurança: **Revogar todos e gerar novo QR**.
7. Corrigir o fluxo de leitura de um segundo QR sem destruir antecipadamente o pareamento atual.
8. Pedir confirmação explícita ao trocar entre dois `device_id` diferentes.
9. Nunca reativar uma identidade de instalação que já foi revogada.
10. Manter Push e Ship Tracking coerentes com a instalação efetivamente ativa.

## 3. Não objetivos

Esta SPEC não deve:

- identificar modelo exato do telefone;
- coletar serial, IMEI, fingerprint ou identificadores invasivos;
- criar nomes amigáveis editáveis para aparelhos;
- revogar automaticamente aparelhos por tempo de inatividade;
- migrar acompanhamentos de navios entre Desktops;
- tornar o código curto um segredo ou mecanismo de autenticação;
- permitir que a PWA liste outros aparelhos conectados;
- apagar imediatamente do banco todo registro revogado;
- criar uma segunda identidade de aparelho concorrente ao `installation_id`;
- permitir que um `installation_id` migre entre `device_id` diferentes.

## 4. Decisões de produto aprovadas

### 4.1 Troca de Desktop exige confirmação

Se uma PWA pareada com o Desktop A ler um QR pertencente ao Desktop B, o QR novo deve ser
validado antes de qualquer alteração e a interface deve perguntar se o usuário deseja trocar.

Cancelar mantém A integralmente ativo.

### 4.2 Identificação humana simples

Cada instalação possui:

- plataforma: `ios`, `android` ou `other`;
- código curto permanente, por exemplo `K7M4Q2`.

A UI traduz:

- `ios` → **iPhone/iPad**;
- `android` → **Android**;
- `other` → **Outro aparelho**.

Não haverá nome amigável no escopo desta SPEC.

### 4.3 Histórico de revogados

Instalações revogadas aparecem na área **Revogados** por 30 dias a partir de `revoked_at`.

Depois desse período deixam de ser retornadas para a interface administrativa. A retenção visual
de 30 dias não exige exclusão física imediata das linhas no banco.

### 4.4 Sem revogação automática por inatividade

`last_seen_at` é informativo. Um aparelho pode permanecer autorizado mesmo após longos períodos
sem uso, até que o usuário o revogue, use **Esquecer este aparelho** ou ocorra rotação global.

### 4.5 Ação global explícita

O atual **Gerar novo acesso** passa a ser apresentado como:

**Revogar todos e gerar novo QR**

A confirmação deve informar quantos aparelhos ativos serão desconectados.

## 5. Identidade e modelo de dados

### 5.1 `installation_id` continua canônico

`installation_id` permanece UUID e continua sendo a identidade técnica usada por:

- sessão mobile;
- Push;
- Ship Tracking;
- deliveries;
- revogação.

O código curto é apenas uma representação humana.

### 5.2 Novos metadados em `mobile_installations`

Adicionar:

```text
platform      text
display_code  text
```

`platform` deve ser normalizado para `ios | android | other`.

`display_code` deve possuir 6 caracteres e usar alfabeto sem símbolos visualmente ambíguos:

```text
ABCDEFGHJKLMNPQRSTUVWXYZ23456789
```

O código deve ser gerado no servidor, nunca pelo navegador, e protegido por constraint/índice
de unicidade. Em colisão, o servidor gera outro código.

`display_code` não participa de autenticação e pode ser exibido livremente na UI.

### 5.3 Instalações existentes

A migration deve preencher `display_code` para todas as instalações já existentes.

Instalações antigas sem plataforma conhecida iniciam como `other`. A plataforma pode ser
atualizada posteriormente por uma PWA nova autenticada, sem alterar `installation_id` ou código.

### 5.4 Instalação revogada não ressuscita

A operação hoje equivalente a `ensure_mobile_installation` deve mudar de semântica:

- inexistente + credencial válida → cria instalação;
- existente, mesmo Desktop e ativa → reutiliza/atualiza atividade;
- existente e revogada → não reativa;
- existente em outro Desktop → rejeita.

Se um aparelho revogado parear novamente, deve nascer um novo `installation_id` e,
consequentemente, um novo `display_code`.

## 6. Plataforma do aparelho

A detecção é deliberadamente grosseira e apenas de apresentação.

A PWA pode usar sinais do navegador para classificar:

- iPhone/iPad/iPod;
- Android;
- fallback `other`.

Para iPadOS que se apresenta como macOS, pode-se combinar plataforma com capacidade de toque.

O servidor nunca confia em `platform` para autorização.

A criação normal de sessão deve aceitar `platform` como campo opcional. Clientes antigos que não
enviam esse campo continuam válidos e são registrados como `other`.

## 7. Atividade e `last_seen_at`

A data exibida como **Última atividade** deve refletir uso recente da PWA, e não apenas a data
em que a sessão foi criada.

Para evitar escrita a cada polling de 30 segundos, a PWA deve enviar heartbeat leve enquanto
estiver ativa/visível, aproximadamente a cada 5 minutos e também ao iniciar uma sessão visível.

Contrato conceitual:

```text
POST /api/v1/mobile/session/heartbeat
Cookie: sessão mobile atual
body: { "platform": "ios | android | other" }
```

O servidor atualiza `mobile_installations.last_seen_at` de forma idempotente/throttled.

O heartbeat também pode atualizar `platform` quando uma instalação antiga ainda estiver como
`other`.

Falha de heartbeat nunca derruba a PWA nem invalida o pareamento.

## 8. API administrativa do Desktop

Toda operação administrativa é autenticada pela credencial do Desktop (`DEVICE_SECRET`).
Sessão PWA e `VIEW_SECRET` não podem acessar essa superfície.

### 8.1 Listar instalações

Contrato conceitual:

```text
GET /api/v1/devices/{device_id}/mobile-installations
Authorization: Device <DEVICE_SECRET>
```

Resposta:

```json
{
  "active_count": 2,
  "active": [],
  "recently_revoked": []
}
```

Cada item expõe somente:

- `installation_id`;
- `display_code`;
- `platform`;
- `active`;
- `created_at`;
- `last_seen_at`;
- `revoked_at`.

`recently_revoked` inclui somente itens com `revoked_at >= now - 30 dias`.

O backend sempre restringe a consulta ao `device_id` autenticado.

### 8.2 Revogar uma instalação

Contrato conceitual:

```text
DELETE /api/v1/devices/{device_id}/mobile-installations/{installation_id}
Authorization: Device <DEVICE_SECRET>
```

A operação deve ser idempotente para uma instalação pertencente ao próprio Desktop.
Instalação inexistente ou pertencente a outro `device_id` não pode ser revelada como válida.

Revogar significa, numa única operação lógica:

- `mobile_installations.active=false`;
- preencher `revoked_at`;
- encerrar `tracked_vessels` ativos daquela instalação;
- desativar/limpar a `push_installation` correspondente;
- impedir resolução futura da sessão daquela instalação.

## 9. Gestão no AlertaM Desktop

### 9.1 Janela Conectar Celular permanece limpa

A janela existente continua focada em conexão:

- QR Code;
- link/copiar;
- estado do acesso;
- contador **Aparelhos conectados: N**;
- botão **Gerenciar aparelhos**;
- ação **Revogar todos e gerar novo QR**.

A lista de instalações não aparece diretamente nessa janela.

Se a consulta administrativa falhar, o QR continua funcionando. O contador pode mostrar
**Aparelhos conectados: indisponível**.

### 9.2 Janela Gerenciar aparelhos

Abrir uma janela separada com duas abas:

- **Ativos (N)**;
- **Revogados (N)**.

Cada ativo mostra:

- indicador visual ativo;
- plataforma + código;
- última atividade;
- data de conexão quando útil;
- botão **Revogar**.

Os revogados mostram:

- plataforma + código;
- data de revogação;
- última atividade anterior.

Não existe botão **Reativar**.

### 9.3 Confirmação individual

Antes de revogar:

```text
Revogar iPhone/iPad · K7M4Q2?

Este aparelho perderá acesso ao AlertaM.
Suas notificações e acompanhamentos serão encerrados.
```

Falha de rede não remove otimisticamente o item da lista.

### 9.4 Rede fora da Tk main thread

Listagem e revogação devem seguir o padrão assíncrono existente do Desktop.

A Tk main thread recebe apenas mensagens/resultados já produzidos pelo serviço de infraestrutura.

## 10. PWA Config.

A página Config. deve separar claramente a identidade do telefone da identidade do Desktop.

Exemplo:

```text
Este aparelho
iPhone/iPad · K7M4Q2

AlertaM conectado
pecem-55ee08ee
```

O UUID completo de `installation_id` não deve ser exibido na interface comum.

Os contratos de criação/recuperação de sessão devem estender a resposta atual, preservando os
campos existentes e acrescentando `display_code` e `platform`. Assim a própria sessão autenticada
é a fonte canônica da identidade exibida em Config.

Esses metadados podem ser persistidos localmente para permitir exibição consistente mesmo durante
indisponibilidade temporária da API.

## 11. Validação de um novo QR sem efeitos colaterais

Ler um QR não deve criar instalação, trocar cookie ou revogar o pareamento atual antes da
confirmação do usuário.

Criar endpoint conceitual:

```text
POST /api/v1/mobile/pairing/validate
Authorization: Bearer <VIEW_SECRET>
body: { "device_id": "..." }
```

Esse endpoint:

- valida `device_id + VIEW_SECRET`;
- retorna o `device_id` validado e somente metadados mínimos necessários;
- não cria `mobile_installation`;
- não altera sessão;
- não altera Push;
- não altera Ship Tracking.

Falha de validação mantém o pareamento atual intacto.

## 12. QR pertencente ao mesmo Desktop

Se o QR validado possui o mesmo `device_id` do pareamento atual, não mostrar diálogo
**Trocar AlertaM**.

Há dois casos:

1. sessão/instalação atual ainda é válida: renovar/sincronizar o acesso sem criar nova identidade;
2. instalação anterior foi revogada: ela não pode ser reativada; um novo pareamento cria
   novo `installation_id` e novo código.

Escanear novamente o mesmo QR válido não deve multiplicar instalações ativas.

## 13. QR pertencente a outro Desktop

Fluxo obrigatório:

```text
Desktop A ativo
  ↓
ler QR de B
  ↓
validar B sem efeitos colaterais
  ↓
A != B
  ↓
pedir confirmação
  ↓
Cancelar → permanecer em A
Confirmar → executar troca segura
```

Mensagem sugerida:

```text
Você já está conectado a outro AlertaM.

Atual: pecem-antigo
Novo:   pecem-novo

[ Cancelar ]  [ Trocar AlertaM ]
```

## 14. Troca segura de sessão

Criar contrato dedicado, conceitualmente:

```text
POST /api/v1/mobile/session/switch
Cookie: sessão atual A
Authorization: Bearer <VIEW_SECRET de B>
```

Body inclui:

- `device_id` de B;
- novo `installation_id`;
- `platform`;
- `switch_id` UUID para idempotência/reconciliação.

A operação inicial exige sessão A válida e credencial B válida.

Na mesma transação lógica:

1. validar A;
2. validar B;
3. criar instalação B;
4. revogar instalação A;
5. encerrar trackings de A;
6. desativar Push de A;
7. registrar conclusão do `switch_id`;
8. emitir sessão/cookie de B.

O registro de `switch_id` permite que um retry após resposta de rede ambígua reconcilie a
operação sem criar várias instalações nem exigir que a instalação A ainda esteja ativa.

O backend deve rejeitar reutilização do mesmo `switch_id` com parâmetros diferentes.

## 15. Estado candidato na PWA

Durante a troca, a PWA mantém separadamente:

- pareamento ativo A;
- candidato B;
- novo `installation_id`;
- `switch_id`.

O candidato nunca substitui o estado ativo antes da resposta de sucesso/reconciliação.

Após sucesso:

- salvar pairing B;
- salvar installation B;
- atualizar metadados de Config.;
- limpar estado candidato.

Após cancelamento:

- descartar candidato;
- manter A.

Após erro temporário:

- manter A;
- permitir tentar novamente.

## 16. Push durante a troca

Acompanhamentos de navio não migram de A para B.

A preferência do usuário por notificações pode ser reaplicada em B:

- permissão do navegador permanece como está;
- Push de A é desativado pela revogação;
- após troca concluída, a PWA tenta registrar a subscription existente para B;
- as categorias selecionadas são reaplicadas para a nova instalação.

Falha nessa reativação não desfaz a troca de Desktop.

A Config. deve permitir que o usuário reative notificações manualmente se necessário.

## 17. Acesso revogado observado pela PWA

Quando uma instalação é revogada individualmente ou pela rotação global, chamadas autenticadas
subsequentes devem falhar como acesso inválido.

A PWA deve limpar o estado local que não pode mais ser reutilizado e mostrar:

```text
Acesso revogado

Este aparelho não possui mais acesso ao AlertaM.
Escaneie um novo QR Code para conectar novamente.
```

Ao novo pareamento, gerar novo `installation_id`; nunca reaproveitar o revogado.

## 18. Revogar todos e gerar novo QR

A ação global continua baseada na rotação de `VIEW_SECRET`.

A confirmação no Desktop deve informar o número atual de instalações ativas.

Ao confirmar com sucesso:

- todas as `mobile_installations` daquele Desktop ficam revogadas;
- todos os trackings dessas instalações são encerrados;
- todas as instalações Push correspondentes ficam desativadas;
- o Desktop recebe/persiste o novo `VIEW_SECRET`;
- um novo QR é apresentado;
- a lista administrativa é atualizada.

Essa ação não deve depender de a tela Gerenciar aparelhos estar aberta.

## 19. Segurança

Princípios obrigatórios:

1. `display_code` nunca autentica nada.
2. `platform` nunca decide autorização.
3. PWA não lista outras instalações.
4. Endpoint administrativo exige autenticação de Desktop.
5. `device_id` do path nunca autoriza por si só.
6. Um Desktop não pode listar/revogar instalação de outro Desktop.
7. Um `installation_id` nunca muda de `device_id`.
8. Uma instalação revogada nunca volta a ativa.
9. QR candidato não altera estado antes de confirmação.
10. `VIEW_SECRET` não deve aparecer em logs.
11. `switch_id` deve ser imprevisível e não reutilizável com payload divergente.
12. Cookies mobile permanecem HttpOnly, Secure em produção e SameSite conforme contrato atual.
## 20. Compatibilidade e rollout

A evolução deve ser implantada de forma compatível.

Ordem recomendada:

1. migration de banco;
2. API capaz de aceitar clientes antigos;
3. deploy API;
4. deploy PWA com plataforma, Config. e troca segura;
5. Desktop com contador e Gerenciar aparelhos;
6. smoke em aparelhos reais.

Enquanto houver PWA antiga em uso:

- ausência de `platform` deve ser aceita como `other`;
- resposta de sessão pode adicionar campos sem remover os existentes;
- instalações antigas recebem `display_code` via migration;
- contratos atuais de snapshot/eventos não mudam.

## 21. Testes API

Cobertura mínima unitária/integração:

- criação de código curto válido;
- retry em colisão de código;
- backfill de instalação existente;
- plataforma normalizada;
- instalação revogada não reativa;
- instalação não pode trocar de `device_id`;
- listagem retorna somente o Desktop autenticado;
- ativos e revogados recentes separados;
- revogado com mais de 30 dias não aparece;
- inatividade não revoga;
- DELETE individual é idempotente;
- DELETE encerra tracking;
- DELETE desativa Push;
- rotação global continua revogando tudo;
- pairing validate é side-effect free;
- switch A→B revoga A e cria B;
- `switch_id` repetido com mesmo payload reconcilia;
- `switch_id` repetido com payload diferente rejeita;
- falha transacional não deixa A revogado sem B válido;
- sessão de instalação revogada é rejeitada.

## 22. Testes PWA

Cobertura mínima:

- Config. mostra plataforma + código;
- Config. distingue aparelho de AlertaM conectado;
- leitura de QR inválido preserva pareamento atual;
- falha de rede na validação preserva pareamento atual;
- QR do mesmo Desktop não mostra troca;
- QR de Desktop diferente mostra confirmação;
- Cancelar preserva A;
- Confirmar promove B somente após sucesso;
- erro temporário no switch preserva estado candidato e A;
- retry/reconciliação não duplica instalação;
- acesso revogado limpa identidade local revogada;
- novo pareamento após revogação gera novo UUID;
- Push é reaplicado após troca quando possível;
- falha de Push não desfaz a troca;
- heartbeat não interfere no polling principal.

## 23. Testes Desktop

Cobertura mínima:

- janela Conectar Celular não renderiza lista completa;
- contador de ativos é exibido;
- erro na listagem não quebra QR;
- botão Gerenciar aparelhos abre janela própria;
- abas Ativos/Revogados exibem dados corretos;
- revogação exige confirmação;
- falha de revogação mantém item visível;
- sucesso move item para Revogados;
- botão global usa texto **Revogar todos e gerar novo QR**;
- confirmação global informa quantidade de ativos;
- chamadas de rede não bloqueiam Tk;
- mensagens da thread de serviço chegam via fila da UI.

Os testes Tk reais/Xephyr continuam sendo gate para mudanças visuais do Desktop.

## 24. Smoke manual obrigatório

Antes de declarar produção validada:

1. parear iPhone/iPad e confirmar código na PWA e Desktop;
2. parear um segundo aparelho quando disponível;
3. revogar apenas um e confirmar que o outro continua funcionando;
4. confirmar perda de Push/Tracking do revogado;
5. re-parear o revogado e confirmar novo código;
6. PWA em A lê QR de B e cancela → continua A;
7. PWA em A lê QR de B e confirma → passa a B;
8. simular/reproduzir falha de rede durante validação/troca quando viável;
9. usar revogação global e confirmar que todos perdem acesso;
10. escanear novo QR e confirmar recuperação normal.

Android não bloqueia conclusão se não houver aparelho disponível no momento, desde que a
classificação e os testes automatizados estejam cobertos. O smoke iOS real permanece obrigatório,
pois foi onde o problema original foi observado.

## 25. Critérios de aceite

A SPEC está funcionalmente concluída quando:

- Desktop identifica instalações ativas por plataforma + código;
- PWA mostra a mesma identificação em Config.;
- revogação individual afeta somente a instalação escolhida;
- revogados aparecem por 30 dias;
- não há revogação automática por inatividade;
- instalação revogada não pode ser reativada;
- ação global revoga todos e gera novo QR;
- lista completa não polui a janela Conectar Celular;
- novo QR de outro Desktop é validado antes da confirmação;
- Cancelar mantém o Desktop atual;
- Confirmar realiza troca segura e recuperável;
- Push antigo é desativado;
- Ship Tracking antigo é encerrado;
- preferências de Push podem ser reaplicadas no novo Desktop;
- os dois repositórios passam em suas suítes automatizadas;
- UI Desktop passa no gate Tk/Xephyr;
- smoke real de troca/revogação é documentado.

## 26. Fora do escopo futuro

Podem ser considerados depois, sem entrar nesta SPEC:

- nomes amigáveis editáveis como “iPhone do Ciro”;
- auditoria administrativa mais longa;
- remoção física/housekeeping de instalações antigas;
- notificação no Desktop quando um novo aparelho conecta;
- detalhes de modelo do aparelho;
- limite configurável de aparelhos por Desktop.

## 27. Perguntas em aberto

Nenhuma pergunta de produto bloqueante permanece.

Decisões técnicas de baixo nível — nomes finais de classes, divisão exata de módulos e formato
interno do registro de idempotência — devem ser detalhadas no plano de implementação sem alterar
os contratos e invariantes desta SPEC.
