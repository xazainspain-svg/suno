# Gestión de riesgo

## Fórmula base

```
Riesgo en dinero  = Balance × % riesgo
Tamaño posición   = Riesgo en dinero / (Distancia al stop × valor por unidad)
R:R               = |Target − Entrada| / |Entrada − Stop|
```

El apalancamiento **no cambia** el riesgo de la operación si el tamaño se
calcula así: solo cambia el margen que se bloquea. Lo que sí cambia es la
distancia a la liquidación. Explícaselo al usuario cuando confunda
"apalancamiento" con "riesgo".

Usa siempre `scripts/position_size.py` para los números.

## Reglas por defecto (si el usuario no define las suyas)

| Regla                          | Valor por defecto |
|--------------------------------|-------------------|
| Riesgo por operación           | 1% (máx. 2%)      |
| R:R mínimo                     | 1:2               |
| Pérdida máxima diaria          | 3% → dejar de operar ese día |
| Pérdida máxima semanal         | 6% → pausa y revisión del diario |
| Operaciones abiertas correlacionadas | riesgo total ≤ 3% |
| Tras 3 pérdidas seguidas       | pausa obligatoria, reducir tamaño a la mitad |

**Correlación:** largo en BTC + ETH + SOL es casi una sola operación con el
triple de riesgo. Lo mismo EURUSD largo + GBPUSD largo, o NASDAQ + NVDA + AAPL.

## Esperanza matemática

```
Expectancy (R) = WinRate × R medio ganador − (1 − WinRate) × R medio perdedor
```

| Win rate | R:R necesario para break-even |
|----------|-------------------------------|
| 30%      | 1 : 2,33                      |
| 40%      | 1 : 1,5                       |
| 50%      | 1 : 1                         |
| 60%      | 1 : 0,67                      |

Úsalo para mostrar que no hace falta acertar mucho si el R:R es bueno.

## Drawdown y recuperación

| Pérdida | Ganancia necesaria para recuperar |
|---------|-----------------------------------|
| 10%     | 11%                               |
| 20%     | 25%                               |
| 30%     | 43%                               |
| 50%     | 100%                              |
| 75%     | 300%                              |

Arriesgando 1%: 10 pérdidas seguidas ≈ −9,6%. Arriesgando 5%: ≈ −40%.

## Colocación del stop

- En el punto donde la idea queda **invalidada** (bajo el mínimo del
  retroceso, fuera del rango, al otro lado de la zona), más un margen de
  0,5–1 ATR.
- Nunca un stop "por dinero" (p. ej. "pongo 50 € de stop") ignorando la
  estructura: primero el stop técnico, luego el tamaño se adapta.
- Si el stop técnico queda tan lejos que el tamaño resultante es ridículo,
  la operación no vale la pena en esa temporalidad → bajar de temporalidad o
  no operar.

## Gestión de la operación

- **Parciales:** p. ej. 50% en TP1 (1R–1,5R), mover stop a break-even, dejar
  correr el resto a TP2 o con trailing (bajo HL / EMA20 / ATR).
- **Break-even:** no moverlo demasiado pronto (antes de 1R) o el ruido te saca.
- **Nunca** ampliar el stop en contra ni promediar perdedoras sin plan previo.

## Apalancamiento (cripto/futuros)

Liquidación aproximada en margen aislado (sin comisiones ni margen de
mantenimiento):
- Largo:  Entrada × (1 − 1/apalancamiento)
- Corto:  Entrada × (1 + 1/apalancamiento)

Regla: la liquidación debe estar **mucho más lejos** que el stop (al menos
2× la distancia al stop). Si no, avisar fuerte.

## Señales de sobreoperación

- Más operaciones de lo normal tras una pérdida.
- Subir tamaño tras pérdidas para "recuperar".
- Operar fuera del horario/plan habitual.
- Cambiar de setup cada día.

Respuesta: pausa, revisar diario (`journal.py stats --by emotion`), volver a
riesgo mínimo.
