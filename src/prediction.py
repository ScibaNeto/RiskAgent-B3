"""Experimento retrospectivo. A origem é o fechamento t e o alvo é o próximo pregão BVMF."""
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit

from .b3_sessions import session_prices

FEATURES = ["acao_1", "mercado_1", "acao_5", "vol_20"]
FIRST_TEST_YEAR = 2021
CALIBRATION_SIZE = 252


def examples(history):
    prices = pd.DataFrame(history).set_index("date")[["PETR4", "IBOV"]]
    prices.index = pd.to_datetime(prices.index)
    prices = session_prices(prices).where(lambda x: x > 0)
    daily = np.log(prices).diff()
    stock = daily.PETR4
    frame = pd.DataFrame(dict(acao_1=stock, mercado_1=daily.IBOV,
                              acao_5=stock.rolling(5).sum(), vol_20=stock.rolling(20).std()))
    future = stock.shift(-1)
    frame["up"] = (future > 0).where(future.notna())
    frame["target"] = frame.index.to_series().shift(-1)
    return frame.replace([np.inf, -np.inf], np.nan).dropna().astype({"up":float})


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


def evaluate(history, *, predictions_csv=None):
    if not history:
        return None
    data = examples(history)
    predictions, folds = [], []
    for year in sorted(set(data.index.year[data.index.year >= FIRST_TEST_YEAR])):
        test = data.loc[data.index.year == year]
        previous = data.loc[data.target < test.index[0]]
        calibration = previous.tail(CALIBRATION_SIZE)
        if len(calibration) < CALIBRATION_SIZE:
            continue
        train = previous.loc[previous.target < calibration.index[0]]
        if len(train) < 504 or min(train.up.nunique(), calibration.up.nunique()) < 2:
            continue
        mean, std = train[FEATURES].mean(), train[FEATURES].std().replace(0, 1)

        def scaled(part):
            return ((part[FEATURES]-mean)/std).to_numpy()

        beta = logistic(scaled(train), train.up.to_numpy())
        cal_scores = beta[0] + scaled(calibration) @ beta[1:]
        calibration_beta = logistic(cal_scores[:, None], calibration.up.to_numpy())
        test_scores = beta[0] + scaled(test) @ beta[1:]
        forecast = expit(calibration_beta[0] + calibration_beta[1] * test_scores)
        baseline = float(previous.up.mean())
        result = test[["target", "up"]].assign(model=forecast, baseline=baseline)
        predictions.append(result)
        folds.append(dict(train_from=str(train.index[0].date()), train_to=str(train.target.iloc[-1].date()),
                          cal_from=str(calibration.index[0].date()), cal_to=str(calibration.target.iloc[-1].date()),
                          test_from=str(test.index[0].date()), test_to=str(test.target.iloc[-1].date()),
                          n=len(test), model=scores(result.up,result.model),
                          baseline=scores(result.up,result.baseline)))
    if not predictions:
        return None
    joined = pd.concat(predictions)
    if predictions_csv is not None:
        joined.to_csv(predictions_csv, index_label="origin")
    groups = {}
    for name in ["model", "baseline"]:
        buckets = pd.cut(joined[name], np.linspace(0,1,11), include_lowest=True)
        groups[name] = [dict(n=len(g),mean=float(g[name].mean()),observed=float(g.up.mean()))
                        for _,g in joined.groupby(buckets,observed=True)]
    return dict(n=len(joined), folds=folds, calibration=groups,
                model=scores(joined.up,joined.model), baseline=scores(joined.up,joined.baseline))