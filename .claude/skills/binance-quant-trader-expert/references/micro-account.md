# MICRO_ACCOUNT_MODE — 10 EUR

```
MICRO_ACCOUNT_MODE=true
INITIAL_CAPITAL=10 EUR   (convertir a USDT con el tipo actual, p.ej. EUR/USDT ≈ 1,15 → ~11,5 USDT; verificar)
LIVE_TRADING=false hasta autorización explícita
MAX_OPEN_POSITIONS=1 · MAX_LEVERAGE=x2 · sin aumentar capital automáticamente
```

## Objetivo
Validar ejecución, riesgo, infraestructura y comportamiento real de la estrategia (slippage, fills, reconciliación, reportes). **No** conseguir una rentabilidad. Un +20% sobre 10 € es ruido estadístico, no evidencia.

## La aritmética del mínimo nocional
Con riesgo 1% de ~11,5 USDT → ~0,115 USDT de riesgo por trade.
Si el mínimo nocional del símbolo es N (leer de exchangeInfo; en muchos pares spot USDT ronda 5 USDT, pero varía):

```
distancia_stop_máxima% ≈ riesgo / N = 0,115 / 5 ≈ 2,3 %  (menos los costes)
```
- Stops más amplios que ~2% → la orden mínima arriesga más del 1% → **NO TRADE (MINIMUM ORDER)**.
- Stops muy ajustados → los costes (0,1% + 0,1% + slippage ≈ 0,2–0,25% del nocional) son una parte enorme del riesgo → **EXECUTION RISK** si superan el 25% del riesgo.
- Ventana viable aproximada: stop entre ~0,7% y ~2% en spot con comisiones estándar. `risk_check.py --micro` lo calcula exacto con los filtros reales.
- Futuros USDⓈ-M: los mínimos nocionales de muchos contratos (p. ej. BTCUSDT) son mucho mayores que 10 € → normalmente inviable sin apalancamiento alto → NO TRADE. Verificar el minNotional actual por símbolo.

## Alternativas honestas cuando no cuadra
1. Elegir símbolos líquidos con minNotional bajo y volatilidad que permita stops de 1–2%.
2. Subir el riesgo por trade a 2% **solo** si el usuario lo decide explícitamente (queda registrado). Nunca más.
3. Seguir en paper/testnet hasta que el capital lo permita.
4. Aceptar que en esta fase muchas señales acabarán en NO TRADE: es el resultado correcto.

## Qué medir en esta fase
- Slippage real vs supuesto del backtest.
- % de órdenes límite que no se llenan (y si las que no se llenan eran las ganadoras → sesgo de selección adversa).
- Fees reales, redondeos a stepSize, rechazos de la API y su causa.
- Que la reconciliación y el circuit breaker se disparan cuando deben (probarlos a propósito).
- Informe diario completo (`quant_journal.py report`).

Pasar a más capital solo con: ≥ 30 trades micro sin incidencias de infraestructura, costes medidos ≈ supuestos, y decisión explícita del usuario.
