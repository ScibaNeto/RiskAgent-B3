# Marco 4 · Motor preditivo experimental de PETR4

Entrega de engenharia em 27/11/2026, com o histórico ajustado até 26/11 da execução `run_20261127T190904_280437Z`. Os quatro horizontes são contados no calendário BVMF. O alvo de retorno é simples, em pontos percentuais, e exige todos os retornos diários intermediários. Cada horizonte tem uma regressão logística calibrada, uma regressão ridge para a média e quantis de 10% e 90% construídos com resíduos da janela de calibração. As referências usam frequência de altas, retorno médio e quantis empíricos do passado.

## Teste histórico

Os parâmetros são ajustados antes dos últimos 252 exemplos de calibração. O retorno final de qualquer exemplo de ajuste deve anteceder a primeira origem da calibração. O alvo de cada exemplo de calibração deve anteceder a primeira origem do teste anual. As janelas de teste são posteriores aos ajustes e o painel exibe os cortes de cada ano. Os alvos de origens vizinhas se sobrepõem no mesmo bloco para horizontes maiores que um. Portanto o número de linhas não representa observações independentes.

| Pregões | Previsões testadas | Brier modelo / referência | Log loss modelo / referência | Cobertura da faixa nominal de 80% |
|---|---:|---|---|---:|
| 1 | 1470 | 0,24996 / 0,24983 | 0,69308 / 0,69281 | 79,6% |
| 5 | 1466 | 0,24722 / 0,24773 | 0,68760 / 0,68861 | 79,9% |
| 20 | 1451 | 0,24585 / 0,24464 | 0,68711 / 0,68241 | 76,8% |
| 60 | 1411 | 0,21884 / 0,23938 | 0,65838 / 0,67185 | 70,7% |

O painel inclui a curva de calibração, a contagem por faixa, erro absoluto médio e perdas quantílicas para o modelo e a referência. A comparação é retrospectiva e descritiva. O prazo de 60 pregões teve menor erro direcional e subcobertura do intervalo. Nenhum modelo foi promovido automaticamente. A versão dos preços contém ajustes conhecidos no instante da coleta.

## Teste prospectivo iniciado

O arquivo `outputs/prediction/2026-11-26/forecast.json` registra a primeira emissão em 27/11 às 16h12 de Brasília, depois da abertura e antes do fechamento. O ajuste usa dados diários até 26/11. Para emissão, treino e calibração são atualizados com a história elegível àquela origem; no teste histórico os ajustes são anuais. O procedimento de emissão diária precisará de avaliação prospectiva própria. Os vencimentos são 27/11, 03/12, 28/12 e 26/02/2027.

A rotina `.\.venv\Scripts\python.exe src\daily_update.py` atualiza preços, emite apenas com origem no último pregão encerrado e apura alvos vencidos com histórico completo. A opção `--watch` mantém essa rotina em execução enquanto o processo estiver aberto. Cada emissão é gravada sob bloqueio e preservada nas reexecuções. A primeira apuração de cada horizonte recebe arquivo próprio, hash da previsão original, valores realizados e pontuação direcional. A tela mostra a contagem e compara as previsões aos resultados apurados. Em 27/11 às 16h12 havia quatro previsões emitidas e zero apurações reais. Os testes automatizados exercitam vencimento, recusa de dados desatualizados, repetição e preservação da emissão; maturidade real exige a passagem dos pregões.

## Uso

Abra `entregas/outputs/Painel-Marco-4.html` para consultar a entrega congelada. Para atualizar a apuração, execute a rotina diária com os dados acessíveis e depois `.\.venv\Scripts\python.exe painel.py`. A promoção de qualquer modelo depende de novos dados observados. A etapa seguinte do plano é Carteira e Estratégias.