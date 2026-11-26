# Marco 3 · Aceite da primeira integração dos motores de mercado

Em 25/11/2026 a página local reuniu as cinco frentes do Marco 3 para PETR4 e seu contexto brasileiro. O aceite cobre as fontes e os indicadores discriminados abaixo.

| Frente | Resultado disponível | Unidade, data e controle |
|---|---|---|
| Técnica | Preço, volume, média de 20 pregões, RSI de Wilder (14), MACD (12/26 e sinal 9) | Fechamentos ajustados nos indicadores; volume em ações. O último trecho de dados consecutivos determina o aquecimento. RSI constante usa 50. As médias exponenciais começam no primeiro fechamento do trecho. |
| Fundamentos | DRE consolidada da Petrobras, receita, lucro líquido consolidado e margem acumulados desde janeiro | Contas CVM 3.01 e 3.11, em milhares de reais convertidos para reais. O ITR informa data de referência, entrega e versão. Em setembro de 2026, R$ 462,569 bilhões de receita e R$ 125,039 bilhões de lucro. |
| Macro | Meta Selic, IPCA mensal e dólar de venda | Séries BCB 432, 433 e 1, respectivamente em % anual, % mensal e R$/US$. Cada série preserva sua própria data de referência e instante de consulta. |
| Notícias | Até cinco manchetes da editoria econômica do IBGE com link e data de publicação | Seleção cronológica dentre os 60 itens consultados; horário interpretado em Brasília. O escopo é notícias econômicas nacionais. |
| Regimes | Direção do Ibovespa em 20 pregões e oscilação recente comparada aos 60 pregões anteriores | Retorno simples acumulado e desvio amostral dos retornos logarítmicos, anualizado por 252. Exige 81 preços consecutivos. É uma descrição histórica; utilidade preditiva ainda não foi avaliada. |

## Rastreabilidade e operação

O coletor registra a URL do provedor, o hash do conteúdo recebido, a versão extraída e o instante em que a gravação se tornou conhecida pelo agente. O arquivo bruto fica localmente em `data/context/raw` identificado por hash. O Git inclui os registros extraídos em `data/context`. A consulta por instante seleciona o último registro válido já conhecido e aponta falhas posteriores. Para demonstrativos, revisões só entram se o arquivo recebido as contiver e a entrega já tiver ocorrido. Para notícias, o horário de publicação precisa anteceder o corte. A recuperação de versões anteriores à instalação depende de arquivos coletados naquela época.

A atualização diária existente também consulta essas fontes. Para atualizar apenas o contexto e gerar a página, na raiz do projeto:

```powershell
.\.venv\Scripts\python.exe -m src.market_context
.\.venv\Scripts\python.exe painel.py --ao-vivo
```

A área intradiária consulta PETR4 enquanto a página está aberta. Os quadros de contexto correspondem ao instante da geração. Uma cópia independente do servidor está em `entregas/outputs/Painel-Etapa-3.html`.

## Verificação de aceite

77 testes Python, teste JavaScript e compilação aprovados. Os casos incluem revisão de ITR após o corte, conversão de unidade, rejeição de observações futuras, notícias futuras ou de domínio externo, falha de provedor com recuperação da última versão e indicadores em séries constantes, com alta e com lacuna. O navegador renderizou os sete quadros com dados reais. Preços e regime tinham corte em 24/11; os três indicadores macro exibiram as datas específicas de cada série.

O roadmap completo ainda prevê mais ativos, indicadores fundamentalistas, notícias corporativas, sentimento e pesquisa de regimes preditivos. Esses itens permanecem identificados como expansões. O Marco 4 inicia a avaliação cronológica do primeiro modelo de previsão.