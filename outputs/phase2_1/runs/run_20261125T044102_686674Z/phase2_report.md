# RiskAgent B3 — Relatorio da Fase 2.1

Projeto educacional. Este relatorio nao e recomendacao de investimento.

Execucao UTC: 2026-11-25 04:41:37
Nivel de cauda: 1.0% | VaR: 99% | Janela: 1000 pregoes

## Dados utilizados

- PETR4: 4196 precos disponiveis
- VALE3: 4197 precos disponiveis
- IBOV: 4188 precos disponiveis

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
           IBOV         EWMA normal   3187          50              1.5689      -3.1114     -3.5646          0.0029               0.0288                  0.2067                       1.0000                        0.0053                             0.0372
           IBOV         GJR-GARCH t   3187          35              1.0982      -3.2746     -3.9661          0.5833               1.0000                  0.3779                       1.0000                        0.5832                             0.9106
           IBOV Simulacao historica   3187          35              1.0982      -3.7469     -5.7614          0.5833               1.0000                  0.0005                       0.0050                        0.0018                             0.0177
          PETR4         EWMA normal   3195          59              1.8466      -6.0492     -6.9304          0.0000               0.0002                  0.0048                       0.0431                        0.0000                             0.0000
          PETR4         GJR-GARCH t   3195          38              1.1894      -6.9056     -8.9490          0.2962               1.0000                  0.0842                       0.6734                        0.1305                             0.6523
          PETR4 Simulacao historica   3195          48              1.5023      -8.1858    -12.2542          0.0079               0.0632                  0.0001                       0.0007                        0.0000                             0.0001
PORTFOLIO_50_50         EWMA normal   3195          52              1.6275      -4.7391     -5.4294          0.0011               0.0119                  0.2764                       1.0000                        0.0026                             0.0212
PORTFOLIO_50_50         GJR-GARCH t   3195          38              1.1894      -5.1359     -6.3589          0.2962               1.0000                  0.0842                       0.6734                        0.1305                             0.6523
PORTFOLIO_50_50 Simulacao historica   3195          43              1.3459      -5.8427     -8.6044          0.0620               0.4340                  0.0024                       0.0243                        0.0018                             0.0177
          VALE3         EWMA normal   3196          49              1.5332      -5.3909     -6.1762          0.0050               0.0447                  0.7669                       1.0000                        0.0185                             0.1111
          VALE3         GJR-GARCH t   3196          29              0.9074      -5.9142     -7.3908          0.5929               1.0000                  0.2564                       1.0000                        0.4553                             0.9106
          VALE3 Simulacao historica   3196          41              1.2829      -6.2871     -9.0601          0.1236               0.7417                  0.5417                       1.0000                        0.2537                             0.7610
```

## Resultados exploratorios por periodo (p-valores originais e BH)

```text
             period           asset               model  n_obs  kupiec_p_value  kupiec_p_value_bh  christoffersen_p_value  christoffersen_p_value_bh  conditional_coverage_p_value  conditional_coverage_p_value_bh
pre_covid_2015_2019            IBOV         EWMA normal   1235          0.1304             0.3129                  0.4654                     0.7658                        0.2440                           0.3989
pre_covid_2015_2019            IBOV         GJR-GARCH t   1235          0.4870             0.5844                  0.6860                     0.7978                        0.7238                           0.7896
pre_covid_2015_2019            IBOV Simulacao historica   1235          0.4870             0.5844                  0.6860                     0.7978                        0.7238                           0.7896
pre_covid_2015_2019           PETR4         EWMA normal   1243          0.2173             0.3401                  0.2280                     0.5863                        0.2259                           0.3872
pre_covid_2015_2019           PETR4         GJR-GARCH t   1243          0.4733             0.5844                  0.6870                     0.7978                        0.7130                           0.7896
pre_covid_2015_2019           PETR4 Simulacao historica   1243          0.2173             0.3401                  0.0170                     0.1504                        0.0271                           0.1085
pre_covid_2015_2019 PORTFOLIO_50_50         EWMA normal   1243          0.2173             0.3401                  0.4921                     0.7658                        0.3689                           0.4743
pre_covid_2015_2019 PORTFOLIO_50_50         GJR-GARCH t   1243          0.4780             0.5844                  0.5448                     0.7845                        0.6472                           0.7766
pre_covid_2015_2019 PORTFOLIO_50_50 Simulacao historica   1243          0.0003             0.0102                  0.1254                     0.3761                        0.0005                           0.0087
pre_covid_2015_2019           VALE3         EWMA normal   1243          0.2173             0.3401                  0.4921                     0.7658                        0.3689                           0.4743
pre_covid_2015_2019           VALE3         GJR-GARCH t   1243          0.6776             0.7392                  0.6575                     0.7978                        0.8313                           0.8733
pre_covid_2015_2019           VALE3 Simulacao historica   1243          0.0139             0.0713                  0.3730                     0.7461                        0.0326                           0.1172
    covid_2020_2021            IBOV         EWMA normal    473          0.0049             0.0353                  0.4288                     0.7658                        0.0140                           0.0628
    covid_2020_2021            IBOV         GJR-GARCH t    473          0.0340             0.1326                  0.5106                     0.7658                        0.0852                           0.2191
    covid_2020_2021            IBOV Simulacao historica    473          0.0049             0.0353                  0.0019                     0.0559                        0.0002                           0.0054
    covid_2020_2021           PETR4         EWMA normal    473          0.0134             0.0713                  0.0209                     0.1504                        0.0033                           0.0294
    covid_2020_2021           PETR4         GJR-GARCH t    473          0.5731             0.6448                  0.0576                     0.3058                        0.1406                           0.2665
    covid_2020_2021           PETR4 Simulacao historica    473          0.1691             0.3381                  0.0047                     0.0559                        0.0071                           0.0365
    covid_2020_2021 PORTFOLIO_50_50         EWMA normal    473          0.0340             0.1326                  0.1977                     0.5475                        0.0461                           0.1510
    covid_2020_2021 PORTFOLIO_50_50         GJR-GARCH t    473          0.3275             0.4589                  0.0841                     0.3365                        0.1393                           0.2665
    covid_2020_2021 PORTFOLIO_50_50 Simulacao historica    473          0.1691             0.3381                  0.0047                     0.0559                        0.0071                           0.0365
    covid_2020_2021           VALE3         EWMA normal    473          0.1691             0.3381                  0.5994                     0.7978                        0.3384                           0.4693
    covid_2020_2021           VALE3         GJR-GARCH t    473          0.9016             0.9274                  0.7435                     0.8111                        0.9407                           0.9407
    covid_2020_2021           VALE3 Simulacao historica    473          0.3275             0.4589                  0.0841                     0.3365                        0.1393                           0.2665
 recent_2022_onward            IBOV         EWMA normal   1222          0.1944             0.3401                  0.4884                     0.7658                        0.3390                           0.4693
 recent_2022_onward            IBOV         GJR-GARCH t   1222          0.7212             0.7637                  0.6547                     0.7978                        0.8490                           0.8733
 recent_2022_onward            IBOV Simulacao historica   1222          0.0473             0.1418                  0.8077                     0.8307                        0.1356                           0.2665
 recent_2022_onward           PETR4         EWMA normal   1221          0.0006             0.0102                  0.1204                     0.3761                        0.0008                           0.0094
 recent_2022_onward           PETR4         GJR-GARCH t   1221          0.1198             0.3080                  0.2645                     0.6348                        0.1600                           0.2880
 recent_2022_onward           PETR4 Simulacao historica   1221          0.1033             0.2861                  0.7762                     0.8219                        0.2548                           0.3989
 recent_2022_onward PORTFOLIO_50_50         EWMA normal   1221          0.0402             0.1326                  0.3341                     0.7075                        0.0764                           0.2117
 recent_2022_onward PORTFOLIO_50_50         GJR-GARCH t   1221          0.9517             0.9517                  0.1039                     0.3740                        0.2660                           0.3990
 recent_2022_onward PORTFOLIO_50_50 Simulacao historica   1221          0.0015             0.0181                  0.9032                     0.9032                        0.0065                           0.0365
 recent_2022_onward           VALE3         EWMA normal   1222          0.0405             0.1326                  0.3155                     0.7075                        0.0741                           0.2117
 recent_2022_onward           VALE3         GJR-GARCH t   1222          0.5099             0.5921                  0.0595                     0.3058                        0.1362                           0.2665
 recent_2022_onward           VALE3 Simulacao historica   1222          0.3314             0.4589                  0.7304                     0.8111                        0.5880                           0.7299
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
