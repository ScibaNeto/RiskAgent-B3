# RiskAgent B3 — Relatorio da Fase 2.1

Projeto educacional. Este relatorio nao e recomendacao de investimento.

Execucao UTC: 2026-11-25 05:14:09
Nivel de cauda: 1.0% | VaR: 99% | Janela: 1000 pregoes

## Dados utilizados

- PETR4: 4187 precos disponiveis
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
           IBOV         EWMA normal   3183          50              1.5708      -3.1127     -3.5661          0.0028               0.0281                  0.2064                       1.0000                        0.0052                             0.0363
           IBOV         GJR-GARCH t   3183          35              1.0996      -3.2658     -3.9522          0.5784               1.0000                  0.3776                       1.0000                        0.5806                             0.5806
           IBOV Simulacao historica   3183          35              1.0996      -3.7481     -5.7642          0.5784               1.0000                  0.0005                       0.0050                        0.0018                             0.0172
          PETR4         EWMA normal   3184          60              1.8844      -6.0577     -6.9401          0.0000               0.0001                  0.0057                       0.0511                        0.0000                             0.0000
          PETR4         GJR-GARCH t   3184          39              1.2249      -6.9114     -8.9420          0.2180               0.8719                  0.0940                       0.5639                        0.1152                             0.3577
          PETR4 Simulacao historica   3184          48              1.5075      -8.1934    -12.2650          0.0074               0.0668                  0.0001                       0.0007                        0.0000                             0.0001
PORTFOLIO_50_50         EWMA normal   3184          52              1.6332      -4.7438     -5.4348          0.0010               0.0110                  0.2781                       1.0000                        0.0025                             0.0198
PORTFOLIO_50_50         GJR-GARCH t   3184          40              1.2563      -5.1456     -6.3617          0.1622               0.8110                  0.0139                       0.1113                        0.0183                             0.1098
PORTFOLIO_50_50 Simulacao historica   3184          43              1.3505      -5.8480     -8.6111          0.0592               0.4142                  0.0025                       0.0246                        0.0017                             0.0172
          VALE3         EWMA normal   3185          48              1.5071      -5.3971     -6.1833          0.0075               0.0668                  0.7403                       1.0000                        0.0264                             0.1320
          VALE3         GJR-GARCH t   3185          30              0.9419      -5.9386     -7.4127          0.7394               1.0000                  0.0299                       0.2090                        0.0894                             0.3577
          VALE3 Simulacao historica   3185          41              1.2873      -6.2947     -9.0668          0.1187               0.7122                  0.5436                       1.0000                        0.2462                             0.4924
```

## Resultados exploratorios por periodo (p-valores originais e BH)

```text
             period           asset               model  n_obs  kupiec_p_value  kupiec_p_value_bh  christoffersen_p_value  christoffersen_p_value_bh  conditional_coverage_p_value  conditional_coverage_p_value_bh
pre_covid_2015_2019            IBOV         EWMA normal   1234          0.1296             0.3111                  0.4652                     0.7153                        0.2429                           0.3801
pre_covid_2015_2019            IBOV         GJR-GARCH t   1234          0.4888             0.5865                  0.6859                     0.7717                        0.7251                           0.7678
pre_covid_2015_2019            IBOV Simulacao historica   1234          0.4888             0.5865                  0.6859                     0.7717                        0.7251                           0.7678
pre_covid_2015_2019           PETR4         EWMA normal   1234          0.2073             0.3244                  0.2298                     0.5516                        0.2196                           0.3593
pre_covid_2015_2019           PETR4         GJR-GARCH t   1234          0.4888             0.5865                  0.6859                     0.7717                        0.7251                           0.7678
pre_covid_2015_2019           PETR4 Simulacao historica   1234          0.2073             0.3244                  0.0173                     0.1245                        0.0266                           0.0956
pre_covid_2015_2019 PORTFOLIO_50_50         EWMA normal   1234          0.2073             0.3244                  0.4905                     0.7153                        0.3560                           0.4577
pre_covid_2015_2019 PORTFOLIO_50_50         GJR-GARCH t   1234          0.3166             0.4419                  0.5166                     0.7153                        0.4908                           0.5890
pre_covid_2015_2019 PORTFOLIO_50_50 Simulacao historica   1234          0.0003             0.0102                  0.1271                     0.3521                        0.0004                           0.0079
pre_covid_2015_2019           VALE3         EWMA normal   1234          0.3166             0.4419                  0.5166                     0.7153                        0.4908                           0.5890
pre_covid_2015_2019           VALE3         GJR-GARCH t   1234          0.6961             0.7371                  0.6563                     0.7717                        0.8392                           0.8490
pre_covid_2015_2019           VALE3 Simulacao historica   1234          0.0128             0.0658                  0.3713                     0.7035                        0.0302                           0.0990
    covid_2020_2021            IBOV         EWMA normal    472          0.0048             0.0289                  0.4283                     0.7153                        0.0137                           0.0549
    covid_2020_2021            IBOV         GJR-GARCH t    472          0.0336             0.1326                  0.5101                     0.7153                        0.0842                           0.2021
    covid_2020_2021            IBOV Simulacao historica    472          0.0048             0.0289                  0.0019                     0.0421                        0.0001                           0.0054
    covid_2020_2021           PETR4         EWMA normal    472          0.0048             0.0289                  0.0311                     0.1866                        0.0018                           0.0166
    covid_2020_2021           PETR4         GJR-GARCH t    472          0.5699             0.6217                  0.0577                     0.2379                        0.1405                           0.2530
    covid_2020_2021           PETR4 Simulacao historica    472          0.1675             0.3174                  0.0047                     0.0421                        0.0071                           0.0318
    covid_2020_2021 PORTFOLIO_50_50         EWMA normal    472          0.0336             0.1326                  0.1982                     0.5096                        0.0457                           0.1371
    covid_2020_2021 PORTFOLIO_50_50         GJR-GARCH t    472          0.1675             0.3174                  0.0047                     0.0421                        0.0071                           0.0318
    covid_2020_2021 PORTFOLIO_50_50 Simulacao historica    472          0.1675             0.3174                  0.0047                     0.0421                        0.0071                           0.0318
    covid_2020_2021           VALE3         EWMA normal    472          0.1675             0.3174                  0.5990                     0.7717                        0.3359                           0.4519
    covid_2020_2021           VALE3         GJR-GARCH t    472          0.5699             0.6217                  0.0577                     0.2379                        0.1405                           0.2530
    covid_2020_2021           VALE3 Simulacao historica    472          0.3250             0.4419                  0.0843                     0.3036                        0.1389                           0.2530
 recent_2022_onward            IBOV         EWMA normal   1222          0.1944             0.3244                  0.4884                     0.7153                        0.3390                           0.4519
 recent_2022_onward            IBOV         GJR-GARCH t   1222          0.7212             0.7419                  0.6547                     0.7717                        0.8490                           0.8490
 recent_2022_onward            IBOV Simulacao historica   1222          0.0473             0.1418                  0.8077                     0.8307                        0.1356                           0.2530
 recent_2022_onward           PETR4         EWMA normal   1221          0.0006             0.0102                  0.1204                     0.3521                        0.0008                           0.0094
 recent_2022_onward           PETR4         GJR-GARCH t   1221          0.1198             0.3080                  0.2645                     0.5951                        0.1600                           0.2743
 recent_2022_onward           PETR4 Simulacao historica   1221          0.1033             0.2861                  0.7762                     0.8219                        0.2548                           0.3822
 recent_2022_onward PORTFOLIO_50_50         EWMA normal   1221          0.0402             0.1326                  0.3341                     0.6682                        0.0764                           0.1966
 recent_2022_onward PORTFOLIO_50_50         GJR-GARCH t   1221          0.9517             0.9517                  0.1039                     0.3400                        0.2660                           0.3831
 recent_2022_onward PORTFOLIO_50_50 Simulacao historica   1221          0.0015             0.0181                  0.9032                     0.9032                        0.0065                           0.0318
 recent_2022_onward           VALE3         EWMA normal   1222          0.0405             0.1326                  0.3155                     0.6682                        0.0741                           0.1966
 recent_2022_onward           VALE3         GJR-GARCH t   1222          0.5099             0.5921                  0.0595                     0.2379                        0.1362                           0.2530
 recent_2022_onward           VALE3 Simulacao historica   1222          0.3314             0.4419                  0.7304                     0.7968                        0.5880                           0.6828
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
