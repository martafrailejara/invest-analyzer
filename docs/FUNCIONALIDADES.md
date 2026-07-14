# invest-analyzer — Ficha completa de funcionalidades

Referencia de todos los módulos: qué hace cada uno, para qué sirve, cómo funciona por
dentro y qué significan las métricas y tecnicismos que muestra. La aplicación es
**descriptiva**: enseña datos, simulaciones y estadísticas sobre el pasado; las páginas
que emiten sugerencias (chequeo, fiscalidad) lo hacen como reglas mecánicas con
disclaimer explícito, nunca como asesoramiento profesional.

## Índice

1. [Arquitectura y capa de datos](#1-arquitectura-y-capa-de-datos)
2. [Mi cartera](#2-mi-cartera--cartera)
3. [Chequeo de cartera](#3-chequeo-de-cartera--chequeo)
4. [Metas financieras](#4-metas-financieras--metas)
5. [Backtester](#5-backtester--backtester)
6. [Simulador qué-pasaría-si](#6-simulador-qué-pasaría-si--simulador)
7. [Optimizador de cartera](#7-optimizador-de-cartera--optimizador)
8. [Análisis de riesgo](#8-análisis-de-riesgo--riesgo)
9. [Proyección Monte Carlo](#9-proyección-monte-carlo--montecarlo)
10. [Dividendos](#10-dividendos--dividendos)
11. [Detector de anomalías](#11-detector-de-anomalías--anomalias)
12. [Fiscalidad](#12-fiscalidad--fiscalidad)
13. [Análisis guardados](#13-análisis-guardados--guardados)
14. [Glosario rápido](#14-glosario-rápido)

---

## 1. Arquitectura y capa de datos

Tres capas: **datos** (`core/market_data.py`, `core/portfolio.py`), **motor de cálculo
compartido** (`core/engine.py`, `core/metrics.py`) y **módulos funcionales**
(`modules/*`) servidos por Flask (`app/*`, un blueprint por página).

### Precios de mercado (`core/market_data.py`)

- **Fuente:** yfinance (API no oficial de Yahoo Finance). Se descargan **precios de
  cierre ajustados** (`auto_adjust=True`): el precio corregido por splits y dividendos,
  que es el correcto para calcular retornos comparables en el tiempo.
- **Caché local:** cada ticker se guarda en `data/market/<ticker>.parquet` junto a un
  sidecar `<ticker>.meta.json` que registra el rango de fechas ya cubierto. Una petición
  dentro del rango cubierto se sirve de disco (milisegundos); si lo desborda, se descarga
  la unión de rangos y se reemplaza. La cobertura registrada nunca supera "hoy" (evita
  cachés estancadas) y un meta con cobertura futura se considera corrupto y se refresca.
- **Divisas:** la divisa de cada ticker se estima por su sufijo (`.DE`, `.MC`, `.PA`,
  `-EUR`… → EUR; sin sufijo o `-USD` → USD). Los precios en USD se convierten a EUR con
  el cruce `EURUSD=X` alineado por fecha (precio_EUR = precio_USD / tasa), con aviso
  visible. Así nunca se suman divisas distintas en una misma cartera.
- **Huecos:** los festivos/fines de semana de una bolsa frente a cripto (que cotiza a
  diario) se rellenan con el último precio conocido (*forward fill*) en el motor, y los
  días previos a que todos los activos tengan histórico se descartan **con aviso**.

### Cartera personal (`core/portfolio.py` + `core/isin_map.py`)

- **Entrada:** el export CSV de transacciones de Trade Republic, tal cual
  (`data/transacciones.csv`, fuera de git). Se filtran las filas de trading
  (`category=TRADING`, tipos `BUY`/`SELL`) y se descarta el ruido de caja (recargas,
  tarjeta, transferencias).
- **Posiciones por transacciones, no por foto:** las unidades y el coste se derivan
  acumulando compras y ventas. Al vender se usa **coste medio** para la vista de cartera
  (y **FIFO** en fiscalidad, que es el criterio legal).
- **ISIN → ticker:** Trade Republic identifica fondos por ISIN; yfinance usa tickers.
  El mapeo se mantiene a mano en `core/isin_map.py` (p. ej. `IE00B5BMR087 → SXR8.DE`).
- **Catálogo de tickers** (`core/tickers.py`): ~25 activos frecuentes con su nombre
  completo; alimenta el autocompletado de los formularios y el nombre que aparece al
  dejar el ratón sobre un campo de ticker.

### Motor compartido (`core/engine.py`, `core/metrics.py`)

Simulación día a día: dadas unas ponderaciones objetivo y un calendario de aportaciones,
compra al cierre (unidades fraccionarias, sin comisiones) y devuelve la serie de valor
más los retornos **time-weighted** (ver glosario). Backtester, simulador y optimizador
comparten este motor: el simulador es N ejecuciones del backtester y el optimizador
consume los mismos retornos.

---

## 2. Mi cartera (`/cartera`)

**Definición.** Panel de la cartera real: las posiciones del export valoradas al último
cierre de mercado.

**Para qué sirve.** Responder de un vistazo "¿cuánto tengo, cuánto he puesto y cuánto ha
hecho el mercado por mí?".

**Cómo funciona.** Reconstruye día a día las **unidades en cartera** (función escalón a
partir de las transacciones), las multiplica por los precios de cierre y obtiene la
curva de valor. En paralelo acumula el **aportado neto** (compras suman, ventas
devuelven). Sobre ambas series calcula:

- **Curva principal:** valor de la cartera frente a aportado neto (línea escalonada,
  porque las aportaciones son saltos discretos).
- **Ganancia acumulada** = valor − aportado: aísla la parte de la subida que pone el
  mercado, quitando el efecto de que tú metas dinero cada mes.
- **Flujo neto por mes:** barras con lo aportado (o retirado) cada mes — el plan de
  inversión hecho visible.
- **Tiles:** ganancia total (€ y %), variación de la última sesión, aportado en los
  últimos 30 días, **CAGR time-weighted** y **máximo drawdown** de la cartera real.
- **Tabla por posición:** unidades, coste medio, último cierre, variación de sesión,
  valor, P&L y peso. Más el historial completo de transacciones plegable.

**Tecnicismos.**
- *Coste medio*: coste total desembolsado (comisiones incluidas) dividido por unidades;
  al vender, el coste se reduce proporcionalmente.
- *TWR (time-weighted return)*: retorno del patrimonio excluyendo el efecto de los
  flujos; ver glosario. Es la forma honesta de medir "cómo lo ha hecho la estrategia"
  cuando hay aportaciones periódicas.

---

## 3. Chequeo de cartera (`/chequeo`)

**Definición.** Motor de reglas estadísticas que examina la cartera real y emite
hallazgos con severidad (atención > aviso > info) o confirmaciones. **No es
asesoramiento profesional**: cada regla es mecánica, con su umbral y su número.

**Para qué sirve.** Detectar de forma automática lo que un inversor disciplinado
revisaría a mano cada mes.

**Las siete reglas** (umbrales en `modules/checkup.py`, ajustables):

| Regla | Umbral | Qué comprueba |
|---|---|---|
| Pesos objetivo | ±5 pp | Desviación del peso actual frente al que definiste; calcula los € a mover para rebalancear |
| Concentración | 60 % | Ningún activo debería dominar la cartera (riesgo específico) |
| Correlación | 0,85 | Pares de activos que se mueven casi a la vez: "diversificación ilusoria" |
| Eficiencia | 1 pp | Compara tu (retorno, volatilidad) con la frontera eficiente **de tus propios activos**: cuánto retorno histórico "dejas" al mismo riesgo |
| Comisiones | 1 % | Compras cuya comisión superó el 1 % del importe (en compras pequeñas la comisión fija pesa mucho) |
| Ritmo de aportación | 6 meses | Meses del último medio año sin ninguna compra: la regularidad del DCA |
| Anomalías | 14 días | Algún activo tuyo con movimientos estadísticamente inusuales recientes (reutiliza el detector) |

**Cómo funciona.** Reúne datos de otros módulos (holdings, riesgo, optimizador,
anomalías) y los pasa por `evaluar()`, una función pura testeada regla a regla. Los
pesos objetivo se guardan en `data/config.json` desde el formulario de la propia página
(validando que sumen 100).

---

## 4. Metas financieras (`/metas`)

**Definición.** "Quiero X € en el año Y": progreso real hacia la meta y probabilidad
estadística de alcanzarla.

**Para qué sirve.** Convertir el ahorro mensual en una pregunta con respuesta: ¿me da o
no me da, y cuánto cambia si aporto más?

**Cómo funciona.** Toma el **valor actual** y los **pesos actuales** de tu cartera real,
y lanza la proyección Monte Carlo (ver §9) desde ese punto hasta el año objetivo, con tu
aportación mensual prevista. La probabilidad es exacta dentro de la simulación: el
porcentaje de los 1.000 futuros simulados que terminan ≥ al importe objetivo. Se calculan
además **variantes de aportación** (0,5×, 1×, 1,5×, 2×) para ver la sensibilidad — la
probabilidad es monótona con la aportación (verificado por test). La meta queda guardada
en la configuración y se precarga en la siguiente visita.

**Tecnicismos.** *Probabilidad empírica*: `P(alcanzar) = nº de simulaciones con valor
terminal ≥ objetivo / nº de simulaciones`. No es una probabilidad "real" del futuro:
es la frecuencia bajo la hipótesis de que los meses futuros se parecen a los pasados.

---

## 5. Backtester (`/backtester`)

**Definición.** Simula cómo habría rendido una estrategia de inversión aplicada sobre
precios históricos reales.

**Para qué sirve.** Responder "si hubiera invertido 200 €/mes en X desde 2015 con
rebalanceo anual, ¿cuánto tendría y cuánto habría sufrido por el camino?".

**Cómo funciona.** Las estrategias son **configuraciones de un único motor**, no
implementaciones separadas:

- *Buy & hold*: aportación única al inicio.
- *DCA (dollar-cost averaging)*: aportación fija el **primer día de negociación de cada
  mes**, opcionalmente solo durante N meses ("repartir 10.000 € en 12 meses").
- *Rebalanceo*: el primer día de cada periodo (mensual/trimestral/anual) las posiciones
  se devuelven a los pesos objetivo vendiendo lo sobreponderado y comprando lo
  infraponderado (sin coste en la simulación).
- *Benchmark opcional*: la misma pauta de aportaciones invertida al 100 % en otro activo,
  superpuesta en el gráfico para comparar.

Las compras se ejecutan al cierre del día, con unidades fraccionarias y sin comisiones.
Los resultados pueden guardarse con nombre (ver §13).

**Métricas que muestra.**

- **Valor final y total aportado** — la respuesta en euros.
- **CAGR (Compound Annual Growth Rate)** — retorno anual compuesto:
  `CAGR = (V_final/V_inicial)^(365,25/días) − 1`, calculado sobre el **índice TWR**, no
  sobre el valor bruto (ver glosario: con DCA, el valor bruto engaña).
- **Volatilidad anualizada** — desviación típica de los retornos diarios × √252
  (252 ≈ sesiones de bolsa por año). Mide cuánto "se mueve" la estrategia.
- **Ratio de Sharpe** — retorno medio en exceso de la tasa libre de riesgo dividido por
  la volatilidad, anualizado: `(media(r − rf) / σ(r − rf)) × √252`. Cuánto retorno
  obtienes por unidad de riesgo total; >1 se considera bueno.
- **Máximo drawdown** — la peor caída desde un pico previo:
  `min(V_t / max(V_0..V_t) − 1)`. El COVID de marzo de 2020, por ejemplo, es ≈ −34 % en
  una cartera 80/20 S&P/IBEX. Es la métrica de "cuánto estómago necesitas".

---

## 6. Simulador qué-pasaría-si (`/simulador`)

**Definición.** Comparación lado a lado de 2-3 escenarios de inversión sobre el mismo
periodo.

**Para qué sirve.** Preguntas del tipo "¿10.000 € de golpe o repartidos en DCA 12
meses?" o "¿este activo o aquel, con la misma pauta?".

**Cómo funciona.** Cada escenario (nombre, activos y pesos, aportación inicial, mensual,
meses aportando, rebalanceo) es **una ejecución independiente del backtester** — la
consistencia con el backtester es por construcción y está verificada por test. Las curvas
se alinean a un índice de fechas común (activos distintos cotizan días distintos) y la
tabla enfrenta las métricas de §5 por columnas.

**Nota estadística.** En un mercado históricamente alcista, la aportación única suele
ganar al DCA (el dinero pasa más tiempo invertido); el DCA reduce el riesgo de entrar en
un pico. El simulador te deja ver ambas caras con datos reales.

---

## 7. Optimizador de cartera (`/optimizador`)

**Definición.** Frontera eficiente de Markowitz: para un conjunto de activos, las
combinaciones de pesos que minimizan el riesgo histórico a cada nivel de retorno.

**Para qué sirve.** Ver qué mezclas de tus activos candidatos fueron eficientes, dónde
está la cartera de mínimo riesgo, la de mejor retorno/riesgo, y qué retorno era posible
con tu tolerancia al riesgo.

**Cómo funciona.**
- Retornos diarios → **retorno esperado anualizado** (`μ = media diaria × 252`) y
  **matriz de covarianza anualizada** (`Σ = cov diaria × 252`).
- La volatilidad de una cartera con pesos `w` es `σ(w) = √(wᵀ Σ w)` — aquí es donde la
  correlación entre activos reduce (o no) el riesgo total.
- Optimización numérica con **SLSQP** (`scipy.optimize.minimize`), con restricciones:
  pesos entre 0 y 1 (sin posiciones cortas) y suma 1.
- **Mínima varianza**: minimiza `wᵀΣw` sin más restricciones.
- **Máximo Sharpe** (cartera tangente): maximiza `(wᵀμ − rf)/σ(w)`.
- **Frontera**: barrido de retornos objetivo entre el de mínima varianza y el máximo
  alcanzable, minimizando varianza con la restricción `wᵀμ = objetivo`.
- **Volatilidad objetivo** (la lectura "con este % de riesgo, ¿qué retorno era
  posible?"): maximiza `wᵀμ` sujeto a `σ(w) ≤ objetivo`. Si el objetivo está por debajo
  del riesgo mínimo alcanzable con esos activos, informa del suelo.

El gráfico riesgo/retorno muestra la frontera, los activos individuales etiquetados, y
las dos carteras destacadas; **click en cualquier punto de la frontera** enseña su
composición. Todo el lenguaje es histórico ("dio", no "dará").

**Limitación conocida (documentada a propósito).** Markowitz es sensible a la ventana:
μ y Σ estimados con historia pasada no son estables. Por eso la página lo presenta como
descripción del periodo analizado, no como receta.

---

## 8. Análisis de riesgo (`/riesgo`)

**Definición.** Batería de métricas de riesgo de una cartera frente a un índice de
referencia, más la matriz de correlación entre sus activos.

**Para qué sirve.** Cuantificar el riesgo más allá de la volatilidad: caídas extremas,
asimetría de las pérdidas y dependencia del mercado.

**Métricas (todas sobre retornos diarios del periodo elegido).**

- **Retorno y volatilidad anualizados** — como en §5.
- **Sharpe** — ver §5.
- **Sortino** — como Sharpe pero dividiendo solo por la **desviación a la baja**
  (*downside deviation*: raíz de la media de los cuadrados de los retornos por debajo
  del mínimo aceptable). Castiga solo la volatilidad "mala": una estrategia con sustos
  al alza y pocas caídas tiene Sortino > Sharpe.
- **VaR 95 % (Value at Risk, histórico)** — el percentil 5 de los retornos diarios:
  "en el 5 % de los peores días se pierde al menos esto". Método histórico puro (el
  cuantil empírico), sin asumir normalidad.
- **CVaR 95 % (Conditional VaR / expected shortfall)** — la **media** de los retornos
  peores que el VaR: cuánto se pierde en promedio cuando el día es de los malos. Siempre
  ≤ VaR; es la métrica preferida en gestión de riesgo moderna porque mira dentro de la
  cola.
- **Beta (β)** — `cov(cartera, índice) / var(índice)`: sensibilidad al mercado de
  referencia. β=1 se mueve como el índice; β=1,5 amplifica; β<1 amortigua.
- **Máximo drawdown** — ver §5.
- **Matriz de correlación** — correlación de Pearson de los retornos diarios entre cada
  par de activos, como heatmap divergente (azul = positiva, ámbar = negativa).
  Correlaciones cercanas a +1 significan que "diversificar" entre esos dos apenas reduce
  riesgo.

---

## 9. Proyección Monte Carlo (`/montecarlo`)

**Definición.** Simulación de miles de futuros posibles de una cartera con aportaciones,
mostrada como abanico de percentiles. No es una predicción: es la distribución de
resultados **si el futuro se pareciera estadísticamente al pasado**.

**Para qué sirve.** Poner rangos honestos a "¿cuánto tendré en 20 años aportando
200 €/mes?" en lugar de una única cifra engañosa.

**Cómo funciona (bootstrap).**
1. Se calculan los **retornos mensuales históricos** de la cartera (retornos diarios
   ponderados por pesos y compuestos por mes de calendario). Mínimo 24 meses.
2. Cada simulación construye un futuro **reordenando al azar, con reemplazo**, esos
   meses reales (bootstrap). Ventaja frente a asumir una normal: conserva la
   distribución empírica, incluidas las **colas gruesas** (los meses de crash reales
   pueden repetirse en la simulación).
3. Sobre cada camino se aplica la aportación mensual al principio de cada mes y se
   compone: `V_{m+1} = (V_m + aportación) × (1 + r_sorteado)`.
4. Con 1.000 caminos se calculan los **percentiles 10/25/50/75/90** de cada mes (las
   bandas del gráfico) y del valor terminal.

**Lecturas.**
- *Mediana (p50)*: el escenario "del medio", mejor referencia que la media (que la
  sesgan los caminos extremos al alza).
- *p10 / p90*: escenario pesimista/optimista razonables (no el peor/mejor posible).
- *Probabilidad de ganar / doblar*: fracción de caminos que terminan por encima de lo
  aportado / del doble.

**Limitaciones explícitas.** Asume que los retornos mensuales son intercambiables
(ignora autocorrelación y cambios de régimen) y que el conjunto histórico es
representativo. Las cifras son nominales (sin descontar inflación).

---

## 10. Dividendos (`/dividendos`)

**Definición.** Agregador de los dividendos cobrados por la cartera y proyección simple
de los próximos 12 meses.

**Para qué sirve.** "¿Cuánto he cobrado este año y cuánto cobraría el que viene si no
toco nada?"

**Cómo funciona.** Para cada posición cruza el **histórico de dividendos por acción**
(yfinance) con las **unidades en cartera estrictamente antes de cada fecha
ex-dividendo**, reconstruidas de las transacciones — así una compra posterior al
ex-date no cuenta, y una venta anterior tampoco.

**Tecnicismos.**
- *Fecha ex-dividendo (ex-date)*: primer día en que comprar la acción ya no da derecho
  al dividendo anunciado. El corte de titularidad se aproxima como "unidades antes del
  ex-date".
- *DPS 12m*: dividendo por acción sumado de los últimos 365 días.
- *Yield on cost*: `DPS_12m × unidades / coste total` — la renta anual como porcentaje
  de lo que **te costó** la posición (no de su precio actual).
- *Proyección 12 meses*: `DPS_12m × unidades actuales` — extrapolación etiquetada como
  tal; no incorpora anuncios, recortes ni retenciones.

**Nota práctica.** Los ETFs **de acumulación (Acc)** reinvierten el dividendo
internamente y no reparten: con una cartera 100 % Acc esta página muestra ceros (y lo
explica). El conmutador `?cartera=ejemplo` usa una cartera versionada con activos de
distribución (VUSA, Telefónica) para ver el módulo en acción.

---

## 11. Detector de anomalías (`/anomalias`)

**Definición.** Identifica días en los que el precio se movió de forma estadísticamente
inusual respecto al comportamiento reciente del activo. Dos métodos conmutables.

**Para qué sirve.** Vigilancia: separar el ruido normal de los movimientos que merecen
una mirada (crashes, gaps, cambios de régimen).

**Método 1 — z-score (estadístico, por defecto).**
- Para cada día se calcula `z = (r_t − μ_prev) / σ_prev`, donde μ y σ son la media y la
  desviación típica de los retornos de la **ventana móvil anterior** (60 sesiones por
  defecto), **sin incluir el propio día** (`shift`): un desplome no infla la desviación
  con la que se evalúa a sí mismo (sin este detalle, las anomalías se auto-amortiguan).
- Un día es anómalo si `|z| >` umbral (3σ por defecto). Detecta en ambas direcciones:
  el −8 % del 12-03-2020 y el rebote del +8,5 % del 24-03-2020.
- Con 3σ y colas gruesas de renta variable, la tasa típica de anomalías ronda el 1-2 %
  de las sesiones (bajo una normal serían 0,27 %: la diferencia **es** la no-normalidad
  de los mercados).

**Método 2 — Isolation Forest (machine learning).**
- Algoritmo **no supervisado** (scikit-learn) que aísla observaciones raras: construye
  árboles que parten el espacio al azar; los puntos anómalos quedan aislados en pocas
  particiones (profundidad media baja = más anómalo).
- Features por día: `(retorno, volatilidad móvil previa)` — capta no solo saltos de
  precio sino **combinaciones raras** (p. ej. un movimiento moderado en un régimen de
  calma extrema).
- *Contaminación*: el parámetro de sensibilidad — la fracción de días que el modelo
  marcará como anómalos (2 % por defecto). Reproducible (`random_state` fijo).

**Bandas de Bollinger** (visualización de contexto, ambas variantes): media móvil de 20
sesiones ± 2 desviaciones típicas del **precio**. La franja sombreada donde "suele"
estar el precio; no interviene en la detección.

---

## 12. Fiscalidad (`/fiscalidad`)

**Definición.** Plusvalías realizadas con criterio FIFO y simulador de venta con la
cuota estimada del IRPF del ahorro. **Estimación simplificada, no asesoría fiscal.**

**Para qué sirve.** Saber qué has "realizado" fiscalmente cada año y, antes de vender,
estimar cuánto se llevaría Hacienda.

**Cómo funciona.**
- **Lotes FIFO:** cada compra crea un lote (fecha, unidades, coste unitario **con la
  comisión prorrateada**). Las ventas consumen lotes **del más antiguo al más nuevo**
  (*First In, First Out*, el criterio que exige la normativa española). La plusvalía de
  una venta es `importe neto de venta − coste FIFO de las unidades vendidas`.
- **Tramos de la base del ahorro** (estatal + autonómico): 19 % hasta 6.000 €, 21 %
  hasta 50.000 €, 23 % hasta 200.000 €, 27 % hasta 300.000 €, 30 % en adelante. La cuota
  se calcula por tramos (los primeros 6.000 € siempre al 19 %, etc.).
- **Simulador de venta:** eliges activo y unidades; el precio se toma del último cierre
  si no lo indicas. Devuelve coste FIFO, plusvalía, cuota estimada, neto, y los lotes
  concretos que consumiría la venta.

**Simplificaciones declaradas.** Calcula la cuota sobre la ganancia **aislada**: no
compensa con pérdidas de otros activos ni ejercicios, no suma otras rentas del ahorro
(dividendos, intereses), no aplica la regla de los dos meses (recompra de valores
homogéneos) ni retenciones ya practicadas.

---

## 13. Análisis guardados (`/guardados`)

**Definición.** Persistencia en SQLite (`data/analyses.db`) de análisis con nombre.

**Cómo funciona.** Al ejecutar un backtest aparece un campo "guardar como"; se almacena
el tipo, el nombre, **los parámetros del formulario** y un resumen de métricas. Desde la
lista puedes **cargar** (rellena el formulario y reejecuta con datos frescos — no
congela el resultado viejo) o **borrar** (con confirmación). Preparado para extenderse a
otros módulos.

---

## 14. Glosario rápido

| Término | Definición |
|---|---|
| **Retorno simple** | `r_t = P_t/P_{t−1} − 1`. Base de casi todas las métricas. |
| **TWR (time-weighted return)** | Retorno por periodo del patrimonio **excluyendo el flujo entrante**: `r_t = (V_t − F_t)/V_{t−1} − 1`. Encadenados (`∏(1+r_t)`) dan el índice TWR. Imprescindible con DCA: cada aportación "tapa" caídas y el valor bruto engañaría a CAGR y drawdown. |
| **CAGR** | Retorno anual compuesto: `(final/inicial)^(365,25/días) − 1`. |
| **Volatilidad anualizada** | `σ(retornos diarios) × √252`. |
| **Sharpe** | Exceso de retorno por unidad de riesgo total. |
| **Sortino** | Exceso de retorno por unidad de riesgo **a la baja** (downside deviation). |
| **Máximo drawdown** | Peor caída pico-a-valle del periodo. |
| **VaR / CVaR 95 %** | Percentil 5 de los retornos / media de lo que hay por debajo de él. |
| **Beta** | Sensibilidad al índice: `cov/var`. |
| **Correlación** | De Pearson entre retornos diarios de dos activos, en [−1, +1]. |
| **Frontera eficiente** | Conjunto de carteras con mínimo riesgo para cada retorno (Markowitz). |
| **Bootstrap** | Remuestreo con reemplazo de datos reales; aquí, meses históricos para simular futuros. |
| **Percentil pN** | Valor por debajo del cual queda el N % de las simulaciones. |
| **Ex-date** | Primer día sin derecho al dividendo anunciado. |
| **Yield on cost** | Renta anual de dividendos sobre el coste de compra de la posición. |
| **FIFO** | Las unidades vendidas son fiscalmente las compradas primero. |
| **DCA** | Aportar una cantidad fija a intervalos regulares. |
| **z-score** | Desviaciones típicas que un dato se aleja de su media de referencia. |
| **Isolation Forest** | Detector de anomalías no supervisado basado en aislar puntos con particiones aleatorias. |
| **Cierre ajustado** | Precio corregido por splits y dividendos; el correcto para retornos. |

---

*Documento generado a partir del código en `modules/`, `core/` y `app/`. Los umbrales y
parámetros citados son los valores por defecto en el código y pueden ajustarse ahí.*
