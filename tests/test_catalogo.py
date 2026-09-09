from pathlib import Path

from radares.catalogo import desde_csv, parsear_feed_google, parsear_precio, _productos_jsonld


def test_parsear_precio_formatos():
    assert parsear_precio("$ 5.990") == 5990
    assert parsear_precio("5.990,50") == 5990.5
    assert parsear_precio("5990.50") == 5990.5
    assert parsear_precio("UYU 1,234") == 1234
    assert parsear_precio("") is None


def test_csv_columnas_flexibles(tmp_path: Path):
    p = tmp_path / "c.csv"
    p.write_text("SKU;Nombre;Marca;Precio;Stock;URL\nA1;Samba OG;Adidas;$ 6.490;10;https://s/samba\nA2;;Nike;1;;\n", encoding="utf-8")
    cat = desde_csv(p)
    assert len(cat) == 1 and cat.productos[0].precio == 6490 and cat.productos[0].marca == "Adidas"


def test_feed_google():
    xml = b"""<?xml version="1.0"?><rss xmlns:g="http://base.google.com/ns/1.0"><channel>
    <item><title>Nike Pegasus 41</title><g:brand>Nike</g:brand><g:price>8990 UYU</g:price><g:sale_price>7990 UYU</g:sale_price><g:availability>in stock</g:availability><link>https://s/p</link><g:id>X1</g:id></item>
    </channel></rss>"""
    cat = parsear_feed_google(xml)
    assert len(cat) == 1 and cat.productos[0].precio == 7990 and cat.productos[0].sku == "X1"


def test_jsonld_product():
    html = """<html><head><script type="application/ld+json">{"@context":"https://schema.org","@type":"Product","name":"Adidas Samba OG","brand":{"@type":"Brand","name":"Adidas"},"offers":{"@type":"Offer","price":"6490","priceCurrency":"UYU","availability":"https://schema.org/InStock"}}</script></head></html>"""
    ps = _productos_jsonld(html, "https://x/p")
    assert ps[0].nombre == "Adidas Samba OG" and ps[0].precio == 6490 and ps[0].stock == "InStock"


def test_tenemos(catalogo):
    estado, m = catalogo.tenemos("Championes Adidas Samba OG Hombre")
    assert estado == "si" and m[0].producto.sku == "AD-SAMBA"
    assert catalogo.tenemos("crocs classic clog")[0] == "no"
    assert catalogo.tenemos("nike pegasus")[0] in ("si", "parcial")
