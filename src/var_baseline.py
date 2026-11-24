"""
var_baseline.py — Fase 1 do RiskAgent B3

Compara três modelos de VaR 99% (Simulação Histórica, EWMA e GJR-GARCH com
t-Student) em PETR4, VALE3 e Ibovespa, com backtest fora da amostra e teste
de Kupiec.

Uso:   python src/var_baseline.py
Saída: outputs/resultados_var.csv  e  outputs/var_2020_<ativo>.png
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # salva o PNG sem abrir janela
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf
from arch import arch_model
from scipy import stats
from scipy.special import xlogy

# ── Configuração ─────────────────────────────────────────────────────────────
ATIVOS = {"PETR4": "PETR4.SA", "VALE3": "VALE3.SA", "IBOV": "^BVSP"}
INICIO = "2010-01-01"
ALPHA = 0.01           # VaR 99% → olhamos o 1% pior dos retornos
JANELA = 1000          # ≈ 4 anos de pregões usados para estimar cada modelo
REESTIMAR_A_CADA = 20  # reajusta o GARCH a cada ~1 mês (mais rápido)
LAMBDA = 0.94          # decaimento do EWMA (padrão RiskMetrics)
PLOT_DE, PLOT_ATE = "2019-10-01", "2020-12-31"  # zoom na crise da covid

RAIZ = Path(__file__).resolve().parents[1]
DADOS = RAIZ / "data" / "raw"
SAIDA = RAIZ / "outputs"


# ── Dados ────────────────────────────────────────────────────────────────────
def _baixar_yahoo(ticker: str) -> pd.Series:
    """Preço de fechamento ajustado; tenta yf.download e, se falhar, Ticker.history."""
    try:
        px = yf.download(ticker, start=INICIO, auto_adjust=True, progress=False)["Close"]
        if isinstance(px, pd.DataFrame):  # versões novas do yfinance
            px = px.iloc[:, 0]
        if px.dropna().size > 0:
            return px
    except Exception as erro:
        print(f"  yf.download falhou ({erro}); tentando outro método...")
    return yf.Ticker(ticker).history(start=INICIO, auto_adjust=True)["Close"]


def baixar_retornos(nome: str, ticker: str, tentativas: int = 4) -> pd.Series:
    """Retornos logarítmicos diários em % (com cache em data/raw e validação)."""
    import time

    minimo = JANELA + 250  # precisa sobrar ao menos ~1 ano de dados para testar
    DADOS.mkdir(parents=True, exist_ok=True)
    arquivo = DADOS / f"{nome}.csv"

    preco = None
    if arquivo.exists():
        cache = pd.read_csv(arquivo, index_col=0, parse_dates=True)
        if len(cache) >= minimo:
            preco = cache.iloc[:, 0]
        else:
            print(f"  cache de {nome} incompleto ({len(cache)} linhas); baixando de novo...")

    if preco is None:
        for tentativa in range(1, tentativas + 1):
            try:
                px = _baixar_yahoo(ticker).dropna()
            except Exception as erro:
                print(f"  tentativa {tentativa}/{tentativas} falhou: {erro}")
                px = pd.Series(dtype=float)
            if len(px) >= minimo:
                px.index = pd.to_datetime(px.index).tz_localize(None)
                px.to_csv(arquivo)  # só guarda no cache se o download veio completo
                preco = px
                break
            print(f"  {ticker}: vieram {len(px)} pregões (tentativa {tentativa}/{tentativas}); aguardando...")
            time.sleep(5 * tentativa)
        else:
            raise RuntimeError(
                f"Não consegui baixar {ticker} (esperava ao menos {minimo} pregões). "
                "Verifique a internet, tente de novo em alguns minutos ou troque o ticker em ATIVOS."
            )
    return (100 * np.log(preco / preco.shift(1))).dropna().rename(nome)


# ── Modelos: cada um prevê o VaR do dia t usando apenas dados até t-1 ────────
def var_historico(r: pd.Series) -> pd.Series:
    """Simulação histórica: quantil empírico dos últimos JANELA retornos."""
    return r.rolling(JANELA).quantile(ALPHA).shift(1)


def var_ewma(r: pd.Series) -> pd.Series:
    """EWMA (RiskMetrics): volatilidade exponencial × quantil da normal."""
    sigma = np.sqrt(r.pow(2).ewm(alpha=1 - LAMBDA, adjust=False).mean().shift(1))
    return stats.norm.ppf(ALPHA) * sigma


def var_gjr_garch_t(r: pd.Series) -> pd.Series:
    """GJR-GARCH(1,1) com t-Student, reestimado a cada REESTIMAR_A_CADA dias."""
    out = pd.Series(np.nan, index=r.index)
    for i in range(JANELA, len(r), REESTIMAR_A_CADA):
        spec = dict(mean="Zero", vol="GARCH", p=1, o=1, q=1, dist="t")
        ajuste = arch_model(r.iloc[i - JANELA:i], **spec).fit(disp="off")
        nu = ajuste.params["nu"]
        # Reaplica os parâmetros já estimados ao próximo bloco (sem olhar o futuro)
        bloco = r.iloc[i - JANELA:i + REESTIMAR_A_CADA]
        sigma = arch_model(bloco, **spec).fix(ajuste.params).conditional_volatility
        sigma = sigma.iloc[JANELA:]  # volatilidade condicional de cada dia do bloco
        z = stats.t.ppf(ALPHA, nu) * np.sqrt((nu - 2) / nu)  # t padronizada
        out.iloc[i:i + len(sigma)] = z * sigma.to_numpy()
    return out


# ── Backtest ─────────────────────────────────────────────────────────────────
def kupiec(violacoes: pd.Series) -> tuple[float, float]:
    """Teste de Kupiec. H0: a taxa de violações é igual a ALPHA."""
    n, x = len(violacoes), int(violacoes.sum())
    p_obs = x / n
    lr = -2 * (
        (n - x) * np.log(1 - ALPHA) + x * np.log(ALPHA)
        - xlogy(n - x, 1 - p_obs) - xlogy(x, p_obs)
    )
    return lr, float(stats.chi2.sf(lr, df=1))


def avaliar(ativo: str, r: pd.Series, vars_: dict) -> list[dict]:
    linhas = []
    for modelo, v in vars_.items():
        base = pd.concat([r, v], axis=1, keys=["ret", "var"]).dropna()
        viol = base["ret"] < base["var"]  # perda maior que o VaR previsto
        _, p = kupiec(viol)
        linhas.append({
            "ativo": ativo,
            "modelo": modelo,
            "n_obs": len(base),
            "violações": int(viol.sum()),
            "esperadas": round(len(base) * ALPHA, 1),
            "taxa_%": round(100 * viol.mean(), 2),
            "var_médio_%": round(base["var"].mean(), 2),
            "p_valor_kupiec": round(p, 3),
            "veredito": "✅ calibrado" if p >= 0.05 else "❌ rejeitado",
        })
    return linhas


def grafico(ativo: str, r: pd.Series, vars_: dict) -> None:
    """Zoom na crise de 2020: onde cada modelo errou?"""
    zoom = slice(PLOT_DE, PLOT_ATE)
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(r.loc[zoom], color="lightgray", lw=0.8, label="retorno diário (%)")
    for modelo, v in vars_.items():
        (linha,) = ax.plot(v.loc[zoom], lw=1.4, label=f"VaR 99% — {modelo}")
        ret, var = r.loc[zoom], v.loc[zoom]
        violacoes = ret[ret < var]
        ax.scatter(violacoes.index, violacoes, marker="x", s=40,
                   color=linha.get_color(), zorder=3)
    ax.set_title(f"{ativo} — VaR 99% (× = violação)")
    ax.set_ylabel("%")
    ax.legend(loc="lower left", fontsize=8)
    ax.grid(alpha=0.3)
    fig.savefig(SAIDA / f"var_2020_{ativo}.png", dpi=130, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    linhas = []
    for ativo, ticker in ATIVOS.items():
        print(f"▶ {ativo}: baixando dados e ajustando modelos...")
        r = baixar_retornos(ativo, ticker)
        vars_ = {
            "Simulação histórica": var_historico(r),
            "EWMA (normal)": var_ewma(r),
            "GJR-GARCH-t": var_gjr_garch_t(r),
        }
        # amostra comum a todos os modelos: só depois da primeira janela
        vars_ = {m: v.iloc[JANELA:] for m, v in vars_.items()}
        linhas += avaliar(ativo, r, vars_)
        grafico(ativo, r, vars_)

    tabela = pd.DataFrame(linhas)
    tabela.to_csv(SAIDA / "resultados_var.csv", index=False)
    print("\n" + tabela.to_string(index=False))
    print(f"\nArquivos salvos em: {SAIDA}")


if __name__ == "__main__":
    main()