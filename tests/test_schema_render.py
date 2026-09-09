import pytest
from pydantic import ValidationError

from radares.render import render_informe
from radares.schema import Informe, Score
from tests.conftest import INFORME_EJEMPLO


def test_score_se_recorta_a_1_5():
    s = Score(impacto=9, esfuerzo=0, confianza=3, urgencia=-2)
    assert (s.impacto, s.esfuerzo, s.confianza, s.urgencia) == (5, 1, 3, 1)
    assert s.prioridad == 15.0


def test_informe_exige_entre_3_y_5_oportunidades():
    data = dict(INFORME_EJEMPLO, oportunidades=INFORME_EJEMPLO["oportunidades"][:2])
    with pytest.raises(ValidationError):
        Informe.model_validate(data)


def test_render_sin_tablas_y_con_apuesta():
    inf = Informe.model_validate(INFORME_EJEMPLO)
    txt = render_informe(inf)
    assert "|" not in txt
    assert "MEJOR APUESTA" in txt
    assert "On Running sin distribución oficial" in txt
    assert "Impacto 4/5" in txt
    assert txt.count("Qué está pasando.") == 3
    assert "Necesito que me contestes esto" in txt
    assert "¿Cuál de las tres descartás sin dudar?" in txt
