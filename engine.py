"""
Motor de cálculo de fechas en cascada.
- Días hábiles (lun-vie), saltando además los feriados configurados.
- Cada tarea inicia al máximo entre: inicio del proyecto, fin de la tarea anterior
  de su línea, y fin de la tarea de la que depende (depends_on, puede ser de otra línea).
"""
import datetime
from db import dict_cur

def _load_holidays(con):
    with dict_cur(con) as cur:
        cur.execute("SELECT day FROM holidays")
        return {r["day"] for r in cur.fetchall()}

def _is_working(d, holidays):
    return d.weekday() < 5 and d not in holidays

def _next_working(d, holidays):
    while not _is_working(d, holidays):
        d += datetime.timedelta(days=1)
    return d

def add_working_days(start, days, holidays):
    """Suma 'days' días hábiles desde start. Fracción -> redondeo hacia arriba a 1 día."""
    whole = int(days)
    frac = days - whole
    steps = whole + (1 if frac > 0 else 0)
    d = start
    moved = 0
    while moved < steps:
        d += datetime.timedelta(days=1)
        if _is_working(d, holidays):
            moved += 1
    return d

def recompute(con, project_id):
    holidays = _load_holidays(con)
    with dict_cur(con) as cur:
        cur.execute("SELECT * FROM projects WHERE id=%s", (project_id,))
        proj = cur.fetchone()
        if not proj:
            return
        pstart = proj["start_date"]
        cur.execute("SELECT * FROM lines WHERE project_id=%s ORDER BY position", (project_id,))
        lines = cur.fetchall()
        line_tasks = {}
        for ln in lines:
            cur.execute("SELECT * FROM tasks WHERE line_id=%s ORDER BY position", (ln["id"],))
            line_tasks[ln["id"]] = cur.fetchall()

    computed = {}  # task_id -> (start, end)

    # varias pasadas para resolver dependencias cruzadas entre líneas
    for _ in range(6):
        for ln in lines:
            prev_end = None
            for t in line_tasks[ln["id"]]:
                candidates = [pstart]
                if prev_end:
                    candidates.append(prev_end)
                dep = t["depends_on"]
                if dep and dep in computed:
                    candidates.append(computed[dep][1])
                start = max(candidates)
                start = _next_working(start, holidays)
                end = add_working_days(start, t["days"], holidays) if t["days"] > 0 else start
                computed[t["id"]] = (start, end)
                prev_end = end

    with con.cursor() as cur:
        for tid, (s, e) in computed.items():
            cur.execute("UPDATE tasks SET start_date=%s, end_date=%s WHERE id=%s", (s, e, tid))
    con.commit()
