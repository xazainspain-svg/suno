#!/usr/bin/env python3
"""Diario de trading en CSV con estadísticas.

  journal.py add --symbol BTCUSDT --side long --entry 64250 --stop 63400 --exit 66100 --size 0.06 ...
  journal.py close --id 3 --exit 1.0912 [--pnl 84.5] [--fees 2]
  journal.py list [--last 10] [--open]
  journal.py stats [--by setup] [--since 2026-09-01]
  journal.py export-md
Usa --file RUTA (antes del subcomando) para otro archivo. Por defecto: trading_journal.csv
"""
import argparse
import csv
import os
import sys
from collections import defaultdict
from datetime import datetime

FIELDS = ["id", "date", "symbol", "market", "side", "entry", "stop", "target", "exit",
          "size", "fees", "pnl", "r", "setup", "timeframe", "emotion", "followed_plan", "notes"]


def load(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def compute(row):
    """Rellena pnl y r si hay datos suficientes."""
    e, s, x = fnum(row.get("entry")), fnum(row.get("stop")), fnum(row.get("exit"))
    size, fees = fnum(row.get("size")), fnum(row.get("fees")) or 0.0
    d = 1 if row.get("side", "long").lower() == "long" else -1
    if x is not None and e is not None:
        if fnum(row.get("pnl")) is None and size is not None:
            row["pnl"] = f"{(x - e) * size * d - fees:.2f}"
        if s is not None and e != s:
            row["r"] = f"{(x - e) * d / abs(e - s):.2f}"
    return row


def cmd_add(a):
    rows = load(a.file)
    nid = max((int(r["id"]) for r in rows), default=0) + 1
    row = {
        "id": nid, "date": a.date or datetime.now().isoformat(timespec="minutes"),
        "symbol": a.symbol.upper(), "market": a.market, "side": a.side, "entry": a.entry,
        "stop": a.stop if a.stop is not None else "", "target": a.target if a.target is not None else "",
        "exit": a.exit if a.exit is not None else "", "size": a.size if a.size is not None else "",
        "fees": a.fees, "pnl": a.pnl if a.pnl is not None else "", "r": "",
        "setup": a.setup, "timeframe": a.timeframe, "emotion": a.emotion,
        "followed_plan": a.followed_plan, "notes": a.notes,
    }
    rows.append(compute(row))
    save(a.file, rows)
    state = "cerrada" if row["exit"] != "" else "ABIERTA"
    print(f"Operación #{nid} guardada ({state}) en {a.file}. PnL={row['pnl'] or '-'} R={row['r'] or '-'}")


def cmd_close(a):
    rows = load(a.file)
    for r in rows:
        if str(r["id"]) == str(a.id):
            r["exit"] = a.exit
            if a.fees is not None:
                r["fees"] = a.fees
            if a.pnl is not None:
                r["pnl"] = a.pnl
            elif fnum(r.get("size")) is not None:
                r["pnl"] = ""  # se recalcula con el precio de salida
            if a.notes:
                r["notes"] = (r.get("notes", "") + " | " + a.notes).strip(" |")
            compute(r)
            save(a.file, rows)
            print(f"Operación #{a.id} cerrada. PnL={r['pnl'] or '-'} R={r['r'] or '-'}")
            return
    print(f"No existe la operación #{a.id}")
    sys.exit(1)


def cmd_list(a):
    rows = load(a.file)
    if a.open:
        rows = [r for r in rows if not r.get("exit")]
    rows = rows[-a.last:] if a.last else rows
    if not rows:
        print("Sin operaciones.")
        return
    cols = ["id", "date", "symbol", "side", "entry", "stop", "exit", "pnl", "r", "setup", "emotion"]
    print(" | ".join(cols))
    for r in rows:
        print(" | ".join(str(r.get(c, "")) for c in cols))


def stats_for(rows):
    closed = [r for r in rows if r.get("exit") and fnum(r.get("pnl")) is not None]
    n = len(closed)
    if n == 0:
        return None
    pnls = [fnum(r["pnl"]) for r in closed]
    rs = [fnum(r["r"]) for r in closed if fnum(r.get("r")) is not None]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gp, gl = sum(wins), -sum(losses)
    eq, peak, mdd = 0.0, 0.0, 0.0
    streak = max_streak = 0
    for p in pnls:
        eq += p
        peak = max(peak, eq)
        mdd = max(mdd, peak - eq)
        streak = streak + 1 if p <= 0 else 0
        max_streak = max(max_streak, streak)
    return {
        "n": n, "win_rate": len(wins) / n * 100, "pnl": sum(pnls),
        "avg_win": gp / len(wins) if wins else 0.0,
        "avg_loss": -gl / len(losses) if losses else 0.0,
        "profit_factor": gp / gl if gl > 0 else float("inf"),
        "expectancy": sum(pnls) / n,
        "expectancy_r": sum(rs) / len(rs) if rs else None, "total_r": sum(rs) if rs else None,
        "max_dd": mdd, "max_losing_streak": max_streak,
        "plan_broken": sum(1 for r in closed if r.get("followed_plan", "").lower() == "no"),
    }


def fmt_stats(s):
    er = f"{s['expectancy_r']:.2f}R" if s["expectancy_r"] is not None else "-"
    tr = f"{s['total_r']:.2f}R" if s["total_r"] is not None else "-"
    pf = "∞" if s["profit_factor"] == float("inf") else f"{s['profit_factor']:.2f}"
    return (f"Ops cerradas: {s['n']} | Win rate: {s['win_rate']:.1f}% | PnL: {s['pnl']:.2f} | Total: {tr}\n"
            f"Media ganadora: {s['avg_win']:.2f} | Media perdedora: {s['avg_loss']:.2f} | Profit factor: {pf}\n"
            f"Expectancy: {s['expectancy']:.2f}/op ({er}) | Max drawdown: {s['max_dd']:.2f} | "
            f"Racha perdedora máx: {s['max_losing_streak']} | Sin seguir plan: {s['plan_broken']}")


def filtered(a):
    rows = load(a.file)
    if getattr(a, "since", None):
        rows = [r for r in rows if r.get("date", "") >= a.since]
    return rows


def cmd_stats(a):
    rows = filtered(a)
    s = stats_for(rows)
    if not s:
        print("No hay operaciones cerradas.")
        return
    print("=== GLOBAL ===")
    print(fmt_stats(s))
    if s["n"] < 30:
        print(f"(Muestra pequeña: {s['n']} operaciones. Conclusiones provisionales.)")
    if a.by:
        groups = defaultdict(list)
        for r in rows:
            groups[r.get(a.by) or "(vacío)"].append(r)
        print(f"\n=== POR {a.by.upper()} ===")
        res = [(k, stats_for(v)) for k, v in groups.items()]
        res = sorted([x for x in res if x[1]], key=lambda x: x[1]["pnl"], reverse=True)
        for k, st in res:
            er = f"{st['expectancy_r']:.2f}R" if st["expectancy_r"] is not None else "-"
            print(f"- {k}: n={st['n']} WR={st['win_rate']:.0f}% PnL={st['pnl']:.2f} Exp={er}")
    opened = [r for r in rows if not r.get("exit")]
    if opened:
        print(f"\nOperaciones abiertas: {len(opened)}")


def cmd_export(a):
    rows = filtered(a)
    s = stats_for(rows)
    print("# Resumen del diario de trading\n")
    if s:
        print("```\n" + fmt_stats(s) + "\n```\n")
    print("| # | Fecha | Símbolo | Lado | Entrada | Salida | PnL | R | Setup | Emoción |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['id']} | {r['date']} | {r['symbol']} | {r['side']} | {r['entry']} | {r.get('exit','')} | "
              f"{r.get('pnl','')} | {r.get('r','')} | {r.get('setup','')} | {r.get('emotion','')} |")


def main():
    p = argparse.ArgumentParser(description="Diario de trading")
    p.add_argument("--file", default="trading_journal.csv")
    sub = p.add_subparsers(dest="cmd", required=True)

    ad = sub.add_parser("add")
    ad.add_argument("--symbol", required=True)
    ad.add_argument("--side", required=True, choices=["long", "short"])
    ad.add_argument("--entry", type=float, required=True)
    ad.add_argument("--stop", type=float)
    ad.add_argument("--target", type=float)
    ad.add_argument("--exit", type=float)
    ad.add_argument("--size", type=float)
    ad.add_argument("--fees", type=float, default=0.0)
    ad.add_argument("--pnl", type=float)
    ad.add_argument("--market", default="crypto", choices=["crypto", "forex", "stocks", "futures"])
    ad.add_argument("--setup", default="")
    ad.add_argument("--timeframe", default="")
    ad.add_argument("--emotion", default="")
    ad.add_argument("--followed-plan", default="yes", choices=["yes", "no"])
    ad.add_argument("--notes", default="")
    ad.add_argument("--date", help="ISO, p.ej. 2026-10-02T14:30")
    ad.set_defaults(fn=cmd_add)

    cl = sub.add_parser("close")
    cl.add_argument("--id", required=True)
    cl.add_argument("--exit", type=float, required=True)
    cl.add_argument("--pnl", type=float)
    cl.add_argument("--fees", type=float)
    cl.add_argument("--notes", default="")
    cl.set_defaults(fn=cmd_close)

    ls = sub.add_parser("list")
    ls.add_argument("--last", type=int, default=0)
    ls.add_argument("--open", action="store_true")
    ls.set_defaults(fn=cmd_list)

    st = sub.add_parser("stats")
    st.add_argument("--by", choices=["setup", "symbol", "emotion", "side", "market", "timeframe", "followed_plan"])
    st.add_argument("--since")
    st.set_defaults(fn=cmd_stats)

    ex = sub.add_parser("export-md")
    ex.add_argument("--since")
    ex.set_defaults(fn=cmd_export)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
