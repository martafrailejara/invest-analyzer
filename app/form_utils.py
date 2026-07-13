"""Helpers de validación de formularios compartidos por los módulos del dashboard.

Todas las funciones acumulan mensajes legibles en la lista ``errores`` en vez
de lanzar excepciones, para poder mostrar todos los problemas de una vez.
"""

from __future__ import annotations

from datetime import date


def parsea_importe(texto: str, nombre: str, errores: list[str]) -> float:
    """Número no negativo desde texto (admite coma decimal); 0 si está vacío."""
    txt = (texto or "").strip() or "0"
    try:
        valor = float(txt.replace(",", "."))
    except ValueError:
        errores.append(f"La {nombre} no es un número.")
        return 0.0
    if valor < 0:
        errores.append(f"La {nombre} no puede ser negativa.")
    return valor


def parsea_activos(filas: list[tuple[str, str]], errores: list[str], contexto: str = "") -> dict[str, float]:
    """Filas (ticker, peso%) → pesos normalizados a fracción; validan suma 100.

    ``contexto`` prefija los mensajes (p. ej. "Escenario A: ") para formularios
    con varios bloques de activos.
    """
    pesos: dict[str, float] = {}
    for i, (ticker_txt, peso_txt) in enumerate(filas):
        ticker = (ticker_txt or "").strip().upper()
        peso_txt = (peso_txt or "").strip()
        if not ticker and not peso_txt:
            continue
        if not ticker or not peso_txt:
            errores.append(f"{contexto}La fila {i + 1} de activos necesita ticker y peso.")
            continue
        try:
            peso = float(peso_txt.replace(",", "."))
        except ValueError:
            errores.append(f"{contexto}El peso de {ticker} no es un número.")
            continue
        if peso <= 0:
            errores.append(f"{contexto}El peso de {ticker} debe ser mayor que 0.")
            continue
        pesos[ticker] = pesos.get(ticker, 0) + peso

    if not pesos:
        errores.append(f"{contexto}Indica al menos un activo con su peso.")
    elif abs(sum(pesos.values()) - 100) > 0.01:
        errores.append(f"{contexto}Los pesos deben sumar 100 (suman {sum(pesos.values()):g}).")
    return {t: p / 100 for t, p in pesos.items()}


def parsea_fechas(start: str, end: str, errores: list[str], avisos: list[str]) -> str:
    """Valida el rango y devuelve el ``end`` efectivo, recortado a hoy si hace falta."""
    hoy = date.today()
    try:
        fin = date.fromisoformat(end)
        if fin > hoy:
            avisos.append(f"Solo hay histórico hasta hoy: el rango se recorta de {end} a {hoy.isoformat()}.")
            end, fin = hoy.isoformat(), hoy
        if date.fromisoformat(start) >= fin:
            errores.append("La fecha inicial debe ser anterior a la final.")
    except ValueError:
        errores.append("Fechas incompletas o con formato incorrecto.")
    return end


def parsea_rebalanceo(valor: str, errores: list[str]) -> str | None:
    rebalance = valor or None
    if rebalance not in (None, "M", "Q", "Y"):
        errores.append("Frecuencia de rebalanceo no reconocida.")
    return rebalance


def eur(v: float) -> str:
    entero, decimales = f"{v:,.2f}".split(".")
    return entero.replace(",", ".") + "," + decimales + " €"


def pct(v: float) -> str:
    import math

    if math.isnan(v):
        return "—"
    return f"{v * 100:.2f}".replace(".", ",") + " %"
