"""CLI: correr, feedback, ver, historial, lecciones."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .cliente import RechazoError, crear_cliente, describir_error
from .config import FOCOS, MODEL, PERFIL_PATH
from .memoria import Memoria, ahora_iso, hoy_texto, nuevo_id_corrida
from .render import render_corrida, render_historial, render_lecciones
from .schema import Corrida

MAX_DATOS_CHARS = 120_000


def _leer_perfil() -> str:
    if not PERFIL_PATH.exists():
        sys.exit(f"No encuentro el perfil del negocio en {PERFIL_PATH}. Creá perfil.md antes de correr.")
    return PERFIL_PATH.read_text(encoding="utf-8")


def _leer_datos(paths: list[str] | None) -> str | None:
    if not paths:
        return None
    partes = []
    total = 0
    for p in paths:
        path = Path(p)
        if not path.exists():
            sys.exit(f"No existe el archivo de datos: {p}")
        contenido = path.read_text(encoding="utf-8", errors="replace")
        total += len(contenido)
        partes.append(f"### {path.name}\n{contenido}")
    datos = "\n\n".join(partes)
    if total > MAX_DATOS_CHARS:
        sys.exit(
            f"Los datos internos suman {total} caracteres; el tope es {MAX_DATOS_CHARS}. "
            "Filtrá la exportación (por ejemplo, últimas 8 semanas o top 500 productos) y volvé a intentar."
        )
    return datos


def cmd_correr(args: argparse.Namespace) -> int:
    from .analizar import analizar
    from .investigar import investigar

    mem = Memoria()
    perfil = _leer_perfil()
    datos = _leer_datos(args.datos)
    lecciones_txt = mem.lecciones_como_texto()
    corridas_txt = mem.corridas_como_texto()
    hoy = hoy_texto()
    client = crear_cliente()

    print(f"[radares] modelo {MODEL} · foco {args.foco} · web {'sí' if not args.sin_web else 'no'}", file=sys.stderr)
    try:
        print("[radares] fase 1: investigando…", file=sys.stderr)
        dossier, uso1 = investigar(
            client,
            perfil=perfil,
            lecciones_txt=lecciones_txt,
            corridas_txt=corridas_txt,
            foco=args.foco,
            hoy=hoy,
            nota=args.nota,
            datos=datos,
            con_web=not args.sin_web,
            verbose=args.verbose,
        )
        print(f"\n[radares] fase 2: analizando ({uso1['busquedas']} búsquedas hechas)…", file=sys.stderr)
        informe, uso2 = analizar(
            client,
            perfil=perfil,
            lecciones_txt=lecciones_txt,
            corridas_txt=corridas_txt,
            dossier=dossier,
            foco=args.foco,
            hoy=hoy,
        )
    except RechazoError as e:
        sys.exit(f"[radares] {e}")
    except Exception as e:  # noqa: BLE001
        sys.exit(f"[radares] {describir_error(e)}")

    corrida = Corrida(
        id=nuevo_id_corrida(),
        fecha=ahora_iso(),
        foco=args.foco,
        modelo=MODEL,
        nota=args.nota,
        informe=informe,
        dossier=dossier,
        uso={
            "input_tokens": uso1["input_tokens"] + uso2["input_tokens"],
            "output_tokens": uso1["output_tokens"] + uso2["output_tokens"],
            "busquedas": uso1["busquedas"],
        },
    )
    texto = render_corrida(corrida)
    path = mem.guardar_corrida(corrida, texto)
    print(texto)
    print(f"[radares] guardado en {path}", file=sys.stderr)
    return 0


def cmd_feedback(args: argparse.Namespace) -> int:
    from .aprender import aplicar_aprendizaje, destilar

    mem = Memoria()
    try:
        corrida = mem.cargar_corrida(args.corrida) if args.corrida != "ultima" else mem.ultima_corrida()
    except FileNotFoundError as e:
        sys.exit(f"[radares] {e}")
    if corrida is None:
        sys.exit("[radares] No hay corridas. Ejecutá `radares correr` primero.")

    texto = " ".join(args.texto).strip() if args.texto else ""
    if not texto:
        if sys.stdin.isatty():
            print("Escribí tu feedback (Ctrl-D para terminar):", file=sys.stderr)
        texto = sys.stdin.read().strip()
    if not texto:
        sys.exit("[radares] Feedback vacío. Decime algo concreto: qué descartás, qué ya sabías, qué dato tenés.")

    perfil = _leer_perfil()
    client = crear_cliente()
    try:
        extraido = destilar(client, perfil=perfil, corrida=corrida, lecciones_txt=mem.lecciones_como_texto(), feedback=texto)
    except RechazoError as e:
        sys.exit(f"[radares] {e}")
    except Exception as e:  # noqa: BLE001
        sys.exit(f"[radares] {describir_error(e)}")

    lineas = aplicar_aprendizaje(mem, corrida, texto, extraido)
    print(extraido.respuesta_al_dueno.strip())
    print()
    for ln in lineas:
        print("· " + ln)
    return 0


def cmd_ver(args: argparse.Namespace) -> int:
    mem = Memoria()
    try:
        corrida = mem.cargar_corrida(args.corrida) if args.corrida != "ultima" else mem.ultima_corrida()
    except FileNotFoundError as e:
        sys.exit(f"[radares] {e}")
    if corrida is None:
        sys.exit("[radares] No hay corridas.")
    if args.dossier:
        print(corrida.dossier or "(sin dossier guardado)")
    else:
        print(render_corrida(corrida))
    return 0


def cmd_historial(_: argparse.Namespace) -> int:
    print(render_historial(Memoria().listar_corridas()), end="")
    return 0


def cmd_lecciones(args: argparse.Namespace) -> int:
    mem = Memoria()
    if args.borrar:
        ok = mem.borrar_leccion(args.borrar)
        print("Borrada." if ok else f"No existe la lección {args.borrar}.")
        return 0 if ok else 1
    if args.agregar:
        l = mem.agregar_leccion(args.agregar, args.aplica_a, "manual", "manual")
        print(f"Agregada [{l.id}]: {l.regla}")
        return 0
    print(render_lecciones(mem.cargar_lecciones()), end="")
    return 0


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="radares", description="Agente de tres radares para e-commerce de calzado en Uruguay.")
    p.add_argument("--version", action="version", version=f"radares {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("correr", help="Ejecuta una corrida completa y entrega 3 a 5 oportunidades.")
    c.add_argument("--foco", choices=("todos",) + FOCOS, default="todos", help="Radar a investigar. Default: los tres.")
    c.add_argument("--nota", help="Contexto extra para esta corrida (ej: 'se viene Hot Sale, tengo sobrestock de Fila').")
    c.add_argument("--datos", nargs="*", help="Archivos CSV/JSON con datos internos (exportación GA4, ventas, búsquedas del sitio).")
    c.add_argument("--sin-web", action="store_true", help="No usar búsqueda web (solo perfil, memoria y datos).")
    c.add_argument("-v", "--verbose", action="store_true", help="Muestra el razonamiento y el dossier mientras se genera.")
    c.set_defaults(func=cmd_correr)

    f = sub.add_parser("feedback", help="Registra feedback sobre una corrida y extrae lecciones.")
    f.add_argument("corrida", nargs="?", default="ultima", help="ID de corrida (o prefijo). Default: la última.")
    f.add_argument("texto", nargs="*", help="Feedback. Si se omite, se lee de stdin.")
    f.set_defaults(func=cmd_feedback)

    v = sub.add_parser("ver", help="Muestra una corrida guardada.")
    v.add_argument("corrida", nargs="?", default="ultima")
    v.add_argument("--dossier", action="store_true", help="Muestra el dossier de investigación en vez del informe.")
    v.set_defaults(func=cmd_ver)

    h = sub.add_parser("historial", help="Lista corridas anteriores.")
    h.set_defaults(func=cmd_historial)

    l = sub.add_parser("lecciones", help="Lista, agrega o borra lecciones aprendidas.")
    l.add_argument("--agregar", help="Agrega una lección manual.")
    l.add_argument("--aplica-a", default="general", help="Ámbito de la lección manual.")
    l.add_argument("--borrar", help="ID de lección a borrar.")
    l.set_defaults(func=cmd_lecciones)
    return p


def main(argv: list[str] | None = None) -> None:
    args = construir_parser().parse_args(argv)
    sys.exit(args.func(args))
