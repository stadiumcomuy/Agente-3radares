"""Renderizado del informe a texto ejecutivo. Cero tablas."""
from __future__ import annotations

from .config import FOCO_LABEL
from .schema import Corrida, Informe

NUM = ["①", "②", "③", "④", "⑤"]


def _score_linea(s) -> str:
    return (
        f"Impacto {s.impacto}/5 · Esfuerzo {s.esfuerzo}/5 · "
        f"Confianza {s.confianza}/5 · Urgencia {s.urgencia}/5 · Prioridad {s.prioridad}"
    )


def render_informe(inf: Informe, titulo: str = "Tres radares") -> str:
    out = [f"# {titulo}", "", inf.resumen_ejecutivo.strip(), ""]
    for i, o in enumerate(inf.oportunidades, 1):
        num = NUM[i - 1] if i <= len(NUM) else f"{i}."
        apuesta = "  ← MEJOR APUESTA" if i == inf.mejor_apuesta else ""
        out.append(f"{num} {o.titulo}{apuesta}")
        out.append(f"Radar: {FOCO_LABEL.get(o.foco, o.foco)} · Marca: {o.marca_sugerida}")
        out.append("")
        out.append(f"Qué está pasando. {o.que_pasa.strip()}")
        out.append(f"Por qué es una grieta. {o.por_que_es_grieta.strip()}")
        out.append(f"Acción mínima. {o.accion_minima.strip()}")
        out.append(f"Qué validar. {o.que_validar.strip()}")
        out.append(_score_linea(o.score))
        if o.fuentes:
            out.append("Fuentes: " + " · ".join(o.fuentes))
        out.append("")
    ap = inf.apuesta()
    out.append(f"## Mejor apuesta: {ap.titulo}")
    out.append(inf.por_que_mejor_apuesta.strip())
    out.append("")
    out.append("## Necesito que me contestes esto")
    for q in inf.preguntas_feedback:
        out.append(f"- {q.strip()}")
    return "\n".join(out).rstrip() + "\n"


def render_corrida(c: Corrida) -> str:
    cuerpo = render_informe(c.informe, titulo=f"Tres radares · {c.fecha[:10]} · corrida {c.id}")
    pie = [
        "",
        f"Para dar feedback: radares feedback {c.id} \"tu respuesta\"",
    ]
    if c.uso:
        pie.append(
            "Uso: entrada {input} · salida {output} · búsquedas web {busquedas}".format(
                input=c.uso.get("input_tokens", "?"),
                output=c.uso.get("output_tokens", "?"),
                busquedas=c.uso.get("busquedas", "?"),
            )
        )
    return cuerpo + "\n".join(pie) + "\n"


def render_historial(corridas) -> str:
    if not corridas:
        return "Sin corridas todavía. Ejecutá: radares correr\n"
    out = []
    for c in corridas:
        ap = c.informe.apuesta()
        n_fb = len(c.feedback)
        out.append(f"{c.id}  {c.fecha[:10]}  foco={c.foco}  apuesta=\"{ap.titulo}\"  feedback={n_fb}")
    return "\n".join(out) + "\n"


def render_lecciones(lecciones) -> str:
    if not lecciones:
        return "Sin lecciones todavía. Se generan con: radares feedback <corrida> \"texto\"\n"
    lecciones = sorted(lecciones, key=lambda l: (-l.peso, l.fecha))
    out = []
    for l in lecciones:
        out.append(f"[{l.id}] peso {l.peso} · {l.aplica_a} · {l.fecha}\n  {l.regla}\n  origen: {l.origen}")
    return "\n".join(out) + "\n"
