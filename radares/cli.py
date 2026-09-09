"""CLI: correr, fuentes, feedback, ver, historial, lecciones."""
from __future__ import annotations

import argparse
import sys

from . import __version__
from .cliente import RechazoError, crear_cliente, describir_error
from .config import FRENTES, MODEL, PERFIL_PATH, cargar_fuentes
from .memoria import Memoria, ahora_iso, hoy_texto, nuevo_id_corrida
from .render import render_corrida, render_historial, render_lecciones
from .schema import Corrida


def _leer_perfil() -> str:
    if not PERFIL_PATH.exists():
        sys.exit(f"[radares] No encuentro {PERFIL_PATH}. Creá perfil.md antes de correr.")
    return PERFIL_PATH.read_text(encoding="utf-8")


def _frentes(args) -> list[str]:
    return list(FRENTES) if args.frente == "todos" else [args.frente]


def _evidencia(args):
    from .recolectar import recolectar

    conf = cargar_fuentes()
    return recolectar(
        conf, _frentes(args),
        catalogo_csv=args.catalogo, ga4_items=args.ga4_items, ga4_busquedas=args.ga4_busquedas, trends_csv=args.trends_csv,
    )


def cmd_correr(args: argparse.Namespace) -> int:
    from .analizar import analizar
    from .recolectar import etiqueta_frentes

    mem = Memoria()
    perfil = _leer_perfil()
    frentes = _frentes(args)
    print(f"[radares] modelo {MODEL} · frentes: {etiqueta_frentes(frentes)}", file=sys.stderr)
    ev = _evidencia(args)
    evidencia_txt = ev.texto()
    if args.solo_evidencia:
        print(evidencia_txt)
        return 0
    if not any((ev.interno, ev.externo, ev.oferta)):
        sys.exit("[radares] Ninguna fuente devolvió datos. Revisá fuentes.toml o corré `radares fuentes` para diagnosticar.")

    client = crear_cliente()
    try:
        print("[radares] analizando…", file=sys.stderr)
        informe, uso = analizar(
            client, perfil=perfil, lecciones_txt=mem.lecciones_como_texto(), corridas_txt=mem.corridas_como_texto(),
            evidencia=evidencia_txt, frentes_txt=etiqueta_frentes(frentes), hoy=hoy_texto(), nota=args.nota, con_web=not args.sin_web,
        )
    except RechazoError as e:
        sys.exit(f"[radares] {e}")
    except Exception as e:  # noqa: BLE001
        sys.exit(f"[radares] {describir_error(e)}")

    corrida = Corrida(
        id=nuevo_id_corrida(), fecha=ahora_iso(), modelo=MODEL, nota=args.nota, informe=informe,
        evidencia=evidencia_txt, estado_fuentes=ev.estado, uso=uso,
    )
    texto = render_corrida(corrida)
    path = mem.guardar_corrida(corrida, texto)
    print(texto)
    print(f"[radares] guardado en {path}", file=sys.stderr)
    return 0


def cmd_fuentes(args: argparse.Namespace) -> int:
    """Diagnóstico: prueba cada fuente y muestra qué devuelve."""
    ev = _evidencia(args)
    print("Estado de fuentes:")
    for k, v in ev.estado.items():
        print(f"- {k}: {v}")
    if args.detalle:
        print()
        print(ev.texto())
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
    client = crear_cliente()
    try:
        extraido = destilar(client, perfil=_leer_perfil(), corrida=corrida, lecciones_txt=mem.lecciones_como_texto(), feedback=texto)
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
    print(corrida.evidencia or "(sin evidencia guardada)") if args.evidencia else print(render_corrida(corrida))
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


def _args_fuentes(p: argparse.ArgumentParser) -> None:
    p.add_argument("--frente", choices=("todos",) + FRENTES, default="todos", help="Frente a mirar. Default: los tres.")
    p.add_argument("--catalogo", help="CSV del catálogo (pisa fuentes.toml).")
    p.add_argument("--ga4-items", help="CSV exportado de GA4: informe de ítems (en vez de la API).")
    p.add_argument("--ga4-busquedas", help="CSV exportado de GA4: términos de búsqueda (en vez de la API).")
    p.add_argument("--trends-csv", help="CSV de consultas relacionadas exportado de Google Trends (en vez de pytrends).")


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="radares", description="Radar de tres frentes para un e-commerce de calzado en Uruguay.")
    p.add_argument("--version", action="version", version=f"radares {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("correr", help="Recolecta las fuentes, analiza y entrega el informe.")
    _args_fuentes(c)
    c.add_argument("--nota", help="Contexto para esta corrida (ej: 'Hot Sale en 3 semanas, sobrestock de Fila').")
    c.add_argument("--sin-web", action="store_true", help="No dejar que el analista use búsqueda web para llenar huecos.")
    c.add_argument("--solo-evidencia", action="store_true", help="Imprime la evidencia recolectada y no llama al modelo.")
    c.set_defaults(func=cmd_correr)

    f = sub.add_parser("fuentes", help="Prueba cada fuente y muestra su estado. No llama al modelo.")
    _args_fuentes(f)
    f.add_argument("--detalle", action="store_true", help="Muestra también las señales detectadas.")
    f.set_defaults(func=cmd_fuentes)

    fb = sub.add_parser("feedback", help="Registra feedback sobre una corrida y extrae lecciones.")
    fb.add_argument("corrida", nargs="?", default="ultima", help="ID de corrida (o prefijo). Default: la última.")
    fb.add_argument("texto", nargs="*", help="Feedback. Si se omite, se lee de stdin.")
    fb.set_defaults(func=cmd_feedback)

    v = sub.add_parser("ver", help="Muestra una corrida guardada.")
    v.add_argument("corrida", nargs="?", default="ultima")
    v.add_argument("--evidencia", action="store_true", help="Muestra la evidencia cruda en vez del informe.")
    v.set_defaults(func=cmd_ver)

    sub.add_parser("historial", help="Lista corridas anteriores.").set_defaults(func=cmd_historial)

    l = sub.add_parser("lecciones", help="Lista, agrega o borra lecciones aprendidas.")
    l.add_argument("--agregar", help="Agrega una lección manual.")
    l.add_argument("--aplica-a", default="general")
    l.add_argument("--borrar", help="ID de lección a borrar.")
    l.set_defaults(func=cmd_lecciones)
    return p


def main(argv: list[str] | None = None) -> None:
    args = construir_parser().parse_args(argv)
    sys.exit(args.func(args))
