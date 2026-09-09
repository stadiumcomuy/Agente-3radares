"""Configuración: modelo, rutas y fuentes (fuentes.toml)."""
from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

MODEL = os.environ.get("RADARES_MODEL", "claude-opus-5")
FALLBACKS_ENABLED = os.environ.get("RADARES_FALLBACKS", "1") != "0"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_BUSQUEDAS_WEB = int(os.environ.get("RADARES_MAX_BUSQUEDAS", "8"))
MAX_PAUSE_TURN_RESTARTS = 4

RAIZ = Path(__file__).resolve().parent.parent
PERFIL_PATH = Path(os.environ.get("RADARES_PERFIL", RAIZ / "perfil.md"))
FUENTES_PATH = Path(os.environ.get("RADARES_FUENTES", RAIZ / "fuentes.toml"))
MEMORIA_DIR = Path(os.environ.get("RADARES_DIR", RAIZ / "memoria"))

FRENTES = ("demanda_interna", "demanda_externa", "oferta_externa")
FRENTE_LABEL = {
    "demanda_interna": "Demanda interna",
    "demanda_externa": "Demanda externa",
    "oferta_externa": "Oferta externa",
}
FRENTE_PREFIJO = {"demanda_interna": "DI", "demanda_externa": "DE", "oferta_externa": "OE"}

USER_LOCATION = {"type": "approximate", "city": "Montevideo", "region": "Montevideo", "country": "UY", "timezone": "America/Montevideo"}

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
    "Accept-Language": "es-UY,es;q=0.9,en;q=0.7",
}
HTTP_TIMEOUT = 20

_DEFAULTS: dict[str, Any] = {
    "sitio": {"nombre": "", "url": ""},
    "catalogo": {"csv": "", "feed_google": "", "sitemap": "", "max_paginas": 400},
    "ga4": {"property_id": "", "proyecto": "", "credenciales": "", "dias": 28, "min_vistas": 20},
    "trends": {"geo": "UY", "periodo": "today 3-m", "semillas": []},
    "meli": {"sitio": "MLU", "consultas": [], "max_items_preguntas": 4},
    "competencia": {"max_links": 8, "sitios": []},
}


def cargar_fuentes(path: Path = FUENTES_PATH) -> dict[str, Any]:
    conf = {k: dict(v) for k, v in _DEFAULTS.items()}
    if path.exists():
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        for k, v in raw.items():
            if isinstance(v, dict):
                conf.setdefault(k, {}).update(v)
            else:
                conf[k] = v
    ga4 = conf["ga4"]
    ga4["property_id"] = ga4.get("property_id") or os.environ.get("GA4_PROPERTY_ID", "")
    ga4["credenciales"] = ga4.get("credenciales") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if ga4.get("proyecto"):
        os.environ.setdefault("GOOGLE_CLOUD_QUOTA_PROJECT", str(ga4["proyecto"]))
    return conf
