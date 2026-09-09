# Agente de tres radares

Detecta grietas accionables para un e-commerce de calzado en Uruguay. Tres radares: demanda interna, demanda externa y oferta externa. Cada corrida entrega de 3 a 5 oportunidades con qué está pasando, por qué es una grieta, marca sugerida, acción mínima, qué validar y score de impacto, esfuerzo, confianza y urgencia. Elige una sola mejor apuesta, pide feedback concreto y aprende de él. Salida ejecutiva, cero planillas.

## Cómo funciona

Cada corrida son dos llamadas a Claude Opus 5 más una tercera cuando das feedback:

1. **Investigación.** Lee `perfil.md`, la memoria (lecciones y corridas anteriores) y los datos internos que le pases. Sale a buscar con la herramienta de búsqueda web, con ubicación Uruguay, y escribe un dossier de hallazgos con fuentes y fecha. Lo que no tiene fuente queda marcado.
2. **Análisis.** Convierte el dossier en un informe con esquema fijo (salida estructurada). Ahí aplica el criterio: 3 a 5 grietas, una mejor apuesta, 3 preguntas cerradas para vos.
3. **Aprendizaje.** Cuando respondés, destila tu feedback en lecciones operativas de una oración y registra qué oportunidad validaste, descartaste o estás probando. Eso se inyecta en todas las corridas siguientes.

Todo lo que aprende queda en `memoria/` en JSON plano. Podés editarlo o borrarlo a mano.

## Instalación

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # y completá ANTHROPIC_API_KEY, o usá `ant auth login`
```

Editá `perfil.md` antes de la primera corrida. Es lo que separa una grieta para tu negocio de una idea genérica.

## Uso

```bash
radares correr                                  # los tres radares
radares correr --foco oferta_externa            # un solo radar
radares correr --nota "Hot Sale en 3 semanas, sobrestock de Fila 42-44"
radares correr --datos exportacion_ga4.csv ventas_agosto.csv
radares correr -v                               # muestra razonamiento y dossier en vivo

radares feedback "La 2 la descarto, Fila ya rotó. On me la ofreció un distribuidor argentino en junio."
radares feedback 20260909-1430 "..."            # feedback a una corrida específica (acepta prefijo)

radares ver                                     # última corrida
radares ver 20260909-1430 --dossier             # el dossier de investigación con fuentes
radares historial
radares lecciones
radares lecciones --agregar "Nunca sugerir calzado formal." --aplica-a general
radares lecciones --borrar L1a2b3c
```

## Datos internos (GA4, ventas)

El agente no se conecta a Google Analytics. Le pasás exportaciones con `--datos`: CSV o JSON de GA4 (páginas más vistas, búsquedas del sitio, productos con más agregados al carrito), o ventas por producto y talle. Las usa como evidencia primaria del radar de demanda interna y cita la métrica cuando la usa. Tope de 120.000 caracteres por corrida: filtrá a las últimas 8 semanas o al top de productos antes de pasarlo.

## Costos

Cada corrida completa usa Claude Opus 5 con razonamiento adaptativo, hasta 18 búsquedas web (configurable con `RADARES_MAX_BUSQUEDAS`) y dos llamadas largas. Presupuestá entre 1 y 3 dólares por corrida según cuánto investigue. El feedback cuesta centavos. El uso de tokens y búsquedas queda registrado al pie de cada informe.

## Configuración

Variables de entorno, todas opcionales salvo la clave:

- `ANTHROPIC_API_KEY`: clave de API. Alternativa: `ant auth login`.
- `RADARES_MODEL`: default `claude-opus-5`.
- `RADARES_DIR`: dónde guardar la memoria. Default `./memoria`.
- `RADARES_PERFIL`: ruta al perfil. Default `./perfil.md`.
- `RADARES_MAX_BUSQUEDAS`: tope de búsquedas web por corrida. Default 18.
- `RADARES_FALLBACKS=0`: desactiva el fallback server-side ante rechazos de los clasificadores de seguridad. Viene activado.

## Estructura

```
perfil.md            contexto del negocio (editable)
radares/
  prompts.py         identidad del agente y prompts de las tres fases
  investigar.py      fase 1: búsqueda web, dossier
  analizar.py        fase 2: informe estructurado
  aprender.py        fase 3: feedback a lecciones
  schema.py          modelos de datos (oportunidad, informe, lección)
  memoria.py         persistencia en memoria/
  render.py          informe a texto ejecutivo
  cliente.py         SDK de Anthropic: streaming, refusal, fallbacks
  cli.py             comandos
memoria/             corridas, lecciones y feedback (no se versiona)
tests/               pruebas sin llamadas reales a la API
```

## Tests

```bash
pytest -q
```

Las pruebas simulan al cliente de la API: no gastan tokens.
