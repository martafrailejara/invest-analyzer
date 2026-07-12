"""El simulador debe coincidir exactamente con ejecuciones independientes del backtester."""

import pandas as pd
import pytest

from modules import backtester, simulator
from modules.simulator import Scenario


def downloader_sintetico(ticker, start, end):
    fechas = pd.bdate_range(start, end)
    base = float(sum(ord(c) for c in ticker) % 50) + 50
    return pd.Series([base + i * 0.3 for i in range(len(fechas))], index=fechas)


ESCENARIOS = [
    Scenario("Aportación única", {"AAA": 1.0}, initial_investment=10000),
    Scenario("DCA 12 meses", {"AAA": 1.0}, monthly_contribution=833.33),
    Scenario("Mixto 60/40", {"AAA": 0.6, "BBB": 0.4}, initial_investment=5000,
             monthly_contribution=100, rebalance_freq="Q"),
]


def test_consistencia_con_el_backtester(tmp_path):
    """Criterio de 'hecho' de la fase: las curvas del simulador coinciden con
    lo que darían ejecuciones independientes del backtester."""
    args = dict(cache_dir=tmp_path, downloader=downloader_sintetico)
    resultados = simulator.run(ESCENARIOS, "2024-01-02", "2024-12-31", **args)
    assert len(resultados) == 3

    for escenario, res in resultados:
        independiente = backtester.run(
            dict(escenario.weights), "2024-01-02", "2024-12-31",
            initial_investment=escenario.initial_investment,
            monthly_contribution=escenario.monthly_contribution,
            rebalance_freq=escenario.rebalance_freq,
            **args,
        )
        pd.testing.assert_series_equal(res.value, independiente.value, check_freq=False)
        pd.testing.assert_series_equal(res.invested, independiente.invested, check_freq=False)


def test_lump_sum_y_dca_difieren_como_se_espera(tmp_path):
    """Con precio siempre creciente, invertir todo al principio gana al DCA."""
    args = dict(cache_dir=tmp_path, downloader=downloader_sintetico)
    resultados = simulator.run(ESCENARIOS[:2], "2024-01-02", "2024-12-31", **args)
    (_, golpe), (_, dca) = resultados
    assert golpe.value.iloc[-1] > dca.value.iloc[-1]


def test_menos_de_dos_escenarios_error(tmp_path):
    with pytest.raises(ValueError, match="al menos dos escenarios"):
        simulator.run(ESCENARIOS[:1], "2024-01-02", "2024-12-31",
                      cache_dir=tmp_path, downloader=downloader_sintetico)
