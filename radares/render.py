"""Informe a texto ejecutivo, por frente. Cero tablas."""
from __future__ import annotations

from .config import FRENTE_LABEL, FRENTES
from .schema import Corrida, Informe, Oportunidad

TENEMOS = {"si": "lo tenemos", "parcial": "lo tenemos parcial", "no": "no lo tenemos"}


def _score(s) -> str:
    return f"Impacto {s.impacto} · Esfuerzo {s.esfuerzo} · Confianza {s.confianza} · Urgencia {s.urgencia} · Prioridad {s.prioridad}"


def _oportunidad(o: Oportunidad, apuesta: bool) -> list[str]:
    out = [f"{o.id} · {o.titulo}" + ("  ← APUESTA" if apuesta else "")]
    out.append(f"{TENEMOS.get(o.lo_tenemos, o.lo_tenemos).capitalize()} · {o.marca_sugerida} · {o.producto_o_termino}")
    out.append(f"Dato. {o.que_pasa.strip()}")
    out.append(f"Grieta. {o.por_que_es_grieta.strip()}")
    if o.gap_precio or o.precio_nuestro or o.precio_afuera:
        precios = " · ".join(x for x in [f"nuestro {o.precio_nuestro}" if o.precio_nuestro else "", f"afuera {o.precio_afuera}" if o.precio_afuera else "", o.gap_precio or ""] if x)
        out.append(f"Precio. {precios}")
    out.append(f"Acción. {o.accion_minima.strip()}")
    out.append(f"Validar. {o.que_validar.strip()}")
    out.append(_score(o.score))
    if o.fuentes:
        out.append("Fuentes: " + " · ".join(o.fuentes))
    out.append("")
    return out


def render_informe(inf: Informe, titulo: str = "Radar", estado_fuentes: dict | None = None) -> str:
    out = [f"# {titulo}"]
    if estado_fuentes:
        out.append("Fuentes: " + " · ".join(f"{k}: {v}" for k, v in estado_fuentes.items()))
    out.append("")
    for nombre in FRENTES:
        f = inf.frente(nombre)
        if not f:
            continue
        out.append(f"## {FRENTE_LABEL[nombre]}")
        out.append(f.lectura.strip())
        out.append("")
        for o in f.oportunidades:
            out += _oportunidad(o, o.id == inf.mejor_apuesta)
    ap = inf.apuesta()
    out.append(f"## Apuesta: {ap.id} · {ap.titulo}")
    out.append(inf.por_que_mejor_apuesta.strip())
    out.append("")
    out.append("## Contestame")
    for q in inf.preguntas_feedback:
        out.append(f"- {q.strip()}")
    return "\n".join(out).rstrip() + "\n"


def render_corrida(c: Corrida) -> str:
    cuerpo = render_informe(c.informe, titulo=f"Radar · {c.fecha[:10]} · {c.id}", estado_fuentes=c.estado_fuentes)
    pie = ["", f"Feedback: radares feedback {c.id} \"tu respuesta\""]
    if c.uso:
        pie.append(f"Uso: entrada {c.uso.get('input_tokens', '?')} · salida {c.uso.get('output_tokens', '?')} · web {c.uso.get('busquedas', 0)}")
    return cuerpo + "\n".join(pie) + "\n"


def render_historial(corridas) -> str:
    if not corridas:
        return "Sin corridas todavía. Ejecutá: radares correr\n"
    return "\n".join(f"{c.id}  {c.fecha[:10]}  apuesta={c.informe.apuesta().id} \"{c.informe.apuesta().titulo}\"  feedback={len(c.feedback)}" for c in corridas) + "\n"


def render_lecciones(lecciones) -> str:
    if not lecciones:
        return "Sin lecciones todavía. Se generan con: radares feedback \"texto\"\n"
    lecciones = sorted(lecciones, key=lambda l: (-l.peso, l.fecha))
    return "\n".join(f"[{l.id}] peso {l.peso} · {l.aplica_a} · {l.fecha}\n  {l.regla}\n  origen: {l.origen}" for l in lecciones) + "\n"
