# Handoff — SPEC 026 Plano 2 concluído: PWA e troca segura de pareamento

**Data:** 2026-09-30  
**Branch:** `feat/api-bootstrap`  
**Base do Plano 2:** `7c6ae52 docs: consolida api da gestão mobile`  
**Push:** não realizado por decisão do usuário.

## Objetivo entregue

O Plano 2 implementou na PWA:

- identificação humana da instalação por plataforma + `display_code`;
- persistência local separada da metadata da instalação;
- criação de UUID candidato sem persistência antecipada;
- cliente para create/recover/validate/switch/heartbeat da sessão mobile;
- validação de QR sem side effects;
- confirmação explícita ao trocar entre Desktops diferentes;
- preservação do Desktop atual enquanto o candidato ainda não foi promovido;
- retry idempotente de switch com o mesmo `switch_id`;
- tratamento explícito de acesso revogado;
- Config. com **Este aparelho** e **AlertaM conectado**;
- heartbeat de atividade da instalação;
- remount da árvore operacional quando o `installationId` muda;
- reaplicação automática de Push após switch, sem migrar Tracking.

## Commits do Plano 2

1. `5a3cc81 feat: identifica instalação mobile na pwa`
2. `ffb65e6 feat: adiciona contratos de sessão e troca mobile`
3. `7276554 feat: confirma troca segura entre alertam`
4. `e3bff8d feat: exibe identidade do aparelho na pwa`
5. `ced24a0 fix: endurece transição de sessão mobile`
6. `c3e7977 feat: atualiza atividade da instalação mobile`
7. `275fd8e feat: reaplica push após troca de alertam`
8. `696fbbf fix: corrige build do rebind push`

A quantidade excede o mínimo de 2 commits autorizado pelo usuário. Nenhum push foi feito.

## Identidade da instalação

Arquivos principais:

- `frontend/src/features/pairing/devicePlatform.ts`
- `frontend/src/features/pairing/installationMetadata.ts`
- `frontend/src/features/push/installationId.ts`

Plataformas:

- `ios`
- `android`
- `other`

A PWA detecta apenas a categoria grosseira do aparelho. Não coleta modelo, serial ou fingerprint.

A metadata persistida localmente contém somente:

```text
installationId
displayCode
platform
```

O `deviceId` do Desktop continua pertencendo ao pairing, não à metadata da instalação.

O UUID candidato pode ser gerado por `createFreshInstallationId()` sem gravar nada até a promoção confirmada.

## Config. da PWA

A página Config. passou a separar:

```text
Este aparelho
iPhone/iPad · K7M4Q2

AlertaM conectado
pecem-55ee08ee
```

O UUID técnico não é exibido.

**Esquecer este aparelho**:

1. tenta desativar Push em best effort;
2. delega toda limpeza de pairing/UUID/metadata ao `PairingGate`;
3. não duplica limpeza local dentro da página.

## Cliente de sessão mobile

Arquivo:

`frontend/src/features/pairing/mobileSessionClient.ts`

Contratos consumidos:

- `POST /api/v1/mobile/session`
- `GET /api/v1/mobile/session`
- `DELETE /api/v1/mobile/session`
- `POST /api/v1/mobile/pairing/validate`
- `POST /api/v1/mobile/session/switch`
- `POST /api/v1/mobile/session/heartbeat`

Create/recovery persistem somente identidade confirmada pelo servidor.

Validation/switch/heartbeat não promovem ou limpam pairing local por conta própria.

`clearMobileSession()` é best effort e limpa somente o cookie remoto; o dono do estado local é o `PairingGate`.

## PairingGate — state machine

O `PairingGate` agora distingue:

- pairing ativo A;
- candidato B;
- validação em andamento;
- confirmação A → B;
- erro temporário;
- switch com resposta ambígua;
- acesso revogado.

### QR candidato

Fluxo:

```text
ler fragmento
  ↓
remover fragmento da URL
  ↓
validar B sem side effects
  ↓
mesmo Desktop?
  ├─ sim → tentar reaproveitar instalação ativa
  │          └─ UUID revogado → criar UUID novo uma única vez
  └─ não → pedir confirmação
```

O fragmento é removido da URL antes da chamada de validação.

### Cancelamento

Cancelar a troca:

- descarta B;
- mantém A;
- mantém installation A;
- não chama switch;
- não gera UUID desnecessário.

### Confirmação

Ao confirmar A → B:

- gera novo `installationId`;
- gera `switch_id`;
- envia ambos uma única vez;
- só promove B depois da resposta/reconciliação positiva.

### Resposta ambígua

Se o request de switch pode ter sido concluído no servidor, mas a resposta falha:

- o mesmo draft é mantido em memória;
- o mesmo `installationId` é reutilizado;
- o mesmo `switch_id` é reutilizado;
- a árvore operacional de A fica desmontada durante esse estado;
- botão **Tentar novamente** reconcilia sem gerar outro aparelho.

Essa desmontagem foi adicionada na auto-revisão para impedir que polling de A receba 401 e destrua o estado necessário ao retry.

## Mesmo Desktop

Se o QR pertence ao mesmo `device_id`:

- não exibe diálogo **Trocar de AlertaM**;
- se a instalação atual ainda é válida, reutiliza-a;
- se o UUID atual foi revogado, tenta exatamente uma instalação nova;
- um UUID órfão no storage não é reutilizado em primeiro pareamento.

## Revogação explícita

Quando a API reporta acesso revogado, o `PairingGate` mostra:

```text
Acesso revogado

Este aparelho não possui mais acesso ao AlertaM.
Escaneie um novo QR Code para conectar novamente.
```

A identidade local ativa é limpa.

## Bloqueio de recovery após “Esquecer”/revogação

Foi criado um tombstone local:

`alertam.mobile.session.recovery-blocked.v1`

Motivação:

se o DELETE remoto falhar por rede e o cookie HttpOnly continuar no navegador, um reload não pode recuperar silenciosamente a sessão antiga depois que o usuário escolheu **Esquecer este aparelho**.

Regras:

- reset manual bloqueia recovery;
- revogação observada bloqueia recovery;
- reload respeita o bloqueio e permanece aguardando novo QR;
- novo pairing promovido com sucesso remove o bloqueio.

## Snapshot e ownership da identidade

A auto-revisão removeu do `useSnapshotPolling` a responsabilidade de executar `clearPairing()`.

Agora um 401 de snapshot apenas entra em estado `revoked`; a limpeza da identidade é centralizada no `PairingGate`.

Isso evita múltiplos owners do pairing e protege o estado de reconciliação do switch.

## Remount por installationId

No `App`, a árvore:

```text
SnapshotProvider
  EventProvider
    TrackingProvider
      PushProvider
        AppRoutes
```

é keyed pelo `installationId`.

Ao promover B:

- Snapshot é remontado;
- Eventos são remontados;
- Tracking é remontado;
- Push é remontado.

Portanto estado de Tracking/Eventos de A não atravessa para B.

## Heartbeat da instalação

Arquivo:

`frontend/src/features/pairing/useMobileSessionHeartbeat.ts`

Comportamento:

- somente com sessão pronta;
- não roda no demo;
- envio imediato quando a PWA está visível;
- aproximadamente a cada 5 minutos;
- pausa enquanto `document.visibilityState !== "visible"`;
- ao retornar para visible, envia novamente;
- falha temporária não derruba a PWA;
- 401 chama o callback de acesso revogado uma vez e encerra o ciclo.

Esse heartbeat é separado de `useForegroundHeartbeat` do Push porque representam responsabilidades diferentes.

## Push após switch

Foi criado:

`frontend/src/features/push/pushPreferenceStorage.ts`

Persistência não sensível:

```text
optedIn
preferences.confirmed
preferences.updated
preferences.completed
preferences.cancelled
```

Ao montar a nova instalação B:

1. consulta Push de B no servidor;
2. se ainda não existe e `optedIn=true`;
3. exige `Notification.permission === "granted"`;
4. reutiliza somente uma browser subscription já existente;
5. não abre novo prompt de permissão;
6. não cria nova subscription automaticamente;
7. registra a subscription existente para B;
8. reaplica as preferências.

Falha temporária no rebind:

- não desfaz o switch para B;
- deixa Push inativo/com erro;
- mantém opt-in salvo para recuperação/manual retry;
- não chama revogação da sessão.

Se o registro servidor foi criado, mas a reaplicação de preferências falha, o provider tenta rollback do binding Push em best effort.

## Auto-revisão intermediária

Executada após a Task 4, conforme solicitado.

Foram encontrados e corrigidos quatro findings:

### 1. Snapshot apagava pairing diretamente

Problema:

`useSnapshotPolling` ainda chamava `clearPairing()` em 401.

Risco:

múltiplos owners do estado e destruição do pairing A durante switch ambíguo.

Correção:

snapshot apenas reporta estado revoked; `PairingGate` limpa identidade.

### 2. Aplicação A permanecia montada durante resposta ambígua do switch

Problema:

polling de A poderia receber 401 porque o servidor já concluiu A → B.

Risco:

callback de revogação apagaria o draft necessário à reconciliação.

Correção:

durante `temporary-switch`, a árvore operacional não é montada.

### 3. Metadata local continha `deviceId` extra

Problema:

`MobileSessionInfo` inteiro estava sendo passado ao storage.

Correção:

persistência explícita somente de `installationId + displayCode + platform`.

### 4. “Esquecer” offline podia ser desfeito por cookie antigo após reload

Problema:

DELETE remoto é best effort; se falhasse, cookie HttpOnly poderia continuar válido e recovery reentraria sozinho no app.

Correção:

tombstone persistente de bloqueio de recovery até um novo pairing ser promovido.

Commit da auto-revisão:

`ced24a0 fix: endurece transição de sessão mobile`

## Verificação

### Checkpoints focados

- Task 1: 12 testes
- Task 2: 10 testes do client + 10 regressões do PairingGate
- Task 3: 22 testes client/gate + build
- Task 4: gate completo na metade do plano
- auto-revisão: 37 testes focados
- Task 5: 14 testes heartbeat/App
- Task 6: 14 testes Push/storage/remount

### Gate final

Executado após todas as mudanças de produção:

`npm test -- --run`

Resultado:

**47 arquivos de teste / 251 testes passaram.**

`npm run build`

Resultado:

**PASS — TypeScript + Vite/PWA build concluído.**

`git diff --check`

Resultado:

**PASS.**

## Revisão de segurança

Verificado no diff do Plano 2:

- fragmento do QR removido antes da validação;
- nenhum log/debug novo expõe `viewSecret`;
- nenhum erro novo inclui `viewSecret`;
- nenhum storage adicional guarda `viewSecret`;
- referências restantes a `viewSecret` são as esperadas no modelo de pairing e header Bearer.

## Dependência externa ainda pendente do Plano 1

As migrations 013/014 ainda não foram validadas contra Postgres/Supabase real neste ambiente porque `TEST_POSTGRES_DSN` não estava configurado.

Isso não invalida os testes locais da PWA, mas continua sendo gate obrigatório antes do rollout real da SPEC 026.

## Próximo plano

Plano 3:

`docs/superpowers/plans/2026-09-30-spec026-plan3-desktop-device-management.md`

Objetivo:

- cliente administrativo Desktop;
- contador de aparelhos na janela Conectar Celular;
- janela separada **Gerenciar aparelhos**;
- abas Ativos/Revogados;
- revogação individual;
- ação **Revogar todos e gerar novo QR**;
- gate `make check`;
- Tk/Xephyr;
- smoke cross-repo.

## Estado do Desktop antes do Plano 3

Antes de iniciar o Plano 3, revisar a árvore do repositório:

`/home/ciro/dev/prog/alertamaritimo`

Existe trabalho anterior independente da SPEC 026 relacionado a som/marcador de acompanhados. Esse trabalho não deve ser misturado com commits da gestão de aparelhos sem antes ser checkpointado separadamente.

## Regra de versionamento

Commits locais estão autorizados.

**Push não está autorizado e não foi executado.**
