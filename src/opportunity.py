"""Triagem descritiva de ações. Regras explícitas; nenhum peso ajustado no histórico."""
import math

import pandas as pd

from .b3_sessions import completed_sessions


def finite(value):
    return isinstance(value, (float, int)) and math.isfinite(value)


def scan(data, quality, risk_rows, cutoff):
    now = pd.Timestamp(cutoff)
    sessions = completed_sessions(str((now-pd.Timedelta(days=30)).date()), now)
    expected = str(sessions[-1].date())
    history = data["history"]
    day = history[-1]["date"] if history else None
    window = history[-21:]
    cards = []
    for asset in ("PETR4", "VALE3"):
        missing, conflicts = [], []
        asset_quality = quality.get(asset, {})
        if (expected != day or asset_quality.get("stale_sessions") != 0
                or asset_quality.get("freshness") != "atualizado"
                or quality.get("IBOV", {}).get("freshness") != "atualizado"):
            missing.append("O fechamento do ativo e do índice precisa estar atualizado.")
        momentum = relative = None
        if len(window)==21 and all(finite(r.get(k)) and r[k]>0 for r in window for k in (asset,"IBOV")):
            momentum = 100*(window[-1][asset]/window[0][asset]-1)
            relative = momentum - 100*(window[-1]["IBOV"]/window[0]["IBOV"]-1)
            if momentum*relative<0:
                conflicts.append("A direção do preço e o desempenho relativo ao índice apontam em sentidos diferentes.")
        else:
            missing.append("Faltam fechamentos em 21 pregões consecutivos.")
        risk = risk_rows.get(asset, {})
        var, realized = risk.get("var_pct"), risk.get("return_pct")
        if not (risk.get("date")==day and finite(var) and var<0 and finite(realized)):
            var = realized = None
            missing.append("Falta a comparação diária de risco do GJR-GARCH.")
        elif realized<var:
            conflicts.append("A perda realizada ultrapassou o VaR de 99% desse pregão.")
        forecast = None
        sealed = data.get("prospective") or {}
        if (asset=="PETR4" and sealed.get("origin")==day and sealed.get("run")==data["run"]
                and pd.notna(pd.to_datetime(sealed.get("issued"),utc=True,errors="coerce"))
                and pd.to_datetime(sealed.get("issued"),utc=True,errors="coerce")<=now):
            forecast = next((f for f in sealed["forecasts"] if f["horizon"]==1), None)
        if forecast and (not finite(forecast.get("model")) or not 0<=forecast["model"]<=1):
            forecast = None
        if forecast and momentum is not None and (forecast["model"]-.5)*momentum<0:
            conflicts.append("A previsão experimental de um pregão diverge da direção histórica de 20 pregões.")
        label = ("Dados insuficientes" if missing else "Sinais conflitantes" if conflicts
                 else "Para pesquisa" if momentum>0 and relative>0 else "Sem destaque")
        cards.append(dict(asset=asset,status=label,missing=missing,conflicts=conflicts,
                          momentum=momentum, relative=relative,var=var,realized=realized,
                          history_quality=asset_quality.get("completeness","desconhecida"),
                          forecast=forecast))
    return dict(as_of=now.isoformat(),expected=expected,date=day,run=data["run"],cards=cards,
                candidates=[c["asset"] for c in cards if c["status"]=="Para pesquisa"])


def latest_risks(run, day):
    source = run / "phase2_forecasts.csv"
    if not source.exists() or not day:
        return {}
    df = pd.read_csv(source,usecols=["date","asset","model","var_pct","return_pct"])
    batch = df.loc[(df.date==day) & (df.model=="GJR-GARCH t")]
    return batch.set_index("asset").to_dict("index")