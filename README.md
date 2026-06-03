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

## Qué hace

**Cronograma**
- Panel editable en línea: tareas, días, estado, responsable, descripción.
- **Cascada automática**: cambias los días de una tarea y se recalculan las fechas
  de las que dependen. Salta fines de semana **y feriados**.
- **Dependencias**: cada tarea sigue a la anterior de su línea ("Secuencial") o puede
  depender de cualquier otra tarea (incluso de otra línea).
- Agregar / renombrar / quitar líneas paralelas y tareas.

**Resumen** — avance %, fechas y días por línea + arranque/cierre global. Se guarda en BD.

**Responsables** — persona y email por departamento del proyecto.

**Feriados** — lista editable de días inhábiles que la cascada respeta.

**Monday (⚙ en la barra superior)**
- **Board ID + IDs de columnas** del board destino.
- **Catálogo de personas** → user_id de Monday.
- **Catálogo de departamentos** → label / índice de la columna status.
- Al publicar, los responsables y deptos se **traducen a esos IDs**.

**Plantillas** — "Guardar como plantilla" congela la estructura (líneas, tareas, días,
descripciones; sin responsables/fechas/estados). Al crear un proyecto nuevo eliges
partir de una plantilla o de la estructura original del Excel.

**PDF** — botón ⬇ PDF exporta el cronograma con la identidad Zebra (logo, banda dorada,
cards de métricas, tablas, descripciones de tareas).

**Publicar a Monday** — valida primero (tareas sin responsable, deptos/personas sin
mapeo, board sin configurar), arma el payload con IDs traducidos, lo guarda en BD y
marca el proyecto como Lanzado. Con `MONDAY_API_TOKEN` + Board ID hace la llamada real;
sin ellos, queda en modo simulación mostrando el payload.

---

## Estructura del repo

```
.
├── app.py            # Endpoints Flask
├── db.py             # Conexión Postgres + esquema
├── engine.py         # Motor de cascada (dependencias, fines de semana, feriados)
├── pdf_export.py     # Generador de PDF con formato Zebra
├── seed.json         # 52 tareas extraídas del Excel original
├── static/
│   └── index.html    # Toda la interfaz
├── Dockerfile        # Imagen para EasyPanel
├── requirements.txt
├── .env.example
└── README.md
```

---

## Pendiente para envío real a Monday

Para que la publicación cree ítems reales necesito (del API de Monday):
1. El **board_id** del board "* CREACIÓN DE TAREAS *".
2. Los **column_id** de: Estatus, Especialista, Departamento, SM, Cliente, Fecha límite.

Esos se cargan en la pestaña **Monday** de la app. Mientras tanto, la mutación incluida
verifica la conexión y el payload queda listo y traducido para mandarse.

Las columnas "Especialista: Tiempo dedicado" y "SM: Tiempo dedicado" **no se usan**
(se omiten del payload, como pediste).
