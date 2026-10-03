# Laboratorio de estrategias

Ninguna estrategia "funciona" por defecto. Cada familia de abajo es un punto de
partida de **investigación**: escribe la hipótesis (plantilla en
research-validation.md), pruébala y acepta el resultado aunque sea negativo.

Implementadas en `backtest.py`: `ema_trend_v001`, `donchian_breakout_v001`,
`zscore_meanrev_v001`. Para añadir una: entrada en `STRATEGIES` (hipótesis,
regímenes, defaults, grid), cálculo en `precompute()` y regla en `signal()`
usando solo datos ≤ i.

## Trend following
- **EMA cross / EMA stack** con filtro ADX; **Donchian** (canal n); **breakouts** de máximos de n velas.
- Regímenes: TREND_UP/DOWN, EXPANSION. Falla en RANGE (whipsaws).
- Perfil típico: win rate bajo (30–45%), R:R alto; edge concentrado en pocos trades grandes → necesita muestra grande y paciencia.

## Momentum
- **ROC**, fuerza relativa vs BTC, **ranking de momentum** cross-sectional (comprar los top-k del universo, rebalanceo periódico).
- Riesgo: reversión violenta en altcoins; incluir costes de rebalanceo y survivorship (monedas deslistadas).

## Mean reversion
- **z-score** del precio vs media, **desviación del VWAP**, toques de **Bollinger**, extremos estadísticos (RSI 2–5).
- Regímenes: RANGE, LOW_VOLATILITY. Peligrosa en tendencia fuerte o capitulación: obligatorio filtro de régimen y stop.
- Perfil: win rate alto, R:R bajo → muy sensible a costes.

## Volatilidad
- **Contracción → expansión** (squeeze de Bollinger/Keltner, NR7, ATR en percentil bajo).
- Regímenes de ATR para escalar tamaño (menos tamaño en HIGH_VOLATILITY).

## Breakout
- Ruptura de rango con **confirmación de volumen** (vol z > 1) y expansión de volatilidad; filtro de retest opcional.
- Medir falsas rupturas por régimen y por sesión (Asia/Europa/EE. UU.).

## Order flow (requiere trades/book)
- **Imbalance** del libro, **delta** (taker buy − taker sell, disponible en klines como taker_buy_base), volumen agresivo, cambios de liquidez (retirada de bids/asks).
- Horizonte corto (minutos): costes y latencia dominan → validar con datos tick y slippage realista.

## Derivados
- **Funding** extremo (p. ej. > percentil 95 histórico) como señal contraria de posicionamiento saturado.
- **Basis** perp−spot / mark−index; cash-and-carry (largo spot + corto perp cobrando funding) — riesgo de liquidación en la pata corta, costes y cambio de signo del funding.
- **OI**: precio ↑ + OI ↑ = nuevas posiciones (tendencia con combustible); precio ↑ + OI ↓ = cierre de cortos (squeeze, menos sostenible); precio ↓ + OI ↑ = cortos agresivos; precio ↓ + OI ↓ = desapalancamiento/capitulación.
- Interacción funding/OI: funding alto + OI récord + precio estancado = riesgo de barrido de largos.

## Arbitraje estadístico
- **Pares** (p. ej. ETH/BTC, SOL/ETH): test de **cointegración** (Engle-Granger / Johansen), hedge ratio por regresión rolling, z-score del spread, half-life de reversión.
- Riesgo: ruptura de la relación (correlation breakdown); stop por z extremo y por tiempo.

## Checklist de una idea nueva
1. ¿Hay un motivo económico/conductual para que exista?
2. ¿Se puede medir con los datos disponibles sin look-ahead?
3. ¿El edge esperado supera claramente los costes (en R)?
4. ¿En qué régimen debería fallar? ¿Se puede filtrar ese régimen?
5. ¿Cuántos trades/mes generará? (pocos → validación lenta)
