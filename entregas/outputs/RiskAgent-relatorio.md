# RiskAgent B3 · Dados de mercado e validação do GJR-GARCH

25 de novembro de 2026 · Revisão local do Marco 1 e primeiro teste de integração do Marco 2

## Resultado

As Fases 1 e 2.1 agora usam a mesma regra para construir retornos diários. Cada retorno exige o fechamento de dois pregões consecutivos. Os dois backtests terminaram com os caches locais. A verificação ao vivo de PETR4, feita sobre uma cópia isolada, recebeu três linhas do Yahoo Finance. O fechamento mais recente disponível nessa consulta continuava sendo o de 23 de novembro.

O GitHub mostrava zero PRs abertos, zero issues abertas e zero execuções de GitHub Actions no repositório, em 25 de novembro. O trabalho foi preparado na branch local `codex/riskagent-marco-0-garch-alignment`, com base em `16d3f6c`. A cópia anterior à intervenção contém o Git, o código, os resultados e os caches locais. A verificação de integridade do ZIP passou. [PRs](https://github.com/ScibaNeto/RiskAgent-B3/pulls) · [Issues](https://github.com/ScibaNeto/RiskAgent-B3/issues) · [Actions](https://github.com/ScibaNeto/RiskAgent-B3/actions)

## O que o calendário mudou

O corte da execução foi a madrugada de 25 de novembro em São Paulo. O último pregão encerrado era 24 de novembro. A comparação usa os mesmos três arquivos brutos da execução anterior. Os hashes SHA-256 conferiram com o backup.

| Série | Último preço | Retornos antes | Retornos agora | Pregões internos sem preço | Datas fora do calendário | Atraso em pregões |
|---|---|---:|---:|---:|---:|---:|
| PETR4 | 23/11/2026 | 4.195 | 4.184 | 2 | 9 | 1 |
| VALE3 | 24/11/2026 | 4.196 | 4.185 | 2 | 9 | 0 |
| Ibovespa | 24/11/2026 | 4.187 | 4.183 | 3 | 1 | 0 |

Faltaram os fechamentos de **22/02/2012** e **20/11/2020** nas três séries. O Ibovespa também apresentou uma lacuna em **02/01/2012**. A B3 anunciou negociação normal em 20/11/2020 e suspensão em 20/11/2026. O teste automatizado cobre essa diferença histórica. [Comunicado da B3 sobre 2020](https://www.b3.com.br/pt_br/noticias/funcionamento-da-b3-8AE490C97215B74E0172959F18F11323.htm) · [Calendário da B3 para 2026](https://www.b3.com.br/pt_br/noticias/calendario-de-negociacao-da-b3-confira-o-funcionamento-da-bolsa-em-2026.htm)

O cálculo usa `100 × ln(P_t / P_anterior)`, em que o preço anterior corresponde à sessão imediatamente precedente do calendário BVMF. Se faltar um fechamento, o cálculo volta a produzir retornos quando houver novamente dois fechamentos consecutivos. Na carteira com rebalanceamento diário, os retornos simples dos componentes precisam ter a mesma data e o mesmo horizonte. O modelo pondera esses retornos antes de aplicar `100 × ln(1 + retorno_da_carteira)`.

Os retornos logarítmicos diários absolutos acima de 15% ficaram sinalizados. PETR4 teve nove, VALE3 teve cinco e o Ibovespa teve um. Eles continuaram no backtest.

## Efeito sobre o backtest

| Série | Observações fora da amostra antes → agora | Violações do VaR 99% do GJR antes → agora |
|---|---:|---:|
| PETR4 | 3.195 → 3.184 | 38 → 39 |
| VALE3 | 3.196 → 3.185 | 29 → 30 |
| Ibovespa | 3.187 → 3.183 | 35 → 35 |
| Carteira 50/50 | 3.195 → 3.184 | 38 → 40 |

Cada violação indica que a perda observada superou a estimada pelo VaR. As datas de entrada e as janelas de estimação mudaram. Uma comparação de capacidade preditiva exigirá uma amostra de avaliação fixada previamente. A Fase 1 registrou convergência em 480 de 480 ajustes GJR, e a Fase 2.1 em 640 de 640.

## Coleta e arquivos

- **Calendário e retornos.** `src/b3_sessions.py` usa a versão 4.13.3 de `exchange-calendars`. O fechamento programado da sessão determina quando o preço do dia se torna elegível.
- **Coleta e cache.** `src/market_data.py` valida preços, datas, duplicidades, ordem, tamanho da amostra e atualidade. Um lote inválido aciona o fallback. Revisão do primeiro preço coincidente no período de sobreposição exige a releitura integral do histórico. A nova série completa deve cobrir o histórico válido anterior e conferir com o lote que motivou a releitura.
- **Persistência.** A substituição do CSV é atômica. Um bloqueio de escrita e a comparação da versão lida impedem que uma atualização concorrente sobrescreva a outra. O modo offline lê os arquivos locais. O modo estrito admite por padrão um pregão encerrado de atraso, ajustável com `--max-stale-sessions`.
- **Rastreabilidade.** Cada execução aceita grava os arquivos de entrada em `inputs/`, com SHA-256, origem, tentativas, lacunas, revisões, extremos e versões em `manifest.json`. A hora de coleta fica desconhecida para caches históricos. O instante da análise fica registrado separadamente. A recusa de uma série gera `data_failure.json` antes da estimação dos modelos.
- **Integração.** Foram atualizados `src/var_baseline.py`, `src/phase2_risk_engine_v2.py`, `src/data_manifest.py`, o README, as dependências, as regras de exclusão dos snapshots no Git e os testes das duas fases. O script legado da Fase 2, os três CSVs originais e os resultados anteriores foram preservados.

## Verificação

Os **31 testes da versão inicial** passaram antes da alteração. A primeira execução com o novo calendário apontou quatro falhas de asserção e sete erros. As séries de teste continham fins de semana ou feriados, e um teste ainda esperava um retorno atravessando uma lacuna. As séries de negociação passaram a usar pregões, e datas fixas verificam de forma independente a exclusão dos dois retornos afetados por um preço ausente.

A suíte final teve **48 testes aprovados**. Os novos casos cobrem recusa de lote parcialmente inválido, interrupção por atraso, falha de gravação, escrita concorrente, revisão de preços ajustados, preservação dos bytes em fallback, reprodução exata da entrada do modelo e cálculo da carteira com datas faltantes. A compilação de `src` e `tests`, a verificação das dependências com `pip check` e a verificação do diff também passaram. A dependência de calendário emite um aviso de depreciação com pandas 3.1.1.

O teste de integração do GJR usa uma série sintética isolada com semente fixa e 500 observações para estimação. Para as seis seguintes, cada previsão de referência da biblioteca `arch` usa os parâmetros ajustados e a série encerrada no dia anterior. O VaR das duas fases coincidiu com as seis referências nas tolerâncias absoluta e relativa de `1e-8`. A amostra de mercado das execuções completas usa exclusivamente os arquivos históricos.

A execução com limite zero parou em PETR4 antes do ajuste e gravou o diagnóstico. Com limite de um pregão, as duas fases terminaram e registraram cobertura parcial. Para verificar os resultados a partir da raiz do projeto, use os comandos abaixo.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe src\var_baseline.py --offline --strict-cache
.\.venv\Scripts\python.exe src\phase2_risk_engine_v2.py --offline --strict-cache
```

| Evidência | Local no repositório |
|---|---|
| Fase 1 | `outputs/phase1/runs/run_20261125T051336_163679Z/` |
| Fase 2.1 | `outputs/phase2_1/runs/run_20261125T051352_640204Z/` |
| Interrupção com limite zero | `outputs/phase1/runs/run_20261125T051209_924123Z/data_failure.json` |
| Comparação anterior da Fase 2.1 | `outputs/phase2_1/runs/run_20261125T044102_686674Z/` |

## Limitações e próxima etapa

A origem dos preços ajustados continua sendo o Yahoo Finance. O calendário indica **quando** houve negociação. A conciliação dos preços com uma segunda fonte, a identificação dos motivos das lacunas e a verificação dos eventos corporativos permanecem pendentes. Os snapshots reproduzem a versão dos dados observada no momento da coleta. A reconstrução da versão que o provedor disponibilizava em cada data histórica exigiria arquivos de época.

O próximo passo do Marco 2 é definir um período final de avaliação e registrar a primeira previsão de cada janela antes de comparar modelos. Também é preciso tratar explicitamente as quebras de sequência na recursão da volatilidade e na contagem de transições do teste de Christoffersen. Hoje essas rotinas recebem a sequência de retornos válidos depois da exclusão das lacunas.
