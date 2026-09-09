"""Fase 3: destilar feedback del dueño en lecciones operativas y resultados por oportunidad."""
from __future__ import annotations

import json
from typing import Any

import anthropic
from pydantic import ValidationError

from .cliente import llamar_stream, params_comunes, texto_de, verificar_stop
from .memoria import Memoria, ahora_iso
from .prompts import DESTILADOR, bloque_perfil, pedido_destilacion
from .render import render_informe
from .schema import Corrida, Feedback, LeccionesExtraidas


def _parsear(message) -> LeccionesExtraidas:
    parsed = getattr(message, "parsed_output", None)
    if isinstance(parsed, LeccionesExtraidas):
        return parsed
    texto = texto_de(message).strip()
    try:
        return LeccionesExtraidas.model_validate_json(texto)
    except ValidationError:
        ini, fin = texto.find("{"), texto.rfind("}")
        if ini >= 0 and fin > ini:
            return LeccionesExtraidas.model_validate(json.loads(texto[ini : fin + 1]))
        raise


def destilar(client: anthropic.Anthropic, *, perfil: str, corrida: Corrida, lecciones_txt: str, feedback: str) -> LeccionesExtraidas:
    system = [
        {"type": "text", "text": DESTILADOR, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": bloque_perfil(perfil)},
    ]
    kwargs: dict[str, Any] = dict(
        params_comunes(effort="medium"),
        system=system,
        messages=[{"role": "user", "content": pedido_destilacion(render_informe(corrida.informe), lecciones_txt, feedback)}],
        output_format=LeccionesExtraidas,
    )
    final = llamar_stream(client, max_tokens=8000, **kwargs)
    verificar_stop(final, "aprendizaje")
    return _parsear(final)


def aplicar_aprendizaje(mem: Memoria, corrida: Corrida, feedback_txt: str, extraido: LeccionesExtraidas) -> list[str]:
    """Persiste feedback, resultados y lecciones. Devuelve líneas para mostrar."""
    lineas: list[str] = []
    existentes = {l.id for l in mem.cargar_lecciones()}
    ids = {o.id: o for o in corrida.informe.oportunidades()}
    resultados = [r for r in extraido.resultados if r.id in ids]
    fb = Feedback(fecha=ahora_iso(), corrida=corrida.id, texto=feedback_txt, resultados=resultados)
    mem.agregar_feedback(corrida, fb)
    for r in resultados:
        lineas.append(f"{r.id} \"{ids[r.id].titulo}\": {r.resultado}" + (f" ({r.nota})" if r.nota else ""))
    for ln in extraido.lecciones:
        if ln.refuerza_id and ln.refuerza_id in existentes:
            l = mem.reforzar_leccion(ln.refuerza_id)
            if l:
                lineas.append(f"Lección reforzada [{l.id}] peso {l.peso}: {l.regla}")
                continue
        nueva = mem.agregar_leccion(ln.regla, ln.aplica_a, ln.origen, corrida.id)
        lineas.append(f"Lección nueva [{nueva.id}] ({nueva.aplica_a}): {nueva.regla}")
    if not extraido.lecciones and not resultados:
        lineas.append("No se extrajo ninguna lección: el feedback no alcanzó para cambiar criterio.")
    return lineas
