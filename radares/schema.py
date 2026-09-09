"""Modelos de datos: informe por frente, oportunidades, lecciones y feedback."""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

Frente = Literal["demanda_interna", "demanda_externa", "oferta_externa"]
Tenemos = Literal["si", "parcial", "no"]
Resultado = Literal["validada", "descartada", "en_prueba", "sin_dato"]


def _clamp(v: int) -> int:
    return max(1, min(5, int(v)))


class Score(BaseModel):
    """Escala 1-5. 5 = mucho impacto, mucho esfuerzo, mucha confianza, muy urgente."""

    impacto: int = Field(description="1-5. Cuánta venta mueve si sale bien.")
    esfuerzo: int = Field(description="1-5. Cuánto cuesta ejecutar la acción. 5 = muy costoso.")
    confianza: int = Field(description="1-5. Qué tan sólido es el dato detrás.")
    urgencia: int = Field(description="1-5. Cuánto se pierde si se espera un mes.")

    @field_validator("impacto", "esfuerzo", "confianza", "urgencia", mode="before")
    @classmethod
    def _rango(cls, v):
        return _clamp(v)

    @property
    def prioridad(self) -> float:
        return round((self.impacto * self.confianza * self.urgencia) / self.esfuerzo, 1)


class Oportunidad(BaseModel):
    id: str = Field(description="DI-n, DE-n u OE-n según el frente, numerado desde 1 dentro del frente.")
    titulo: str = Field(description="Máximo 10 palabras. Producto, marca o término concreto.")
    que_pasa: str = Field(description="El dato. Con número y fuente. 1-3 oraciones.")
    por_que_es_grieta: str = Field(description="La brecha entre lo que la gente pide o la competencia empuja y lo que hacemos. 1-3 oraciones.")
    lo_tenemos: Tenemos = Field(description="si | parcial | no, según el cruce con el catálogo.")
    marca_sugerida: str = Field(description="Una marca concreta.")
    producto_o_termino: str = Field(description="El producto, modelo o término de búsqueda exacto sobre el que se actúa.")
    accion_minima: str = Field(description="Qué bombear o qué hacer, dónde, en qué plazo. La acción más chica que prueba la hipótesis.")
    que_validar: str = Field(description="El dato que confirma o mata la idea antes de gastar.")
    precio_nuestro: Optional[str] = Field(default=None, description="Nuestro precio si aplica, con moneda.")
    precio_afuera: Optional[str] = Field(default=None, description="Precio en competencia o MercadoLibre si aplica, con moneda y quién.")
    gap_precio: Optional[str] = Field(default=None, description="Ej: 'estamos 12% más caros que La Cancha' o 'estamos 8% más baratos'. null si no hay comparación.")
    fuentes: List[str] = Field(default_factory=list, description="Fuente concreta de cada dato: GA4, Trends, URL de MELI, URL del competidor.")
    score: Score


class FrenteInforme(BaseModel):
    frente: Frente
    lectura: str = Field(description="2-3 oraciones. Qué dice este frente hoy. Si las fuentes fallaron, decirlo acá y no inventar.")
    oportunidades: List[Oportunidad] = Field(default_factory=list, description="0 a 3 por frente.")

    @field_validator("oportunidades")
    @classmethod
    def _max3(cls, v):
        return v[:3]


class Informe(BaseModel):
    frentes: List[FrenteInforme] = Field(description="Exactamente tres, en orden: demanda_interna, demanda_externa, oferta_externa.")
    mejor_apuesta: str = Field(description="El id de la única oportunidad elegida como mejor apuesta.")
    por_que_mejor_apuesta: str = Field(description="1-3 oraciones. Por qué esta y no las otras.")
    preguntas_feedback: List[str] = Field(description="3 preguntas cerradas al dueño, que se contesten con un dato o un sí/no.")

    def oportunidades(self) -> List[Oportunidad]:
        return [o for f in self.frentes for o in f.oportunidades]

    def frente(self, nombre: str) -> Optional[FrenteInforme]:
        return next((f for f in self.frentes if f.frente == nombre), None)

    def apuesta(self) -> Oportunidad:
        ops = self.oportunidades()
        return next((o for o in ops if o.id == self.mejor_apuesta), ops[0])

    @model_validator(mode="after")
    def _consistencia(self):
        ops = self.oportunidades()
        if not 3 <= len(ops) <= 5:
            raise ValueError(f"Se esperaban 3 a 5 oportunidades en total, llegaron {len(ops)}")
        vistos = set()
        for o in ops:
            if o.id in vistos:
                raise ValueError(f"Id de oportunidad repetido: {o.id}")
            vistos.add(o.id)
        if self.mejor_apuesta not in vistos:
            self.mejor_apuesta = ops[0].id
        return self


class Leccion(BaseModel):
    id: str
    regla: str
    aplica_a: str = Field(description="general | demanda_interna | demanda_externa | oferta_externa | marca:<nombre>")
    origen: str
    fecha: str
    corrida: str
    peso: int = 1


class LeccionNueva(BaseModel):
    regla: str
    aplica_a: str
    origen: str
    refuerza_id: Optional[str] = Field(default=None, description="Si confirma una lección existente, su id. Si no, null.")


class ResultadoOportunidad(BaseModel):
    id: str = Field(description="Id de la oportunidad (DI-1, DE-2, OE-1...).")
    resultado: Resultado
    nota: str = ""


class LeccionesExtraidas(BaseModel):
    lecciones: List[LeccionNueva]
    resultados: List[ResultadoOportunidad] = Field(default_factory=list)
    respuesta_al_dueno: str = Field(description="1-3 oraciones, directas. Qué se entendió y qué cambia. Sin agradecer.")


class Feedback(BaseModel):
    fecha: str
    corrida: str
    texto: str
    resultados: List[ResultadoOportunidad] = Field(default_factory=list)


class Corrida(BaseModel):
    id: str
    fecha: str
    modelo: str
    nota: Optional[str] = None
    informe: Informe
    evidencia: str = ""
    estado_fuentes: dict = Field(default_factory=dict)
    feedback: List[Feedback] = Field(default_factory=list)
    uso: dict = Field(default_factory=dict)
