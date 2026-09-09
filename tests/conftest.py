import json
import os
from types import SimpleNamespace

import pytest


@pytest.fixture
def memoria_tmp(tmp_path, monkeypatch):
    from radares import memoria as m
    monkeypatch.setattr(m, "MEMORIA_DIR", tmp_path / "memoria")
    return m.Memoria(tmp_path / "memoria")


INFORME_EJEMPLO = {
    "resumen_ejecutivo": "Hay tres grietas concretas esta semana. La más rentable es traer On Running antes de la maratón.",
    "oportunidades": [
        {
            "titulo": "On Running sin distribución oficial antes de la maratón",
            "foco": "oferta_externa",
            "que_pasa": "On no tiene distribuidor en Uruguay. Las búsquedas de 'On Cloud Uruguay' subieron.",
            "por_que_es_grieta": "Nadie la vende localmente y el comprador de running de ticket alto la pide.",
            "marca_sugerida": "On Running",
            "accion_minima": "Pedir 60 pares vía distribuidor argentino y medir sell-through en 3 semanas.",
            "que_validar": "Que el distribuidor argentino acepte vender a Uruguay y el precio final quede bajo USD 220.",
            "fuentes": ["https://ejemplo.uy/on-running"],
            "score": {"impacto": 4, "esfuerzo": 3, "confianza": 3, "urgencia": 4},
        },
        {
            "titulo": "Sobrestock de Fila choca con liquidación de competidor",
            "foco": "demanda_interna",
            "que_pasa": "Un competidor liquidó Fila con 40% off.",
            "por_que_es_grieta": "El precio de referencia bajó y el stock propio queda caro.",
            "marca_sugerida": "Fila",
            "accion_minima": "Bundle Fila + medias con 25% off en 7 días.",
            "que_validar": "Rotación semanal actual de Fila por talle.",
            "fuentes": [],
            "score": {"impacto": 2, "esfuerzo": 1, "confianza": 4, "urgencia": 5},
        },
        {
            "titulo": "Samba y siluetas terrace siguen creciendo en Brasil",
            "foco": "demanda_externa",
            "que_pasa": "Adidas Samba y Gazelle dominan búsquedas en Brasil y Argentina.",
            "por_que_es_grieta": "El surtido local está flojo en talles chicos de Samba.",
            "marca_sugerida": "Adidas",
            "accion_minima": "Reponer talles 36-39 de Samba OG.",
            "que_validar": "Búsquedas internas sin resultado para 'samba' por talle.",
            "fuentes": ["https://ejemplo.br/samba"],
            "score": {"impacto": 3, "esfuerzo": 2, "confianza": 4, "urgencia": 3},
        },
    ],
    "mejor_apuesta": 1,
    "por_que_mejor_apuesta": "Es la única con ventana clara y sin competencia local.",
    "preguntas_feedback": [
        "¿Algún distribuidor te ofreció On en los últimos 6 meses?",
        "¿Cuántos pares de Fila tenés hoy en stock?",
        "¿Cuál de las tres descartás sin dudar?",
    ],
}


def mensaje_falso(texto: str, stop_reason: str = "end_turn", busquedas: int = 0):
    """Imita lo mínimo de BetaMessage que usa el código."""
    usage = SimpleNamespace(
        input_tokens=100,
        output_tokens=50,
        server_tool_use=SimpleNamespace(web_search_requests=busquedas),
    )
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=texto)],
        stop_reason=stop_reason,
        stop_details=None,
        usage=usage,
        parsed_output=None,
    )


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
    """Devuelve respuestas predefinidas en orden y guarda los kwargs de cada llamada."""

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
