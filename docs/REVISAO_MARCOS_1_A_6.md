# Revisão integrada dos Marcos 1 a 6

27 de novembro de 2026. Universo demonstrativo de PETR4 e VALE3, com o Ibovespa como referência. A página arquivada é `entregas/outputs/Painel-Marco-6.html`. O painel informa o fechamento usado e o último pregão que deveria estar disponível quando foi gerado.

## Aceite do scanner

Na execução `run_20261127T190904_280437Z`, os preços terminam em 26/11. PETR4 caiu 18,19% em 20 pregões e ficou 18,81 pontos percentuais abaixo do índice. A previsão experimental de um pregão indicava 57,45% de chance de alta. O scanner expôs essa divergência de horizontes. VALE3 caiu 6,78% e ficou 7,40 pontos percentuais abaixo do índice. Nenhum papel entrou na lista de pesquisa.

A decisão usa regras explícitas sem pesos estatísticos. Para destacar um ativo, exige alta em 20 pregões, desempenho acima do índice, janela completa, fechamento atual segundo o calendário e risco válido no mesmo dia. Um conflito bloqueia o destaque. Incompletude em períodos antigos continua visível e a janela recente é verificada separadamente. Fundamentos e notícias são contexto. A falta de previsão ou balanço específico de VALE3 é indicada. As métricas de retorno simples em 20 pregões e risco logarítmico diário têm rótulos separados. A triagem é descritiva. A rentabilidade futura da regra ainda não foi avaliada.

## O que foi revisto

| Marco | Evidência e achados |
|---|---|
| 1 · Dados | Reabertas 39 entradas arquivadas com snapshot e manifesto versão 2 nas duas fases. O leitor verificou hash e contagem de preços. A rotina diária agora regenera a página ao processar preços, inclusive após falha da etapa de risco, para que o scanner possa mostrar atraso. A publicação do HTML usa substituição atômica. |
| 2 · Risco | Os nove CSVs comuns das duas execuções de referência tiveram bytes iguais. Na execução integrada mais recente foram lidas 36 combinações de cobertura e 640 ajustes GJR convergentes. O EWMA continua experimental para cauda; convergência não garante calibração. |
| 3 · Motores de mercado | Revistos preços e retornos, calendário intradiário, snapshots de CVM, BCB e IBGE e suas datas de conhecimento. A suíte inclui versões posteriores, falha do provedor e lacunas. A cotação por minuto depende do serviço local em execução. |
| 4 · Previsão | No navegador, troca entre 1, 5, 20 e 60 pregões conferida contra as amostras da execução. Quatro previsões reais estavam registradas e zero apuradas no corte. O scanner verifica origem, execução e hora de emissão antes de usar a previsão. O modelo não está promovido. |
| 5 · Carteiras | Reexecutados os exemplos controlados de custo, pesos e retorno. As três regras funcionaram no navegador. O laboratório considera posições fracionárias, sem impostos, corretagem fixa nem impacto de mercado. |
| 6 · Oportunidades | Testes cobrem candidato elegível, divergência com o índice, violação de risco, ausência de dados, fechamento vencido e previsão emitida depois do corte ou pertencente a outra execução. O navegador exibiu as duas fichas e a lista vazia no caso real. |

Validação local: 85 testes Python e duas suítes JavaScript passaram. A verificação das dependências e da integridade interna do Git passou. Há avisos de depreciação do pandas. As verificações usaram os dados arquivados e não reconsultaram cada provedor nem repetiram o treinamento integral do GJR. O teste prospectivo e a validação financeira de uma estratégia de seleção seguem em aberto.

## Estado dos 15 componentes após a primeira integração

| Componente | Estado confirmado |
|---|---|
| 1 · Dados | Em uso para os ativos cobertos, com qualidade e versões. |
| 2 · Risco | Integrado para o universo demonstrativo. |
| 3 · Previsão | Experimental; registro prospectivo iniciado. |
| 4 · Técnica | Integrada em PETR4; tendência e comparação relativas também para VALE3. |
| 5 · Fundamentos | Parcial; ITR consolidado da Petrobras. |
| 6 · Macro | Parcial; Selic, IPCA e dólar. |
| 7 · Notícias | Parcial; notícias econômicas do IBGE. Sentimento e eventos por empresa pendentes. |
| 8 · Carteiras | Simulação de duas ações com custos proporcionais. |
| 9 · Estratégias | Três regras de alocação testáveis. |
| 10 · Regime | Descrição histórica do Ibovespa. |
| 11 · Oportunidades | Scanner demonstrativo com dois ativos e critérios visíveis. |
| 12 · Explicabilidade | Motivos da triagem, resultados e limitações; explicação geral por modelo parcial. |
| 13 · Copilot | Perguntas guiadas no protótipo anterior. Integração generativa pendente. |
| 14 · Validação e MLOps | Testes, snapshots e livro de previsões; maturação prospectiva em curso. |
| 15 · Plataforma | Painel local com serviço intradiário. Plataforma hospedada e acesso multiusuário pendentes. |

O Marco 7 trata do Copilot com consultas vinculadas às fontes. A ampliação para outros ativos depende de dados equivalentes por papel.