import json
from types import SimpleNamespace

import pytest


@pytest.fixture
def memoria_tmp(tmp_path):
    from radares.memoria import Memoria
    return Memoria(tmp_path / "memoria")


def opp(id_, titulo, marca, tenemos="si", producto="", score=(3, 2, 4, 3), gap=None):
    i, e, c, u = score
    return {
        "id": id_, "titulo": titulo, "que_pasa": "Dato con número y fuente.", "por_que_es_grieta": "Brecha concreta.",
        "lo_tenemos": tenemos, "marca_sugerida": marca, "producto_o_termino": producto or titulo,
        "accion_minima": "Bombear en home 14 días.", "que_validar": "Rotación semanal.",
        "precio_nuestro": None, "precio_afuera": None, "gap_precio": gap, "fuentes": ["GA4"],
        "score": {"impacto": i, "esfuerzo": e, "confianza": c, "urgencia": u},
    }


INFORME_EJEMPLO = {
    "frentes": [
        {"frente": "demanda_interna", "lectura": "Dos productos convierten al doble de la mediana con la mitad de vistas.",
         "oportunidades": [opp("DI-1", "New Balance 574 talle 44 convierte y no se ve", "New Balance", score=(4, 1, 5, 4)),
                           opp("DI-2", "Buscan 'crocs' y no hay catálogo", "Crocs", tenemos="no", score=(2, 3, 3, 2))]},
        {"frente": "demanda_externa", "lectura": "MELI muestra preguntas repetidas por talle en Samba.",
         "oportunidades": [opp("DE-1", "Samba OG: preguntas por talle en MELI", "Adidas", gap="estamos 8% más baratos que MELI", score=(3, 2, 4, 3))]},
        {"frente": "oferta_externa", "lectura": "La Cancha bombea Nike Pegasus 41 en home.",
         "oportunidades": [opp("OE-1", "La Cancha empuja Pegasus 41 y estamos 10% más caros", "Nike", gap="estamos 10% más caros que La Cancha", score=(3, 2, 4, 4))]},
    ],
    "mejor_apuesta": "DI-1",
    "por_que_mejor_apuesta": "Esfuerzo 1, dato propio, se mide en una semana.",
    "preguntas_feedback": ["¿Tenés stock de 574 en 43-45?", "¿Ya pautaste Samba este mes?", "¿Cuál descartás sin dudar?"],
}


def mensaje_falso(texto: str, stop_reason: str = "end_turn", busquedas: int = 0):
    usage = SimpleNamespace(input_tokens=100, output_tokens=50, server_tool_use=SimpleNamespace(web_search_requests=busquedas))
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=texto)], stop_reason=stop_reason, stop_details=None, usage=usage, parsed_output=None)


class StreamFalso:
    def __init__(self, mensaje):
        self._m = mensaje

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        for b in self._m.content:
            yield SimpleNamespace(type="content_block_delta", delta=SimpleNamespace(type="text_delta", text=b.text))

    def get_final_message(self):
        return self._m


class ClienteFalso:
    def __init__(self, respuestas):
        self._respuestas = list(respuestas)
        self.llamadas = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **kwargs):
        self.llamadas.append(kwargs)
        return StreamFalso(self._respuestas.pop(0))


@pytest.fixture
def informe_json():
    return json.dumps(INFORME_EJEMPLO, ensure_ascii=False)


@pytest.fixture
def catalogo():
    from radares.catalogo import Catalogo, Producto
    return Catalogo([
        Producto("574 Classic", "New Balance", "lifestyle", 5990, "in stock", "https://s/574", "NB574"),
        Producto("Samba OG", "Adidas", "lifestyle", 6490, "in stock", "https://s/samba", "AD-SAMBA"),
        Producto("Pegasus 41", "Nike", "running", 8990, "in stock", "https://s/peg41", "NK-PEG41"),
        Producto("Suede Classic XXI", "Puma", "lifestyle", 4290, "in stock", "https://s/suede", "PM-SUEDE"),
        Producto("Gel-Kayano 31", "Asics", "running", 9990, "in stock", "https://s/kayano", "AS-KAY"),
    ], origen="test")
