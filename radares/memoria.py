"""Persistencia local: corridas, lecciones y feedback. Todo en JSON plano bajo memoria/."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .config import MEMORIA_DIR
from .schema import Corrida, Feedback, Leccion


def ahora_iso() -> str:
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()


def hoy_texto() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def nuevo_id_corrida() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M") + "-" + uuid.uuid4().hex[:4]


class Memoria:
    def __init__(self, base: Path = MEMORIA_DIR):
        self.base = Path(base)
        self.corridas_dir = self.base / "corridas"
        self.lecciones_path = self.base / "lecciones.json"
        self.corridas_dir.mkdir(parents=True, exist_ok=True)

    # ---- corridas -------------------------------------------------------
    def guardar_corrida(self, corrida: Corrida, texto_render: str | None = None) -> Path:
        path = self.corridas_dir / f"{corrida.id}.json"
        path.write_text(corrida.model_dump_json(indent=2, exclude_none=True), encoding="utf-8")
        if texto_render is not None:
            (self.corridas_dir / f"{corrida.id}.md").write_text(texto_render, encoding="utf-8")
        return path

    def cargar_corrida(self, id_corrida: str) -> Corrida:
        path = self.corridas_dir / f"{id_corrida}.json"
        if not path.exists():
            candidatos = sorted(self.corridas_dir.glob(f"{id_corrida}*.json"))
            if len(candidatos) == 1:
                path = candidatos[0]
            elif len(candidatos) > 1:
                raise FileNotFoundError(f"'{id_corrida}' es ambiguo: {[c.stem for c in candidatos]}")
            else:
                raise FileNotFoundError(f"No existe la corrida '{id_corrida}' en {self.corridas_dir}")
        return Corrida.model_validate_json(path.read_text(encoding="utf-8"))

    def listar_corridas(self) -> List[Corrida]:
        out = []
        for p in sorted(self.corridas_dir.glob("*.json")):
            try:
                out.append(Corrida.model_validate_json(p.read_text(encoding="utf-8")))
            except Exception:
                continue
        return out

    def ultima_corrida(self) -> Optional[Corrida]:
        corridas = self.listar_corridas()
        return corridas[-1] if corridas else None

    # ---- lecciones ------------------------------------------------------
    def cargar_lecciones(self) -> List[Leccion]:
        if not self.lecciones_path.exists():
            return []
        raw = json.loads(self.lecciones_path.read_text(encoding="utf-8"))
        return [Leccion.model_validate(x) for x in raw]

    def guardar_lecciones(self, lecciones: List[Leccion]) -> None:
        self.lecciones_path.write_text(
            json.dumps([l.model_dump() for l in lecciones], ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def agregar_leccion(self, regla: str, aplica_a: str, origen: str, corrida: str) -> Leccion:
        lecciones = self.cargar_lecciones()
        nueva = Leccion(
            id="L" + uuid.uuid4().hex[:6],
            regla=regla.strip(),
            aplica_a=aplica_a.strip() or "general",
            origen=origen.strip(),
            fecha=hoy_texto(),
            corrida=corrida,
        )
        lecciones.append(nueva)
        self.guardar_lecciones(lecciones)
        return nueva

    def reforzar_leccion(self, id_leccion: str) -> Optional[Leccion]:
        lecciones = self.cargar_lecciones()
        for l in lecciones:
            if l.id == id_leccion:
                l.peso += 1
                self.guardar_lecciones(lecciones)
                return l
        return None

    def borrar_leccion(self, id_leccion: str) -> bool:
        lecciones = self.cargar_lecciones()
        restantes = [l for l in lecciones if l.id != id_leccion]
        if len(restantes) == len(lecciones):
            return False
        self.guardar_lecciones(restantes)
        return True

    # ---- feedback -------------------------------------------------------
    def agregar_feedback(self, corrida: Corrida, fb: Feedback) -> None:
        corrida.feedback.append(fb)
        self.guardar_corrida(corrida)

    # ---- texto para inyectar en prompts ---------------------------------
    def lecciones_como_texto(self) -> str:
        lecciones = self.cargar_lecciones()
        if not lecciones:
            return ""
        lecciones.sort(key=lambda l: (-l.peso, l.fecha))
        return "\n".join(f"- [{l.id}] ({l.aplica_a}, peso {l.peso}) {l.regla}" for l in lecciones)

    def corridas_como_texto(self, ultimas: int = 4) -> str:
        corridas = self.listar_corridas()[-ultimas:]
        if not corridas:
            return ""
        bloques = []
        for c in corridas:
            estado = {}
            for fb in c.feedback:
                for r in fb.resultados:
                    estado[r.indice] = r.resultado + (f" ({r.nota})" if r.nota else "")
            lineas = [f"Corrida {c.id} ({c.fecha[:10]}, foco {c.foco}):"]
            for i, o in enumerate(c.informe.oportunidades, 1):
                marca = "apuesta" if i == c.informe.mejor_apuesta else ""
                lineas.append(
                    f"  {i}. {o.titulo} [{o.foco}, marca {o.marca_sugerida}, "
                    f"I{o.score.impacto} E{o.score.esfuerzo} C{o.score.confianza} U{o.score.urgencia}] "
                    f"{marca} -> {estado.get(i, 'sin feedback')}"
                )
            fb_txt = [fb.texto.strip().replace("\n", " ")[:300] for fb in c.feedback if fb.texto.strip()]
            if fb_txt:
                lineas.append("  Feedback del dueño: " + " | ".join(fb_txt))
            bloques.append("\n".join(lineas))
        return "\n\n".join(bloques)
