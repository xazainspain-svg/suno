# Análisis técnico — método

## Índice
1. Análisis top-down
2. Estructura de mercado
3. Niveles y zonas
4. Velas y patrones
5. Indicadores (uso correcto)
6. Tipos de setup
7. Checklist antes de dar una entrada
8. Cómo leer una captura de gráfico

---

## 1. Análisis top-down

| Estilo        | Contexto (tendencia/zonas) | Ejecución (gatillo) |
|---------------|----------------------------|---------------------|
| Scalping      | 1H / 15m                   | 5m / 1m             |
| Intradía      | 4H / 1H                    | 15m / 5m            |
| Swing         | Semanal / Diario           | 4H / 1H             |
| Posicional    | Mensual / Semanal          | Diario              |

Regla: opera a favor de la temporalidad superior salvo que haya un cambio de
estructura claro en ella. Una señal en 5m contra la tendencia diaria es un
trade de baja probabilidad.

## 2. Estructura de mercado

- **Tendencia alcista:** máximos más altos (HH) y mínimos más altos (HL).
- **Tendencia bajista:** máximos más bajos (LH) y mínimos más bajos (LL).
- **Rango:** precio rebotando entre un techo y un suelo; opera los extremos o
  espera la ruptura, nunca el centro.
- **BOS (Break of Structure):** el precio rompe el último máximo (en
  alcista) o mínimo (en bajista) → continuación.
- **CHoCH (Change of Character):** primera ruptura en contra de la tendencia
  → posible giro; necesita confirmación (retest, nuevo mínimo/máximo).
- **Barrido de liquidez:** mecha que supera un máximo/mínimo obvio y vuelve
  dentro rápidamente. Suele preceder movimientos en sentido contrario.

## 3. Niveles y zonas

Prioridad de niveles (de más a menos fuerte):
1. Máximos/mínimos de temporalidades altas (semanal, diario, mensual).
2. Zonas donde el precio reaccionó varias veces (soporte que se convierte en
   resistencia y viceversa — *flip*).
3. Zonas de oferta/demanda: origen de un movimiento impulsivo fuerte.
4. Máximo/mínimo del día anterior, apertura semanal/diaria.
5. Números redondos (100.000 en BTC, 1.1000 en EURUSD, 5000 en S&P).
6. VWAP y medias de 200 en temporalidades altas.
7. Fibonacci 0.5–0.618 (zona de retroceso) y extensiones 1.272/1.618 para
   objetivos — úsalo como confluencia, no como señal aislada.

Los niveles son **zonas**, no líneas exactas. Marca un rango y pon el stop
fuera de la zona, no justo en el borde.

## 4. Velas y patrones

Velas de gatillo útiles (siempre en un nivel, nunca en mitad de la nada):
- Envolvente alcista/bajista.
- Pin bar / martillo / estrella fugaz (mecha ≥ 2× cuerpo).
- Inside bar en nivel (compresión antes de ruptura).
- Cierre fuerte fuera de un rango (cuerpo grande, mecha pequeña).

Patrones chartistas: doble techo/suelo, HCH / HCH invertido, triángulos,
banderas y banderines, cuñas, canales. Objetivo medido = altura del patrón
proyectada desde la ruptura. Exigir cierre de vela fuera del patrón, idealmente
con volumen.

## 5. Indicadores (uso correcto)

| Indicador       | Para qué sirve                                  | Error típico |
|-----------------|-------------------------------------------------|--------------|
| EMA 20/50/200   | Tendencia y soporte dinámico; precio > EMA200 = sesgo alcista | Comprar cada cruce |
| RSI (14)        | Momento; divergencias en niveles clave          | Vender solo porque RSI > 70 en tendencia fuerte |
| MACD            | Cambio de momento, divergencias                 | Usarlo junto a RSI (redundante) |
| VWAP            | Precio "justo" intradía, acciones e índices     | Usarlo en swing |
| ATR (14)        | Volatilidad → distancia de stop y objetivos     | Ignorarlo y poner stops demasiado ajustados |
| Volumen         | Confirmar rupturas y agotamiento                | En forex spot el volumen es de tick, no real |
| Bandas Bollinger| Compresión (squeeze) antes de expansión         | Vender cada toque de banda superior |

Regla: máximo 1 indicador de tendencia + 1 de momento + volumen/ATR.

**Divergencia:** precio hace nuevo máximo y el RSI no → debilidad. Solo es
relevante en un nivel clave y con confirmación de estructura.

**Stop con ATR:** stop técnico + margen de 0,5–1 × ATR para no salir por ruido.

## 6. Tipos de setup

1. **Pullback en tendencia:** tendencia clara en TF superior → retroceso a
   zona (EMA50, soporte flip, 0.5–0.618) → vela gatillo → entrada.
   Stop bajo el mínimo del retroceso.
2. **Ruptura y retest:** rango/patrón bien definido → cierre fuera con
   volumen → retest del nivel roto → entrada. Stop dentro del rango.
3. **Reversión en nivel mayor:** precio llega a nivel semanal/diario +
   barrido de liquidez + divergencia + CHoCH en TF inferior. Menor
   probabilidad, mayor R:R. Tamaño reducido.
4. **Rango:** comprar suelo / vender techo con stop fuera del rango, objetivo
   el lado opuesto o el centro.

## 7. Checklist antes de dar una entrada

- [ ] ¿Tendencia de la TF superior identificada?
- [ ] ¿El precio está en un nivel relevante (no en mitad de la nada)?
- [ ] ¿Hay gatillo claro (vela/estructura) o solo una "sensación"?
- [ ] ¿Stop en un punto de invalidación lógico, no arbitrario?
- [ ] ¿R:R ≥ 1:2 hasta el siguiente nivel opuesto?
- [ ] ¿Noticias de alto impacto en las próximas horas?
- [ ] ¿Tamaño calculado con el script de riesgo?

Si fallan 2 o más → "no operar" o "esperar a X".

## 8. Cómo leer una captura de gráfico

1. Identifica: activo, exchange/bróker, temporalidad, precio actual, fecha si se
   ve, indicadores y dibujos visibles.
2. Si falta algo crítico (temporalidad, eje de precios ilegible), pregunta o
   dilo explícitamente.
3. Describe la estructura y los niveles que ves **con los precios del eje**.
4. Recuerda que una captura es una foto: si es antigua, el precio actual puede
   ser otro → ofrece verificar con datos en vivo.
