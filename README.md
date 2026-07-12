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

## Estado

En construcción por fases. Completado: Fase 0 (esqueleto). Siguiente: Fase 1 (capa de datos).
