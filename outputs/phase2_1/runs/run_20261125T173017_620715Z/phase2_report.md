# RiskAgent B3 — Relatorio da Fase 2.1

Projeto educacional. Este relatorio nao e recomendacao de investimento.

Execucao UTC: 2026-11-25 17:30:33
Nivel de cauda: 1.0% | VaR: 99% | Janela: 1000 pregoes

## Dados utilizados

- PETR4: 4188 precos disponiveis
- VALE3: 4188 precos disponiveis
- IBOV: 4187 precos disponiveis

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
           IBOV         EWMA normal   3183          50              1.5708      -3.1127     -3.5661          0.0028               0.0281                  0.2063                       1.0000                        0.0051                             0.0359
           IBOV         GJR-GARCH t   3183          35              1.0996      -3.2658     -3.9522          0.5784               1.0000                  0.3775                       1.0000                        0.5793                             0.5793
           IBOV Simulacao historica   3183          35              1.0996      -3.7481     -5.7642          0.5784               1.0000                  0.0005                       0.0050                        0.0018                             0.0166
          PETR4         EWMA normal   3185          60              1.8838      -6.0578     -6.9402          0.0000               0.0001                  0.0057                       0.0511                        0.0000                             0.0000
          PETR4         GJR-GARCH t   3185          39              1.2245      -6.9111     -8.9417          0.2187               0.8747                  0.0940                       0.5639                        0.1149                             0.3583
          PETR4 Simulacao historica   3185          48              1.5071      -8.1926    -12.2635          0.0075               0.0671                  0.0001                       0.0007                        0.0000                             0.0001
PORTFOLIO_50_50         EWMA normal   3185          52              1.6327      -4.7435     -5.4345          0.0010               0.0111                  0.2781                       1.0000                        0.0025                             0.0197
PORTFOLIO_50_50         GJR-GARCH t   3185          40              1.2559      -5.1452     -6.3613          0.1628               0.8138                  0.0139                       0.1113                        0.0182                             0.1095
PORTFOLIO_50_50 Simulacao historica   3185          44              1.3815      -5.8472     -8.6097          0.0408               0.2856                  0.0027                       0.0270                        0.0014                             0.0136
          VALE3         EWMA normal   3185          48              1.5071      -5.3971     -6.1833          0.0075               0.0671                  0.7405                       1.0000                        0.0261                             0.1307
          VALE3         GJR-GARCH t   3185          30              0.9419      -5.9386     -7.4127          0.7394               1.0000                  0.0299                       0.2091                        0.0896                             0.3583
          VALE3 Simulacao historica   3185          41              1.2873      -6.2947     -9.0668          0.1187               0.7122                  0.5438                       1.0000                        0.2448                             0.4896
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
pre_covid_2015_2019 PORTFOLIO_50_50         GJR-GARCH t   1234          0.3166             0.4419                  0.5166                     0.7153                        0.4893                           0.5872
pre_covid_2015_2019 PORTFOLIO_50_50 Simulacao historica   1234          0.0003             0.0103                  0.1271                     0.3521                        0.0009                           0.0113
pre_covid_2015_2019           VALE3         EWMA normal   1234          0.3166             0.4419                  0.5166                     0.7153                        0.4893                           0.5872
pre_covid_2015_2019           VALE3         GJR-GARCH t   1234          0.6961             0.7371                  0.6563                     0.7717                        0.8401                           0.8499
pre_covid_2015_2019           VALE3 Simulacao historica   1234          0.0128             0.0658                  0.3713                     0.7035                        0.0300                           0.1080
    covid_2020_2021            IBOV         EWMA normal    472          0.0048             0.0347                  0.4278                     0.7153                        0.0133                           0.0598
    covid_2020_2021            IBOV         GJR-GARCH t    472          0.0336             0.1326                  0.5096                     0.7153                        0.0823                           0.1974
    covid_2020_2021            IBOV Simulacao historica    472          0.0048             0.0347                  0.0019                     0.0423                        0.0001                           0.0052
    covid_2020_2021           PETR4         EWMA normal    472          0.0048             0.0347                  0.0312                     0.1875                        0.0018                           0.0161
    covid_2020_2021           PETR4         GJR-GARCH t    472          0.5699             0.6217                  0.0579                     0.2379                        0.1400                           0.2521
    covid_2020_2021           PETR4 Simulacao historica    472          0.1675             0.3174                  0.0047                     0.0423                        0.0070                           0.0360
    covid_2020_2021 PORTFOLIO_50_50         EWMA normal    472          0.0336             0.1326                  0.1987                     0.5108                        0.0448                           0.1343
    covid_2020_2021 PORTFOLIO_50_50         GJR-GARCH t    472          0.1675             0.3174                  0.0047                     0.0423                        0.0070                           0.0360
    covid_2020_2021 PORTFOLIO_50_50 Simulacao historica    472          0.1675             0.3174                  0.0047                     0.0423                        0.0070                           0.0360
    covid_2020_2021           VALE3         EWMA normal    472          0.1675             0.3174                  0.5986                     0.7717                        0.3311                           0.4502
    covid_2020_2021           VALE3         GJR-GARCH t    472          0.5699             0.6217                  0.0579                     0.2379                        0.1400                           0.2521
    covid_2020_2021           VALE3 Simulacao historica    472          0.3250             0.4419                  0.0845                     0.3043                        0.1378                           0.2521
 recent_2022_onward            IBOV         EWMA normal   1222          0.1944             0.3244                  0.4884                     0.7153                        0.3376                           0.4502
 recent_2022_onward            IBOV         GJR-GARCH t   1222          0.7212             0.7419                  0.6547                     0.7717                        0.8499                           0.8499
 recent_2022_onward            IBOV Simulacao historica   1222          0.0473             0.1418                  0.8077                     0.8307                        0.1363                           0.2521
 recent_2022_onward           PETR4         EWMA normal   1222          0.0006             0.0103                  0.1202                     0.3521                        0.0008                           0.0113
 recent_2022_onward           PETR4         GJR-GARCH t   1222          0.1205             0.3099                  0.2643                     0.5946                        0.1599                           0.2741
 recent_2022_onward           PETR4 Simulacao historica   1222          0.1028             0.2846                  0.7763                     0.8220                        0.2548                           0.3822
 recent_2022_onward PORTFOLIO_50_50         EWMA normal   1222          0.0405             0.1326                  0.3338                     0.6676                        0.0764                           0.1965
 recent_2022_onward PORTFOLIO_50_50         GJR-GARCH t   1222          0.9494             0.9494                  0.1038                     0.3397                        0.2658                           0.3828
 recent_2022_onward PORTFOLIO_50_50 Simulacao historica   1222          0.0060             0.0358                  0.8883                     0.8883                        0.0227                           0.0909
 recent_2022_onward           VALE3         EWMA normal   1222          0.0405             0.1326                  0.3155                     0.6676                        0.0737                           0.1965
 recent_2022_onward           VALE3         GJR-GARCH t   1222          0.5099             0.5921                  0.0595                     0.2379                        0.1365                           0.2521
 recent_2022_onward           VALE3 Simulacao historica   1222          0.3314             0.4419                  0.7304                     0.7968                        0.5896                           0.6847
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
