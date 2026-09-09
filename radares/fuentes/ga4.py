"""GA4 Data API: métricas por ítem y términos de búsqueda interna. Fallback: CSV exportado de GA4."""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from ..catalogo import normalizar, parsear_precio


@dataclass
class ItemMetricas:
    nombre: str
    marca: str = ""
    categoria: str = ""
    vistas: int = 0
    carrito: int = 0
    compras: int = 0
    ingresos: float = 0.0

    @property
    def cr(self) -> float:
        return self.compras / self.vistas if self.vistas else 0.0

    @property
    def tasa_carrito(self) -> float:
        return self.carrito / self.vistas if self.vistas else 0.0


@dataclass
class TerminoBusqueda:
    termino: str
    busquedas: int
    sesiones: int = 0
    conversiones: Optional[int] = None


@dataclass
class DatosGA4:
    items: List[ItemMetricas] = field(default_factory=list)
    busquedas: List[TerminoBusqueda] = field(default_factory=list)
    dias: int = 28
    origen: str = ""


# ------------------------------------------------------------- API oficial
def _cliente(credenciales: str):
    from google.analytics.data_v1beta import BetaAnalyticsDataClient

    if credenciales:
        from google.oauth2 import service_account

        creds = service_account.Credentials.from_service_account_file(
            credenciales, scopes=["https://www.googleapis.com/auth/analytics.readonly"]
        )
        return BetaAnalyticsDataClient(credentials=creds)
    return BetaAnalyticsDataClient()


def _run(client, property_id: str, dims: List[str], mets: List[str], dias: int, limit: int = 5000, filtro_evento: Optional[str] = None):
    from google.analytics.data_v1beta.types import (
        DateRange, Dimension, Filter, FilterExpression, Metric, OrderBy, RunReportRequest,
    )

    req = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[Dimension(name=d) for d in dims],
        metrics=[Metric(name=m) for m in mets],
        date_ranges=[DateRange(start_date=f"{dias}daysAgo", end_date="yesterday")],
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name=mets[0]), desc=True)],
        limit=limit,
    )
    if filtro_evento:
        req.dimension_filter = FilterExpression(
            filter=Filter(field_name="eventName", string_filter=Filter.StringFilter(value=filtro_evento))
        )
    resp = client.run_report(req)
    filas = []
    for r in resp.rows:
        d = {dims[i]: r.dimension_values[i].value for i in range(len(dims))}
        for i, m in enumerate(mets):
            d[m] = r.metric_values[i].value
        filas.append(d)
    return filas


def desde_api(property_id: str, credenciales: str = "", dias: int = 28) -> DatosGA4:
    client = _cliente(credenciales)
    filas = _run(
        client, property_id,
        ["itemName", "itemBrand", "itemCategory"],
        ["itemsViewed", "itemsAddedToCart", "itemsPurchased", "itemRevenue"],
        dias,
    )
    items = [
        ItemMetricas(
            nombre=f["itemName"], marca=f.get("itemBrand", ""), categoria=f.get("itemCategory", ""),
            vistas=int(float(f["itemsViewed"] or 0)), carrito=int(float(f["itemsAddedToCart"] or 0)),
            compras=int(float(f["itemsPurchased"] or 0)), ingresos=float(f["itemRevenue"] or 0),
        )
        for f in filas
        if f["itemName"] and f["itemName"] != "(not set)"
    ]
    busquedas: List[TerminoBusqueda] = []
    intentos = (
        (["searchTerm"], ["eventCount", "sessions", "keyEvents"]),
        (["searchTerm"], ["eventCount", "sessions"]),
        (["searchTerm"], ["eventCount"]),
    )
    ultimo_error: Optional[Exception] = None
    for dims, mets in intentos:
        try:
            filas_b = _run(client, property_id, dims, mets, dias, limit=1000, filtro_evento="view_search_results")
        except Exception as e:  # noqa: BLE001 - combinaciones incompatibles según la propiedad
            ultimo_error = e
            continue
        for f in filas_b:
            t = f["searchTerm"].strip()
            if not t or t == "(not set)":
                continue
            busquedas.append(
                TerminoBusqueda(
                    termino=t, busquedas=int(float(f["eventCount"] or 0)),
                    sesiones=int(float(f.get("sessions", 0) or 0)),
                    conversiones=int(float(f["keyEvents"])) if "keyEvents" in f else None,
                )
            )
        break
    else:
        if ultimo_error:
            raise ultimo_error
    return DatosGA4(items=items, busquedas=busquedas, dias=dias, origen=f"GA4 API {property_id}")


# ------------------------------------------------------------- CSV exportado
_ITEM_COLS = {
    "nombre": ["item name", "itemname", "nombre del artículo", "nombre del articulo", "nombre"],
    "marca": ["item brand", "itembrand", "marca del artículo", "marca"],
    "categoria": ["item category", "itemcategory", "categoría del artículo", "categoria"],
    "vistas": ["items viewed", "itemsviewed", "artículos vistos", "articulos vistos", "vistas"],
    "carrito": ["items added to cart", "itemsaddedtocart", "artículos añadidos al carrito", "carrito"],
    "compras": ["items purchased", "itemspurchased", "artículos comprados", "compras"],
    "ingresos": ["item revenue", "itemrevenue", "ingresos por artículo", "ingresos"],
}
_BUSQ_COLS = {
    "termino": ["search term", "searchterm", "término de búsqueda", "termino de busqueda", "termino"],
    "busquedas": ["event count", "eventcount", "recuento de eventos", "búsquedas", "busquedas", "events"],
    "sesiones": ["sessions", "sesiones"],
    "conversiones": ["key events", "keyevents", "conversions", "conversiones"],
}


def _leer_csv(path: str | Path) -> List[dict]:
    texto = Path(path).read_text(encoding="utf-8-sig")
    # Las exportaciones de GA4 traen un encabezado de comentarios con '#'; se salta.
    lineas = [l for l in texto.splitlines() if l and not l.startswith("#")]
    try:
        dialecto = csv.Sniffer().sniff("\n".join(lineas[:5]), delimiters=",;\t")
    except csv.Error:
        dialecto = csv.excel
    return list(csv.DictReader(lineas, dialect=dialecto))


def _col(fila: dict, mapa: dict, nombre: str) -> str:
    claves = {normalizar(k): k for k in fila.keys()}
    for alias in mapa[nombre]:
        k = claves.get(normalizar(alias))
        if k is not None and fila[k] not in (None, ""):
            return str(fila[k]).strip()
    return ""


def _entero(v: str) -> int:
    p = parsear_precio(v)
    return int(p) if p is not None else 0


def desde_csv(items_csv: Optional[str], busquedas_csv: Optional[str], dias: int = 28) -> DatosGA4:
    items, busquedas = [], []
    if items_csv:
        for r in _leer_csv(items_csv):
            n = _col(r, _ITEM_COLS, "nombre")
            if not n:
                continue
            items.append(
                ItemMetricas(
                    nombre=n, marca=_col(r, _ITEM_COLS, "marca"), categoria=_col(r, _ITEM_COLS, "categoria"),
                    vistas=_entero(_col(r, _ITEM_COLS, "vistas")), carrito=_entero(_col(r, _ITEM_COLS, "carrito")),
                    compras=_entero(_col(r, _ITEM_COLS, "compras")),
                    ingresos=parsear_precio(_col(r, _ITEM_COLS, "ingresos")) or 0.0,
                )
            )
    if busquedas_csv:
        for r in _leer_csv(busquedas_csv):
            t = _col(r, _BUSQ_COLS, "termino")
            if not t:
                continue
            conv = _col(r, _BUSQ_COLS, "conversiones")
            busquedas.append(
                TerminoBusqueda(
                    termino=t, busquedas=_entero(_col(r, _BUSQ_COLS, "busquedas")),
                    sesiones=_entero(_col(r, _BUSQ_COLS, "sesiones")), conversiones=_entero(conv) if conv else None,
                )
            )
    origen = ", ".join(Path(p).name for p in (items_csv, busquedas_csv) if p)
    return DatosGA4(items=items, busquedas=busquedas, dias=dias, origen=f"CSV {origen}")


def cargar_ga4(conf: dict, items_csv: Optional[str] = None, busquedas_csv: Optional[str] = None) -> DatosGA4:
    if items_csv or busquedas_csv:
        return desde_csv(items_csv, busquedas_csv, int(conf.get("dias", 28)))
    if not conf.get("property_id"):
        raise RuntimeError("GA4 sin configurar: falta property_id (fuentes.toml o GA4_PROPERTY_ID), o pasá --ga4-items/--ga4-busquedas.")
    return desde_api(str(conf["property_id"]), conf.get("credenciales", ""), int(conf.get("dias", 28)))


# ------------------------------------------------------------- descubrimiento
def listar_propiedades(credenciales: str = "") -> List[dict]:
    """Lista cuentas y propiedades GA4 visibles para la credencial (Admin API, solo lectura)."""
    from google.analytics.admin import AnalyticsAdminServiceClient

    if credenciales:
        from google.oauth2 import service_account

        creds = service_account.Credentials.from_service_account_file(
            credenciales, scopes=["https://www.googleapis.com/auth/analytics.readonly"]
        )
        client = AnalyticsAdminServiceClient(credentials=creds)
    else:
        client = AnalyticsAdminServiceClient()
    out = []
    for cuenta in client.list_account_summaries():
        for prop in cuenta.property_summaries:
            out.append({
                "cuenta": cuenta.display_name,
                "propiedad": prop.display_name,
                "property_id": prop.property.split("/")[-1],
                "tipo": str(prop.property_type).replace("PropertyType.", ""),
            })
    return out
