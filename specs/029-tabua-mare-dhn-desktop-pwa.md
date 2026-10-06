# SPEC 029 — Tábua de maré DHN no Desktop e PWA + identidade discreta do Desktop

| Campo | Valor |
|---|---|
| Status | Implementado e integrado em `feat/api-bootstrap`; validações Windows/release tratadas separadamente no fluxo pré-Plan 4 |
| Criado em | 2026-10-04 |
| Atualizado em | 2026-10-04 |
| Evidência de conclusão | `docs/superpowers/handoffs/2026-10-04-spec029-tabua-mare-handoff.md` |

## Objetivo

Disponibilizar ao operador do AlertaM a tábua de maré oficial do Terminal Portuário do Pecém para
**hoje e amanhã**, com leitura rápida no Desktop e na página **Tempo e mar** do PWA, sem depender de
rede em runtime.

No Desktop, aproveitar o mesmo refinamento para retirar o ID AlertaM permanente abaixo de
`Modo compacto` e substituí-lo por um controle discreto `ⓘ` com versão, `device_id` e autoria.

## Fonte normativa dos dados

Fonte fornecida pelo usuário:

- **TERMINAL PORTUÁRIO DO PECÉM (ESTADO DO CEARÁ) — 2026**;
- DHN;
- latitude 03° 32'.1 S;
- longitude 38° 47'.9 W;
- fuso UTC −03:00;
- Nível Médio 1,56 m;
- Carta 711;
- PDF: `16 - TERMINAL PORTUÁRIO DO PECÉM  58 - 60.pdf`;
- SHA-256 do PDF recebido: `dad5ef1a49ddf499c25dce5488612e521c4be614dc1c465a1f6c1ecf2b49b6bd`.

A tabela anual de 2026 é a única fonte de valores desta SPEC. Não interpolar, recalcular ou obter
valores alternativos da internet.

## Decisão principal

A tábua DHN será convertida **uma única vez** para JSON estático normalizado e empacotada nos dois
clientes:

- Desktop Python;
- PWA Vite.

O PDF **não será lido em runtime**.

A API, Supabase, `MobileSnapshot`, WebPilot e Open-Meteo não participam do transporte desses dados.

A duplicação do JSON entre os dois repositórios é aceita porque:
- o dado é anual, pequeno e imutável;
- Desktop precisa funcionar offline;
- PWA precisa funcionar mesmo sem novo endpoint;
- um gate de paridade byte-a-byte/hash impede divergência entre as duas cópias.

## Relação com o roadmap atual

Esta SPEC é uma **trilha lateral de UX operacional**.

Ela:
- não altera a SPEC 025;
- não bloqueia nem é pré-requisito do Plan 4/Shadow;
- não altera a SPEC 027/Cloud;
- não cria schema de snapshot novo;
- não muda freshness meteorológico;
- não transforma a tábua DHN em medição em tempo real.

A próxima etapa crítica da SPEC 025 continua sendo o Plan 4 — Maneuver HTTP Shadow.

## Modelo de dados estático

Formato normalizado v1:

```json
{
  "schema_version": 1,
  "station": "TERMINAL PORTUÁRIO DO PECÉM",
  "year": 2026,
  "timezone_offset": "-03:00",
  "source": {
    "publisher": "DHN",
    "chart": "711",
    "mean_level_m": 1.56,
    "source_pdf_sha256": "dad5ef1a49ddf499c25dce5488612e521c4be614dc1c465a1f6c1ecf2b49b6bd"
  },
  "days": {
    "2026-10-04": [
      {"time": "04:49", "height_m": 0.77},
      {"time": "11:12", "height_m": 2.12},
      {"time": "17:06", "height_m": 0.99},
      {"time": "23:36", "height_m": 2.37}
    ]
  }
}
```

Regras:
- uma chave por data ISO;
- 365 datas em 2026;
- cada dia preserva exatamente as linhas publicadas no PDF;
- não completar artificialmente um dia com quatro eventos;
- preservar alturas negativas;
- horários no formato `HH:MM`;
- eventos do dia em ordem cronológica;
- JSON do Desktop e do PWA deve ser idêntico byte a byte.

## Regra temporal

A seleção de **hoje** e **amanhã** usa sempre a data local do Pecém, fixa em UTC −03:00 para esta
fonte, e **não** o timezone atual do celular/notebook.

Isto evita que um operador viajando ou um aparelho configurado em outro fuso veja o dia incorreto.

A aplicação também identifica o **próximo evento de maré**:
- primeiro evento de hoje cujo horário ainda não ocorreu;
- se todos os eventos de hoje já passaram, o primeiro de amanhã;
- se amanhã não existir no dataset, nenhum evento é inventado.

## UX — Desktop

A linha discreta da janela principal passa a ser conceitualmente:

```text
[📖 Guia] [Conectar Celular] [☆ Acompanhados]      [🌊 Maré] [ⓘ] [ ] Modo compacto
```

Regras:

1. Remover a linha permanente `ID AlertaM: ...` atualmente exibida abaixo do rodapé.
2. Adicionar controle discreto `ⓘ`.
3. Hover/foco em `ⓘ` mostra:
   - `AlertaM Desktop`;
   - versão atual;
   - `device_id`;
   - `Desenvolvido por Ciro Torres`.
4. Não expor `DEVICE_SECRET`, `VIEW_SECRET`, cookies ou qualquer credencial.
5. Adicionar `🌊 Maré` ao lado do `ⓘ`.
6. `🌊 Maré` abre um único `Toplevel` não modal e reutilizável.
7. A janela mostra:
   - cabeçalho `Tábua de maré — Pecém`;
   - bloco `Hoje · DD MMM`;
   - bloco `Amanhã · DD MMM`;
   - exatamente 3–4 linhas conforme o dataset;
   - horário e altura em metros;
   - destaque discreto `Próxima` no próximo evento;
   - fonte `DHN · 2026 · Carta 711 · UTC−03`.
8. Não mostrar fases da Lua nesta primeira versão.
9. O recurso deve funcionar offline e no executável PyInstaller.

## UX — PWA

Não criar novo item no footer/navigation.

Na rota existente `/tempo`, abaixo de Atmosfera/Complementar/Condições marítimas, adicionar um card:

`Tábua de maré · DHN`

O card mostra:
- Hoje;
- Amanhã;
- horários;
- alturas;
- destaque do próximo evento;
- fonte DHN/ano/Carta 711/UTC−03.

A tábua deve permanecer visualmente separada de:
- WebPilot;
- Open-Meteo Forecast;
- Open-Meteo Marine.

Não usar labels `fresh/stale`, pois a tábua é uma previsão anual oficial estática e não um dado
observado em runtime.

## Ano indisponível

Se a data solicitada não existir no dataset:

- não extrapolar;
- não consultar serviço externo silenciosamente;
- mostrar `Tábua de maré de <ano> ainda não disponível.`.

Exemplo obrigatório:
- em 31/12/2026, o bloco Hoje mostra 31/12 normalmente;
- o bloco Amanhã (01/01/2027) mostra indisponibilidade até existir dataset 2027.

A arquitetura deve permitir adicionar `pecem-2027.json` futuramente sem alterar o contrato da UI.

## Escopo

- normalizar a fonte DHN 2026;
- empacotar dataset no Desktop;
- empacotar dataset no PWA;
- remover ID permanente do Desktop;
- adicionar `ⓘ` no Desktop;
- adicionar `🌊 Maré` no Desktop;
- adicionar card de maré na página Tempo do PWA;
- destacar próximo evento;
- validar paridade dos datasets;
- testes e build.

## Fora do escopo

- API endpoint de maré;
- banco/Supabase;
- novo `MobileSnapshot`;
- download automático do PDF;
- scraping do site da Marinha;
- interpolação de altura entre horários;
- gráfico/curva de maré;
- fases da Lua;
- alarmes/push de maré;
- notificação por altura;
- cálculo astronômico;
- maré observada em tempo real;
- mistura com Open-Meteo Marine.

## Impacto

| Camada | Impacto |
|---|---|
| Desktop domain/application | modelo/query simples da tábua estática |
| Desktop infrastructure | carregamento do JSON empacotado |
| Desktop UI | `🌊 Maré`, `ⓘ`, remoção do ID permanente, janela de maré |
| Desktop build | incluir JSON no PyInstaller |
| API backend | nenhum |
| Supabase | nenhum |
| PWA | helper de data Pecém + card na WeatherPage |
| MobileSnapshot | nenhum |
| Testes | parser/seleção temporal/UI/paridade/build |

## Riscos

- erro manual na transcrição anual;
- diferença entre JSON Desktop e PWA;
- usar timezone do aparelho e virar o dia antes/depois do Pecém;
- perder o arquivo JSON no bundle PyInstaller;
- tratar 2027 ausente como zeros ou extrapolação;
- misturar visualmente tábua DHN com condições marítimas Open-Meteo.

## Critérios de aceite

- [ ] dataset 2026 contém 365 datas e preserva todos os eventos/alturas da fonte;
- [ ] amostras de janeiro, outubro e dezembro batem com o PDF;
- [ ] altura negativa é preservada;
- [ ] JSON Desktop e PWA são byte-idênticos;
- [ ] seleção Hoje/Amanhã usa UTC−03, independente do timezone do aparelho;
- [ ] próximo evento é destacado corretamente;
- [ ] 31/12/2026 não fabrica 01/01/2027;
- [ ] Desktop não mostra mais ID permanente abaixo de `Modo compacto`;
- [ ] `ⓘ` mostra produto, versão, device_id e autoria sem segredo;
- [ ] `🌊 Maré` abre janela única com Hoje/Amanhã;
- [ ] executável inclui o dataset;
- [ ] PWA mostra card na rota Tempo sem novo item de navegação;
- [ ] PWA mantém DHN separado de WebPilot/Open-Meteo;
- [ ] API/Supabase/MobileSnapshot permanecem sem alteração;
- [ ] suites e builds normais dos dois repositórios passam.

## Perguntas em aberto

Nenhuma. As decisões de produto necessárias para o primeiro escopo foram fechadas nesta SPEC.


## Ruling de sequenciamento — 2026-10-04

Por decisão do usuário, a SPEC 029 deixa de ser apenas uma trilha lateral executável a qualquer momento e passa a ser **executada intencionalmente antes do Plan 4 da SPEC 025**, sem criar dependência técnica entre as duas.

Objetivo operacional desta ordem:
- concluir os refinamentos visuais Desktop/PWA;
- usar essa entrega como conteúdo da primeira release genérica real do updater;
- validar atualização no computador do pai do usuário;
- somente depois iniciar Maneuver Shadow.

Fluxo detalhado:
`docs/superpowers/plans/2026-10-04-pre-plan4-spec029-updater-pilot.md`.

Esse gate temporário de 2026-10-04 foi posteriormente superado pelo alinhamento pós-SPEC 030 de 2026-10-06. O Plan 4 continua posterior à SPEC 029, mas sua abertura agora depende do hotfix pré-Plan 4 do `DeviceOperationalGate`, da janela de UI escolhida pelo usuário e de nova revisão do `develop` corrente.
