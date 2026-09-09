import json

from radares import cli
from radares.memoria import ahora_iso
from radares.schema import Corrida, Informe
from tests.conftest import INFORME_EJEMPLO


def test_historial_y_ver(memoria_tmp, capsys, monkeypatch):
    monkeypatch.setattr(cli, "Memoria", lambda: memoria_tmp)
    corrida = Corrida(id="20260909-1200-aaaa", fecha=ahora_iso(), foco="todos", modelo="m",
                      informe=Informe.model_validate(INFORME_EJEMPLO), dossier="## dossier")
    memoria_tmp.guardar_corrida(corrida)

    try:
        cli.main(["historial"])
    except SystemExit as e:
        assert e.code == 0
    out = capsys.readouterr().out
    assert "20260909-1200-aaaa" in out and "On Running" in out

    try:
        cli.main(["ver", "20260909", "--dossier"])
    except SystemExit as e:
        assert e.code == 0
    assert "## dossier" in capsys.readouterr().out


def test_lecciones_manual(memoria_tmp, capsys, monkeypatch):
    monkeypatch.setattr(cli, "Memoria", lambda: memoria_tmp)
    try:
        cli.main(["lecciones", "--agregar", "Nunca sugerir calzado formal.", "--aplica-a", "general"])
    except SystemExit:
        pass
    out = capsys.readouterr().out
    assert "Agregada [L" in out
    lid = out.split("[")[1].split("]")[0]
    try:
        cli.main(["lecciones", "--borrar", lid])
    except SystemExit as e:
        assert e.code == 0
    assert "Borrada." in capsys.readouterr().out
