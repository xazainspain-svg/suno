#!/usr/bin/env python3
"""RISK ENGINE pre-trade. Tiene autoridad absoluta: devuelve APPROVED o NO TRADE con motivos.

Aplica: riesgo por trade, R:R neto de costes, filtros de Binance (tickSize, stepSize,
minQty, minNotional), límites diarios/semanales/drawdown, exposición y correlación,
apalancamiento vs liquidación, liquidez (spread/profundidad) y MICRO_ACCOUNT_MODE.

Ejemplos:
  risk_check.py --balance 10 --micro --entry 2450 --stop 2410 --target 2550 \
      --exchange-info exinfo.json --symbol ETHUSDT --spread-bps 1 --depth-usd 250000
  risk_check.py --balance 1000 --entry 64000 --stop 63000 --target 67000 \
      --tick-size 0.01 --step-size 0.00001 --min-qty 0.00001 --min-notional 5 \
      --futures --leverage 3 --daily-pnl-pct -1.2 --open-positions 1 --correlated-risk-pct 1
Salida: texto + JSON (--json) con decision, reasons, qty, price, risk, costes.
Código de salida: 0 = APPROVED, 3 = NO TRADE.
"""
import argparse
import json
import sys
from decimal import Decimal, ROUND_DOWN, ROUND_UP

DEFAULTS = {
    "RISK_PER_TRADE": 1.0, "MAX_DAILY_LOSS": 3.0, "MAX_WEEKLY_LOSS": 6.0, "MAX_DRAWDOWN": 15.0,
    "MAX_EXPOSURE": 100.0, "MAX_LEVERAGE": 3.0, "MAX_OPEN_POSITIONS": 3,
    "MAX_CORRELATED_EXPOSURE": 2.0, "MAX_POSITION_SIZE": 100.0, "MIN_RR": 1.5,
    "MAX_SPREAD_BPS": 10.0, "MAX_DEPTH_SHARE": 0.05, "MAX_COST_SHARE_OF_RISK": 0.25,
}


def D(x):
    return Decimal(str(x))


def round_step(x, step, mode=ROUND_DOWN):
    if not step or D(step) == 0:
        return D(x)
    return (D(x) / D(step)).to_integral_value(rounding=mode) * D(step)


def filters_from_exchange_info(path, symbol):
    """Lee filtros de un JSON de /api/v3/exchangeInfo o /fapi/v1/exchangeInfo."""
    with open(path) as f:
        data = json.load(f)
    syms = data.get("symbols", [data] if "filters" in data else [])
    for s in syms:
        if s.get("symbol") == symbol:
            out = {"tick_size": None, "step_size": None, "min_qty": None, "min_notional": None, "status": s.get("status")}
            for flt in s.get("filters", []):
                t = flt.get("filterType")
                if t == "PRICE_FILTER":
                    out["tick_size"] = float(flt["tickSize"])
                elif t == "LOT_SIZE":
                    out["step_size"] = float(flt["stepSize"])
                    out["min_qty"] = float(flt["minQty"])
                elif t in ("NOTIONAL", "MIN_NOTIONAL"):
                    v = flt.get("minNotional", flt.get("notional"))
                    if v is not None:
                        out["min_notional"] = float(v)
            return out
    raise SystemExit(f"Símbolo {symbol} no encontrado en {path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--balance", type=float, required=True, help="Capital disponible en la divisa de cotización (USDT)")
    ap.add_argument("--entry", type=float, required=True)
    ap.add_argument("--stop", type=float, required=True)
    ap.add_argument("--target", type=float, required=True)
    ap.add_argument("--risk-pct", type=float, help="Riesgo por trade (def. RISK_PER_TRADE)")
    ap.add_argument("--entry-type", choices=["market", "limit"], default="limit")
    ap.add_argument("--taker-fee", type=float, default=0.10, help="%%")
    ap.add_argument("--maker-fee", type=float, default=0.10, help="%%")
    ap.add_argument("--slippage-bps", type=float, default=2.0)
    ap.add_argument("--spread-bps", type=float, help="Spread actual (de bookTicker)")
    ap.add_argument("--depth-usd", type=float, help="Profundidad acumulada del lado relevante dentro de ±0.5%%")
    ap.add_argument("--exchange-info", help="JSON de exchangeInfo")
    ap.add_argument("--symbol")
    ap.add_argument("--tick-size", type=float)
    ap.add_argument("--step-size", type=float)
    ap.add_argument("--min-qty", type=float)
    ap.add_argument("--min-notional", type=float)
    ap.add_argument("--futures", action="store_true")
    ap.add_argument("--leverage", type=float, default=1.0)
    ap.add_argument("--mmr", type=float, default=0.5, help="Maintenance margin rate %% (ver leverageBracket)")
    ap.add_argument("--daily-pnl-pct", type=float, default=0.0, help="PnL realizado hoy en %% (negativo = pérdida)")
    ap.add_argument("--weekly-pnl-pct", type=float, default=0.0)
    ap.add_argument("--drawdown-pct", type=float, default=0.0, help="Drawdown actual desde el pico")
    ap.add_argument("--open-positions", type=int, default=0)
    ap.add_argument("--exposure-pct", type=float, default=0.0, help="Exposición nocional abierta en %% del balance")
    ap.add_argument("--correlated-risk-pct", type=float, default=0.0, help="Riesgo abierto en activos correlacionados (>0.7)")
    ap.add_argument("--regime", default="", help="Régimen actual; UNKNOWN => NO TRADE")
    ap.add_argument("--strategy-regimes", default="", help="Regímenes declarados por la estrategia, separados por coma")
    ap.add_argument("--micro", action="store_true", help="MICRO_ACCOUNT_MODE (10 EUR)")
    ap.add_argument("--limits", help="JSON con overrides de límites (claves como DEFAULTS)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    L = dict(DEFAULTS)
    if a.limits:
        L.update(json.load(open(a.limits)))
    if a.micro:
        # En micro-cuenta el objetivo es validar infraestructura; el riesgo % se mantiene,
        # y NO se relajan los mínimos del exchange.
        L["MAX_LEVERAGE"] = min(L["MAX_LEVERAGE"], 2.0)
        L["MAX_OPEN_POSITIONS"] = 1

    flt = {"tick_size": a.tick_size, "step_size": a.step_size, "min_qty": a.min_qty,
           "min_notional": a.min_notional, "status": "TRADING"}
    if a.exchange_info:
        if not a.symbol:
            ap.error("--symbol obligatorio con --exchange-info")
        flt.update({k: v for k, v in filters_from_exchange_info(a.exchange_info, a.symbol).items() if v is not None})

    reasons, notes = [], []
    side = "LONG" if a.stop < a.entry else "SHORT"
    if (side == "LONG" and a.target <= a.entry) or (side == "SHORT" and a.target >= a.entry):
        reasons.append("BAD RISK/REWARD: target del lado equivocado")
    if any(flt[k] is None for k in ("tick_size", "step_size", "min_notional")):
        reasons.append("DATA PROBLEM: faltan filtros del símbolo (tickSize/stepSize/minNotional). "
                       "Descarga exchangeInfo; no se asumen")
    if flt.get("status") not in (None, "TRADING"):
        reasons.append(f"EXECUTION RISK: símbolo en estado {flt['status']}")

    # Redondeo de precios a tickSize (stop/target hacia el lado conservador)
    tick = flt["tick_size"] or 0
    entry = round_step(a.entry, tick, ROUND_DOWN if side == "LONG" else ROUND_UP)
    stop = round_step(a.stop, tick, ROUND_DOWN if side == "LONG" else ROUND_UP)
    target = round_step(a.target, tick, ROUND_DOWN if side == "LONG" else ROUND_UP)
    dist = abs(entry - stop)
    risk_pct = D(a.risk_pct if a.risk_pct is not None else L["RISK_PER_TRADE"])
    if risk_pct > D(L["RISK_PER_TRADE"]) * 2:
        reasons.append(f"RISK LIMIT: riesgo {risk_pct}% > 2× RISK_PER_TRADE")
    bal = D(a.balance)
    risk_cash = bal * risk_pct / 100

    fee_in = D(a.taker_fee if a.entry_type == "market" else a.maker_fee) / 100
    fee_out_stop = D(a.taker_fee) / 100
    slip = D(a.slippage_bps) / 10000
    half_spread = D(a.spread_bps or 0) / 20000
    # Pérdida real por unidad si salta el stop: distancia + slippage del stop + comisiones ida/vuelta
    loss_unit = dist + stop * slip + entry * fee_in + stop * fee_out_stop + (entry * half_spread if a.entry_type == "market" else 0)
    qty = round_step(risk_cash / loss_unit, flt["step_size"]) if dist > 0 else D(0)
    max_notional = bal * D(min(a.leverage if a.futures else 1.0, L["MAX_LEVERAGE"])) * D(L["MAX_POSITION_SIZE"]) / 100
    if qty * entry > max_notional:
        qty = round_step(max_notional / entry, flt["step_size"])
        notes.append("Tamaño recortado por apalancamiento/MAX_POSITION_SIZE")
    min_n = D(flt["min_notional"] or 0)
    min_q = D(flt["min_qty"] or 0)
    notional = qty * entry
    if qty <= 0 or qty < min_q or notional < min_n:
        # ¿Qué riesgo implicaría la orden mínima posible?
        q_min = max(min_q, round_step(min_n / entry, flt["step_size"], ROUND_UP)) if entry > 0 else D(0)
        risk_min = q_min * loss_unit
        reasons.append(f"MINIMUM ORDER: la orden mínima ({q_min} ≈ {q_min * entry:.2f} nocional) arriesgaría "
                       f"{risk_min:.4f} = {risk_min / bal * 100:.2f}% del balance (> {risk_pct}% permitido)")
    if a.entry_type == "market":
        fee_tp = D(a.taker_fee) / 100
    else:
        fee_tp = D(a.maker_fee) / 100
    gain_unit = abs(target - entry) - entry * fee_in - target * fee_tp
    rr_gross = abs(target - entry) / dist if dist else D(0)
    rr_net = gain_unit / loss_unit if loss_unit else D(0)
    cost_unit = loss_unit - dist
    if rr_net < D(L["MIN_RR"]):
        reasons.append(f"BAD RISK/REWARD: R:R neto {rr_net:.2f} < {L['MIN_RR']}")
    if dist and cost_unit / loss_unit > D(L["MAX_COST_SHARE_OF_RISK"]):
        reasons.append(f"EXECUTION RISK: los costes son el {cost_unit / loss_unit:.0%} del riesgo (stop demasiado ajustado)")

    # Límites de cuenta
    if a.daily_pnl_pct <= -L["MAX_DAILY_LOSS"]:
        reasons.append(f"RISK LIMIT: pérdida diaria {a.daily_pnl_pct}% alcanzó MAX_DAILY_LOSS (circuit breaker)")
    elif a.daily_pnl_pct - float(risk_pct) < -L["MAX_DAILY_LOSS"]:
        reasons.append("RISK LIMIT: si este trade pierde se supera MAX_DAILY_LOSS")
    if a.weekly_pnl_pct <= -L["MAX_WEEKLY_LOSS"]:
        reasons.append("RISK LIMIT: MAX_WEEKLY_LOSS alcanzado")
    if a.drawdown_pct >= L["MAX_DRAWDOWN"]:
        reasons.append("RISK LIMIT: MAX_DRAWDOWN alcanzado (circuit breaker)")
    if a.open_positions >= L["MAX_OPEN_POSITIONS"]:
        reasons.append("RISK LIMIT: MAX_OPEN_POSITIONS")
    if a.exposure_pct + float(notional / bal * 100 if bal else 0) > L["MAX_EXPOSURE"] * (a.leverage if a.futures else 1):
        reasons.append("RISK LIMIT: MAX_EXPOSURE")
    if a.correlated_risk_pct + float(risk_pct) > L["MAX_CORRELATED_EXPOSURE"]:
        reasons.append(f"HIGH CORRELATION: riesgo correlacionado total {a.correlated_risk_pct + float(risk_pct):.2f}% "
                       f"> {L['MAX_CORRELATED_EXPOSURE']}%")
    if a.futures and a.leverage > L["MAX_LEVERAGE"]:
        reasons.append(f"RISK LIMIT: apalancamiento x{a.leverage} > MAX_LEVERAGE x{L['MAX_LEVERAGE']}")
    liq = None
    if a.futures and a.leverage > 1:
        # Aproximación margen aislado: liq ≈ entry × (1 ∓ 1/lev ± mmr)
        mmr = D(a.mmr) / 100
        lev = D(a.leverage)
        liq = entry * (1 - 1 / lev + mmr) if side == "LONG" else entry * (1 + 1 / lev - mmr)
        if abs(entry - liq) < 2 * dist:
            reasons.append(f"RISK LIMIT: liquidación aprox. {liq:.4f} a menos de 2× la distancia del stop")

    # Liquidez
    if a.spread_bps is None:
        notes.append("Spread desconocido: consúltalo en bookTicker antes de ejecutar")
    elif a.spread_bps > L["MAX_SPREAD_BPS"]:
        reasons.append(f"HIGH SPREAD: {a.spread_bps} bps > {L['MAX_SPREAD_BPS']}")
    if a.depth_usd is None:
        notes.append("Profundidad desconocida: consulta depth antes de ejecutar")
    elif notional > D(a.depth_usd) * D(L["MAX_DEPTH_SHARE"]):
        reasons.append(f"LOW LIQUIDITY: la orden es > {L['MAX_DEPTH_SHARE']:.0%} de la profundidad cercana")

    # Régimen
    if a.regime.upper() == "UNKNOWN":
        reasons.append("UNKNOWN REGIME")
    if a.regime and a.strategy_regimes:
        if a.regime.upper() not in [r.strip().upper() for r in a.strategy_regimes.split(",")]:
            reasons.append(f"NO EDGE: la estrategia no declara el régimen {a.regime}")

    decision = "NO TRADE" if reasons else "APPROVED"
    out = {
        "decision": decision, "reasons": reasons, "notes": notes, "side": side,
        "entry": str(entry), "stop": str(stop), "target": str(target), "qty": str(qty),
        "notional": f"{notional:.4f}", "risk_cash": f"{qty * loss_unit:.4f}",
        "risk_pct_effective": f"{(qty * loss_unit / bal * 100) if bal else 0:.3f}",
        "rr_gross": f"{rr_gross:.2f}", "rr_net": f"{rr_net:.2f}",
        "est_cost_if_stopped": f"{qty * cost_unit:.4f}",
        "liquidation_approx": None if liq is None else f"{liq:.4f}",
        "micro_account_mode": a.micro, "filters": flt,
    }
    if a.json:
        print(json.dumps(out, indent=2, default=str))
    else:
        print(f"=== RISK ENGINE · {a.symbol or ''} {side} {'· MICRO' if a.micro else ''} ===")
        print(f"Entrada {entry} · Stop {stop} · Target {target} (redondeados a tickSize)")
        print(f"Cantidad {qty} · Nocional {notional:.4f} · Riesgo efectivo {out['risk_cash']} ({out['risk_pct_effective']}%)")
        print(f"R:R bruto {out['rr_gross']} · R:R neto de costes {out['rr_net']} · Coste si salta el stop {out['est_cost_if_stopped']}")
        if liq is not None:
            print(f"Liquidación aprox. {out['liquidation_approx']} (verificar con la plataforma)")
        print(f"\nDECISIÓN: {decision}")
        for r in reasons:
            print(f"  ✗ {r}")
        for n in notes:
            print(f"  · {n}")
    return 0 if decision == "APPROVED" else 3


if __name__ == "__main__":
    sys.exit(main())
