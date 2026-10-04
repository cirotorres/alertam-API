Quero executar o fluxo pré-Plan 4: SPEC 029 + preparação completa do piloto do updater Windows.

Use Desktop Commander Remote.

Repositórios canônicos atuais:
- Desktop: /home/ciro/dev/prog/alertamaritimo
- API/PWA: /home/ciro/dev/prog/alertamaritimoAPI

Leia primeiro, integralmente:
1. /home/ciro/dev/prog/alertamaritimoAPI/docs/superpowers/plans/2026-10-04-pre-plan4-spec029-updater-pilot.md
2. /home/ciro/dev/prog/alertamaritimoAPI/docs/superpowers/handoffs/2026-10-04-spec029-tabua-mare-handoff.md
3. /home/ciro/dev/prog/alertamaritimoAPI/specs/029-tabua-mare-dhn-desktop-pwa.md
4. /home/ciro/dev/prog/alertamaritimoAPI/docs/superpowers/plans/2026-10-04-spec029-tabua-mare-desktop-pwa.md

Estado:
- SPEC 025 Plan 3 encerrado.
- Plan 4 está tecnicamente liberado, mas deliberadamente ADIADO até concluir este fluxo.
- Desktop canônico atual: branch develop.
- API/PWA canônico atual: branch feat/api-bootstrap.
- Não iniciar Shadow/Plan 4 nesta sessão.

OBJETIVO DESTA SESSÃO

Quero que você execute autonomamente TODO o trabalho que puder ser concluído sem minha presença física no Windows.

Avance até o último ponto automatizável:
1. implementar integralmente a SPEC 029;
2. normalizar o controle ⓘ do Desktop;
3. validar e integrar o dataset DHN 2026;
4. implementar maré no Desktop e no PWA;
5. rodar todos os testes/gates automatizados;
6. revisar o escopo e corrigir problemas encontrados;
7. integrar a implementação sobre as branches atuais do projeto, sem reabrir trabalhos antigos;
8. deixar a árvore pronta para eu, posteriormente no Windows, apenas executar a preparação/publicação manual da release e o smoke manual do updater.

NÃO pare entre Tasks/Fases apenas para pedir autorização de continuidade.
Execute Fases A → B → C → D completas, respeitando os STOPs técnicos reais.
Só pare antes de qualquer passo que dependa da minha presença física ou decisão manual de publicação.

BRANCHES / INTEGRAÇÃO

Trabalhe integrado ao estado canônico atual:

Desktop:
- base autoritativa: develop

API/PWA:
- base autoritativa: feat/api-bootstrap

Você pode criar branches/worktrees de implementação para isolamento, mas ao final o resultado deve estar reconciliado com as bases atuais, sem rebaixar funcionalidades já existentes.

Preserve como autoritativos:
- MobileSnapshot v1|v2;
- WeatherPage A3;
- hotfix de acompanhamentos/fundeio já integrada;
- pareamento/código temporário atual;
- updater/identidade persistente existentes;
- documentação de roadmap já presente.

Não usar reset/clean destrutivo.
Nunca usar git add .
Não tocar em docs/superpowers/strategy/ salvo se estritamente necessário e previamente justificado.

COMMIT

Quero UM ÚNICO COMMIT FINAL por repositório modificado.

Como Desktop e API/PWA são repositórios Git separados, isso significa:
- no máximo 1 commit final no Desktop;
- no máximo 1 commit final no API/PWA.

Não criar commits intermediários por Task/Fase.
Não fazer squash de histórico alheio.
Antes de cada commit:
- revisar git status;
- revisar diff;
- rodar os gates finais;
- stage apenas dos arquivos pertencentes à SPEC 029 / fluxo pré-Plan 4.

Mensagens de commit em português-BR e descrevendo a entrega completa.

NÃO FAZER PUSH.
NÃO FAZER MERGE REMOTO.
NÃO CRIAR RELEASE.
NÃO FAZER DEPLOY MANUAL ALÉM DO QUE JÁ ESTIVER AUTOMATICAMENTE ACOPLADO A UM PUSH — e como push está proibido, nenhum deploy deve ocorrer nesta sessão.

FONTE DHN

Fonte:
PDF DHN 2026 "16 - TERMINAL PORTUÁRIO DO PECÉM  58 - 60.pdf"

SHA-256 esperado:
dad5ef1a49ddf499c25dce5488612e521c4be614dc1c465a1f6c1ecf2b49b6bd

Antes de pedir ao usuário para reanexar:
- procure se o PDF está disponível nos arquivos da conversa/Project/Library acessíveis nesta sessão;
- procure também em paths locais plausíveis já autorizados do projeto;
- não use fonte web substituta.

Se o PDF realmente não puder ser obtido, este é um STOP real da Task 1: registre exatamente o que falta e pare sem improvisar dados.

FASE A — DATASET

Executar integralmente a Task 1:
- validar SHA-256;
- gerar JSON canônico;
- 365 datas;
- 3–4 eventos conforme fonte;
- preservar altura negativa;
- validar amostras obrigatórias;
- copiar byte a byte Desktop/PWA;
- provar hash igual;
- testes focados verdes.

FASE B — DESKTOP

Executar integralmente a Task 2:
- Hoje/Amanhã em UTC−03;
- próximo evento;
- loader offline;
- remover ID permanente;
- normalizar controle ⓘ:
  - compacto;
  - focável;
  - alinhado visualmente;
  - hover/foco mostra produto, versão, device_id e autoria;
  - nunca segredo;
- adicionar 🌊 Maré;
- janela única/reutilizável;
- incluir JSON no PyInstaller;
- testes unitários;
- testes Tk/Xephyr disponíveis no ambiente;
- regressão Desktop completa.

FASE C — PWA

Executar integralmente a Task 3:
- helper temporal equivalente;
- card "Tábua de maré · DHN" em /tempo;
- Hoje/Amanhã;
- próximo evento;
- manter WebPilot/Open-Meteo separados;
- nenhum novo item de navegação;
- nenhuma mudança backend/Supabase/MobileSnapshot;
- testes focados;
- frontend completo;
- npm run build.

FASE D — CROSS-REPO / FECHAMENTO

Executar integralmente a Task 4:
- paridade byte-a-byte dos datasets;
- guard negativo de escopo;
- diff-check;
- buscas de segredo;
- regressão A3;
- gates completos;
- auto-revisão final;
- corrigir quaisquer problemas encontrados dentro do escopo;
- atualizar a documentação de execução/handoff com evidências reais.

PREPARAÇÃO PARA A RELEASE PILOTO

Quero que você deixe também preparado tudo que NÃO exige minha presença no Windows.

Planejamento da primeira release genérica:
- versão alvo: 4.3.1, somente se continuar semanticamente válida e não existir release pública maior;
- confirmar read-only se cirotorres/alertam-releases continua sem release conflitante;
- preparar o arquivo:
  docs/releases/notes/4.3.1.md
  com um rascunho objetivo das novidades da SPEC 029 e melhorias já presentes que o usuário do Desktop perceberá após atualizar;
- NÃO publicar;
- NÃO alterar para uma versão diferente sem registrar motivo.

Se a alteração de src/alertam/version.py para 4.3.1 for necessária para deixar o checkout realmente pronto para o build manual posterior, faça isso dentro do commit final Desktop.
Caso o plano/regras do updater indiquem que a versão só deve ser alterada no momento da publicação, documente o ruling e deixe o passo explícito para a retomada no Windows.

STOP FINAL OBRIGATÓRIO

Pare SOMENTE quando o próximo passo exigir minha presença física/manual no Windows.

O handoff final deve me entregar exatamente:
1. branches/HEADs finais;
2. hashes dos commits locais criados;
3. status limpo ou explicar qualquer arquivo propositalmente não commitado;
4. resultado dos testes Desktop;
5. resultado Xephyr/Tk;
6. resultado frontend;
7. resultado build PWA;
8. hash/paridade do dataset DHN;
9. estado da versão preparada;
10. conteúdo/caminho das release notes;
11. checklist exato para eu executar quando estiver no Windows;
12. comando(s) exatos para build/hash da release;
13. passos manuais no GitHub Release;
14. passos de teste no computador do meu pai;
15. indicação explícita de que NÃO houve push, deploy, migration ou release.

NÃO executar nesta sessão:
- publicação GitHub Release;
- push;
- teste manual no PC do pai;
- inspeção manual de %LOCALAPPDATA% no PC do pai;
- smoke humano de atualização;
- Plan 4/Shadow;
- Cloud;
- SPEC 028 automatizada.

O próximo ponto após seu STOP deve ser algo que dependa realmente de mim estar no Windows.


REVISAO INDEPENDENTE OBRIGATORIA

A auto-revisao final nao encerra o trabalho.

Use este documento como ledger oficial da execucao:
- /home/ciro/dev/prog/alertamaritimoAPI/docs/superpowers/handoffs/2026-10-04-spec029-tabua-mare-handoff.md

Ao concluir as Fases A-D e toda a preparacao automatizavel da 4.3.1:

1. anexe no handoff uma secao completa:
   "Execucao SPEC 029 + preparacao 4.3.1 — Executor — <data>";

2. registre:
   - estado inicial/base;
   - arquivos alterados;
   - evidencias por fase;
   - hashes do dataset;
   - testes e builds com numeros reais;
   - diffs/guardas de escopo;
   - commits locais finais;
   - estado da versao 4.3.1;
   - release notes preparadas;
   - desvios/rulings;
   - itens que dependem fisicamente do Windows;

3. finalize o handoff com:
   "Pedido de revisao independente";

4. PARE nesse ponto.

Nao interpretar auto-revisao como aprovacao.
Nao fazer push, deploy, release, smoke manual ou Plan 4 antes do parecer do Revisor.

O proximo passo depois do seu STOP deve ser:
"Ciro envia o handoff ao Revisor para R1 independente."
