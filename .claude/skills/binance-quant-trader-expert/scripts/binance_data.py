#!/usr/bin/env python3
"""DATA ENGINE: descarga datos PÚBLICOS de Binance (sin API key) y valida su calidad.

  binance_data.py klines --symbol BTCUSDT --tf 1h --days 365 [--futures] [--out BTCUSDT_1h.csv]
  binance_data.py check  --file BTCUSDT_1h.csv --tf 1h
  binance_data.py exchange-info [--futures] [--symbol ETHUSDT] --out exinfo.json
  binance_data.py book   --symbol BTCUSDT [--futures]          # bid/ask/spread
  binance_data.py depth  --symbol BTCUSDT [--futures] [--band 0.5]
  binance_data.py ticker --symbol BTCUSDT [--futures]          # 24h
  binance_data.py funding --symbol BTCUSDT [--limit 100]       # histórico funding (futuros)
  binance_data.py premium --symbol BTCUSDT                     # mark/index/funding actual
  binance_data.py oi --symbol BTCUSDT [--period 1h --limit 200]

Endpoints usados (verificar en la documentación oficial si algo falla):
  Spot:    https://api.binance.com  (alternativa solo-mercado: https://data-api.binance.vision)
           /api/v3/klines, /api/v3/exchangeInfo, /api/v3/ticker/bookTicker, /api/v3/depth, /api/v3/ticker/24hr
  Futuros USDⓈ-M: https://fapi.binance.com
           /fapi/v1/klines, /fapi/v1/exchangeInfo, /fapi/v1/ticker/bookTicker, /fapi/v1/depth,
           /fapi/v1/ticker/24hr, /fapi/v1/fundingRate, /fapi/v1/premiumIndex,
           /fapi/v1/openInterest, /futures/data/openInterestHist
Solo se guardan velas CERRADAS. Cada fila conserva timestamp, source, symbol y timeframe.
"""
import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import quantlib as q

SPOT = os.environ.get("BINANCE_SPOT_BASE", "https://api.binance.com")
FUT = os.environ.get("BINANCE_FUTURES_BASE", "https://fapi.binance.com")


def get(base, path, params=None, retries=4):
    url = base + path + ("?" + urllib.parse.urlencode(params) if params else "")
    delay = 1
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "quant-research/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                w = r.headers.get("X-MBX-USED-WEIGHT-1M") or r.headers.get("X-MBX-USED-WEIGHT-1m")
                if w and int(w) > 1000:
                    time.sleep(5)  # cerca del límite de peso: frenar
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:300]
            if e.code == 418:
                raise SystemExit(f"IP baneada temporalmente por rate limit (418). Parar. {body}")
            if e.code == 429 or e.code >= 500:
                retry_after = int(e.headers.get("Retry-After") or delay)
                if attempt < retries:
                    time.sleep(retry_after)
                    delay *= 2
                    continue
            raise SystemExit(f"HTTP {e.code} en {path}: {body}")
        except urllib.error.URLError as e:
            if attempt < retries:
                time.sleep(delay)
                delay *= 2
                continue
            raise SystemExit(f"API failure / red: {e}. No se usan datos parciales.")


def cmd_klines(a):
    base, path, lim = (FUT, "/fapi/v1/klines", 1500) if a.futures else (SPOT, "/api/v3/klines", 1000)
    step = q.INTERVAL_MS[a.tf]
    now = int(time.time() * 1000)
    start = now - a.days * 86_400_000
    rows = []
    while start < now:
        data = get(base, path, {"symbol": a.symbol, "interval": a.tf, "startTime": start, "limit": lim})
        if not data:
            break
        rows.extend(data)
        start = data[-1][0] + step
        if len(data) < lim:
            break
        time.sleep(0.15)
    source = ("binance_usdm" if a.futures else "binance_spot") + path
    out = a.out or f"{a.symbol}_{a.tf}{'_perp' if a.futures else ''}.csv"
    seen, kept = set(), 0
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "datetime_utc", "open", "high", "low", "close", "volume", "quote_volume",
                    "trades", "taker_buy_base", "taker_buy_quote", "source", "symbol", "timeframe"])
        for k in rows:
            if k[0] in seen or k[6] >= now:  # duplicada o vela aún abierta
                continue
            seen.add(k[0])
            w.writerow([k[0], time.strftime("%Y-%m-%d %H:%M", time.gmtime(k[0] / 1000)), k[1], k[2], k[3], k[4],
                        k[5], k[7], k[8], k[9], k[10], source, a.symbol, a.tf])
            kept += 1
    print(f"{kept} velas cerradas guardadas en {out}")
    a.file = out
    cmd_check(a)


def cmd_check(a):
    c = q.load_candles(a.file)
    iss = q.quality_report(c, a.tf)
    print(f"Calidad de datos {a.file}: {len(c)} velas")
    ok = True
    for k, v in iss.items():
        if v:
            ok = False
            sample = ", ".join(time.strftime("%Y-%m-%d %H:%M", time.gmtime(t / 1000)) for t in v[:5])
            print(f"  ✗ {k}: {len(v)} (ej.: {sample})")
    if ok:
        print("  ✓ sin velas faltantes, duplicadas, desordenadas, OHLC inválido ni outliers extremos")
    else:
        print("  → Gaps pequeños pueden ser mantenimiento del exchange: documentarlos. Duplicados/OHLC inválido:"
              " NO usar para entrenar hasta corregir.")


def cmd_exinfo(a):
    base, path = (FUT, "/fapi/v1/exchangeInfo") if a.futures else (SPOT, "/api/v3/exchangeInfo")
    params = {"symbol": a.symbol} if a.symbol and not a.futures else None
    data = get(base, path, params)
    if a.symbol and a.futures:
        data["symbols"] = [s for s in data["symbols"] if s["symbol"] == a.symbol]
    out = a.out or "exchange_info.json"
    json.dump(data, open(out, "w"), indent=1)
    for s in data["symbols"][:5]:
        fl = {f["filterType"]: f for f in s["filters"]}
        print(s["symbol"], s.get("status"), "tick", fl.get("PRICE_FILTER", {}).get("tickSize"),
              "step", fl.get("LOT_SIZE", {}).get("stepSize"), "minQty", fl.get("LOT_SIZE", {}).get("minQty"),
              "minNotional", (fl.get("NOTIONAL") or fl.get("MIN_NOTIONAL") or {}).get("minNotional",
                                                                                       (fl.get("MIN_NOTIONAL") or {}).get("notional")))
    print(f"Guardado en {out}")


def cmd_book(a):
    base, path = (FUT, "/fapi/v1/ticker/bookTicker") if a.futures else (SPOT, "/api/v3/ticker/bookTicker")
    d = get(base, path, {"symbol": a.symbol})
    bid, ask = float(d["bidPrice"]), float(d["askPrice"])
    mid = (bid + ask) / 2
    print(json.dumps({"symbol": a.symbol, "bid": bid, "ask": ask, "bid_qty": d["bidQty"], "ask_qty": d["askQty"],
                      "spread_bps": round((ask - bid) / mid * 1e4, 3), "ts_local": int(time.time() * 1000)}, indent=1))


def cmd_depth(a):
    base, path = (FUT, "/fapi/v1/depth") if a.futures else (SPOT, "/api/v3/depth")
    d = get(base, path, {"symbol": a.symbol, "limit": a.limit})
    bids = [(float(p), float(s)) for p, s in d["bids"]]
    asks = [(float(p), float(s)) for p, s in d["asks"]]
    mid = (bids[0][0] + asks[0][0]) / 2
    band = a.band / 100
    bid_usd = sum(p * s for p, s in bids if p >= mid * (1 - band))
    ask_usd = sum(p * s for p, s in asks if p <= mid * (1 + band))
    imb = (bid_usd - ask_usd) / (bid_usd + ask_usd) if bid_usd + ask_usd else 0
    print(json.dumps({"symbol": a.symbol, "mid": mid, "spread_bps": round((asks[0][0] - bids[0][0]) / mid * 1e4, 3),
                      f"bid_depth_quote_{a.band}%": round(bid_usd, 2), f"ask_depth_quote_{a.band}%": round(ask_usd, 2),
                      "imbalance": round(imb, 4), "levels": a.limit}, indent=1))


def cmd_ticker(a):
    base, path = (FUT, "/fapi/v1/ticker/24hr") if a.futures else (SPOT, "/api/v3/ticker/24hr")
    d = get(base, path, {"symbol": a.symbol})
    keys = ["symbol", "lastPrice", "priceChangePercent", "highPrice", "lowPrice", "volume", "quoteVolume", "count"]
    print(json.dumps({k: d.get(k) for k in keys}, indent=1))


def cmd_funding(a):
    d = get(FUT, "/fapi/v1/fundingRate", {"symbol": a.symbol, "limit": a.limit})
    rates = [float(x["fundingRate"]) for x in d]
    for x in d[-10:]:
        print(time.strftime("%Y-%m-%d %H:%M", time.gmtime(x["fundingTime"] / 1000)), f"{float(x['fundingRate']) * 100:+.4f}%")
    if rates:
        print(f"Media {len(rates)} periodos: {sum(rates) / len(rates) * 100:+.4f}% · último {rates[-1] * 100:+.4f}%")
    if a.out:
        json.dump(d, open(a.out, "w"))


def cmd_premium(a):
    d = get(FUT, "/fapi/v1/premiumIndex", {"symbol": a.symbol})
    mark, index = float(d["markPrice"]), float(d["indexPrice"])
    print(json.dumps({"symbol": a.symbol, "mark": mark, "index": index,
                      "basis_bps": round((mark - index) / index * 1e4, 3),
                      "last_funding_rate_pct": float(d["lastFundingRate"]) * 100,
                      "next_funding_utc": time.strftime("%Y-%m-%d %H:%M", time.gmtime(d["nextFundingTime"] / 1000))}, indent=1))


def cmd_oi(a):
    now = get(FUT, "/fapi/v1/openInterest", {"symbol": a.symbol})
    hist = get(FUT, "/futures/data/openInterestHist", {"symbol": a.symbol, "period": a.period, "limit": a.limit})
    print(f"OI actual: {now['openInterest']} {a.symbol}")
    if hist:
        first, last = float(hist[0]["sumOpenInterestValue"]), float(hist[-1]["sumOpenInterestValue"])
        print(f"OI (valor) hace {len(hist)}×{a.period}: {first:,.0f} → ahora {last:,.0f} ({(last / first - 1) * 100:+.2f}%)")
    if a.out:
        json.dump(hist, open(a.out, "w"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["klines", "check", "exchange-info", "book", "depth", "ticker", "funding", "premium", "oi"])
    ap.add_argument("--symbol")
    ap.add_argument("--tf", default="1h", choices=list(q.INTERVAL_MS))
    ap.add_argument("--days", type=int, default=180)
    ap.add_argument("--futures", action="store_true")
    ap.add_argument("--file")
    ap.add_argument("--out")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--band", type=float, default=0.5, help="%% alrededor del mid para medir profundidad")
    ap.add_argument("--period", default="1h")
    a = ap.parse_args()
    if a.cmd != "check" and a.cmd != "exchange-info" and not a.symbol:
        ap.error("--symbol obligatorio")
    if a.cmd == "check" and not a.file:
        ap.error("--file obligatorio")
    {"klines": cmd_klines, "check": cmd_check, "exchange-info": cmd_exinfo, "book": cmd_book, "depth": cmd_depth,
     "ticker": cmd_ticker, "funding": cmd_funding, "premium": cmd_premium, "oi": cmd_oi}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
