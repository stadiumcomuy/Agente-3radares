"""Configuración central: modelo, rutas, límites."""
from __future__ import annotations

import os
from pathlib import Path

MODEL = os.environ.get("RADARES_MODEL", "claude-opus-5")

# Fallback server-side ante rechazos de los clasificadores de seguridad.
# Header y forma "default" según la referencia de la API para Claude Opus 5.
FALLBACKS_ENABLED = os.environ.get("RADARES_FALLBACKS", "1") != "0"
FALLBACK_BETA = "server-side-fallback-2026-07-01"

MAX_BUSQUEDAS = int(os.environ.get("RADARES_MAX_BUSQUEDAS", "18"))
MAX_PAUSE_TURN_RESTARTS = 4

RAIZ = Path(__file__).resolve().parent.parent
PERFIL_PATH = Path(os.environ.get("RADARES_PERFIL", RAIZ / "perfil.md"))
MEMORIA_DIR = Path(os.environ.get("RADARES_DIR", RAIZ / "memoria"))

FOCOS = ("demanda_interna", "demanda_externa", "oferta_externa")

FOCO_LABEL = {
    "demanda_interna": "Demanda interna",
    "demanda_externa": "Demanda externa",
    "oferta_externa": "Oferta externa",
}

USER_LOCATION = {
    "type": "approximate",
    "city": "Montevideo",
    "region": "Montevideo",
    "country": "UY",
    "timezone": "America/Montevideo",
}
