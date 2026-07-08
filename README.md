# Zebra · Automatizador de Cronograma de Lanzamientos

App web para armar el cronograma de lanzamiento de cada cliente, recalcular fechas
en cascada, guardar plantillas, y publicar a Monday con un clic. Construida para
desplegarse vía **Git → EasyPanel** con **PostgreSQL**.

---

## Despliegue en EasyPanel

### 1. Crear el servicio de base de datos
En EasyPanel: **+ Create Service → Postgres**. Anota la conexión; EasyPanel te da una
`DATABASE_URL` (algo como `postgresql://user:pass@host:5432/db`).

### 2. Crear la app desde Git
**+ Create Service → App → Source: GitHub** y apunta a este repositorio.
EasyPanel detecta el `Dockerfile` automáticamente y construye la imagen.

### 3. Variables de entorno (pestaña Environment del servicio App)
```
DATABASE_URL = (la URL del Postgres del paso 1)
MONDAY_API_TOKEN = (tu token de Monday; opcional, para envío real)
```
`PORT` lo inyecta EasyPanel solo. El esquema de tablas se crea automáticamente al
primer arranque.

### 4. Dominio
Asigna un dominio en la pestaña **Domains**. Listo.

---

## Correr en local (para probar)

Necesitas un Postgres corriendo. Luego:

```bash
pip install -r requirements.txt
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/zebra"
python app.py
```

Abre http://localhost:5000

---

## Cómo funciona (explicación completa)

👉 Lee **[COMO_FUNCIONA.md](COMO_FUNCIONA.md)** para una explicación en lenguaje
natural de todo el sistema: el modelo mental, el flujo completo, el motor de
fechas, la integración con Monday y el modelo de datos.

---

## Qué hace (resumen)

**Cronograma**
- Panel editable en línea: tareas, días, estado, descripción.
- **Cascada automática** de fechas: cambias los días y se recalcula todo lo que
  sigue. Salta fines de semana **y feriados**.
- **Dependencias**: cada tarea sigue a la anterior ("Secuencial") o depende de
  cualquier otra tarea (incluso de otra línea).
- **Fecha de inicio manual** (override) para tareas secuenciales, con botón ↺ para
  volver a automático.
- **Responsable = departamentos** como etiquetas de color (varios por tarea).
- **Check "crear en Monday"** por tarea, con botones *✓ Todos / ✕ Ninguno* por línea.

**Gantt** — líneas horizontales (barras por fecha), coloreadas por departamento,
con marcador de hoy y sombreado de fines de semana.

**Resumen** — avance %, fechas y días por línea + arranque/cierre global.

**Responsables** — por departamento, eliges la **persona** (del catálogo) que se
asignará en Monday al publicar.

**Feriados** — lista editable de días inhábiles que la cascada respeta.

**📁 Proyectos** — vista para listar, abrir/editar, exportar PDF y **eliminar**
proyectos y plantillas.

**⚙ Monday** — Board ID, IDs de columnas, **mapeo de estatus** (label o índice),
catálogo de personas (con departamento y `user_id`) y catálogo de departamentos
(con color, label e índice).

**Plantillas** — "Guardar como plantilla" congela la estructura (líneas, tareas,
días, descripciones; sin responsables/fechas/estados) para reutilizarla.

**PDF** — exporta el cronograma con la identidad Zebra (logo, banda dorada, cards
de métricas, tablas).

**Publicar a Monday** — valida, traduce responsables/deptos/estatus a los IDs de
Monday, crea **un grupo con el nombre del cliente** y un ítem por tarea marcada
(título `Lanzamiento | {cliente} | {tarea}`). Crea el cliente/labels que falten
(`create_labels_if_missing`), envía **de una en una** con reintento por límite de
tasa, y reporta *"Creadas X/Y"* con los errores exactos de Monday si los hay.

---

## Estructura del repo

```
.
├── app.py            # Endpoints Flask (proyectos, tareas, catálogos, publicar a Monday)
├── db.py             # Conexión Postgres + esquema + migraciones automáticas
├── engine.py         # Motor de cascada (dependencias, fines de semana, feriados, override)
├── pdf_export.py     # Generador de PDF con formato Zebra
├── seed.json         # Tareas base extraídas del Excel original
├── static/
│   ├── index.html    # Toda la interfaz (HTML + CSS + JS)
│   └── logo.png      # Logo Zebra
├── Dockerfile        # Imagen para EasyPanel (gunicorn)
├── requirements.txt
├── COMO_FUNCIONA.md  # Documentación en lenguaje natural
└── README.md
```

---

## Variables de entorno

| Variable | Para qué |
|---|---|
| `DATABASE_URL` | Conexión a PostgreSQL (la inyecta EasyPanel). |
| `MONDAY_API_TOKEN` | Token de Monday; sin él, publicar queda en modo simulación. |
| `MONDAY_DELAY` | (Opcional) Segundos de pausa entre tareas al publicar. Default `0.4`. |
| `PORT` | Lo inyecta EasyPanel automáticamente. |

