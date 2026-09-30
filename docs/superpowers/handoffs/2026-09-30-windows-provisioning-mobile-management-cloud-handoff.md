# Handoff — Provisionamento Windows, gestão mobile e direção AlertaM Cloud

**Data:** 2026-09-30  
**Projeto:** AlertaM / API-PWA  
**Objetivo deste handoff:** permitir que a próxima sessão retome o projeto sem redescobrir os testes reais feitos no Windows, as correções locais realizadas e as ideias arquiteturais levantadas depois desses testes.

## 1. Repositórios e branches

Desktop:
- caminho: `/home/ciro/dev/prog/alertamaritimo`
- branch: `develop`
- base remota atual antes destas correções: `e52ec3d feat: automatiza provisionamento mobile por desktop`
- não fazer push sem autorização explícita do usuário.

API/PWA:
- caminho: `/home/ciro/dev/prog/alertamaritimoAPI`
- branch: `feat/api-bootstrap`
- HEAD atual: `21f4ccb Plan: Decisões e estrutura de uma nova arquitetura e melhoria do sistema.`
- essa branch está 1 commit à frente de `origin/feat/api-bootstrap`; esse commit contém a SPEC 025 e seus cinco planos.
- não rebasear, resetar, descartar nem misturar esse trabalho com as correções abaixo.
- não fazer push sem autorização explícita do usuário.

## 2. Teste real feito no Windows

O usuário executou o pipeline em:
`G:\PROGRAMACAO\ProjetosALL\ProjetosPY\Projeto_AlertaM5.0\alertam`

Os repositórios ficaram como irmãos:
- `alertam\`
- `alertamaritimoAPI\`

O provisionamento finalmente criou:
- `DEVICE_ID=pecem-55ee08ee`
- registro no banco: criado
- `.env` Desktop atualizado
- `DEVICE_SECRET` gerado/sincronizado sem aparecer no console.

Depois `.\tasks.ps1 build` gerou um EXE funcional e o EXE exibiu QR Code corretamente.
## 3. Problemas encontrados no primeiro uso do Windows

Foram observados, em ordem:
1. o Desktop só procurava o irmão chamado exatamente `alertamaritimoAPI`; o checkout inicialmente se chamava `alertam-api` e precisou ser renomeado. Isso ainda não foi alterado nesta correção e permanece como possível refinamento futuro;
2. sem Node/npx, o task parava corretamente;
3. no primeiro `npx vercel@latest`, o npm aguardava silenciosamente `Ok to proceed? (y)`, parecendo travado;
4. depois, o `vercel link` falhou por ausência de login; usar `vercel login` diretamente não funcionava porque o CLI não estava instalado globalmente, somente via npx;
5. o `vercel env pull` avisou que Secrets não exportáveis foram gravados como `[SENSITIVE]`;
6. o provisionador era executado como `python scripts/provision_device.py` e no Windows falhou com `ModuleNotFoundError: No module named 'app'`;
7. com chave administrativa inválida/placeholder, o erro útil ao usuário era apenas `401 Unauthorized`.

## 4. Correções implementadas localmente

Desktop, ainda sem commit:
- `tasks.ps1`: usa `npx --yes vercel@latest`, evitando a confirmação inicial do npm;
- valida autenticação com `whoami` e abre `npx --yes vercel@latest login` quando necessário;
- mantém o `link` interativo somente quando `.vercel/project.json` não existe;
- valida `SUPABASE_URL` e uma chave administrativa antes de provisionar;
- reconhece `[SENSITIVE]` mesmo quando o valor veio entre aspas;
- executa o provisionador como módulo: `python -m scripts.provision_device`;
- passa `--admin-env` explicitamente;
- `README.md` foi atualizado com o fluxo real;
- `tests/unit/test_windows_tasks.py` foi atualizado antes da implementação (TDD).

API, ainda sem commit:
- `api/scripts/provision_device.py`: normaliza aspas de credenciais;
- rejeita placeholder `[SENSITIVE]` com mensagem específica;
- se `SUPABASE_SECRET_KEY` for placeholder mas a `SUPABASE_SERVICE_ROLE_KEY` legada for válida, usa a legada;
- respostas 401/403 do Supabase agora explicam que as credenciais administrativas devem ser verificadas, sem imprimir a chave;
- `api/tests/unit/test_provision_device.py` cobre esses casos.
## 5. Evidência de TDD e verificação

RED observado:
- `tests/unit/test_windows_tasks.py` falhou antes das mudanças porque não existiam `npx --yes`, login explícito, validação de env nem execução via `-m`;
- três novos testes de `test_provision_device.py` falharam antes da implementação: placeholder não era rejeitado, fallback legado não ocorria e 401 continuava genérico.

GREEN observado depois:
- teste focado Desktop: passou;
- `api/tests/unit/test_provision_device.py`: 15 testes passaram;
- smoke `uv run python -m scripts.provision_device --help`: exit 0;
- suíte Desktop completa: **544 passed, 63 skipped**;
- `make test` da API: exit 0;
- `git diff --check` nos dois repositórios: exit 0.

Limitação importante:
- o Ubuntu usado para desenvolvimento não possui `pwsh`/Windows PowerShell;
- portanto a sintaxe/fluxo interativo real da Vercel no PowerShell precisa de uma validação final no Windows;
- o teste ideal é um checkout sem `api/.env.prod` e, preferencialmente, sem sessão Vercel prévia, para validar `npx --yes -> whoami -> login -> link -> env pull -> validação -> provisionamento`.

## 6. Estado Git a preservar

Nenhuma das correções desta sessão foi commitada ou enviada ao remoto.
O Desktop contém alterações locais em:
- `tasks.ps1`
- `README.md`
- `tests/unit/test_windows_tasks.py`

A API contém alterações locais em:
- `api/scripts/provision_device.py`
- `api/tests/unit/test_provision_device.py`
- este handoff.

Antes de qualquer commit futuro, fazer `git status` fresco em ambos os repositórios. Não incluir ou reescrever o commit `21f4ccb` acidentalmente e não fazer push sem autorização explícita.
## 7. Identidades: Desktop x aparelho móvel

Hoje existem duas identidades diferentes:
- `public.devices.device_id`: identifica a instância do AlertaM Desktop, por exemplo `pecem-55ee08ee`;
- `public.mobile_installations.installation_id`: UUID individual do navegador/PWA conectado a esse Desktop.

A tabela `mobile_installations` já guarda:
- `installation_id`
- `device_id`
- `active`
- `created_at`
- `last_seen_at`
- `revoked_at`
- `updated_at`.

Por isso vários celulares/tablets ligados ao mesmo Desktop exibem o mesmo `pecem-55ee08ee`, mas cada um tem seu próprio `installation_id`.

Na PWA, `ConfigPage.tsx` mostra hoje `Dispositivo: {pairing.deviceId}`. Isso é tecnicamente o Desktop conectado, não o aparelho móvel. Ideia aprovada conceitualmente para planejamento futuro: renomear essa superfície para algo como **Desktop conectado** ou **AlertaM conectado**.

## 8. O que “Esquecer este aparelho” faz hoje

Não é somente localStorage.
O fluxo atual combina limpeza local e revogação remota:
- pareamento local: `alertam.mobile.pairing.v1`;
- installation id local: `alertam.mobile.installation.v1`;
- push é desativado/limpo em best effort;
- o reset do PairingGate chama `DELETE /api/v1/mobile/session`;
- a API resolve a sessão pelo cookie HttpOnly `alertam_mobile_session`;
- a instalação correspondente é marcada `active=false` e recebe `revoked_at`;
- o cookie de sessão é apagado.

No teste real do iPhone, escanear o QR do novo Desktop não substituiu o pareamento antigo automaticamente. Safari e PWA continuaram mostrando o Desktop Ubuntu. O fluxo que resolveu foi:
1. Config. -> Esquecer este aparelho;
2. escanear novamente o QR do Windows;
3. o novo pareamento passou a atualizar normalmente.

Isso deve orientar a próxima decisão de UX, não ser tratado como defeito de snapshot/API.
## 9. Ideia futura: gestão de aparelhos conectados pelo Desktop

A infraestrutura já permite saber quais instalações pertencem a um `device_id`, mas ainda não existe endpoint/serviço administrativo para listar todas elas nem UI no Desktop.

Direção para brainstorm futuro:
- na tela **Conectar Celular**, mostrar discretamente `Aparelhos conectados: N`;
- permitir abrir uma lista com instalações ativas/revogadas, última atividade e data de criação;
- permitir revogar uma instalação específica;
- considerar um `label` opcional para nomes amigáveis como “iPhone do Ciro” ou “Tablet”, sem depender de fingerprint invasivo;
- o endpoint de administração deve ser autenticado pelo Desktop e nunca virar uma listagem pública para a PWA;
- manter histórico revogado por algum período pode ajudar diagnóstico, em vez de apagar linhas imediatamente.

Também vale planejar um fluxo **Trocar Desktop** na PWA. Quando um QR novo aponta para outro `device_id` e já existe um pareamento ativo, a PWA deveria reconhecer a troca e pedir confirmação, por exemplo:
`Conectado a pecem-antigo. Trocar para pecem-novo?`
Ao confirmar, deve revogar/encerrar a instalação antiga de forma segura e só então promover o novo pareamento. Não implementar automaticamente antes de uma SPEC/design próprio.

## 10. Ideia futura: perfis de provisionamento para gerar vários EXEs no mesmo Windows

Caso real do usuário:
- ele compila todos os EXEs no próprio Windows;
- quer enviar um EXE para o notebook do pai;
- pode querer outro EXE para o computador do trabalho;
- cada computador deve possuir `device_id` e `DEVICE_SECRET` próprios.

O pipeline atual preserva a identidade do `.env` do checkout. Portanto rodar `provision-mobile` repetidamente no mesmo checkout reutiliza a mesma identidade; isso é correto para rebuilds da mesma máquina, mas não atende bem à “fábrica de EXEs” para vários destinos.

Direção a discutir em sessão futura:
- perfis nomeados de destino, por exemplo `meu-pc`, `notebook-pai`, `trabalho-pai`;
- cada perfil guarda sua identidade em armazenamento local ignorado pelo Git;
- o build seleciona explicitamente qual perfil será incorporado;
- evitar sobrescrever silenciosamente a identidade ativa;
- preservar o princípio: um computador de destino = uma identidade Desktop independente.

Não implementar ainda; precisa de brainstorm porque envolve UX de build, armazenamento seguro e risco de gerar/entregar EXE com a identidade errada.
## 11. Ideia central: AlertaM Cloud Collector

A ideia não é colocar a GUI Tk inteira na nuvem. O desenho conceitual é extrair um worker headless que faça a função operacional do Desktop:
- autenticar no WebPilot;
- coletar dados;
- interpretar manobras/clima;
- gerar eventos/snapshot;
- publicar na API;
- continuar ativo 24h sem depender de um computador local ligado.

A PWA continuaria consumindo a API existente. O Desktop local poderia continuar existindo como interface/alternativa.

A autenticação WebPilot no cloud deve permanecer privada ao collector:
- usuário/senha em Secret Manager/variáveis seguras do provedor;
- nunca em Supabase público, PWA, QR Code, snapshot ou logs;
- browser headless/Selenium/Playwright pode ser usado somente para obter/renovar a sessão;
- depois da autenticação, o tráfego normal deve preferir HTTP com cookies;
- expiração deve ser detectada semanticamente, inclusive HTTP 200 que na verdade voltou à tela de login;
- uma única recuperação de autenticação por vez;
- consumidores aguardam nova `session_generation`;
- no máximo uma repetição do request depois da renovação, sem loop infinito de login.

Isso casa diretamente com a SPEC 025 já planejada. A SPEC 025 introduz justamente o coordenador de autenticação WebPilot, cliente HTTP, clima observado e shadow HTTP das manobras. Por isso o Cloud Collector deve ser planejado depois que essa separação estiver comprovada, em vez de copiar o Selenium atual para um servidor.

## 12. Riscos/decisões do Cloud que ainda precisam de brainstorm

- testar se a mesma conta WebPilot aceita sessões simultâneas. Se um login invalida o outro, Cloud e Desktop podem entrar em ping-pong de renovação;
- se sessões não coexistirem, avaliar: conta exclusiva para cloud, cloud como fonte oficial e Desktop consumidor da API, ou somente uma fonte ativa por vez;
- CAPTCHA/2FA/código por e-mail podem exigir estado `requires_operator_action`;
- não usar Vercel Functions como processo persistente para o collector; pensar em worker/container/VPS;
- inicialmente dar ao cloud uma identidade própria, sem fingir ser um Desktop físico;
- evitar dois coletores gerando eventos/push duplicados até existir regra explícita de fonte oficial/failover.

Evolução arquitetural possível depois: introduzir uma entidade superior “Estação / Porto do Pecém”, e fazer a PWA se conectar à estação em vez de a um computador específico. Por trás dessa estação poderiam existir Cloud e Desktops como fontes, com política explícita de prioridade/failover. Isso é ideia, não decisão fechada.
## 13. Ordem sugerida para a próxima sessão

1. Fazer status fresco dos dois repositórios e ler este handoff.
2. Validar no Windows o novo primeiro uso de `provision-mobile`, de preferência com cenário limpo de Vercel/.env.prod.
3. Se o usuário aprovar, revisar e commitar separadamente as correções Desktop e API; **não fazer push sem autorização explícita**.
4. Só depois decidir qual brainstorm vem primeiro:
   - perfis de provisionamento para vários EXEs;
   - gestão/revogação de aparelhos conectados + Trocar Desktop;
   - AlertaM Cloud Collector.
5. Não transformar automaticamente essas ideias em uma única SPEC grande. Elas podem acabar exigindo SPECs separadas.
6. Manter a SPEC 025 como base técnica para qualquer Cloud Collector.

## 14. Segurança e cuidados

- nunca imprimir `DEVICE_SECRET`, `SUPABASE_SECRET_KEY`, cookies WebPilot ou credenciais WebPilot;
- `.env` e `.env.prod` continuam locais/ignorados pelo Git;
- não copiar o `.env` de um Desktop para outro;
- não revogar/destruir registros de `devices` como forma padrão de gestão; para mobiles já existe semântica `active/revoked_at`;
- qualquer futura revogação “do Desktop inteiro” deve ser desenhada de forma explícita e não destrutiva;
- o teste manual Tk/Xephyr e testes físicos iOS continuam responsabilidade final do usuário quando necessários.

## 15. Ponto de retomada

As correções de onboarding Windows estão implementadas e cobertas por testes automatizados no Ubuntu, mas o fluxo PowerShell/Vercel novo ainda precisa da validação manual real no Windows.

As ideias de gestão mobile, troca de Desktop, perfis de build e AlertaM Cloud estão documentadas apenas como direção para brainstorm. Nenhuma delas foi implementada e nenhuma nova SPEC foi aberta nesta sessão.
