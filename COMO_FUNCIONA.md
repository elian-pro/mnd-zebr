# Cómo funciona Zebra · Cronograma → Monday

Este documento explica **en lenguaje natural** cómo está pensado y cómo funciona
el sistema, de principio a fin. No hace falta saber programar para entenderlo:
la idea es que cualquier persona del equipo pueda leer esto y comprender qué hace
la herramienta, con qué piezas trabaja y cómo viaja la información hasta Monday.

---

## 1. La idea en una frase

> Armas el **cronograma de lanzamiento** de un cliente (líneas de trabajo y tareas
> con sus días), la app **calcula solita todas las fechas** respetando fines de
> semana y feriados, y con un clic **publica esas tareas en Monday** ya asignadas
> a la persona correcta de cada departamento.

Todo lo demás (plantillas, PDF, resumen, colores, checkboxes) son comodidades
alrededor de esas tres cosas: **planear → calcular → publicar**.

---

## 2. El modelo mental (los conceptos)

Piensa en muñecas rusas, de lo más grande a lo más pequeño:

- **Proyecto** = el lanzamiento de **un cliente**. Tiene un nombre de cliente,
  una fecha de inicio y un estado (En proceso / Lanzado / Pausado).
- **Línea de trabajo** = una etapa o carril del proyecto (ej. *ONBOARDING Y
  PRODUCCIÓN*, *CLOSING DEL PROYECTO*). Un proyecto tiene varias líneas.
- **Tarea** = el trabajo concreto dentro de una línea (ej. *Pago de licencias*).
  Cada tarea tiene: nombre, descripción, **días** que dura, **estado**,
  **responsable(s)** (departamentos), de quién **depende**, y un check de
  "¿crear en Monday?".

Alrededor de las tareas hay varios **catálogos y ajustes**:

- **Responsables del proyecto**: por cada departamento eliges **una persona**
  que será la responsable *en ese proyecto*.
- **Catálogo de personas** (global): la lista de gente del equipo, cada una con
  su **`user_id` de Monday** y el **departamento** al que pertenece.
- **Catálogo de departamentos** (global): cada departamento con su **color**
  (para el Gantt) y su **label/índice** en Monday.
- **Feriados**: días inhábiles que el cálculo de fechas salta.
- **Plantillas**: la estructura de un proyecto (líneas + tareas + días) guardada
  para reutilizarla, sin fechas ni responsables.
- **Configuración de Monday**: el Board ID, los IDs de columnas y el mapeo de
  estatus.

---

## 3. El flujo completo, paso a paso

### Paso 1 — Crear el proyecto
Pulsas **+ Nuevo proyecto**, escribes el **nombre del cliente** (siempre es un
cliente nuevo) y la **fecha de inicio**. Puedes partir de la **estructura original**
(las ~52 tareas del Excel) o de una **plantilla** guardada.

Al crear el proyecto, la app copia esa estructura de líneas y tareas, y crea una
fila de responsable vacía por cada departamento.

### Paso 2 — Editar el cronograma
En la pestaña **Cronograma** ajustas todo en línea: cambias días, estado,
descripción, agregas o quitas tareas y líneas, eliges los **departamentos
responsables** de cada tarea (etiquetas de color) y marcas de quién **depende**
cada tarea.

Cada vez que cambias algo que afecta el tiempo, la app **recalcula las fechas**
automáticamente (ver sección 4).

### Paso 3 — Asignar responsables
En la pestaña **Responsables** eliges, por cada departamento, **qué persona**
del catálogo lo representa en este proyecto. Esa persona es la que se asignará
en Monday al publicar.

### Paso 4 — Revisar
- **Gantt**: ves las tareas como barras horizontales en el tiempo, coloreadas
  por departamento.
- **Resumen**: avance %, fechas y días por línea, y arranque/cierre global.
- **PDF**: descargas el cronograma con la identidad visual de Zebra.

### Paso 5 — Publicar a Monday
Pulsas **🚀 Publicar a Monday**. La app:
1. **Valida** (avisa de tareas sin responsable, departamentos/personas sin mapeo,
   board sin configurar).
2. **Traduce** cada tarea a lo que Monday entiende (ver sección 5).
3. **Crea** un grupo con el nombre del cliente y, dentro, una tarea (ítem) por
   cada tarea marcada con el check de Monday.
4. Marca el proyecto como **Lanzado** y guarda una copia de lo enviado.

---

## 4. El motor de fechas (la "cascada")

Esta es la parte más lista de la herramienta. Tú **nunca escribes fechas a mano**
(salvo que quieras); solo dices cuántos **días** dura cada tarea y el orden, y la
app calcula el inicio y fin de cada una. Las reglas, en palabras:

1. **El proyecto arranca** en su fecha de inicio.
2. Dentro de una línea, cada tarea **empieza cuando termina la anterior**
   (modo "Secuencial").
3. Si una tarea **depende de otra** (incluso de otra línea), no empieza hasta que
   esa termine.
4. Solo se cuentan **días hábiles**: se saltan sábados, domingos y los **feriados**
   que hayas cargado.
5. Una tarea de **0 días** es un hito: empieza y termina el mismo día.

**Fijar una fecha manualmente:** si una tarea es *Secuencial*, puedes escribir su
fecha de inicio a mano. Entonces esa fecha manda (se ve en negrita) y las tareas
siguientes se recalculan a partir de ahí. El botón **↺** la regresa a automático.

> En términos simples: mueves una pieza y todo lo que viene detrás se reacomoda
> solo, respetando fines de semana y feriados.

---

## 5. Cómo se traduce y se publica a Monday

Monday no entiende "Pendiente" o "Media" tal cual: cada columna espera un formato
y unos identificadores específicos. La app hace de **traductor**.

### Qué estructura se crea en Monday
```
Board configurado (Board ID)
 └─ Grupo: «Nombre del cliente»
      ├─ Ítem: «Lanzamiento | {cliente} | {tarea 1}»
      ├─ Ítem: «Lanzamiento | {cliente} | {tarea 2}»
      └─ ... (solo las tareas con el check de Monday activado)
```
Todas las tareas van a **un solo grupo** con el nombre del cliente.

### Cómo se llena cada columna del ítem
| Columna en Monday | De dónde sale | Formato que se manda |
|---|---|---|
| **Estatus** | el estado de la tarea, pasado por el **Mapeo de estatus** | `{"index": N}` o `{"label": "..."}` |
| **Especialista** (personas) | la persona asignada al departamento de la tarea → su `user_id` | `{"personsAndTeams": [...]}` |
| **Departamento** | el label/índice del departamento | `{"label": "..."}` o `{"index": N}` |
| **Cliente** | el nombre del cliente del proyecto | `{"labels": ["..."]}` (dropdown) |
| **Fecha límite** | la fecha de fin calculada de la tarea | `{"date": "AAAA-MM-DD"}` |

Puntos clave del comportamiento:

- **Traducción de responsables**: en la tarea eliges *departamentos*; al publicar,
  cada departamento se convierte en la **persona** que asignaste en la pestaña
  Responsables, y esa persona en su **`user_id`** de Monday.
- **Crear si no existe**: se envía `create_labels_if_missing`, así que si el
  cliente (o un label de estatus/departamento) **no existe** en el board, Monday
  **lo crea solo**. Por eso puedes usar clientes nuevos sin prepararlos antes.
- **Mapeo de estatus configurable**: como los estatus del board pueden llamarse
  distinto (ej. *Finalizada*, *En proceso*), en la pestaña Monday mapeas cada
  estado de la app a un **label** (texto) o un **índice** (número) del board.
  Si dejas un estatus vacío, esa columna simplemente no se toca.
- **Columna que no está configurada = se omite**, así un ítem nunca falla entero
  por un solo dato faltante.
- **Se envían de una en una**, con una pausa entre cada una (variable
  `MONDAY_DELAY`, 0.4s por defecto) y **reintento automático** si Monday responde
  con límite de tasa. Así no se saturan los límites de la API.

Al terminar, la app te dice **"Creadas X/Y tareas"** y, si alguna falló, el
**error exacto** que devolvió Monday.

---

## 6. Las vistas de la app (qué hace cada pestaña)

- **Cronograma**: la tabla editable de líneas y tareas. Aquí vive la cascada, el
  selector de departamentos responsables, el override de fecha de inicio y el
  check de "crear en Monday" (con botones *✓ Todos / ✕ Ninguno* por línea).
- **Gantt**: línea de trabajo = fila; tareas = barras posicionadas por fecha y
  coloreadas por departamento; marca el día de hoy y sombrea fines de semana.
- **Resumen**: métricas de avance por línea y del proyecto completo.
- **Responsables**: la persona (del catálogo) responsable de cada departamento en
  este proyecto — la que se dispara en Monday.
- **Feriados**: los días inhábiles que la cascada salta.
- **📁 Proyectos** (botón del header): lista todos los proyectos y todas las
  plantillas para **abrir/editar, exportar PDF o eliminar**.
- **⚙ Monday** (botón del header): Board ID, IDs de columnas, mapeo de estatus,
  catálogo de personas (con departamento y `user_id`) y catálogo de departamentos
  (con color, label e índice).

---

## 7. El modelo de datos (las "tablas") en lenguaje natural

Todo se guarda en una base de datos PostgreSQL. Cada "tabla" es una lista:

- **projects**: los proyectos (cliente, fecha de inicio, estado, cuándo se lanzó,
  y una copia del último payload enviado a Monday).
- **lines**: las líneas de trabajo de cada proyecto, con su orden.
- **tasks**: las tareas de cada línea (nombre, días, estado, responsable,
  de qué depende, fecha manual opcional, si va a Monday, y las fechas calculadas).
- **responsibles**: por proyecto y departamento, la persona y su email.
- **monday_people**: catálogo global de personas → `user_id` + departamento.
- **monday_departments**: catálogo global de departamentos → label, índice y color.
- **templates**: estructuras guardadas para reutilizar.
- **holidays**: días feriados.
- **config**: ajustes sueltos (Board ID, IDs de columnas, mapeo de estatus).

Cuando borras un proyecto, se borran en cascada sus líneas, tareas y responsables.

---

## 8. La arquitectura técnica (para quien mantenga el código)

Es una app web clásica y sencilla, sin frameworks pesados:

- **Backend**: Python con **Flask**. Expone una API REST (`/api/...`) que lee y
  escribe en PostgreSQL. Todo el backend vive en pocos archivos:
  - `app.py` — los endpoints (proyectos, líneas, tareas, catálogos, publicar).
  - `db.py` — conexión a Postgres, el esquema de tablas y las migraciones suaves.
  - `engine.py` — el motor de cascada de fechas.
  - `pdf_export.py` — el generador de PDF.
  - `seed.json` — las tareas base extraídas del Excel original.
- **Frontend**: un único archivo `static/index.html` con HTML + CSS + JavaScript
  puro (sin build, sin dependencias). Llama a la API con `fetch` y redibuja la
  pantalla. El logo está en `static/logo.png`.
- **Base de datos**: PostgreSQL. El esquema se crea solo al primer arranque, y las
  columnas nuevas se agregan con migraciones automáticas (`ALTER TABLE ... IF NOT
  EXISTS`), así que actualizar la app no rompe los datos existentes.
- **Servidor**: **gunicorn** sirve la app; el `Dockerfile` la empaqueta para
  **EasyPanel**. Variables de entorno: `DATABASE_URL` (Postgres),
  `MONDAY_API_TOKEN` (token de Monday) y, opcional, `MONDAY_DELAY`.

El "framework" del sistema, entonces, es este ciclo:

```
Interfaz (index.html)
      │  fetch /api/...
      ▼
API Flask (app.py) ──── motor de fechas (engine.py)
      │                        ▲
      │  lee/escribe            │ recalcula al cambiar algo
      ▼                        │
PostgreSQL (db.py) ────────────┘
      │
      │  al publicar: traduce a IDs y llama a la API de Monday (de una en una)
      ▼
   Monday.com
```

---

## 9. Cómo extenderlo (patrones que sigue el código)

- **Un dato nuevo en la tarea** → se agrega una columna en `db.py` (con su
  `ALTER TABLE ... IF NOT EXISTS`), se permite en el endpoint `update_task`, y se
  pinta en la tabla del Cronograma en `index.html`. (Así se agregaron el override
  de fecha y el check de Monday.)
- **Un catálogo nuevo** → tabla en `db.py` + endpoints GET/POST/PUT/DELETE en
  `app.py` + su tabla de edición en la pestaña Monday.
- **Otra regla de fechas** → se ajusta `recompute` en `engine.py`.
- **Otra columna en Monday** → se agrega su ID a la configuración y se arma su
  valor con el formato correcto en `build_payload` / `push_to_monday`.

En resumen: cada pieza está aislada y hace una sola cosa, para que agregar una
función sea "una columna + un endpoint + un control en la pantalla".
