# Handoff — SPEC 029 — Tábua de maré DHN no Desktop e PWA

**Data:** 2026-10-04
**Estado:** implementado localmente; revisão independente pendente.
**Escopo:** Desktop + PWA; sem backend/Supabase/MobileSnapshot.
**Commit/push:** commits locais de execução registrados no ledger; nenhum push.

## 1. Objetivo original da sessão de implementação

Implementar a SPEC 029:

- tábua de maré DHN 2026 do Terminal Portuário do Pecém;
- Hoje + Amanhã;
- próximo evento destacado;
- Desktop: `🌊 Maré` + `ⓘ` e remoção do ID permanente;
- PWA: card `Tábua de maré · DHN` dentro de `Tempo e mar`.

## 2. Leia primeiro

### Fonte de verdade da feature

1. `/home/ciro/dev/prog/alertamaritimoAPI/specs/029-tabua-mare-dhn-desktop-pwa.md`
2. `/home/ciro/dev/prog/alertamaritimoAPI/docs/superpowers/plans/2026-10-04-spec029-tabua-mare-desktop-pwa.md`
3. este handoff.

### Contexto de roadmap

4. `/home/ciro/dev/prog/alertamaritimo/docs/superpowers/strategy/2026-10-02-alertam-cloud-desktop-roadmap.md`
5. `/home/ciro/dev/prog/alertamaritimoAPI/docs/superpowers/strategy/2026-10-02-alertam-cloud-evolution-roadmap.md`

## 3. Repositórios/base

Desktop:

```text
/home/ciro/dev/prog/alertamaritimo
base: develop
```

API/PWA:

```text
/home/ciro/dev/prog/alertamaritimoAPI
base: feat/api-bootstrap
```

Recomendação para execução:
- criar worktree isolado em cada repositório;
- usar o mesmo nome lógico de branch, por exemplo `feat/spec029-tabua-mare-dhn`;
- não implementar diretamente nas branches canônicas.

## 4. Estado anterior já concluído

### Desktop

A1 + A2 + MobileSnapshot v2 estão materializados em `develop`.

Gate oficial mais recente após integração:

```text
make test-ui XEPHYR_N=27
949 passed, 1 skipped
```

### API/PWA

A3 MobileSnapshot v1+v2 e hotfix acompanhamentos/fundeio estão em produção.

A SPEC 029 não deve reabrir esses contratos.

## 5. Fonte DHN

O usuário forneceu o PDF:

```text
16 - TERMINAL PORTUÁRIO DO PECÉM  58 - 60.pdf
```

Identidade esperada:

```text
TERMINAL PORTUÁRIO DO PECÉM (ESTADO DO CEARÁ) - 2026
DHN
Fuso UTC -03.0
Nível Médio 1.56 m
Carta 711
```

SHA-256 esperado:

```text
dad5ef1a49ddf499c25dce5488612e521c4be614dc1c465a1f6c1ecf2b49b6bd
```

**Importante:** o PDF anexado nesta sessão pode não estar disponível numa nova sessão. Se o executor
não conseguir localizar o arquivo, deve pedir ao usuário que o reanexe antes de iniciar a Task 1.
Não pesquisar/substituir por outra tabela na web.

## 6. Decisões fechadas

### Dataset

- JSON estático;
- 2026;
- 365 datas;
- 3 ou 4 eventos conforme fonte;
- alturas negativas preservadas;
- Desktop e PWA usam cópias byte-idênticas;
- sem leitura de PDF em runtime;
- sem endpoint;
- sem banco;
- sem snapshot novo.

### Data/hora

Hoje/Amanhã usa Pecém UTC−03 independentemente do timezone do aparelho.

### Desktop

Linha discreta desejada:

```text
[📖 Guia] [Conectar Celular] [☆ Acompanhados]      [🌊 Maré] [ⓘ] [ ] Modo compacto
```

- remover `ID AlertaM: ...` permanente;
- `ⓘ`: produto, versão, device_id e `Desenvolvido por Ciro Torres`;
- `🌊 Maré`: janela única/reutilizável;
- Hoje + Amanhã;
- próximo evento destacado;
- fonte DHN.

### PWA

- manter `Tempo` como entrada existente;
- adicionar card dentro da WeatherPage;
- não criar navegação nova;
- DHN visualmente separado de WebPilot/Open-Meteo.

### Fora do escopo

- gráfico;
- interpolação;
- Lua;
- push;
- API;
- Supabase;
- Open-Meteo tide;
- download automático de PDF.

## 7. Relação com SPEC 025 Plan 4

O Plan 4 — Maneuver HTTP Shadow continua alinhado e é a próxima etapa da trilha crítica.

SPEC 029 é lateral:
- pode ser executada antes do Plan 4;
- depois do Plan 4;
- ou em uma sessão isolada em paralelo.

Ela **não autoriza iniciar Shadow** e Shadow não precisa esperar a SPEC 029.

## 8. Arquivos principais previstos

Desktop:
- `src/alertam/data/tides/pecem-2026.json`;
- `src/alertam/application/tide_table.py`;
- `src/alertam/infrastructure/tide_table_resource.py`;
- `src/alertam/ui/tide_window.py`;
- `src/alertam/ui/widget_tooltip.py`;
- `src/alertam/ui/main_window.py`;
- `src/alertam/bootstrap.py`;
- `alertam.spec`;
- testes correspondentes.

PWA:
- `frontend/src/data/tides/pecem-2026.json`;
- `frontend/src/features/tides/tideTable.ts`;
- `frontend/src/features/tides/TideTableCard.tsx`;
- `frontend/src/pages/WeatherPage.tsx`;
- `frontend/src/styles/app.css`;
- testes correspondentes.

Nenhum arquivo de `api/app` ou `api/supabase` é esperado.

## 9. Estratégia de execução

Seguir o plano em TDD:

```text
Task 1 — dataset/paridade
Task 2 — Desktop
Task 3 — PWA
Task 4 — gates/revisão
```

Não começar Task 2/3 com dataset não validado.

Na Task 1, confirmar amostras fixas do PDF, especialmente:
- 01/01;
- 04/10;
- 05/10;
- altura negativa em 24/12;
- 31/12.

## 10. STOP gates

Parar e pedir confirmação se:
- PDF correto não estiver disponível;
- hash da fonte divergir;
- implementação exigir backend/snapshot inesperadamente;
- execução chegar a commit/push/deploy sem autorização explícita.

## 11. Resultado esperado da próxima sessão

Ao fim da implementação local:
- datasets validados e iguais;
- Desktop funcional em Xephyr;
- PWA full tests/build verdes;
- revisão independente preparada;
- sem alterar Plan 4/Shadow;
- sem push/deploy se não houver autorização.

## 12. Prompt curto

O prompt de início também está salvo em:

`docs/superpowers/prompts/2026-10-04-spec029-start-prompt.md`.


## 13. Nova ordem operacional — SPEC 029 antes do Plan 4

Decisão posterior do usuário:

```text
SPEC 029
  -> revisão/integração Desktop + PWA
  -> primeira release genérica manual 4.3.1
  -> happy path do updater no PC do pai
  -> evidência de identidade/PWA preservados
  -> somente então SPEC 025 Plan 4
```

Documento normativo desse sequenciamento:

`docs/superpowers/plans/2026-10-04-pre-plan4-spec029-updater-pilot.md`

A SPEC 029 continua sem dependência técnica de Shadow. A mudança é apenas de ordem de execução deliberada.

### Ajuste adicional de UX do `ⓘ`

O controle de informação do Desktop deve ser tratado como controle compacto normalizado:
- focável por teclado;
- mesma altura/alinhamento visual da linha de ações;
- sem label permanente de ID;
- hover/foco mostra produto, versão, device_id e autoria;
- nenhuma credencial;
- deve coexistir de forma limpa com `🌊 Maré` e `Modo compacto`.

### Release piloto

- versão alvo inicial: `4.3.1`, desde que continue sendo maior que qualquer release pública no momento da execução;
- publicação manual via `build` + `hash-release` + GitHub Release;
- SPEC 028 automatizada fica fora deste piloto;
- antes de publicar, confirmar no PC alvo a existência de `%LOCALAPPDATA%\AlertaM\desktop_identity.json`.


## 14. Contrato de execução e revisão independente

A implementação da SPEC 029 + preparação do piloto do updater deve usar **este mesmo handoff como ledger de execução**.

A auto-revisão do Executor é obrigatória, mas **não substitui revisão independente**.

Ao concluir todo o trabalho automatizável, o Executor deve anexar neste documento uma seção:

```text
## Execução SPEC 029 + preparação 4.3.1 — Executor — <data>
```

Essa seção deve conter, no mínimo:

### Estado inicial
- branch/HEAD/base de cada repositório;
- worktrees usados;
- dirty state pré-existente distinguido do escopo novo.

### Fase A — Dataset DHN
- caminho/hash do PDF usado;
- SHA-256 conferido;
- quantidade de datas/eventos;
- amostras normativas validadas;
- hash final dos dois JSONs;
- prova de byte-identidade.

### Fase B — Desktop
- arquivos alterados;
- resumo da solução de maré;
- normalização do `ⓘ`;
- remoção do ID permanente;
- inclusão PyInstaller;
- testes unitários/Tk/Xephyr executados e resultados.

### Fase C — PWA
- arquivos alterados;
- integração com WeatherPage;
- confirmação de ausência de backend/Supabase/MobileSnapshot;
- testes focados/full/build e resultados.

### Fase D — Gates cross-repo
- `git diff --check`;
- guardas de escopo;
- busca de segredo;
- paridade dos datasets;
- regressões relevantes A3/PWA;
- quaisquer warnings conhecidos e classificação.

### Preparação 4.3.1
- confirmação read-only do estado de `cirotorres/alertam-releases`;
- versão definida em `src/alertam/version.py`, ou ruling explícito caso ainda não seja alterada;
- caminho e conteúdo resumido de `docs/releases/notes/4.3.1.md`;
- artefatos que ainda dependem do Windows e por isso NÃO foram gerados;
- checklist exato de retomada manual.

### Git
- commits locais finais;
- hash e mensagem de cada commit;
- no máximo um commit final por repositório;
- confirmação explícita de que não houve push.

### Desvios
- qualquer desvio do plano;
- motivo;
- impacto;
- decisão tomada.

### Pedido ao Revisor
Encerrar com uma seção objetiva:

```text
## Pedido de revisão independente
```

solicitando revisão de:
- fidelidade do dataset DHN;
- timezone/virada do dia;
- UI Desktop `ⓘ` + Maré;
- PyInstaller;
- PWA WeatherPage;
- ausência de mudança de contrato/backend;
- qualidade dos testes;
- preparação segura da 4.3.1;
- escopo dos commits.

### STOP

Após escrever o pedido de revisão:
- **parar**;
- não fazer push;
- não publicar release;
- não executar smoke manual;
- não iniciar Plan 4;
- aguardar parecer do Revisor.

O Revisor poderá então:
- aprovar;
- abrir findings;
- pedir correções;
- repetir testes;
- somente após aprovação liberar a etapa manual no Windows.


## Execução SPEC 029 + preparação 4.3.1 — Executor — 2026-10-04

### Estado inicial

Desktop:
- repositório canônico: `/home/ciro/dev/prog/alertamaritimo`;
- branch/base autoritativa: `develop`;
- HEAD inicial: `7e3f088`;
- worktree isolado: `/home/ciro/dev/prog/.worktrees/alertamaritimo-spec029`;
- branch de execução: `feat/spec029-tabua-mare-dhn`;
- dirty state pré-existente na árvore canônica, preservado e fora do commit desta execução:
  - `docs/releases/windows-update-smoke.md`;
  - `docs/superpowers/strategy/2026-10-02-alertam-cloud-desktop-roadmap.md`;
  - `specs/README.md`.

API/PWA:
- repositório canônico: `/home/ciro/dev/prog/alertamaritimoAPI`;
- branch/base autoritativa: `feat/api-bootstrap`;
- HEAD inicial: `c3de5c1`;
- worktree isolado: `/home/ciro/dev/prog/.worktrees/alertamaritimoAPI-spec029`;
- branch de execução: `feat/spec029-tabua-mare-dhn`;
- dirty state pré-existente na árvore canônica, preservado e fora do código novo:
  - `docs/superpowers/plans/2026-09-29-spec025-plan4-maneuver-shadow.md`;
  - `docs/superpowers/plans/2026-10-03-spec025-a3-mobile-snapshot-v2-execution.md`;
  - `docs/superpowers/strategy/2026-10-02-alertam-cloud-evolution-roadmap.md`;
  - `specs/README.md`;
  - documentos da própria SPEC 029 que estavam não versionados e foram trazidos ao worktree para integrar o ledger/planejamento no commit final.

Nenhum `reset`/`clean` destrutivo foi usado. As branches canônicas não foram alteradas durante a implementação.

### Fase A — Dataset DHN

Fonte usada:
- arquivo original anexado pelo usuário: `16 - TERMINAL PORTUÁRIO DO PECÉM  58 - 60.pdf`;
- cópia acessível nesta sessão em `/mnt/data/16 - TERMINAL PORTUÁRIO DO PECÉM  58 - 60.pdf`;
- SHA-256 conferido: `dad5ef1a49ddf499c25dce5488612e521c4be614dc1c465a1f6c1ecf2b49b6bd`.

Resultado da normalização:
- 365 datas de 2026;
- 1.411 eventos;
- 316 dias com 4 eventos;
- 49 dias com 3 eventos;
- alturas negativas preservadas.

Amostras normativas conferidas:
- 01/01: `02:38 2.62`, `08:36 0.48`, `14:57 2.89`, `21:19 0.16`;
- 04/10: `04:49 0.77`, `11:12 2.12`, `17:06 0.99`, `23:36 2.37`;
- 05/10: `06:14 0.70`, `12:31 2.22`, `18:31 0.87`;
- 24/12: preservado `23:14 -0.06`;
- 31/12: `04:25 0.77`, `10:46 2.29`, `16:51 0.86`, `23:16 2.22`.

Cópias:
- Desktop: `src/alertam/data/tides/pecem-2026.json`;
- PWA: `frontend/src/data/tides/pecem-2026.json`.

SHA-256 dos dois JSONs:
`f55961baee0daf9623c3428fd4bb22010d292ac49815d58e5f0503c8a8312677`

A paridade foi provada por `sha256sum` nos dois caminhos. Além das amostras, uma segunda extração independente, baseada nas coordenadas das três páginas do PDF, reconstruiu os 365 dias/1.411 eventos e serializou o dataset novamente; o hash resultante foi exatamente o mesmo `f55961ba...`, reforçando a fidelidade anual da transcrição.

Testes focados:
- Desktop: `uv run pytest tests/unit/test_tide_dataset.py -q` → 2 passed;
- PWA: `npm test -- --run src/features/tides/tideDataset.test.ts` → 2 passed.

### Fase B — Desktop

Arquivos pertencentes ao commit Desktop:
- `.gitignore`;
- `alertam.spec`;
- `docs/releases/notes/4.3.1.md`;
- `src/alertam/application/tide_table.py`;
- `src/alertam/bootstrap.py`;
- `src/alertam/data/tides/pecem-2026.json`;
- `src/alertam/infrastructure/tide_table_resource.py`;
- `src/alertam/ui/main_window.py`;
- `src/alertam/ui/tide_window.py`;
- `src/alertam/ui/widget_tooltip.py`;
- `src/alertam/version.py`;
- `tests/integration/test_tide_ui.py`;
- `tests/integration/test_ui_real.py`;
- `tests/unit/test_pyinstaller_spec.py`;
- `tests/unit/test_ship_tracking_ui_logic.py`;
- `tests/unit/test_tide_dataset.py`;
- `tests/unit/test_tide_table.py`;
- `tests/unit/test_update_notes_bootstrap.py`;
- `tests/unit/test_version.py`.

Solução:
- domínio temporal puro usa offset fixo UTC−03;
- `select_tide_view` resolve Hoje/Amanhã e próximo evento sem usar timezone do sistema;
- 31/12 mantém Hoje e torna 01/01/2027 explicitamente indisponível;
- loader valida schema, metadados, fonte, 365 datas, ordem dos horários e tipos;
- falha de carregamento do dataset não derruba o monitor: o bootstrap registra warning e mantém o Desktop operacional;
- `🌊 Maré` abre `TideWindow` não modal e reutilizável;
- janela mostra exatamente as linhas publicadas, fonte DHN/Carta 711/UTC−03 e marca `Próxima`;
- `Esc`/fechamento seguem o padrão das demais janelas.

Normalização do `ⓘ`:
- removida a label permanente `ID AlertaM: ...`;
- controle `ⓘ` é compacto e focável;
- hover/foco mostram somente produto, versão, `device_id` e autoria;
- contrato verificado em runtime:
  - `AlertaM Desktop`;
  - `Versão: 4.3.1`;
  - `ID: pecem-55ee08ee` no fixture;
  - `Desenvolvido por Ciro Torres`;
- busca negativa nos arquivos da feature não encontrou `device_secret`, `view_secret`, Authorization/Bearer, password, token ou cookie;
- medição Tk no layout padrão e compacto confirmou que `Guia`, `Conectar Celular`, `Acompanhados`, `🌊 Maré`, `ⓘ` e `Modo compacto` permanecem na mesma faixa e cabem sem sobreposição.

PyInstaller:
- `alertam.spec` inclui `pecem-2026.json` em `alertam/data/tides`;
- `.gitignore` foi ajustado para versionar esse recurso estático apesar da regra geral de `data/` de runtime;
- teste do spec cobre a inclusão do recurso e preserva o comportamento do build genérico/bridge existente.

Gates Desktop:
- focados de domínio/info/PyInstaller: 16 testes passaram;
- focados Tk reais da maré + UI principal em Xephyr: passaram;
- `make check` final: **881 passed, 80 skipped**, seguido de `imports OK`;
- suíte completa com Tk real em Xephyr: **960 passed, 1 skipped em 200.85s**.

### Fase C — PWA

Arquivos funcionais:
- `frontend/src/data/tides/pecem-2026.json`;
- `frontend/src/features/tides/tideTable.ts`;
- `frontend/src/features/tides/tideTable.test.ts`;
- `frontend/src/features/tides/tideDataset.test.ts`;
- `frontend/src/features/tides/TideTableCard.tsx`;
- `frontend/src/pages/WeatherPage.tsx`;
- `frontend/src/pages/pages.test.tsx`;
- `frontend/src/styles/app.css`.

Integração:
- `selectTideView(now)` usa relógio fixo UTC−03, sem depender do timezone do browser;
- `TideTableCard` exibe Hoje/Amanhã, horários, alturas, `Próxima` e fonte;
- 01/01/2027 fica indisponível no bloco Amanhã em 31/12/2026;
- o card `Tábua de maré · DHN` foi adicionado à `WeatherPage` após os blocos meteorológicos existentes;
- nenhum item novo foi adicionado ao BottomNav/Drawer;
- DHN permanece visual e semanticamente separado de WebPilot/Open-Meteo;
- não há `fetch`/API para maré.

Testes/gates:
- focados `tideTable.test.ts + pages.test.tsx`: **35 passed** em 2 arquivos;
- frontend completo final: **50 arquivos / 286 testes passed**;
- `npm run build`: sucesso, incluindo service worker/PWA injectManifest.

### Fase D — Gates cross-repo

- paridade final dos datasets: hashes idênticos `f55961baee0daf9623c3428fd4bb22010d292ac49815d58e5f0503c8a8312677`;
- `git diff --check`: sem erros nos dois repositórios antes do fechamento;
- guarda de escopo API/PWA: nenhum arquivo sob `api/app/`, `api/supabase/` e nenhuma alteração em `frontend/src/api/contract.ts`;
- nenhuma mudança de contrato `MobileSnapshot`;
- regressão A3/WeatherPage coberta pela suíte frontend completa e pelos testes de páginas;
- busca de segredo da superfície nova: sem ocorrências sensíveis;
- não houve migration, backend novo ou transporte runtime de maré.

Warnings conhecidos:
- Vite/Rollup remove comentários de anotação em código de dependência `zod`; build termina com sucesso;
- bundle aponta um chunk acima de 500 kB; warning de tamanho não bloqueante, sem falha de build/PWA.

### Preparação 4.3.1

Consulta read-only de `cirotorres/alertam-releases` via GitHub retornou lista de releases vazia (`[]`). Portanto não existe release pública conflitante neste checkpoint e `4.3.1` continua semanticamente disponível.

Desktop preparado com:
- `src/alertam/version.py` = `4.3.1`;
- testes de versão/update notes coerentes com 4.3.1;
- release notes em `docs/releases/notes/4.3.1.md`.

Resumo das release notes:
- tábua DHN 2026 Desktop/PWA;
- identidade Desktop no `ⓘ`;
- código temporário de 6 dígitos no Conectar Celular já presente na base;
- fluxo de updater já presente na base;
- manutenção dos contratos operacionais/API/Supabase/MobileSnapshot.

Artefatos propositalmente NÃO gerados nesta sessão por dependerem do Windows alvo:
- `dist\AlertaM.exe`;
- `dist\AlertaM.exe.sha256`;
- GitHub Release `v4.3.1`.

Checklist exato de retomada manual, somente depois da aprovação do Revisor:

1. No computador alvo do pai, confirmar que o AlertaM atual abre e que o PWA/mobile atual funciona.
2. Registrar somente o `device_id` atual.
3. Confirmar a existência de `%LOCALAPPDATA%\AlertaM\desktop_identity.json`.
4. Não abrir, copiar ou registrar o segredo contido/protegido no estado local.
5. Se o arquivo não existir, **STOP**: não usar a release genérica como primeira migração; executar antes o fluxo bridge apropriado.
6. No Windows de build, usar o checkout aprovado da versão 4.3.1 e rodar:
   - `.\tasks.ps1 check`
   - `.\tasks.ps1 build`
   - `.\tasks.ps1 hash-release`
7. Conferir `dist\AlertaM.exe` e `dist\AlertaM.exe.sha256`.
8. Confirmar que o build genérico não contém configuração mobile provisionada.
9. Criar manualmente GitHub Release estável `v4.3.1`, sem draft e sem prerelease.
10. Anexar exatamente `AlertaM.exe` e `AlertaM.exe.sha256`.
11. Usar o conteúdo de `docs/releases/notes/4.3.1.md` como body da release.
12. No computador do pai, fechar/reabrir o AlertaM antigo e confirmar `Nova versão 4.3.1 disponível`.
13. Acionar Atualizar e conferir progresso, validação SHA-256, fechamento e respawn automático.
14. Confirmar versão 4.3.1 e janela `AlertaM atualizado` com as notas corretas.
15. Clicar `Entendi` e confirmar comportamento once-only das notas.
16. Confirmar o **mesmo `device_id`** no novo `ⓘ`.
17. Confirmar PWA/mobile funcionando sem novo pareamento.
18. Confirmar que `Conectar Celular` oferece o código temporário de 6 dígitos.
19. Confirmar `🌊 Maré` e os valores do dia no Desktop.
20. Confirmar monitoramento, coleta WebPilot e voz normais.

### Git

Desktop:
- commit local final: `c91ddf5fe6986d60be7f5a87f379ec6d99a6bfd0`;
- mensagem: `feat: entrega tábua DHN e prepara versão 4.3.1`;
- exatamente um commit desta execução;
- worktree limpo após o commit.

API/PWA:
- commit local final: `__API_COMMIT_SELF_HASH__`;
- mensagem planejada: `feat: integra tábua DHN no PWA e documenta SPEC 029`;
- exatamente um commit desta execução.

Não houve push em nenhum repositório.

### Desvios / rulings

1. **Xephyr sob Desktop Commander Remote:** o alvo `make test-ui XEPHYR_N=27` informou inicialmente que o Xephyr não subiu porque o shell remoto não herdava `DISPLAY`/`XAUTHORITY` da sessão GNOME/Wayland e o lifecycle do comando em background não se comportou como no terminal interativo. A causa foi investigada; não houve alteração do harness para mascarar o ambiente. O mesmo Xephyr foi iniciado explicitamente a partir do Xwayland autorizado e a suíte completa foi executada diretamente com `DISPLAY=:30`, resultando em 960 passed/1 skipped. Impacto: nenhum no código; apenas forma equivalente de executar o gate Tk real nesta sessão remota.

2. **Hash do próprio commit API/PWA no handoff:** um arquivo não pode conter de forma estável o SHA do commit que o contém, pois qualquer inserção do SHA altera o próprio commit. Para cumprir simultaneamente “um único commit por repositório” e entregar o hash exato ao Revisor, o commit API/PWA conterá este ledger com um marcador; imediatamente após o commit, somente esse marcador será preenchido no worktree com o SHA real e ficará propositalmente não commitado. Não haverá amend nem segundo commit. Impacto: o status final API/PWA terá apenas esta alteração documental pós-commit, explicitamente identificada.

3. **Etapas Windows/release:** build EXE, checksum de release, inspeção do estado local do PC do pai, publicação e happy path do updater não foram executados, conforme STOP explícito do fluxo. Impacto: permanecem gates manuais posteriores à aprovação independente.

### Confirmações negativas

- nenhum push;
- nenhum deploy;
- nenhuma GitHub Release criada;
- nenhuma migration;
- nenhum smoke no computador do pai;
- nenhuma inspeção manual de `%LOCALAPPDATA%` no PC do pai;
- nenhuma integração da SPEC 028;
- nenhum Cloud;
- nenhum início da SPEC 025 Plan 4 / Maneuver Shadow.

## Pedido de revisão independente

Solicito R1 independente antes de qualquer push, deploy, release ou etapa manual Windows. Revisar especificamente:
- fidelidade integral do dataset DHN 2026 à fonte e paridade Desktop/PWA;
- UTC−03, virada do dia, seleção de próximo evento e fronteira 31/12→2027;
- UI Desktop `ⓘ` + `🌊 Maré`, inclusive foco/tooltip, ausência do ID permanente e ausência de segredo;
- comportamento de fallback quando o dataset Desktop não carrega;
- inclusão do JSON no PyInstaller;
- integração do card na WeatherPage e separação DHN × WebPilot/Open-Meteo;
- ausência de alteração de backend/Supabase/MobileSnapshot/contratos;
- qualidade e suficiência dos testes, incluindo Tk/Xephyr e regressão A3;
- preparação segura da versão/release notes 4.3.1;
- escopo dos dois commits e preservação das alterações pré-existentes.

Próximo passo após este STOP: **Ciro envia o handoff ao Revisor para R1 independente.**
