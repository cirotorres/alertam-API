# Pré-Plan 4 — SPEC 029 + piloto real do updater Windows

**Data:** 2026-10-04
**Status:** fluxo aprovado para execução; código não iniciado por este documento.
**Objetivo:** executar a SPEC 029 antes do Maneuver Shadow e usar o resultado como primeira release genérica real do updater, validando o caminho de atualização no computador do pai do usuário.

## 1. Decisão de ordem

O Plan 4 da SPEC 025 continua **tecnicamente liberado**, porém sua execução fica **deliberadamente adiada** por decisão do usuário.

Nova ordem operacional:

1. implementar SPEC 029 — tábua DHN + refinamento do controle de informação;
2. revisar e integrar SPEC 029 em Desktop/PWA;
3. publicar PWA da SPEC 029;
4. preparar primeira release genérica Windows **4.3.1** pelo fluxo manual atual;
5. validar happy path do updater no computador do pai do usuário;
6. registrar evidência;
7. somente então iniciar SPEC 025 Plan 4 — Maneuver Shadow.

Isso é uma decisão de sequenciamento, não uma dependência técnica entre SPEC 029 e Shadow.

## 2. Bases canônicas

Desktop:

```text
/home/ciro/dev/prog/alertamaritimo
branch base: develop
HEAD de referência na criação deste fluxo: 7e3f088
```

API/PWA:

```text
/home/ciro/dev/prog/alertamaritimoAPI
branch base: feat/api-bootstrap
HEAD de referência na criação deste fluxo: c3de5c1
```

A implementação deve usar worktrees/branches isolados, sem trabalhar diretamente nas branches canônicas.

## 3. Escopo funcional antes da release

### Desktop

Entregar a SPEC 029 e normalizar o controle de informação:

- remover a linha permanente `ID AlertaM: ...`;
- usar um **controle de informação real, compacto e focável**, visualmente alinhado aos demais controles da linha inferior;
- manter o símbolo `ⓘ` ou ícone equivalente já disponível no projeto, sem depender de asset externo;
- hover/foco deve mostrar produto, versão, `device_id` e autoria;
- nunca mostrar segredo;
- adicionar `🌊 Maré` na mesma linha;
- janela de maré Hoje+Amanhã, não modal, reutilizável e offline;
- representação enxuta por linha: horário + altura + indicador discreto `Próxima`;
- fonte DHN visível e separada de meteorologia observada/modelada.

### PWA

- manter navegação atual;
- adicionar `Tábua de maré · DHN` na rota Tempo;
- Hoje+Amanhã;
- mesmo dataset do Desktop;
- sem API/Supabase/MobileSnapshot;
- sem misturar DHN com WebPilot/Open-Meteo.

## 4. Fonte DHN

A execução da Task 1 exige o PDF original:

```text
16 - TERMINAL PORTUÁRIO DO PECÉM  58 - 60.pdf
```

SHA-256 esperado:

```text
dad5ef1a49ddf499c25dce5488612e521c4be614dc1c465a1f6c1ecf2b49b6bd
```

O arquivo não está versionado nos repositórios. Se não estiver disponível na nova sessão do Executor, ele deve pedir ao usuário que o reanexe. Não substituir por fonte web.

## 5. Fases de implementação

### Fase A — Dataset

Executar Task 1 da SPEC 029:
- validar hash do PDF;
- gerar JSON canônico 2026;
- copiar byte a byte para Desktop/PWA;
- validar 365 dias, eventos, alturas negativas, amostras fixas e paridade de hash.

**Checkpoint A:** revisão do dataset antes de UI.

### Fase B — Desktop

Executar Task 2:
- domínio temporal UTC−03;
- loader offline;
- `🌊 Maré`;
- `ⓘ` normalizado;
- remoção do ID permanente;
- PyInstaller inclui o JSON;
- testes unitários + Tk/Xephyr.

**Checkpoint B:** revisão Desktop.

### Fase C — PWA

Executar Task 3:
- helper temporal equivalente;
- card de maré na WeatherPage;
- regressão da meteorologia A3;
- frontend full + build.

**Checkpoint C:** revisão PWA.

### Fase D — Cross-repo

Executar Task 4:
- hashes dos datasets iguais;
- nenhum backend/Supabase/contract alterado;
- gates completos;
- revisão independente.

Após aprovação explícita:
- commits por repositório;
- merge para `develop` e `feat/api-bootstrap`;
- push/deploy PWA;
- smoke visual PWA.

## 6. Piloto do updater — versão 4.3.1

O repositório público `cirotorres/alertam-releases` estava sem releases na revisão deste fluxo. A primeira release genérica pode, portanto, usar:

```text
4.3.1
```

Desde que nenhuma release maior seja criada antes da execução.

### Pré-condição obrigatória no computador do pai

Antes de publicar a release pública:

1. confirmar que o AlertaM atual abre e o PWA/mobile dele funciona;
2. registrar apenas o `device_id` atualmente mostrado pelo Desktop;
3. confirmar a existência de:
   ```text
   %LOCALAPPDATA%\AlertaM\desktop_identity.json
   ```
4. **não abrir, copiar ou registrar o segredo contido/protegido nesse estado**;
5. se o arquivo não existir, **STOP**: não usar a release genérica como primeira migração; executar antes o fluxo bridge apropriado.

A cronologia do código indica que identidade persistente e updater já existiam antes do EXE gerado em 01/10 às 22:13, mas o gate real é a presença/validação do store local no Windows alvo.

## 7. Preparação manual da release

Após SPEC 029 integrada e revisada:

1. alterar:
   ```text
   src/alertam/version.py -> 4.3.1
   ```
2. criar, para rastreabilidade:
   ```text
   docs/releases/notes/4.3.1.md
   ```
   usando o mesmo texto que será o body da GitHub Release;
3. rodar no Windows:
   ```powershell
   .\tasks.ps1 check
   .\tasks.ps1 build
   .\tasks.ps1 hash-release
   ```
4. conferir:
   - `dist\AlertaM.exe`;
   - `dist\AlertaM.exe.sha256`;
   - ausência de config mobile embutida no build genérico;
5. criar manualmente GitHub Release estável:
   ```text
   v4.3.1
   ```
6. anexar exatamente:
   - `AlertaM.exe`;
   - `AlertaM.exe.sha256`;
7. usar o conteúdo de `docs/releases/notes/4.3.1.md` como body;
8. não marcar draft/prerelease.

A automação `publish-release` existente na branch separada da SPEC 028 **não participa deste piloto**.

## 8. Happy path no computador do pai

Depois da publicação:

1. fechar e reabrir o AlertaM antigo para forçar a consulta inicial;
2. confirmar a faixa `Nova versão 4.3.1 disponível`;
3. clicar em atualizar;
4. confirmar progresso do download;
5. confirmar SHA-256/validação sem erro;
6. confirmar fechamento e respawn automático;
7. confirmar versão 4.3.1;
8. confirmar janela `AlertaM atualizado` com as notas corretas;
9. clicar `Entendi` e provar comportamento once-only;
10. confirmar **mesmo device_id** no novo `ⓘ`;
11. confirmar PWA/mobile sem novo pareamento;
12. confirmar que a janela `Conectar Celular` agora possui o código temporário de 6 dígitos;
13. confirmar `🌊 Maré` e tábua correta no Desktop;
14. confirmar monitoramento/coleta/voz continuam normais.

## 9. O que este piloto comprova — e o que não comprova

Se passar, comprova:
- descoberta de release;
- download;
- checksum;
- handoff;
- respawn;
- release notes;
- persistência de identidade;
- compatibilidade do Desktop antigo do pai com o updater atual.

Não fecha sozinho:
- cenário proposital de falha de startup;
- rollback automático;
- ausência de loop após rollback.

Esses itens continuam pertencendo ao smoke completo do updater e podem ser executados separadamente antes da release 6.0.0.

## 10. Relação com SPEC 028

Existe implementação de SPEC 028 na branch Desktop:

```text
spec028-plan1-desktop
```

incluindo commits:
- `136ddb4` — bridge com identidade explícita;
- `006e265` — `build-new-desktop`;
- `b59f699` — `publish-release`.

Ela **não está integrada em `develop`** neste checkpoint.

Decisão para este fluxo:
- não mergear SPEC 028 apenas para executar o piloto 4.3.1;
- usar publicação manual atual;
- após Cloud, forward-portar/revisar a SPEC 028 contra a `develop` atual;
- usar então `build-new-desktop` e `publish-release` como fluxo administrativo oficial antes da 6.0.0.

## 11. Gate para retornar ao Plan 4

Plan 4 só volta a ser iniciado depois de:
- SPEC 029 tecnicamente aprovada e integrada;
- PWA da 029 validado;
- release 4.3.1 publicada;
- happy path no computador do pai confirmado;
- identidade/PWA preservados;
- evidência registrada.

Falha no updater vira prioridade de correção antes do Shadow.

## 12. Restrições

- nenhum cutover HTTP;
- nenhum Cloud;
- nenhum backend novo para maré;
- não aplicar SPEC 028 neste piloto;
- não fazer commit/push/deploy sem autorização explícita do usuário;
- não publicar 4.3.1 antes da revisão final da SPEC 029 e do preflight do computador do pai.
