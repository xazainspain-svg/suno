# Particularidades por mercado

## Cripto

- **Mercado 24/7.** Fines de semana con menos liquidez → mechas y falsas
  rupturas. Apertura semanal (domingo 00:00 UTC) y cierre diario (00:00 UTC)
  son niveles de referencia.
- **Spot vs perpetuos.** En perpetuos: apalancamiento, liquidación y
  **funding rate** (cada 8 h normalmente). Funding muy positivo = mercado
  sobreapalancado en largos → riesgo de barrido a la baja (y al revés).
- **Open Interest:** subida de precio + subida de OI = nuevas posiciones
  (tendencia con combustible); subida de precio + bajada de OI = cierre de
  cortos (short squeeze, menos sostenible).
- **BTC manda.** Las altcoins suelen amplificar el movimiento de BTC. Mirar
  BTC.D (dominancia) y ETH/BTC para el apetito por altcoins.
- **Riesgos específicos:** hackeos, deslistados, desbloqueos de tokens
  (*token unlocks*), noticias regulatorias (SEC, ETF), quiebras de exchanges.
  Altcoins pequeñas: baja liquidez, slippage, manipulación.
- **Tamaño mínimo y decimales:** cada exchange tiene paso de cantidad; el
  script da el tamaño teórico, el usuario debe redondear hacia abajo.

## Forex

- **Sesiones (hora UTC aprox., verano/invierno varía 1 h):**
  - Asia (Tokio): 00:00–09:00 — rangos estrechos, JPY/AUD/NZD.
  - Londres: 07:00–16:00 — mayor volumen, rupturas del rango asiático.
  - Nueva York: 12:00–21:00 — solape con Londres (12:00–16:00) = máxima
    volatilidad.
- **Pip:** 0,0001 en la mayoría de pares; 0,01 en pares con JPY. 1 lote
  estándar = 100.000 unidades; mini = 10.000; micro = 1.000.
- **Valor del pip (lote estándar):** ≈ 10 USD en pares XXX/USD. En otros pares
  depende del tipo de cambio → pide el valor al usuario o calcúlalo
  (`--pip-value`). Oro (XAUUSD): habitualmente 1 lote = 100 oz, 1 pip = 0,01 →
  1 USD por pip y lote... pero varía por bróker: confirmar con la
  especificación del contrato.
- **Noticias de alto impacto:** NFP (primer viernes de mes), IPC/CPI, decisión
  de tipos (FOMC, BCE, BoE, BoJ), PMI. Spreads se disparan alrededor.
- **Swap:** coste/abono por mantener la posición de un día a otro; relevante en
  swing.
- **Correlaciones:** EURUSD y GBPUSD positivas; EURUSD y USDCHF negativas; DXY
  inverso a la mayoría de XXX/USD.

## Acciones e índices

- **Horario:** NYSE/NASDAQ 9:30–16:00 ET (15:30–22:00 hora España
  normalmente). Pre-market y after-hours con poca liquidez y gaps.
- **Gaps:** el precio puede abrir lejos del cierre anterior → un stop no
  garantiza el precio de salida. Reducir tamaño si se mantiene posición en
  earnings o fin de semana.
- **Earnings:** comprobar siempre la fecha de resultados antes de una operación
  swing. Movimientos del 5–20% en una sesión son normales.
- **Catalizadores macro:** FOMC, IPC, empleo, rendimiento del bono a 10 años,
  VIX (miedo). Índices: S&P 500 (SPX/ES/SPY), NASDAQ 100 (NDX/NQ/QQQ), Dow,
  DAX, IBEX.
- **Acciones:** 1 acción = 1 unidad; tamaño en número de acciones (fracciones
  si el bróker lo permite).
- **Futuros de índices:** valor por punto según contrato (ES = 50 $/punto,
  MES = 5 $/punto, NQ = 20 $/punto, MNQ = 2 $/punto) → usar
  `--market futures --point-value`.
- **CFDs:** el valor por punto depende del bróker; pedirlo al usuario.
- **Sector y amplitud:** mirar el sector (XLK, SMH...) y el índice; una acción
  rara vez sube con fuerza si su sector y el índice caen.

## Fuentes recomendadas para datos en vivo

- Precios: TradingView, CoinMarketCap/CoinGecko, Investing.com, Yahoo Finance.
- Calendario: Investing.com / Forex Factory (calendario económico), Earnings
  Whispers / Nasdaq (resultados).
- Cripto derivados: Coinglass (funding, OI, liquidaciones).
- Noticias: Reuters, Bloomberg, CoinDesk, The Block.

Cita siempre la fuente y la hora del dato.
