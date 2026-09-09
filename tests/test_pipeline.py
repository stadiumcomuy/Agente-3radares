import json

import pytest

from radares.analizar import analizar
from radares.aprender import aplicar_aprendizaje, destilar
from radares.cliente import RechazoError
from radares.memoria import ahora_iso
from radares.recolectar import Evidencia
from radares.render import render_informe
from radares.schema import Corrida, Informe
from tests.conftest import INFORME_EJEMPLO, ClienteFalso, mensaje_falso


def test_informe_valida_total_e_ids():
    inf = Informe.model_validate(INFORME_EJEMPLO)
    assert [o.id for o in inf.oportunidades()] == ["DI-1", "DI-2", "DE-1", "OE-1"]
    assert inf.apuesta().id == "DI-1"
    malo = json.loads(json.dumps(INFORME_EJEMPLO))
    malo["frentes"][0]["oportunidades"] = []
    malo["frentes"][1]["oportunidades"] = []
    with pytest.raises(Exception):
        Informe.model_validate(malo)  # solo 1 oportunidad


def test_render_por_frente_sin_tablas():
    txt = render_informe(Informe.model_validate(INFORME_EJEMPLO), estado_fuentes={"GA4": "ok"})
    assert "|" not in txt
    for h in ("## Demanda interna", "## Demanda externa", "## Oferta externa", "## Apuesta: DI-1", "## Contestame"):
        assert h in txt
    assert "← APUESTA" in txt and "estamos 10% más caros que La Cancha" in txt


def test_analizar_con_web_y_pause_turn(informe_json):
    cliente = ClienteFalso([mensaje_falso("parcial", stop_reason="pause_turn", busquedas=2), mensaje_falso("x " + informe_json + " y", busquedas=1)])
    inf, uso = analizar(cliente, perfil="p", lecciones_txt="", corridas_txt="", evidencia="<demanda_interna>...</demanda_interna>", frentes_txt="los tres", hoy="2026-09-09")
    assert inf.apuesta().id == "DI-1" and uso["busquedas"] == 3
    kw = cliente.llamadas[0]
    assert kw["output_format"] is Informe and kw["fallbacks"] == "default" and kw["thinking"]["type"] == "adaptive"
    assert {t["name"] for t in kw["tools"]} == {"web_search", "web_fetch"}
    assert cliente.llamadas[1]["messages"][1]["role"] == "assistant"


def test_analizar_sin_web_y_rechazo(informe_json):
    cliente = ClienteFalso([mensaje_falso(informe_json)])
    analizar(cliente, perfil="p", lecciones_txt="", corridas_txt="", evidencia="e", frentes_txt="f", hoy="h", con_web=False)
    assert "tools" not in cliente.llamadas[0]
    with pytest.raises(RechazoError):
        analizar(ClienteFalso([mensaje_falso("", stop_reason="refusal")]), perfil="p", lecciones_txt="", corridas_txt="", evidencia="e", frentes_txt="f", hoy="h")


def test_evidencia_texto_con_fuentes_caidas(catalogo):
    ev = Evidencia(catalogo=catalogo, estado={"GA4": "caída: RuntimeError: sin property_id"})
    t = ev.texto()
    assert "GA4 no disponible" in t and "caída" in t and "5 productos" in t


def test_feedback_por_id(memoria_tmp):
    corrida = Corrida(id="20260909-1000-abcd", fecha=ahora_iso(), modelo="m", informe=Informe.model_validate(INFORME_EJEMPLO))
    memoria_tmp.guardar_corrida(corrida)
    previa = memoria_tmp.agregar_leccion("No sugerir Crocs.", "marca:Crocs", "viejo", "x")
    salida = {
        "lecciones": [
            {"regla": "La Cancha siempre está 10% más barata en Nike; diferenciar por talles, no igualar precio.", "aplica_a": "oferta_externa", "origen": "no puedo igualar", "refuerza_id": None},
            {"regla": "No sugerir Crocs.", "aplica_a": "marca:Crocs", "origen": "crocs no", "refuerza_id": previa.id},
        ],
        "resultados": [{"id": "DI-2", "resultado": "descartada", "nota": "no traigo Crocs"}, {"id": "ZZ-9", "resultado": "validada", "nota": "inválido"}],
        "respuesta_al_dueno": "Entendido.",
    }
    ext = destilar(ClienteFalso([mensaje_falso(json.dumps(salida, ensure_ascii=False))]), perfil="p", corrida=corrida, lecciones_txt="", feedback="crocs no; no puedo igualar")
    lineas = aplicar_aprendizaje(memoria_tmp, corrida, "texto", ext)
    assert len(memoria_tmp.cargar_lecciones()) == 2
    assert next(l for l in memoria_tmp.cargar_lecciones() if l.id == previa.id).peso == 2
    rec = memoria_tmp.cargar_corrida("20260909")
    assert [r.id for r in rec.feedback[0].resultados] == ["DI-2"]
    txt = memoria_tmp.corridas_como_texto()
    assert "DI-2" in txt and "descartada (no traigo Crocs)" in txt and "[apuesta]" in txt
    assert any("reforzada" in l for l in lineas)
