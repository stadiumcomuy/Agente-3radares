"""Modelos de datos: oportunidades, informe, lecciones y feedback."""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

Foco = Literal["demanda_interna", "demanda_externa", "oferta_externa"]
Resultado = Literal["validada", "descartada", "en_prueba", "sin_dato"]


def _clamp(v: int) -> int:
    return max(1, min(5, int(v)))


class Score(BaseModel):
    """Cuatro dimensiones en escala 1-5. 5 = mucho impacto, mucho esfuerzo, mucha confianza, muy urgente."""

    impacto: int = Field(description="1-5. Cuánta plata o posición mueve si sale bien.")
    esfuerzo: int = Field(description="1-5. Cuánto cuesta ejecutar la acción mínima. 5 = muy costoso.")
    confianza: int = Field(description="1-5. Qué tan sólida es la evidencia detrás.")
    urgencia: int = Field(description="1-5. Cuánto se pierde si se espera un mes.")

    @field_validator("impacto", "esfuerzo", "confianza", "urgencia", mode="before")
    @classmethod
    def _rango(cls, v):
        return _clamp(v)

    @property
    def prioridad(self) -> float:
        """Heurística simple para ordenar: (impacto * confianza * urgencia) / esfuerzo."""
        return round((self.impacto * self.confianza * self.urgencia) / self.esfuerzo, 1)


class Oportunidad(BaseModel):
    titulo: str = Field(description="Máximo 10 palabras. Concreto, sin adjetivos vacíos.")
    foco: Foco
    que_pasa: str = Field(description="Hecho observable con dato o fuente. 2-4 oraciones.")
    por_que_es_grieta: str = Field(
        description="Por qué hay una brecha entre lo que el mercado pide u ofrece y lo que este negocio hace hoy. 2-4 oraciones."
    )
    marca_sugerida: str = Field(description="Una marca concreta, o 'ninguna' con motivo.")
    accion_minima: str = Field(description="La acción más chica que prueba la hipótesis. Con plazo y responsable sugerido.")
    que_validar: str = Field(description="Dato o señal que confirma o mata la idea antes de invertir.")
    fuentes: List[str] = Field(default_factory=list, description="URLs o referencias concretas que sostienen 'que_pasa'.")
    score: Score


class Informe(BaseModel):
    resumen_ejecutivo: str = Field(description="3-5 oraciones. Qué cambió en el mercado y qué hay que hacer esta semana.")
    oportunidades: List[Oportunidad] = Field(description="Entre 3 y 5. Ni más ni menos.")
    mejor_apuesta: int = Field(description="Índice (desde 1) de la única oportunidad que se elige como mejor apuesta.")
    por_que_mejor_apuesta: str = Field(description="2-3 oraciones. Por qué esta y no las otras.")
    preguntas_feedback: List[str] = Field(
        description="3 preguntas concretas y cerradas para el dueño del negocio, que permitan aprender para la próxima corrida."
    )

    @field_validator("oportunidades")
    @classmethod
    def _cantidad(cls, v):
        if not 3 <= len(v) <= 5:
            raise ValueError(f"Se esperaban 3 a 5 oportunidades, llegaron {len(v)}")
        return v

    @field_validator("mejor_apuesta", mode="before")
    @classmethod
    def _indice(cls, v):
        return max(1, int(v))

    def apuesta(self) -> Oportunidad:
        idx = min(self.mejor_apuesta, len(self.oportunidades)) - 1
        return self.oportunidades[idx]


class Leccion(BaseModel):
    id: str
    regla: str = Field(description="Una regla operativa, imperativa, de una oración.")
    aplica_a: str = Field(description="general | demanda_interna | demanda_externa | oferta_externa | marca:<nombre>")
    origen: str = Field(description="Cita corta del feedback que la generó.")
    fecha: str
    corrida: str
    peso: int = Field(default=1, description="Cuántas veces se confirmó. Sube si el feedback la repite.")


class LeccionesExtraidas(BaseModel):
    """Salida estructurada del destilador de feedback."""

    lecciones: List["LeccionNueva"]
    resultados: List["ResultadoOportunidad"] = Field(default_factory=list)
    respuesta_al_dueno: str = Field(
        description="1-3 oraciones, directas. Qué se entendió y qué va a cambiar en la próxima corrida. Sin agradecer."
    )


class LeccionNueva(BaseModel):
    regla: str
    aplica_a: str
    origen: str
    refuerza_id: Optional[str] = Field(
        default=None, description="Si el feedback confirma una lección existente, su id. Si no, null."
    )


class ResultadoOportunidad(BaseModel):
    indice: int = Field(description="Índice (desde 1) de la oportunidad a la que refiere el feedback.")
    resultado: Resultado
    nota: str = ""


class Feedback(BaseModel):
    fecha: str
    corrida: str
    texto: str
    resultados: List[ResultadoOportunidad] = Field(default_factory=list)


class Corrida(BaseModel):
    id: str
    fecha: str
    foco: str
    modelo: str
    nota: Optional[str] = None
    informe: Informe
    dossier: str = ""
    feedback: List[Feedback] = Field(default_factory=list)
    uso: dict = Field(default_factory=dict)
