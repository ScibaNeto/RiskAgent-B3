"""Experimento retrospectivo. A origem é o fechamento t e o alvo é o próximo pregão BVMF."""
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit

from .b3_sessions import session_prices

FEATURES = ["acao_1", "mercado_1", "acao_5", "vol_20"]
FIRST_TEST_YEAR = 2021
CALIBRATION_SIZE = 252


def design(history):
    prices = pd.DataFrame(history).set_index("date")[["PETR4", "IBOV"]]
    prices.index = pd.to_datetime(prices.index)
    prices = session_prices(prices).where(lambda x: x > 0)
    daily = np.log(prices).diff()
    stock = daily.PETR4
    frame = pd.DataFrame(dict(acao_1=stock, mercado_1=daily.IBOV,
                              acao_5=stock.rolling(5).sum(), vol_20=stock.rolling(20).std()))
    return stock, frame.replace([np.inf, -np.inf], np.nan)


def examples(history, horizon=1):
    stock, frame = design(history)
    future = stock.rolling(horizon).sum().shift(-horizon)
    frame["return_pct"] = 100*np.expm1(future.dropna())
    frame["up"] = (future > 0).where(future.notna())
    frame["target"] = frame.index.to_series().shift(-horizon)
    return frame.dropna().astype({"up":float})

def logistic(x, y):
    """Perda logística com penalidade L2 unitária, intercepto livre."""
    if len(np.unique(y)) < 2:
        raise ValueError("Sem duas classes no ajuste.")
    x = np.column_stack([np.ones(len(x)), x])

    def objective(beta):
        score = x @ beta
        loss = np.sum(np.logaddexp(0, score) - y * score) + .5 * np.sum(beta[1:]**2)
        grad = x.T @ (expit(score) - y) + np.r_[0, beta[1:]]
        return loss, grad

    fit = minimize(objective, np.zeros(x.shape[1]), jac=True, method="L-BFGS-B")
    if not fit.success:
        raise ValueError("Ajuste logístico sem convergência.")
    return fit.x


def scores(y, p):
    p = np.clip(p, 1e-12, 1-1e-12)
    return dict(brier=float(np.mean((p-y)**2)),
                log_loss=float(-np.mean(y*np.log(p)+(1-y)*np.log1p(-p))))


HORIZONS = (1, 5, 20, 60)


def fit_fold(previous, test):
    calibration = previous.tail(CALIBRATION_SIZE)
    if len(calibration) < CALIBRATION_SIZE:
        return None
    train = previous.loc[previous.target < calibration.index[0]]
    if len(train) < 504 or min(train.up.nunique(), calibration.up.nunique()) < 2:
        return None
    mean, std = train[FEATURES].mean(), train[FEATURES].std().replace(0, 1)
    x, c, t = [((part[FEATURES]-mean)/std).to_numpy() for part in (train, calibration, test)]
    beta = logistic(x, train.up.to_numpy())
    cal = logistic((beta[0] + c @ beta[1:])[:, None], calibration.up.to_numpy())
    prob = expit(cal[0] + cal[1] * (beta[0] + t @ beta[1:]))
    # Estimativa condicional da média com ridge e quantis dos resíduos na calibração.
    design_matrix = np.column_stack([np.ones(len(x)), x])
    coef = np.linalg.solve(design_matrix.T @ design_matrix + np.diag([0]+[1]*x.shape[1]),
                           design_matrix.T @ train.return_pct)
    point = coef[0] + t @ coef[1:]
    residual = calibration.return_pct - (coef[0] + c @ coef[1:])
    low, high = residual.quantile([.1, .9])
    base_low, base_high = previous.return_pct.quantile([.1, .9])
    result = test.copy()
    result = result.assign(model=prob, baseline=previous.up.mean(), point=point,
                           q10=point+low, q90=point+high, base_point=previous.return_pct.mean(),
                           base_q10=base_low, base_q90=base_high)
    dates = dict(train_from=str(train.index[0].date()), train_to=str(train.target.iloc[-1].date()),
                 cal_from=str(calibration.index[0].date()), cal_to=str(calibration.target.iloc[-1].date()))
    return result, dates


def return_scores(data, prefix):
    err = data.return_pct-data[prefix+"point"]
    lo, hi = data[prefix+"q10"], data[prefix+"q90"]
    def pinball(q, forecast):
        error = data.return_pct-forecast
        return float(np.maximum(q*error,(q-1)*error).mean())
    return dict(mae=float(err.abs().mean()), coverage=float(data.return_pct.between(lo,hi).mean()),
                q10_loss=pinball(.1,lo), q90_loss=pinball(.9,hi))


def evaluate(history, *, predictions_csv=None, horizon=1):
    if not history:
        return None
    data = examples(history, horizon)
    predictions, folds = [], []
    for year in sorted(set(data.index.year[data.index.year >= FIRST_TEST_YEAR])):
        test = data.loc[data.index.year == year]
        fit = fit_fold(data.loc[data.target < test.index[0]], test)
        if fit is None:
            continue
        result, dates = fit
        predictions.append(result)
        folds.append(dict(**dates,test_from=str(test.index[0].date()),test_to=str(test.target.iloc[-1].date()),
                          n=len(test),model=scores(result.up,result.model),baseline=scores(result.up,result.baseline)))
    if not predictions:
        return None
    joined = pd.concat(predictions)
    if predictions_csv is not None:
        joined.drop(columns=FEATURES).to_csv(predictions_csv,index_label="origin")
    groups = {}
    for name in ["model", "baseline"]:
        buckets = pd.cut(joined[name], np.linspace(0,1,11), include_lowest=True)
        groups[name] = [dict(n=len(g),mean=float(g[name].mean()),observed=float(g.up.mean()))
                        for _,g in joined.groupby(buckets,observed=True)]
    return dict(n=len(joined), folds=folds, calibration=groups,
                model=scores(joined.up,joined.model), baseline=scores(joined.up,joined.baseline),
                returns=return_scores(joined,""), reference_returns=return_scores(joined,"base_"))