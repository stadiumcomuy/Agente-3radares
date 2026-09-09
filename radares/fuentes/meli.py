"""MercadoLibre Uruguay: resultados por consulta y preguntas en publicaciones.

Con MELI_ACCESS_TOKEN usa la API (la búsqueda pública quedó restringida en 2024-2025).
Sin token lee las páginas públicas de listado y de producto.
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from . import guardar_html
from ..catalogo import parsear_precio
from ..config import HTTP_HEADERS, HTTP_TIMEOUT


@dataclass
class PublicacionMeli:
    titulo: str
    precio: Optional[float]
    url: str
    vendidos: Optional[int] = None
    mas_vendido: bool = False
    preguntas: List[str] = field(default_factory=list)
    n_preguntas: Optional[int] = None


@dataclass
class ResultadoConsulta:
    consulta: str
    total_resultados: Optional[int]
    publicaciones: List[PublicacionMeli]


@dataclass
class DatosMeli:
    consultas: List[ResultadoConsulta] = field(default_factory=list)
    origen: str = ""
    errores: List[str] = field(default_factory=list)


_DOMINIO = {"MLU": "listado.mercadolibre.com.uy", "MLA": "listado.mercadolibre.com.ar", "MLB": "lista.mercadolivre.com.br"}


def _slug(q: str) -> str:
    return re.sub(r"\s+", "-", q.strip().lower())


# ------------------------------------------------------------- páginas públicas
def parsear_listado(html: str) -> tuple[Optional[int], List[PublicacionMeli]]:
    soup = BeautifulSoup(html, "lxml")
    total = None
    q = soup.select_one(".ui-search-search-result__quantity-results")
    if q:
        n = re.sub(r"[^\d]", "", q.get_text())
        total = int(n) if n else None
    pubs: List[PublicacionMeli] = []
    for card in soup.select("li.ui-search-layout__item, div.poly-card, li.ui-search-result"):
        t = card.select_one("h2.ui-search-item__title, h3.poly-component__title, a.poly-component__title, h2.poly-box")
        if not t:
            continue
        titulo = t.get_text(" ", strip=True)
        a = t if t.name == "a" else card.select_one("a.poly-component__title, a.ui-search-link, a.ui-search-item__group__element, a[href]")
        url = a["href"].split("#")[0] if a and a.has_attr("href") else ""
        fr = card.select_one(".andes-money-amount__fraction")
        precio = parsear_precio(fr.get_text()) if fr else None
        texto = card.get_text(" ", strip=True).lower()
        mas_vendido = "más vendido" in texto or "mas vendido" in texto
        vend = re.search(r"(\d[\d.]*)\s*vendidos", texto)
        pubs.append(
            PublicacionMeli(
                titulo=titulo, precio=precio, url=url, mas_vendido=mas_vendido,
                vendidos=int(vend.group(1).replace(".", "")) if vend else None,
            )
        )
    return total, pubs


def parsear_preguntas(html: str) -> tuple[Optional[int], List[str]]:
    soup = BeautifulSoup(html, "lxml")
    preguntas = []
    for el in soup.select(
        ".ui-pdp-questions__questions-list__question__item, .ui-pdp-questions__questions-list__container-question, "
        "[class*='questions-list__question']"
    ):
        t = el.get_text(" ", strip=True)
        if t and t not in preguntas and len(t) < 300:
            preguntas.append(t)
    n = None
    m = re.search(r"Últimas\s+(\d+)\s+preguntas|(\d+)\s+preguntas", soup.get_text(" ", strip=True), re.I)
    if m:
        n = int(m.group(1) or m.group(2))
    if n is None and preguntas:
        n = len(preguntas)
    return n, preguntas[:12]


def desde_paginas(consultas: List[str], sitio: str = "MLU", max_items_preguntas: int = 4, pausa: float = 1.0,
                  sesion: Optional[requests.Session] = None) -> DatosMeli:
    s = sesion or requests.Session()
    dominio = _DOMINIO.get(sitio, _DOMINIO["MLU"])
    datos = DatosMeli(origen=f"MercadoLibre {sitio} (páginas públicas)")
    for q in consultas:
        url = f"https://{dominio}/{_slug(q)}"
        try:
            r = s.get(url, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
            r.raise_for_status()
            guardar_html(f"meli_listado_{_slug(q)}", r.text)
            total, pubs = parsear_listado(r.text)
            if not pubs:
                datos.errores.append(f"{q}: la página respondió pero no se reconocieron publicaciones (¿cambió el HTML o hay captcha?)")
        except requests.RequestException as e:
            datos.errores.append(f"{q}: {e}")
            continue
        for p in pubs[:max_items_preguntas]:
            if not p.url:
                continue
            try:
                time.sleep(pausa)
                rp = s.get(p.url, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
                if rp.ok:
                    guardar_html(f"meli_item_{_slug(q)}_{pubs.index(p)}", rp.text)
                    p.n_preguntas, p.preguntas = parsear_preguntas(rp.text)
            except requests.RequestException:
                continue
        datos.consultas.append(ResultadoConsulta(q, total, pubs[:30]))
        time.sleep(pausa)
    return datos


# ------------------------------------------------------------- API con token
def desde_api(consultas: List[str], token: str, sitio: str = "MLU", max_items_preguntas: int = 4,
              sesion: Optional[requests.Session] = None) -> DatosMeli:
    s = sesion or requests.Session()
    h = {"Authorization": f"Bearer {token}", **HTTP_HEADERS}
    datos = DatosMeli(origen=f"MercadoLibre {sitio} (API)")
    for q in consultas:
        try:
            r = s.get(f"https://api.mercadolibre.com/sites/{sitio}/search", params={"q": q, "limit": 30}, headers=h, timeout=HTTP_TIMEOUT)
            r.raise_for_status()
            j = r.json()
        except (requests.RequestException, ValueError) as e:
            datos.errores.append(f"{q}: {e}")
            continue
        pubs = [
            PublicacionMeli(
                titulo=it.get("title", ""), precio=parsear_precio(it.get("price")), url=it.get("permalink", ""),
                vendidos=it.get("sold_quantity"),
            )
            for it in j.get("results", [])
        ]
        for it, p in zip(j.get("results", [])[:max_items_preguntas], pubs):
            try:
                rq = s.get("https://api.mercadolibre.com/questions/search", params={"item": it.get("id"), "api_version": 4, "limit": 12},
                           headers=h, timeout=HTTP_TIMEOUT)
                if rq.ok:
                    jq = rq.json()
                    p.n_preguntas = jq.get("total")
                    p.preguntas = [x.get("text", "") for x in jq.get("questions", []) if x.get("text")]
            except (requests.RequestException, ValueError):
                continue
        datos.consultas.append(ResultadoConsulta(q, (j.get("paging") or {}).get("total"), pubs))
    return datos


def cargar_meli(conf: dict, consultas_extra: Optional[List[str]] = None) -> DatosMeli:
    consultas = list(dict.fromkeys([*(conf.get("consultas") or []), *(consultas_extra or [])]))[:12]
    if not consultas:
        raise RuntimeError("MELI sin consultas: configurá [meli].consultas en fuentes.toml.")
    token = os.environ.get("MELI_ACCESS_TOKEN", "")
    sitio = conf.get("sitio", "MLU")
    n = int(conf.get("max_items_preguntas", 4))
    if token:
        datos = desde_api(consultas, token, sitio, n)
        if datos.consultas:
            return datos
    return desde_paginas(consultas, sitio, n)
