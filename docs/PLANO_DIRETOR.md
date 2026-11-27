# RISKAGENT B3
## Onde o projeto está e como chegar à plataforma do desenho

**Auditoria de 25 de novembro de 2026** · Daily Quantitative Investment Intelligence Platform

**Missão** · Transformar dados financeiros em inteligência quantitativa, explicável, atualizada e verificável.

**Atualização de 25/11 à tarde.** O aceite do Marco 1, o estado dos 15 componentes e as primeiras entregas 2.2/2.3 estão no [relatório de progresso](ACEITE_MARCO_1.md). O texto abaixo registra a auditoria anterior.

**Marco 2.** A execução seguinte incorporou inferência do ES e choques simultâneos no [relatório de risco](RISCO_ES_CHOQUES.md).

### O que você já consegue fazer

Hoje você consegue abrir uma execução local, escolher PETR4 e responder a uma pergunta concreta: *qual perda o modelo estimava para aquele pregão e o que aconteceu de fato?* No backtest de 18/05/2017, o modelo GJR-GARCH-t estimou um limite de **−5,96%** para a cauda de 1%. O retorno logarítmico observado foi **−17,15%**. O sistema contou uma violação. Esse exemplo usa preços ajustados da cópia histórica disponível em 2026. Uma previsão efetivamente publicada em 2017 exigiria registros daquela época.

| Para acompanhar o projeto | Posição atual |
|---|---|
| Onde entramos no desenho | Em **Dados financeiros**. Já há ingestão, calendário de pregões, controles de qualidade, cache e cópias por execução. |
| O que sai desses dados | O **Risk Engine** calcula medidas de perda. O **Portfolio Engine** já tem o exemplo de uma carteira hipotética 50/50. O bloco **Model Validation** avalia essas estimativas no histórico. |
| O que você pode abrir hoje | Tabelas CSV, gráficos e relatórios das execuções locais. As 12 telas, o scanner e o chat são entregas futuras. |
| O que mudou nesta auditoria | O teste de perdas agrupadas passou a respeitar interrupções na série de pregões. Os resultados quantitativos e a comparação estão abaixo. |
| Entrega já disponível | Consultar os preços que o projeto havia arquivado até um horário. A próxima extensão é guardar e identificar os lotes recusados na coleta. |

### 1. O que foi verificado

A cópia de trabalho está em `C:\Users\joses\Downloads\riskagent-b3`, na branch `codex/riskagent-marco-0-garch-alignment`. O GitHub e o HEAD local apontavam para `16d3f6c45cebee9c695a4b8a4135261eaabe30b9`. O commit público contém oito arquivos, entre eles o script da Fase 1 e seus resultados. A cópia local inclui mudanças ainda fora desse commit, como a Fase 2.1, os módulos de dados, os testes e os relatórios mais recentes. A consulta ao GitHub retornou zero PRs abertos e zero issues abertas. [Commit público inspecionado](https://github.com/ScibaNeto/RiskAgent-B3/commit/16d3f6c45cebee9c695a4b8a4135261eaabe30b9)

- A auditoria conferiu os pontos de entrada dos dois programas, as funções de ingestão, calendário, risco e backtesting, os testes, a árvore Git e os resultados gravados. Antes das alterações de código foi criada e verificada uma cópia local com 179 arquivos, incluindo os dados, os resultados e o Git.
- Os **48 testes anteriores passaram**. A nova execução da Fase 2.1 utilizou o modo offline estrito. Os hashes SHA-256 das três entradas conferiram com os respectivos manifestos. A Fase 1 tem uma execução anterior preservada com 480 ajustes GJR convergentes. Nesta auditoria, os testes das duas fases foram repetidos e a Fase 2.1 foi executada de ponta a ponta.
- A Fase 2.1 calcula risco histórico, EWMA e GJR-GARCH com distribuição t-Student. O nível implementado é VaR de 99%, com janela de 1.000 retornos e reestimação do GJR a cada 20 observações. A rotina avalia VaR com Kupiec, independência e cobertura condicional. Calcula também o score conjunto FZ0 para VaR e ES, métricas por período e ajustes de comparações múltiplas.

**Inventário de preços.** A tabela usa o manifesto da execução, com corte na madrugada de 25/11. O pregão mais recente já encerrado era 24/11. A cobertura ficou classificada como parcial nas três séries.

| Série | Intervalo dos preços aceitos | Preços aceitos | Retornos diários usados | Pregões internos sem preço | Atraso no corte |
|---|---|---:|---:|---:|---:|
| PETR4 | 04/01/2010 a 23/11/2026 | 4.187 | 4.184 | 2 | 1 pregão |
| VALE3 | 04/01/2010 a 24/11/2026 | 4.188 | 4.185 | 2 | 0 |
| Ibovespa | 04/01/2010 a 24/11/2026 | 4.187 | 4.183 | 3 | 0 |

Os totais maiores citados no texto do projeto vieram da versão anterior ao tratamento de lacunas. As séries atuais somam 12.552 retornos de ativo por data. Vários se referem ao mesmo dia e compartilham os mesmos choques de mercado. A contagem de exemplos estatisticamente independentes exige avaliar essas dependências.

### 2. Os 15 blocos do seu projeto

“Em uso” significa que há um caminho executável no projeto. “Parcial” indica uma capacidade demonstrada e uma lacuna relevante. “Planejado” identifica um componente ainda por desenvolver.

| Bloco | Estado verificável e componente reaproveitável | Dependência ou entrega que falta |
|---|---|---|
| 1 · Data Intelligence | **Parcial.** Fechamento ajustado, Yahoo Finance, cache incremental, verificações BVMF, snapshots e manifesto. | Contrato temporal compartilhado, versões consultáveis por data, quarentena de lotes, conciliação de fontes e outras famílias de dados. |
| 2 · Quantitative Risk | **Em uso para o recorte atual.** VaR e ES a 99%, três modelos e backtests nas Fases 1 e 2.1. | Validar a dinâmica após lacunas, ampliar níveis de risco, testar ES formalmente e implementar estresse. |
| 3 · Market Prediction | **Planejado.** As previsões de risco existentes podem servir de variável de entrada. | Alvos de 1, 5, 20 e 60 pregões, baselines, treinamento cronológico, calibração e avaliação final reservada. |
| 4 · Technical Intelligence | **Planejado.** Os retornos e o calendário já servem de base para tendência e momentum. | Indicadores com convenções testadas. ATR demanda máximas e mínimas. Indicadores de volume dependem da nova coleta. |
| 5 · Fundamental Analysis | **Planejado.** | Associar empresa ao ativo. Guardar demonstrativo, período, versão e divulgação antes de calcular indicadores e comparar setores. |
| 6 · Macro Intelligence | **Planejado.** | Séries econômicas com unidade, frequência, divulgação e revisões. Começar por uma série da Selic. |
| 7 · News & Sentiment | **Planejado.** | Coletar documentos autorizados, deduplicar, vincular empresa e preservar link, publicação e coleta. |
| 8 · Portfolio Intelligence | **Parcial.** Carteira demonstrativa de PETR4/VALE3 com pesos iguais, rebalanceamento diário implícito, VaR e ES. | Carteiras hipotéticas configuráveis, concentração, contribuições de risco, custos e cenários. |
| 9 · Strategy Research | **Planejado.** Os resultados por data e as métricas de risco são insumos. | Simulação de estratégias com regra de execução, histórico do universo, custos, liquidez e benchmark comparável. |
| 10 · Market Regime | **Planejado.** Há relatórios por períodos históricos definidos manualmente. | Detectar regimes com informações disponíveis na data. Avaliar estabilidade e utilidade fora da amostra. |
| 11 · Opportunity Intelligence | **Planejado.** | Integrar resultados datados com risco, tendência, fundamentos e incerteza. O scanner deve poder retornar zero candidatos. |
| 12 · Explainable AI | **Parcial nos diagnósticos de risco.** Estão disponíveis parâmetros, convergência, violações e desempenho histórico. | Explicação por estimativa com fatores, limitações, divergências e evidências. Importância de variáveis exige modelo validado. |
| 13 · Generative AI Copilot | **Planejado.** | Ferramentas de leitura com esquemas, recuperação de documentos e respostas com fonte e data. Os módulos quantitativos produzem os números. |
| 14 · Model Validation & MLOps | **Parcial.** Há testes, avaliação temporal de risco, logs de ajuste, versões de bibliotecas e hashes de entrada. | Versão exata do código/modelo, registro de experimentos, calibração, monitoramento e aprovação de candidatos. |
| 15 · Dashboard & Application | **Planejado.** Existem relatórios e gráficos estáticos reutilizáveis. | API de consulta e navegação pelos resultados de uma mesma execução. A primeira tela com dados suficientes é o Risk Center. |

### 3. Correção executada e resultado

O teste de Christoffersen investiga se uma perda acima do VaR costuma vir logo depois de outra. Para isso, precisa saber quais pregões eram vizinhos. A função anterior removia os registros ausentes e depois percorria as linhas restantes em sequência. Nos dados de PETR4, isso criava uma ligação entre **19/11/2020 e 24/11/2020**. O fechamento de 20/11 estava ausente e o retorno do pregão seguinte também não podia ser calculado.

A Fase 2.1 agora alinha os indicadores ao calendário BVMF antes da contagem. Feriados e fins de semana preservam a vizinhança entre pregões. Um pregão sem retorno ou sem previsão válida interrompe a contagem. O CSV registra quantos pares foram usados e quantas ligações foram descartadas. Quando os dados não permitem estimar o teste, o veredito aparece como **indisponível**.

| PETR4 · GJR-GARCH-t | Antes | Depois |
|---|---:|---:|
| Dias avaliados | 3.184 | 3.184 |
| Perdas além do VaR | 39 | 39 |
| Pares usados no teste de independência | 3.183 | 3.182 |
| Pares em que nenhum dos dias teve violação | 3.107 | 3.106 |
| P-valor bruto de cobertura condicional | 0,115185 | 0,114718 |

**Método.** Para cada pregão válido, o indicador vale 1 quando o retorno observado é inferior ao VaR previsto. As quatro contagens `n00, n01, n10, n11` usam pares de pregões consecutivos. O teste de independência compara a verossimilhança de uma taxa comum com a de duas taxas, uma por estado anterior. A cobertura condicional usa os mesmos pares e condiciona no primeiro dia de cada trecho. O teste de Kupiec isolado usa todos os dias avaliáveis. Os p-valores são aproximações assintóticas, com interpretação especialmente limitada quando há poucas violações. [Christoffersen, *Evaluating Interval Forecasts*, seção 3](https://users.ssc.wisc.edu/~behansen/718/Christoffersen1998.pdf)

**Evidência.** Na entrega da correção do backtest passaram **51 testes**. Os três novos casos cobrem lacunas na cotação ou na previsão, ausência de pares e presença de um único estado. A compilação e a verificação das dependências passaram. A combinação instalada de calendário e pandas emitiu um aviso de depreciação durante os testes. A execução completa produziu 12 combinações de série/modelo, 36 avaliações por período e **640 de 640 ajustes GJR convergentes**. As previsões gravadas antes e depois têm conteúdo idêntico byte a byte. A mudança afetou a avaliação dessas previsões.

| Para conferir na cópia local | Caminho relativo à raiz do projeto |
|---|---|
| Código corrigido e testes | `src/phase2_risk_engine_v2.py` e `tests/test_phase2_statistics.py` |
| Nova execução completa | `outputs/phase2_1/runs/run_20261125T052512_992676Z/` |
| Execução anterior comparável | `outputs/phase2_1/runs/run_20261125T051352_640204Z/` |
| Entradas e previsões | `manifest.json`, `inputs/` e `phase2_forecasts.csv` em cada execução |
| Resultado do teste corrigido | `phase2_metrics.csv` e `phase2_period_metrics.csv` na nova execução |

### 4. Arquitetura e dependências

A proposta é manter uma aplicação Python modular no mesmo repositório. Os scripts atuais continuam como entradas executáveis. Extrair uma função para um módulo compartilhado faz sentido quando um segundo motor precisar dela. As evidências e os contratos abaixo orientam essas extrações.

1. **Provedores → dados históricos.** Cada adaptador conhece o formato e a convenção do provedor. A validação classifica o lote, conserva a versão e registra o último sucesso ou o motivo da recusa.
2. **Histórico → motores.** Risco e técnica leem preços. Fundamentos leem documentos por empresa. Macro e notícias têm seus próprios calendários. Cada motor recebe um horário de corte e devolve resultados com unidade, período e origem.
3. **Motores → previsão, carteira e pesquisa.** Variáveis e alvos seguem o calendário apropriado. O laboratório de estratégias aplica o atraso de execução e os custos. O registro de modelos identifica qual versão pode gerar previsões.
4. **Resultados → scanner.** O scanner compara apenas informações compatíveis no tempo, mostra cobertura, incerteza e conflitos. Uma classificação composta dependerá de validação histórica dos pesos.
5. **Resultados → interface e Copilot.** Dashboard e chat consultam as mesmas funções de leitura. Uma resposta sobre PETR4 deve apontar o ativo, a data, a execução e os resultados usados. Documentos recuperados são evidência citável. A permissão para acionar ferramentas é definida pela aplicação.
6. **Resultados realizados → validação.** Quando o horizonte vence, o sistema compara a previsão registrada com o realizado. O monitoramento investiga degradação. Um candidato passa por janelas cronológicas e pelo teste final antes de qualquer promoção.

**Armazenamento e custo.** Os CSVs e manifestos locais atendem à escala atual. A primeira extensão proposta é um catálogo SQLite para localizar versões, mantendo os conteúdos imutáveis por hash. Parquet e DuckDB passam a fazer sentido quando consultas a vários ativos e fontes ficarem caras. API, interface web e provedor de linguagem entram nas etapas que os utilizam. A auditoria e a correção rodaram localmente, sem contratar serviços.

**Como os resultados chegam às 12 telas.** Risk Center e Model Observatory podem reaproveitar desde já relatórios de risco e diagnósticos. Market Overview e Asset Intelligence dependem também de dados diários por ativo. Fundamental Center, Macro Center e News Intelligence dependem de seus coletores. Prediction Center exige modelos calibrados. Portfolio Lab e Research Lab dependem das simulações. Opportunity Scanner e AI Copilot consomem os resultados integrados. A rotina final após o fechamento publica a execução com sua cobertura e continua avaliando previsões antigas à medida que os resultados chegam.

### 5. Ordem de desenvolvimento e critérios de aceite

| Marco | Entrega observável | Como decidir que a etapa pode avançar |
|---|---|---|
| 0 · Auditoria | Inventário de código, árvore pública e resultados locais. Esta revisão atualiza o diagnóstico anterior. | Um revisor localiza arquivos e execuções e reproduz o exemplo de PETR4. |
| 1 · Fundação | Contratos de observação, consulta por data de conhecimento, armazenamento de revisões, quarentena e conciliação. | Uma revisão posterior não altera o resultado da consulta anterior. Dado futuro é recusado, lote inválido é rastreável e o último cache válido pode ser reproduzido. |
| 2 · Risk Engine | Consolidar a Fase 1 e a 2.1. Proposta para 2.2: validar a recursão com lacunas, incluir múltiplos níveis de VaR, intervalos de violações e backtest de ES. Proposta para 2.3: estresse histórico e hipotético. | Fórmulas conferidas em casos conhecidos, curvas comparadas nos mesmos dias, falhas explicitadas e cenários com premissas reproduzíveis. |
| 3 · Motores de mercado | Entregar por fatias. Primeiro preço, volume e indicadores técnicos. Depois demonstrativos e macro com divulgação. Em seguida notícias e regime. | Cada adaptador passa por teste de revisão temporal e de falha. Cada indicador tem unidade, calendário e caso de referência. |
| 4 · Prediction Engine | Baseline de frequência histórica e regressão logística para o próximo pregão. Depois ampliar para 5, 20 e 60 pregões e previsões de retorno/quantis. | Treino, validação de calibração e teste final têm datas registradas. Usar walk-forward, excluir alvos sobrepostos quando necessário e publicar Brier, log loss e curvas por horizonte contra o baseline. |
| 5 · Carteira e estratégias | Pesos configuráveis, correlação, cenários, benchmark e simulações com execução e custos. | A carteira 50/50 reproduz a referência. Casos controlados conferem custos, turnover, pesos e retornos. Resultado líquido e hipóteses ficam visíveis. |
| 6 · Opportunity Intelligence | Ficha diária por ativo com risco, tendência, contexto, qualidade da informação e divergências. | Um caso com sinais conflitantes exibe o conflito. Um dia com evidência insuficiente admite lista vazia. Eventuais pesos são comparados fora da amostra e testados por sensibilidade. |
| 7 · Copilot | Primeiras ferramentas de consulta de ativo e risco, seguidas de documentos e notícias com citação. | Perguntas de referência recuperam os valores da execução correta. Casos sem dados declaram a limitação. Testes cobrem conteúdo externo, permissões, privacidade e orçamento. |
| 8 · Plataforma | API e painel. Começar com risco e página do ativo, acrescentando as demais telas quando seus motores estiverem prontos. | A métrica na tela confere com a execução selecionada. Fonte, data, unidade, tipo de resultado e estado parcial aparecem na interface. |
| 9 · Automação e MLOps | Rotina pós-mercado, agenda por fonte, registro de experimentos, monitoramento e promoção controlada. | Reexecutar uma data preserva versões. Uma falha recuperável usa a política de cache. Atrasos geram alerta. A comparação com o realizado ocorre só quando vence o horizonte. |
| 10 · Consolidação | Demonstração integrada e auditoria final de desempenho, custo, recuperação, segurança e limitações. | Reconstruir uma análise completa em ambiente limpo a partir do código, dados versionados, modelo e configuração. |

**Política inicial proposta.** Consultar preços após o fechamento do pregão e documentos após divulgação. Executar inferência diária com a versão aprovada. A reestimação atual do GJR a cada 20 observações é uma configuração do baseline. Para modelos futuros, definir em validação a frequência de treino e guardar o candidato separadamente até sua avaliação. Um período já examinado nas execuções históricas serve para pesquisa retrospectiva. Para medir desempenho prospectivo, congelar critérios agora e registrar as previsões futuras antes de observar o resultado.

### 6. Incremento entregue no Marco 1

**Bloco do desenho: Dados financeiros.** Foi implementada a função `get_observations` em `src/known_prices.py`. Ela seleciona o último manifesto compatível até o horário consultado, verifica o hash do arquivo e recupera os fechamentos aceitos. O horário do manifesto é usado como evidência conservadora de disponibilidade local. A rotina lê os manifestos existentes por demanda. Um índice de banco de dados pode ser acrescentado se o volume justificar.

| Campo do contrato proposto | Significado |
|---|---|
| Ativo, campo, valor, unidade e provedor | Identificam exatamente o dado. Fechamento ajustado e cotação nominal têm convenções diferentes. |
| Data de referência | Pregão do preço ou período contábil/econômico medido. |
| Publicado em | Quando a fonte divulgou o dado, se houver evidência. Preservar a precisão original da data. |
| Observado em pelo RiskAgent | Primeiro instante comprovado em que a plataforma teve acesso àquela versão. |
| Identificador da versão, hash e execução | Permitem refazer a consulta e seguir a cadeia de revisões. |

**Critério demonstrável.** Em uma série de teste, a plataforma recebe a versão A na segunda-feira e uma correção B na quarta. A consulta com corte na terça deve devolver A mesmo depois da correção. A consulta posterior deve devolver B. Uma consulta anterior ao primeiro registro deve retornar “histórico de versões indisponível”. A data de um preço antigo dentro de um CSV coletado hoje, sozinha, é insuficiente para afirmar o que se conhecia naquele pregão.

**Exemplo executado.** Na raiz do repositório, `.\\.venv\\Scripts\\python.exe src\\known_prices.py PETR4 --as-of 2026-11-25T02:14:00-03:00` selecionou a execução `run_20261125T051352_640204Z`. O último fechamento ajustado disponível era R$ 41,30 em 23/11. Para um corte em 18/05/2017, a consulta retornou histórico de versões indisponível. Os testes novos simulam revisão, consulta anterior à primeira versão e alteração do arquivo após arquivamento. A disponibilidade local dos snapshots antigos permanece limitada às datas efetivamente registradas. A próxima implementação é a quarentena de lotes rejeitados antes do fallback, com motivo, fonte, instante e teste de preservação do cache.

**Fontes para os primeiros pilotos.**

- **Preços e volume.** Usar a série histórica da B3 para conciliar datas, volume e cotações nominais. A B3 informa que os preços históricos vêm sem ajuste por proventos. Comparar valores ajustados do Yahoo exige reconstruir a convenção dos eventos corporativos. Verificar as condições aplicáveis ao uso e à distribuição antes de disponibilizar dados a terceiros. [Séries históricas da B3](https://www.b3.com.br/main.jsp?doui_processActionId=setLocaleProcessAction&locale=pt_BR&lumA=1&lumII=2C9E0371634B781701634B7C27111B5F&lumPageId=8A6A8C244DE7C289014DE80C873C130E) · [FAQ de Market Data](https://b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/distribuidores/perguntas-frequentes/)
- **Fundamentos.** Usar ITR e DFP da CVM. Os arquivos podem incorporar reapresentações. Guardar o documento e sua versão desde a primeira ingestão e verificar a data de disponibilização antes de vinculá-lo ao preço. [ITR da CVM](https://dados.cvm.gov.br/dataset/cia_aberta-doc-itr) · [DFP da CVM](https://dados.cvm.gov.br/dataset/cia_aberta-doc-dfp)
- **Macro.** A série 11 do BCB divulga a Selic em percentual ao dia. As consultas por intervalo a séries diárias em JSON/CSV têm limite de dez anos. Para indicadores do IBGE, associar a divulgação ao calendário. Para séries americanas revisadas, avaliar as versões históricas do ALFRED. [Selic no BCB](https://dadosabertos.bcb.gov.br/pt_BR/dataset/11-taxa-de-juros---selic) · [Calendário do IBGE](https://www.ibge.gov.br/calendario-de-divulgacao.html) · [Versões históricas do ALFRED](https://fred.stlouisfed.org/docs/api/fred/alfred.html)

### 7. Pendências que afetam a leitura dos resultados

1. **Recursão da volatilidade.** A correção desta auditoria cobre o backtest de independência e cobertura condicional. GJR e EWMA ainda precisam de política explícita para recomeçar ou propagar a variância após lacunas.
2. **Identidade da execução.** Acrescentar versão do modelo e identificação do código local, incluindo alterações fora do commit. Ao comparar Fase 1 e 2.1, verificar versões dos dados e as datas. Hoje a rotina procura o CSV mais recente da Fase 1.
3. **ES e escassez de eventos.** O FZ0 permite comparar previsões conjuntas. Ainda faltam teste formal de ES, avaliação das amostras de cauda e intervalos para a frequência de violações. Convergência do otimizador indica que o ajuste terminou segundo o critério numérico.
4. **Fontes e abrangência.** A verificação desta auditoria utilizou os arquivos locais. A disponibilidade de versões históricas para preços, macro, notícias e demonstrativos deve ser demonstrada fonte a fonte. Ampliar o universo exige identificar papéis que saíram do mercado e preservar sua composição em cada data.

O primeiro resultado visível depois da fundação deve ser uma ficha de PETR4 que mostre a data da análise, os preços utilizados, o risco estimado, o resultado realizado e a origem de cada número. Esse mesmo registro poderá alimentar o Risk Center e responder a uma pergunta do Copilot.

### Componente 4 · Análise técnica de PETR4

Parcial. O painel por data e a central didática mostram a média móvel simples de 20 fechamentos ajustados. A janela termina no pregão consultado e exige 20 valores válidos consecutivos. O indicador usa a versão do histórico carregada pelo painel. RSI, MACD e volume seguem pendentes.

## Passagem ao Marco 3 · 25/11/2026

Marco 2 aceito no universo diário demonstrativo. Avançaram os componentes Risco quantitativo, Carteiras, Validação e Painel. Os demais mantêm o estágio registrado. Evidências, limites e reprodução no [aceite do Marco 2](ACEITE_MARCO_2.md). O próximo incremento é o volume negociado na página do ativo.

### Marco 3 em andamento · PETR4 intradiária

Avançaram os componentes 1 (dados), 4 (análise técnica) e 15 (painel). O modo ao vivo apresenta preço e volume da última barra encerrada, horários e atraso, situação do pregão, volume diário e média dos 20 pregões anteriores. Na verificação local de 25/11, o provedor retornou 64.227.800 ações no dia e média anterior de 58.118.015. Os cálculos de risco permanecem diários. Fundamentos, macroeconomia, notícias e regime continuam no escopo do Marco 3.

## Passagem ao Marco 4 · 25/11/2026

Marco 3 aceito para a primeira integração de PETR4 e contexto brasileiro. No roteiro de 15 componentes avançaram os componentes 1 (dados), 4 (técnica), 5 (fundamentos), 6 (macro), 7 (notícias), 10 (regime), 14 (validação) e 15 (aplicação). As expansões e os demais componentes mantêm seus estados. [Critérios, resultados, limites e reprodução](ACEITE_MARCO_3.md).

## Marco 4 em andamento · Primeira previsão de direção

O experimento da execução `run_20261126T011339_584948Z` estima a probabilidade de o fechamento ajustado de PETR4 subir entre dois pregões BVMF consecutivos. Usa retornos de PETR4 e Ibovespa de um dia, retorno acumulado da ação em cinco dias e desvio amostral dos últimos 20 retornos. As variáveis usam log-retornos. O alvo é excluído se faltar qualquer um dos dois fechamentos. A taxa básica de comparação é a proporção de altas cujos desfechos já eram conhecidos antes do bloco de teste.

A regressão logística usa padronização ajustada no treino e penalização L2 unitária. A cada ano, o treino cresce; as últimas 252 observações elegíveis anteriores ao teste calibram a probabilidade por uma segunda regressão logística. Cortes estritos pelas datas de realização evitam sobreposição entre treino, calibração e teste. O painel informa as datas efetivas de cada bloco. O último alvo avaliado ocorreu em 24/11/2026.

Na reconstrução retrospectiva de 1.468 previsões, Brier 0,24998 e log loss 0,69313 para o modelo; Brier 0,24984 e log loss 0,69283 para a frequência histórica. A referência teve menor erro em ambas. O modelo permanece experimental. O arquivo `entregas/outputs/Previsoes-PETR4-1-pregao.csv` guarda cada data de origem, data do alvo, resultado e duas probabilidades. As frequências observadas por faixa aparecem no painel. O histórico ajustado pertence à versão do snapshot e pode incorporar revisões posteriores às datas avaliadas. Os resultados são retrospectivos e não constituem evidência prospectiva.

Avançaram Previsão de Mercado, Validação e Painel. Permanecem os horizontes de 5, 20 e 60 pregões, avaliação de retornos e quantis e o registro prospectivo antes do resultado.
## Marco 4 · Entrega do motor e início da avaliação prospectiva

Horizontes de 1, 5, 20 e 60 pregões integrados com retornos, quantis, comparações cronológicas e registro antes do vencimento. Avançaram os componentes 3 (previsão), 14 (validação) e 15 (painel). A maturação prospectiva segue aberta. [Aceite técnico e evidências](ACEITE_MARCO_4.md).
