"""Persistencia de análisis guardados en SQLite.

Guarda backtests (y, en el futuro, otros módulos) con su nombre, los
parámetros con los que se lanzaron y un resumen de métricas, para poder
revisitarlos y recargarlos. La base vive en ``data/`` (fuera del repo).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "analyses.db"


def _conn(db_path: Path | str | None) -> sqlite3.Connection:
    ruta = Path(db_path) if db_path else DEFAULT_DB
    ruta.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(ruta)
    con.row_factory = sqlite3.Row
    con.execute(
        """CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            name TEXT NOT NULL,
            params TEXT NOT NULL,
            summary TEXT NOT NULL,
            created_at TEXT NOT NULL
        )"""
    )
    return con


def save(kind: str, name: str, params: dict, summary: dict, *, db_path=None) -> int:
    """Guarda un análisis y devuelve su id."""
    nombre = (name or "").strip() or "Sin nombre"
    with _conn(db_path) as con:
        cur = con.execute(
            "INSERT INTO analyses (kind, name, params, summary, created_at) VALUES (?, ?, ?, ?, ?)",
            (kind, nombre, json.dumps(params), json.dumps(summary), datetime.now().isoformat(timespec="seconds")),
        )
        return int(cur.lastrowid)


def list_all(kind: str | None = None, *, db_path=None) -> list[dict]:
    """Análisis guardados, del más reciente al más antiguo."""
    with _conn(db_path) as con:
        if kind:
            filas = con.execute("SELECT * FROM analyses WHERE kind = ? ORDER BY id DESC", (kind,)).fetchall()
        else:
            filas = con.execute("SELECT * FROM analyses ORDER BY id DESC").fetchall()
    return [_row(f) for f in filas]


def get(analysis_id: int, *, db_path=None) -> dict | None:
    with _conn(db_path) as con:
        fila = con.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
    return _row(fila) if fila else None


def delete(analysis_id: int, *, db_path=None) -> bool:
    with _conn(db_path) as con:
        cur = con.execute("DELETE FROM analyses WHERE id = ?", (analysis_id,))
        return cur.rowcount > 0


def _row(fila: sqlite3.Row) -> dict:
    return {
        "id": fila["id"],
        "kind": fila["kind"],
        "name": fila["name"],
        "params": json.loads(fila["params"]),
        "summary": json.loads(fila["summary"]),
        "created_at": fila["created_at"],
    }
