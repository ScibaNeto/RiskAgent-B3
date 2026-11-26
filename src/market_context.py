"""Fontes públicas da página de contexto. A consulta histórica usa o instante de coleta."""
import csv
import hashlib
import io
import json
import math
import os
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

BR = ZoneInfo("America/Sao_Paulo")
STORE = Path(__file__).resolve().parents[1] / "data" / "context"
CNPJ = "33.000.167/0001-01"


def urls(now):
    day = now.astimezone(BR).date()
    # No início do ano, o último ITR disponível ainda pertence ao ano anterior.
    year = day.year if day.month >= 5 else day.year - 1
    return {
        "cvm": f"https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_{year}.zip",
        "bcb": "https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados?" + urlencode(dict(
            formato="json", dataInicial=(day-timedelta(days=40)).strftime("%d/%m/%Y"), dataFinal=day.strftime("%d/%m/%Y"))),
        "ipca": "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?" + urlencode(dict(
            formato="json", dataInicial=(day-timedelta(days=110)).strftime("%d/%m/%Y"), dataFinal=day.strftime("%d/%m/%Y"))),
        "usd": "https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados?" + urlencode(dict(
            formato="json", dataInicial=(day-timedelta(days=20)).strftime("%d/%m/%Y"), dataFinal=day.strftime("%d/%m/%Y"))),
        "ibge": "https://servicodados.ibge.gov.br/api/v3/noticias/?" + urlencode(dict(
            qtd=60, tipo="noticia", ate=day.strftime("%m-%d-%Y"))),
    }


def statements(raw, now):
    day = now.astimezone(BR).date().isoformat()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        dre = next(n for n in archive.namelist() if "_DRE_con_" in n)
        def records(name):
            with archive.open(name) as stream:
                yield from csv.DictReader(io.TextIOWrapper(stream, encoding="latin1"), delimiter=";")
        filings = {(r["DT_REFER"], int(r["VERSAO"])): r for r in records(dre.replace("_DRE_con", ""))
                   if r["CNPJ_CIA"] == CNPJ and r["DT_REFER"] <= r["DT_RECEB"] <= day}
        if not filings:
            raise ValueError("Sem ITR entregue até o corte.")
        key = max(filings)
        accounts = {}
        for r in records(dre):
            if (r["CNPJ_CIA"] == CNPJ and (r["DT_REFER"], int(r["VERSAO"])) == key
                    and r["DT_FIM_EXERC"] == key[0] and r["DT_INI_EXERC"] == key[0][:4] + "-01-01"
                    and r["ORDEM_EXERC"] == "ÚLTIMO" and r["CD_CONTA"] in {"3.01", "3.11"}
                    and r["MOEDA"] == "REAL" and r["ESCALA_MOEDA"] == "MIL"):
                accounts[r["CD_CONTA"]] = float(r["VL_CONTA"]) * 1000
        revenue, profit = accounts["3.01"], accounts["3.11"]
        if revenue <= 0 or not all(map(math.isfinite, (revenue, profit))):
            raise ValueError("Valores contábeis inválidos.")
        return dict(period=key[0], version=key[1], received=filings[key]["DT_RECEB"],
                    revenue=revenue, profit=profit, margin=100*profit/revenue)


def sgs(raw, now, minimum=None):
    day = now.astimezone(BR).date()
    values = {}
    for r in json.loads(raw):
        date = datetime.strptime(r["data"], "%d/%m/%Y").date()
        if date <= day:
            rate = float(r["valor"])
            if not math.isfinite(rate) or (minimum is not None and rate < minimum) or date in values:
                raise ValueError("Observação SGS inválida.")
            values[date] = rate
    date = max(values)
    return dict(date=date.isoformat(), rate=values[date])


def news(raw, now):
    items = {}
    for r in json.loads(raw)["items"]:
        if "economicas" not in r["editorias"].split(","):
            continue
        published = datetime.strptime(r["data_publicacao"], "%d/%m/%Y %H:%M:%S").replace(tzinfo=BR)
        link = urlsplit(r["link"])
        if published <= now and link.hostname == "agenciadenoticias.ibge.gov.br" and link.scheme in {"http","https"} and r["titulo"].strip():
            url = link._replace(scheme="https").geturl()
            items[url] = dict(title=r["titulo"], published=published.isoformat(), url=url)
    result = sorted(items.values(), key=lambda r:r["published"], reverse=True)[:5]
    if not result:
        raise ValueError("Sem notícia econômica válida.")
    return result


PARSERS = {"cvm": statements, "bcb": lambda b,n: sgs(b,n,0), "usd": lambda b,n: sgs(b,n,0), "ipca": sgs, "ibge": news}


def fetch(url):
    with urlopen(Request(url, headers={"User-Agent":"RiskAgent-B3/1.0"}), timeout=30) as result:
        return result.read()


def history(root, source, cutoff):
    latest_error = None
    for path in sorted((root/source).glob("*.json"), reverse=True):
        if path.stem > cutoff.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"):
            continue
        item = json.loads(path.read_text(encoding="utf8"))
        if item.get("error"):
            latest_error = latest_error or item
        else:
            return dict(record=item, failure=latest_error)
    return dict(record=None, failure=latest_error)


def refresh(root=STORE, download=fetch, force=False):
    from filelock import FileLock
    root.mkdir(parents=True, exist_ok=True)
    with FileLock(str(root/".update.lock"), timeout=120):
        for source, url in urls(datetime.now(timezone.utc)).items():
            now = datetime.now(timezone.utc)
            latest = history(root, source, now)
            if not force and latest["record"] and not latest["failure"]:
                known = datetime.fromisoformat(latest["record"]["known"]).astimezone(BR)
                if known.date() == now.astimezone(BR).date():
                    continue
            item = dict(source=source, url=url)
            try:
                raw = download(url)
                item["source_sha256"] = hashlib.sha256(raw).hexdigest()
                archive = root / "raw" / source
                archive.mkdir(parents=True, exist_ok=True)
                target = archive / item["source_sha256"]
                if not target.exists():
                    with tempfile.NamedTemporaryFile(dir=archive, delete=False) as tmp:
                        tmp.write(raw)
                    os.replace(tmp.name, target)
                item["data"] = PARSERS[source](raw, datetime.now(timezone.utc))
            except (OSError, ValueError, LookupError, TypeError, zipfile.BadZipFile, StopIteration) as exc:
                item["error"] = str(exc) or type(exc).__name__
            now = datetime.now(timezone.utc)
            item["known"] = now.isoformat()
            folder = root/source
            folder.mkdir(exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf8", dir=folder, delete=False) as tmp:
                json.dump(item,tmp,ensure_ascii=False,allow_nan=False)
            os.replace(tmp.name,folder/(now.strftime("%Y%m%dT%H%M%S%fZ")+".json"))


def technical(rows):
    """Wilder 14, MACD 12/26 e sinal 9. Cada lacuna reinicia o aquecimento."""
    prices = pd.Series([r["PETR4"] for r in rows], dtype=float)
    valid = prices.gt(0) & np.isfinite(prices)
    prices = prices.loc[valid & ((~valid).cumsum() == (~valid).sum())]
    if len(prices) < 34:
        return None
    delta = prices.diff().dropna()
    gains, losses = delta.clip(lower=0), (-delta).clip(lower=0)
    gain, loss = gains.iloc[:14].mean(), losses.iloc[:14].mean()
    for up, down in zip(gains.iloc[14:], losses.iloc[14:]):
        gain, loss = (13*gain+up)/14, (13*loss+down)/14
    rsi = 100*gain/(gain+loss) if gain+loss else 50.
    macd = prices.ewm(span=12, adjust=False).mean() - prices.ewm(span=26, adjust=False).mean()
    signal = macd.iloc[25:].ewm(span=9, adjust=False).mean()
    return dict(date=rows[-1]["date"], rsi=float(rsi), macd=float(macd.iloc[-1]), signal=float(signal.iloc[-1]))


def market_regime(rows):
    frame = pd.DataFrame(rows)
    if frame.empty:
        return None
    prices = frame.IBOV.tail(81).to_numpy(dtype=float)
    if len(prices)<81 or not np.isfinite(prices).all() or (prices<=0).any():
        return None
    ret = np.diff(np.log(prices))
    vol = float(np.std(ret[-20:],ddof=1)*np.sqrt(252)*100)
    reference = float(np.std(ret[:-20],ddof=1)*np.sqrt(252)*100)
    gain = 100*(prices[-1]/prices[-21]-1)
    return dict(date=frame.date.iloc[-1], change=gain, volatility=vol, reference=reference,
                direction="alta" if gain>0 else "queda" if gain<0 else "estável",
                variability="acima" if vol>reference+1e-10 else "abaixo" if vol<reference-1e-10 else "igual")


if __name__ == "__main__":
    refresh(force=True)
    for source in PARSERS:
        result = history(STORE, source, datetime.now(timezone.utc))
        print(source, result["failure"] or "OK")