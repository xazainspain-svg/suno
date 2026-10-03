#!/usr/bin/env python3
"""EXECUTION + RECONCILIATION mínimos para Binance Spot (y lectura de Futuros USDⓈ-M).

SEGURIDAD
  - Claves SOLO por variables de entorno: BINANCE_API_KEY, BINANCE_API_SECRET (o un .env que cargues tú).
    Nunca se imprimen ni se escriben en logs.
  - BINANCE_ENV=testnet por defecto (https://testnet.binance.vision). Mainnet requiere BINANCE_ENV=mainnet.
  - Una orden REAL en mainnet requiere TODO esto a la vez:
        LIVE_TRADING=true  (variable de entorno, nunca la cambia el sistema)
        --authorize        (flag explícito en el comando)
        sin archivo FREEZE (lo crea reconcile ante discrepancias)
    Si falta algo, se usa /api/v3/order/test (valida la orden SIN ejecutarla).

  binance_client.py time
  binance_client.py account                       # balances no nulos
  binance_client.py open-orders [--symbol X]
  binance_client.py order --symbol ETHUSDT --side BUY --type LIMIT --qty 0.0025 --price 2450 [--authorize]
  binance_client.py status --symbol ETHUSDT --client-id ID
  binance_client.py cancel --symbol ETHUSDT --client-id ID [--authorize]
  binance_client.py reconcile --state local_state.json
  binance_client.py futures-positions             # solo lectura

Verifica siempre los endpoints y parámetros en la documentación oficial vigente
(https://developers.binance.com/docs/) antes de usar en mainnet.
"""
import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ENV = os.environ.get("BINANCE_ENV", "testnet").lower()
SPOT = {"testnet": "https://testnet.binance.vision", "mainnet": "https://api.binance.com"}[ENV]
FUT = {"testnet": "https://testnet.binancefuture.com", "mainnet": "https://fapi.binance.com"}[ENV]
FREEZE = os.environ.get("BINANCE_FREEZE_FILE", "FREEZE")
AUDIT = os.environ.get("BINANCE_AUDIT_LOG", "audit_log.jsonl")
_offset = 0


def audit(event, **kw):
    kw = {k: v for k, v in kw.items() if k not in ("signature", "api_key", "secret")}
    with open(AUDIT, "a") as f:
        f.write(json.dumps({"ts": int(time.time() * 1000), "env": ENV, "event": event, **kw}, default=str) + "\n")


def keys():
    k, s = os.environ.get("BINANCE_API_KEY"), os.environ.get("BINANCE_API_SECRET")
    if not k or not s:
        raise SystemExit("Faltan BINANCE_API_KEY / BINANCE_API_SECRET en el entorno (no se aceptan por argumento).")
    return k, s


def http(method, base, path, params=None, signed=False):
    global _offset
    params = dict(params or {})
    headers = {"User-Agent": "quant-exec/1.0"}
    if signed:
        k, s = keys()
        params["timestamp"] = int(time.time() * 1000) + _offset
        params.setdefault("recvWindow", 5000)
        qs = urllib.parse.urlencode(params)
        sig = hmac.new(s.encode(), qs.encode(), hashlib.sha256).hexdigest()
        qs += "&signature=" + sig
        headers["X-MBX-APIKEY"] = k
    else:
        qs = urllib.parse.urlencode(params)
    url = base + path + ("?" + qs if qs and method in ("GET", "DELETE") else "")
    data = qs.encode() if method in ("POST", "PUT") else None
    if data:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:400]
        audit("http_error", path=path, code=e.code, body=body)
        if e.code in (418, 429):
            raise SystemExit(f"RATE LIMIT ({e.code}). STOP NEW TRADES. {body}")
        raise SystemExit(f"HTTP {e.code} {path}: {body}")
    except urllib.error.URLError as e:
        audit("network_error", path=path, error=str(e))
        raise SystemExit(f"API/NETWORK FAILURE: {e}. STOP NEW TRADES.")


def sync_time():
    global _offset
    t0 = int(time.time() * 1000)
    srv = http("GET", SPOT, "/api/v3/time")["serverTime"]
    t1 = int(time.time() * 1000)
    _offset = srv - (t0 + t1) // 2
    return _offset


def cmd_time(a):
    off = sync_time()
    print(f"env={ENV} offset reloj local vs servidor: {off} ms" + ("  ⚠️ >1000 ms: sincroniza el reloj" if abs(off) > 1000 else ""))


def cmd_account(a):
    sync_time()
    acc = http("GET", SPOT, "/api/v3/account", signed=True)
    bal = [b for b in acc.get("balances", []) if float(b["free"]) or float(b["locked"])]
    print(json.dumps({"env": ENV, "canTrade": acc.get("canTrade"), "balances": bal,
                      "commissionRates": acc.get("commissionRates")}, indent=1))


def cmd_open_orders(a):
    sync_time()
    p = {"symbol": a.symbol} if a.symbol else {}
    print(json.dumps(http("GET", SPOT, "/api/v3/openOrders", p, signed=True), indent=1))


def live_allowed(a):
    checks = {
        "BINANCE_ENV=mainnet": ENV == "mainnet",
        "LIVE_TRADING=true": os.environ.get("LIVE_TRADING", "false").lower() == "true",
        "--authorize": bool(a.authorize),
        "sin FREEZE": not os.path.exists(FREEZE),
    }
    return all(checks.values()), checks


def cmd_order(a):
    if os.path.exists(FREEZE):
        raise SystemExit(f"FREEZE activo ({open(FREEZE).read().strip()}). No se envían órdenes nuevas.")
    sync_time()
    cid = a.client_id or f"q{uuid.uuid4().hex[:20]}"  # idempotencia: evita duplicados en reintentos
    p = {"symbol": a.symbol, "side": a.side, "type": a.type, "quantity": a.qty, "newClientOrderId": cid,
         "newOrderRespType": "FULL"}
    if a.type in ("LIMIT", "LIMIT_MAKER", "STOP_LOSS_LIMIT", "TAKE_PROFIT_LIMIT"):
        p["price"] = a.price
    if a.type == "LIMIT" or a.type in ("STOP_LOSS_LIMIT", "TAKE_PROFIT_LIMIT"):
        p["timeInForce"] = a.tif
    if a.stop_price:
        p["stopPrice"] = a.stop_price
    real = ENV == "testnet" or live_allowed(a)[0]
    path = "/api/v3/order" if real else "/api/v3/order/test"
    if ENV == "mainnet" and not real:
        ok, checks = live_allowed(a)
        print("LIVE bloqueado → orden de PRUEBA (no se ejecuta). Condiciones:", checks)
    audit("order_submit", path=path, params=p)
    res = http("POST", SPOT, path, p, signed=True)
    audit("order_response", client_id=cid, response=res)
    if path.endswith("/test"):
        print("Orden validada por Binance (test). No ejecutada.")
        return
    # Nunca asumir el fill: consultar estado real
    time.sleep(0.5)
    st = http("GET", SPOT, "/api/v3/order", {"symbol": a.symbol, "origClientOrderId": cid}, signed=True)
    audit("order_status", client_id=cid, status=st.get("status"), executedQty=st.get("executedQty"))
    print(json.dumps({"clientOrderId": cid, "status": st.get("status"), "executedQty": st.get("executedQty"),
                      "cummulativeQuoteQty": st.get("cummulativeQuoteQty"), "price": st.get("price")}, indent=1))


def cmd_status(a):
    sync_time()
    print(json.dumps(http("GET", SPOT, "/api/v3/order", {"symbol": a.symbol, "origClientOrderId": a.client_id}, signed=True), indent=1))


def cmd_cancel(a):
    sync_time()
    if ENV == "mainnet" and not a.authorize:
        raise SystemExit("Cancelar en mainnet requiere --authorize.")
    res = http("DELETE", SPOT, "/api/v3/order", {"symbol": a.symbol, "origClientOrderId": a.client_id}, signed=True)
    audit("order_cancel", client_id=a.client_id, response=res)
    print(json.dumps({"status": res.get("status"), "executedQty": res.get("executedQty")}, indent=1))


def cmd_reconcile(a):
    """Compara estado local (JSON) con Binance. Discrepancia => crea FREEZE."""
    local = json.load(open(a.state))
    sync_time()
    acc = http("GET", SPOT, "/api/v3/account", signed=True)
    remote_bal = {b["asset"]: float(b["free"]) + float(b["locked"]) for b in acc["balances"]}
    remote_orders = {o["clientOrderId"]: o for o in http("GET", SPOT, "/api/v3/openOrders", signed=True)}
    diffs = []
    tol = a.tolerance
    for asset, qty in local.get("balances", {}).items():
        r = remote_bal.get(asset, 0.0)
        if abs(r - qty) > max(tol, abs(qty) * 1e-6):
            diffs.append(f"balance {asset}: local {qty} vs binance {r}")
    for cid in local.get("open_orders", []):
        if cid not in remote_orders:
            diffs.append(f"orden {cid} abierta en local pero no en Binance (¿llenada/cancelada?)")
    for cid in remote_orders:
        if cid not in local.get("open_orders", []):
            diffs.append(f"orden {cid} abierta en Binance pero desconocida en local")
    audit("reconcile", diffs=diffs)
    if diffs:
        with open(FREEZE, "w") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} reconcile mismatch: {len(diffs)} diferencias\n")
        print("✗ DISCREPANCIA → FREEZE NEW ORDERS:")
        for d in diffs:
            print("  -", d)
        print(f"Revisa manualmente y borra '{FREEZE}' solo cuando el estado esté explicado.")
        sys.exit(4)
    print("✓ Estado local == Binance")


def cmd_futures_positions(a):
    sync_time()
    pos = http("GET", FUT, "/fapi/v2/positionRisk", signed=True)
    for p in pos:
        if float(p.get("positionAmt", 0)):
            print({k: p.get(k) for k in ("symbol", "positionAmt", "entryPrice", "markPrice", "liquidationPrice",
                                          "leverage", "marginType", "unRealizedProfit", "positionSide")})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["time", "account", "open-orders", "order", "status", "cancel", "reconcile", "futures-positions"])
    ap.add_argument("--symbol")
    ap.add_argument("--side", choices=["BUY", "SELL"])
    ap.add_argument("--type", default="LIMIT", choices=["LIMIT", "MARKET", "LIMIT_MAKER", "STOP_LOSS_LIMIT", "TAKE_PROFIT_LIMIT"])
    ap.add_argument("--qty")
    ap.add_argument("--price")
    ap.add_argument("--stop-price")
    ap.add_argument("--tif", default="GTC", choices=["GTC", "IOC", "FOK"])
    ap.add_argument("--client-id")
    ap.add_argument("--authorize", action="store_true")
    ap.add_argument("--state")
    ap.add_argument("--tolerance", type=float, default=1e-8)
    a = ap.parse_args()
    fn = {"time": cmd_time, "account": cmd_account, "open-orders": cmd_open_orders, "order": cmd_order,
          "status": cmd_status, "cancel": cmd_cancel, "reconcile": cmd_reconcile,
          "futures-positions": cmd_futures_positions}[a.cmd]
    fn(a)


if __name__ == "__main__":
    main()
