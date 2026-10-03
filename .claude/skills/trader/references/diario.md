# Diario de trading

## Por qué

Sin registro no hay mejora: el diario convierte sensaciones ("este setup me
funciona") en datos (win rate, R medio, expectancy por setup).

## Archivo

CSV (por defecto `trading_journal.csv` en el directorio actual; cambiar con
`--file RUTA`). Columnas:

| Campo     | Descripción |
|-----------|-------------|
| id        | Autonumérico |
| date      | Fecha/hora de entrada (ISO). Por defecto, ahora |
| symbol    | BTCUSDT, EURUSD, AAPL, ES... |
| market    | crypto / forex / stocks / futures |
| side      | long / short |
| entry     | Precio de entrada |
| stop      | Stop loss inicial (necesario para calcular R) |
| target    | Objetivo planificado (opcional) |
| exit      | Precio de salida (vacío si sigue abierta) |
| size      | Cantidad (unidades, lotes × tamaño de contrato, contratos × valor punto) |
| fees      | Comisiones totales |
| pnl       | P&L en dinero. Se calcula solo si no se da: (exit−entry)×size×dirección − fees |
| r         | Resultado en R = (exit−entry)×dirección / |entry−stop| |
| setup     | Nombre del setup ("pullback EMA50", "ruptura rango"...) |
| timeframe | Temporalidad de ejecución |
| emotion   | Estado emocional (tranquilo, FOMO, revancha, miedo, aburrido...) |
| followed_plan | yes / no |
| notes     | Texto libre: qué salió bien/mal, lección |

Para forex/futuros, `size` debe ir en unidades de valor (p. ej. 0,5 lotes
EURUSD = 50000) o pasar `--pnl` directamente desde la plataforma.

## Comandos

```bash
python3 scripts/journal.py add ...            # nueva operación (abierta o cerrada)
python3 scripts/journal.py close --id 7 --exit 1.0912 [--pnl 84.5] [--fees 2]
python3 scripts/journal.py list [--last N] [--open]
python3 scripts/journal.py stats [--by setup|symbol|emotion|side|market|timeframe|followed_plan] [--since 2026-09-01]
python3 scripts/journal.py export-md > resumen.md
```

## Cómo registrar con el usuario

- Si el usuario cuenta una operación de palabra, extrae los campos y
  pregunta solo por lo imprescindible que falte (entrada, salida, stop,
  tamaño o P&L). El resto, opcional.
- Pregunta siempre por la emoción y si siguió el plan: es lo más valioso a
  largo plazo y lo que más se olvida.

## Cómo interpretar las estadísticas

- **Muestra:** < 30 operaciones = conclusiones provisionales; dilo.
- **Expectancy (R) > 0** → sistema con ventaja. Prioridad #1.
- **Profit factor:** > 1,5 bueno, > 2 muy bueno, < 1 pierde dinero.
- **Por setup:** recomendar eliminar o reducir tamaño en setups con expectancy
  negativa tras ≥ 15–20 operaciones.
- **Por emoción / followed_plan = no:** suele ser donde se concentran las
  pérdidas. Señalarlo con números ("las 9 operaciones con FOMO suman −6,2R").
- **Racha perdedora máxima y drawdown máximo:** para ajustar el % de riesgo
  a lo que el usuario psicológicamente aguanta.
- Cerrar siempre con 1–3 acciones concretas para la próxima semana.

## Revisión semanal (plantilla)

```
Semana: ...
Operaciones: N · Win rate: x% · Resultado: +x R / +x €
Mejor operación y por qué:
Peor operación y por qué:
¿Respeté el riesgo? ¿Seguí el plan?
Patrón a eliminar:
Patrón a repetir:
Objetivo de proceso para la próxima semana:
```
