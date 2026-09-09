"""Demanda interna: qué convierte bien pero se ve poco (subexpuesto), y qué se busca en el sitio sin respuesta."""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import List

from .catalogo import Catalogo
from .fuentes.ga4 import DatosGA4, ItemMetricas


@dataclass
class Senal:
    tipo: str        # subexpuesto | buscado_sin_catalogo | buscado_subexpuesto | carrito_sin_compra | marca_subexpuesta
    sujeto: str
    detalle: str
    dato: dict = field(default_factory=dict)


@dataclass
class RadarInterno:
    senales: List[Senal] = field(default_factory=list)
    resumen: str = ""
    dias: int = 28


def _pct(xs: List[float], p: float) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    k = max(0, min(len(xs) - 1, int(round(p * (len(xs) - 1)))))
    return xs[k]


def detectar_subexpuestos(items: List[ItemMetricas], min_vistas: int = 20, max_n: int = 12) -> List[Senal]:
    base = [i for i in items if i.vistas >= min_vistas]
    if len(base) < 8:
        return []
    crs = [i.cr for i in base]
    vistas = [float(i.vistas) for i in base]
    cr_alto = max(_pct(crs, 0.75), statistics.median(crs) * 1.5)
    vistas_med = statistics.median(vistas)
    vistas_p75 = _pct(vistas, 0.75)
    cands = [i for i in base if i.cr >= cr_alto and i.cr > 0 and i.vistas <= vistas_med]
    cands.sort(key=lambda i: -(i.cr * i.compras))
    out = []
    for i in cands[:max_n]:
        out.append(
            Senal(
                "subexpuesto", i.nombre,
                f"{i.compras} compras sobre {i.vistas} vistas (CR {i.cr:.1%}, mediana del sitio {statistics.median(crs):.1%}). "
                f"Vistas por debajo de la mediana ({vistas_med:.0f}); los productos top tienen {vistas_p75:.0f}+.",
                {"marca": i.marca, "categoria": i.categoria, "vistas": i.vistas, "compras": i.compras, "cr": round(i.cr, 4), "ingresos": round(i.ingresos, 2)},
            )
        )
    return out


def detectar_carrito_sin_compra(items: List[ItemMetricas], min_vistas: int = 20, max_n: int = 5) -> List[Senal]:
    base = [i for i in items if i.vistas >= min_vistas and i.carrito >= 5]
    if len(base) < 8:
        return []
    tasas = [i.tasa_carrito for i in base]
    alto = _pct(tasas, 0.75)
    cands = [i for i in base if i.tasa_carrito >= alto and i.compras / i.carrito < 0.25]
    cands.sort(key=lambda i: -i.carrito)
    return [
        Senal(
            "carrito_sin_compra", i.nombre,
            f"{i.carrito} agregados al carrito, {i.compras} compras. Lo quieren y no cierra: talle, precio o envío.",
            {"marca": i.marca, "vistas": i.vistas, "carrito": i.carrito, "compras": i.compras},
        )
        for i in cands[:max_n]
    ]


def detectar_marcas(items: List[ItemMetricas], max_n: int = 4) -> List[Senal]:
    agg: dict[str, dict] = {}
    for i in items:
        m = (i.marca or "").strip()
        if not m:
            continue
        a = agg.setdefault(m, {"vistas": 0, "compras": 0, "ingresos": 0.0})
        a["vistas"] += i.vistas
        a["compras"] += i.compras
        a["ingresos"] += i.ingresos
    if len(agg) < 3:
        return []
    total_v = sum(a["vistas"] for a in agg.values()) or 1
    total_c = sum(a["compras"] for a in agg.values()) or 1
    out = []
    for m, a in agg.items():
        if a["vistas"] < 100 or a["compras"] < 3:
            continue
        share_v, share_c = a["vistas"] / total_v, a["compras"] / total_c
        if share_c >= share_v * 1.4:
            out.append(
                Senal(
                    "marca_subexpuesta", m,
                    f"{share_c:.0%} de las compras con {share_v:.0%} de las vistas. Convierte muy por encima de su exposición.",
                    {"vistas": a["vistas"], "compras": a["compras"], "share_vistas": round(share_v, 3), "share_compras": round(share_c, 3)},
                )
            )
    out.sort(key=lambda s: -(s.dato["share_compras"] / max(s.dato["share_vistas"], 1e-6)))
    return out[:max_n]


def cruzar_busquedas(ga4: DatosGA4, catalogo: Catalogo, subexpuestos: List[Senal], max_n: int = 12) -> List[Senal]:
    if not ga4.busquedas:
        return []
    top = sorted(ga4.busquedas, key=lambda b: -b.busquedas)[:60]
    nombres_sub = {s.sujeto.lower() for s in subexpuestos}
    out = []
    for b in top:
        estado, matches = catalogo.tenemos(b.termino) if len(catalogo) else ("sin_catalogo", [])
        if estado == "no":
            out.append(Senal("buscado_sin_catalogo", b.termino, f"{b.busquedas} búsquedas en {ga4.dias} días y ningún producto del catálogo coincide.", {"busquedas": b.busquedas, "sesiones": b.sesiones, "conversiones": b.conversiones}))
        elif estado in ("si", "parcial") and any(m.producto.nombre.lower() in nombres_sub for m in matches):
            out.append(Senal("buscado_subexpuesto", b.termino, f"{b.busquedas} búsquedas; el producto que responde convierte bien pero se ve poco: {matches[0].producto.nombre}.", {"busquedas": b.busquedas, "producto": matches[0].producto.nombre, "precio": matches[0].producto.precio}))
        elif b.conversiones is not None and b.sesiones and b.conversiones / b.sesiones >= 0.08 and estado != "sin_catalogo":
            out.append(Senal("buscado_subexpuesto", b.termino, f"{b.busquedas} búsquedas con {b.conversiones} conversiones sobre {b.sesiones} sesiones. Cierra bien; empujarlo fuera del buscador.", {"busquedas": b.busquedas, "sesiones": b.sesiones, "conversiones": b.conversiones}))
        if len(out) >= max_n:
            break
    return out


def radar_demanda_interna(ga4: DatosGA4, catalogo: Catalogo, min_vistas: int = 20) -> RadarInterno:
    r = RadarInterno(dias=ga4.dias)
    sub = detectar_subexpuestos(ga4.items, min_vistas)
    r.senales += sub
    r.senales += detectar_marcas(ga4.items)
    r.senales += cruzar_busquedas(ga4, catalogo, sub)
    r.senales += detectar_carrito_sin_compra(ga4.items, min_vistas)
    n_items = len(ga4.items)
    r.resumen = (
        f"{n_items} ítems con datos en {ga4.dias} días, {len(ga4.busquedas)} términos de búsqueda interna. "
        f"Subexpuestos: {len(sub)}. Marcas que convierten sobre su exposición: {sum(1 for s in r.senales if s.tipo == 'marca_subexpuesta')}. "
        f"Búsquedas sin respuesta en catálogo: {sum(1 for s in r.senales if s.tipo == 'buscado_sin_catalogo')}."
    )
    return r
