from radares.fuentes.competencia import Competidor, DatosCompetencia, extraer_banners
from radares.fuentes.ga4 import DatosGA4, ItemMetricas, TerminoBusqueda, desde_csv as ga4_csv
from radares.fuentes.meli import DatosMeli, PublicacionMeli, ResultadoConsulta, parsear_listado, parsear_preguntas
from radares.fuentes.trends import ConsultaRelacionada, DatosTrends, InteresSemilla, desde_csv as trends_csv
from radares.catalogo import Producto
from radares.radar_externo import radar_demanda_externa
from radares.radar_interno import radar_demanda_interna
from radares.radar_oferta import radar_oferta_externa


def _items():
    items = []
    for i in range(12):
        items.append(ItemMetricas(f"Producto {i}", "Nike", "running", vistas=500 + i * 50, carrito=40, compras=10))  # CR ~2%
    items.append(ItemMetricas("574 Classic", "New Balance", "lifestyle", vistas=120, carrito=30, compras=12))  # CR 10%, pocas vistas
    items.append(ItemMetricas("Gel-Kayano 31", "Asics", "running", vistas=900, carrito=200, compras=5))       # carrito alto, no cierra
    return items


def test_radar_interno_detecta_subexpuesto_y_busquedas(catalogo):
    ga4 = DatosGA4(items=_items(), busquedas=[
        TerminoBusqueda("new balance 574", 80, 70, 9), TerminoBusqueda("crocs", 60, 55, 0), TerminoBusqueda("samba", 40, 38, 1),
    ])
    r = radar_demanda_interna(ga4, catalogo, min_vistas=20)
    tipos = {(s.tipo, s.sujeto) for s in r.senales}
    assert ("subexpuesto", "574 Classic") in tipos
    assert ("buscado_sin_catalogo", "crocs") in tipos
    assert ("buscado_subexpuesto", "new balance 574") in tipos
    assert ("carrito_sin_compra", "Gel-Kayano 31") in tipos
    assert any(s.tipo == "marca_subexpuesta" and s.sujeto == "New Balance" for s in r.senales)


def test_ga4_csv_export(tmp_path):
    p = tmp_path / "items.csv"
    p.write_text("# GA4 export\n# ----\nItem name,Item brand,Items viewed,Items added to cart,Items purchased,Item revenue\nSamba OG,Adidas,\"1,200\",90,30,\"194,700.00\"\n", encoding="utf-8")
    b = tmp_path / "busq.csv"
    b.write_text("Search term,Event count,Sessions\nsamba,55,50\n", encoding="utf-8")
    d = ga4_csv(str(p), str(b))
    assert d.items[0].vistas == 1200 and d.items[0].compras == 30 and d.items[0].ingresos == 194700.0
    assert d.busquedas[0].termino == "samba" and d.busquedas[0].sesiones == 50


def test_meli_parseo_listado_y_preguntas():
    html = """<div class="ui-search-search-result__quantity-results">1.234 resultados</div>
    <ol><li class="ui-search-layout__item"><div class="poly-card"><h3 class="poly-component__title"><a class="poly-component__title" href="https://articulo.mercadolibre.com.uy/MLU-1#pos">Championes Adidas Samba Og Hombre</a></h3>
    <span class="andes-money-amount__fraction">5.990</span><span>Más vendido</span><span>+50 vendidos</span></div></li></ol>"""
    total, pubs = parsear_listado(html)
    assert total == 1234 and pubs[0].titulo.startswith("Championes Adidas") and pubs[0].precio == 5990 and pubs[0].mas_vendido and pubs[0].vendidos == 50
    assert pubs[0].url == "https://articulo.mercadolibre.com.uy/MLU-1"
    n, qs = parsear_preguntas("""<div>Últimas 3 preguntas</div><ul class="ui-pdp-questions__questions-list">
    <li class="ui-pdp-questions__questions-list__question__item">Hola, tienen talle 44?</li>
    <li class="ui-pdp-questions__questions-list__question__item">Es original?</li></ul>""")
    assert n == 3 and qs[0] == "Hola, tienen talle 44?"


def test_trends_csv(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text("Categoría: Todas las categorías\n\nPRINCIPALES\nchampiones nike,100\nadidas samba,45\n\nEN AUMENTO\nnew balance 530,Breakout\n", encoding="utf-8")
    d = trends_csv(p)
    assert [(r.consulta, r.tipo) for r in d.relacionadas] == [("championes nike", "top"), ("adidas samba", "top"), ("new balance 530", "rising")]


def test_radar_externo_cruza_catalogo(catalogo):
    trends = DatosTrends(relacionadas=[ConsultaRelacionada("adidas", "adidas samba og", "Breakout", "rising"), ConsultaRelacionada("nike", "crocs uruguay", "250", "rising")],
                         interes=[InteresSemilla("new balance", 60, 30)], origen="Google Trends UY today 3-m")
    meli = DatosMeli(consultas=[ResultadoConsulta("championes adidas", 900, [
        PublicacionMeli("Championes Adidas Samba Og", 6990, "https://m/1", vendidos=120, mas_vendido=True, preguntas=["tienen 44?"], n_preguntas=15)])])
    r = radar_demanda_externa(trends, meli, catalogo)
    samba = [s for s in r.senales if "samba" in s.sujeto.lower()]
    assert samba and all(s.tenemos == "si" for s in samba)
    m = next(s for s in samba if s.fuente == "meli")
    assert m.precio_nuestro == 6490 and m.precio_afuera == 6990 and round(m.gap_pct, 3) == round((6490 - 6990) / 6990, 3)
    assert any(s.sujeto == "crocs uruguay" and s.tenemos == "no" for s in r.senales)
    assert any(s.sujeto == "new balance" and "sube 100%" in s.detalle for s in r.senales)


def test_extraer_banners():
    html = """<html><body>
    <div class="home-slider"><a href="/coleccion/pegasus-41"><img src="/img/hero.jpg" alt="Nike Pegasus 41 – nueva llegada"></a></div>
    <a href="/sale">Hasta 40% OFF en running</a>
    <a href="/carrito">Carrito</a><a href="https://instagram.com/x">IG</a>
    <a href="/marcas/nike"><img class="logo" alt="Nike"></a>
    </body></html>"""
    bs = extraer_banners(html, "https://www.lacancha.uy/")
    textos = [b.texto for b in bs]
    assert "Nike Pegasus 41 – nueva llegada" in textos
    assert "Hasta 40% OFF en running" in textos
    assert all("carrito" not in b.href for b in bs)
    assert "Nike" not in textos  # logo sin pista de banner no es banner


def test_radar_oferta_precio_gap(catalogo):
    comp = DatosCompetencia(competidores=[
        Competidor("La Cancha", "https://www.lacancha.uy", banners=[], productos=[Producto("Pegasus 41", "Nike", precio=8090, url="https://lc/p")]),
        Competidor("Menpi", "https://menpi.uy", error="no se pudo leer la home"),
    ])
    comp.competidores[0].banners = [type("B", (), {"texto": "Nike Pegasus 41 – nueva llegada", "href": "https://www.lacancha.uy/p", "tipo": "imagen"})()]
    r = radar_oferta_externa(comp, catalogo)
    prod = next(s for s in r.senales if s.tipo == "producto")
    assert prod.tenemos == "si" and prod.precio_nuestro == 8990 and round(prod.gap_pct, 3) == round(900 / 8090, 3)
    assert "+11%" in prod.detalle
    assert r.estado_sitios["Menpi"].startswith("no se pudo")
    assert "1/2 sitios" in r.resumen
