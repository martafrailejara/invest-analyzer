# Plataforma de Análisis de Inversión — Proyecto de Portfolio

## Objetivo

App web en Python para analizar y simular estrategias de inversión, combinando datos de mercado (ETFs/acciones) con datos reales de cartera personal. Proyecto de portfolio, independiente de otros proyectos previos (Thru, Soluto).

**Nota de alcance importante:** la app debe quedarse en el terreno descriptivo/analítico (mostrar datos, simulaciones, métricas) y NUNCA emitir recomendaciones prescriptivas de compra/venta ("deberías comprar X"), para evitar entrar en terreno de asesoramiento financiero regulado.

## Stack técnico

- **Backend**: Python, pandas, numpy para cálculos
- **Frontend**: Flask (server-rendered, como en el proyecto Thru de la autora)
- **Datos de mercado**: yfinance (precios históricos, dividendos)
- **Datos de cartera personal**: import manual/CSV (a definir origen exacto — posiblemente export de Trade Republic)

## Arquitectura general

1. **Capa de datos**: ingesta de precios históricos + import de posiciones de cartera propia. Base común de la que dependen todos los módulos.
2. **Motor de cálculo compartido**: retornos, retornos acumulados, métricas de rendimiento y riesgo — reutilizado por varios módulos (especialmente Backtester y Simulador).
3. **Módulos funcionales** (ver detalle abajo).
4. **Dashboard Flask**: visualización de resultados de cada módulo.

## Módulos funcionales

### 1. Backtester de estrategias
Simula cómo habría rendido una estrategia de inversión (DCA mensual, rebalanceo periódico, buy & hold) aplicada sobre datos históricos reales.

- Ejemplo de uso: "Si hubiera invertido 200€/mes en el S&P 500 desde 2015 con rebalanceo anual 80/20, ¿cuánto tendría hoy y cuál fue el máximo drawdown?"
- Necesita: datos históricos de precios, motor de simulación periodo a periodo, estrategias parametrizables, cálculo de CAGR / volatilidad / máximo drawdown / Sharpe ratio.

### 2. Detector de anomalías en precios
Identifica movimientos de precio inusuales respecto al comportamiento histórico del activo.

- Ejemplo de uso: alertar si el precio se mueve más de X desviaciones estándar en un día, o si entra en un régimen de volatilidad distinto.
- Necesita: series temporales de precios, método estadístico (z-score sobre retornos, bandas de Bollinger, o Isolation Forest si se quiere ML), umbral configurable, visualización sobre el gráfico.

### 3. Simulador "qué pasaría si"
Compara distintos escenarios de inversión lado a lado (aportación inicial, aportación mensual, plazo, activo).

- Ejemplo de uso: "¿Qué diferencia hay entre invertir 10.000€ de golpe hoy vs repartirlos en DCA durante 12 meses?"
- Necesita: reutiliza el motor de cálculo del backtester comparando 2+ escenarios en paralelo, interfaz para definir cada escenario, gráfico comparativo.

### 4. Optimizador de cartera
Calcula la combinación de pesos entre activos que maximiza el retorno esperado para un nivel de riesgo dado (teoría moderna de carteras / frontera eficiente de Markowitz).

- Ejemplo de uso: "Dado un conjunto de ETFs candidatos, ¿qué proporción de cada uno minimiza el riesgo para un retorno esperado del 7% anual?"
- Necesita: retornos históricos y matriz de covarianza, librería de optimización (scipy.optimize o PyPortfolioOpt), visualización de la frontera eficiente.

### 5. Agregador de dividendos
Recopila histórico de dividendos de los activos de la cartera y proyecta ingresos pasivos futuros.

- Ejemplo de uso: "¿Cuánto he cobrado en dividendos este año y cuánto proyecto cobrar el año que viene manteniendo posiciones?"
- Necesita: datos históricos de dividendos por activo, posiciones reales del usuario, cálculo de yield on cost y proyección simple.

## Estado actual

- Las 5 funcionalidades están definidas conceptualmente.
- Decisiones tomadas: una sola app integrada (no proyectos separados), Flask como frontend, uso combinado de datos de mercado + cartera personal.
- Pendiente: definir origen exacto de los datos de cartera personal, estructura de carpetas del repo, y por qué módulo empezar a implementar (recomendado: capa de datos → backtester, por ser la base que reutilizan los demás módulos).
