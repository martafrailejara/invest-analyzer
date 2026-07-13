# invest-analyzer

Plataforma web de análisis y simulación de estrategias de inversión. Combina datos de mercado (yfinance) con la cartera personal (export de transacciones de Trade Republic) en cinco módulos: backtester de estrategias, simulador de escenarios, optimizador de cartera (Markowitz), agregador de dividendos y detector de anomalías de precio.

> **Alcance:** la aplicación es descriptiva/analítica. Muestra datos, simulaciones y métricas; nunca emite recomendaciones de compra o venta.

## Stack

- **Backend:** Python, pandas, numpy
- **Web:** Flask (server-rendered) + Chart.js
- **Datos de mercado:** yfinance, con caché local en parquet
- **Cartera personal:** parser del CSV de transacciones de Trade Republic

## Estructura

```
app/      # Aplicación Flask (blueprints por módulo)
core/     # Capa de datos y motor de cálculo compartido
modules/  # Lógica de los cinco módulos funcionales
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

El dashboard navega entre los 5 módulos con ⌘K (paleta de comandos). El diseño usa tokens propios ([app/static/tokens.css](app/static/tokens.css)) y Chart.js vendorizado en local.

La página de dividendos lee la cartera real de `data/transacciones.csv`; como alternativa, `?cartera=ejemplo` usa [samples/transacciones_ejemplo.csv](samples/transacciones_ejemplo.csv) (activos de distribución, útil cuando la cartera real solo tiene ETFs de acumulación).

## Estado

En construcción por fases. Completado: Fase 0 (esqueleto), Fase 1 (capa de datos: precios/dividendos con caché parquet + posiciones desde el export de Trade Republic), Fase 2 (motor de métricas y simulación + backtester, con retornos time-weighted), Fase 3 (dashboard Flask con la página del backtester funcional), Fase 4 (simulador qué-pasaría-si con 2-3 escenarios comparados), Fase 5 (optimizador de cartera: frontera eficiente de Markowitz con scipy), Fase 6 (agregador de dividendos con proyección a 12 meses). Siguiente: Fase 7 (detector de anomalías).
