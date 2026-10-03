# Binance — base de conocimiento

> Binance cambia endpoints, filtros, comisiones y reglas con frecuencia. Esta
> guía es el mapa conceptual; **cualquier dato concreto se verifica en
> https://developers.binance.com/docs/ antes de usarlo en real.** Nunca inventes
> un endpoint o parámetro.

## Índice
1. Spot · 2. Futuros · 3. Filtros de símbolo · 4. Comisiones · 5. API REST ·
6. Autenticación · 7. Rate limits · 8. WebSockets · 9. Ciclo de vida de órdenes ·
10. Entornos de prueba

## 1. Spot
- Balances: `free` y `locked` por activo (`GET /api/v3/account`, firmado).
- Símbolos y reglas: `GET /api/v3/exchangeInfo` (status TRADING, filtros, tipos de orden permitidos `orderTypes`, `ocoAllowed`/`otoAllowed`, etc.).
- Tipos de orden: `LIMIT`, `MARKET` (por `quantity` o `quoteOrderQty`), `STOP_LOSS`, `STOP_LOSS_LIMIT`, `TAKE_PROFIT`, `TAKE_PROFIT_LIMIT`, `LIMIT_MAKER` (post-only: se rechaza si cruzaría).
- `timeInForce`: GTC, IOC, FOK.
- Listas de órdenes (OCO/OTO/OTOCO): existen, pero los endpoints han cambiado entre versiones (`/api/v3/orderList/oco` sustituyó al antiguo `/api/v3/order/oco`) → **verificar documentación actual**.
- Endpoint de prueba: `POST /api/v3/order/test` valida sin ejecutar.

## 2. Futuros
- **USDⓈ-M** (`https://fapi.binance.com`, margen en USDT/USDC, contratos lineales) y **COIN-M** (`https://dapi.binance.com`, margen en la cripto, contratos inversos con tamaño de contrato en USD).
- **Apalancamiento** por símbolo (`POST /fapi/v1/leverage`), máximo según brackets de nocional (`GET /fapi/v1/leverageBracket`).
- **Margen aislado vs cruzado** (`POST /fapi/v1/marginType`). Aislado limita la pérdida al margen de esa posición; cruzado usa todo el balance de la cuenta de futuros.
- **Margen de mantenimiento**: tasa (mmr) por bracket; la liquidación ocurre cuando el margen cae por debajo. La fórmula exacta incluye el mmr y una cantidad de mantenimiento; el script da una aproximación → contrastar con `liquidationPrice` de `positionRisk`.
- **Mark price** (precio justo para PnL no realizado y liquidaciones) vs **index price** (media de spot en varios exchanges) vs **last price**. Las liquidaciones usan mark price. `GET /fapi/v1/premiumIndex`.
- **Funding rate**: pago periódico entre largos y cortos (habitualmente cada 8 h; algunos símbolos tienen otro intervalo → `GET /fapi/v1/fundingInfo`). Positivo: largos pagan a cortos. Histórico: `GET /fapi/v1/fundingRate`.
- **Open interest**: `GET /fapi/v1/openInterest`; histórico agregado `GET /futures/data/openInterestHist` (periodos 5m…1d, ventana limitada a ~30 días).
- **reduceOnly**: la orden solo puede reducir la posición (usar en stops/targets).
- **Position mode**: one-way (una posición neta por símbolo) vs hedge (LONG y SHORT simultáneos, con `positionSide`). `GET/POST /fapi/v1/positionSide/dual`.
- Tipos de orden futuros: LIMIT, MARKET, STOP, STOP_MARKET, TAKE_PROFIT, TAKE_PROFIT_MARKET, TRAILING_STOP_MARKET; `workingType` MARK_PRICE / CONTRACT_PRICE; `priceProtect`. Binance ha ido moviendo órdenes condicionales a endpoints específicos ("algo orders") → **verificar documentación actual** antes de usar stops en futuros.

## 3. Filtros de símbolo (exchangeInfo → `filters`)
| Filtro | Campos | Regla |
|---|---|---|
| PRICE_FILTER | minPrice, maxPrice, tickSize | precio múltiplo de tickSize |
| LOT_SIZE | minQty, maxQty, stepSize | cantidad múltiplo de stepSize |
| MARKET_LOT_SIZE | igual | límites para órdenes MARKET |
| NOTIONAL (spot) | minNotional, maxNotional, applyMinToMarket | precio × cantidad ≥ minNotional |
| MIN_NOTIONAL | minNotional (spot antiguo) / notional (futuros) | idem |
| PERCENT_PRICE_BY_SIDE / PERCENT_PRICE | multiplicadores | el precio no puede alejarse demasiado del promedio |
| MAX_NUM_ORDERS, MAX_NUM_ALGO_ORDERS | | límites de órdenes abiertas |

**Siempre** leer los filtros reales del símbolo; no asumir valores típicos. `risk_check.py --exchange-info` los lee de un JSON descargado con `binance_data.py exchange-info`.

## 4. Comisiones
- Spot: tarifa base histórica 0,10% maker/taker (descuento pagando con BNB); varía por nivel VIP. Comisiones reales de la cuenta: `GET /api/v3/account` (`commissionRates`) o `GET /api/v3/account/commission`.
- USDⓈ-M: tarifa base aproximada 0,02% maker / 0,05% taker; `GET /fapi/v1/commissionRate`.
- **No asumir**: consultar la cuenta del usuario o la web oficial. En backtests, ser conservador (usar taker si hay duda).

## 5. API REST — endpoints públicos frecuentes
| Dato | Spot | USDⓈ-M |
|---|---|---|
| Ping / hora | `/api/v3/ping`, `/api/v3/time` | `/fapi/v1/ping`, `/fapi/v1/time` |
| Velas | `/api/v3/klines` (máx 1000) | `/fapi/v1/klines` (máx 1500) |
| Trades | `/api/v3/trades`, `/api/v3/aggTrades` | `/fapi/v1/trades`, `/fapi/v1/aggTrades` |
| Libro | `/api/v3/depth` | `/fapi/v1/depth` |
| Mejor bid/ask | `/api/v3/ticker/bookTicker` | `/fapi/v1/ticker/bookTicker` |
| 24h | `/api/v3/ticker/24hr` | `/fapi/v1/ticker/24hr` |
| Mark/funding | — | `/fapi/v1/premiumIndex`, `/fapi/v1/fundingRate` |
| OI | — | `/fapi/v1/openInterest`, `/futures/data/openInterestHist` |

Formato kline: `[openTime, open, high, low, close, volume, closeTime, quoteVolume, trades, takerBuyBase, takerBuyQuote, ignore]`. La última vela puede estar abierta → descartar si `closeTime >= ahora`.

Datos históricos masivos: https://data.binance.vision (ficheros diarios/mensuales de klines, aggTrades, trades) — preferible a paginar REST para años de datos.

## 6. Autenticación
- Cabecera `X-MBX-APIKEY`.
- Endpoints SIGNED: `timestamp` (ms) + `recvWindow` opcional (≤ 60000; usar 5000) + `signature` = HMAC-SHA256(secret, query string completa). Binance también admite claves Ed25519 y RSA (recomendadas actualmente para nuevas claves) → verificar el método de firma configurado.
- Errores típicos: `-1021` timestamp fuera de recvWindow (sincronizar reloj con `/api/v3/time`), `-1022` firma inválida, `-2010` orden rechazada (fondos/filtros), `-1013` filtro incumplido, `-2011` cancelación de orden desconocida.
- Permisos de la clave: solo lectura para análisis; trading sin retirada; restricción por IP siempre que sea posible.

## 7. Rate limits
- Límites por peso (REQUEST_WEIGHT por minuto por IP), por número de órdenes (ORDERS por 10 s y por día por cuenta) y RAW_REQUESTS. Valores actuales en `exchangeInfo.rateLimits`.
- Cabeceras de respuesta: `X-MBX-USED-WEIGHT-1M`, `X-MBX-ORDER-COUNT-10S`, etc.
- HTTP 429 → reducir y respetar `Retry-After`. HTTP 418 → IP baneada temporalmente: parar todo.
- Preferir WebSockets para datos continuos en vez de sondear REST.

## 8. WebSockets
- Mercado spot: `wss://stream.binance.com:9443/ws/<stream>` o combinados `/stream?streams=a/b`. Futuros: `wss://fstream.binance.com`.
- Streams: `<symbol>@kline_<tf>`, `@aggTrade`, `@trade`, `@bookTicker`, `@depth<levels>` / `@depth@100ms`, futuros `@markPrice`, `@forceOrder` (liquidaciones).
- Conexiones con vida limitada (~24 h) y ping/pong: implementar reconexión con backoff y **resincronizar estado por REST** tras reconectar.
- Libro local: snapshot REST + diffs del stream respetando `U`/`u`/`lastUpdateId` (procedimiento documentado; si hay hueco → re-snapshot).
- User data stream (órdenes, ejecuciones, balances): históricamente con `listenKey` (`POST /api/v3/userDataStream`) y keepalive; Binance está migrando a suscripción vía WebSocket API → **verificar documentación actual**. Eventos: `executionReport` (spot), `outboundAccountPosition`, `ORDER_TRADE_UPDATE` y `ACCOUNT_UPDATE` (futuros).

## 9. Ciclo de vida de órdenes
Estados Binance: NEW, PARTIALLY_FILLED, FILLED, CANCELED, PENDING_CANCEL (no usado normalmente), REJECTED, EXPIRED, EXPIRED_IN_MATCH (prevención de self-trade).
Mapeo a la máquina de estados interna en `risk-execution.md`.
- Usar `newClientOrderId` propio para idempotencia y para consultar/cancelar sin depender del orderId.
- Tras timeout de red al enviar: **no reenviar a ciegas** → consultar por clientOrderId; si no existe, entonces reenviar.

## 10. Entornos de prueba
- Spot testnet: `https://testnet.binance.vision` (claves propias del testnet).
- Futuros testnet: `https://testnet.binancefuture.com` (verificar URL vigente; Binance ha ofrecido también "demo trading").
- El testnet no replica liquidez ni slippage reales: valida infraestructura, no rentabilidad.
