#!/usr/bin/env python3
"""Calculadora de tamaño de posición para cripto, forex, acciones y futuros.

Ejemplos:
  python3 position_size.py --market crypto --balance 5000 --risk 1 \
      --entry 64250 --stop 63400 --target 66800 --leverage 5
  python3 position_size.py --market forex --balance 3000 --risk 1 \
      --entry 1.0850 --stop 1.0820 --target 1.0920 --pair EURUSD
  python3 position_size.py --market stocks --balance 10000 --risk 0.5 \
      --entry 182.4 --stop 178.9 --target 192
  python3 position_size.py --market futures --balance 20000 --risk 1 \
      --entry 5210 --stop 5195 --target 5250 --point-value 5   # MES
"""
import argparse
import math
import sys


def pip_size(pair: str) -> float:
    return 0.01 if pair and "JPY" in pair.upper() else 0.0001


def main() -> int:
    p = argparse.ArgumentParser(description="Calculadora de tamaño de posición")
    p.add_argument("--market", required=True, choices=["crypto", "forex", "stocks", "futures"])
    p.add_argument("--balance", type=float, required=True, help="Capital de la cuenta")
    p.add_argument("--risk", type=float, default=1.0, help="%% de la cuenta a arriesgar (def. 1)")
    p.add_argument("--risk-amount", type=float, help="Riesgo fijo en dinero (ignora --risk)")
    p.add_argument("--entry", type=float, required=True)
    p.add_argument("--stop", type=float, required=True)
    p.add_argument("--target", type=float, help="Take profit (para R:R)")
    p.add_argument("--leverage", type=float, default=1.0, help="Apalancamiento (cripto/futuros)")
    p.add_argument("--fee", type=float, default=0.0, help="Comisión por lado en %% del nocional (p.ej. 0.05)")
    p.add_argument("--pair", default="", help="Par forex, p.ej. EURUSD o USDJPY")
    p.add_argument("--pip-value", type=float, help="Valor de 1 pip por lote estándar en moneda de la cuenta (def. 10)")
    p.add_argument("--lot-size", type=float, default=100_000, help="Unidades por lote estándar (forex, def. 100000)")
    p.add_argument("--point-value", type=float, help="Valor por punto y contrato (futuros/CFD)")
    a = p.parse_args()

    if a.entry == a.stop:
        print("ERROR: entrada y stop no pueden ser iguales.")
        return 1
    side = "LONG" if a.stop < a.entry else "SHORT"
    if a.target is not None:
        if (side == "LONG" and a.target <= a.entry) or (side == "SHORT" and a.target >= a.entry):
            print("ERROR: el target está del lado equivocado respecto a la entrada.")
            return 1

    risk_money = a.risk_amount if a.risk_amount is not None else a.balance * a.risk / 100
    dist = abs(a.entry - a.stop)
    warnings = []
    out = []

    if a.market in ("crypto", "stocks"):
        # Pérdida por unidad = distancia + comisiones de entrada y salida
        fee_per_unit = (a.entry + a.stop) * a.fee / 100
        units = risk_money / (dist + fee_per_unit)
        if a.market == "stocks":
            units = math.floor(units)
            if units == 0:
                warnings.append("El riesgo no alcanza ni para 1 acción: stop demasiado lejos o cuenta pequeña.")
        notional = units * a.entry
        margin = notional / a.leverage
        out += [("Unidades", f"{units:,.6f}" if a.market == "crypto" else f"{units:,}"),
                ("Nocional", f"{notional:,.2f}"),
                ("Margen requerido", f"{margin:,.2f}  (apalancamiento x{a.leverage:g})")]
        if margin > a.balance:
            warnings.append("El margen supera el balance: sube apalancamiento o reduce el tamaño.")
        if a.leverage > 1:
            liq = a.entry * (1 - 1 / a.leverage) if side == "LONG" else a.entry * (1 + 1 / a.leverage)
            liq_dist = abs(a.entry - liq)
            out.append(("Liquidación aprox. (aislado)", f"{liq:,.4f}"))
            if liq_dist < 2 * dist:
                warnings.append("La liquidación está a menos de 2x la distancia del stop: apalancamiento demasiado alto.")
            if (side == "LONG" and liq >= a.stop) or (side == "SHORT" and liq <= a.stop):
                warnings.append("¡PELIGRO! Te liquidan ANTES de tocar el stop.")
        fees_total = units * fee_per_unit
    elif a.market == "forex":
        ps = pip_size(a.pair)
        pips = dist / ps
        pv = a.pip_value if a.pip_value is not None else 10.0
        if a.pip_value is None and a.pair and not a.pair.upper().endswith("USD"):
            warnings.append("Valor de pip asumido 10/lote: solo exacto en pares XXX/USD con cuenta en USD. Usa --pip-value.")
        lots = risk_money / (pips * pv)
        out += [("Distancia stop", f"{pips:.1f} pips"),
                ("Lotes estándar", f"{lots:.2f}"),
                ("Mini lotes (0.1)", f"{lots * 10:.1f}"),
                ("Micro lotes (0.01)", f"{lots * 100:.0f}"),
                ("Unidades", f"{lots * a.lot_size:,.0f}")]
        fees_total = 0.0
        if pips < 5:
            warnings.append("Stop de menos de 5 pips: el spread puede sacarte por ruido.")
    else:  # futures
        if a.point_value is None:
            print("ERROR: futuros necesita --point-value (ES=50, MES=5, NQ=20, MNQ=2...).")
            return 1
        contracts_f = risk_money / (dist * a.point_value)
        contracts = math.floor(contracts_f)
        out += [("Contratos (exacto)", f"{contracts_f:.2f}"),
                ("Contratos (redondeado abajo)", f"{contracts}")]
        if contracts == 0:
            warnings.append("No llega a 1 contrato con este riesgo: usa el micro o amplía el riesgo con cabeza.")
        risk_money_eff = contracts * dist * a.point_value
        out.append(("Riesgo real con contratos enteros", f"{risk_money_eff:,.2f}"))
        fees_total = 0.0

    print(f"\n=== {a.market.upper()} · {side} ===")
    print(f"Balance: {a.balance:,.2f} | Riesgo: {risk_money:,.2f} ({risk_money / a.balance * 100:.2f}%)")
    print(f"Entrada {a.entry} | Stop {a.stop} (distancia {dist:g}, {dist / a.entry * 100:.2f}%)")
    for k, v in out:
        print(f"  {k:<32} {v}")
    if a.fee and a.market in ("crypto", "stocks"):
        print(f"  {'Comisiones estimadas (ida+vuelta)':<32} {fees_total:,.2f}")
    if a.target is not None:
        rr = abs(a.target - a.entry) / dist
        print(f"Target {a.target} | R:R = 1:{rr:.2f} | Ganancia potencial ≈ {risk_money * rr:,.2f}")
        if rr < 2:
            warnings.append(f"R:R 1:{rr:.2f} por debajo del mínimo recomendado 1:2.")
    pct = risk_money / a.balance * 100
    if pct > 2:
        warnings.append(f"Riesgo del {pct:.1f}% por operación: por encima del máximo recomendado (2%).")
    if warnings:
        print("\n⚠️  AVISOS:")
        for w in warnings:
            print(f"  - {w}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
