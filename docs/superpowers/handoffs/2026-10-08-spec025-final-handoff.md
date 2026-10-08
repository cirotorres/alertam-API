# SPEC 025 — Gate Shadow concluído; handoff de encerramento documental (2026-10-08)

**Status:** gate técnico MET; aceite humano contextual para iniciar trilha de desenvolvimento SPEC 027. Finalização documental/integracao de branch pendentes. Sem cutover.
**Desktop:** /home/ciro/dev/prog/alertamaritimo — feat/spec025-plan5-shadow-evidence-gate, HEAD atualizado 9e5b5e1 (documentos R2 e gate commitados); develop abe386f, integração pendente.
**API/PWA:** /home/ciro/dev/prog/alertamaritimoAPI.
**Handoff de evidência detalhado:** /home/ciro/dev/prog/alertamaritimo/docs/superpowers/handoffs/2026-10-06-spec025-plan5-shadow-evidence-gate-handoff.md

## Evidência operacional real — ponto de aceite

- Início: 2026-10-07 01:49:51 UTC.
- Último ciclo no aceite: 2026-10-08 03:42:52 UTC (25h53m observados).
- 1501 ciclos comparáveis; 1499 equivalentes; últimos 109 limpos.
- Nenhuma falha técnica, nenhum skip administrativo, nenhum overflow crítico.
- Cobertura obrigatória completa: ATRACADO, FUNDEADO, PREVISTO, POB, entrada/saída, campos vazios; também berth_change. Shift opcional não observado.
- 2 ciclos divergentes, 4 registros de campos, todos ocorrências únicas.
- Registro A em 07/10 02h35 (Fortaleza), IMO 9471898: mudança simultânea de ATRACADO para DESATRACANDO e deslocamento de horário entre ETB/ETS e POB.
- Registro B em 07/10 22h48 (Fortaleza), IMO 9529530: HTTP inclui TAURUS I na lista de rebocadores antes do Selenium; usuário confirmou que o Desktop depois também exibiu os 3 rebocadores.
- Hipótese aceita para revisão: **diferença temporal de amostragem durante alteração operacional do WebPilot**. Muito plausível, mas **não comprovada** com timestamps do servidor. Não declarar prova de ausência de bug.

## Revisão humana e gate

Em 2026-10-08, o usuário autorizou documentar essas ocorrências como provável delay e **seguir com as próximas etapas do AlertaM Cloud**, sem parar a coleta Shadow. As quatro divergências foram marcadas explained individualmente, cada uma com justificativa sanitizada e indicação explícita de incerteza. Isso não altera contadores nem histórico de evidência.

Estado após os comandos: **Gate técnico MET**; 0 críticas abertas; 4 explicadas; relatório diz “Cutover: aguardando aprovação humana”. A decisão humana aqui aceita **reuso do collector como fundamento da implementação SPEC 027**, não autoriza cutover local Selenium→HTTP nem ativação operacional Cloud em produção.

## Residual de observabilidade (prioridade alta)

ShadowMetricsStore._record_divergence, quando encontra uma assinatura já classificada explained, apenas incrementa occurrences/last_seen e **não reabre** a crítica. Logo, uma reincidência idêntica pode continuar com status explained. Requer hotfix TDD e revisão independente para reabrir futuras ocorrências da mesma assinatura e preservar o histórico de explicação. Enquanto runtime antigo permanecer ativo, conferir contadores de occurrences e last_seen, além das críticas abertas. Não interromper o Shadow sem coordenação com o operador.

## Situação de implementação

- Plan 1/A1: concluído e integrado.
- Plan 2/A2: concluído e integrado.
- Plan 3/A3: concluído e integrado.
- Plan 4: integrado em Desktop/develop.
- Plan 5 Tasks 1–4: implementação revisada R2, suite previamente verde; branch ainda não integrada a develop.
- Plan 5 Task 5: janela real >24h e thresholds completos; duas ocorrências isoladas explicadas sob hipótese temporal, evidência retida.
- Plan 5 Task 6: status/roadmap já commitados no API/PWA (3253e44) e Desktop (9e5b5e1), **revisão de fechamento e integração Desktop/develop ainda pendentes**.

## Autorizações e proibições

- Permitido: iniciar planejamento detalhado e execução revisada por etapas C1, C2, C3 da SPEC 027 a partir da base correta, sob TDD e aprovações de cada gate; manter Shadow observacional.
- **Não autorizado nesta revisão:** deploy Cloud operacional com WebPilot real, transferir cookies/SessionLease reais, migrations em produção, publicar source=cloud, failover/failback real, mudar autoridade Desktop, cutover Selenium local.
- Nenhum commit, merge, push, deploy, restart ou reset foi executado neste fechamento documental.
