"""
Zebra · capa de datos (PostgreSQL).
Conexión por DATABASE_URL (la inyecta EasyPanel) con fallback a variables sueltas.
"""
import os
import psycopg2
import psycopg2.extras

def _dsn():
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    return dict(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD", "postgres"),
        dbname=os.environ.get("PGDATABASE", "zebra"),
    )

def connect():
    dsn = _dsn()
    if isinstance(dsn, str):
        con = psycopg2.connect(dsn)
    else:
        con = psycopg2.connect(**dsn)
    con.autocommit = False
    return con

def dict_cur(con):
    return con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects(
  id SERIAL PRIMARY KEY,
  client TEXT NOT NULL,
  start_date DATE NOT NULL,
  status TEXT DEFAULT 'En proceso',
  created_at TIMESTAMP DEFAULT now(),
  launched_at TIMESTAMP,
  monday_payload JSONB
);
CREATE TABLE IF NOT EXISTS lines(
  id SERIAL PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  position INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks(
  id SERIAL PRIMARY KEY,
  line_id INTEGER NOT NULL REFERENCES lines(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT DEFAULT '',
  days REAL DEFAULT 0,
  status TEXT DEFAULT 'Pendiente',
  responsible TEXT DEFAULT '',
  position INTEGER NOT NULL,
  depends_on INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
  start_date DATE,
  end_date DATE
);
CREATE TABLE IF NOT EXISTS responsibles(
  id SERIAL PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  depto TEXT NOT NULL,
  person TEXT DEFAULT '',
  email TEXT DEFAULT ''
);
-- catálogo global de personas Zebra -> user_id de Monday
CREATE TABLE IF NOT EXISTS monday_people(
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  monday_user_id TEXT DEFAULT ''
);
-- catálogo global de departamentos -> label/índice de la columna status "Departamento"
CREATE TABLE IF NOT EXISTS monday_departments(
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  monday_label TEXT DEFAULT '',
  monday_index INTEGER
);
-- plantillas (solo estructura: líneas + tareas con días y dependencias)
CREATE TABLE IF NOT EXISTS templates(
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT now(),
  structure JSONB NOT NULL
);
-- feriados que la cascada salta
CREATE TABLE IF NOT EXISTS holidays(
  id SERIAL PRIMARY KEY,
  day DATE NOT NULL UNIQUE,
  label TEXT DEFAULT ''
);
-- configuración (board_id, column_ids de Monday, etc.)
CREATE TABLE IF NOT EXISTS config(
  key TEXT PRIMARY KEY,
  value TEXT DEFAULT ''
);
"""

DEPTOS = ["Success M", "Media", "CRM", "iA", "Creativo", "Admin", "Cliente"]

# claves de configuración esperadas (column_ids del board de Monday)
CONFIG_KEYS = [
    "monday_board_id",
    "col_status",       # columna Estatus
    "col_person_esp",   # columna Especialista (people)
    "col_person_sm",    # columna SM (people)
    "col_department",   # columna Departamento (status)
    "col_client",       # columna Cliente (text)
    "col_deadline",     # columna Fecha límite (date)
]

def init_db():
    con = connect()
    with con.cursor() as cur:
        cur.execute(SCHEMA)
        # sembrar claves de config vacías si no existen
        for k in CONFIG_KEYS:
            cur.execute("INSERT INTO config(key,value) VALUES(%s,'') ON CONFLICT (key) DO NOTHING", (k,))
    con.commit()
    con.close()

def get_config(con):
    with dict_cur(con) as cur:
        cur.execute("SELECT key,value FROM config")
        return {r["key"]: r["value"] for r in cur.fetchall()}
