# RiskAgent B3

Projeto educacional de engenharia de dados e risco de mercado para PETR4, VALE3 e Ibovespa. Os modelos calculam VaR e Expected Shortfall (ES) com dados historicos; os resultados nao sao recomendacao de investimento.

Auditoria inicial do workspace e roteiro priorizado: [docs/INITIAL_AUDIT.md](docs/INITIAL_AUDIT.md).

## Abrir o painel no VS Code

Abra a pasta inteira do projeto. No terminal integrado do PowerShell, execute:

```powershell
.\.venv\Scripts\python.exe painel.py
```

A seção **PETR4 e Ibovespa** permite escolher a data e a janela, comparar o desempenho em base 100, visualizar a queda desde o pico e conferir o retorno realizado contra o VaR do GJR-GARCH-t. Experimente 18/05/2017.

O navegador abre um HTML local com seleção de ativo, comparação dos três modelos e cenários da carteira. O painel lê a execução completa mais recente em `outputs/phase2_1/runs/`. Em um clone novo, instale as dependências conforme a seção abaixo e execute `src/phase2_risk_engine_v2.py` com o Python do ambiente para gerar a primeira análise. Os dados de mercado e os resultados gerados ficam locais.

## Estrutura

```text
src/                         scripts das fases
  var_baseline.py            Fase 1: VaR, backtest e Kupiec
  phase2_risk_engine_v2.py   Fase 2.1 oficial: VaR, ES, testes e carteira
  phase2_risk_engine.py      implementacao anterior da Fase 2 (legada)
data/raw/                    cache local de precos (nao versionado)
outputs/                     resultados historicos e execucoes versionadas
tests/                       testes automatizados (stdlib unittest)
requirements.txt             dependencias Python
```

## Fases

- **Fase 1** (`src/var_baseline.py`): simulacao historica, EWMA normal e GJR-GARCH-t; backtest fora da amostra e teste de Kupiec em cada ativo.
- **Fase 2.1** (`src/phase2_risk_engine_v2.py`, versao oficial): VaR e ES por ativo e para carteira demonstrativa 50/50 de PETR4/VALE3; testes de Kupiec, Christoffersen e cobertura condicional; score conjunto FZ0; metricas por periodo; ajustes de p-valores.
- `src/phase2_risk_engine.py` e a implementacao anterior da Fase 2, mantida para referencia. Use a v2 para novas execucoes da Fase 2.1.
- Fases posteriores ainda nao estao implementadas.

## Dependencias e instalacao

Requer Python 3.11 ou superior. As dependencias estao em `requirements.txt`: pandas, numpy, scipy, matplotlib, arch, yfinance, exchange-calendars e filelock. Os testes usam `unittest`, incluido no Python.

No PowerShell, a partir da raiz do repositorio:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Execucao

```powershell
.\.venv\Scripts\python.exe src\var_baseline.py
.\.venv\Scripts\python.exe src\phase2_risk_engine_v2.py
```

As duas fases compartilham a coleta incremental do fechamento ajustado, com cinco dias corridos de sobreposição. Uma revisão no primeiro pregão coincidente exige nova coleta de todo o histórico para evitar combinar bases de ajuste diferentes. A gravação do CSV usa substituição atômica após a validação da amostra. Em caso de falha, a execução registra o motivo e tenta usar o último cache válido.

O calendário BVMF define quais pregões já encerraram no instante de corte. O limite padrão é um pregão em atraso. Em modo normal, ultrapassar esse limite gera aviso. Com `--strict-cache`, a execução é interrompida. Use `--max-stale-sessions 0` para exigir a última sessão encerrada e `--offline` para trabalhar apenas com os arquivos locais.

```powershell
.\.venv\Scripts\python.exe src\var_baseline.py --offline --strict-cache
.\.venv\Scripts\python.exe src\phase2_risk_engine_v2.py --offline --strict-cache
```

Uma lacuna interna elimina os retornos que precisam daquele fechamento. Os preços extremos continuam na amostra e aparecem na auditoria. A carteira usa apenas datas com retorno diário válido para todos os ativos incluídos na carteira.

## Resultados

Cada execucao cria uma pasta nova, sem substituir execucoes anteriores:

- Fase 1: `outputs/phase1/runs/<identificador>/`
- Fase 2.1: `outputs/phase2_1/runs/<identificador>/`

Os arquivos historicos que ja existem diretamente em `outputs/` e `outputs/phase2_1/` sao preservados. Cada execução com entradas aceitas salva em `inputs/` uma cópia local dos bytes usados. O arquivo `manifest.json` registra o SHA-256 da cópia, as versões das bibliotecas, a origem de cada série, o corte temporal e as ocorrências de qualidade. A cobertura parcial identifica pregões faltantes ou atraso. A data de coleta fica nula quando só o cache foi usado. Se a entrada for recusada, o motivo aparece em `data_failure.json`. A Fase 1 salva metricas, `garch_diagnostics.csv` e graficos; a Fase 2.1 salva previsoes, metricas, diagnosticos, relatorio e graficos.

## Amostra e comparacoes estatisticas

A janela de estimacao e de 1.000 retornos e o minimo de teste e de 250 observacoes. Sao exigidos 1.250 retornos validos depois da limpeza; sem valores ausentes, isso corresponde a pelo menos 1.251 precos.

Na Fase 2.1, p-valores fora da amostra completos sao a familia confirmatoria: cada tipo de teste (Kupiec, independencia de Christoffersen e cobertura condicional) e ajustado por Holm em conjunto sobre todos os ativos e modelos. As analises por periodo sao exploratorias: para cada tipo de teste, Benjamini-Hochberg e aplicado em conjunto sobre periodos, ativos e modelos. A interpretacao do controle FDR do BH assume independencia ou dependencia positiva apropriada entre testes; sob dependencias arbitrarias, nao ha essa garantia. Colunas originais permanecem; novas colunas terminam em `_holm` ou `_bh`. Scores FZ0 nao sao p-valores e nao sao ajustados.

## Testes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
