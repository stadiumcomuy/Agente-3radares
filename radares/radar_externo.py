"""Demanda externa: qué busca la gente en Google y MercadoLibre, cruzado con lo que tenemos."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .catalogo import Catalogo
from .fuentes.meli import DatosMeli
from .fuentes.trends import DatosTrends


@dataclass
class SenalExterna:
    fuente: str          # trends | meli
    sujeto: str
    tenemos: str         # si | parcial | no | sin_catalogo
    detalle: str
    precio_nuestro: Optional[float] = None
    precio_afuera: Optional[float] = None
    producto_nuestro: str = ""
    fuentes: List[str] = field(default_factory=list)
    dato: dict = field(default_factory=dict)

    @property
    def gap_pct(self) -> Optional[float]:
        if self.precio_nuestro and self.precio_afuera:
            return (self.precio_nuestro - self.precio_afuera) / self.precio_afuera
        return None


@dataclass
class RadarExterno:
    senales: List[SenalExterna] = field(default_factory=list)
    resumen: str = ""


def _cruce(catalogo: Catalogo, texto: str):
    if not len(catalogo):
        return "sin_catalogo", None, ""
    estado, m = catalogo.tenemos(texto)
    if m:
        return estado, m[0].producto.precio, m[0].producto.nombre
    return estado, None, ""


def senales_trends(trends: DatosTrends, catalogo: Catalogo, max_n: int = 15) -> List[SenalExterna]:
    out = []
    vistos = set()
    rising = [r for r in trends.relacionadas if r.tipo == "rising"]
    top = [r for r in trends.relacionadas if r.tipo == "top"][:20]
    for r in rising + top:
        q = r.consulta.strip()
        if q.lower() in vistos:
            continue
        vistos.add(q.lower())
        estado, precio, prod = _cruce(catalogo, q)
        etiqueta = "en alza" if r.tipo == "rising" else "consulta top"
        valor = "Breakout" if "breakout" in r.valor.lower() else f"+{r.valor}%" if r.tipo == "rising" else f"índice {r.valor}"
        out.append(SenalExterna("trends", q, estado, f"'{q}' ({etiqueta}, {valor}) relacionada con '{r.semilla}' en Google Trends {trends.origen.split()[-2] if len(trends.origen.split()) > 2 else 'UY'}.", precio, None, prod, ["Google Trends"], {"tipo": r.tipo, "valor": r.valor, "semilla": r.semilla}))
        if len(out) >= max_n:
            break
    for i in trends.interes:
        if abs(i.variacion) >= 0.25 and i.promedio_reciente >= 10:
            estado, precio, prod = _cruce(catalogo, i.semilla)
            signo = "sube" if i.variacion > 0 else "cae"
            out.append(SenalExterna("trends", i.semilla, estado, f"El interés por '{i.semilla}' {signo} {abs(i.variacion):.0%} en las últimas 4 semanas vs. el período previo.", precio, None, prod, ["Google Trends"], {"variacion": round(i.variacion, 3)}))
    return out


def senales_meli(meli: DatosMeli, catalogo: Catalogo, max_por_consulta: int = 4) -> List[SenalExterna]:
    out = []
    for rc in meli.consultas:
        pubs = sorted(rc.publicaciones, key=lambda p: (-(p.n_preguntas or 0), not p.mas_vendido, -(p.vendidos or 0)))
        for p in pubs[:max_por_consulta]:
            estado, precio, prod = _cruce(catalogo, p.titulo)
            partes = []
            if p.mas_vendido:
                partes.append("etiqueta 'más vendido'")
            if p.vendidos:
                partes.append(f"{p.vendidos} vendidos")
            if p.n_preguntas:
                partes.append(f"{p.n_preguntas} preguntas")
            if rc.total_resultados:
                partes.append(f"{rc.total_resultados} publicaciones para '{rc.consulta}'")
            detalle = f"MELI: '{p.titulo}'" + (f" a {p.precio:.0f}" if p.precio else "") + (". " + ", ".join(partes) if partes else "") + "."
            if p.preguntas:
                detalle += " Preguntas: " + " | ".join(q[:90] for q in p.preguntas[:4])
            out.append(SenalExterna("meli", p.titulo, estado, detalle, precio, p.precio, prod, [p.url] if p.url else ["MercadoLibre"], {"consulta": rc.consulta, "preguntas": p.preguntas[:6], "n_preguntas": p.n_preguntas, "vendidos": p.vendidos, "mas_vendido": p.mas_vendido}))
    return out


def radar_demanda_externa(trends: Optional[DatosTrends], meli: Optional[DatosMeli], catalogo: Catalogo) -> RadarExterno:
    r = RadarExterno()
    if trends:
        r.senales += senales_trends(trends, catalogo)
    if meli:
        r.senales += senales_meli(meli, catalogo)
    tenemos = sum(1 for s in r.senales if s.tenemos == "si")
    parcial = sum(1 for s in r.senales if s.tenemos == "parcial")
    no = sum(1 for s in r.senales if s.tenemos == "no")
    r.resumen = f"{len(r.senales)} señales externas. Las tenemos: {tenemos}. Parcial: {parcial}. No las tenemos: {no}."
    return r
