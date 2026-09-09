from radares import cli
from radares.memoria import ahora_iso
from radares.schema import Corrida, Informe
from tests.conftest import INFORME_EJEMPLO


def _run(argv):
    try:
        cli.main(argv)
    except SystemExit as e:
        return e.code
    return 0


def test_historial_ver_y_lecciones(memoria_tmp, capsys, monkeypatch):
    monkeypatch.setattr(cli, "Memoria", lambda: memoria_tmp)
    memoria_tmp.guardar_corrida(Corrida(id="20260909-1200-aaaa", fecha=ahora_iso(), modelo="m", informe=Informe.model_validate(INFORME_EJEMPLO), evidencia="<evidencia/>"))
    assert _run(["historial"]) == 0
    out = capsys.readouterr().out
    assert "20260909-1200-aaaa" in out and "DI-1" in out
    assert _run(["ver", "20260909", "--evidencia"]) == 0
    assert "<evidencia/>" in capsys.readouterr().out
    assert _run(["lecciones", "--agregar", "Nunca sugerir calzado formal."]) == 0
    lid = capsys.readouterr().out.split("[")[1].split("]")[0]
    assert _run(["lecciones", "--borrar", lid]) == 0


def test_fuentes_con_csv_sin_red(tmp_path, capsys, monkeypatch):
    cat = tmp_path / "cat.csv"
    cat.write_text("nombre,marca,precio\nSamba OG,Adidas,6490\n" + "".join(f"Producto {i},Nike,5000\n" for i in range(10)), encoding="utf-8")
    items = tmp_path / "items.csv"
    items.write_text("Item name,Item brand,Items viewed,Items added to cart,Items purchased,Item revenue\n"
                     + "".join(f"Producto {i},Nike,{500 + i * 10},40,10,50000\n" for i in range(10)) + "Samba OG,Adidas,100,30,12,70000\n", encoding="utf-8")
    monkeypatch.setattr(cli, "cargar_fuentes", lambda: {"catalogo": {}, "ga4": {"dias": 28, "min_vistas": 20}, "trends": {}, "meli": {}, "competencia": {}})
    assert _run(["fuentes", "--frente", "demanda_interna", "--catalogo", str(cat), "--ga4-items", str(items), "--detalle"]) == 0
    out = capsys.readouterr().out
    assert "GA4: CSV items.csv: 11 ítems" in out and "[subexpuesto] Samba OG" in out
