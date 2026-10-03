# Investigación y validación

## Índice
1. Plantilla de hipótesis · 2. Data engine · 3. Features · 4. Régimen ·
5. Multi-timeframe · 6. Backtest y sesgos · 7. Métricas de edge · 8. Walk-forward ·
9. Robustez de parámetros · 10. Monte Carlo · 11. ML · 12. Versionado ·
13. Criterios de aceptación

## 1. Plantilla de hipótesis (obligatoria por estrategia)
```
STRATEGY: nombre_v001
HYPOTHESIS: Cuando X ocurre bajo régimen Y, Z ocurre con frecuencia
            estadísticamente significativa (falsable).
RATIONALE: por qué existiría (comportamiento, flujo, estructura, coste de oportunidad...)
DATA REQUIRED: símbolos, timeframes, periodo, fuentes (OHLCV, funding, OI, book...)
ENTRY / EXIT / STOP / TARGET: reglas exactas, sin discrecionalidad
EXPECTED EDGE: expectancy esperada en R y nº de trades/mes
EXPECTED COST: fees + spread + slippage + funding por trade (en R)
FAILURE CONDITIONS: qué resultado refuta la hipótesis (p.ej. expectancy OOS ≤ 0 tras 100 trades)
MARKET REGIMES: dónde debería funcionar y dónde no
```

## 2. Data engine
- Fuentes: REST (`binance_data.py`), ficheros históricos data.binance.vision, WebSockets en vivo.
- Conservar siempre `timestamp`, `source`, `symbol`, `timeframe`.
- Detectar: velas faltantes, duplicadas, outliers, errores de timestamp, gaps de API, bad ticks, OHLC inconsistente. (`binance_data.py check`).
- Gaps por mantenimiento de Binance: documentar, no interpolar precios inventados. Si se rellenan para cálculos, marcar las velas sintéticas y no operar en ellas.
- Spot y perpetuo del mismo activo son series distintas: no mezclarlas.

## 3. Features
Precio/volatilidad: returns, log returns, ATR, realized/rolling volatility, Bollinger width, compresión/expansión de rango, EMA distance, VWAP deviation, momentum/ROC, ADX, RSI, MACD, volume z-score.
Microestructura (requiere book/trades): spread, imbalance del libro (bid−ask)/(bid+ask) en una banda, profundidad, imbalance de trades, volumen agresivo (taker buy vs sell: `taker_buy_base` en klines), presión compradora/vendedora.
Derivados: funding, cambio de OI, basis (mark−index o perp−spot), divergencia precio/OI, interacción funding/OI.
Regla: cada feature debe calcularse con datos disponibles en el instante t (sin look-ahead).

## 4. Régimen
Clases: TREND_UP, TREND_DOWN, RANGE, BREAKOUT, HIGH_VOLATILITY, LOW_VOLATILITY, CAPITULATION, EXPANSION, UNKNOWN.
`quantlib.regime_at` es un clasificador heurístico transparente (ADX, EMAs 50/200, percentil de ATR%, Bollinger width, Donchian, volumen z). Se puede enriquecer con OI y funding. Cada estrategia declara sus regímenes; operar fuera de ellos → NO EDGE. UNKNOWN → NO TRADE.

## 5. Multi-timeframe
Ejemplo: 4H régimen → 1H estructura → 15M setup → 5M ejecución. El TF inferior no contradice automáticamente al superior; solo afina la entrada. En backtest, alinear los TF por tiempo de CIERRE (la vela 4H solo se conoce cuando cierra).

## 6. Backtest y sesgos
Incluir: fees maker/taker, spread, slippage, funding, latencia (entrada en la vela siguiente), partial fills (asumir peor caso en órdenes límite: solo se llenan si el precio cruza, no si toca), minQty/minNotional, tickSize/stepSize.

| Sesgo | Cómo se cuela | Cómo evitarlo |
|---|---|---|
| Look-ahead | usar el close de la vela actual para entrar a ese close; indicadores centrados; TF superior no cerrado | señal al cierre, ejecución en la siguiente apertura |
| Survivorship | universo = monedas que existen hoy | incluir deslistadas, universo por fecha |
| Data leakage | normalizar/escalar con todo el dataset; seleccionar features mirando el test | ajustar transformaciones solo en train |
| Overfitting | muchos parámetros, poca muestra | pocos parámetros, regiones estables, OOS |
| P-hacking | probar 200 variantes y quedarse con la mejor | registrar TODAS las pruebas; corregir por múltiples comparaciones (exigir más en OOS cuanto más se probó) |

## 7. Métricas de edge
Win rate, avg win, avg loss, expectancy (en dinero y en R), profit factor, max drawdown, Sharpe, Sortino, Calmar, nº de trades, racha perdedora, concentración (cuánto beneficio aportan los mejores trades).
Preguntas obligatorias: ¿el edge es estable en el tiempo (por año/trimestre)? ¿depende de pocos trades? ¿de un periodo concreto (p. ej. bull 2021)? ¿de un solo activo? ¿de un solo régimen? ¿decae (edge decay: comparar primera vs segunda mitad)?
Significancia aproximada: t = expectancy_R / (std_R / √n). t < 2 → no distinguible de ruido.

## 8. Walk-forward
TRAIN → VALIDATION → TEST; ventanas rodantes (`backtest.py wf`): optimizar en train, medir en el bloque siguiente nunca visto, concatenar OOS. Eficiencia WF = expectancy OOS / IS. < 50% → FLAG OVERFITTING. Reservar un holdout final que se usa **una vez**.

## 9. Robustez de parámetros
`backtest.py sens`: rejilla razonable. Buscar mesetas (muchos vecinos rentables), no picos. Si el mejor resultado tiene vecinos perdedores → FLAG OVERFIT. Probar también en otros activos y otros periodos; y con costes ×1,5.

## 10. Monte Carlo
Bootstrap o permutación de trades (`monte_carlo.py`): distribución de drawdown máximo, rachas, retorno final, riesgo de ruina. Usar p95 de drawdown para fijar el riesgo por trade. Requiere ≥ 30 trades (idealmente ≥ 100). No es predicción: asume que el futuro se parece a la muestra.

## 11. Machine learning
Solo si aporta valor medible frente a un baseline simple (reglas, regresión logística) en OOS. Usos razonables: clasificación de régimen, ranking de señales, predicción de volatilidad, detección de anomalías, estimación de probabilidad, sizing. Validación con purged/embargoed CV en series temporales. Nada de reentrenar online cambiando la estrategia en vivo: NEW DATA → RESEARCH → VALIDATION → OOS → PAPER → APPROVAL → DEPLOY.

## 12. Versionado
`estrategia_v001`, `_v002`…; nunca sobrescribir. Cada versión guarda: reglas, parámetros, datos usados, resultados IS/OOS/WF/MC/paper, fecha y motivo del cambio. Cada modificación repite backtest → validation → walk-forward → OOS → paper.

## 13. Criterios mínimos de aceptación (por defecto)
| Fase | Requisito |
|---|---|
| Backtest | ≥ 100 trades (o ≥ 30 en TF altos), expectancy > 0 neta, PF > 1,2, DD aceptable |
| Robustez | ≥ 60% de vecinos de parámetros rentables; sobrevive costes ×1,5 |
| Walk-forward | eficiencia ≥ 50%, mayoría de folds OOS positivos |
| Holdout | expectancy > 0 |
| Monte Carlo | DD p95 compatible con MAX_DRAWDOWN |
| Paper | ≥ 2–4 semanas o ≥ 30 señales; ejecución y costes dentro de lo esperado |
| Live micro | sin errores de infraestructura; slippage medido ≈ supuesto |
Si falla cualquiera → NO EDGE / OVERFIT STRATEGY, y se vuelve a investigar.
