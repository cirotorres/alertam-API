# SPEC 024 — mapa de execução

**Spec:** `specs/024-operational-maneuver-timing-ux-refinements.md`

A SPEC 024 será executada em três planos. A divisão evita misturar a evolução
do contrato temporal com correções de gesto mobile e refinamentos visuais do Desktop.

## Ordem recomendada

1. `2026-09-29-spec024-operational-timing-contract.md`
   - captura ATRAC real no Desktop;
   - evolui ManeuverEvent sem migration;
   - preserva o contrato na API;
   - apresenta duração operacional correta no PWA.

2. `2026-09-29-spec024-mobile-ux.md`
   - estrela nos navios acompanhados;
   - footer em Acompanhados;
   - superfície contínua de scroll;
   - bottom sheets com prioridade real de toque.

3. `2026-09-29-spec024-desktop-ux.md`
   - estrela amarela no mapa;
   - detalhes de manobra com semântica operacional;
   - timeline local de Acompanhados enriquecida.

## Dependências

O Plano 1 define os campos `operational_at` e `operational_marker`.
O Plano 2 não depende desses campos e pode ser revisado isoladamente.
O Plano 3 depende do Plano 1 para mostrar o horário ATRAC e a duração real.

## Rollout de produção

A ordem de desenvolvimento acima não altera a ordem segura de publicação: primeiro API/PWA aceitando os campos opcionais; depois Desktop emitindo-os. Nenhum deploy faz parte destes planos sem autorização operacional explícita.

## Gates globais

- TDD obrigatório em cada task.
- Eventos legados continuam válidos.
- Nenhum backfill de horário operacional.
- Sem nova migration SQL.
- Sem nova variável de ambiente.
- `occurred_at - pob_at` nunca volta a representar duração da movimentação.
- Push, tracking e debounce existentes não mudam de regra.
- Não fazer push sem autorização explícita de Ciro.
