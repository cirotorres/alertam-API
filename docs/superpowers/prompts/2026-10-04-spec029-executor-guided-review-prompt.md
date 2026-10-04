Quero que você execute integralmente o fluxo pré-Plan 4 da SPEC 029 e deixe o trabalho pronto para revisão independente.

Use Desktop Commander Remote.

Repositórios:
- Desktop: /home/ciro/dev/prog/alertamaritimo
- API/PWA: /home/ciro/dev/prog/alertamaritimoAPI

Leia primeiro, integralmente e nesta ordem:
1. /home/ciro/dev/prog/alertamaritimoAPI/docs/superpowers/plans/2026-10-04-pre-plan4-spec029-updater-pilot.md
2. /home/ciro/dev/prog/alertamaritimoAPI/docs/superpowers/handoffs/2026-10-04-spec029-tabua-mare-handoff.md
3. /home/ciro/dev/prog/alertamaritimoAPI/specs/029-tabua-mare-dhn-desktop-pwa.md
4. /home/ciro/dev/prog/alertamaritimoAPI/docs/superpowers/plans/2026-10-04-spec029-tabua-mare-desktop-pwa.md

Contexto:
- SPEC 025 Plan 3 encerrado.
- Plan 4 está tecnicamente liberado, mas temporariamente ADIADO.
- Primeiro devemos concluir SPEC 029 + preparação da release piloto 4.3.1.
- Não iniciar Shadow/Plan 4 nesta sessão.
- Não iniciar Cloud.
- Não integrar SPEC 028 nesta sessão.

Bases autoritativas:
- Desktop: develop
- API/PWA: feat/api-bootstrap

Antes de alterar código:
- confira branch, HEAD e git status dos dois repositórios;
- identifique alterações pré-existentes e preserve-as;
- crie branches/worktrees isolados se necessário;
- não use reset/clean destrutivo;
- nunca use git add .

Execução:
- avance autonomamente por Fase A -> B -> C -> D;
- não pare entre tasks apenas para pedir autorização;
- siga TDD;
- corrija problemas encontrados dentro do escopo;
- execute todos os gates automatizáveis disponíveis.

Fase A:
- validar PDF DHN 2026;
- SHA-256 esperado:
  dad5ef1a49ddf499c25dce5488612e521c4be614dc1c465a1f6c1ecf2b49b6bd
- gerar dataset 2026;
- 365 datas;
- preservar 3/4 eventos e alturas negativas;
- JSON Desktop/PWA byte-idêntico;
- validar amostras normativas.

Se o PDF não estiver acessível:
- tente localizar primeiro nos arquivos disponíveis e paths autorizados;
- não substitua por fonte web;
- se realmente ausente, STOP técnico e peça o PDF.

Fase B Desktop:
- Hoje/Amanhã UTC-03;
- próximo evento;
- loader offline;
- remover ID permanente;
- normalizar controle ⓘ;
- hover/foco: produto, versão, device_id, autoria;
- nunca segredo;
- adicionar 🌊 Maré;
- janela única/reutilizável;
- incluir JSON no PyInstaller;
- testes unitários/Tk/Xephyr;
- regressão completa Desktop.

Fase C PWA:
- helper temporal equivalente;
- card "Tábua de maré · DHN" na WeatherPage;
- manter WebPilot/Open-Meteo separados;
- sem novo item de navegação;
- não alterar backend/Supabase/MobileSnapshot;
- testes focados/full;
- npm run build.

Fase D:
- paridade dos datasets;
- diff-check;
- guardas de escopo;
- busca de segredo;
- regressão A3;
- gates finais;
- auto-revisão.

Integração e commits:
- integrar sobre o estado canônico atual;
- preservar funcionalidades existentes;
- um único commit final por repositório modificado;
- no máximo 1 commit Desktop + 1 commit API/PWA;
- mensagens em português-BR;
- não criar commits intermediários;
- não fazer push;
- não fazer deploy;
- não criar release.

Preparação 4.3.1:
- confirmar read-only se cirotorres/alertam-releases continua sem release conflitante;
- preparar docs/releases/notes/4.3.1.md;
- definir src/alertam/version.py como 4.3.1 se isso for necessário para deixar o checkout pronto para o build manual posterior;
- se decidir não alterar ainda, registrar ruling claro;
- não gerar/publicar release nesta sessão.

Documento obrigatório de fechamento:
Use este handoff como ledger oficial:
- /home/ciro/dev/prog/alertamaritimoAPI/docs/superpowers/handoffs/2026-10-04-spec029-tabua-mare-handoff.md

Ao final, anexe nele:
- estado inicial;
- evidências Fases A-D;
- arquivos alterados;
- hashes;
- resultados reais dos testes;
- commits locais finais;
- estado da versão 4.3.1;
- release notes;
- desvios/rulings;
- checklist do que ainda depende fisicamente do Windows.

Finalize com uma seção:
"Pedido de revisão independente"

STOP FINAL:
Depois de escrever o pedido de revisão independente, PARE.

Não faça:
- push;
- deploy;
- GitHub Release;
- smoke manual;
- teste no PC do pai;
- Plan 4;
- Cloud.

O próximo passo deverá ser:
"Ciro envia o handoff ao Revisor para R1 independente."
