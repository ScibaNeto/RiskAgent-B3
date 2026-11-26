# Marco 2 · Aceite do Risk Engine

Em 25/11/2026, a execução offline `run_20261126T011339_584948Z` atendeu aos critérios do Marco 2 da seção 5 do plano diretor para PETR4, VALE3, Ibovespa e a carteira demonstrativa 50/50. O identificador usa UTC. O último fechamento disponível foi 24/11, um pregão de atraso no momento da execução. O relatório de qualidade preserva as lacunas por ativo.

| Critério | Verificação |
|---|---|
| Conferir fórmulas em casos conhecidos | Testes unitários de VaR, ES, alinhamento GJR com referência da biblioteca, variação após lacunas e cenários. Novos casos verificam quantis históricos de janela anterior, escala da t e exposições conhecidas a dois fatores. Passaram 69 testes Python e o teste JavaScript. |
| Comparar nos mesmos dias | 114.642 linhas de VaR, com 36 combinações de ativo, modelo e nível. Cada ativo usa a interseção dos dias disponíveis. Conferidos o ordenamento dos três quantis e o alinhamento individual das 38.214 previsões a 99% com a referência. Os CSVs preexistentes na execução de referência de 25/11 às 17h30 UTC coincidiram byte a byte com seus equivalentes novos. |
| Explicitar falhas e limites | 640 de 640 ajustes GJR convergiram. O teste de ES apontou subestimação pelo EWMA nas quatro séries após correção de Holm. O modelo segue como referência comparativa. Os intervalos binomiais de cobertura supõem independência. |
| Fixar política após lacunas | Política oficial: atualizar a recursão nos retornos observáveis, com retornos entre preços separados por lacunas excluídos. O CSV de sensibilidade mostra a alternativa por variância esperada na primeira observação após cada lacuna. Quatro casos avaliáveis por modelo justificam preservar a referência ao comparar versões; o efeito acumulado nos dias posteriores continua desconhecido. |
| Reproduzir cenários | Há eventos históricos, choques individuais e conjuntos e três choques de fatores. A soma das contribuições ponderadas reproduz o impacto da carteira. O painel apresenta cobertura nos três níveis e os cenários de fatores. |

## Premissas dos fatores

A série 1 do SGS (dólar americano, venda, reais por dólar) foi consultada para 2023–2024 e arquivada em `data/reference/bcb_sgs_1_2023_2024.json`. O manifesto registra seu SHA-256 e o motor verifica os bytes ao ler. [Consulta original ao Banco Central](https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados?formato=json&dataInicial=01%2F01%2F2023&dataFinal=31%2F12%2F2024).

Em 498 retornos diários comuns entre 03/01/2023 e 30/12/2024, cada ação é regredida em retornos simples do dólar e do índice, com constante. Os impactos são incrementos relativos ao cenário de choque zero, mantendo os demais fatores constantes. A hipótese conjunta de Ibovespa −5% e dólar +5% produziu −3,85% na carteira. A calibração usa a versão retrospectiva arquivada. Os coeficientes medem associação na janela escolhida e podem mudar. A convenção de fechamento da série cambial pode diferir do horário de fechamento das ações.

## Reproduzir e abrir

No VS Code, abra `entregas/outputs/Painel-Etapa-2.html` no navegador para explorar o resultado arquivado. Para uma nova execução com os caches locais da base diária, rode `.\.venv\Scripts\python.exe src\phase2_risk_engine_v2.py --offline --strict-cache` e depois `.\.venv\Scripts\python.exe painel.py`. A validação de atualidade considera o dia da nova execução. A data e as versões dos insumos de referência ficam no manifesto arquivado.

A próxima etapa é o Marco 3, motores de mercado. A conclusão deste marco cobre o motor diário do universo demonstrativo. A ampliação do programa de risco inclui DQ, outros fatores como juros e commodities e atribuição marginal de risco.