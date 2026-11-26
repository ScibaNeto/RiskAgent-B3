# RiskAgent B3 — Relatorio da Fase 2

Projeto educacional. Este relatorio nao e recomendacao de investimento.

Execucao UTC: 2026-11-25 03:05:43
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

## Resultados por ativo/modelo

```text
          asset               model  n_obs  violations  violation_rate_pct  avg_var_pct  avg_es_pct  kupiec_p_value  christoffersen_p_value  conditional_coverage_p_value
           IBOV         EWMA normal   3187          50              1.5689      -3.1114     -3.5646          0.0029                  0.2067                        0.0053
           IBOV         GJR-GARCH t   3187          35              1.0982      -3.2756     -3.9675          0.5833                  0.3779                        0.5832
           IBOV Simulacao historica   3187          35              1.0982      -3.7469     -5.7614          0.5833                  0.0005                        0.0018
          PETR4         EWMA normal   3195          59              1.8466      -6.0492     -6.9304          0.0000                  0.0048                        0.0000
          PETR4         GJR-GARCH t   3195          40              1.2520      -6.9039     -8.9468          0.1684                  0.0138                        0.0187
          PETR4 Simulacao historica   3195          48              1.5023      -8.1858    -12.2542          0.0079                  0.0001                        0.0000
PORTFOLIO_50_50         EWMA normal   3195          53              1.6588      -4.7458     -5.4371          0.0006                  0.2955                        0.0017
PORTFOLIO_50_50         GJR-GARCH t   3195          37              1.1581      -5.1468     -6.3828          0.3811                  0.0756                        0.1406
PORTFOLIO_50_50 Simulacao historica   3195          43              1.3459      -5.9189     -8.7225          0.0620                  0.0212                        0.0123
          VALE3         EWMA normal   3196          49              1.5332      -5.3909     -6.1762          0.0050                  0.7669                        0.0185
          VALE3         GJR-GARCH t   3196          31              0.9700      -5.9151     -7.3920          0.8638                  0.0341                        0.1044
          VALE3 Simulacao historica   3196          41              1.2829      -6.2871     -9.0601          0.1236                  0.5417                        0.2537
```

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

- `phase2_metrics.csv`: metricas e testes estatisticos.
- `phase2_forecasts.csv`: previsoes diarias de VaR e ES.
- `phase2_garch_diagnostics.csv`: convergencia das estimacoes GJR-GARCH.
- `phase2_portfolio_weights.csv`: pesos usados na carteira demonstrativa.
- `phase2_portfolio_var.png`, `phase2_portfolio_es.png` e `phase2_backtest_exceptions.png`: graficos.
