# SPEC 024 — Tempo operacional da manobra e refinamentos de UX pós-SPEC 023

**Status:** Design aprovado; aguardando revisão formal da SPEC  
**Data:** 2026-09-29  
**Escopo:** AlertaM Desktop + API FastAPI/Supabase + PWA React/Vite  
**Origem:** validação humana da SPEC 023 em operação real

## 1. Contexto

A SPEC 023 implementou Ship Tracking no Desktop e no PWA, com timeline unificada,
favoritos persistentes, eventos de manobra e eventos de acompanhamento. Após os
testes automatizados e o gate Tk/Xephyr, a validação real revelou uma diferença
semântica importante entre o horário operacional do navio e o horário em que o
AlertaM detecta uma atualização da planilha.

O caso de referência é o navio **FERNAO DE MAGALHAES**, IMO **9603221**.

Na atracação de 29/09/2026:
- POB confirmado: **02:30**;
- primeira observação da conclusão pelo AlertaM: **10:45:35**;
- confirmação da conclusão pelo debounce: **10:46:36**;
- ingestão do evento na API: **10:46:39**;
- valor operacional atual da coluna ATRAC/FUND/ETA: **ATRAC: 29/09 - 05:28**.

Logo, 10:46 − 02:30 não representa a duração real da movimentação.
O intervalo operacional relevante nesse caso é **02:30 → 05:28 = 2h58**.

## 2. Objetivos

1. Separar claramente o relógio operacional do navio do relógio de observação do AlertaM.
2. Persistir o marco operacional conhecido no próprio ManeuverEvent.
3. Exibir como informação principal o que aconteceu com o navio.
4. Manter horários de observação do sistema como informação secundária e auditável.
5. Aplicar a mesma semântica no Desktop e no PWA.
6. Corrigir problemas de toque, rolagem, navegação e identificação de navios acompanhados.
7. Preservar compatibilidade com eventos antigos e com versões anteriores durante o rollout.

## 3. Não objetivos

- Não inferir quando a planilha foi efetivamente editada por um operador.
- Não chamar 05:28 → 10:45 de “atraso da planilha”.
- Não reconstruir retrospectivamente horários operacionais de eventos antigos.
- Não criar nova fonte externa de dados marítimos.
- Não mudar as regras de confirmação/debounce da SPEC 021/022.
- Não alterar regras de Web Push, preferências ou instalação da SPEC 023.
- Não criar um novo subsistema de histórico no Desktop.

## 4. Vocabulário obrigatório

**Horário operacional:** horário declarado pela própria planilha para um marco do navio,
como ATRAC: 29/09 - 05:28.
**Primeira observação:** primeira coleta em que o AlertaM detectou um estado candidato
a mudança. Corresponde a first_observed_at.

**Confirmação pelo AlertaM:** coleta que confirmou a mudança após as regras de debounce.
Corresponde a occurred_at.

**Ingestão:** momento em que a API persistiu o evento. Corresponde a ingested_at.

Esses conceitos não podem ser apresentados ao usuário como equivalentes.

## 5. Evolução do contrato ManeuverEvent

Adicionar dois campos opcionais e retrocompatíveis:

    operational_at: string | null
    operational_marker: string | null

operational_at deve ser timestamp ISO 8601 com timezone.

operational_marker identifica o marcador que originou o horário operacional.
Nesta SPEC, o único valor aceito além de null é ATRAC para conclusão de atracação.

Os dois campos formam um par: ambos devem estar preenchidos ou ambos devem ser null.
Eventos antigos ou eventos sem fonte operacional confiável usam ambos como null.

A persistência continua no event_payload JSONB de maneuver_events.
**Não é necessária migration SQL para esses campos.**

Os contratos Desktop, API e Zod do PWA devem aceitar ausência dos campos e
normalizá-los para null.

## 6. Captura no Desktop
Para uma ATRACACAO que passa para ATRACADO, o Desktop deve examinar o valor
da coluna hoje transportada como Navio.eta.

Formato observado e suportado inicialmente:

    ATRAC: DD/MM - HH:MM

Quando o valor for válido:
- normalizar para timestamp aware em America/Fortaleza;
- como o texto não contém ano, reutilizar a regra do POB: testar ano anterior, atual e seguinte e escolher o instante de calendário mais próximo de observed_at;
- preencher operational_at;
- preencher operational_marker = "ATRAC".

O valor precisa participar do fingerprint do candidato terminal quando disponível.
Assim, a mesma conclusão e o mesmo horário operacional precisam permanecer estáveis
durante a confirmação por debounce.

Se o valor estiver ausente, malformado ou não corresponder ao marcador esperado,
a conclusão continua válida, mas operational_at e operational_marker ficam nulos.

Para DESATRACACAO, esta SPEC **não inventa** um horário operacional terminal.
Enquanto não houver marcador confiável equivalente na fonte, esses campos permanecem
nulos na conclusão da desatracação.

FUND e outros marcadores poderão ser incorporados futuramente somente após
ser estabelecida sua relação semântica com uma manobra específica.

## 7. Duração da movimentação
A duração operacional deve ser calculada somente quando existirem:
- pob_at;
- operational_at;
- timestamps válidos e aware;
- operational_at maior ou igual a pob_at.

Fórmula:

    tempo_da_movimentacao = operational_at - pob_at

No caso de referência:

    POB                  29/09 02:30
    ATRAC na planilha    29/09 05:28
    Tempo da movimentação      2h58

occurred_at não pode mais ser usado para calcular “Diferença para o POB”
na conclusão da manobra.

Eventos legados sem operational_at não mostram uma duração operacional.
A UI deve preferir ausência explícita a apresentar um número semanticamente incorreto.

## 8. Apresentação no PWA

Na ficha/timeline de uma conclusão com horário operacional disponível, a hierarquia é:

1. **Atracação concluída**
2. POB vigente
3. ATRAC informado na planilha
4. **Tempo da movimentação**
5. seção secundária “Monitoramento do AlertaM”
6. primeira observação
7. confirmação pelo AlertaM
Exemplo:

    Atracação concluída

    POB                     02:30
    ATRAC na planilha       05:28
    Tempo da movimentação   2h58

    Monitoramento do AlertaM
    Primeira observação     10:45
    Confirmação             10:46

Não usar “horário aproximado da conclusão” para occurred_at quando houver
operational_at: são conceitos diferentes.

Quando o horário operacional não existir, exibir os horários de monitoramento sem
fabricar duração. Uma nota curta pode informar “Horário operacional não disponível
neste registro.” quando isso for necessário para evitar ambiguidade.

Atualizações de POB continuam podendo mostrar a diferença entre POB anterior e novo;
essa regra é distinta da duração da movimentação.

## 9. Apresentação no Desktop

A janela existente de detalhes da manobra deve adotar a mesma hierarquia semântica
do PWA. Não criar uma segunda janela para o mesmo ciclo.

A janela existente “⭐ Acompanhados” já possui “Linha do tempo local”.
Ela deve continuar sendo o ponto de entrada do histórico de um navio acompanhado,
mas suas projeções devem usar os novos resumos operacionais quando houver
ManeuverEvent relacionado.

O objetivo é equivalência de interpretação entre Desktop e PWA, não identidade visual.
## 10. Estrela de acompanhamento no PWA

Nas listas operacionais de navios, um navio acompanhado neste aparelho deve possuir
uma ★ discreta junto ao nome.

A estrela:
- deriva exclusivamente do estado do TrackingProvider;
- não substitui o nome do navio;
- não muda status operacional;
- não interfere nos pulsos vermelho/verde;
- usa amarelo/âmbar para diferenciá-la do restante da tipografia.

Não é necessário adicionar a estrela a cada card histórico de evento.

## 11. Estrela no mapa do Desktop

O marcador ★ já existente sobre o sprite do navio deixa de ser branco e passa a
usar amarelo/âmbar visível.

Essa mudança é estritamente visual. Pulso de confirmação, pulso de alerta, situação
do navio e regras do mapa permanecem independentes.

## 12. Alertas/Histórico: superfície de rolagem

Nas páginas mobile de Alertas, Histórico e Acompanhados, o grande card externo não
deve ser a única área capaz de receber a rolagem.

A superfície útil da página deve funcionar como o contêiner de scroll contínuo.
Os cards de eventos/ciclos permanecem como unidades visuais internas.

A mudança deve ser localizada nessas páginas/modificadores e não transformar
indiscriminadamente todas as telas que reutilizam .page-stack.
A aparência geral pode permanecer próxima da atual; a prioridade é eliminar zonas
mortas de gesto nas margens do card externo.

## 13. Bottom sheets e prioridade de toque

Quando BottomSheetFrame estiver aberto:
- a página por trás não pode rolar;
- a página por trás não pode receber gesto de swipe;
- a navegação inferior não pode capturar o toque por baixo da sheet;
- o backdrop deve cobrir a viewport interativa;
- a própria sheet mantém scroll vertical interno;
- o gesto de fechar para baixo continua funcionando quando iniciado em condição válida.

A solução deve ser centralizada no componente compartilhado, com bloqueio de
scroll/overscroll apropriado para Safari/iOS PWA.

O fechamento deve restaurar exatamente o estado de scroll da tela de fundo.

Acessibilidade existente (role="dialog", aria-modal, foco e fechamento) deve ser
preservada ou melhorada.

## 14. Footer em Acompanhados

A rota /acompanhados deve manter o footer de navegação inferior visível.

Como “Acompanhados” não é uma das cinco tabs do footer, nenhuma opção deve ser marcada
falsamente como a página atual enquanto essa rota estiver aberta.

Isso permite navegar diretamente de Acompanhados para Manobras, Atracação,
Desatracação, Fundeados ou Tempo sem retornar primeiro pelo drawer.
## 15. Compatibilidade e rollout

Eventos existentes sem os novos campos continuam válidos.

Não haverá backfill a partir do snapshot atual, pois isso poderia associar a um
evento passado um valor observado somente depois.

Ordem de publicação:
1. API/PWA aceitando e exibindo campos opcionais;
2. Desktop atualizado passando a emitir os campos;
3. validação cross-repo com evento real/sintético.

Nenhuma variável de ambiente nova é necessária.

## 16. Estratégia de testes — TDD obrigatório

### Desktop

Cobrir antes da implementação:
- parse válido de ATRAC: DD/MM - HH:MM;
- valor inválido retorna ausência, sem impedir conclusão;
- candidato terminal exige estabilidade do horário operacional;
- serialização/deserialização aceita eventos antigos sem os campos;
- duração usa operational_at - pob_at;
- occurred_at - pob_at não é apresentado como duração;
- detalhes Desktop exibem hierarquia operacional e monitoramento;
- estrela do mapa permanece funcional e usa cor não branca;
- timeline local do acompanhado recebe resumo coerente.

### API
Cobrir:
- POST aceita novos campos opcionais;
- payload legado continua aceito;
- feed e detalhe devolvem os campos sem perda;
- idempotência permanece baseada no event_id;
- nenhuma alteração de schema SQL é exigida.

### PWA

Cobrir:
- Zod normaliza campos legados para null;
- conclusão com operational_at exibe 2h58 no fixture equivalente ao FERNAO;
- conclusão sem horário operacional não exibe duração falsa;
- listas mostram ★ somente para navio acompanhado;
- /acompanhados mantém BottomNav sem tab falsamente ativa;
- Alertas/Histórico/Acompanhados rolam pela superfície útil;
- BottomSheet aberta impede scroll e toque no conteúdo de fundo;
- scroll interno e swipe-to-dismiss da sheet continuam funcionando.

### E2E / cross-repo

Fixture de aceitação principal:

    Navio: FERNAO DE MAGALHAES
    IMO: 9603221
    POB: 29/09 02:30
    ATRAC: 29/09 05:28
    first_observed_at: 29/09 10:45:35 -03
    occurred_at: 29/09 10:46:36 -03
Resultado esperado:
- duração mostrada: **2h58**;
- 10:45 identificado como primeira observação;
- 10:46 identificado como confirmação do AlertaM;
- nenhum texto sugere que 10:46 foi o horário real da atracação.

## 17. Critérios de aceite

A SPEC estará concluída quando:
- Desktop, API e PWA preservarem operational_at/operational_marker;
- FERNAO de referência produzir semanticamente 02:30 → 05:28 → 2h58;
- eventos antigos permanecerem legíveis;
- Desktop e PWA separarem informação operacional de monitoramento;
- estrela mobile identificar acompanhados nas listas;
- estrela Desktop estiver amarela/âmbar;
- footer permanecer em Acompanhados;
- sheets bloquearem interação do fundo no iOS/PWA;
- Alertas/Histórico não possuírem zona morta de rolagem;
- suítes focadas, completas e smoke cross-repo passarem;
- validação manual mobile e Tk/Xephyr confirmar o comportamento.

## 18. Decisões explícitas

A SPEC 023 permanece como implementação original concluída.
Esta SPEC registra refinamentos descobertos durante sua validação real.

A prioridade de UX é: **o que aconteceu com o navio primeiro; quando o AlertaM
descobriu isso depois**.
