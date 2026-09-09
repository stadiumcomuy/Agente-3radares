"""Orquesta las fuentes y arma la evidencia que recibe el analista. Cada fuente falla por separado."""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .catalogo import Catalogo, cargar_catalogo
from .config import FRENTE_LABEL
from .fuentes.competencia import cargar_competencia
from .fuentes.ga4 import cargar_ga4
from .fuentes.meli import cargar_meli
from .fuentes.trends import cargar_trends
from .radar_externo import RadarExterno, radar_demanda_externa
from .radar_interno import RadarInterno, radar_demanda_interna
from .radar_oferta import RadarOferta, radar_oferta_externa


@dataclass
class Evidencia:
    catalogo: Catalogo
    interno: Optional[RadarInterno] = None
    externo: Optional[RadarExterno] = None
    oferta: Optional[RadarOferta] = None
    estado: dict = field(default_factory=dict)

    def texto(self, max_senales: int = 30) -> str:
        partes = [f"<catalogo>\n{self.catalogo.resumen()}\n</catalogo>"]
        partes.append("<estado_fuentes>\n" + "\n".join(f"- {k}: {v}" for k, v in self.estado.items()) + "\n</estado_fuentes>")

        partes.append("<demanda_interna>")
        if self.interno:
            partes.append(self.interno.resumen)
            for s in self.interno.senales[:max_senales]:
                partes.append(f"- [{s.tipo}] {s.sujeto}: {s.detalle}")
        else:
            partes.append("Sin datos: GA4 no disponible en esta corrida.")
        partes.append("</demanda_interna>")

        partes.append("<demanda_externa>")
        if self.externo:
            partes.append(self.externo.resumen)
            for s in self.externo.senales[:max_senales]:
                extra = f" Tenemos: {s.tenemos}" + (f" ({s.producto_nuestro} a {s.precio_nuestro:.0f})" if s.producto_nuestro and s.precio_nuestro else f" ({s.producto_nuestro})" if s.producto_nuestro else "")
                if s.gap_pct is not None:
                    extra += f". Gap de precio: {'+' if s.gap_pct >= 0 else ''}{s.gap_pct:.0%} vs MELI"
                partes.append(f"- [{s.fuente}] {s.detalle}{extra}. Fuente: {', '.join(s.fuentes)}")
        else:
            partes.append("Sin datos: ni Trends ni MercadoLibre disponibles en esta corrida.")
        partes.append("</demanda_externa>")

        partes.append("<oferta_externa>")
        if self.oferta:
            partes.append(self.oferta.resumen)
            for k, v in self.oferta.estado_sitios.items():
                partes.append(f"  sitio {k}: {v}")
            for s in self.oferta.senales[:max_senales * 2]:
                extra = f" Tenemos: {s.tenemos}" + (f" ({s.producto_nuestro})" if s.producto_nuestro and s.tipo == "banner" else "")
                partes.append(f"- [{s.tipo}] {s.detalle}{extra}." + (f" URL: {s.url}" if s.url else ""))
        else:
            partes.append("Sin datos: no se leyó ningún competidor.")
        partes.append("</oferta_externa>")
        return "\n".join(partes)


def _intentar(nombre: str, fn: Callable, estado: dict, log):
    try:
        out = fn()
        return out
    except Exception as e:  # noqa: BLE001 - cada fuente cae sola, el informe lo dice
        estado[nombre] = f"caída: {type(e).__name__}: {str(e)[:160]}"
        log(f"[radares] {nombre}: {estado[nombre]}")
        return None


def recolectar(
    conf: dict,
    frentes: List[str],
    *,
    catalogo_csv: Optional[str] = None,
    ga4_items: Optional[str] = None,
    ga4_busquedas: Optional[str] = None,
    trends_csv: Optional[str] = None,
    log: Callable[[str], None] = lambda m: print(m, file=sys.stderr),
) -> Evidencia:
    estado: dict = {}
    catalogo = _intentar("catálogo", lambda: cargar_catalogo(conf["catalogo"], catalogo_csv), estado, log) or Catalogo([], "caído")
    estado.setdefault("catálogo", catalogo.resumen())
    ev = Evidencia(catalogo=catalogo, estado=estado)

    ga4 = None
    if "demanda_interna" in frentes:
        log("[radares] leyendo GA4…")
        ga4 = _intentar("GA4", lambda: cargar_ga4(conf["ga4"], ga4_items, ga4_busquedas), estado, log)
        if ga4:
            estado["GA4"] = f"{ga4.origen}: {len(ga4.items)} ítems, {len(ga4.busquedas)} términos"
            ev.interno = radar_demanda_interna(ga4, catalogo, int(conf["ga4"].get("min_vistas", 20)))

    if "demanda_externa" in frentes:
        semillas_extra = [b.termino for b in sorted(ga4.busquedas, key=lambda b: -b.busquedas)[:6]] if ga4 else []
        semillas_extra += catalogo.marcas()[:8]
        log("[radares] leyendo Google Trends…")
        trends = _intentar("Trends", lambda: cargar_trends(conf["trends"], semillas_extra, trends_csv), estado, log)
        if trends:
            estado["Trends"] = f"{trends.origen}: {len(trends.relacionadas)} consultas relacionadas, {len(trends.interes)} series" + (f"; errores: {len(trends.errores)} ({trends.errores[0][:90]})" if trends.errores else "")
        log("[radares] leyendo MercadoLibre…")
        meli = _intentar("MercadoLibre", lambda: cargar_meli(conf["meli"], semillas_extra[:4]), estado, log)
        if meli:
            n_pubs = sum(len(c.publicaciones) for c in meli.consultas)
            estado["MercadoLibre"] = f"{meli.origen}: {len(meli.consultas)} consultas, {n_pubs} publicaciones" + (f"; avisos: {len(meli.errores)} ({meli.errores[0][:90]})" if meli.errores else "")
        if trends or meli:
            ev.externo = radar_demanda_externa(trends, meli, catalogo)

    if "oferta_externa" in frentes:
        log("[radares] leyendo competencia…")
        comp = _intentar("Competencia", lambda: cargar_competencia(conf["competencia"]), estado, log)
        if comp:
            ev.oferta = radar_oferta_externa(comp, catalogo)
            estado["Competencia"] = ev.oferta.resumen
    return ev


def etiqueta_frentes(frentes: List[str]) -> str:
    return ", ".join(FRENTE_LABEL[f] for f in frentes)
