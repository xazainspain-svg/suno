#!/usr/bin/env python3
"""MARKET SCANNER + REGIME: analiza uno o varios CSV de velas y produce CANDIDATES.

No es una recomendación de compra: cada candidato debe pasar después por
backtest/validación de su estrategia y por risk_check.py.

  scanner.py --tf 4h data/BTCUSDT_4h.csv data/ETHUSDT_4h.csv data/SOLUSDT_4h.csv
  scanner.py --tf 1h --corr data/*.csv          # + matriz de correlación de retornos
"""
import argparse
import math
import os
import sys

import quantlib as q

STRAT_FIT = {
    "TREND_UP": "ema_trend_v001 (long), donchian_breakout_v001",
    "TREND_DOWN": "ema_trend_v001 (short, futuros), donchian_breakout_v001",
    "BREAKOUT": "donchian_breakout_v001",
    "EXPANSION": "donchian_breakout_v001, ema_trend_v001",
    "RANGE": "zscore_meanrev_v001",
    "LOW_VOLATILITY": "zscore_meanrev_v001 / esperar expansión",
    "HIGH_VOLATILITY": "reducir tamaño o no operar",
    "CAPITULATION": "no operar hasta estabilización",
    "UNKNOWN": "NO TRADE",
}


def corr(a, b):
    n = min(len(a), len(b))
    a, b = a[-n:], b[-n:]
    ma, mb = sum(a) / n, sum(b) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va = math.sqrt(sum((x - ma) ** 2 for x in a))
    vb = math.sqrt(sum((y - mb) ** 2 for y in b))
    return cov / (va * vb) if va and vb else 0.0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--tf", required=True, choices=list(q.INTERVAL_MS))
    ap.add_argument("--corr", action="store_true")
    ap.add_argument("--corr-window", type=int, default=200)
    ap.add_argument("--min-quote-vol", type=float, default=0, help="Volumen en USDT mínimo (media 20 velas)")
    a = ap.parse_args()

    rows, rets = [], {}
    for path in a.files:
        c = q.load_candles(path)
        name = c[0].get("symbol") if c and c[0].get("symbol") else os.path.basename(path).split("_")[0]
        if len(c) < 250:
            rows.append({"sym": name, "regime": "UNKNOWN", "why": f"solo {len(c)} velas (<250)", "score": -1})
            continue
        issues = q.quality_report(c[-300:], a.tf)
        dq = {k: len(v) for k, v in issues.items() if v}
        f = q.features(c, a.tf)
        i = len(c) - 1
        reg, why = q.regime_at(c, f, i)
        qv = [x.get("quote_volume", x["volume"] * x["close"]) for x in c[-20:]]
        avg_qv = sum(qv) / len(qv)
        trend = (f["close"][i] / f["ema200"][i] - 1) if f["ema200"][i] else 0
        r = {
            "sym": name, "close": f["close"][i], "regime": reg, "why": why,
            "adx": f["adx"][i], "rsi": f["rsi"][i], "atr_pct": f["atr_pct"][i] * 100,
            "rv": f["rv"][i] * 100, "roc20": f["roc20"][i] * 100, "vs_ema200": trend * 100,
            "vol_z": f["vol_z"][i], "qvol": avg_qv, "dq": dq,
        }
        # Puntuación de "interés para investigar" (no de compra): liquidez + claridad de régimen + momento
        liq = math.log10(max(avg_qv, 1))
        clarity = {"TREND_UP": 1, "TREND_DOWN": 1, "BREAKOUT": 0.8, "RANGE": 0.6, "EXPANSION": 0.6,
                   "LOW_VOLATILITY": 0.3, "HIGH_VOLATILITY": 0.1, "CAPITULATION": 0, "UNKNOWN": 0}[reg]
        r["score"] = liq * clarity + min(abs(r["roc20"]), 30) / 30
        if dq or avg_qv < a.min_quote_vol:
            r["score"] = -1
            r["why"] += " | EXCLUIDO: " + ("DATA PROBLEM " + str(dq) if dq else "LOW LIQUIDITY")
        rows.append(r)
        rets[name] = [math.log(c[k]["close"] / c[k - 1]["close"]) for k in range(len(c) - a.corr_window, len(c))]

    rows.sort(key=lambda r: r["score"], reverse=True)
    print(f"=== SCANNER {a.tf} · {len(rows)} activos · CANDIDATES (no son señales) ===")
    print(f"{'símbolo':<10} {'régimen':<16} {'ADX':>5} {'RSI':>5} {'ATR%':>6} {'RV%':>6} {'ROC20%':>7} {'vsEMA200%':>9} {'QVol(avg)':>12}  estrategias compatibles")
    for r in rows:
        if "adx" not in r:
            print(f"{r['sym']:<10} {r['regime']:<16} {r['why']}")
            continue
        flag = "" if r["score"] >= 0 else "  ✗"
        print(f"{r['sym']:<10} {r['regime']:<16} {r['adx']:5.1f} {r['rsi']:5.1f} {r['atr_pct']:6.2f} {r['rv']:6.1f} "
              f"{r['roc20']:7.2f} {r['vs_ema200']:9.2f} {r['qvol']:12.0f}  {STRAT_FIT[r['regime']]}{flag}")
        print(f"{'':<10} └ {r['why']}")
    if a.corr and len(rets) > 1:
        names = list(rets)
        print(f"\nCorrelación de retornos (últimas {a.corr_window} velas):")
        print(" " * 10 + "".join(f"{n[:8]:>9}" for n in names))
        high = []
        for x in names:
            line = f"{x[:9]:<10}"
            for y in names:
                cv = corr(rets[x], rets[y])
                line += f"{cv:9.2f}"
                if x < y and cv > 0.7:
                    high.append((x, y, cv))
            print(line)
        for x, y, cv in high:
            print(f"⚠️  {x}/{y} corr {cv:.2f}: posiciones en ambos = misma apuesta → REDUCE EXPOSURE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
