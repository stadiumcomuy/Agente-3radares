import json

import pytest

from radares.aprender import aplicar_aprendizaje, destilar
from radares.analizar import analizar
from radares.cliente import RechazoError
from radares.investigar import investigar
from radares.memoria import ahora_iso
from radares.schema import Corrida, Informe
from tests.conftest import INFORME_EJEMPLO, ClienteFalso, mensaje_falso


def test_investigar_maneja_pause_turn_y_cuenta_busquedas():
    cliente = ClienteFalso([
        mensaje_falso("parcial", stop_reason="pause_turn", busquedas=5),
        mensaje_falso("## Demanda interna\nhallazgo con fuente", busquedas=3),
    ])
    dossier, uso = investigar(
        cliente, perfil="perfil", lecciones_txt="", corridas_txt="", foco="todos", hoy="2026-09-09"
    )
    assert dossier.startswith("## Demanda interna")
    assert uso["busquedas"] == 8
    assert len(cliente.llamadas) == 2
    # la segunda llamada reenvía el turno pausado
    assert cliente.llamadas[1]["messages"][1]["role"] == "assistant"
    # herramienta web con ubicación en Uruguay y fallback server-side
    tool = cliente.llamadas[0]["tools"][0]
    assert tool["type"] == "web_search_20260209"
    assert tool["user_location"]["country"] == "UY"
    assert cliente.llamadas[0]["fallbacks"] == "default"
    assert cliente.llamadas[0]["thinking"]["type"] == "adaptive"


def test_investigar_sin_web_no_manda_tools_y_pasa_datos():
    cliente = ClienteFalso([mensaje_falso("## Demanda interna\nSIN FUENTE: x")])
    investigar(
        cliente, perfil="p", lecciones_txt="", corridas_txt="", foco="demanda_interna",
        hoy="2026-09-09", datos="producto,sesiones\nsamba,1200", con_web=False,
    )
    kw = cliente.llamadas[0]
    assert "tools" not in kw
    assert "<datos_internos>" in kw["messages"][0]["content"]
    assert "samba,1200" in kw["messages"][0]["content"]


def test_investigar_propaga_rechazo():
    cliente = ClienteFalso([mensaje_falso("", stop_reason="refusal")])
    with pytest.raises(RechazoError):
        investigar(cliente, perfil="p", lecciones_txt="", corridas_txt="", foco="todos", hoy="2026-09-09")


def test_analizar_parsea_json_con_texto_alrededor(informe_json):
    cliente = ClienteFalso([mensaje_falso("Acá va:\n" + informe_json + "\nfin")])
    informe, uso = analizar(
        cliente, perfil="p", lecciones_txt="", corridas_txt="", dossier="d", foco="todos", hoy="2026-09-09"
    )
    assert isinstance(informe, Informe)
    assert informe.apuesta().marca_sugerida == "On Running"
    assert cliente.llamadas[0]["output_format"] is Informe
    assert uso["output_tokens"] == 50


def test_feedback_genera_lecciones_y_resultados(memoria_tmp):
    corrida = Corrida(
        id="20260909-1000-abcd", fecha=ahora_iso(), foco="todos", modelo="m",
        informe=Informe.model_validate(INFORME_EJEMPLO),
    )
    memoria_tmp.guardar_corrida(corrida)
    previa = memoria_tmp.agregar_leccion("No sugerir Crocs.", "marca:Crocs", "feedback viejo", "x")

    salida = {
        "lecciones": [
            {"regla": "On Running ya fue ofrecida por un distribuidor argentino; priorizar contacto directo.",
             "aplica_a": "marca:On Running", "origen": "me la ofrecieron en junio", "refuerza_id": None},
            {"regla": "No sugerir Crocs.", "aplica_a": "marca:Crocs", "origen": "crocs no", "refuerza_id": previa.id},
        ],
        "resultados": [
            {"indice": 2, "resultado": "descartada", "nota": "Fila ya rotó"},
            {"indice": 9, "resultado": "validada", "nota": "índice inválido"},
        ],
        "respuesta_al_dueno": "Entendido. Próxima corrida sin Fila y con contacto directo a On.",
    }
    cliente = ClienteFalso([mensaje_falso(json.dumps(salida, ensure_ascii=False))])
    extraido = destilar(cliente, perfil="p", corrida=corrida, lecciones_txt=memoria_tmp.lecciones_como_texto(),
                        feedback="me la ofrecieron en junio; crocs no; Fila ya rotó")
    lineas = aplicar_aprendizaje(memoria_tmp, corrida, "texto", extraido)

    lecciones = memoria_tmp.cargar_lecciones()
    assert len(lecciones) == 2
    assert next(l for l in lecciones if l.id == previa.id).peso == 2
    recargada = memoria_tmp.cargar_corrida("20260909")
    assert len(recargada.feedback) == 1
    assert [r.indice for r in recargada.feedback[0].resultados] == [2]
    assert any("reforzada" in l for l in lineas) and any("nueva" in l for l in lineas)

    # la memoria inyectada en la próxima corrida refleja el estado
    txt = memoria_tmp.corridas_como_texto()
    assert "descartada (Fila ya rotó)" in txt
    assert "apuesta" in txt
    assert "[" + previa.id + "]" in memoria_tmp.lecciones_como_texto()
