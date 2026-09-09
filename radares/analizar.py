"""De la evidencia al informe estructurado. Opcionalmente con búsqueda web para llenar huecos."""
from __future__ import annotations

import json
from typing import Any, Optional

import anthropic
from pydantic import ValidationError

from .cliente import llamar_stream, params_comunes, texto_de, verificar_stop
from .config import MAX_BUSQUEDAS_WEB, MAX_PAUSE_TURN_RESTARTS, USER_LOCATION
from .prompts import ANALISTA, bloque_memoria, bloque_perfil, pedido_analisis
from .schema import Informe


def herramientas_web(max_uses: int = MAX_BUSQUEDAS_WEB) -> list[dict[str, Any]]:
    return [
        {"type": "web_search_20260209", "name": "web_search", "max_uses": max_uses, "user_location": USER_LOCATION},
        {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": max_uses},
    ]


def parsear_informe(message) -> Informe:
    parsed = getattr(message, "parsed_output", None)
    if isinstance(parsed, Informe):
        return parsed
    texto = texto_de(message).strip()
    try:
        return Informe.model_validate_json(texto)
    except ValidationError:
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
    evidencia: str,
    frentes_txt: str,
    hoy: str,
    nota: Optional[str] = None,
    con_web: bool = True,
) -> tuple[Informe, dict]:
    system = [
        {"type": "text", "text": ANALISTA, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": bloque_perfil(perfil)},
        {"type": "text", "text": bloque_memoria(lecciones_txt, corridas_txt)},
    ]
    messages: list[dict[str, Any]] = [{"role": "user", "content": pedido_analisis(evidencia, frentes_txt, hoy, nota)}]
    uso = {"input_tokens": 0, "output_tokens": 0, "busquedas": 0}
    final = None
    for _ in range(MAX_PAUSE_TURN_RESTARTS + 1):
        kwargs: dict[str, Any] = dict(params_comunes(effort="high"), system=system, messages=messages, output_format=Informe)
        if con_web:
            kwargs["tools"] = herramientas_web()
        final = llamar_stream(client, max_tokens=24000, **kwargs)
        uso["input_tokens"] += final.usage.input_tokens
        uso["output_tokens"] += final.usage.output_tokens
        su = getattr(final.usage, "server_tool_use", None)
        uso["busquedas"] += int(getattr(su, "web_search_requests", 0) or 0) if su else 0
        if final.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": final.content})
            continue
        break
    verificar_stop(final, "análisis")
    return parsear_informe(final), uso
