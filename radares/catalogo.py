"""Catálogo propio: carga desde CSV, feed de Google Merchant o sitemap + JSON-LD. Cruce difuso por nombre."""
from __future__ import annotations

import csv
import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional

import requests
from bs4 import BeautifulSoup
from rapidfuzz import fuzz

from .config import HTTP_HEADERS, HTTP_TIMEOUT


def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-z0-9 ]+", " ", t.lower())
    return re.sub(r"\s+", " ", t).strip()


def parsear_precio(v) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d,.]", "", str(v))
    if not s:
        return None
    # "1.234,50" -> 1234.50 ; "1234.50" -> 1234.50 ; "1,234" -> 1234
    if "," in s and "." in s:
        # El último separador es el decimal: "1.234,50" (es) o "1,234.50" (en)
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".") if len(s.split(",")[-1]) == 2 else s.replace(",", "")
    elif s.count(".") > 1 or (s.count(".") == 1 and len(s.split(".")[-1]) == 3):
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


@dataclass
class Producto:
    nombre: str
    marca: str = ""
    categoria: str = ""
    precio: Optional[float] = None
    stock: Optional[str] = None
    url: str = ""
    sku: str = ""

    @property
    def clave(self) -> str:
        return normalizar(f"{self.marca} {self.nombre}")


@dataclass
class Coincidencia:
    producto: Producto
    puntaje: int


@dataclass
class Catalogo:
    productos: List[Producto] = field(default_factory=list)
    origen: str = "vacío"

    def __len__(self) -> int:
        return len(self.productos)

    def marcas(self) -> List[str]:
        conteo: dict[str, int] = {}
        for p in self.productos:
            if p.marca:
                conteo[p.marca.strip()] = conteo.get(p.marca.strip(), 0) + 1
        return [m for m, _ in sorted(conteo.items(), key=lambda x: -x[1])]

    def buscar(self, texto: str, umbral: int = 78, max_n: int = 5) -> List[Coincidencia]:
        q = normalizar(texto)
        if not q or not self.productos:
            return []
        out = []
        for p in self.productos:
            s = fuzz.token_set_ratio(q, p.clave)
            if s >= umbral:
                out.append(Coincidencia(p, int(s)))
        out.sort(key=lambda c: -c.puntaje)
        return out[:max_n]

    def tenemos(self, texto: str) -> tuple[str, List[Coincidencia]]:
        """Devuelve ('si'|'parcial'|'no', coincidencias)."""
        fuertes = self.buscar(texto, umbral=85)
        if fuertes:
            return "si", fuertes
        debiles = self.buscar(texto, umbral=65)
        if debiles:
            return "parcial", debiles
        return "no", []

    def resumen(self, max_marcas: int = 15) -> str:
        if not self.productos:
            return "Catálogo vacío: no se pudo cruzar nada. Configurá [catalogo] en fuentes.toml."
        precios = [p.precio for p in self.productos if p.precio]
        rango = f", precios {min(precios):.0f}-{max(precios):.0f}" if precios else ""
        return f"{len(self.productos)} productos ({self.origen}{rango}). Marcas: {', '.join(self.marcas()[:max_marcas])}."


# ---------------------------------------------------------------- cargadores
_COLS = {
    "nombre": ["nombre", "name", "title", "producto", "product", "item name", "itemname"],
    "marca": ["marca", "brand", "item brand"],
    "categoria": ["categoria", "categoría", "category", "product_type", "item category"],
    "precio": ["precio", "price", "sale_price", "precio_venta"],
    "stock": ["stock", "availability", "disponibilidad", "quantity"],
    "url": ["url", "link", "enlace"],
    "sku": ["sku", "id", "codigo", "código", "item id", "item_id"],
}


def _col(fila: dict, nombre: str) -> str:
    claves = {normalizar(k): k for k in fila.keys()}
    for alias in _COLS[nombre]:
        k = claves.get(normalizar(alias))
        if k is not None and fila[k] not in (None, ""):
            return str(fila[k]).strip()
    return ""


def desde_csv(path: str | Path) -> Catalogo:
    path = Path(path)
    with path.open(encoding="utf-8-sig", newline="") as f:
        muestra = f.read(4096)
        f.seek(0)
        try:
            dialecto = csv.Sniffer().sniff(muestra, delimiters=",;\t")
        except csv.Error:
            dialecto = csv.excel
        filas = list(csv.DictReader(f, dialect=dialecto))
    productos = [
        Producto(
            nombre=_col(r, "nombre"), marca=_col(r, "marca"), categoria=_col(r, "categoria"),
            precio=parsear_precio(_col(r, "precio")), stock=_col(r, "stock") or None,
            url=_col(r, "url"), sku=_col(r, "sku"),
        )
        for r in filas
        if _col(r, "nombre")
    ]
    return Catalogo(productos, origen=f"csv {path.name}")


def desde_feed_google(fuente: str, sesion: Optional[requests.Session] = None) -> Catalogo:
    """Feed RSS/Atom de Google Merchant (namespace g:)."""
    if fuente.startswith("http"):
        s = sesion or requests.Session()
        r = s.get(fuente, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT * 3)
        r.raise_for_status()
        xml = r.content
    else:
        xml = Path(fuente).read_bytes()
    return parsear_feed_google(xml, origen="feed google")


def parsear_feed_google(xml: bytes, origen: str = "feed google") -> Catalogo:
    soup = BeautifulSoup(xml, "xml")
    productos = []
    for it in soup.find_all(["item", "entry"]):
        def g(*nombres):
            for n in nombres:
                el = it.find(n)
                if el and el.text.strip():
                    return el.text.strip()
            return ""
        nombre = g("title", "g:title")
        if not nombre:
            continue
        productos.append(
            Producto(
                nombre=nombre, marca=g("g:brand", "brand"), categoria=g("g:product_type", "product_type", "g:google_product_category"),
                precio=parsear_precio(g("g:sale_price", "sale_price") or g("g:price", "price")),
                stock=g("g:availability", "availability") or None, url=g("link", "g:link"), sku=g("g:id", "id"),
            )
        )
    return Catalogo(productos, origen=origen)


def _productos_jsonld(html: str, url: str) -> List[Producto]:
    soup = BeautifulSoup(html, "lxml")
    out: List[Producto] = []

    def visitar(obj):
        if isinstance(obj, list):
            for x in obj:
                visitar(x)
            return
        if not isinstance(obj, dict):
            return
        tipo = obj.get("@type", "")
        tipos = tipo if isinstance(tipo, list) else [tipo]
        if "Product" in tipos:
            ofertas = obj.get("offers") or {}
            if isinstance(ofertas, list):
                ofertas = ofertas[0] if ofertas else {}
            precio = ofertas.get("price") or ofertas.get("lowPrice")
            marca = obj.get("brand")
            if isinstance(marca, dict):
                marca = marca.get("name", "")
            out.append(
                Producto(
                    nombre=str(obj.get("name", "")).strip(), marca=str(marca or "").strip(),
                    categoria=str(obj.get("category", "") or ""), precio=parsear_precio(precio),
                    stock=str(ofertas.get("availability", "") or "").split("/")[-1] or None,
                    url=obj.get("url") or url, sku=str(obj.get("sku", "") or ""),
                )
            )
        for v in obj.values():
            if isinstance(v, (dict, list)):
                visitar(v)

    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            visitar(json.loads(tag.string or ""))
        except (json.JSONDecodeError, TypeError):
            continue
    return [p for p in out if p.nombre]


def _urls_sitemap(url: str, s: requests.Session, limite: int) -> List[str]:
    r = s.get(url, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    soup = BeautifulSoup(r.content, "xml")
    urls: List[str] = []
    for sm in soup.find_all("sitemap"):
        loc = sm.find("loc")
        if loc and len(urls) < limite:
            try:
                urls.extend(_urls_sitemap(loc.text.strip(), s, limite - len(urls)))
            except requests.RequestException:
                continue
    for u in soup.find_all("url"):
        loc = u.find("loc")
        if loc:
            urls.append(loc.text.strip())
    return urls[:limite]


def desde_sitemap(url: str, max_paginas: int = 400, hilos: int = 8) -> Catalogo:
    s = requests.Session()
    urls = _urls_sitemap(url, s, max_paginas)

    def leer(u: str) -> List[Producto]:
        try:
            r = s.get(u, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
            if r.ok:
                return _productos_jsonld(r.text, u)
        except requests.RequestException:
            pass
        return []

    productos: List[Producto] = []
    with ThreadPoolExecutor(max_workers=hilos) as ex:
        for lote in ex.map(leer, urls):
            productos.extend(lote)
    vistos = set()
    unicos = []
    for p in productos:
        k = (p.sku or p.url or p.nombre)
        if k not in vistos:
            vistos.add(k)
            unicos.append(p)
    return Catalogo(unicos, origen=f"sitemap ({len(urls)} páginas)")


def cargar_catalogo(conf: dict, override_csv: Optional[str] = None) -> Catalogo:
    if override_csv:
        return desde_csv(override_csv)
    if conf.get("csv"):
        return desde_csv(conf["csv"])
    if conf.get("feed_google"):
        return desde_feed_google(conf["feed_google"])
    if conf.get("sitemap"):
        return desde_sitemap(conf["sitemap"], int(conf.get("max_paginas", 400)))
    return Catalogo([], origen="sin configurar")
