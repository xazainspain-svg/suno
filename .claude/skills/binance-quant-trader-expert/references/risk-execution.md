# Riesgo, cartera, ejecución y fallos

## 1. Risk Engine — variables por defecto (`risk_check.py`)
| Variable | Default | Nota |
|---|---|---|
| RISK_PER_TRADE | 1% | riesgo real = distancia stop + costes |
| MAX_DAILY_LOSS | 3% | alcanzado → circuit breaker hasta el día siguiente |
| MAX_WEEKLY_LOSS | 6% | pausa y revisión |
| MAX_DRAWDOWN | 15% | desde el pico → circuit breaker, revisión completa |
| MAX_EXPOSURE | 100% del balance × apalancamiento permitido | |
| MAX_LEVERAGE | x3 (x2 en micro) | |
| MAX_OPEN_POSITIONS | 3 (1 en micro) | |
| MAX_CORRELATED_EXPOSURE | 2% de riesgo total en activos con corr > 0.7 | |
| MAX_POSITION_SIZE | 100% del nocional permitido | |
| MIN_RR | 1,5 neto de costes | |
| MAX_SPREAD_BPS | 10 | |
| MAX_DEPTH_SHARE | 5% de la profundidad en ±0,5% | |
| MAX_COST_SHARE_OF_RISK | 25% | si los costes son > 25% del riesgo, el stop es demasiado ajustado |
Sobreescribir con `--limits limits.json`. El Risk Engine puede vetar cualquier operación; nadie (ni el usuario por chat) lo salta: se cambia el límite explícitamente y queda registrado.

## 2. Position sizing
```
qty = (equity × risk%) / (|entry − stop| + slippage_stop + fee_in + fee_out)
qty = floor(qty / stepSize) × stepSize ; precios redondeados a tickSize (stop hacia el lado conservador)
check: qty ≥ minQty, qty × price ≥ minNotional, nocional ≤ equity × leverage
```
Ajustar por liquidez (no más del 5% de la profundidad cercana). Si cumplir minNotional exige arriesgar más del permitido → NO TRADE (MINIMUM ORDER).

## 3. Portfolio y correlación
- Analizar BTC, ETH y elegibles conjuntamente: correlación rolling (`scanner.py --corr`), beta respecto a BTC, volatilidad, concentración por tema (L1, memes, IA, DeFi...).
- La correlación cripto sube en caídas (correlation breakdown/regime): usar la correlación de periodos de estrés, no la media.
- Varias posiciones = misma apuesta → sumar su riesgo y aplicar MAX_CORRELATED_EXPOSURE → REDUCE EXPOSURE.

## 4. Liquidez (antes de ejecutar)
spread (`binance_data.py book`) · profundidad en ±0,5% (`depth`) · volumen 24h (`ticker`) · slippage estimado (recorrer el libro con la cantidad) · impacto · mínimos del símbolo. Insuficiente → NO TRADE (LOW LIQUIDITY / HIGH SPREAD).

## 5. Ejecución
Pipeline: SIGNAL → RISK → ORDER → EXECUTION → RECONCILIATION (cada etapa registra su decisión en el audit log).
- Límite / LIMIT_MAKER (post-only) cuando el impacto importa y la urgencia es baja; market solo si el coste de no entrar supera al slippage esperado.
- Stops: STOP_LOSS_LIMIT en spot (riesgo de no llenarse en gaps) o STOP_MARKET reduceOnly en futuros (workingType MARK_PRICE).
- Take profit: límite (maker) reduceOnly en futuros.
- Tras enviar: consultar estado; manejar parciales (ajustar stop/target a la cantidad realmente llenada).

## 6. Máquina de estados de órdenes (interna)
```
NEW → ACKNOWLEDGED → PARTIALLY_FILLED → FILLED
            │               │
            ├──→ CANCEL_PENDING → CANCELLED
            ├──→ REJECTED
            ├──→ EXPIRED
            └──→ ERROR (timeout/respuesta desconocida → consultar por clientOrderId, nunca reenviar a ciegas)
```
Transiciones solo con confirmación de Binance (respuesta REST o executionReport). Nunca marcar FILLED porque se envió.

## 7. Reconciliación
Comparar continuamente LOCAL vs BINANCE: balances, posiciones (futuros: positionRisk), órdenes abiertas, fills (myTrades / userTrades). Discrepancia → **FREEZE NEW ORDERS** (`binance_client.py reconcile` crea el fichero FREEZE) hasta explicación manual.

## 8. Failure engine y circuit breaker
Detectar: fallo de API, red, rate limit, datos obsoletos (última vela/tick más vieja que 2× el intervalo), precio inválido (fuera de PERCENT_PRICE o salto > N·ATR), posición o balance inesperado, orden duplicada, mismatch de ejecución, desconexión de websocket.
Circuit breaker si: MAX_DAILY_LOSS · MAX_DRAWDOWN · umbral de fallos de API · POSITION_MISMATCH · DATA_FAILURE · EXECUTION_ANOMALY (slippage > 3× esperado) · MARKET_ANOMALY (volatilidad extrema, halt, depeg de stablecoin).
Acción: cancelar entradas nuevas, no aumentar riesgo, mantener/gestionar stops existentes, registrar causa, notificar.

## 9. Seguridad
- Claves en `.env` (fuera del repositorio, en `.gitignore`), variables de entorno o gestor de secretos.
- Permisos mínimos (sin retirada), whitelist de IP.
- Nunca imprimir API_KEY, API_SECRET, firmas ni peticiones firmadas; los logs filtran esos campos.
- Si una clave se expone (chat, commit, captura): revocar y regenerar inmediatamente.

## 10. Audit log
Cada decisión reconstruible: datos de entrada (hash/rango), features, señal, decisión de riesgo (con motivos), decisión de orden, respuesta de ejecución, resultado, versión de estrategia, versión de software, timestamp UTC. Formato append-only (JSONL). `binance_client.py` escribe `audit_log.jsonl`; `quant_journal.py` registra decisiones y trades.

## 11. Execution analytics (por trade)
expected vs actual entry/exit, slippage (bps), spread, fees, latencia, implementation shortfall = PnL en papel desde el precio de señal − PnL real. Comparar calidad de señal vs calidad de ejecución: una buena señal mal ejecutada no es un fallo de la estrategia, y viceversa.
