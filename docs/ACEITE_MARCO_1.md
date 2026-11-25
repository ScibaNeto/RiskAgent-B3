# RiskAgent B3 · Aceite do Marco 1 e início do Marco 2

**25/11/2026 · Escopo aceito:** fechamentos diários ajustados de PETR4, VALE3 e Ibovespa, seus retornos e a carteira demonstrativa. Novas fontes, fundamentos e notícias terão critérios próprios no Marco 3. As seis condições abaixo encerram o Marco 1 neste universo.

| Critério fixado | Evidência de aceite |
|---|---|
| 1. Isolar lotes rejeitados e conservar a última entrada válida | Testes conferem conteúdo entregue pelo adaptador, origem, símbolo, tentativa, horário UTC, motivo e hash. Conferem também a igualdade byte a byte do cache após recusa e o tratamento de escrita concorrente. O pacote de quarentena é publicado por renomeação atômica. |
| 2. Atualizar incrementalmente e classificar a qualidade | A consulta real por sobreposição trouxe 24/11 para PETR4. O calendário BVMF identifica o último pregão encerrado. Testes distinguem falha de conexão, lote inválido, atraso, histórico incompleto, feriado e sessão em andamento. |
| 3. Verificar integridade e versões | SHA-256 identifica os bytes de cada snapshot. A gravação do manifesto e a leitura histórica verificam o arquivo. Corrupção simulada foi detectada. O manifesto também registra versão de Python, bibliotecas e hashes do código Python local. |
| 4. Reproduzir a consulta por data de conhecimento | Dois cortes reais em 25/11 recuperaram versões distintas e verificadas de PETR4. Antes da primeira versão compatível o sistema informa indisponibilidade. |
| 5. Alinhar os ativos | O relatório registrou 4.183 datas de retorno comuns aos três instrumentos. Testes específicos cobrem falta de um componente e exclusão de retornos que atravessariam uma lacuna. |
| 6. Repetir e preservar | Duas execuções offline produziram arquivos idênticos de previsões, métricas, cauda e cenários. Os 137 arquivos de resultados preexistentes conferiram byte a byte com a cópia anterior. 61 testes passaram, a compilação passou e o ambiente passou em pip check. |

### PETR4 em 24 de novembro

| Evidência em 25/11, horário de Brasília | Resultado |
|---|---|
| Consulta histórica às 02h14 | A versão arquivada terminava em 23/11, com fechamento ajustado de R$ 41,30. Na coleta isolada iniciada às 02h14, o Yahoo devolveu três linhas desde 18/11, sem datas excluídas pela validação. O dado ficou marcado com um pregão de atraso, dentro da tolerância de um. |
| Nova consulta à tarde | O Yahoo passou a devolver 24/11 com fechamento ajustado de R$ 40,55 e volume de 89.295.300. A atualização incremental trouxe o fechamento ao cache corrente. |
| Fonte independente | O arquivo diário da B3 retornou HTTP 200. O registro à vista de PETR4 em 24/11 contém fechamento nominal de R$ 40,55 e 88.597 negócios. A coincidência de valores nesse dia é compatível com a observação do Yahoo. Os campos “volume” e “número de negócios” medem coisas diferentes. [Arquivo diário oficial da B3](https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_D24112026.ZIP) |

O corte de 24/11 era apropriado pelo calendário da B3. A resposta disponível pela via de coleta da madrugada ainda terminava no dia anterior. Não há registro da hora de publicação nem evidência para atribuir a demora à B3, ao Yahoo, a uma camada de cache ou à biblioteca. As lacunas históricas de PETR4 continuam registradas separadamente do atraso, que passou a zero.

### O que o sistema registra agora

- **Entrada recusada.** A quarentena fica em `data/raw/quarantine/<ativo>/<evento>/`. O CSV contém o lote recebido na fronteira do adaptador, antes da limpeza. Para cache local inválido, conserva os bytes originais. O JSON registra SHA-256 e motivo. A resposta HTTP bruta do Yahoo fica fora do alcance do adaptador yfinance. Uma falha de conexão sem conteúdo produz diagnóstico de indisponibilidade.
- **Cinco situações.** A atualidade indica atualizado ou desatualizado pela distância em pregões. A cobertura identifica incompleto quando há lacunas. Lote inválido e provedor indisponível têm registros próprios. Um cache pode estar atualizado e incompleto ao mesmo tempo. Em interrupções, `data_failure.json` explica o motivo. Nas execuções aceitas, `data_quality.json` detalha cada fonte e o alinhamento.
- **Atualização automática.** O comando `.\.venv\Scripts\python.exe src\daily_update.py` verifica se a atualização é devida. A opção `--watch` repete essa verificação a cada 30 minutos enquanto o processo estiver em execução. Um bloqueio evita sobreposição entre instâncias desse comando. O acompanhamento contínuo fica disponível para operação local. Nenhum serviço de inicialização com o Windows foi instalado. Na verificação real, o comando constatou que o pregão de 24/11 já estava atualizado.
- **Point-in-Time.** `src/known_prices.py PETR4 --as-of 2026-11-25T02:14:00-03:00` recupera a versão da madrugada. O corte às 14h25 recupera a nova versão. Executar pelo Python do projeto. A evidência é a hora registrada no manifesto do RiskAgent. Para dados anteriores aos primeiros arquivos de época, a disponibilidade histórica efetiva do provedor permanece desconhecida.
- **Preservação.** Os caches ativos evoluem com a coleta. As versões anteriores estão em snapshots e no backup local `antes-quarentena-20261125T172218Z.zip`. O identificador SHA-256 detecta mudanças nos bytes quando comparado a um registro confiável. A autenticação criptográfica dos registros é uma questão distinta.

### Risk Engine · entregas iniciais

**Fase 2.2.** O arquivo `phase2_2_tail.csv` traz intervalos binomiais exatos de 95% para a frequência de violações e o momento incondicional normalizado de ES. Para PETR4 e GJR-GARCH-t houve 39 violações em 3.185 observações. O intervalo nominal foi de 0,87% a 1,67%, sob a hipótese binomial de independência. A estatística de ES foi −0,275. Calcula-se 1 menos a média de (retorno / ES) × indicador de violação dividida por alfa, no domínio válido. O valor aponta perdas de cauda agregadas maiores do que a referência do modelo nessa amostra. A calibração de uma distribuição nula para inferência, inclusive com dependência temporal, permanece pendente.

**Fase 2.3.** O arquivo `phase2_3_stress.csv` contém o pior pregão comum observado e choques hipotéticos isolados. Na carteira de pesos iguais, a perda diária simples máxima observada foi 22,45% em 09/03/2020. Uma queda hipotética de 10% em apenas um dos ativos, com o outro estável, gera perda de 5%. São cálculos de um pregão com os pesos da carteira demonstrativa. Permanecem para a consolidação os choques combinados, os cenários macroeconômicos, os níveis adicionais de VaR e a política de variância após uma lacuna.

### Execuções verificadas

| Execução | Identificador em outputs |
|---|---|
| Fase 2.1 com atualização pelo provedor | `phase2_1/runs/run_20261125T172336_750227Z` |
| Fase 2 com extensões e repetição offline | `phase2_1/runs/run_20261125T172441_564902Z` e `phase2_1/runs/run_20261125T172544_507316Z` |
| Fase 1 com os mesmos caches | `phase1/runs/run_20261125T172544_509860Z` |

A Fase 2 registrou 640 de 640 ajustes GJR convergentes. O primeiro teste novo de comparação de bytes falhou porque a referência usava caracteres literais no lugar da quebra de linha. A referência foi corrigida e a comparação passou sem relaxar a igualdade. Permanece um aviso de depreciação da dependência de calendário com pandas.

### Roadmap dos 15 componentes

| Componente | Progresso atual |
|---|---|
| 1. Data Intelligence | Marco 1 aceito para os três instrumentos diários. Quarentena, estados, versão, reexecução e qualidade demonstrados. |
| 2. Quantitative Risk | Fases 1 e 2.1 executadas. Primeiras entregas 2.2 e 2.3 integradas ao ponto de entrada oficial. |
| 3. Market Prediction | Planejado. Depende de alvos cronológicos e calibração. |
| 4. Technical Intelligence | Planejado. Há retornos diários utilizáveis. |
| 5. Fundamental Analysis | Planejado. Primeira fonte prevista é a CVM. |
| 6. Macro Intelligence | Planejado. Requer calendário de divulgação e versões das séries. |
| 7. News & Sentiment | Planejado. Requer fontes e horários de publicação verificáveis. |
| 8. Portfolio Intelligence | Parcial. Carteira 50/50 com alinhamento e cenários de estresse. |
| 9. Strategy Research | Planejado. Faltam regras de execução, custos e benchmarks. |
| 10. Market Regime | Planejado. O projeto dispõe de comparações por períodos fixos. |
| 11. Opportunity Intelligence | Planejado. Depende de motores validados e cobertura explícita. |
| 12. Explainable AI | Parcial nos diagnósticos quantitativos. As explicações por previsão ainda estão no roadmap. |
| 13. Generative AI Copilot | Planejado. Consumirá ferramentas com resultados e fontes auditáveis. |
| 14. Model Validation & MLOps | Parcial. Há 61 testes, rastreabilidade de entradas e código e diagnósticos adicionais. Faltam registro de modelos e monitoramento prospectivo. |
| 15. Dashboard & Application | Planejado. Relatórios locais de qualidade, risco e cenários já podem alimentar o futuro Risk Center. |

**Próxima decisão de engenharia:** concentrar o próximo incremento na validade estatística da Fase 2.2 e nos cenários da Fase 2.3. Reabrir a base diária para um defeito reproduzível ou para uma necessidade concreta de um novo motor.
