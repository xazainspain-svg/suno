#!/usr/bin/env python3
"""TRADING JOURNAL + EXECUTION ANALYTICS + DAILY REPORT (JSONL, append-only).

Cada línea es un evento auditable. Nunca se reescriben ni borran eventos.

  quant_journal.py decision --symbol ETHUSDT --strategy donchian_breakout_v001 --regime BREAKOUT \
      --direction long --decision "NO TRADE" --reasons "MINIMUM ORDER;HIGH SPREAD"
  quant_journal.py trade --symbol ETHUSDT --strategy donchian_breakout_v001 --regime BREAKOUT \
      --direction long --signal-price 2450 --expected-entry 2450 --actual-entry 2451.2 \
      --stop 2410 --target 2550 --qty 0.0025 --expected-exit 2550 --actual-exit 2549.1 \
      --fees 0.012 --funding 0 --entry-ts 2026-10-03T10:00 --exit-ts 2026-10-03T18:00 \
      --spread-bps 0.8 --latency-ms 140 --reason "cierre > Donchian-20, vol z 1.8"
  quant_journal.py report [--date 2026-10-03] --capital 11.6
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

FILE = os.environ.get("QUANT_JOURNAL", "quant_journal.jsonl")


def append(ev):
    ev["logged_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(FILE, "a") as f:
        f.write(json.dumps(ev) + "\n")


def load():
    if not os.path.exists(FILE):
        return []
    return [json.loads(l) for l in open(FILE) if l.strip()]


def cmd_decision(a):
    append({"type": "decision", "symbol": a.symbol, "strategy": a.strategy, "regime": a.regime,
            "direction": a.direction, "decision": a.decision,
            "reasons": [r.strip() for r in (a.reasons or "").split(";") if r.strip()],
            "date": a.date or datetime.now(timezone.utc).date().isoformat()})
    print("Decisión registrada.")


def cmd_trade(a):
    d = 1 if a.direction == "long" else -1
    risk_unit = abs(a.expected_entry - a.stop)
    gross = (a.actual_exit - a.actual_entry) * a.qty * d
    pnl = gross - a.fees - a.funding
    entry_slip = (a.actual_entry - a.expected_entry) * d          # >0 = peor de lo esperado
    exit_slip = (a.expected_exit - a.actual_exit) * d if a.expected_exit is not None else 0.0
    paper_pnl = ((a.expected_exit if a.expected_exit is not None else a.actual_exit) - a.signal_price) * a.qty * d
    shortfall = paper_pnl - pnl                                    # implementation shortfall en dinero
    ev = {
        "type": "trade", "symbol": a.symbol, "strategy": a.strategy, "regime": a.regime, "direction": a.direction,
        "entry_ts": a.entry_ts, "exit_ts": a.exit_ts, "date": (a.exit_ts or a.entry_ts or "")[:10]
        or datetime.now(timezone.utc).date().isoformat(),
        "signal_price": a.signal_price, "expected_entry": a.expected_entry, "actual_entry": a.actual_entry,
        "stop": a.stop, "target": a.target, "qty": a.qty, "expected_exit": a.expected_exit,
        "actual_exit": a.actual_exit, "fees": a.fees, "funding": a.funding, "pnl": round(pnl, 8),
        "risk": round(risk_unit * a.qty, 8), "r": round(pnl / (risk_unit * a.qty), 4) if risk_unit and a.qty else None,
        "entry_slippage_bps": round(entry_slip / a.expected_entry * 1e4, 2),
        "exit_slippage_bps": round(exit_slip / a.expected_exit * 1e4, 2) if a.expected_exit else None,
        "implementation_shortfall": round(shortfall, 8), "spread_bps": a.spread_bps, "latency_ms": a.latency_ms,
        "reason": a.reason, "exit_reason": a.exit_reason, "mode": a.mode,
    }
    total_slip = (ev["entry_slippage_bps"] or 0) + (ev["exit_slippage_bps"] or 0)
    ev["execution_quality"] = "GOOD" if total_slip <= 5 else "FAIR" if total_slip <= 15 else "POOR"
    append(ev)
    print(json.dumps({k: ev[k] for k in ("pnl", "r", "entry_slippage_bps", "exit_slippage_bps",
                                         "implementation_shortfall", "execution_quality")}, indent=1))
    print("Post-trade: ¿la señal era válida? ¿régimen correcto? ¿coste esperado? "
          "No cambies la estrategia por un único resultado.")


def cmd_report(a):
    evs = load()
    day = a.date or datetime.now(timezone.utc).date().isoformat()
    trades = [e for e in evs if e["type"] == "trade" and e.get("date") == day]
    all_trades = [e for e in evs if e["type"] == "trade" and e.get("date", "") <= day]
    decisions = [e for e in evs if e["type"] == "decision" and e.get("date") == day]
    rejected = [d for d in decisions if d["decision"].upper() == "NO TRADE"]
    errors = [e for e in evs if e["type"] == "error" and e.get("date") == day]
    pnl = sum(t["pnl"] for t in trades)
    cum = a.capital
    peak, dd = cum, 0.0
    for t in all_trades:
        cum += t["pnl"]
        peak = max(peak, cum)
        dd = max(dd, (peak - cum) / peak if peak else 0)
    wins = [t for t in trades if t["pnl"] > 0]
    gl = -sum(t["pnl"] for t in trades if t["pnl"] <= 0)
    gp = sum(t["pnl"] for t in wins)
    by_strat = {}
    for t in trades:
        by_strat.setdefault(t["strategy"], []).append(t["pnl"])
    reasons = {}
    for d in rejected:
        for r in d["reasons"] or ["(sin motivo)"]:
            key = r.split(":")[0]
            reasons[key] = reasons.get(key, 0) + 1
    start_cap = cum - pnl
    print(f"# DAILY TRADING REPORT · {day}\n")
    rows = [
        ("Capital (cierre)", f"{cum:.4f}"), ("PnL", f"{pnl:+.4f}"),
        ("PnL %", f"{pnl / start_cap * 100:+.2f}%" if start_cap else "-"), ("Drawdown máx. acumulado", f"{dd:.2%}"),
        ("Trades", len(trades)), ("Win rate", f"{len(wins) / len(trades):.0%}" if trades else "-"),
        ("Profit factor", ("inf" if gl == 0 else f"{gp / gl:.2f}") if trades else "-"),
        ("Fees", f"{sum(t['fees'] for t in trades):.4f}"), ("Funding", f"{sum(t['funding'] for t in trades):.4f}"),
        ("Slippage medio entrada (bps)", f"{sum(t['entry_slippage_bps'] for t in trades) / len(trades):.2f}" if trades else "-"),
        ("Riesgo medio por trade", f"{sum(t['risk'] for t in trades) / len(trades):.4f}" if trades else "-"),
        ("Mejor trade", f"{max(trades, key=lambda t: t['pnl'])['symbol']} {max(t['pnl'] for t in trades):+.4f}" if trades else "-"),
        ("Peor trade", f"{min(trades, key=lambda t: t['pnl'])['symbol']} {min(t['pnl'] for t in trades):+.4f}" if trades else "-"),
        ("Regímenes", ", ".join(sorted({t['regime'] for t in trades} | {d['regime'] for d in decisions})) or "-"),
        ("Decisiones evaluadas", len(decisions)), ("Rechazadas (NO TRADE)", len(rejected)),
        ("Errores de sistema", len(errors)),
    ]
    print("| Métrica | Valor |\n|---|---|")
    for k, v in rows:
        print(f"| {k} | {v} |")
    if by_strat:
        print("\n**Por estrategia:** " + "; ".join(f"{k}: n={len(v)} PnL={sum(v):+.4f}" for k, v in by_strat.items()))
    if reasons:
        print("\n**Motivos de NO TRADE:** " + ", ".join(f"{k} ×{v}" for k, v in sorted(reasons.items(), key=lambda x: -x[1])))
    poor = [t for t in trades if t["execution_quality"] == "POOR"]
    if poor:
        print(f"\n⚠️ {len(poor)} trades con ejecución POOR: revisar tipo de orden/liquidez.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("decision")
    for k in ("symbol", "strategy", "regime", "decision"):
        d.add_argument(f"--{k}", required=True)
    d.add_argument("--direction", default="flat")
    d.add_argument("--reasons")
    d.add_argument("--date")
    d.set_defaults(fn=cmd_decision)
    t = sub.add_parser("trade")
    for k in ("symbol", "strategy", "regime"):
        t.add_argument(f"--{k}", required=True)
    t.add_argument("--direction", required=True, choices=["long", "short"])
    for k in ("signal-price", "expected-entry", "actual-entry", "stop", "qty", "actual-exit"):
        t.add_argument(f"--{k}", type=float, required=True)
    t.add_argument("--target", type=float)
    t.add_argument("--expected-exit", type=float)
    t.add_argument("--fees", type=float, default=0.0)
    t.add_argument("--funding", type=float, default=0.0)
    t.add_argument("--spread-bps", type=float)
    t.add_argument("--latency-ms", type=float)
    t.add_argument("--entry-ts")
    t.add_argument("--exit-ts")
    t.add_argument("--reason", default="")
    t.add_argument("--exit-reason", default="")
    t.add_argument("--mode", default="paper", choices=["backtest", "paper", "live_micro", "live"])
    t.set_defaults(fn=cmd_trade)
    r = sub.add_parser("report")
    r.add_argument("--date")
    r.add_argument("--capital", type=float, required=True, help="Capital inicial de la cuenta")
    r.set_defaults(fn=cmd_report)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
