"""Google Trends vía pytrends (no oficial, puede devolver 429). Fallback: CSV de 'consultas relacionadas' exportado."""
from __future__ import annotations

import csv
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class ConsultaRelacionada:
    semilla: str
    consulta: str
    valor: str  # "Breakout" o número
    tipo: str   # rising | top


@dataclass
class InteresSemilla:
    semilla: str
    promedio_reciente: float
    promedio_previo: float

    @property
    def variacion(self) -> float:
        if self.promedio_previo <= 0:
            return 0.0 if self.promedio_reciente <= 0 else 1.0
        return (self.promedio_reciente - self.promedio_previo) / self.promedio_previo


@dataclass
class DatosTrends:
    relacionadas: List[ConsultaRelacionada] = field(default_factory=list)
    interes: List[InteresSemilla] = field(default_factory=list)
    origen: str = ""
    errores: List[str] = field(default_factory=list)


def desde_pytrends(semillas: List[str], geo: str = "UY", periodo: str = "today 3-m", pausa: float = 1.5) -> DatosTrends:
    from pytrends.request import TrendReq

    tr = TrendReq(hl="es-UY", tz=180, timeout=(5, 20), retries=2, backoff_factor=0.5)
    datos = DatosTrends(origen=f"Google Trends {geo} {periodo}")
    semillas = [s.strip() for s in semillas if s.strip()]
    for i in range(0, len(semillas), 5):
        lote = semillas[i : i + 5]
        try:
            tr.build_payload(lote, timeframe=periodo, geo=geo)
            iot = tr.interest_over_time()
            if iot is not None and not iot.empty:
                n = len(iot)
                corte = max(1, n - 4)
                for s in lote:
                    if s in iot.columns:
                        rec = float(iot[s].iloc[corte:].mean())
                        prev = float(iot[s].iloc[:corte].mean()) if corte > 0 else 0.0
                        datos.interes.append(InteresSemilla(s, rec, prev))
            rq = tr.related_queries()
            for s in lote:
                bloque = rq.get(s) or {}
                for tipo in ("rising", "top"):
                    df = bloque.get(tipo)
                    if df is None or getattr(df, "empty", True):
                        continue
                    for _, fila in df.head(10).iterrows():
                        datos.relacionadas.append(ConsultaRelacionada(s, str(fila["query"]), str(fila["value"]), tipo))
        except Exception as e:  # noqa: BLE001 - pytrends falla seguido (429); se registra y se sigue
            datos.errores.append(f"{', '.join(lote)}: {type(e).__name__}: {e}")
        time.sleep(pausa)
    return datos


def desde_csv(path: str | Path, semilla: str = "export") -> DatosTrends:
    """CSV exportado de trends.google.com ('Consultas relacionadas'). Formato: encabezado libre, luego 'consulta,valor'."""
    texto = Path(path).read_text(encoding="utf-8-sig")
    datos = DatosTrends(origen=f"CSV Trends {Path(path).name}")
    tipo = "top"
    for linea in texto.splitlines():
        l = linea.strip()
        if not l:
            continue
        bajo = l.lower()
        if bajo.startswith(("top", "principales")):
            tipo = "top"
            continue
        if bajo.startswith(("rising", "aumento", "en aumento")):
            tipo = "rising"
            continue
        partes = next(csv.reader([l]))
        if len(partes) >= 2 and partes[0].lower() not in ("query", "consulta"):
            datos.relacionadas.append(ConsultaRelacionada(semilla, partes[0].strip(), partes[1].strip(), tipo))
    return datos


def cargar_trends(conf: dict, semillas_extra: Optional[List[str]] = None, csv_path: Optional[str] = None) -> DatosTrends:
    if csv_path:
        return desde_csv(csv_path)
    semillas = list(dict.fromkeys([*(conf.get("semillas") or []), *(semillas_extra or [])]))[:20]
    if not semillas:
        raise RuntimeError("Trends sin semillas: configurá [trends].semillas en fuentes.toml.")
    return desde_pytrends(semillas, conf.get("geo", "UY"), conf.get("periodo", "today 3-m"))
