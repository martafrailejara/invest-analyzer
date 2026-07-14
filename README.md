# invest-analyzer

Plataforma web de análisis y simulación de estrategias de inversión. Combina datos de mercado (yfinance) con la cartera personal (export de transacciones de Trade Republic) en cinco módulos: backtester de estrategias, simulador de escenarios, optimizador de cartera (Markowitz), agregador de dividendos y detector de anomalías de precio.

> **Alcance:** la aplicación es descriptiva/analítica. Muestra datos, simulaciones y métricas; nunca emite recomendaciones de compra o venta.

## Stack

- **Backend:** Python, pandas, numpy
- **Web:** Flask (server-rendered) + Chart.js
- **Datos de mercado:** yfinance, con caché local en parquet
- **Cálculo:** numpy, pandas, scipy (optimización), scikit-learn (Isolation Forest)
- **Persistencia:** SQLite para análisis guardados
- **Cartera personal:** parser del CSV de transacciones de Trade Republic

## Estructura

```
app/      # Aplicación Flask (blueprints por módulo)
core/     # Capa de datos y motor de cálculo compartido
modules/  # Lógica de los módulos funcionales
tests/    # Tests (pytest, con fixtures sintéticos — nunca datos reales)
data/     # Caché de mercado y datos personales (fuera del repo)
```

## Desarrollo

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

Para probar la capa de datos con datos reales (descarga de yfinance + cartera propia):

```bash
# opcional: guarda tu export de Trade Republic en data/transacciones.csv
python scripts/demo_fase1.py
```

Los ISINs del export se traducen a tickers de yfinance en `core/isin_map.py`; al incorporar un activo nuevo a la cartera hay que añadir ahí su mapeo.

El backtester puede probarse desde consola con el caso de ejemplo del proyecto (200€/mes en 80/20 S&P 500 / IBEX 35 desde 2015, rebalanceo anual):

```bash
python scripts/demo_fase2.py
```

O desde el navegador, con el dashboard Flask:

```bash
flask --app app run
# http://127.0.0.1:5000 → formulario del backtester, gráfico y métricas
```

El dashboard navega entre los módulos con ⌘K (paleta de comandos). El diseño usa tokens propios ([app/static/tokens.css](app/static/tokens.css)) y Chart.js vendorizado en local.

La página de dividendos lee la cartera real de `data/transacciones.csv`; como alternativa, `?cartera=ejemplo` usa [samples/transacciones_ejemplo.csv](samples/transacciones_ejemplo.csv) (activos de distribución, útil cuando la cartera real solo tiene ETFs de acumulación).

Hay una **ficha completa de funcionalidades** — qué hace cada módulo, cómo funciona por dentro y qué significa cada métrica — en [docs/FUNCIONALIDADES.md](docs/FUNCIONALIDADES.md).

## Estado

Módulos, todos funcionales:

0. **Landing** — portada que organiza los módulos por intención; navegación ⌘K y catálogo de tickers con autocompletado y nombre al pasar el ratón.
1. **Mi cartera** — posiciones reales valoradas a mercado, curva valor vs aportado, ganancia de mercado aislada, flujo mensual, P&L por posición e historial.
1b. **Chequeo de cartera** — recomendaciones estadísticas con severidad: desviación de pesos objetivo, concentración, correlaciones, eficiencia vs frontera, comisiones, ritmo de DCA y anomalías recientes (no es asesoramiento profesional).
1c. **Metas financieras** — progreso hacia "X € en el año Y" y probabilidad Monte Carlo de llegar, con variantes de aportación.
1d. **Fiscalidad** — plusvalías realizadas con FIFO por lotes y simulador de venta con la cuota estimada de la base del ahorro (estimación, no asesoría fiscal).
2. **Backtester** — estrategias parametrizables (buy & hold, DCA, rebalanceo, benchmark, DCA de N meses) con métricas time-weighted. Los backtests se pueden **guardar** (SQLite) y recargar.
3. **Simulador qué-pasaría-si** — 2-3 escenarios comparados sobre el mismo motor.
4. **Optimizador** — frontera eficiente de Markowitz (scipy, sin cortos), mínima varianza y máximo Sharpe, frontera clicable.
5. **Análisis de riesgo** — Sharpe, Sortino, VaR/CVaR, beta vs índice y matriz de correlación (heatmap).
6. **Proyección Monte Carlo** — bootstrap de retornos mensuales, abanico de percentiles a X años con aportaciones.
7. **Dividendos** — cobrado por año/posición, yield on cost y proyección a 12 meses.
8. **Anomalías** — z-score sobre ventana previa (sin lookahead) o **Isolation Forest** (ML), con bandas de Bollinger.

Los tickers en USD se convierten automáticamente a EUR (cruce EURUSD=X). Construido por fases (0-7) con tests en cada capa: métricas y motor verificados contra casos calculados a mano, módulos contra propiedades y casos analíticos, y las páginas Flask con motores sustituidos (sin red).
