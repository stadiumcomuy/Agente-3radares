"""Fase 1: investigación con búsqueda web. Devuelve un dossier de hallazgos con fuentes."""
from __future__ import annotations

import sys
from typing import Any, Callable, Optional

import anthropic

from .cliente import llamar_stream, params_comunes, texto_de, verificar_stop
from .config import MAX_BUSQUEDAS, MAX_PAUSE_TURN_RESTARTS, USER_LOCATION
from .prompts import INVESTIGADOR, bloque_memoria, bloque_perfil, pedido_investigacion


def herramientas_web(max_uses: int = MAX_BUSQUEDAS) -> list[dict[str, Any]]:
    return [
        {
            "type": "web_search_20260209",
            "name": "web_search",
            "max_uses": max_uses,
            "user_location": USER_LOCATION,
        }
    ]


def contar_busquedas(message) -> int:
    su = getattr(message.usage, "server_tool_use", None)
    return int(getattr(su, "web_search_requests", 0) or 0) if su else 0


def investigar(
    client: anthropic.Anthropic,
    *,
    perfil: str,
    lecciones_txt: str,
    corridas_txt: str,
    foco: str,
    hoy: str,
    nota: Optional[str] = None,
    datos: Optional[str] = None,
    con_web: bool = True,
    verbose: bool = False,
) -> tuple[str, dict]:
    system = [
        {"type": "text", "text": INVESTIGADOR, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": bloque_perfil(perfil)},
        {"type": "text", "text": bloque_memoria(lecciones_txt, corridas_txt)},
    ]
    if not con_web:
        system.append(
            {
                "type": "text",
                "text": "En esta corrida NO tenés búsqueda web. Trabajá con el perfil, la memoria y los datos internos. "
                "Marcá como SIN FUENTE todo lo que no puedas respaldar.",
            }
        )
    pedido = pedido_investigacion(foco, hoy, nota, datos)
    messages: list[dict[str, Any]] = [{"role": "user", "content": pedido}]

    on_text: Optional[Callable[[str], None]] = None
    on_thinking: Optional[Callable[[str], None]] = None
    if verbose:
        on_text = lambda t: print(t, end="", file=sys.stderr, flush=True)
        on_thinking = lambda t: print(t, end="", file=sys.stderr, flush=True)

    uso = {"input_tokens": 0, "output_tokens": 0, "busquedas": 0}
    tools = herramientas_web() if con_web else []
    final = None
    for intento in range(MAX_PAUSE_TURN_RESTARTS + 1):
        kwargs: dict[str, Any] = dict(params_comunes(effort="high"), system=system, messages=messages)
        if tools:
            kwargs["tools"] = tools
        final = llamar_stream(client, max_tokens=32000, on_text=on_text, on_thinking=on_thinking, **kwargs)
        uso["input_tokens"] += final.usage.input_tokens
        uso["output_tokens"] += final.usage.output_tokens
        uso["busquedas"] += contar_busquedas(final)
        if final.stop_reason == "pause_turn":
            # La herramienta server-side pausó el turno: se reenvía el historial completo para continuar.
            messages.append({"role": "assistant", "content": final.content})
            if verbose:
                print("\n[continuando turno pausado]", file=sys.stderr)
            continue
        break

    verificar_stop(final, "investigación")
    dossier = texto_de(final).strip()
    if not dossier:
        raise RuntimeError("La investigación no devolvió texto.")
    return dossier, uso
