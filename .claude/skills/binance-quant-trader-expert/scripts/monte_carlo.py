#!/usr/bin/env python3
"""Monte Carlo sobre una lista de operaciones (columna r en R, o pnl).

Remuestrea la secuencia de trades (bootstrap con reemplazo, o permutación) y
reporta la DISTRIBUCIÓN de drawdowns, rachas y capital final. No es una
predicción: asume que los trades futuros se parecen a los pasados.

  monte_carlo.py --trades trades.csv --risk-pct 1 --sims 5000 --ruin-dd 50
"""
import argparse
import csv
import random
import sys


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p / 100 * len(xs)))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades", required=True, help="CSV con columna r (preferida) o pnl")
    ap.add_argument("--risk-pct", type=float, default=1.0, help="%% de equity arriesgado por trade (si usa r)")
    ap.add_argument("--capital", type=float, default=1000.0, help="Capital inicial (si usa pnl)")
    ap.add_argument("--sims", type=int, default=5000)
    ap.add_argument("--n", type=int, help="Trades por simulación (def. = histórico)")
    ap.add_argument("--method", choices=["bootstrap", "shuffle"], default="bootstrap")
    ap.add_argument("--ruin-dd", type=float, default=50.0, help="%% de drawdown considerado ruina")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    with open(a.trades, newline="") as f:
        rows = list(csv.DictReader(f))
    use_r = rows and "r" in rows[0] and rows[0]["r"] not in ("", None)
    vals = [float(r["r"] if use_r else r["pnl"]) for r in rows if (r.get("r") if use_r else r.get("pnl")) not in ("", None)]
    if len(vals) < 30:
        print(f"Solo {len(vals)} trades. Monte Carlo con menos de 30 trades no es fiable; resultado orientativo.")
    if not vals:
        return 1
    rnd = random.Random(a.seed)
    n = a.n or len(vals)
    dds, finals, streaks, ruined = [], [], [], 0
    for _ in range(a.sims):
        seq = [rnd.choice(vals) for _ in range(n)] if a.method == "bootstrap" else rnd.sample(vals, len(vals))
        eq = 1.0 if use_r else a.capital
        start = eq
        peak, mdd, st, mst = eq, 0.0, 0, 0
        for v in seq:
            eq = eq * (1 + v * a.risk_pct / 100) if use_r else eq + v
            peak = max(peak, eq)
            mdd = max(mdd, (peak - eq) / peak if peak > 0 else 1.0)
            st = st + 1 if v <= 0 else 0
            mst = max(mst, st)
            if eq <= 0:
                mdd = 1.0
                break
        dds.append(mdd * 100)
        finals.append((eq / start - 1) * 100)
        streaks.append(mst)
        ruined += mdd * 100 >= a.ruin_dd
    print(f"=== MONTE CARLO · {a.method} · {a.sims} sims × {n} trades · base: {'R' if use_r else 'PnL'} "
          f"{'(riesgo ' + str(a.risk_pct) + '%/trade)' if use_r else ''} ===")
    print(f"Media histórica por trade: {sum(vals) / len(vals):+.4f}{'R' if use_r else ''}")
    for name, xs in (("Max drawdown %", dds), ("Retorno final %", finals), ("Racha perdedora", streaks)):
        print(f"{name:<17} p5={pct(xs, 5):8.2f}  p25={pct(xs, 25):8.2f}  p50={pct(xs, 50):8.2f}  "
              f"p75={pct(xs, 75):8.2f}  p95={pct(xs, 95):8.2f}")
    print(f"Prob. retorno final < 0: {sum(1 for f in finals if f < 0) / a.sims:.1%}")
    print(f"Riesgo de ruina (DD >= {a.ruin_dd:.0f}%): {ruined / a.sims:.2%}")
    print("Interpretación: planifica para el drawdown p95, no para la mediana. Esto NO es una predicción.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
