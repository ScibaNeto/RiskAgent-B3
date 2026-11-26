# RiskAgent B3 · Risco de cauda e choques conjuntos

**25/11/2026.** O Risk Engine agora testa o momento de Expected Shortfall e calcula cenários com choques simultâneos nas posições. A execução oficial usou os caches locais das três séries e os pesos de 50% em PETR4 e 50% em VALE3.

## Resultado da Fase 2.2

O EWMA com distribuição normal apresentou evidência de subestimação do risco de cauda nas quatro séries ao nível de 5%, após Holm sobre 12 comparações. O indicador é conjunto: uma discrepância pode vir da frequência de violações do VaR, da perda observada nessas violações ou de ambas. Para o GJR-GARCH-t e a simulação histórica, a evidência foi insuficiente para rejeitar a hipótese neste teste.

| Série | p ajustado, EWMA normal |
|---|---:|
| PETR4 | 0,00082 |
| VALE3 | 0,02541 |
| Ibovespa | 0,01118 |
| Carteira 50/50 | 0,00792 |

### Método e limites

Para o nível de cauda α = 1%, em cada dia elegível calcula-se **m = 1 − (retorno / ES) × indicador(retorno < VaR) / α**. VaR e ES usam a convenção de retornos com sinal. O ES deve ser negativo e menor ou igual ao VaR. Sob a referência de calibração conjunta, a média esperada do momento é zero. Valores negativos apontam na direção de risco subestimado. O momento parte do teste incondicional de Acerbi e Székely. [Artigo dos autores](https://www.msci.com/research-and-insights/paper/research-insight-backtesting-expected-shortfall-december-2014)

A inferência implementada usa aproximação normal unilateral com erro padrão HAC e pesos Bartlett. O número de defasagens é a parte inteira de 4 × (n/100)^(2/9), igual a oito nesta execução. O estimador soma as covariâncias dentro de trechos de pregões consecutivos e condiciona a análise às datas disponíveis. A cauda inferior da distribuição normal fornece o p-valor bruto. A correção de Holm considera as combinações de modelo e série avaliáveis. [Newey e West](https://www.nber.org/papers/t0055)

É uma aproximação histórica que depende de estabilidade dos momentos e dependência temporal suficientemente fraca. A incerteza da seleção dos modelos e mudanças estruturais podem afetar a leitura. Foram adotados limites operacionais de pelo menos 20 violações esperadas e 10 realizadas no domínio válido. Com amostra escassa ou variância degenerada, o resultado fica indisponível. Esses limites evitam apresentar inferência nos casos mais frágeis e não asseguram precisão em amostras pequenas. O teste implementado usa distribuição assintótica, distinta da simulação de valores críticos condicionada às distribuições preditivas completas.

## Resultado da Fase 2.3

| Cenário de um pregão | PETR4 | VALE3 | Carteira |
|---|---:|---:|---:|
| Histórico em 09/03/2020 | −29,70% | −15,20% | −22,45% |
| Hipotético, queda uniforme | −10% | −10% | −10% |
| Hipotético, queda assimétrica | −20% | −10% | −15% |
| Hipotético, movimentos opostos | −15% | +5% | −5% |

O cálculo soma os retornos simples ponderados pelos pesos antes do choque. Os três choques conjuntos são premissas ilustrativas. Nenhuma probabilidade foi atribuída a esses cenários. Os dois choques isolados anteriores continuam disponíveis no CSV.

## Evidência e continuidade

- Execução nova em `outputs/phase2_1/runs/run_20261125T173017_620715Z/`. Comparação com `run_20261125T172544_507316Z`. O arquivo de previsões coincidiu byte a byte e todas as colunas anteriores de métricas de cauda coincidiram após leitura.
- 64 testes passaram. Os três novos casos verificam o estimador HAC contra uma matriz Bartlett calculada à mão com uma lacuna, a direção do teste e a insuficiência de violações, e o retorno de choques conjuntos com pesos desiguais. A compilação passou. Os 640 ajustes GJR registraram convergência.
- Implementação em `src/risk_extensions.py`, integração em `src/phase2_risk_engine_v2.py` e testes em `tests/test_risk_extensions.py`. Para repetir a partir da raiz do projeto, executar `.\.venv\Scripts\python.exe src\phase2_risk_engine_v2.py --offline --strict-cache`.
- No roadmap, avançaram Quantitative Risk, Portfolio Intelligence e Model Validation. A próxima decisão do Marco 2 é definir como EWMA e GJR devem atualizar a variância depois de lacunas e verificar o efeito nos mesmos pregões de avaliação. Também permanecem pendentes os níveis adicionais de VaR e o estresse com fatores macroeconômicos estimados.

### Fase 2.2 · Sensibilidade à primeira observação após lacunas

O motor exporta `phase2_2_gap_sensitivity.csv` em cada nova execução. A comparação arquivada em `entregas/outputs/Risco-apos-lacunas.csv` usa os resultados de `run_20261125T173017_620715Z`. Contam-se os pregões BVMF sem retorno diário observável entre dois retornos válidos. A comparação abrange o primeiro retorno disponível depois da lacuna. Cada linha usa a mesma data e os mesmos parâmetros da previsão original. Os resultados históricos originais continuam como referência.

Para EWMA, substituir o quadrado do choque ausente pela sua esperança condicional mantém a variância. Para GJR com inovação simétrica, cada sessão ausente leva h a omega + (alpha + beta + gamma/2) × h. A coluna de sensibilidade aplica o quantil t à raiz da variância esperada. Essa aproximação isola o efeito da passagem do tempo, sem integrar toda a distribuição de volatilidades ou reestimar o modelo. A alteração de persistência nos dias seguintes ainda não foi avaliada.

Cada modelo apresentou quatro casos avaliáveis (ativo e data) e cinco sem previsão. Em PETR4, em 24/11/2020, o VaR do GJR passou de −6,16% para −6,41% nessa comparação. Alguns ativos compartilham datas e a carteira inclui os mesmos ativos. A evidência é insuficiente para eleger uma política superior.