"""
Zebra · Automatizador de Cronograma de Lanzamientos
Backend Flask + PostgreSQL. Listo para Git + EasyPanel (gunicorn).
"""
import os
import json
import time
import datetime
from flask import Flask, request, jsonify, send_from_directory
import db as DB
from db import connect, dict_cur, get_config, DEPTOS, CONFIG_KEYS
from engine import recompute

BASE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(BASE, "seed.json")
app = Flask(__name__, static_folder="static")

STATUSES = ["Pendiente", "En proceso", "Completado", "Bloqueado"]

# --------------------------------------------------------------------------- helpers
def iso(d):
    return d.isoformat() if isinstance(d, (datetime.date, datetime.datetime)) else d

def serialize(row):
    return {k: iso(v) for k, v in dict(row).items()}

def seed_structure():
    """Estructura base extraída del Excel original."""
    data = json.load(open(SEED, encoding="utf-8"))
    return [{"line": l["line"],
             "tasks": [{"name": t["name"], "days": t["dias"],
                        "responsible": t["resp"], "description": ""} for t in l["tasks"]]}
            for l in data]

def insert_structure(cur, pid, structure, keep_resp=True):
    """Inserta líneas y tareas con dependencia secuencial por defecto."""
    for li, line in enumerate(structure):
        cur.execute("INSERT INTO lines(project_id,name,position) VALUES(%s,%s,%s) RETURNING id",
                    (pid, line["line"], li))
        lid = cur.fetchone()["id"]
        prev = None
        for ti, t in enumerate(line["tasks"]):
            cur.execute(
                """INSERT INTO tasks(line_id,name,description,days,responsible,position,depends_on)
                   VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (lid, t["name"], t.get("description", ""), t.get("days", 0),
                 t.get("responsible", "") if keep_resp else "", ti, prev))
            prev = cur.fetchone()["id"]

# --------------------------------------------------------------------------- proyectos
@app.route("/api/projects", methods=["GET"])
def list_projects():
    con = connect()
    with dict_cur(con) as cur:
        cur.execute("SELECT * FROM projects ORDER BY id DESC")
        rows = [serialize(r) for r in cur.fetchall()]
    con.close()
    return jsonify(rows)

@app.route("/api/projects", methods=["POST"])
def create_project():
    d = request.json
    con = connect()
    with dict_cur(con) as cur:
        cur.execute("INSERT INTO projects(client,start_date) VALUES(%s,%s) RETURNING id",
                    (d["client"], d["start_date"]))
        pid = cur.fetchone()["id"]
        for dep in DEPTOS:
            cur.execute("INSERT INTO responsibles(project_id,depto) VALUES(%s,%s)", (pid, dep))
        # estructura: desde plantilla o desde la semilla del Excel
        tpl_id = d.get("template_id")
        if tpl_id:
            cur.execute("SELECT structure FROM templates WHERE id=%s", (tpl_id,))
            r = cur.fetchone()
            structure = r["structure"] if r else seed_structure()
            insert_structure(cur, pid, structure, keep_resp=False)
        else:
            insert_structure(cur, pid, seed_structure(), keep_resp=True)
    con.commit()
    recompute(con, pid)
    con.close()
    return jsonify({"id": pid})

@app.route("/api/projects/<int:pid>", methods=["GET"])
def get_project(pid):
    con = connect()
    with dict_cur(con) as cur:
        cur.execute("SELECT * FROM projects WHERE id=%s", (pid,))
        proj = cur.fetchone()
        if not proj:
            con.close()
            return jsonify({"error": "not found"}), 404
        cur.execute("SELECT * FROM lines WHERE project_id=%s ORDER BY position", (pid,))
        lines = cur.fetchall()
        out_lines = []
        for ln in lines:
            cur.execute("SELECT * FROM tasks WHERE line_id=%s ORDER BY position", (ln["id"],))
            d = serialize(ln)
            d["tasks"] = [serialize(t) for t in cur.fetchall()]
            out_lines.append(d)
        cur.execute("SELECT * FROM responsibles WHERE project_id=%s ORDER BY id", (pid,))
        resp = [serialize(r) for r in cur.fetchall()]
    con.close()
    return jsonify({"project": serialize(proj), "lines": out_lines,
                    "responsibles": resp, "deptos": DEPTOS, "statuses": STATUSES})

@app.route("/api/projects/<int:pid>", methods=["DELETE"])
def delete_project(pid):
    con = connect()
    with con.cursor() as cur:
        cur.execute("DELETE FROM projects WHERE id=%s", (pid,))
    con.commit(); con.close()
    return jsonify({"ok": True})

@app.route("/api/projects/<int:pid>/meta", methods=["PUT"])
def update_meta(pid):
    d = request.json
    con = connect()
    with con.cursor() as cur:
        for k in ("client", "start_date", "status"):
            if k in d:
                cur.execute(f"UPDATE projects SET {k}=%s WHERE id=%s", (d[k], pid))
    con.commit()
    recompute(con, pid)
    con.close()
    return jsonify({"ok": True})

# --------------------------------------------------------------------------- líneas
@app.route("/api/projects/<int:pid>/lines", methods=["POST"])
def add_line(pid):
    con = connect()
    with dict_cur(con) as cur:
        cur.execute("SELECT COALESCE(MAX(position),-1)+1 p FROM lines WHERE project_id=%s", (pid,))
        pos = cur.fetchone()["p"]
        cur.execute("INSERT INTO lines(project_id,name,position) VALUES(%s,%s,%s)",
                    (pid, request.json.get("name", "Nueva línea"), pos))
    con.commit(); con.close()
    return jsonify({"ok": True})

@app.route("/api/lines/<int:lid>", methods=["PUT"])
def rename_line(lid):
    con = connect()
    with con.cursor() as cur:
        cur.execute("UPDATE lines SET name=%s WHERE id=%s", (request.json["name"], lid))
    con.commit(); con.close()
    return jsonify({"ok": True})

@app.route("/api/lines/<int:lid>", methods=["DELETE"])
def del_line(lid):
    con = connect()
    with con.cursor() as cur:
        cur.execute("DELETE FROM lines WHERE id=%s", (lid,))
    con.commit(); con.close()
    return jsonify({"ok": True})

# --------------------------------------------------------------------------- tareas
def project_of_line(con, lid):
    with dict_cur(con) as cur:
        cur.execute("SELECT project_id FROM lines WHERE id=%s", (lid,))
        return cur.fetchone()["project_id"]

def project_of_task(con, tid):
    with dict_cur(con) as cur:
        cur.execute("SELECT l.project_id pid FROM tasks t JOIN lines l ON t.line_id=l.id WHERE t.id=%s", (tid,))
        row = cur.fetchone()
        return row["pid"] if row else None

@app.route("/api/lines/<int:lid>/tasks", methods=["POST"])
def add_task(lid):
    con = connect()
    with dict_cur(con) as cur:
        cur.execute("SELECT COALESCE(MAX(position),-1)+1 p FROM tasks WHERE line_id=%s", (lid,))
        pos = cur.fetchone()["p"]
        cur.execute("INSERT INTO tasks(line_id,name,days,position) VALUES(%s,%s,%s,%s)",
                    (lid, request.json.get("name", "Nueva tarea"), request.json.get("days", 1), pos))
    pid = project_of_line(con, lid)
    con.commit()
    recompute(con, pid)
    con.close()
    return jsonify({"ok": True})

@app.route("/api/tasks/<int:tid>", methods=["PUT"])
def update_task(tid):
    d = request.json
    con = connect()
    with con.cursor() as cur:
        for k in ("name", "description", "days", "status", "responsible", "depends_on"):
            if k in d:
                cur.execute(f"UPDATE tasks SET {k}=%s WHERE id=%s", (d[k], tid))
    pid = project_of_task(con, tid)
    con.commit()
    recompute(con, pid)
    con.close()
    return jsonify({"ok": True})

@app.route("/api/tasks/<int:tid>", methods=["DELETE"])
def del_task(tid):
    con = connect()
    pid = project_of_task(con, tid)
    with con.cursor() as cur:
        cur.execute("DELETE FROM tasks WHERE id=%s", (tid,))
    con.commit()
    if pid:
        recompute(con, pid)
    con.close()
    return jsonify({"ok": True})

# --------------------------------------------------------------------------- responsables del proyecto
@app.route("/api/responsibles/<int:rid>", methods=["PUT"])
def update_resp(rid):
    d = request.json
    con = connect()
    with con.cursor() as cur:
        for k in ("person", "email", "depto"):
            if k in d:
                cur.execute(f"UPDATE responsibles SET {k}=%s WHERE id=%s", (d[k], rid))
    con.commit(); con.close()
    return jsonify({"ok": True})

# auto-asignar: dado un depto, devolver la persona del catálogo del proyecto
@app.route("/api/projects/<int:pid>/resolve_person", methods=["GET"])
def resolve_person(pid):
    depto = request.args.get("depto", "")
    con = connect()
    with dict_cur(con) as cur:
        cur.execute("SELECT person FROM responsibles WHERE project_id=%s AND depto=%s", (pid, depto))
        r = cur.fetchone()
    con.close()
    return jsonify({"person": r["person"] if r and r["person"] else ""})

# --------------------------------------------------------------------------- resumen
@app.route("/api/projects/<int:pid>/summary", methods=["GET"])
def summary(pid):
    con = connect()
    with dict_cur(con) as cur:
        cur.execute("""
            SELECT l.name line, COUNT(t.id) total,
                   SUM(CASE WHEN t.status='Completado' THEN 1 ELSE 0 END) done,
                   MIN(t.start_date) ini, MAX(t.end_date) fin, COALESCE(SUM(t.days),0) dias
            FROM lines l LEFT JOIN tasks t ON t.line_id=l.id
            WHERE l.project_id=%s GROUP BY l.id, l.name, l.position ORDER BY l.position""", (pid,))
        lines = [serialize(r) for r in cur.fetchall()]
        cur.execute("""SELECT MIN(t.start_date) ini, MAX(t.end_date) fin
                       FROM tasks t JOIN lines l ON t.line_id=l.id WHERE l.project_id=%s""", (pid,))
        overall = serialize(cur.fetchone())
    con.close()
    return jsonify({"lines": lines, "overall": overall})

# --------------------------------------------------------------------------- catálogos Monday
@app.route("/api/monday/people", methods=["GET", "POST"])
def monday_people():
    con = connect()
    if request.method == "POST":
        d = request.json
        with con.cursor() as cur:
            cur.execute("""INSERT INTO monday_people(name,monday_user_id,department) VALUES(%s,%s,%s)
                           ON CONFLICT (name) DO UPDATE SET monday_user_id=EXCLUDED.monday_user_id,
                                                            department=EXCLUDED.department""",
                        (d["name"], d.get("monday_user_id", ""), d.get("department", "")))
        con.commit(); con.close()
        return jsonify({"ok": True})
    with dict_cur(con) as cur:
        cur.execute("SELECT * FROM monday_people ORDER BY name")
        rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return jsonify(rows)

@app.route("/api/monday/people/<int:pid>", methods=["PUT", "DELETE"])
def monday_person(pid):
    con = connect()
    with con.cursor() as cur:
        if request.method == "DELETE":
            cur.execute("DELETE FROM monday_people WHERE id=%s", (pid,))
        else:
            d = request.json
            for k in ("name", "monday_user_id", "department"):
                if k in d:
                    cur.execute(f"UPDATE monday_people SET {k}=%s WHERE id=%s", (d[k], pid))
    con.commit(); con.close()
    return jsonify({"ok": True})

@app.route("/api/monday/departments", methods=["GET", "POST"])
def monday_departments():
    con = connect()
    if request.method == "POST":
        d = request.json
        with con.cursor() as cur:
            cur.execute("""INSERT INTO monday_departments(name,monday_label,monday_index,color) VALUES(%s,%s,%s,%s)
                           ON CONFLICT (name) DO UPDATE SET monday_label=EXCLUDED.monday_label,
                                                            monday_index=EXCLUDED.monday_index,
                                                            color=EXCLUDED.color""",
                        (d["name"], d.get("monday_label", ""), d.get("monday_index"), d.get("color", "")))
        con.commit(); con.close()
        return jsonify({"ok": True})
    with dict_cur(con) as cur:
        cur.execute("SELECT * FROM monday_departments ORDER BY name")
        rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return jsonify(rows)

@app.route("/api/monday/departments/<int:did>", methods=["PUT", "DELETE"])
def monday_department(did):
    con = connect()
    with con.cursor() as cur:
        if request.method == "DELETE":
            cur.execute("DELETE FROM monday_departments WHERE id=%s", (did,))
        else:
            d = request.json
            for k in ("name", "monday_label", "monday_index", "color"):
                if k in d:
                    cur.execute(f"UPDATE monday_departments SET {k}=%s WHERE id=%s", (d[k], did))
    con.commit(); con.close()
    return jsonify({"ok": True})

# --------------------------------------------------------------------------- config (board_id, column_ids)
@app.route("/api/config", methods=["GET", "PUT"])
def config():
    con = connect()
    if request.method == "PUT":
        d = request.json
        with con.cursor() as cur:
            for k, v in d.items():
                cur.execute("""INSERT INTO config(key,value) VALUES(%s,%s)
                               ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value""", (k, v))
        con.commit(); con.close()
        return jsonify({"ok": True})
    cfg = get_config(con); con.close()
    return jsonify({"config": cfg, "keys": CONFIG_KEYS})

# --------------------------------------------------------------------------- feriados
@app.route("/api/holidays", methods=["GET", "POST"])
def holidays():
    con = connect()
    if request.method == "POST":
        d = request.json
        with con.cursor() as cur:
            cur.execute("INSERT INTO holidays(day,label) VALUES(%s,%s) ON CONFLICT (day) DO UPDATE SET label=EXCLUDED.label",
                        (d["day"], d.get("label", "")))
        con.commit(); con.close()
        return jsonify({"ok": True})
    with dict_cur(con) as cur:
        cur.execute("SELECT * FROM holidays ORDER BY day")
        rows = [serialize(r) for r in cur.fetchall()]
    con.close()
    return jsonify(rows)

@app.route("/api/holidays/<int:hid>", methods=["DELETE"])
def del_holiday(hid):
    con = connect()
    with con.cursor() as cur:
        cur.execute("DELETE FROM holidays WHERE id=%s", (hid,))
    con.commit(); con.close()
    return jsonify({"ok": True})

# --------------------------------------------------------------------------- plantillas (solo estructura)
@app.route("/api/templates", methods=["GET", "POST"])
def templates():
    con = connect()
    if request.method == "POST":
        d = request.json
        pid = d["project_id"]
        # extraer estructura del proyecto (líneas + tareas, sin responsables/fechas/estado)
        with dict_cur(con) as cur:
            cur.execute("SELECT * FROM lines WHERE project_id=%s ORDER BY position", (pid,))
            structure = []
            for ln in cur.fetchall():
                cur.execute("SELECT name,description,days,position FROM tasks WHERE line_id=%s ORDER BY position", (ln["id"],))
                tasks = [{"name": t["name"], "description": t["description"],
                          "days": t["days"]} for t in cur.fetchall()]
                structure.append({"line": ln["name"], "tasks": tasks})
            cur.execute("INSERT INTO templates(name,structure) VALUES(%s,%s) RETURNING id",
                        (d["name"], json.dumps(structure, ensure_ascii=False)))
            tid = cur.fetchone()["id"]
        con.commit(); con.close()
        return jsonify({"id": tid})
    with dict_cur(con) as cur:
        cur.execute("SELECT id,name,created_at FROM templates ORDER BY id DESC")
        rows = [serialize(r) for r in cur.fetchall()]
    con.close()
    return jsonify(rows)

@app.route("/api/templates/<int:tid>", methods=["DELETE"])
def del_template(tid):
    con = connect()
    with con.cursor() as cur:
        cur.execute("DELETE FROM templates WHERE id=%s", (tid,))
    con.commit(); con.close()
    return jsonify({"ok": True})

# --------------------------------------------------------------------------- validación previa al lanzamiento
def validate_project(con, pid):
    issues = []
    cfg = get_config(con)
    with dict_cur(con) as cur:
        cur.execute("""SELECT t.* FROM tasks t JOIN lines l ON t.line_id=l.id WHERE l.project_id=%s""", (pid,))
        tasks = cur.fetchall()
        no_resp = [t["name"] for t in tasks if not (t["responsible"] or "").strip()]
        if no_resp:
            issues.append({"level": "warn", "msg": f"{len(no_resp)} tarea(s) sin responsable"})
        # deptos usados en responsables del proyecto sin mapeo en catálogo
        cur.execute("SELECT DISTINCT depto FROM responsibles WHERE project_id=%s", (pid,))
        deptos = [r["depto"] for r in cur.fetchall()]
        cur.execute("SELECT name, monday_label FROM monday_departments")
        dept_map = {r["name"]: r["monday_label"] for r in cur.fetchall()}
        unmapped = [d for d in deptos if not dept_map.get(d)]
        if unmapped:
            issues.append({"level": "warn", "msg": f"Departamentos sin mapeo a Monday: {', '.join(unmapped)}"})
        # personas (responsables) sin user_id
        cur.execute("SELECT person FROM responsibles WHERE project_id=%s AND person<>''", (pid,))
        people = {r["person"] for r in cur.fetchall()}
        cur.execute("SELECT name, monday_user_id FROM monday_people")
        people_map = {r["name"]: r["monday_user_id"] for r in cur.fetchall()}
        no_id = [p for p in people if not people_map.get(p)]
        if no_id:
            issues.append({"level": "warn", "msg": f"Personas sin user_id de Monday: {', '.join(no_id)}"})
    if not cfg.get("monday_board_id"):
        issues.append({"level": "error", "msg": "Falta configurar el Board ID de Monday (pestaña Monday)"})
    return issues

@app.route("/api/projects/<int:pid>/validate", methods=["GET"])
def validate(pid):
    con = connect()
    issues = validate_project(con, pid)
    con.close()
    return jsonify({"issues": issues, "ok": not any(i["level"] == "error" for i in issues)})

# --------------------------------------------------------------------------- publicar a Monday
def build_payload(con, pid):
    data_resp = get_project(pid)
    data = data_resp.get_json()
    proj = data["project"]
    cfg = get_config(con)
    with dict_cur(con) as cur:
        cur.execute("SELECT name, monday_user_id, department FROM monday_people")
        people_rows = cur.fetchall()
        cur.execute("SELECT name, monday_label, monday_index, color FROM monday_departments")
        dept_map = {r["name"]: {"label": r["monday_label"], "index": r["monday_index"],
                                "color": r["color"]} for r in cur.fetchall()}
        # responsable elegido por departamento EN ESTE PROYECTO (pestaña Responsables)
        cur.execute("SELECT depto, person FROM responsibles WHERE project_id=%s", (pid,))
        proj_resp = {r["depto"]: (r["person"] or "").strip() for r in cur.fetchall()}

    people_map = {r["name"]: r["monday_user_id"] for r in people_rows}
    # depto -> lista de user_ids de las personas (con id) que pertenecen a ese departamento
    people_by_dept = {}
    for r in people_rows:
        if r["department"] and r["monday_user_id"]:
            people_by_dept.setdefault(r["department"], []).append(r["monday_user_id"])

    def person_ids(responsible):
        # 'responsible' lista los departamentos (separados por coma) de la tarea.
        # Para cada depto se usa la persona asignada en la pestaña Responsables del proyecto,
        # traducida a su user_id de Monday. Si no hay asignada, cae al catálogo del depto.
        ids = []
        def add(uid):
            if uid and uid not in ids:
                ids.append(uid)
        for part in (responsible or "").split(","):
            dep = part.strip()
            if not dep:
                continue
            assigned = proj_resp.get(dep, "")            # persona elegida para ese depto
            if assigned and people_map.get(assigned):    # 1) asignada en el proyecto + con user_id
                add(people_map[assigned])
                continue
            for uid in people_by_dept.get(dep, []):       # 2) fallback: catálogo del depto
                add(uid)
            add(people_map.get(dep))                      # 3) por si 'dep' nombra a la persona directo
        return ids

    client = proj["client"]
    payload = {
        "board_id": cfg.get("monday_board_id", ""),
        "board_name": f"Lanzamiento · {client}",
        "client": client,
        "columns": {  # rol lógico -> id de columna en Monday
            "status": cfg.get("col_status", ""),
            "person": cfg.get("col_person_esp", ""),
            "department": cfg.get("col_department", ""),
            "client": cfg.get("col_client", ""),
            "deadline": cfg.get("col_deadline", ""),
        },
        "groups": [],
    }
    for ln in data["lines"]:
        g = {"title": ln["name"], "items": []}
        for t in ln["tasks"]:
            dep_info = dept_map.get((t.get("responsible") or "").split(",")[0].strip(), {})
            g["items"].append({
                "name": f"Lanzamiento | {client} | {t['name']}",
                "task": t["name"],
                "description": t.get("description", ""),
                "status": t["status"],
                "person_ids": person_ids(t["responsible"]),
                "department": dep_info.get("label") or "",
                "deadline": t["end_date"],
            })
        payload["groups"].append(g)
    return payload

# --------------------------------------------------------------------------- API Monday (mutations reales)
# Pausa entre llamadas para respetar los límites de tasa de Monday (se envían de uno en uno).
MONDAY_DELAY = float(os.environ.get("MONDAY_DELAY", "0.4"))

def _monday_gql(token, query, variables, tries=4):
    """POST GraphQL a Monday con reintento ante límite de tasa (HTTP 429 o 'complexity budget')."""
    import urllib.request, urllib.error
    body = json.dumps({"query": query, "variables": variables}).encode()
    res = {}
    for attempt in range(tries):
        req = urllib.request.Request(
            "https://api.monday.com/v2", data=body,
            headers={"Authorization": token, "Content-Type": "application/json", "API-Version": "2024-01"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                res = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < tries - 1:
                wait = 0
                try:
                    wait = int(e.headers.get("Retry-After", "0"))
                except (TypeError, ValueError):
                    wait = 0
                time.sleep(min(max(wait, 5 * (attempt + 1)), 60))
                continue
            raise
        # el límite por minuto a veces llega como HTTP 200 con 'errors'
        if "limit" in json.dumps(res.get("errors") or "").lower() and attempt < tries - 1:
            time.sleep(min(10 * (attempt + 1), 60))
            continue
        return res
    return res

def push_to_monday(token, payload):
    """Crea un grupo por línea y un ítem por tarea en el board configurado, de uno en uno.
    Devuelve (creadas, [errores])."""
    board = str(payload["board_id"])
    cols = payload["columns"]
    created, errors = 0, []
    Q_GROUP = "mutation($b:ID!,$n:String!){create_group(board_id:$b,group_name:$n){id}}"
    Q_ITEM = ("mutation($b:ID!,$g:String,$n:String!,$c:JSON){"
              "create_item(board_id:$b,group_id:$g,item_name:$n,column_values:$c){id}}")
    for g in payload["groups"]:
        gid = None
        try:
            res = _monday_gql(token, Q_GROUP, {"b": board, "n": g["title"][:255]})
            gid = (res.get("data") or {}).get("create_group", {}).get("id")
            if not gid:
                errors.append(f"grupo «{g['title']}»: {res.get('errors')}")
        except Exception as e:
            errors.append(f"grupo «{g['title']}»: {e}")
        time.sleep(MONDAY_DELAY)
        for it in g["items"]:
            cv = {}
            if cols.get("status") and it.get("status"):
                cv[cols["status"]] = {"label": it["status"]}
            if cols.get("department") and it.get("department"):
                cv[cols["department"]] = {"label": it["department"]}
            if cols.get("deadline") and it.get("deadline"):
                cv[cols["deadline"]] = {"date": str(it["deadline"])[:10]}
            if cols.get("client") and payload.get("client"):
                cv[cols["client"]] = payload["client"]
            ids = [int(x) for x in (it.get("person_ids") or []) if str(x).isdigit()]
            if cols.get("person") and ids:
                cv[cols["person"]] = {"personsAndTeams": [{"id": i, "kind": "person"} for i in ids]}
            try:
                res = _monday_gql(token, Q_ITEM,
                                  {"b": board, "g": gid, "n": it["name"][:255], "c": json.dumps(cv)})
                if (res.get("data") or {}).get("create_item", {}).get("id"):
                    created += 1
                else:
                    errors.append(f"ítem «{it['task']}»: {res.get('errors')}")
            except Exception as e:
                errors.append(f"ítem «{it['task']}»: {e}")
            time.sleep(MONDAY_DELAY)  # de uno en uno, respetando límites de Monday
    return created, errors

@app.route("/api/projects/<int:pid>/launch", methods=["POST"])
def launch(pid):
    con = connect()
    issues = validate_project(con, pid)
    if any(i["level"] == "error" for i in issues) and not request.json.get("force"):
        con.close()
        return jsonify({"ok": False, "blocked": True, "issues": issues})

    payload = build_payload(con, pid)
    token = os.environ.get("MONDAY_API_TOKEN", "").strip()
    ok, detail = False, ""
    total = sum(len(g["items"]) for g in payload["groups"])
    if token and payload["board_id"]:
        try:
            created, errors = push_to_monday(token, payload)
            ok = created > 0 and not errors
            detail = f"Creadas {created}/{total} tarea(s) en Monday."
            if errors:
                detail += " Errores: " + " · ".join(str(e)[:140] for e in errors[:3])
                if len(errors) > 3:
                    detail += f" (+{len(errors)-3} más)"
        except Exception as e:
            detail = f"Error API Monday: {e}"
    else:
        ok = True
        detail = ("Modo simulación: payload generado y traducido a IDs. "
                  "Configura MONDAY_API_TOKEN (variable de entorno) y el Board ID para envío real.")

    with con.cursor() as cur:
        cur.execute("UPDATE projects SET status='Lanzado', launched_at=now(), monday_payload=%s WHERE id=%s",
                    (json.dumps(payload, ensure_ascii=False), pid))
    con.commit(); con.close()
    return jsonify({"ok": ok, "detail": detail, "payload": payload, "issues": issues})

# --------------------------------------------------------------------------- PDF
@app.route("/api/projects/<int:pid>/pdf", methods=["GET"])
def export_pdf(pid):
    from pdf_export import generate_pdf
    con = connect()
    data = get_project(pid).get_json()
    s = summary(pid).get_json()
    con.close()
    path = generate_pdf(data, s)
    return send_from_directory(os.path.dirname(path), os.path.basename(path),
                               as_attachment=True, download_name=f"Cronograma_{data['project']['client']}.pdf")

# --------------------------------------------------------------------------- static / health
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/health")
def health():
    return jsonify({"ok": True})

# inicializa el esquema al importar (gunicorn) y al correr directo
try:
    DB.init_db()
except Exception as _e:
    print("init_db diferido:", _e)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
