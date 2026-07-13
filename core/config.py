"""Configuración personal persistente (pesos objetivo, metas…) en data/config.json."""

from __future__ import annotations

import json
from pathlib import Path

RUTA = Path(__file__).resolve().parents[1] / "data" / "config.json"


def load(ruta: Path | str | None = None) -> dict:
    ruta = Path(ruta) if ruta else RUTA
    if not ruta.exists():
        return {}
    return json.loads(ruta.read_text())


def save(datos: dict, ruta: Path | str | None = None) -> None:
    ruta = Path(ruta) if ruta else RUTA
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, indent=2, ensure_ascii=False))


def get(clave: str, defecto=None, ruta=None):
    return load(ruta).get(clave, defecto)


def set(clave: str, valor, ruta=None) -> None:
    datos = load(ruta)
    datos[clave] = valor
    save(datos, ruta)
