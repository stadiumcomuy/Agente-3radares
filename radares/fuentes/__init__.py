"""Conectores de fuentes: GA4, Google Trends, MercadoLibre, competencia."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

DEBUG_DIR: Optional[str] = None


def guardar_html(nombre: str, html: str) -> None:
    """Si DEBUG_DIR está seteado, guarda el HTML crudo para depurar parsers."""
    if not DEBUG_DIR:
        return
    d = Path(DEBUG_DIR)
    d.mkdir(parents=True, exist_ok=True)
    seguro = re.sub(r"[^a-zA-Z0-9_.-]+", "_", nombre)[:120]
    (d / f"{seguro}.html").write_text(html, encoding="utf-8")
