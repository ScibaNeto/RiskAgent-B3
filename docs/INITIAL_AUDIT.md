# RiskAgent B3 — auditoria inicial (Marco 0)

Data da auditoria: 25/11/2026. Escopo: workspace local, branch pública `main`, dados locais, Fase 1 e implementações locais da Fase 2.

## Resumo executivo

O workspace local está vários passos à frente da branch pública. O `main` remoto e o `HEAD` local começaram no mesmo commit (`16d3f6c`, baseline da Fase 1), enquanto o workspace já continha alterações locais de cache, a Fase 2/2.1, relatórios e testes. Essas alterações foram preservadas e carregadas para a branch `codex/riskagent-marco-0-garch-alignment`; nenhum commit ou push foi feito.

A auditoria encontrou um erro confirmado de alinhamento no filtro GJR-GARCH da implementação local da Fase 2.1: o último desvio-padrão condicional observado estava sendo usado como previsão para o próximo retorno. A previsão ficava um passo atrasada e o filtro recomeçava repetidamente sobre uma amostra maior que a janela de ajuste. O cálculo foi corrigido para filtrar cada bloco a partir da janela de estimação e alinhar a primeira volatilidade filtrada ao primeiro retorno previsto.

## Inventário e estado inicial

- Branch inicial: `main`, no mesmo commit que `origin/main` (`16d3f6c`).
- Alterações preexistentes: README e `src/var_baseline.py` modificados; `src/phase2_risk_engine.py`, `src/phase2_risk_engine_v2.py`, `tests/` e saídas da Fase 2 não rastreados. Todos foram mantidos.
- O diretório de dados contém caches locais para PETR4, VALE3 e IBOV. Nenhum arquivo de preço foi adicionado ao Git.
- Não foi encontrado `AGENTS.md` no workspace.
- A branch de trabalho foi criada sem mudar o commit-base. O checkout continua sem commits novos.

## Código e métodos examinados

- Fase 1: `src/var_baseline.py` — preços ajustados, retornos logarítmicos, simulação histórica, EWMA normal, GJR-GARCH-t e Kupiec.
- Fase 2 legada: `src/phase2_risk_engine.py`.
- Fase 2.1 local: `src/phase2_risk_engine_v2.py` — VaR/ES, três modelos, diagnósticos GARCH, testes UC/IND/CC, FZ0, ajuste Holm/BH e carteira demonstrativa.
- Testes existentes e resultados CSV/relatórios das versões anteriores.

Convenção de sinais consistente no motor: retornos e VaR/ES da cauda inferior são negativos. O VaR histórico é um quantil móvel; o ES histórico resume a cauda empírica abaixo do quantil. O EWMA aplica o quantil normal à volatilidade estimada com retornos defasados. O GJR-GARCH-t padroniza a t-Student para variância unitária. O backtest usa Kupiec para cobertura incondicional e Christoffersen para independência; a cobertura condicional soma as duas estatísticas LR. O FZ0 é usado como score conjunto VaR/ES, não como p-valor. A carteira 50/50 calcula retornos simples ponderados e depois converte para retorno logarítmico, com rebalanceamento diário implícito.

## Dados locais

Os três caches têm datas ordenadas e únicas, sem nulos ou preços não positivos. Cobrem 04/01/2010 até 23–24/11/2026, com 4.188–4.197 preços por ativo. Foram encontrados retornos logarítmicos absolutos maiores que 15%: 1 para IBOV, 9 para PETR4 e 5 para VALE3. Permaneceram intactos; podem ser eventos de mercado e precisam ser verificados com fonte independente antes de qualquer limpeza.

No início da auditoria, o cálculo não guardava hash dos arquivos, fonte/fallback por ativo, convenção de ajuste nem versões em um manifesto por execução. Nesta branch, `src/data_manifest.py` passou a gerar esse registro para execuções da Fase 1 e Fase 2.1; foi anexado um manifesto à execução comparável abaixo. A idade do cache continua medida em dias corridos; o limite estrito pode precisar de um calendário de pregões para feriados prolongados. A execução completa não conseguiu resolver o Yahoo Finance por DNS e usou os caches recentes, em modo estrito.

Os termos de uso da Yahoo restringem reprodução, distribuição e exploração comercial sem permissão explícita; a biblioteca `yfinance` não substitui autorização do provedor dos dados. A B3 publica políticas diferentes por tipo de acesso/licença e distingue dados em tempo real/atrasados de dados históricos D-1. Portanto, antes de distribuir o dashboard, arquivos ou resultados baseados em dados de mercado, registrar o provedor e confirmar os direitos de uso para o caso específico. Fontes oficiais: [termos Yahoo](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html), [política de consumo de Market Data B3](https://www.b3.com.br/data/files/75/95/28/D6/9D881A10F75B881AAC094EA8/Market%20Data%20B3%20Consumption%20Policy%20V1.2.1.pdf) e [FAQ de Market Data B3](https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/distribuidores/perguntas-frequentes/).

## Achado quantitativo e correção

Antes da correção, `gjr_garch_t_var_es` filtrava retornos até `t-1`, mas usava `conditional_volatility.iloc[-1]`, que corresponde à volatilidade condicional do último índice observado, e não à variância prevista para o índice seguinte. Além disso, criava e filtrava novamente um modelo para cada dia do bloco.

Agora `_fixed_garch_block_sigma` filtra uma janela anterior de 1.000 retornos junto com o bloco previsto, usa os parâmetros estimados apenas na janela e extrai as volatilidades a partir da primeira posição fora da amostra. O bloco é validado antes de preencher as previsões, evitando resultados parciais em caso de erro. O diagnóstico também registra método do otimizador, iterações, log-likelihood e parâmetros; uma estimação sem flag de convergência não é presumida como sucesso. A Fase 1 agora aplica a mesma regra de convergência por bloco e exporta `garch_diagnostics.csv`. O teste de Kupiec passou a tratar amostra vazia e casos degenerados numericamente, e o resultado é descrito como “não rejeitado” em vez de “calibrado”.

Na execução comparável, com os mesmos caches e amostras, os números GJR mudaram:

| Série | Violações antes | Violações corrigidas | Kupiec p antes | Kupiec p corrigido |
|---|---:|---:|---:|---:|
| PETR4 | 40 | 38 | 0,1684 | 0,2962 |
| VALE3 | 31 | 29 | 0,8638 | 0,5929 |
| Carteira 50/50 | 37 | 38 | 0,3811 | 0,2962 |

Os valores mostram que o alinhamento afetava os resultados. P-valores acima de 0,05 apenas indicam que o teste não rejeitou sua hipótese nula; não comprovam que o modelo esteja calibrado.

## Testes e execução

- `python -m unittest discover -s tests -v`: 31 testes passaram.
- `python -m compileall -q src tests`: passou.
- `git diff --check`: passou; restaram avisos de conversão LF/CRLF nos arquivos preexistentes.
- Fase 1 executada com caches em modo estrito: 480/480 ajustes GJR convergiram; foram registrados método, iterações, log-likelihood, parâmetros e status.
- Fase 2.1 executada com caches em modo estrito: 640/640 ajustes GJR convergiram.
- A rede não resolveu o host Yahoo durante a atualização. As execuções offline usaram os caches, com preços mais recentes de 23–24/11/2026.
- Evidência Fase 1: `outputs/phase1/runs/run_20261125T044711_113772Z/`.
- Evidência Fase 2.1: `outputs/phase2_1/runs/run_20261125T044102_686674Z/`.

Os testes de fórmula recém-adicionados cobrem a padronização t, alinhamento sem look-ahead do EWMA e do bloco GJR, contagens de transição de Christoffersen e o cálculo de retorno simples da carteira. Ainda faltam testes de integração com um ajuste GARCH real e testes de qualidade do calendário/alinhamento dos dados.

## Limitações e próximos marcos

1. **Marco 1 — dados:** manifesto com hash, ticker, fonte/fallback, datas, contagens, ajuste, versões e verificações básicas implementado; falta validar gaps de pregão sem preencher silenciosamente. Avaliar fontes alternativas e seus termos antes de implementar uma.
2. **Marco 2 — baseline:** criar teste de ajuste GARCH integrado, registrar avisos/erros completos e comparar previsões antigas e corrigidas em validação cronológica. Definir um período final intocado.
3. **Marco 3 — ES/backtesting:** FZ0 é apenas score; ainda falta backtest formal de ES (por exemplo, Acerbi–Szekely), intervalos para taxa de violações e avaliação de VaR em múltiplos níveis.
4. **Marco 4 — carteira/robustez:** documentar a política constant-mix, avaliar datas ausentes com calendário B3, e adicionar contribuições de risco e cenários de estresse.
5. **Fases ML, agente e plataforma:** não há treinamento supervisionado, API, dashboard ou MLOps ainda. Só avançar após consolidar validação temporal e métricas de cauda.

Esta auditoria não certifica uso financeiro ou regulatório. A branch permanece local, sem publicação.
