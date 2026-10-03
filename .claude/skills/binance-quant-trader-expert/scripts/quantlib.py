"""Librería común (solo stdlib): carga de velas, indicadores, régimen y métricas.

Todas las funciones de indicadores devuelven listas alineadas con la entrada,
con None donde aún no hay datos suficientes. Ningún indicador en el índice i
usa datos posteriores a i (sin look-ahead).
"""
import csv
import math
from statistics import median

INTERVAL_MS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000,
    "1h": 3_600_000, "2h": 7_200_000, "4h": 14_400_000, "6h": 21_600_000,
    "8h": 28_800_000, "12h": 43_200_000, "1d": 86_400_000,
}


def bars_per_year(tf):
    return 365 * 86_400_000 / INTERVAL_MS[tf]


# ---------------------------------------------------------------- datos
def load_candles(path):
    """CSV con columnas timestamp(ms), open, high, low, close, volume [, quote_volume, ...]."""
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            c = {
                "ts": int(float(r["timestamp"])),
                "open": float(r["open"]), "high": float(r["high"]),
                "low": float(r["low"]), "close": float(r["close"]),
                "volume": float(r.get("volume") or 0),
            }
            if r.get("quote_volume"):
                c["quote_volume"] = float(r["quote_volume"])
            for k in ("symbol", "timeframe", "source"):
                if r.get(k):
                    c[k] = r[k]
            out.append(c)
    out.sort(key=lambda c: c["ts"])
    return out


def quality_report(candles, tf):
    """Detecta velas faltantes, duplicadas, desordenadas, OHLC inválido y outliers."""
    step = INTERVAL_MS.get(tf)
    issues = {"missing": [], "duplicates": [], "non_monotonic": [], "invalid_ohlc": [],
              "non_positive": [], "outliers": [], "misaligned": []}
    seen = set()
    for i, c in enumerate(candles):
        if c["ts"] in seen:
            issues["duplicates"].append(c["ts"])
        seen.add(c["ts"])
        if min(c["open"], c["high"], c["low"], c["close"]) <= 0 or c["volume"] < 0:
            issues["non_positive"].append(c["ts"])
        if c["high"] < max(c["open"], c["close"]) or c["low"] > min(c["open"], c["close"]) or c["high"] < c["low"]:
            issues["invalid_ohlc"].append(c["ts"])
        if step and c["ts"] % step != 0 and tf != "1w":
            issues["misaligned"].append(c["ts"])
        if i:
            d = c["ts"] - candles[i - 1]["ts"]
            if d < 0:
                issues["non_monotonic"].append(c["ts"])
            elif step and d > step:
                issues["missing"].extend(range(candles[i - 1]["ts"] + step, c["ts"], step))
    rets = [math.log(candles[i]["close"] / candles[i - 1]["close"])
            for i in range(1, len(candles)) if candles[i - 1]["close"] > 0 and candles[i]["close"] > 0]
    if len(rets) > 20:
        med = median(rets)
        mad = median(abs(r - med) for r in rets) or 1e-12
        for i, r in enumerate(rets, start=1):
            if abs(r - med) / (1.4826 * mad) > 12:
                issues["outliers"].append(candles[i]["ts"])
    return issues


# ---------------------------------------------------------------- indicadores
def sma(x, n):
    out, s = [None] * len(x), 0.0
    for i, v in enumerate(x):
        s += v
        if i >= n:
            s -= x[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def ema(x, n):
    out = [None] * len(x)
    if len(x) < n:
        return out
    k = 2 / (n + 1)
    prev = sum(x[:n]) / n
    out[n - 1] = prev
    for i in range(n, len(x)):
        prev = x[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def rolling_std(x, n):
    out = [None] * len(x)
    for i in range(n - 1, len(x)):
        w = x[i - n + 1:i + 1]
        m = sum(w) / n
        out[i] = math.sqrt(sum((v - m) ** 2 for v in w) / (n - 1)) if n > 1 else 0.0
    return out


def wilder(x, n):
    """Media de Wilder (RMA) sobre una serie que puede empezar con None."""
    out = [None] * len(x)
    vals = [(i, v) for i, v in enumerate(x) if v is not None]
    if len(vals) < n:
        return out
    start = vals[n - 1][0]
    prev = sum(v for _, v in vals[:n]) / n
    out[start] = prev
    for i in range(start + 1, len(x)):
        if x[i] is None:
            continue
        prev = (prev * (n - 1) + x[i]) / n
        out[i] = prev
    return out


def true_range(c):
    tr = [c[0]["high"] - c[0]["low"]]
    for i in range(1, len(c)):
        pc = c[i - 1]["close"]
        tr.append(max(c[i]["high"] - c[i]["low"], abs(c[i]["high"] - pc), abs(c[i]["low"] - pc)))
    return tr


def atr(c, n=14):
    return wilder(true_range(c), n)


def rsi(close, n=14):
    gains, losses = [None], [None]
    for i in range(1, len(close)):
        d = close[i] - close[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    ag, al = wilder(gains, n), wilder(losses, n)
    out = [None] * len(close)
    for i in range(len(close)):
        if ag[i] is not None and al[i] is not None:
            out[i] = 100.0 if al[i] == 0 else 100 - 100 / (1 + ag[i] / al[i])
    return out


def adx(c, n=14):
    pdm, ndm = [None], [None]
    for i in range(1, len(c)):
        up = c[i]["high"] - c[i - 1]["high"]
        dn = c[i - 1]["low"] - c[i]["low"]
        pdm.append(up if up > dn and up > 0 else 0.0)
        ndm.append(dn if dn > up and dn > 0 else 0.0)
    tr = [None] + true_range(c)[1:]
    atr_, sp, sn = wilder(tr, n), wilder(pdm, n), wilder(ndm, n)
    dx = [None] * len(c)
    for i in range(len(c)):
        if atr_[i]:
            pdi, ndi = 100 * sp[i] / atr_[i], 100 * sn[i] / atr_[i]
            dx[i] = 0.0 if pdi + ndi == 0 else 100 * abs(pdi - ndi) / (pdi + ndi)
    return wilder(dx, n)


def bollinger_width(close, n=20, k=2.0):
    m, s = sma(close, n), rolling_std(close, n)
    return [None if m[i] is None else (2 * k * s[i]) / m[i] for i in range(len(close))]


def donchian(c, n=20):
    """Máximo/mínimo de las n velas ANTERIORES (excluye la actual)."""
    hi, lo = [None] * len(c), [None] * len(c)
    for i in range(n, len(c)):
        w = c[i - n:i]
        hi[i] = max(x["high"] for x in w)
        lo[i] = min(x["low"] for x in w)
    return hi, lo


def zscore(x, n=20):
    m, s = sma(x, n), rolling_std(x, n)
    return [None if m[i] is None or not s[i] else (x[i] - m[i]) / s[i] for i in range(len(x))]


def log_returns(close):
    return [None] + [math.log(close[i] / close[i - 1]) for i in range(1, len(close))]


def realized_vol(close, n, tf):
    lr = log_returns(close)
    out = [None] * len(close)
    ann = math.sqrt(bars_per_year(tf))
    for i in range(n, len(close)):
        w = lr[i - n + 1:i + 1]
        m = sum(w) / n
        out[i] = math.sqrt(sum((v - m) ** 2 for v in w) / (n - 1)) * ann
    return out


def pct_rank(x, n):
    """Percentil (0-1) del valor actual dentro de las últimas n observaciones."""
    out = [None] * len(x)
    for i in range(len(x)):
        if x[i] is None:
            continue
        w = [v for v in x[max(0, i - n + 1):i + 1] if v is not None]
        if len(w) >= min(n, 50):
            out[i] = sum(1 for v in w if v <= x[i]) / len(w)
    return out


def features(c, tf):
    close = [x["close"] for x in c]
    vol = [x["volume"] for x in c]
    f = {
        "close": close,
        "ema20": ema(close, 20), "ema50": ema(close, 50), "ema200": ema(close, 200),
        "atr": atr(c, 14), "rsi": rsi(close, 14), "adx": adx(c, 14),
        "bbw": bollinger_width(close, 20), "z20": zscore(close, 20),
        "vol_z": zscore(vol, 20), "rv": realized_vol(close, 20, tf),
    }
    f["don_hi"], f["don_lo"] = donchian(c, 20)
    f["atr_pct"] = [None if a is None else a / close[i] for i, a in enumerate(f["atr"])]
    f["atr_pct_rank"] = pct_rank(f["atr_pct"], 200)
    f["bbw_rank"] = pct_rank(f["bbw"], 200)
    f["roc20"] = [None] * 20 + [close[i] / close[i - 20] - 1 for i in range(20, len(close))]
    return f


# ---------------------------------------------------------------- régimen
REGIMES = ["CAPITULATION", "BREAKOUT", "TREND_UP", "TREND_DOWN", "HIGH_VOLATILITY",
           "RANGE", "LOW_VOLATILITY", "EXPANSION", "UNKNOWN"]


def regime_at(c, f, i):
    """Clasificador heurístico y transparente. Devuelve (régimen, motivo)."""
    need = ("ema50", "ema200", "adx", "atr", "atr_pct_rank", "bbw_rank", "vol_z")
    if any(f[k][i] is None for k in need):
        return "UNKNOWN", "datos insuficientes para los indicadores"
    x, close = c[i], f["close"][i]
    body = x["close"] - x["open"]
    if body < -3 * f["atr"][i] and f["vol_z"][i] > 3:
        return "CAPITULATION", "vela bajista > 3 ATR con volumen z > 3"
    if f["don_hi"][i] and close > f["don_hi"][i] and f["vol_z"][i] > 1.5:
        return "BREAKOUT", "cierre sobre Donchian-20 con volumen z > 1.5"
    if f["don_lo"][i] and close < f["don_lo"][i] and f["vol_z"][i] > 1.5:
        return "BREAKOUT", "cierre bajo Donchian-20 con volumen z > 1.5"
    adx_v, e50, e200 = f["adx"][i], f["ema50"][i], f["ema200"][i]
    if adx_v > 25 and close > e50 > e200:
        return "TREND_UP", f"ADX {adx_v:.0f} > 25, precio > EMA50 > EMA200"
    if adx_v > 25 and close < e50 < e200:
        return "TREND_DOWN", f"ADX {adx_v:.0f} > 25, precio < EMA50 < EMA200"
    if f["atr_pct_rank"][i] > 0.9:
        return "HIGH_VOLATILITY", f"ATR% en percentil {f['atr_pct_rank'][i]:.0%} (200 velas)"
    if adx_v < 20 and f["bbw_rank"][i] < 0.5:
        return "RANGE", f"ADX {adx_v:.0f} < 20 y Bollinger estrecho"
    if f["atr_pct_rank"][i] < 0.1:
        return "LOW_VOLATILITY", f"ATR% en percentil {f['atr_pct_rank'][i]:.0%}"
    if f["bbw_rank"][i] > 0.8 and i and f["adx"][i - 1] is not None and adx_v > f["adx"][i - 1]:
        return "EXPANSION", "Bollinger ancho (p>80) y ADX subiendo"
    return "UNKNOWN", "ninguna regla con evidencia suficiente"


# ---------------------------------------------------------------- métricas
def max_drawdown(equity):
    peak, mdd = equity[0], 0.0
    for e in equity:
        peak = max(peak, e)
        if peak > 0:
            mdd = max(mdd, (peak - e) / peak)
    return mdd


def trade_metrics(pnls, rs=None):
    n = len(pnls)
    if n == 0:
        return {"trades": 0}
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gp, gl = sum(wins), -sum(losses)
    m = {
        "trades": n, "win_rate": len(wins) / n,
        "avg_win": gp / len(wins) if wins else 0.0,
        "avg_loss": -gl / len(losses) if losses else 0.0,
        "profit_factor": gp / gl if gl > 0 else float("inf"),
        "expectancy": sum(pnls) / n, "net_pnl": sum(pnls),
    }
    if rs:
        m["expectancy_r"] = sum(rs) / len(rs)
        # Concentración: ¿cuánto del beneficio viene del top 10% de trades?
        top = sorted(pnls, reverse=True)[:max(1, n // 10)]
        m["top10pct_share"] = sum(top) / sum(pnls) if sum(pnls) > 0 else None
    streak = mx = 0
    for p in pnls:
        streak = streak + 1 if p <= 0 else 0
        mx = max(mx, streak)
    m["max_losing_streak"] = mx
    return m


def equity_metrics(equity, tf):
    """Sharpe/Sortino/Calmar sobre la curva de equity por vela (rf = 0)."""
    rets = [equity[i] / equity[i - 1] - 1 for i in range(1, len(equity)) if equity[i - 1] > 0]
    if len(rets) < 2:
        return {}
    bpy = bars_per_year(tf)
    mean = sum(rets) / len(rets)
    sd = math.sqrt(sum((r - mean) ** 2 for r in rets) / (len(rets) - 1))
    dd = math.sqrt(sum(min(r, 0) ** 2 for r in rets) / len(rets))
    years = len(rets) / bpy
    cagr = (equity[-1] / equity[0]) ** (1 / years) - 1 if years > 0 and equity[-1] > 0 else -1.0
    mdd = max_drawdown(equity)
    return {
        "total_return": equity[-1] / equity[0] - 1, "cagr": cagr, "max_drawdown": mdd,
        "sharpe": mean / sd * math.sqrt(bpy) if sd else 0.0,
        "sortino": mean / dd * math.sqrt(bpy) if dd else 0.0,
        "calmar": cagr / mdd if mdd else 0.0,
    }


def fmt_metrics(m):
    def f(k, v):
        if v is None:
            return f"{k}=-"
        if k in ("win_rate", "total_return", "cagr", "max_drawdown", "top10pct_share"):
            return f"{k}={v:.1%}"
        if isinstance(v, float):
            return f"{k}={'inf' if v == float('inf') else f'{v:.3f}'}"
        return f"{k}={v}"
    return " | ".join(f(k, v) for k, v in m.items())
