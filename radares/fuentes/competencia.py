"""Competencia: qué bombean en sus sitios. Banners de la home, landings a las que apuntan y productos con precio (JSON-LD)."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from . import guardar_html
from ..catalogo import Producto, _productos_jsonld
from ..config import HTTP_HEADERS, HTTP_TIMEOUT

_PISTAS_BANNER = re.compile(r"banner|slider|slide|carousel|carrusel|hero|promo|destacad|campaign|campana|home-", re.I)
_PISTAS_TEXTO = re.compile(r"\d{1,2}\s?%|oferta|sale|descuento|nuev[oa]|lanzamiento|últim|ultim|liquidaci|exclusiv|cuotas|envío gratis|envio gratis", re.I)
_RUIDO = re.compile(r"cart|carrito|login|ingres|cuenta|registr|whatsapp|facebook|instagram|youtube|tiktok|mailto:|tel:|javascript:|#", re.I)


@dataclass
class Banner:
    texto: str
    href: str
    tipo: str  # imagen | texto


@dataclass
class Competidor:
    nombre: str
    url: str
    banners: List[Banner] = field(default_factory=list)
    productos: List[Producto] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class DatosCompetencia:
    competidores: List[Competidor] = field(default_factory=list)
    origen: str = "sitios de competidores"


def _mismo_dominio(base: str, href: str) -> bool:
    b, h = urlparse(base).netloc.replace("www.", ""), urlparse(href).netloc.replace("www.", "")
    return h == "" or h == b


def extraer_banners(html: str, base: str) -> List[Banner]:
    soup = BeautifulSoup(html, "lxml")
    vistos = set()
    out: List[Banner] = []

    def agregar(texto: str, href: str, tipo: str):
        texto = re.sub(r"\s+", " ", texto or "").strip()
        href = urljoin(base, href) if href else ""
        if href and (_RUIDO.search(href) or not _mismo_dominio(base, href)):
            href = ""
        if not texto and not href:
            return
        clave = (texto.lower(), href)
        if clave in vistos or len(texto) > 200:
            return
        vistos.add(clave)
        out.append(Banner(texto, href, tipo))

    # 1) imágenes con alt dentro de links (banners clásicos)
    for img in soup.find_all("img"):
        alt = (img.get("alt") or img.get("title") or "").strip()
        a = img.find_parent("a")
        clase = " ".join(filter(None, [*(img.get("class") or []), *((a.get("class") or []) if a else []), *[" ".join(p.get("class") or []) for p in img.parents if p.name in ("div", "section", "li")][:4]]))
        es_banner = bool(_PISTAS_BANNER.search(clase)) or bool(_PISTAS_BANNER.search(str(img.get("src", "")) + str(img.get("data-src", ""))))
        if a and (es_banner or alt):
            if es_banner or _PISTAS_TEXTO.search(alt):
                agregar(alt, a.get("href", ""), "imagen")
    # 2) bloques con clases de banner/slider/promo: texto + primer link
    for el in soup.find_all(["section", "div", "li", "a"], class_=_PISTAS_BANNER):
        texto = el.get_text(" ", strip=True)
        if not texto or len(texto) > 200:
            continue
        a = el if el.name == "a" else el.find("a", href=True)
        agregar(texto, a.get("href", "") if a else "", "texto")
    # 3) links cuyo texto huele a promoción
    for a in soup.find_all("a", href=True):
        t = a.get_text(" ", strip=True)
        if t and len(t) < 120 and _PISTAS_TEXTO.search(t):
            agregar(t, a["href"], "texto")
    return out[:60]


def _leer(s: requests.Session, url: str, etiqueta: str = "") -> tuple[Optional[str], str]:
    """Devuelve (html, motivo). motivo describe el fallo cuando html es None."""
    try:
        r = s.get(url, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
    except requests.RequestException as e:
        return None, f"{type(e).__name__}"
    if not r.ok:
        return None, f"HTTP {r.status_code}"
    if "text/html" not in r.headers.get("content-type", "text/html"):
        return None, f"content-type {r.headers.get('content-type')}"
    if etiqueta:
        guardar_html(etiqueta, r.text)
    return r.text, ""


def leer_competidor(nombre: str, url: str, max_links: int = 8, pausa: float = 0.8, sesion: Optional[requests.Session] = None) -> Competidor:
    s = sesion or requests.Session()
    comp = Competidor(nombre=nombre, url=url)
    html, motivo = _leer(s, url, f"competidor_{nombre}_home")
    if html is None:
        comp.error = f"no se pudo leer la home ({motivo})"
        return comp
    comp.banners = extraer_banners(html, url)
    comp.productos = _productos_jsonld(html, url)
    hrefs = []
    for b in comp.banners:
        if b.href and b.href not in hrefs and b.href.rstrip("/") != url.rstrip("/"):
            hrefs.append(b.href)
    for h in hrefs[:max_links]:
        time.sleep(pausa)
        page, _ = _leer(s, h)
        if page:
            comp.productos.extend(_productos_jsonld(page, h))
    vistos = set()
    unicos = []
    for p in comp.productos:
        k = (p.nombre.lower(), p.precio)
        if k not in vistos:
            vistos.add(k)
            unicos.append(p)
    comp.productos = unicos[:150]
    return comp


def cargar_competencia(conf: dict) -> DatosCompetencia:
    sitios = conf.get("sitios") or []
    if not sitios:
        raise RuntimeError("Competencia sin configurar: agregá [competencia].sitios en fuentes.toml.")
    datos = DatosCompetencia()
    for sitio in sitios:
        datos.competidores.append(leer_competidor(sitio["nombre"], sitio["url"], int(conf.get("max_links", 8))))
    return datos
