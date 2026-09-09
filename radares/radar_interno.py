"""Demanda interna: qué convierte bien pero se ve poco (subexpuesto), y qué se busca en el sitio sin respuesta."""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from typing import List

from .catalogo import Catalogo
from .fuentes.ga4 import DatosGA4, ItemMetricas

# "Championes de Hombre Adidas Galaxy 7 M - Negro - Blanco Talle 42 (08.5 USA)" -> sin " Talle 42 (08.5 USA)"
_TALLE = re.compile(r"\s+talle\s+\S+(\s*\([^)]*\))?\s*$", re.I)


def nombre_producto(nombre: str) -> str:
    return _TALLE.sub("", nombre).strip()


def agrupar_por_producto(items: List[ItemMetricas]) -> List[ItemMetricas]:
    """Suma las variantes por talle en un solo ítem por producto y color."""
    agg: dict[str, ItemMetricas] = {}
    for i in items:
        k = nombre_producto(i.nombre)
        a = agg.get(k)
        if a is None:
            agg[k] = ItemMetricas(k, i.marca, i.categoria, i.vistas, i.carrito, i.compras, i.ingresos)
        else:
            a.vistas += i.vistas
            a.carrito += i.carrito
            a.compras += i.compras
            a.ingresos += i.ingresos
    return list(agg.values())


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


def detectar_subexpuestos(items: List[ItemMetricas], min_vistas: int = 20, max_n: int = 12, min_compras: int = 3) -> List[Senal]:
    # Se excluyen add-ons de checkout (más compras que vistas) y se compara contra la conversión global del sitio.
    base = [i for i in items if i.vistas >= min_vistas and i.compras <= i.vistas]
    if len(base) < 8:
        return []
    cr_global = sum(i.compras for i in base) / max(1, sum(i.vistas for i in base))
    con_ventas = [float(i.vistas) for i in base if i.compras >= 2]
    if len(con_ventas) < 5:
        return []
    vistas_med = statistics.median(con_ventas)
    vistas_p75 = _pct(con_ventas, 0.75)
    cands = [i for i in base if i.compras >= min_compras and i.cr >= max(2 * cr_global, 0.02) and i.vistas <= vistas_med]
    cands.sort(key=lambda i: -(i.cr * i.compras))
    out = []
    for i in cands[:max_n]:
        out.append(
            Senal(
                "subexpuesto", i.nombre,
                f"{i.compras} compras sobre {i.vistas} vistas (CR {i.cr:.1%}; el sitio convierte {cr_global:.1%} vista a compra). "
                f"Vistas por debajo de la mediana de los productos que venden ({vistas_med:.0f}); el cuartil alto tiene {vistas_p75:.0f}+.",
                {"marca": i.marca, "categoria": i.categoria, "vistas": i.vistas, "compras": i.compras, "cr": round(i.cr, 4), "ingresos": round(i.ingresos, 2)},
            )
        )
    return out


def detectar_carrito_sin_compra(items: List[ItemMetricas], catalogo: Catalogo, min_carrito: int = 20, max_n: int = 6) -> List[Senal]:
    """A nivel talle: lo agregan al carrito y no cierra. Se cruza con la disponibilidad del feed."""
    cands = [i for i in items if i.carrito >= min_carrito and i.compras / i.carrito < 0.1]
    cands.sort(key=lambda i: -i.carrito)
    out = []
    for i in cands[:max_n]:
        stock = ""
        if len(catalogo):
            m = catalogo.buscar(i.nombre, umbral=90, max_n=1)
            if m and m[0].producto.stock:
                stock = f" Feed: {m[0].producto.stock}" + (f", precio {m[0].producto.precio:.0f}" if m[0].producto.precio else "") + "."
        out.append(
            Senal(
                "carrito_sin_compra", i.nombre,
                f"{i.carrito} agregados al carrito, {i.compras} compras, {i.vistas} vistas. Lo quieren y no cierra.{stock}",
                {"marca": i.marca, "vistas": i.vistas, "carrito": i.carrito, "compras": i.compras, "stock_feed": stock.strip()},
            )
        )
    return out


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
        share_v, share_c = a["vistas"] / total_v, a["compras"] / total_c
        if a["vistas"] < 200 or a["compras"] < 10 or share_v < 0.003:
            continue
        if share_c >= share_v * 1.4:
            out.append(
                Senal(
                    "marca_subexpuesta", m,
                    f"{share_c:.1%} de las compras con {share_v:.1%} de las vistas ({a['compras']} compras). Convierte muy por encima de su exposición.",
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
    out = [Senal("top_busquedas", "términos más buscados", ", ".join(f"{b.termino} ({b.busquedas})" for b in top[:25]), {})]
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
    productos = agrupar_por_producto(ga4.items)
    sub = detectar_subexpuestos(productos, min_vistas)
    r.senales += sub
    r.senales += detectar_marcas(productos)
    r.senales += cruzar_busquedas(ga4, catalogo, sub)
    r.senales += detectar_carrito_sin_compra(ga4.items, catalogo)
    n_items = len(ga4.items)
    r.resumen = (
        f"{n_items} variantes ({len(productos)} productos) con datos en {ga4.dias} días, {len(ga4.busquedas)} términos de búsqueda interna. "
        f"Subexpuestos: {len(sub)}. Marcas que convierten sobre su exposición: {sum(1 for s in r.senales if s.tipo == 'marca_subexpuesta')}. "
        f"Búsquedas sin respuesta en catálogo: {sum(1 for s in r.senales if s.tipo == 'buscado_sin_catalogo')}."
    )
    return r
