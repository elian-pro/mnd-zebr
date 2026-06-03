"""
Generador de PDF del cronograma con la identidad visual Zebra:
fondo negro de cabecera, logo ZEBRA, banda dorada, cards de métricas y tablas
con encabezado oscuro. Usa reportlab (Python puro, sin libs de sistema).
"""
import os
import datetime
import tempfile
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                 KeepTogether, Frame, PageTemplate, BaseDocTemplate)
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.utils import ImageReader

LOGO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "logo.png")

INK = colors.HexColor("#111315")
GOLD = colors.HexColor("#C9A227")
SOFT = colors.HexColor("#F6F7F8")
MUTED = colors.HexColor("#6B7177")
LINE = colors.HexColor("#E4E7EA")
OK = colors.HexColor("#1F9D55")
PROC = colors.HexColor("#2563EB")
PEND = colors.HexColor("#9AA0A6")
BLOCK = colors.HexColor("#E02424")

ST_COLORS = {"Completado": OK, "En proceso": PROC, "Pendiente": PEND, "Bloqueado": BLOCK}

def _fmt(d):
    if not d:
        return "—"
    try:
        y, m, day = str(d)[:10].split("-")
        return f"{day}/{m}/{y}"
    except Exception:
        return str(d)

def _styles():
    ss = getSampleStyleSheet()
    out = {}
    out["h1"] = ParagraphStyle("h1", parent=ss["Title"], fontName="Helvetica-Bold",
                               fontSize=22, textColor=INK, spaceAfter=2, leading=26)
    out["sub"] = ParagraphStyle("sub", parent=ss["Normal"], fontSize=10, textColor=MUTED, spaceAfter=14)
    out["h2"] = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold",
                               fontSize=13, textColor=INK, spaceBefore=14, spaceAfter=8)
    out["cell"] = ParagraphStyle("cell", parent=ss["Normal"], fontSize=8.5, textColor=INK, leading=11)
    out["cellmuted"] = ParagraphStyle("cellmuted", parent=ss["Normal"], fontSize=8, textColor=MUTED, leading=10)
    out["desc"] = ParagraphStyle("desc", parent=ss["Normal"], fontSize=7.5, textColor=MUTED, leading=9.5)
    out["th"] = ParagraphStyle("th", parent=ss["Normal"], fontName="Helvetica-Bold",
                               fontSize=8, textColor=colors.white, leading=10)
    out["metriclbl"] = ParagraphStyle("ml", parent=ss["Normal"], fontSize=7.5, textColor=MUTED)
    out["metricval"] = ParagraphStyle("mv", parent=ss["Normal"], fontName="Helvetica-Bold",
                                       fontSize=16, textColor=INK)
    return out

def _header_footer(canvas, doc):
    canvas.saveState()
    w, h = letter
    # banda negra superior
    canvas.setFillColor(INK)
    canvas.rect(0, h - 70, w, 70, fill=1, stroke=0)
    # logo Zebra (blanco) sobre la banda; fallback a texto si falta el archivo
    drew_logo = False
    if os.path.exists(LOGO):
        try:
            img = ImageReader(LOGO)
            iw0, ih0 = img.getSize()
            ih = 46
            iw = ih * (iw0 / ih0) if ih0 else ih
            canvas.drawImage(img, 40, h - 35 - ih / 2, width=iw, height=ih, mask="auto")
            drew_logo = True
        except Exception:
            drew_logo = False
    if not drew_logo:
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 20)
        canvas.drawString(40, h - 42, "Z E B R A")
    # etiqueta a la derecha
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#9AA0A6"))
    canvas.drawRightString(w - 40, h - 42, "C R O N O G R A M A   D E   L A N Z A M I E N T O")
    # banda dorada
    canvas.setFillColor(GOLD)
    canvas.rect(0, h - 74, w, 4, fill=1, stroke=0)
    # pie
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(40, 24, f"Generado: {datetime.date.today().strftime('%d/%m/%Y')}")
    canvas.drawRightString(w - 40, 24, f"Página {doc.page}")
    canvas.restoreState()

def _metric_cards(metrics, st):
    cells = []
    for label, value in metrics:
        inner = Table([[Paragraph(label.upper(), st["metriclbl"])],
                       [Paragraph(str(value), st["metricval"])]], colWidths=[120])
        inner.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), SOFT),
            ("BOX", (0, 0), (-1, -1), 0.5, LINE),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        cells.append(inner)
    t = Table([cells], colWidths=[130] * len(cells))
    t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t

def generate_pdf(data, summ):
    st = _styles()
    proj = data["project"]
    tmp = tempfile.gettempdir()
    safe = "".join(c for c in proj["client"] if c.isalnum() or c in " _-").strip().replace(" ", "_")
    path = os.path.join(tmp, f"Cronograma_{safe or 'proyecto'}.pdf")

    doc = BaseDocTemplate(path, pagesize=letter,
                          leftMargin=40, rightMargin=40, topMargin=90, bottomMargin=40)
    frame = Frame(doc.leftMargin, doc.bottomMargin,
                  doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="zebra", frames=[frame], onPage=_header_footer)])

    story = []
    story.append(Paragraph(proj["client"], st["h1"]))
    story.append(Paragraph(f"Cronograma de lanzamiento · Estado: {proj['status']}", st["sub"]))

    # métricas
    total_tasks = sum(len(l["tasks"]) for l in data["lines"])
    done_tasks = sum(1 for l in data["lines"] for t in l["tasks"] if t["status"] == "Completado")
    metrics = [
        ("Inicio", _fmt(proj["start_date"])),
        ("Cierre estimado", _fmt(summ["overall"].get("fin"))),
        ("Líneas", len(data["lines"])),
        ("Tareas", f"{done_tasks}/{total_tasks}"),
    ]
    story.append(_metric_cards(metrics, st))
    story.append(Spacer(1, 8))

    # resumen por línea
    story.append(Paragraph("Resumen por línea de trabajo", st["h2"]))
    head = [Paragraph(x, st["th"]) for x in ["Línea", "Avance", "Inicio", "Fin", "Días"]]
    rows = [head]
    for l in summ["lines"]:
        total = l["total"] or 0
        done = l["done"] or 0
        pct = round((done / total) * 100) if total else 0
        rows.append([
            Paragraph(l["line"], st["cell"]),
            Paragraph(f"{done}/{total} ({pct}%)", st["cell"]),
            Paragraph(_fmt(l["ini"]), st["cellmuted"]),
            Paragraph(_fmt(l["fin"]), st["cellmuted"]),
            Paragraph(str(l["dias"]), st["cellmuted"]),
        ])
    t = Table(rows, colWidths=[200, 90, 70, 70, 40])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SOFT]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(t)

    # tareas por línea
    for l in data["lines"]:
        story.append(Paragraph(l["name"], st["h2"]))
        head = [Paragraph(x, st["th"]) for x in ["Tarea", "Estado", "Días", "Inicio", "Final", "Responsable"]]
        rows = [head]
        styles_rows = []
        for idx, tk in enumerate(l["tasks"], start=1):
            name_block = [Paragraph(tk["name"], st["cell"])]
            if (tk.get("description") or "").strip():
                name_block.append(Paragraph(tk["description"], st["desc"]))
            rows.append([
                name_block,
                Paragraph(tk["status"], st["cell"]),
                Paragraph(str(tk["days"]), st["cellmuted"]),
                Paragraph(_fmt(tk["start_date"]), st["cellmuted"]),
                Paragraph(_fmt(tk["end_date"]), st["cellmuted"]),
                Paragraph(tk.get("responsible") or "—", st["cellmuted"]),
            ])
            c = ST_COLORS.get(tk["status"], PEND)
            styles_rows.append(("TEXTCOLOR", (1, idx), (1, idx), c))
        t = Table(rows, colWidths=[210, 60, 30, 55, 55, 90])
        base = [
            ("BACKGROUND", (0, 0), (-1, 0), INK),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SOFT]),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
        t.setStyle(TableStyle(base + styles_rows))
        story.append(t)

    # responsables
    story.append(Paragraph("Responsables por departamento", st["h2"]))
    head = [Paragraph(x, st["th"]) for x in ["Departamento", "Persona", "Email"]]
    rows = [head]
    for r in data["responsibles"]:
        rows.append([Paragraph(r["depto"], st["cell"]),
                     Paragraph(r.get("person") or "—", st["cellmuted"]),
                     Paragraph(r.get("email") or "—", st["cellmuted"])])
    t = Table(rows, colWidths=[150, 170, 180])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SOFT]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(t)

    doc.build(story)
    return path
