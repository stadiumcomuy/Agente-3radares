"""Oferta externa: qué bombea la competencia, si lo tenemos y a qué precio."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .catalogo import Catalogo
from .fuentes.competencia import DatosCompetencia


@dataclass
class SenalOferta:
    competidor: str
    tipo: str            # banner | producto
    sujeto: str
    tenemos: str
    detalle: str
    precio_nuestro: Optional[float] = None
    precio_competidor: Optional[float] = None
    producto_nuestro: str = ""
    url: str = ""

    @property
    def gap_pct(self) -> Optional[float]:
        if self.precio_nuestro and self.precio_competidor:
            return (self.precio_nuestro - self.precio_competidor) / self.precio_competidor
        return None


@dataclass
class RadarOferta:
    senales: List[SenalOferta] = field(default_factory=list)
    estado_sitios: dict = field(default_factory=dict)
    resumen: str = ""


def radar_oferta_externa(comp: DatosCompetencia, catalogo: Catalogo, max_banners: int = 12, max_productos: int = 15) -> RadarOferta:
    r = RadarOferta()
    for c in comp.competidores:
        r.estado_sitios[c.nombre] = c.error or f"{len(c.banners)} banners, {len(c.productos)} productos con precio"
        if c.error:
            continue
        for b in c.banners[:max_banners]:
            if not b.texto:
                continue
            estado, m = catalogo.tenemos(b.texto) if len(catalogo) else ("sin_catalogo", [])
            r.senales.append(
                SenalOferta(c.nombre, "banner", b.texto, estado, f"{c.nombre} bombea en home: \"{b.texto}\"" + (f" -> {b.href}" if b.href else ""),
                            m[0].producto.precio if m else None, None, m[0].producto.nombre if m else "", b.href)
            )
        con_precio = [p for p in c.productos if p.precio]
        for p in con_precio[:max_productos]:
            estado, m = catalogo.tenemos(f"{p.marca} {p.nombre}") if len(catalogo) else ("sin_catalogo", [])
            nuestro = m[0].producto.precio if m else None
            detalle = f"{c.nombre} destaca {p.marca + ' ' if p.marca else ''}{p.nombre} a {p.precio:.0f}."
            if nuestro:
                gap = (nuestro - p.precio) / p.precio
                detalle += f" Nosotros: {m[0].producto.nombre} a {nuestro:.0f} ({'+' if gap >= 0 else ''}{gap:.0%})."
            r.senales.append(SenalOferta(c.nombre, "producto", p.nombre, estado, detalle, nuestro, p.precio, m[0].producto.nombre if m else "", p.url))
    caros = sum(1 for s in r.senales if s.gap_pct is not None and s.gap_pct > 0.05)
    baratos = sum(1 for s in r.senales if s.gap_pct is not None and s.gap_pct < -0.05)
    leidos = sum(1 for c in comp.competidores if not c.error)
    r.resumen = (
        f"{leidos}/{len(comp.competidores)} sitios leídos. {sum(1 for s in r.senales if s.tipo == 'banner')} banners, "
        f"{sum(1 for s in r.senales if s.tipo == 'producto')} productos con precio. Comparables donde estamos más caros: {caros}; más baratos: {baratos}."
    )
    return r
