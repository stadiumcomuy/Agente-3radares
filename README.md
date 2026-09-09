# Radar de tres frentes

Agente para un e-commerce de calzado en Uruguay. Mira tres frentes independientes, cruza todo contra el catálogo propio y entrega un informe escueto, ejecutivo y directo. Sin planillas, sin presentaciones.

## Los tres frentes

**Demanda interna (GA4).** Qué busca o mira la gente en el sitio que convierte bien pero se ve poco. La gente que lo encuentra lo compra; lo encuentra poca gente. Eso hay que bombear. También: qué se busca en el sitio y no está en el catálogo.

**Demanda externa (Google Trends + MercadoLibre).** Qué quiere y busca la gente fuera del sitio: consultas en alza en Trends, publicaciones con más preguntas y ventas en MELI. Si lo tenemos, por qué bombearlo y a qué precio estamos contra MELI.

**Oferta externa (competencia).** Qué bombea la competencia en sus banners y destacados, con qué productos y a qué precio. Si lo tenemos, si podemos bombearlo, y si estamos más caros o más baratos para aprovechar o achicar el gap.

Cada corrida entrega entre 3 y 5 oportunidades en total, repartidas por frente, cada una con dato, grieta, marca, producto o término exacto, acción mínima, qué validar y score 1-5 de impacto, esfuerzo, confianza y urgencia. Elige una sola apuesta y cierra con tres preguntas cerradas. El feedback se destila en lecciones que cambian las corridas siguientes.

## Cómo funciona

1. **Recolectar.** Código determinista, sin modelo. Lee GA4, Trends, MELI y los sitios de la competencia, cruza cada señal contra el catálogo (¿lo tenemos? ¿a qué precio?) y calcula las señales: ítems subexpuestos, marcas que convierten sobre su exposición, búsquedas sin respuesta, consultas en alza, publicaciones con preguntas, banners de competidores y gaps de precio. Cada fuente falla por separado y el informe lo dice.
2. **Analizar.** Claude Opus 5 recibe la evidencia ya cruzada, el perfil del negocio y la memoria, y produce el informe con esquema fijo. Puede usar búsqueda web solo para llenar huecos concretos (pautas de un competidor, preguntas de una publicación).
3. **Aprender.** Con tu feedback, destila lecciones de una oración y registra qué oportunidad validaste, descartaste o estás probando.

## Instalación

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env    # ANTHROPIC_API_KEY, y opcionalmente GA4 y MELI
```

Después configurá `fuentes.toml` y `perfil.md`. Sin catálogo no hay cruce, así que empezá por ahí.

## Fuentes: qué necesita cada una

**Catálogo** (obligatorio para cruzar). Una de tres, en `[catalogo]`:
- `csv`: exportación con columnas nombre, marca, precio y opcionalmente sku, categoria, stock, url. Acepta `;` o `,`.
- `feed_google`: URL del feed XML de Google Merchant. Casi todas las plataformas lo exponen.
- `sitemap`: sitemap de productos; se leen los JSON-LD de cada página. Lento, último recurso.

**GA4.** API oficial con service account: `property_id` y `credenciales` en `[ga4]`, o `GA4_PROPERTY_ID` y `GOOGLE_APPLICATION_CREDENTIALS`. La service account tiene que tener acceso de lectura a la propiedad. Sin API: exportá desde GA4 el informe de ítems (nombre, marca, vistas, agregados al carrito, compras, ingresos) y el de términos de búsqueda, y pasalos con `--ga4-items` y `--ga4-busquedas`.

**Google Trends.** Usa `pytrends`, que no es oficial y devuelve 429 seguido. Cuando cae, el informe lo dice. Alternativa: exportá "consultas relacionadas" desde trends.google.com y pasalo con `--trends-csv`.

**MercadoLibre.** La API pública de búsqueda quedó restringida en 2024-2025. Con `MELI_ACCESS_TOKEN` usa la API; sin token lee las páginas públicas de listado y de producto (títulos, precios, "más vendido", preguntas). El scraping puede romperse si MELI cambia el HTML.

**Competencia.** Lista de sitios en `[competencia]`. Lee la home, extrae banners y links promocionales, sigue esos links y saca productos con precio de los JSON-LD. No lee pautas de Meta ni Instagram: la Ad Library no expone pautas comerciales fuera de la UE por API, e Instagram exige login. Para eso el analista puede usar búsqueda web, con resultado variable.

## Uso

```bash
radares fuentes                      # diagnóstico: qué fuente anda y qué devuelve. No llama al modelo.
radares fuentes --detalle            # además muestra las señales detectadas
radares correr                       # los tres frentes
radares correr --frente demanda_interna
radares correr --nota "Hot Sale en 3 semanas, sobrestock de Fila"
radares correr --ga4-items items.csv --ga4-busquedas busquedas.csv --catalogo catalogo.csv
radares correr --solo-evidencia      # imprime la evidencia cruzada y no gasta tokens

radares feedback "DI-2 la descarto, no traigo Crocs. OE-1 sí: bajo Pegasus 8%."
radares ver                          # última corrida
radares ver 20260909 --evidencia     # la evidencia cruda que vio el analista
radares historial
radares lecciones
radares lecciones --agregar "Fila no se bombea hasta liquidar el sobrestock." --aplica-a marca:Fila
```

## Cómo se ve el informe

```
# Radar · 2026-09-09
Fuentes: GA4: API: 812 ítems, 340 términos · Trends: caída: 429 · MercadoLibre: 6 consultas · Competencia: 4/6 sitios leídos

## Demanda interna
Dos productos convierten al doble de la mediana con la mitad de vistas.

DI-1 · New Balance 574 talle 44 convierte y no se ve  ← APUESTA
Lo tenemos · New Balance · New Balance 574 talle 44 convierte y no se ve
Dato. Dato con número y fuente.
Grieta. Brecha concreta.
Acción. Bombear en home 14 días.
Validar. Rotación semanal.
Impacto 4 · Esfuerzo 1 · Confianza 5 · Urgencia 4 · Prioridad 80.0
Fuentes: GA4

DI-2 · Buscan 'crocs' y no hay catálogo
No lo tenemos · Crocs · Buscan 'crocs' y no hay catálogo
Dato. Dato con número y fuente.
Grieta. Brecha concreta.
Acción. Bombear en home 14 días.
Validar. Rotación semanal.
Impacto 2 · Esfuerzo 3 · Confianza 3 · Urgencia 2 · Prioridad 4.0
Fuentes: GA4

## Demanda externa
MELI muestra preguntas repetidas por talle en Samba.

DE-1 · Samba OG: preguntas por talle en MELI
Lo tenemos · Adidas · Samba OG: preguntas por talle en MELI
Dato. Dato con número y fuente.
Grieta. Brecha concreta.
Precio. estamos 8% más baratos que MELI
Acción. Bombear en home 14 días.
Validar. Rotación semanal.
Impacto 3 · Esfuerzo 2 · Confianza 4 · Urgencia 3 · Prioridad 18.0
Fuentes: GA4

## Oferta externa
La Cancha bombea Nike Pegasus 41 en home.

OE-1 · La Cancha empuja Pegasus 41 y estamos 10% más caros
Lo tenemos · Nike · La Cancha empuja Pegasus 41 y estamos 10% más caros
Dato. Dato con número y fuente.
Grieta. Brecha concreta.
Precio. estamos 10% más caros que La Cancha
Acción. Bombear en home 14 días.
Validar. Rotación semanal.
Impacto 3 · Esfuerzo 2 · Confianza 4 · Urgencia 4 · Prioridad 24.0
Fuentes: GA4

## Apuesta: DI-1 · New Balance 574 talle 44 convierte y no se ve
Esfuerzo 1, dato propio, se mide en una semana.

## Contestame
- ¿Tenés stock de 574 en 43-45?
- ¿Ya pautaste Samba este mes?
- ¿Cuál descartás sin dudar?

```

## Configuración

- `ANTHROPIC_API_KEY`: clave de API. Alternativa: `ant auth login`.
- `GA4_PROPERTY_ID`, `GOOGLE_APPLICATION_CREDENTIALS`: GA4 por API.
- `MELI_ACCESS_TOKEN`: MercadoLibre por API en vez de páginas públicas.
- `RADARES_MODEL`: default `claude-opus-5`.
- `RADARES_DIR`: dónde guardar la memoria. Default `./memoria`.
- `RADARES_MAX_BUSQUEDAS`: tope de búsquedas web del analista. Default 8.
- `RADARES_FALLBACKS=0`: desactiva el fallback server-side ante rechazos de seguridad.

## Costos

Recolectar no cuesta tokens. Analizar es una llamada a Opus 5 con la evidencia cruzada y hasta 8 consultas web: presupuestá entre 0,5 y 2 dólares por corrida. El feedback cuesta centavos.

## Estructura

```
fuentes.toml          configuración de fuentes y competidores
perfil.md             contexto del negocio
radares/
  catalogo.py         carga del catálogo y cruce difuso
  fuentes/ga4.py      GA4 API o CSV
  fuentes/trends.py   Google Trends (pytrends) o CSV
  fuentes/meli.py     MercadoLibre API o páginas públicas
  fuentes/competencia.py  banners y productos de competidores
  radar_interno.py    señales de demanda interna
  radar_externo.py    señales de demanda externa
  radar_oferta.py     señales de oferta externa y gap de precio
  recolectar.py       orquesta fuentes y arma la evidencia
  analizar.py         evidencia -> informe (Claude, salida estructurada)
  aprender.py         feedback -> lecciones
  schema.py, render.py, memoria.py, cliente.py, cli.py
memoria/              corridas, lecciones, feedback (no se versiona)
tests/                sin llamadas reales a la API ni a la red
```

## Tests

```bash
pytest -q
```
