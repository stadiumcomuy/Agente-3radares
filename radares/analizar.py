"""Fase 2: del dossier al informe estructurado (salida con esquema JSON)."""
from __future__ import annotations

import json
from typing import Any

import anthropic
from pydantic import ValidationError

from .cliente import llamar_stream, params_comunes, texto_de, verificar_stop
from .prompts import ANALISTA, bloque_memoria, bloque_perfil, pedido_analisis
from .schema import Informe


def parsear_informe(message) -> Informe:
    parsed = getattr(message, "parsed_output", None)
    if isinstance(parsed, Informe):
        return parsed
    texto = texto_de(message).strip()
    try:
        return Informe.model_validate_json(texto)
    except ValidationError:
        # Último recurso: recortar a la primera llave por si vino texto alrededor.
        ini, fin = texto.find("{"), texto.rfind("}")
        if ini >= 0 and fin > ini:
            return Informe.model_validate(json.loads(texto[ini : fin + 1]))
        raise


def analizar(
    client: anthropic.Anthropic,
    *,
    perfil: str,
    lecciones_txt: str,
    corridas_txt: str,
    dossier: str,
    foco: str,
    hoy: str,
) -> tuple[Informe, dict]:
    system = [
        {"type": "text", "text": ANALISTA, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": bloque_perfil(perfil)},
        {"type": "text", "text": bloque_memoria(lecciones_txt, corridas_txt)},
    ]
    kwargs: dict[str, Any] = dict(
        params_comunes(effort="high"),
        system=system,
        messages=[{"role": "user", "content": pedido_analisis(dossier, foco, hoy)}],
        output_format=Informe,
    )
    final = llamar_stream(client, max_tokens=16000, **kwargs)
    verificar_stop(final, "análisis")
    informe = parsear_informe(final)
    uso = {"input_tokens": final.usage.input_tokens, "output_tokens": final.usage.output_tokens}
    return informe, uso
