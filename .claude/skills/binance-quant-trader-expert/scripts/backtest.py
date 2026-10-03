#!/usr/bin/env python3
"""Backtest con costes realistas + walk-forward + sensibilidad de parámetros.

Modelo de ejecución (sin look-ahead):
  - La señal se calcula con la vela i CERRADA; la entrada se ejecuta en el OPEN de i+1.
  - Entrada a mercado: precio ± (medio spread + slippage), comisión taker.
  - Stop: orden stop a mercado (taker + slippage). Si hay gap a través del stop, sale al open.
  - Target: orden límite (maker, sin slippage). Si stop y target caen en la misma vela -> stop (conservador).
  - Tamaño: riesgo% del equity / (distancia al stop + costes estimados por unidad),
    redondeado hacia abajo al stepSize; se rechaza si no cumple minQty / minNotional.
  - Funding (futuros): --funding-rate por cada 8h de posición abierta (largos pagan si > 0).

Uso:
  backtest.py run  --data BTCUSDT_1h.csv --tf 1h --strategy ema_trend_v001 [--params fast=20,slow=50]
  backtest.py wf   --data ... --tf 1h --strategy donchian_breakout_v001 --folds 5 [--holdout 0.2]
  backtest.py sens --data ... --tf 1h --strategy zscore_meanrev_v001
  backtest.py list
"""
import argparse
import csv
import itertools
import json
import math
import sys

import quantlib as q

# ---------------------------------------------------------------- estrategias
# Cada estrategia declara hipótesis, regímenes esperados, parámetros por defecto y rejilla.
STRATEGIES = {
    "ema_trend_v001": {
        "hypothesis": "Tras un cruce EMA rápida/lenta con ADX alto, el precio continúa en la dirección "
                      "del cruce lo suficiente para que un objetivo de rr·riesgo se alcance más que el stop.",
        "regimes": ["TREND_UP", "TREND_DOWN", "EXPANSION"],
        "defaults": {"fast": 20, "slow": 50, "adx_min": 20, "atr_mult": 2.0, "rr": 2.0, "max_bars": 100},
        "grid": {"fast": [10, 20, 30], "slow": [50, 100], "atr_mult": [1.5, 2.0, 3.0], "rr": [1.5, 2.0, 3.0]},
    },
    "donchian_breakout_v001": {
        "hypothesis": "Un cierre fuera del canal Donchian-n con volumen anómalo inicia una expansión de "
                      "volatilidad con continuación estadísticamente favorable.",
        "regimes": ["BREAKOUT", "EXPANSION", "TREND_UP", "TREND_DOWN"],
        "defaults": {"n": 20, "vol_z": 1.0, "atr_mult": 2.0, "rr": 2.5, "max_bars": 60},
        "grid": {"n": [20, 40, 55], "vol_z": [0.5, 1.0, 1.5], "atr_mult": [1.5, 2.0, 3.0], "rr": [2.0, 3.0]},
    },
    "zscore_meanrev_v001": {
        "hypothesis": "En régimen sin tendencia (ADX bajo), desviaciones extremas del precio respecto a su "
                      "media de n velas revierten parcialmente hacia la media.",
        "regimes": ["RANGE", "LOW_VOLATILITY"],
        "defaults": {"n": 20, "entry_z": 2.0, "adx_max": 20, "atr_mult": 1.5, "rr": 1.5, "max_bars": 30},
        "grid": {"n": [20, 30, 50], "entry_z": [1.5, 2.0, 2.5], "atr_mult": [1.0, 1.5, 2.0], "rr": [1.0, 1.5, 2.0]},
    },
}


def precompute(c, p, name):
    close = [x["close"] for x in c]
    ind = {"atr": q.atr(c, 14), "adx": q.adx(c, 14)}
    if name == "ema_trend_v001":
        ind["f"], ind["s"] = q.ema(close, int(p["fast"])), q.ema(close, int(p["slow"]))
    elif name == "donchian_breakout_v001":
        ind["hi"], ind["lo"] = q.donchian(c, int(p["n"]))
        ind["vz"] = q.zscore([x["volume"] for x in c], 20)
    elif name == "zscore_meanrev_v001":
        ind["z"] = q.zscore(close, int(p["n"]))
    return ind


def signal(name, c, ind, p, i, allow_short):
    """Devuelve +1 (long), -1 (short) o 0 usando solo datos hasta i inclusive."""
    def ok(*keys):
        return all(ind[k][i] is not None for k in keys) and i > 0
    d = 0
    if name == "ema_trend_v001":
        if ok("f", "s", "adx") and ind["f"][i - 1] is not None and ind["s"][i - 1] is not None:
            up = ind["f"][i - 1] <= ind["s"][i - 1] and ind["f"][i] > ind["s"][i]
            dn = ind["f"][i - 1] >= ind["s"][i - 1] and ind["f"][i] < ind["s"][i]
            if ind["adx"][i] >= p["adx_min"]:
                d = 1 if up else -1 if dn else 0
    elif name == "donchian_breakout_v001":
        if ok("hi", "lo", "vz"):
            if c[i]["close"] > ind["hi"][i] and ind["vz"][i] >= p["vol_z"]:
                d = 1
            elif c[i]["close"] < ind["lo"][i] and ind["vz"][i] >= p["vol_z"]:
                d = -1
    elif name == "zscore_meanrev_v001":
        if ok("z", "adx") and ind["adx"][i] <= p["adx_max"]:
            d = 1 if ind["z"][i] <= -p["entry_z"] else -1 if ind["z"][i] >= p["entry_z"] else 0
    if d == -1 and not allow_short:
        return 0
    return d


# ---------------------------------------------------------------- motor
def floor_step(x, step):
    if step <= 0:
        return x
    return math.floor(x / step + 1e-9) * step


def backtest(c, name, p, cfg, start=0, end=None):
    """Simula sobre c[start:end]. Los indicadores se calculan con todo el histórico previo
    disponible (warm-up) pero solo se abren operaciones dentro de la ventana."""
    end = len(c) if end is None else end
    ind = precompute(c[:end], p, name)
    fee_t, fee_m = cfg["taker_fee"] / 100, cfg["maker_fee"] / 100
    slip, half_spread = cfg["slippage_bps"] / 1e4, cfg["spread_bps"] / 2e4
    eq = cfg["capital"]
    curve, trades, rejected = [eq], [], {"MINIMUM ORDER": 0, "NO ATR": 0, "LEVERAGE CAP": 0}
    pos = None
    for i in range(max(start, 1), end):
        bar = c[i]
        if pos:
            exit_px, reason = None, None
            d = pos["dir"]
            stop_hit = bar["low"] <= pos["stop"] if d == 1 else bar["high"] >= pos["stop"]
            tgt_hit = bar["high"] >= pos["target"] if d == 1 else bar["low"] <= pos["target"]
            if stop_hit:
                gap = (bar["open"] < pos["stop"]) if d == 1 else (bar["open"] > pos["stop"])
                base = bar["open"] if gap else pos["stop"]
                exit_px, reason, fee = base * (1 - d * slip), "stop", fee_t
            elif tgt_hit:
                exit_px, reason, fee = pos["target"], "target", fee_m
            elif i - pos["i"] >= p["max_bars"] or i == end - 1:
                exit_px, reason, fee = bar["close"] * (1 - d * (slip + half_spread)), "time" if i < end - 1 else "end", fee_t
            if exit_px is not None:
                gross = (exit_px - pos["entry"]) * pos["qty"] * d
                fees = pos["entry_fee"] + exit_px * pos["qty"] * fee
                hours = (bar["ts"] - pos["ts"]) / 3_600_000
                funding = pos["entry"] * pos["qty"] * cfg["funding_rate"] / 100 * math.floor(hours / 8) * d \
                    if cfg["futures"] else 0.0
                pnl = gross - fees - funding
                eq += pnl
                trades.append({
                    "entry_time": pos["ts"], "exit_time": bar["ts"], "dir": d, "entry": pos["entry"],
                    "exit": exit_px, "stop": pos["stop0"], "qty": pos["qty"], "fees": fees,
                    "funding": funding, "pnl": pnl, "r": pnl / pos["risk"], "reason": reason,
                    "regime": pos["regime"], "strategy": name, "params": json.dumps(p, sort_keys=True),
                })
                pos = None
        if pos is None and i < end - 1:
            d = signal(name, c, ind, p, i, cfg["allow_short"])
            if d:
                a = ind["atr"][i]
                if not a:
                    rejected["NO ATR"] += 1
                else:
                    nxt = c[i + 1]
                    entry = nxt["open"] * (1 + d * (slip + half_spread))
                    stop = entry - d * p["atr_mult"] * a
                    target = entry + d * p["rr"] * p["atr_mult"] * a
                    risk_cash = eq * cfg["risk_pct"] / 100
                    cost_unit = entry * fee_t * 2 + entry * slip
                    qty = floor_step(risk_cash / (abs(entry - stop) + cost_unit), cfg["step_size"])
                    if qty * entry > eq * cfg["max_leverage"]:
                        qty = floor_step(eq * cfg["max_leverage"] / entry, cfg["step_size"])
                        rejected["LEVERAGE CAP"] += 1
                    if qty < cfg["min_qty"] or qty * entry < cfg["min_notional"] or qty <= 0:
                        rejected["MINIMUM ORDER"] += 1
                    else:
                        f_ = q.features(c[max(0, i - 400):i + 1], cfg["tf"]) if cfg["tag_regime"] else None
                        reg = q.regime_at(c[max(0, i - 400):i + 1], f_, len(f_["close"]) - 1)[0] if f_ else "-"
                        pos = {"dir": d, "entry": entry, "stop": stop, "stop0": stop, "target": target,
                               "qty": qty, "i": i + 1, "ts": nxt["ts"], "regime": reg,
                               "entry_fee": entry * qty * fee_t,
                               "risk": qty * (abs(entry - stop) + cost_unit)}
        mark = eq
        if pos:
            mark += (bar["close"] - pos["entry"]) * pos["qty"] * pos["dir"]
        curve.append(mark)
    m = q.trade_metrics([t["pnl"] for t in trades], [t["r"] for t in trades])
    m.update(q.equity_metrics(curve, cfg["tf"]))
    m["fees_paid"] = sum(t["fees"] for t in trades)
    m["funding_paid"] = sum(t["funding"] for t in trades)
    m["rejected"] = {k: v for k, v in rejected.items() if v}
    return m, trades, curve


def score(m, min_trades):
    if m.get("trades", 0) < min_trades:
        return -1e9
    return m.get("expectancy_r", -1e9)


def grid_params(name, base):
    g = STRATEGIES[name]["grid"]
    keys = list(g)
    for combo in itertools.product(*(g[k] for k in keys)):
        p = dict(base)
        p.update(dict(zip(keys, combo)))
        if name == "ema_trend_v001" and p["fast"] >= p["slow"]:
            continue
        yield p


# ---------------------------------------------------------------- comandos
def regime_breakdown(trades):
    by = {}
    for t in trades:
        by.setdefault(t["regime"], []).append(t)
    rows = []
    for k, v in sorted(by.items()):
        m = q.trade_metrics([t["pnl"] for t in v], [t["r"] for t in v])
        rows.append(f"  {k:<16} n={m['trades']:<4} WR={m['win_rate']:.0%} expR={m['expectancy_r']:+.3f} "
                    f"PF={'inf' if m['profit_factor'] == float('inf') else round(m['profit_factor'], 2)}")
    return "\n".join(rows)


def warnings_for(m, name):
    w = []
    if m.get("trades", 0) < 30:
        w.append(f"Solo {m.get('trades', 0)} operaciones: muestra insuficiente para concluir nada.")
    if m.get("top10pct_share") and m["top10pct_share"] > 0.8:
        w.append("Más del 80% del beneficio viene del 10% de trades: edge concentrado y frágil.")
    if m.get("expectancy_r", 0) <= 0:
        w.append("Expectancy <= 0 después de costes: NO EDGE.")
    if m.get("max_drawdown", 0) > 0.3:
        w.append(f"Drawdown máximo {m['max_drawdown']:.0%}: inaceptable para capital real.")
    return w


def cmd_run(a, c, cfg):
    p = dict(STRATEGIES[a.strategy]["defaults"])
    p.update(parse_params(a.params))
    m, trades, _ = backtest(c, a.strategy, p, cfg)
    print(f"=== BACKTEST {a.strategy} · {a.data} · {cfg['tf']} ===")
    print(f"Hipótesis: {STRATEGIES[a.strategy]['hypothesis']}")
    print(f"Regímenes declarados: {', '.join(STRATEGIES[a.strategy]['regimes'])}")
    print(f"Parámetros: {p}")
    print(f"Costes: taker {cfg['taker_fee']}% maker {cfg['maker_fee']}% slippage {cfg['slippage_bps']}bps "
          f"spread {cfg['spread_bps']}bps funding {cfg['funding_rate'] if cfg['futures'] else 0}%/8h")
    print(q.fmt_metrics(m))
    if trades and cfg["tag_regime"]:
        print("Por régimen de entrada:\n" + regime_breakdown(trades))
    for w in warnings_for(m, a.strategy):
        print("⚠️ ", w)
    if a.trades_out:
        with open(a.trades_out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(trades[0].keys()) if trades else ["pnl"])
            w.writeheader()
            w.writerows(trades)
        print(f"Trades guardados en {a.trades_out}")


def cmd_wf(a, c, cfg):
    n = len(c)
    hold = int(n * a.holdout)
    usable = n - hold
    k = a.folds
    seg = usable // (k + 1)
    base = dict(STRATEGIES[a.strategy]["defaults"])
    print(f"=== WALK-FORWARD {a.strategy} · {k} folds · train={seg * a.train_mult} velas, test={seg} · "
          f"holdout final {hold} velas ===")
    oos_trades, is_scores, oos_scores, chosen = [], [], [], []
    for j in range(k):
        te_s = seg * (j + 1)
        te_e = te_s + seg
        tr_s = max(0, te_s - seg * a.train_mult)
        best, best_p, best_m = -1e9, None, None
        for p in grid_params(a.strategy, base):
            m, _, _ = backtest(c, a.strategy, p, cfg, tr_s, te_s)
            s = score(m, a.min_trades)
            if s > best:
                best, best_p, best_m = s, p, m
        if best_p is None or best == -1e9:
            print(f"Fold {j + 1}: ningún parámetro con >= {a.min_trades} trades en train -> se omite")
            continue
        m_oos, t_oos, _ = backtest(c, a.strategy, best_p, cfg, te_s, te_e)
        oos_trades += t_oos
        is_scores.append(best_m.get("expectancy_r", 0))
        oos_scores.append(m_oos.get("expectancy_r", 0) if m_oos.get("trades") else 0)
        chosen.append(best_p)
        print(f"Fold {j + 1}: IS expR={best_m.get('expectancy_r', 0):+.3f} (n={best_m['trades']}) | "
              f"OOS expR={oos_scores[-1]:+.3f} (n={m_oos.get('trades', 0)}) | params={ {k2: best_p[k2] for k2 in STRATEGIES[a.strategy]['grid']} }")
    if not oos_trades:
        print("Sin operaciones OOS. NO EDGE demostrable.")
        return
    m = q.trade_metrics([t["pnl"] for t in oos_trades], [t["r"] for t in oos_trades])
    print("\nOOS agregado:", q.fmt_metrics(m))
    is_avg = sum(is_scores) / len(is_scores)
    oos_avg = sum(oos_scores) / len(oos_scores)
    ratio = oos_avg / is_avg if is_avg > 0 else 0
    print(f"IS medio expR={is_avg:+.3f} · OOS medio expR={oos_avg:+.3f} · eficiencia WF={ratio:.0%}")
    flags = []
    if is_avg > 0 and ratio < 0.5:
        flags.append("FLAG OVERFITTING: OOS < 50% del rendimiento in-sample.")
    if sum(1 for s in oos_scores if s > 0) < len(oos_scores) / 2:
        flags.append("Menos de la mitad de los folds OOS son positivos: edge inestable.")
    if len({json.dumps({k2: p[k2] for k2 in STRATEGIES[a.strategy]['grid']}, sort_keys=True) for p in chosen}) == len(chosen) > 2:
        flags.append("Parámetros óptimos distintos en cada fold: no hay región estable.")
    for f in flags:
        print("⚠️ ", f)
    if hold:
        from collections import Counter
        mode = Counter(json.dumps(p, sort_keys=True) for p in chosen).most_common(1)[0][0]
        p = json.loads(mode)
        mh, _, _ = backtest(c, a.strategy, p, cfg, n - hold, n)
        print(f"\nHOLDOUT final (no usado en ninguna optimización) con params más elegidos: {q.fmt_metrics(mh)}")
        print("Usa el holdout UNA sola vez. Si lo miras y vuelves a optimizar, deja de ser out-of-sample.")


def cmd_sens(a, c, cfg):
    base = dict(STRATEGIES[a.strategy]["defaults"])
    rows = []
    for p in grid_params(a.strategy, base):
        m, _, _ = backtest(c, a.strategy, p, cfg)
        rows.append((p, m))
    keys = list(STRATEGIES[a.strategy]["grid"])
    rows.sort(key=lambda r: r[1].get("expectancy_r", -9) if r[1].get("trades", 0) >= a.min_trades else -9, reverse=True)
    print(f"=== SENSIBILIDAD {a.strategy} · {len(rows)} combinaciones ===")
    valid = [r for r in rows if r[1].get("trades", 0) >= a.min_trades]
    pos = sum(1 for r in valid if r[1].get("expectancy_r", 0) > 0)
    print(f"Combinaciones con >= {a.min_trades} trades: {len(valid)} · con expectancy > 0: {pos} "
          f"({pos / len(valid):.0%})" if valid else "Ninguna combinación con trades suficientes.")
    print("Top 10:")
    for p, m in rows[:10]:
        print(f"  {' '.join(f'{k}={p[k]}' for k in keys):<45} n={m.get('trades', 0):<4} "
              f"expR={m.get('expectancy_r', 0):+.3f} PF={m.get('profit_factor', 0):.2f} DD={m.get('max_drawdown', 0):.0%}")
    if valid:
        best_p = valid[0][0]
        neigh = [m for p, m in valid if sum(1 for k in keys if p[k] != best_p[k]) == 1]
        if neigh:
            share = sum(1 for m in neigh if m.get("expectancy_r", 0) > 0) / len(neigh)
            print(f"Vecinos del mejor (1 parámetro distinto): {len(neigh)}, positivos {share:.0%}")
            if share < 0.6:
                print("⚠️  FLAG OVERFIT: el mejor resultado es un pico aislado, no una región estable.")
        if pos / len(valid) < 0.5:
            print("⚠️  La mayoría de combinaciones pierden: la estrategia no es robusta en estos datos.")


def parse_params(s):
    out = {}
    for kv in (s or "").split(","):
        if "=" in kv:
            k, v = kv.split("=", 1)
            out[k.strip()] = float(v)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["run", "wf", "sens", "list"])
    ap.add_argument("--data")
    ap.add_argument("--tf", default="1h", choices=list(q.INTERVAL_MS))
    ap.add_argument("--strategy", default="ema_trend_v001", choices=list(STRATEGIES))
    ap.add_argument("--params", help="k=v,k=v para sobreescribir defaults")
    ap.add_argument("--capital", type=float, default=1000)
    ap.add_argument("--risk-pct", type=float, default=1.0)
    ap.add_argument("--taker-fee", type=float, default=0.10, help="%% (spot estándar 0.10; verificar tu nivel)")
    ap.add_argument("--maker-fee", type=float, default=0.10)
    ap.add_argument("--slippage-bps", type=float, default=2.0)
    ap.add_argument("--spread-bps", type=float, default=1.0)
    ap.add_argument("--futures", action="store_true", help="Aplica funding y permite apalancamiento")
    ap.add_argument("--funding-rate", type=float, default=0.01, help="%% por 8h (aprox.; usa histórico real si puedes)")
    ap.add_argument("--max-leverage", type=float, default=1.0)
    ap.add_argument("--allow-short", action="store_true", help="Cortos (futuros o margin)")
    ap.add_argument("--step-size", type=float, default=0.0, help="stepSize del símbolo (exchangeInfo)")
    ap.add_argument("--min-qty", type=float, default=0.0)
    ap.add_argument("--min-notional", type=float, default=5.0)
    ap.add_argument("--no-regime", action="store_true", help="No etiquetar régimen (más rápido)")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--train-mult", type=int, default=3, help="Train = train_mult × tamaño de test")
    ap.add_argument("--holdout", type=float, default=0.2, help="Fracción final reservada (0 = sin holdout)")
    ap.add_argument("--min-trades", type=int, default=20)
    ap.add_argument("--trades-out", help="CSV de salida con las operaciones (para monte_carlo.py)")
    a = ap.parse_args()

    if a.cmd == "list":
        for k, v in STRATEGIES.items():
            print(f"{k}\n  Hipótesis: {v['hypothesis']}\n  Regímenes: {', '.join(v['regimes'])}\n  Defaults: {v['defaults']}\n")
        return 0
    if not a.data:
        ap.error("--data es obligatorio")
    c = q.load_candles(a.data)
    issues = q.quality_report(c, a.tf)
    bad = {k: len(v) for k, v in issues.items() if v}
    if bad.get("duplicates") or bad.get("invalid_ohlc") or bad.get("non_positive") or bad.get("non_monotonic"):
        print(f"DATA PROBLEM: {bad}. No se hace backtest con datos corruptos. Limpia/redescarga primero.")
        return 2
    if bad:
        print(f"Aviso calidad de datos: {bad}")
    cfg = {
        "tf": a.tf, "capital": a.capital, "risk_pct": a.risk_pct, "taker_fee": a.taker_fee,
        "maker_fee": a.maker_fee, "slippage_bps": a.slippage_bps, "spread_bps": a.spread_bps,
        "futures": a.futures, "funding_rate": a.funding_rate,
        "max_leverage": a.max_leverage if a.futures else 1.0, "allow_short": a.allow_short,
        "step_size": a.step_size, "min_qty": a.min_qty, "min_notional": a.min_notional,
        "tag_regime": not a.no_regime and a.cmd == "run",
    }
    {"run": cmd_run, "wf": cmd_wf, "sens": cmd_sens}[a.cmd](a, c, cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
