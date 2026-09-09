"""Envoltorio fino sobre el SDK de Anthropic: parámetros comunes, streaming, refusal y fallbacks."""
from __future__ import annotations

import sys
from typing import Any, Callable, Optional

import anthropic

from .config import FALLBACKS_ENABLED, FALLBACK_BETA, MODEL


class RechazoError(RuntimeError):
    """El modelo (y su fallback, si lo había) rechazó la solicitud."""


def crear_cliente() -> anthropic.Anthropic:
    # Resuelve credenciales solo: ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN o perfil de `ant auth login`.
    try:
        return anthropic.Anthropic()
    except TypeError as e:
        if "authentication" in str(e).lower():
            sys.exit(
                "[radares] Sin credenciales. Exportá ANTHROPIC_API_KEY (ver .env.example) "
                "o corré `ant auth login` para guardar un perfil."
            )
        raise


def params_comunes(effort: str = "high") -> dict[str, Any]:
    p: dict[str, Any] = {
        "model": MODEL,
        "thinking": {"type": "adaptive", "display": "summarized"},
        "output_config": {"effort": effort},
    }
    if FALLBACKS_ENABLED:
        p["betas"] = [FALLBACK_BETA]
        p["fallbacks"] = "default"
    return p


def texto_de(message) -> str:
    return "".join(b.text for b in message.content if getattr(b, "type", "") == "text")


def verificar_stop(message, contexto: str) -> None:
    if message.stop_reason == "refusal":
        det = getattr(message, "stop_details", None)
        cat = getattr(det, "category", None) if det else None
        exp = getattr(det, "explanation", None) if det else None
        raise RechazoError(f"{contexto}: el modelo rechazó la solicitud (categoría {cat}). {exp or ''}".strip())
    if message.stop_reason == "max_tokens":
        print(f"[aviso] {contexto}: la respuesta se cortó por max_tokens; el resultado puede estar incompleto.", file=sys.stderr)


def llamar_stream(
    client: anthropic.Anthropic,
    *,
    max_tokens: int,
    on_text: Optional[Callable[[str], None]] = None,
    on_thinking: Optional[Callable[[str], None]] = None,
    **kwargs: Any,
):
    """Hace una llamada en streaming y devuelve el mensaje final acumulado."""
    with client.beta.messages.stream(max_tokens=max_tokens, **kwargs) as stream:
        for event in stream:
            if event.type == "content_block_delta":
                d = event.delta
                if d.type == "text_delta" and on_text:
                    on_text(d.text)
                elif d.type == "thinking_delta" and on_thinking and getattr(d, "thinking", ""):
                    on_thinking(d.thinking)
        return stream.get_final_message()


def describir_error(e: Exception) -> str:
    if isinstance(e, TypeError) and "authentication" in str(e).lower():
        return "Sin credenciales. Exportá ANTHROPIC_API_KEY (ver .env.example) o corré `ant auth login`."
    if isinstance(e, anthropic.AuthenticationError):
        return "Credenciales inválidas. Seteá ANTHROPIC_API_KEY o corré `ant auth login`."
    if isinstance(e, anthropic.PermissionDeniedError):
        return "La clave no tiene permiso para este modelo o feature."
    if isinstance(e, anthropic.NotFoundError):
        return f"Modelo o endpoint inexistente ({MODEL}). Revisá RADARES_MODEL."
    if isinstance(e, anthropic.RateLimitError):
        return "Límite de tasa alcanzado. Esperá un minuto y reintentá."
    if isinstance(e, anthropic.BadRequestError):
        return f"Solicitud rechazada por la API: {e.message}"
    if isinstance(e, anthropic.APIStatusError):
        return f"Error de la API ({e.status_code}): {e.message}"
    if isinstance(e, anthropic.APIConnectionError):
        return "Sin conexión con la API. Revisá red o proxy."
    return f"{type(e).__name__}: {e}"
