# Handoff — SPEC 026 Plano 3 concluído: Desktop e gestão de aparelhos

**Data:** 2026-09-30  
**Status geral:** implementação local dos Planos 1, 2 e 3 concluída. Infraestrutura real e smoke físico ainda pendentes.  
**Push:** não realizado em nenhum dos dois repositórios.

## Repositórios e branches

### Desktop

Repositório:

`/home/ciro/dev/prog/alertamaritimo`

Branch:

`develop`

HEAD ao concluir o Plano 3:

`65543d4 docs: atualiza guia de aparelhos conectados`

Estado:

- working tree limpa;
- branch 7 commits à frente de `origin/develop`;
- nenhum push realizado.

O primeiro commit à frente do remoto é um ciclo anterior, independente da SPEC 026:

`4b3e485 feat: sinaliza novidades em acompanhamentos`

Ele foi checkpointado antes do Plano 3 para não misturar as duas features.

### API/PWA

Repositório:

`/home/ciro/dev/prog/alertamaritimoAPI`

Branch:

`feat/api-bootstrap`

HEAD antes deste handoff:

`9337e57 docs: consolida troca segura na pwa`

Estado:

- working tree limpa antes do handoff;
- branch 17 commits à frente de `origin/feat/api-bootstrap`;
- nenhum push realizado.

## Commits do Plano 3 Desktop

1. `5c205f2 feat: adiciona cliente de gestão de aparelhos`
2. `e64861d feat: coordena gestão mobile fora da ui`
3. `8ade67d feat: integra contador de aparelhos no qr`
4. `8e44f42 feat: adiciona gerenciador de aparelhos`
5. `3a20749 feat: sincroniza estado dos aparelhos na ui`
6. `65543d4 docs: atualiza guia de aparelhos conectados`

A quantidade supera o mínimo de dois commits solicitado pelo usuário e corresponde a ciclos funcionais fechados.

## Objetivo entregue no Desktop

O Desktop agora consegue administrar as instalações mobile vinculadas ao seu próprio `device_id` sem expor essa administração à PWA.

Foram entregues:

- cliente HTTP administrativo autenticado com `DEVICE_SECRET`;
- listagem de aparelhos ativos e revogados recentes;
- contador na janela **Conectar Celular**;
- botão **Gerenciar aparelhos**;
- janela separada com abas **Ativos** e **Revogados**;
- código humano como `iPhone/iPad · K7M4Q2`;
- última atividade e data de conexão;
- revogação individual;
- histórico de revogados por 30 dias;
- ação global **Revogar todos e gerar novo QR**;
- confirmação global usando contagem fresca da API;
- cache de último snapshot administrativo confirmado;
- atualização de UI exclusivamente pela fila principal/Tk;
- Guia do operador atualizado.

## Cliente administrativo Desktop

Arquivos principais:

- `src/alertam/application/mobile_installations.py`
- `src/alertam/infrastructure/mobile_installations_http.py`
- `src/alertam/infrastructure/mobile_installations_service.py`

Contratos consumidos:

```text
GET /api/v1/devices/{device_id}/mobile-installations
DELETE /api/v1/devices/{device_id}/mobile-installations/{installation_id}
```

Autenticação:

```text
Authorization: Device <DEVICE_SECRET>
```

O contrato foi conferido diretamente contra o router da API no fechamento do Plano 3.

### Segurança do transporte

- HTTPS obrigatório fora de localhost/loopback;
- timeout limitado a 10 segundos;
- 401/403 viram erro de credencial sanitizado;
- rede/timeout/5xx viram falha temporária;
- corpo de erro HTTP não é propagado para mensagem de usuário;
- `DEVICE_SECRET` não é incluído em logs/mensagens de erro.

## Modelo administrativo

Cada item contém internamente:

- UUID da instalação;
- `display_code`;
- plataforma;
- ativo/inativo;
- criação;
- última atividade;
- revogação.

A UI não exibe o UUID.

Labels:

- `ios` → `iPhone/iPad · <código>`;
- `android` → `Android · <código>`;
- demais → `Outro aparelho · <código>`.

Plataformas inesperadas vindas da API caem para `other`.

## Serviço assíncrono

A gestão administrativa não bloqueia a thread Tk.

`MobileInstallationsService`:

- usa worker daemon;
- permite uma operação administrativa por vez;
- `refresh` e `revoke` são single-flight;
- revogação bem-sucedida consulta novamente a lista no mesmo worker;
- callback tardio é suprimido após `stop()`;
- erros internos são sanitizados;
- shutdown tem join limitado a 0,2 s.

Os resultados entram na `ui_queue` como:

- `MOBILE_INSTALLATIONS_READY`;
- `MOBILE_INSTALLATION_ACTION`.

Nenhum worker chama Tk diretamente.

## Janela Conectar Celular

A janela continua focada no pareamento e não incorpora a lista de aparelhos.

Foram adicionados apenas:

```text
Aparelhos conectados: N

[ Gerenciar aparelhos ]

[ Revogar todos e gerar novo QR ]
```

Quando a contagem ainda não pôde ser carregada:

```text
Aparelhos conectados: indisponível
```

A lista completa permanece em janela separada para não poluir visualmente o fluxo de QR.

## Janela Gerenciar aparelhos

Título:

`AlertaM - Gerenciar aparelhos`

Possui duas abas:

```text
Ativos (N)
Revogados (N)
```

### Aba Ativos

Cada cartão exibe:

- label humano do aparelho;
- última atividade;
- data de conexão;
- botão **Revogar**.

### Aba Revogados

Cada cartão exibe:

- label humano;
- data da revogação;
- última atividade.

A aba é apenas histórico dos revogados retornados pela API nos últimos 30 dias.

A janela é rolável e independente da janela de QR.

## Revogação individual

Ao clicar em **Revogar**, o Desktop pede confirmação mencionando somente aquele aparelho.

A confirmação explica que:

- o aparelho perderá o acesso;
- as notificações daquele aparelho serão encerradas;
- os acompanhamentos daquele aparelho serão encerrados.

Durante a operação:

- novos cliques de revogação ficam bloqueados;
- nenhum item é movido otimisticamente;
- somente o snapshot confirmado pela API move o aparelho de Ativos para Revogados;
- falha preserva o último estado confirmado.

## Revogação global e novo QR

A antiga nomenclatura **Gerar novo acesso** foi substituída na UI/Guia por:

**Revogar todos e gerar novo QR**

Fluxo:

1. usuário clica na ação;
2. Desktop solicita uma listagem administrativa fresca;
3. só depois recebe a contagem atual;
4. confirmação mostra quantos aparelhos ativos serão desconectados;
5. mensagem explica que Push e acompanhamentos serão encerrados;
6. se confirmado, o Desktop executa a rotação do `VIEW_SECRET`;
7. após o novo acesso ficar ativo, o Desktop atualiza novamente a lista administrativa.

A confirmação não usa contador potencialmente antigo.

## Cache e consistência da UI

`MainWindow` mantém:

`_mobile_installations_snapshot`

como último snapshot administrativo confirmado.

Uma resposta válida:

- substitui o cache;
- atualiza o contador na janela de QR;
- atualiza Gerenciar aparelhos apenas se a janela estiver aberta.

Uma falha:

- não apaga o último snapshot confirmado;
- não altera o contador previamente confirmado;
- pode atualizar apenas o estado/aviso da janela administrativa se ela estiver visível.

Callback tardio com a janela fechada não cria novo Toplevel.

## Guia do operador

O Guia foi atualizado para explicar:

- **Gerenciar aparelhos**;
- revogação individual;
- histórico de revogados por 30 dias;
- **Revogar todos e gerar novo QR**.

O texto evita expor identificadores internos como `installation_id`.

## Auto-revisão intermediária do Plano 3

Executada após a Task 3.

Revisado:

- vazamento de `DEVICE_SECRET`;
- chamadas de rede na thread Tk;
- concorrência administrativa;
- contagem fresca antes da rotação global;
- ownership da atualização da UI.

Resultado:

nenhum finding bloqueante.

Gate executado nessa revisão:

`make check`

Resultado naquele checkpoint:

**600 passed, 63 skipped, imports OK**.

## Gates finais Desktop

### Unitários/imports

`make check`

Resultado final:

**614 passed, 64 skipped, imports OK**.

O skip adicional corresponde ao teste Tk real da nova janela quando executado sem `DISPLAY`.

### Tk real / Xephyr

Com a sessão gráfica atual:

```bash
DISPLAY=:0 XAUTHORITY=/run/user/1000/.mutter-Xwaylandauth.V56BW3 \
  make test-ui XEPHYR_N=33
```

Resultado:

**678 passed em 196,01 s (3m16s)**.

Isso inclui o teste Tk real da janela com duas abas.

### Git

`git diff --check`:

**PASS**.

Working tree Desktop após o commit documental:

**limpa**.

## Gates finais API/PWA

Executados novamente no fechamento do Plano 3 para detectar drift entre os repositórios.

### API

`make test`

Resultado:

**PASS / exit 0**.

Integrações que dependem de Postgres real continuam puladas quando `TEST_POSTGRES_DSN` não está configurado.

### PWA

`npm test -- --run`

Resultado:

**47 arquivos / 251 testes passed**.

`npm run build`

Resultado:

**PASS**.

Há um warning conhecido do React em um teste de `AppShell` sobre `act(...)`, mas a suíte passa e esse warning não foi introduzido pelo Plano 3.

## Cross-repo contract check

Verificado localmente no fechamento:

API:

```text
GET    /api/v1/devices/{device_id}/mobile-installations
DELETE /api/v1/devices/{device_id}/mobile-installations/{installation_id}
```

Desktop:

```text
GET    /api/v1/devices/<device>/mobile-installations
DELETE /api/v1/devices/<device>/mobile-installations/<uuid>
Authorization: Device <DEVICE_SECRET>
```

Os contratos estão alinhados.

## Migrations e infraestrutura ainda pendentes

A implementação local da SPEC 026 está completa, mas o rollout real ainda depende de:

1. aplicar `013_mobile_installation_management.sql` no Postgres/Supabase real;
2. aplicar `014_mobile_session_switch.sql`;
3. executar os testes de integração com `TEST_POSTGRES_DSN` configurado;
4. publicar a API;
5. publicar a PWA;
6. disponibilizar um build Desktop contendo o Plano 3.

Não declarar a SPEC 026 como validada em produção antes desses passos.

## Smoke manual obrigatório após deploy

### 1. Pareamento inicial

- abrir **Conectar Celular**;
- parear um iPhone/iPad;
- conferir o label/código na Config. da PWA;
- abrir **Gerenciar aparelhos** no Desktop;
- conferir que aparece o mesmo código curto.

### 2. Revogação individual

- no Desktop, clicar **Revogar** naquele aparelho;
- confirmar;
- verificar que sai de Ativos e entra em Revogados;
- verificar PWA mostrando **Acesso revogado**;
- confirmar que Push e acompanhamentos daquele aparelho foram encerrados.

### 3. Re-pareamento

- escanear QR novamente;
- confirmar que nasce nova instalação;
- conferir novo código curto;
- garantir que a instalação revogada anterior permanece no histórico e não reativa.

### 4. Troca A → B — cancelar

Com a PWA conectada ao Desktop A:

- escanear QR do Desktop B;
- validar que aparece confirmação de troca;
- cancelar;
- confirmar que A continua funcionando.

### 5. Troca A → B — confirmar

- escanear B novamente;
- confirmar;
- conferir novo código/instalação;
- verificar que Tracking/Eventos de A não aparecem em B;
- se Push estava ativado, validar rebind sem novo prompt de permissão.

### 6. Resposta ambígua/retry

Em ambiente de teste onde seja possível interromper a resposta:

- provocar falha de rede após o switch;
- usar **Tentar novamente**;
- confirmar que o mesmo `switch_id` reconcilia sem criar instalação duplicada.

### 7. Rotação global

- conectar pelo menos dois aparelhos;
- abrir **Conectar Celular**;
- clicar **Revogar todos e gerar novo QR**;
- conferir a contagem mostrada na confirmação;
- confirmar;
- verificar todos os aparelhos antigos revogados;
- confirmar Push/Tracking encerrados;
- conferir novo QR funcional.

## Hardware

**iOS real é obrigatório** para o smoke final, pois foi a plataforma onde o problema original de troca entre Desktops foi observado.

Android deve ser testado quando houver aparelho disponível. A ausência temporária de Android não bloqueia os gates automatizados, mas deve permanecer registrada como smoke pendente até ser executado.

## Estado final da SPEC 026

### Implementação local

- Plano 1 — API/Supabase: **concluído**
- Plano 2 — PWA: **concluído**
- Plano 3 — Desktop: **concluído**

### Validação externa

- Postgres/Supabase real: **pendente**
- deploy API/PWA/Desktop: **pendente**
- smoke iOS real: **pendente**
- smoke Android real: **pendente se não houver hardware disponível**

## Regra de versionamento

O usuário autorizou commits locais durante os planos.

**Nenhum push foi executado.**
