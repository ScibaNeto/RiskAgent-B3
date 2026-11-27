# RiskAgent B3 — Relatorio da Fase 2.1

Projeto educacional. Este relatorio nao e recomendacao de investimento.

Execucao UTC: 2026-11-27 19:12:30
Nivel de cauda: 1.0% | VaR: 99% | Janela: 1000 pregoes

## Dados utilizados

- PETR4: 4190 precos disponiveis
- VALE3: 4190 precos disponiveis
- IBOV: 4189 precos disponiveis

## Carteira demonstrativa

- PETR4: 50%
- VALE3: 50%
- Ibovespa: benchmark separado; nao e uma posicao da carteira.
- A serie de carteira usa pesos constantes aplicados diariamente (rebalanceamento diario implicito).

## Como interpretar os testes

- Kupiec (UC): avalia se a frequencia de violacoes e compativel com o nivel de cauda de 1%.
- Christoffersen (IND): avalia se as violacoes sao independentes ao longo do tempo.
- Cobertura condicional (CC): combina frequencia e independencia.
- p-valor >= 0,05 significa que o teste nao rejeitou a hipotese nula; nao prova que o modelo seja perfeito.
- Um teste de VaR aprovado nao garante que o ES esteja correto; o ES tambem exige avaliacao propria.
- `fz0_score_mean` e uma pontuacao conjunta VaR/ES: menor e melhor. Nao e p-valor nem teste de rejeicao.
- As comparacoes por periodo usam janelas fixas; resultados dependem da amostra disponivel.

## Correcao para multiplas comparacoes

- Confirmatorio: nos resultados fora da amostra completos, cada familia agrega todos os ativos/modelos para um mesmo teste (Kupiec UC, Christoffersen IND ou cobertura condicional CC); p-valores originais sao mantidos e Holm controla o erro familiar.
- Exploratorio: nos resultados por periodo, cada familia agrega periodos, ativos e modelos para um mesmo teste (UC, IND ou CC); Benjamini-Hochberg controla a taxa de falsas descobertas sob independencia ou dependencia positiva apropriada.
- Sob dependencia arbitraria entre testes, o controle FDR do Benjamini-Hochberg nao e garantido.
- Scores FZ0 nao sao p-valores e nao recebem ajuste.

## Resultados por ativo/modelo

```text
          asset               model  n_obs  violations  violation_rate_pct  avg_var_pct  avg_es_pct  kupiec_p_value  kupiec_p_value_holm  christoffersen_p_value  christoffersen_p_value_holm  conditional_coverage_p_value  conditional_coverage_p_value_holm
           IBOV         EWMA normal   3185          50              1.5699      -3.1142     -3.5678          0.0028               0.0285                  0.2065                       1.0000                        0.0052                             0.0363
           IBOV         GJR-GARCH t   3185          35              1.0989      -3.2667     -3.9536          0.5808               1.0000                  0.3777                       1.0000                        0.5807                             0.5807
           IBOV Simulacao historica   3185          35              1.0989      -3.7473     -5.7632          0.5808               1.0000                  0.0005                       0.0050                        0.0018                             0.0166
          PETR4         EWMA normal   3187          60              1.8826      -6.0578     -6.9402          0.0000               0.0001                  0.0057                       0.0509                        0.0000                             0.0000
          PETR4         GJR-GARCH t   3187          39              1.2237      -6.9105     -8.9411          0.2200               0.8802                  0.0939                       0.5632                        0.1153                             0.3801
          PETR4 Simulacao historica   3187          48              1.5061      -8.1907    -12.2603          0.0075               0.0679                  0.0001                       0.0007                        0.0000                             0.0001
PORTFOLIO_50_50         EWMA normal   3187          52              1.6316      -4.7433     -5.4342          0.0010               0.0113                  0.2778                       1.0000                        0.0025                             0.0199
PORTFOLIO_50_50         GJR-GARCH t   3187          40              1.2551      -5.1446     -6.3606          0.1639               0.8194                  0.0139                       0.1111                        0.0183                             0.1099
PORTFOLIO_50_50 Simulacao historica   3187          44              1.3806      -5.8457     -8.6068          0.0412               0.2882                  0.0030                       0.0295                        0.0015                             0.0149
          VALE3         EWMA normal   3187          48              1.5061      -5.3973     -6.1835          0.0075               0.0679                  0.7547                       1.0000                        0.0266                             0.1328
          VALE3         GJR-GARCH t   3187          30              0.9413      -5.9391     -7.4137          0.7367               1.0000                  0.0320                       0.2243                        0.0950                             0.3801
          VALE3 Simulacao historica   3187          41              1.2865      -6.2933     -9.0642          0.1196               0.7175                  0.5571                       1.0000                        0.2492                             0.4983
```

## Resultados exploratorios por periodo (p-valores originais e BH)

```text
             period           asset               model  n_obs  kupiec_p_value  kupiec_p_value_bh  christoffersen_p_value  christoffersen_p_value_bh  conditional_coverage_p_value  conditional_coverage_p_value_bh
pre_covid_2015_2019            IBOV         EWMA normal   1234          0.1296             0.3111                  0.4652                     0.7153                        0.2417                           0.3784
pre_covid_2015_2019            IBOV         GJR-GARCH t   1234          0.4888             0.5865                  0.6859                     0.7717                        0.7265                           0.7693
pre_covid_2015_2019            IBOV Simulacao historica   1234          0.4888             0.5865                  0.6859                     0.7717                        0.7265                           0.7693
pre_covid_2015_2019           PETR4         EWMA normal   1234          0.2073             0.3244                  0.2298                     0.5516                        0.2187                           0.3579
pre_covid_2015_2019           PETR4         GJR-GARCH t   1234          0.4888             0.5865                  0.6859                     0.7717                        0.7265                           0.7693
pre_covid_2015_2019           PETR4 Simulacao historica   1234          0.2073             0.3244                  0.0173                     0.1245                        0.0355                           0.1163
pre_covid_2015_2019 PORTFOLIO_50_50         EWMA normal   1234          0.2073             0.3244                  0.4905                     0.7153                        0.3546                           0.4560
pre_covid_2015_2019 PORTFOLIO_50_50         GJR-GARCH t   1234          0.3166             0.4383                  0.5166                     0.7153                        0.4893                           0.5872
pre_covid_2015_2019 PORTFOLIO_50_50 Simulacao historica   1234          0.0003             0.0104                  0.1271                     0.3521                        0.0009                           0.0113
pre_covid_2015_2019           VALE3         EWMA normal   1234          0.3166             0.4383                  0.5166                     0.7153                        0.4893                           0.5872
pre_covid_2015_2019           VALE3         GJR-GARCH t   1234          0.6961             0.7371                  0.6563                     0.7717                        0.8401                           0.8483
pre_covid_2015_2019           VALE3 Simulacao historica   1234          0.0128             0.0658                  0.3713                     0.7035                        0.0300                           0.1080
    covid_2020_2021            IBOV         EWMA normal    472          0.0048             0.0347                  0.4278                     0.7153                        0.0133                           0.0598
    covid_2020_2021            IBOV         GJR-GARCH t    472          0.0336             0.1344                  0.5096                     0.7153                        0.0823                           0.1974
    covid_2020_2021            IBOV Simulacao historica    472          0.0048             0.0347                  0.0019                     0.0423                        0.0001                           0.0052
    covid_2020_2021           PETR4         EWMA normal    472          0.0048             0.0347                  0.0312                     0.1875                        0.0018                           0.0161
    covid_2020_2021           PETR4         GJR-GARCH t    472          0.5699             0.6217                  0.0579                     0.2604                        0.1400                           0.2653
    covid_2020_2021           PETR4 Simulacao historica    472          0.1675             0.3174                  0.0047                     0.0423                        0.0070                           0.0360
    covid_2020_2021 PORTFOLIO_50_50         EWMA normal    472          0.0336             0.1344                  0.1987                     0.5108                        0.0448                           0.1343
    covid_2020_2021 PORTFOLIO_50_50         GJR-GARCH t    472          0.1675             0.3174                  0.0047                     0.0423                        0.0070                           0.0360
    covid_2020_2021 PORTFOLIO_50_50 Simulacao historica    472          0.1675             0.3174                  0.0047                     0.0423                        0.0070                           0.0360
    covid_2020_2021           VALE3         EWMA normal    472          0.1675             0.3174                  0.5986                     0.7717                        0.3311                           0.4539
    covid_2020_2021           VALE3         GJR-GARCH t    472          0.5699             0.6217                  0.0579                     0.2604                        0.1400                           0.2653
    covid_2020_2021           VALE3 Simulacao historica    472          0.3250             0.4383                  0.0845                     0.3043                        0.1378                           0.2653
 recent_2022_onward            IBOV         EWMA normal   1224          0.1965             0.3244                  0.4887                     0.7153                        0.3404                           0.4539
 recent_2022_onward            IBOV         GJR-GARCH t   1224          0.7170             0.7375                  0.6550                     0.7717                        0.8483                           0.8483
 recent_2022_onward            IBOV Simulacao historica   1224          0.0467             0.1401                  0.8078                     0.8309                        0.1350                           0.2653
 recent_2022_onward           PETR4         EWMA normal   1224          0.0006             0.0106                  0.1199                     0.3521                        0.0008                           0.0113
 recent_2022_onward           PETR4         GJR-GARCH t   1224          0.1220             0.3111                  0.2638                     0.5935                        0.1613                           0.2764
 recent_2022_onward           PETR4 Simulacao historica   1224          0.1017             0.2815                  0.7765                     0.8222                        0.2527                           0.3790
 recent_2022_onward PORTFOLIO_50_50         EWMA normal   1224          0.0411             0.1346                  0.3332                     0.6665                        0.0773                           0.1974
 recent_2022_onward PORTFOLIO_50_50         GJR-GARCH t   1224          0.9449             0.9449                  0.1036                     0.3391                        0.2653                           0.3821
 recent_2022_onward PORTFOLIO_50_50 Simulacao historica   1224          0.0059             0.0352                  0.8713                     0.8713                        0.0224                           0.0894
 recent_2022_onward           VALE3         EWMA normal   1224          0.0411             0.1346                  0.3332                     0.6665                        0.0773                           0.1974
 recent_2022_onward           VALE3         GJR-GARCH t   1224          0.5063             0.5880                  0.0673                     0.2692                        0.1507                           0.2712
 recent_2022_onward           VALE3 Simulacao historica   1224          0.3287             0.4383                  0.7149                     0.7799                        0.5822                           0.6760
```text

## Diagnostico das estimacoes GJR-GARCH-t

```text
status            ok
asset               
IBOV             160
PETR4            160
PORTFOLIO_50_50  160
VALE3            160
```

## Arquivos

- `phase2_metrics.csv`: metricas, backtests de VaR e score FZ0 de VaR/ES.
- `phase2_es_scoring.csv`: resumo do score conjunto VaR/ES (FZ0; menor e melhor).
- `phase2_period_metrics.csv`: backtests separados por periodo de mercado.
- `phase2_phase1_comparison.csv`: comparacao com a Fase 1, quando o CSV antigo existe.
- `phase2_forecasts.csv`: previsoes diarias de VaR e ES.
- `phase2_garch_diagnostics.csv`: convergencia das estimacoes GJR-GARCH.
- `manifest.json`: proveniencia, verificacoes basicas, hash do cache e versoes das bibliotecas.
- `phase2_portfolio_weights.csv`: pesos usados na carteira demonstrativa.
- `phase2_portfolio_var.png`, `phase2_portfolio_es.png` e `phase2_backtest_exceptions.png`: graficos.
