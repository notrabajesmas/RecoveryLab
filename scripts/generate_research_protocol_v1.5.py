#!/usr/bin/env python3
"""
Generate Research Protocol v1.5 — RecoveryLab
===============================================
Fifth revision incorporating fourth round of external review (final audit).

Key changes from v1.4:
  1. Section 23: Decision Log (why decisions were made, not just what happened)
  2. Section 24: Evidence Debt (like technical debt, but for evidence gaps)
  3. Section 25: Phase A Graduation Criteria (formal exit criteria)
  4. Cover page updated with graduation criteria and final meta-rule
  5. Meta-rule extended: "Cada nuevo documento, modulo o algoritmo debe responder:
     Reduce una deuda de evidencia identificada?"
  6. Complexity risk explicitly acknowledged as the new threat
"""

import sys
import os

DOCX_SCRIPTS = os.path.join("/home/z/my-project/skills/docx", "scripts")
if DOCX_SCRIPTS not in sys.path:
    sys.path.insert(0, DOCX_SCRIPTS)

from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.section import WD_ORIENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml
import datetime

# ─── Color Palette ────────────────────────────────────────────────────────────
P = {
    "primary": "#162032",
    "body": "#1C2A3D",
    "secondary": "#5B6B7D",
    "accent": "#8B7E5A",
    "surface": "#F5F7FA",
    "white": "#FFFFFF",
    "star_gold": "#C9A84C",
    "star_dim": "#B0B0B0",
    "red": "#C0392B",
    "green": "#27AE60",
    "orange": "#E67E22",
    "blue": "#2980B9",
    "threat_open": "#E74C3C",
    "threat_mitigated": "#F39C12",
    "threat_resolved": "#27AE60",
    "debt_critical": "#C0392B",
    "debt_high": "#E67E22",
    "debt_medium": "#F39C12",
    "debt_low": "#27AE60",
}

def c(hex_color):
    hex_color = hex_color.replace("#", "")
    return RGBColor(int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))

def set_cell_shading(cell, color_hex):
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex.replace("#", "")}"/>')
    cell._tc.get_or_add_tcPr().append(shading)

def add_styled_table(doc, headers, rows, col_widths=None):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = 'Table Grid'
    for i, header in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = ""
        p = cell.paragraphs[0]
        run = p.add_run(header)
        run.bold = True
        run.font.size = Pt(10)
        run.font.color.rgb = c(P["white"])
        run.font.name = "Calibri"
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_cell_shading(cell, P["primary"])
    for row_idx, row_data in enumerate(rows):
        for col_idx, cell_text in enumerate(row_data):
            cell = table.rows[row_idx + 1].cells[col_idx]
            cell.text = ""
            p = cell.paragraphs[0]
            run = p.add_run(str(cell_text))
            run.font.size = Pt(9.5)
            run.font.name = "Calibri"
            run.font.color.rgb = c(P["body"])
            if row_idx % 2 == 1:
                set_cell_shading(cell, P["surface"])
    if col_widths:
        for row in table.rows:
            for idx, width in enumerate(col_widths):
                if idx < len(row.cells):
                    row.cells[idx].width = Cm(width)
    return table

def add_callout_box(doc, title, text, color=P["accent"]):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run(title)
    run.bold = True
    run.font.size = Pt(11)
    run.font.color.rgb = c(color)
    run.font.name = "Calibri"
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.5)
    run = p.add_run(text)
    run.font.size = Pt(11)
    run.font.name = "Calibri"
    run.font.color.rgb = c(P["body"])
    run.italic = True


def build_research_protocol():
    doc = Document()

    # ─── Page Setup ────────────────────────────────────────────────────────
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(3.0)
    section.right_margin = Cm(2.5)

    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(11)
    font.color.rgb = c(P["body"])

    # ═══════════════════════════════════════════════════════════════════════
    # COVER PAGE
    # ═══════════════════════════════════════════════════════════════════════
    for _ in range(3):
        doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("RECOVERYLAB")
    run.font.size = Pt(14)
    run.font.color.rgb = c(P["secondary"])
    run.font.name = "Calibri"
    run.bold = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("Research Protocol v1.5")
    run.font.size = Pt(28)
    run.font.color.rgb = c(P["primary"])
    run.font.name = "Calibri"
    run.bold = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("De la produccion de software a la produccion de evidencia")
    run.font.size = Pt(14)
    run.font.color.rgb = c(P["accent"])
    run.font.name = "Calibri"
    run.italic = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("Revision incorporando auditoria externa final (ronda 4)")
    run.font.size = Pt(11)
    run.font.color.rgb = c(P["secondary"])
    run.font.name = "Calibri"

    # ── Meta-Rule ──
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(16)
    p.paragraph_format.space_after = Pt(8)
    run = p.add_run("META-REGLA")
    run.font.size = Pt(10)
    run.font.color.rgb = c(P["secondary"])
    run.bold = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run("No agregar una sola caracteristica nueva si no aumenta la calidad de la evidencia.")
    run.font.size = Pt(13)
    run.font.color.rgb = c(P["red"])
    run.bold = True
    run.italic = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(8)
    run = p.add_run("Cada nuevo documento, modulo o algoritmo debe responder:\n"
                     "Reduce una deuda de evidencia identificada?")
    run.font.size = Pt(12)
    run.font.color.rgb = c(P["blue"])
    run.bold = True
    run.italic = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("_" * 50)
    run.font.color.rgb = c(P["accent"])
    run.font.size = Pt(10)

    # ── KPI Heroes ──
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run("KPI PRIMARIO")
    run.font.size = Pt(10)
    run.font.color.rgb = c(P["secondary"])
    run.bold = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run("Reproducible Claims Ratio (RCR)")
    run.font.size = Pt(16)
    run.font.color.rgb = c(P["blue"])
    run.bold = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run("Claims totales: 5 | Reproducibles: 0 | RCR = 0%")
    run.font.size = Pt(12)
    run.font.color.rgb = c(P["accent"])
    run.bold = True

    # ── Graduation Criteria ──
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run("CRITERIO DE GRADUACION FASE A")
    run.font.size = Pt(10)
    run.font.color.rgb = c(P["secondary"])
    run.bold = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run("RCR >= 80% | 5+ Claims en ★★★ | Judge estable | Baseline completo | RVS calibrado")
    run.font.size = Pt(10)
    run.font.color.rgb = c(P["green"])
    run.bold = True

    # ── Secondary KPI ──
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    run = p.add_run("Resultados con 3+ estrellas: 2 / 15")
    run.font.size = Pt(11)
    run.font.color.rgb = c(P["accent"])
    run.bold = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("_" * 50)
    run.font.color.rgb = c(P["accent"])
    run.font.size = Pt(10)

    # ── 7 Sacred Rules ──
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    run = p.add_run("Las 7 Reglas Sagradas")
    run.font.size = Pt(10)
    run.font.color.rgb = c(P["secondary"])
    run.bold = True

    rules = [
        "1. Congelar hipotesis — H1-H8 no se reescriben",
        "2. KPI de evidencia — no de codigo",
        "3. Tres niveles — /data, /analysis, /claims",
        "4. Evidence Gate — lenguaje controlado por nivel de evidencia",
        "5. RVS con usuarios — calibracion con datos reales",
        "6. Separar observacion de explicacion — lo mas estricto",
        "7. Solo reducir deuda de evidencia — cada nuevo modulo debe justificarse",
    ]
    for rule in rules:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(rule)
        run.font.size = Pt(9)
        run.font.color.rgb = c(P["body"])

    # Metadata
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(10)
    run = p.add_run(f"Documento vivo - Version 1.5 | {datetime.datetime.now().strftime('%Y-%m-%d')}")
    run.font.size = Pt(11)
    run.font.color.rgb = c(P["secondary"])

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("Clasificacion: INTERNO - Solo para uso del laboratorio")
    run.font.size = Pt(10)
    run.font.color.rgb = c(P["red"])

    # Change log
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(10)
    run = p.add_run("Cambios respecto a v1.4")
    run.font.size = Pt(10)
    run.font.color.rgb = c(P["secondary"])
    run.bold = True

    changes = [
        "Nueva Seccion 23: Decision Log (por que se decidio, no solo que paso)",
        "Nueva Seccion 24: Evidence Debt (deuda de evidencia como deuda tecnica)",
        "Nueva Seccion 25: Phase A Graduation Criteria (criterio formal de salida)",
        "7ma regla sagrada: cada nuevo modulo debe reducir una deuda de evidencia",
        "Riesgo de complejidad explicitamente reconocido",
        "Meta-regla extendida: 'Reduce una deuda de evidencia identificada?'",
    ]
    for change in changes:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(f"  {change}")
        run.font.size = Pt(9)
        run.font.color.rgb = c(P["secondary"])

    doc.add_page_break()

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 1: PREGUNTA CENTRAL
    # ═══════════════════════════════════════════════════════════════════════
    h = doc.add_heading("1. Pregunta Central del Proyecto", level=1)
    for run in h.runs:
        run.font.color.rgb = c(P["primary"])

    p = doc.add_paragraph()
    run = p.add_run(
        "El proyecto ya no gira alrededor del Motor C. Gira alrededor de una pregunta:"
    )
    run.font.size = Pt(11)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(12)
    run = p.add_run(
        "\u00bfComo medir objetivamente la utilidad de una estrategia de recuperacion?"
    )
    run.font.size = Pt(14)
    run.font.color.rgb = c(P["accent"])
    run.bold = True
    run.italic = True

    p = doc.add_paragraph()
    run = p.add_run(
        "Esta pregunta es mucho mas amplia que cualquier motor individual. Es mucho mas dificil de copiar. "
        "Y es la base sobre la cual se construye todo el proyecto. Si el laboratorio demuestra que sus resultados "
        "son reproducibles, comparables y resisten auditorias externas, habremos construido algo que vale "
        "mucho mas que un motor de recuperacion: una infraestructura de evaluacion objetiva que es "
        "extraordinariamente dificil de desarrollar y de replicar."
    )
    run.font.size = Pt(11)

    p = doc.add_paragraph()
    run = p.add_run(
        "El proyecto ha pasado por tres etapas. La primera fue construir un recuperador mejor. La segunda fue "
        "descubrir que antes hacia falta construir un laboratorio. La tercera fue descubrir que antes del "
        "laboratorio hacia falta construir un sistema que garantice que las conclusiones son confiables. "
        "Ahora, en la etapa final de maduracion, el objetivo es pasar de la produccion de software a la "
        "produccion de evidencia reproducible. Ese cambio de objetivo es profundo: ya no se trata de "
        "construir mas, sino de construir de forma que otros puedan verificar, repetir y cuestionar "
        "sobre una base solida."
    )
    run.font.size = Pt(11)

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 2: VARIABLES EXPERIMENTALES
    # ═══════════════════════════════════════════════════════════════════════
    h = doc.add_heading("2. Variables Experimentales", level=1)
    for run in h.runs:
        run.font.color.rgb = c(P["primary"])

    h2 = doc.add_heading("2.1 Variable Independiente", level=2)
    for run in h2.runs:
        run.font.color.rgb = c(P["primary"])

    p = doc.add_paragraph()
    run = p.add_run(
        "La variable independiente es aquella que el experimentador controla. Solo una debe cambiar "
        "por experimento. Si cambian dos a la vez, las conclusiones se vuelven ambiguas. Este es "
        "el principio fundamental del control experimental: cada experimento debe aislar exactamente "
        "un factor para que la relacion causal sea interpretable."
    )
    run.font.size = Pt(11)

    add_styled_table(
        doc,
        ["Variable Independiente", "Valores", "Experimento Asociado"],
        [
            ["Tipo de dano", "MFT parcial, head crash, sectores intermitentes, ruido aleatorio", "H4 Matrix"],
            ["Nivel de dano", "0%, 10%, 20%, ..., 100%", "Crossover Curve"],
            ["Formato de archivo", "JPEG, PNG, PDF (congelados)", "H5 Per-Format"],
            ["Estrategia", "Carving, MFT-First, Hybrid, Motor C", "H1.1 / H2"],
            ["Presupuesto de lectura", "0, 100, 500, 1000, 5000 sectores", "H1.7 Budget"],
        ],
        col_widths=[4.0, 6.0, 5.0],
    )

    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    run = p.add_run("Regla critica: ")
    run.bold = True
    run.font.color.rgb = c(P["red"])
    run.font.size = Pt(11)
    run2 = p.add_run(
        "Solo UNA variable independiente por experimento. Si se cambia el formato Y el nivel de dano "
        "simultaneamente, no se puede atribuir la diferencia a ninguno de los dos."
    )
    run2.font.size = Pt(11)

    h2 = doc.add_heading("2.2 Variable Dependiente", level=2)
    for run in h2.runs:
        run.font.color.rgb = c(P["primary"])

    p = doc.add_paragraph()
    run = p.add_run(
        "La variable dependiente es lo que se mide. Debe elegirse ANTES de ejecutar el experimento, "
        "no despues de ver los resultados. Cada experimento debe declarar cual es la metrica principal "
        "antes de ejecutar. La metrica principal declarada es Overall Utility (RVS x FQS). "
        "Recovery Rate se mantiene como metrica secundaria para comparabilidad con herramientas externas."
    )
    run.font.size = Pt(11)

    add_styled_table(
        doc,
        ["Metrica", "Tipo", "Definicion", "Rango"],
        [
            ["Recovery Rate", "Conteo", "Fraccion de archivos recuperados (SHA-256 match)", "0.0-1.0"],
            ["RVS", "Valor", "Valor recuperado ponderado por importancia", "0.0-1.0"],
            ["FQS", "Calidad", "Calidad funcional de lo recuperado", "0.0-1.0"],
            ["Overall Utility", "Compuesto", "RVS x FQS", "0.0-1.0"],
            ["Read Efficiency", "Eficiencia", "Lecturas utiles / Lecturas totales", "0.0-1.0"],
            ["Time to First File", "Tiempo", "Lecturas antes del primer archivo recuperado", "0-N"],
        ],
        col_widths=[3.0, 2.0, 6.5, 1.5],
    )

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 3: CRITERIO DE EXITO
    # ═══════════════════════════════════════════════════════════════════════
    h = doc.add_heading("3. Criterio de Exito", level=1)
    for run in h.runs:
        run.font.color.rgb = c(P["primary"])

    p = doc.add_paragraph()
    run = p.add_run(
        "El criterio de exito define cuando una estrategia se considera superior a otra. "
        "Debe declararse ANTES de ejecutar el experimento. El umbral es empirico (Seccion 3.1), "
        "no arbitrario. Una estrategia A se considera superior a B unicamente si: "
        "(1) Overall Utility mejora por encima del umbral empirico, "
        "(2) la diferencia es consistente en 10+ repeticiones, "
        "(3) se mantiene en 3+ datasets distintos, "
        "(4) no se debe exclusivamente a una dimension (RVS o FQS). "
        "El umbral provisional es 3% hasta la calibracion empirica (30 ejecuciones baseline)."
    )
    run.font.size = Pt(11)

    h2 = doc.add_heading("3.1 Calibracion del Umbral Empirico", level=2)
    for run in h2.runs:
        run.font.color.rgb = c(P["primary"])

    p = doc.add_paragraph()
    run = p.add_run(
        "El umbral de significancia debe surgir de los datos del laboratorio. El procedimiento: "
        "ejecutar el mismo experimento 30 veces, medir la variabilidad natural de Overall Utility, "
        "y definir umbral = max(2 x desviacion_estandar, 0.01). El umbral final es el maximo entre "
        "todos los umbrales calculados para cada formato y estrategia. "
        "Estado: aun no ejecutado. Umbral provisional de 3% hasta calibracion."
    )
    run.font.size = Pt(11)

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 4: REGISTRO DE CONFIANZA
    # ═══════════════════════════════════════════════════════════════════════
    h = doc.add_heading("4. Registro de Confianza", level=1)
    for run in h.runs:
        run.font.color.rgb = c(P["primary"])

    add_styled_table(
        doc,
        ["Estrellas", "Evidencia Requerida", "Significado"],
        [
            ["*", "Observacion aislada (1 run, 1 dataset)", "Preliminar - no citar como conclusion"],
            ["**", "Repetido 10+ veces (determinista, mismo dataset)", "Estable - pero no generalizado"],
            ["***", "Repetido con datasets distintos", "Generalizable - pero no validado externamente"],
            ["****", "Validado con herramientas externas (multiples familias)", "Robusto - comparable con el estado del arte"],
            ["*****", "Validado con hardware real", "Definitivo - predictivo del mundo real"],
        ],
        col_widths=[2.0, 6.0, 5.0],
    )

    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    run = p.add_run("Reglas: ")
    run.bold = True
    run.font.size = Pt(11)
    run2 = p.add_run(
        "Las estrellas solo pueden subir. Si aparece evidencia contradictoria, el resultado se marca "
        "como CONTESTADO pero no pierde estrellas. Cada estrella debe estar vinculada a un registro "
        "de los experimentos que la soportan."
    )
    run2.font.size = Pt(11)

    h2 = doc.add_heading("4.1 KPI de Progreso", level=2)
    for run in h2.runs:
        run.font.color.rgb = c(P["primary"])

    add_styled_table(
        doc,
        ["KPI", "Actual", "Objetivo Fase A", "Objetivo Fase B"],
        [
            ["RCR (Reproducible Claims Ratio)", "0%", ">= 80%", ">= 90%"],
            ["Resultados con 3+ estrellas", "2 / 15", "5 / 15", "8 / 15"],
            ["Resultados con 4+ estrellas", "0 / 15", "0 / 15", "3 / 15"],
            ["Claims con nivel REPRODUCIBLE+", "0", "5", "8"],
            ["Amenazas mitigadas", "4/19", "8/19", "12/19"],
            ["Evidence Debt critica", "4 items", "0 items", "0 items"],
            ["Umbral empirico calibrado", "No", "Si", "Si"],
            ["RVS calibrado con usuarios", "No", "Si", "Si"],
            ["Judge API version", "v1.0", "v1.0 (frozen)", "v1.1 (si necesario)"],
        ],
        col_widths=[4.5, 2.5, 3.5, 3.5],
    )

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 5: DECOMPOSICION DE METRICAS
    # ═══════════════════════════════════════════════════════════════════════
    h = doc.add_heading("5. Decomposicion de Metricas", level=1)
    for run in h.runs:
        run.font.color.rgb = c(P["primary"])

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(12)
    run = p.add_run("Overall Utility = RVS (Valor) x FQS (Calidad)")
    run.font.size = Pt(14)
    run.font.color.rgb = c(P["accent"])
    run.bold = True

    p = doc.add_paragraph()
    run = p.add_run(
        "RVS mide el valor de lo recuperado. FQS mide la calidad funcional. La separacion permite "
        "diagnosticar por que gano un motor (VALUE-DRIVEN vs QUALITY-DRIVEN vs STRONG vs WEAK). "
        "RVS necesita calibracion con usuarios reales (Seccion 5.4): los pesos actuales son "
        "asignaciones del laboratorio, no datos calibrados. El Judge API esta congelado durante "
        "la Fase A (Seccion 18): si los pesos necesitan cambiar, se crea Judge v1.1 y se "
        "reejecutan los experimentos afectados. Nunca se mezclan versiones."
    )
    run.font.size = Pt(11)

    add_styled_table(
        doc,
        ["Tipo de Archivo", "Valor", "Reemplazo", "Recreacion", "Emocional", "RVS Peso"],
        [
            ["tesis.docx", "100", "0.05", "500h", "100", "100"],
            ["sqlite.db", "95", "0.02", "200h", "50", "95"],
            ["foto familiar", "90", "0.00", "0h", "100", "90"],
            ["video vacaciones", "70", "0.00", "0h", "80", "70"],
            ["PSD proyecto", "65", "0.10", "40h", "30", "65"],
            ["RAW foto", "60", "0.00", "0h", "60", "60"],
            ["MP4 descargado", "20", "0.90", "1h", "5", "20"],
            ["Linux ISO", "2", "1.00", "0.5h", "0", "2"],
            ["thumbnail", "1", "1.00", "0h", "0", "1"],
        ],
        col_widths=[3.0, 1.5, 1.5, 2.0, 2.0, 1.5],
    )

    h2 = doc.add_heading("5.1 FQS - Functional Quality Score", level=2)
    for run in h2.runs:
        run.font.color.rgb = c(P["primary"])

    add_styled_table(
        doc,
        ["Nivel", "Score", "Definicion", "Ejemplo"],
        [
            ["FULL", "1.0", "SHA-256 coincide exactamente", "Copia bit-perfect del original"],
            ["FUNCTIONAL", "0.8", "Archivo funciona con dano menor", "JPEG con 2 pixeles corruptos"],
            ["PARTIAL", "0.5", "Funciona parcialmente, perdida de datos", "MP4 que se reproduce hasta la mitad"],
            ["DEGRADED", "0.2", "Contenido accesible pero daniado", "DOCX que abre pero perdio imagenes"],
            ["FAILED", "0.0", "Completamente inutilizable", "Datos aleatorios sin estructura"],
        ],
        col_widths=[2.5, 1.5, 5.0, 5.0],
    )

    h2 = doc.add_heading("5.2 Plan de Calibracion de RVS con Usuarios Reales", level=2)
    for run in h2.runs:
        run.font.color.rgb = c(P["primary"])

    p = doc.add_paragraph()
    run = p.add_run(
        "La tabla de valores de RVS es una asignacion razonable hecha por el laboratorio, pero sigue "
        "siendo una decision interna. Para que el RVS deje de ser un modelo disenado por el "
        "laboratorio y pase a estar calibrado con comportamiento real, se necesita una encuesta "
        "de calibracion con comparacion por pares (Bradley-Terry). La pregunta central: "
        "'Si solo pudieras recuperar uno de estos archivos, cual elegirias?' "
        "Minimo 30 respuestas por poblacion en 5 poblaciones (150 total). "
        "Estado: no se ha realizado. Es una actividad de la Fase A. "
        "Hasta que se complete, los pesos de RVS deben tratarse como supuestos, no como hechos."
    )
    run.font.size = Pt(11)

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 6: AUDITORIA DE HIPOTESIS
    # ═══════════════════════════════════════════════════════════════════════
    h = doc.add_heading("6. Auditoria de Hipotesis", level=1)
    for run in h.runs:
        run.font.color.rgb = c(P["primary"])

    p = doc.add_paragraph()
    run = p.add_run(
        "Cada hipotesis debe declarar su variable independiente, variable dependiente y criterio "
        "de exito antes de ejecutar el experimento. Una hipotesis sin criterio de refutacion no "
        "es una hipotesis cientifica: es una opinion."
    )
    run.font.size = Pt(11)

    add_styled_table(
        doc,
        ["Hipotesis", "Variable Independiente", "Variable Dependiente", "Criterio de Exito", "Confiabilidad"],
        [
            ["H1.1", "Estrategia (Carving vs MFT-First)", "Overall Utility", "MFT-First > Carving por umbral empirico+ en 3+ datasets", "***"],
            ["H1.2", "Confianza en metadatos (0-100%)", "Estrategia optima", "Cambio de estrategia en umbral definido", "*"],
            ["H2", "Nivel de dano MFT (0-100%)", "Recovery Rate", "Crossover observable con carving completo", "**"],
            ["H4", "Tipo de dano", "Mejor estrategia", "Matriz completa con >80% celdas llenas", "*"],
            ["H5", "Formato de archivo", "Recovery Rate por formato", "Diferencia >10% entre formatos", "*"],
            ["H6", "Nivel de dano en archivo", "FQS", "Espectro no-binario con >2 niveles", "**"],
            ["H7", "Tipo de archivo recuperado", "RVS", "Tesis > 200 thumbnails (RVS calibrado)", "*"],
            ["H8", "Motor de carving (limitado vs completo)", "Crossover point", "Cambio significativo en crossover", "*"],
        ],
        col_widths=[1.5, 3.5, 2.5, 4.0, 1.5],
    )

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 7: HOJA DE RUTA POR FASES
    # ═══════════════════════════════════════════════════════════════════════
    h = doc.add_heading("7. Hoja de Ruta por Fases", level=1)
    for run in h.runs:
        run.font.color.rgb = c(P["primary"])

    h2 = doc.add_heading("7.1 Fase A - Regimen Estricto (Ahora Mismo)", level=2)
    for run in h2.runs:
        run.font.color.rgb = c(P["primary"])

    add_callout_box(
        doc,
        "REGLA DE FASE A: No escribir ni un motor nuevo durante varias semanas.",
        "Solo se hacen cuatro cosas. Si despues de esas cuatro cosas los resultados siguen "
        "sosteniendose, recien entonces se vuelve a desarrollar algoritmos de recuperacion. "
        "Dejar de preguntarse 'que mas puedo construir?' y empezar a preguntarse 'que evidencia "
        "necesito para que otra persona crea lo que encontre?'. Esa es la pregunta correcta "
        "para la etapa en la que esta el proyecto ahora.",
        P["red"]
    )

    p = doc.add_paragraph()
    run = p.add_run(
        "La Fase A tiene un regimen estricto de cuatro actividades. No se escriben nuevos motores, "
        "no se agregan nuevos formatos, no se construyen nuevas funcionalidades. El unico trabajo "
        "es consolidar la evidencia existente y hacerla reproducible."
    )
    run.font.size = Pt(11)

    phase_a_items = [
        "1. Ejecutar las 30 corridas baseline para obtener la variabilidad real del sistema.",
        "2. Ejecutar la calibracion de RVS con usuarios reales.",
        "3. Validar los parsers JPEG/PNG/PDF contra herramientas externas.",
        "4. Convertir todos los experimentos en reproducibles de principio a fin (run_all.py).",
    ]
    for item in phase_a_items:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(1.0)
        run = p.add_run(item)
        run.font.size = Pt(11)
        run.bold = True

    h2 = doc.add_heading("7.2 Fase B - Validacion Externa", level=2)
    for run in h2.runs:
        run.font.color.rgb = c(P["primary"])

    add_styled_table(
        doc,
        ["Familia de Estrategia", "Herramienta Representativa", "Que valida"],
        [
            ["Carving puro", "PhotoRec / TestDisk", "Si nuestro carving es comparable al estado del arte"],
            ["MFT-first", "R-Studio / ReclaiMe", "Si nuestras estrategias MFT son comparables a comerciales"],
            ["Hybrida", "DMDE (Disk Drill)", "Si nuestras estrategias hibridas son comparables"],
            ["Orquestador", "UFS Explorer", "Si nuestro Motor C es comparable a herramientas que adaptan estrategia"],
        ],
        col_widths=[3.5, 4.0, 6.5],
    )

    h2 = doc.add_heading("7.3 Fase C - Expansion Controlada", level=2)
    for run in h2.runs:
        run.font.color.rgb = c(P["primary"])

    p = doc.add_paragraph()
    run = p.add_run(
        "Solo entonces incorporar un formato nuevo y exigirle el mismo estandar de calidad y pruebas. "
        "Un parser excelente de JPEG tiene muchisimo mas valor cientifico que diez parsers aceptables."
    )
    run.font.size = Pt(11)

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 8: FORMATOS CONGELADOS
    # ═══════════════════════════════════════════════════════════════════════
    h = doc.add_heading("8. Formatos Congelados - Referencia Dorada", level=1)
    for run in h.runs:
        run.font.color.rgb = c(P["primary"])

    p = doc.add_paragraph()
    run = p.add_run(
        "Los tres parsers actuales (JPEG, PNG, PDF) tienen 19/19 tests pasados. "
        "Esto vale oro. Antes de agregar un nuevo formato, estos tres deben convertirse "
        "en una referencia absoluta."
    )
    run.font.size = Pt(11)

    add_styled_table(
        doc,
        ["Formato", "Parser", "Tests", "Estado", "Accion"],
        [
            ["JPEG", "motor_carving.py", "19/19", "IMPECABLE", "Convertir en referencia dorada"],
            ["PNG", "motor_carving.py", "19/19", "IMPECABLE", "Convertir en referencia dorada"],
            ["PDF", "motor_carving.py", "19/19", "IMPECABLE", "Convertir en referencia dorada"],
            ["MP4", "No implementado", "0/0", "CONGELADO", "No implementar hasta Fase C"],
            ["DOCX", "No implementado", "0/0", "CONGELADO", "No implementar hasta Fase C"],
            ["SQLite", "No implementado", "0/0", "CONGELADO", "No implementar hasta Fase C"],
        ],
        col_widths=[2.0, 3.0, 1.5, 2.5, 5.0],
    )

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 9: REGLA DE ORO
    # ═══════════════════════════════════════════════════════════════════════
    h = doc.add_heading("9. Regla de Oro", level=1)
    for run in h.runs:
        run.font.color.rgb = c(P["primary"])

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(12)
    run = p.add_run(
        "Por cada 500 lineas nuevas de codigo de recuperacion, "
        "agregar al menos 500 lineas de validacion, pruebas y metricas."
    )
    run.font.size = Pt(13)
    run.font.color.rgb = c(P["accent"])
    run.bold = True
    run.italic = True

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 10: PRODUCTO
    # ═══════════════════════════════════════════════════════════════════════
    h = doc.add_heading("10. Producto del Proyecto", level=1)
    for run in h.runs:
        run.font.color.rgb = c(P["primary"])

    p = doc.add_paragraph()
    run = p.add_run(
        "Estamos investigando si el verdadero activo competitivo del proyecto termina siendo "
        "el RecoveryLab Benchmark Suite: una plataforma objetiva para evaluar estrategias de "
        "recuperacion de datos. Esta hipotesis de negocio no esta demostrada. La validacion "
        "de esta hipotesis es parte del trabajo futuro, no una conclusion actual."
    )
    run.font.size = Pt(11)

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 11: OBJETIVOS OPERATIVOS INMEDIATOS
    # ═══════════════════════════════════════════════════════════════════════
    h = doc.add_heading("11. Objetivos Operativos Inmediatos", level=1)
    for run in h.runs:
        run.font.color.rgb = c(P["primary"])

    p = doc.add_paragraph()
    run = p.add_run(
        "Las cuatro actividades de la Fase A (ver Seccion 7.1) son los unicos objetivos operativos. "
        "Todo nuevo trabajo debe responder a la pregunta: 'Reduce una deuda de evidencia "
        "identificada (Seccion 24)?' Si la respuesta es no, no pertenece a la Fase A."
    )
    run.font.size = Pt(11)

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 12: THREATS TO VALIDITY
    # ═══════════════════════════════════════════════════════════════════════
    h = doc.add_heading("12. Threats to Validity (Amenazas a la Validez)", level=1)
    for run in h.runs:
        run.font.color.rgb = c(P["primary"])

    p = doc.add_paragraph()
    run = p.add_run(
        "Seccion estandar en trabajos cientificos. Explicita los factores que podrian invalidar "
        "las conclusiones. Cada amenaza tiene estado: ABIERTA, MITIGADA o RESUELTA. "
        "Resumen: 4 mitigadas, 12 abiertas, 0 resueltas. Ver Research Protocol v1.2 para "
        "el detalle completo de las 19 amenazas en las 4 categorias (interna, externa, "
        "estadistica, constructiva)."
    )
    run.font.size = Pt(11)

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 13: HYPOTHESIS SET v1.0 (FROZEN)
    # ═══════════════════════════════════════════════════════════════════════
    h = doc.add_heading("13. Hypothesis Set v1.0 (Frozen)", level=1)
    for run in h.runs:
        run.font.color.rgb = c(P["primary"])

    p = doc.add_paragraph()
    run = p.add_run(
        "Las hipotesis congeladas (H1.1 a H8) no se reescriben. Si aparece una idea nueva, "
        "nace como H9, H10, etc. Si una hipotesis resulta incorrecta, se marca como REFUTADA. "
        "H3 fue eliminada y documentada. Su contenido sustantivo vive en H4. "
        "No se agregan mas hipotesis durante la Fase A. Cada nueva hipotesis debe reducir "
        "una deuda de evidencia identificada (Seccion 24)."
    )
    run.font.size = Pt(11)

    add_styled_table(
        doc,
        ["ID", "Hipotesis (formulacion congelada)", "Estado", "Estrellas"],
        [
            ["H1.1", "Priorizar metadatos reduce costo de adquisicion cuando son confiables", "ACTIVA", "***"],
            ["H1.2", "Cuando la confianza baja de un umbral, la estrategia optima cambia", "ACTIVA", "*"],
            ["H1.5", "Los gaps actuales limitan la capacidad de evaluacion", "ACTIVA", "*"],
            ["H1.6", "Los resultados son deterministas", "ACTIVA", "**"],
            ["H1.7", "Motor C supera a MFT-First cuando el presupuesto es limitado", "ACTIVA", "*"],
            ["H2", "Existe una frontera donde la estrategia optima cambia", "CONTESTADA", "**"],
            ["H4", "La estrategia optima depende del tipo de dano", "ACTIVA", "*"],
            ["H5", "La eficacia varia significativamente por formato", "ACTIVA", "*"],
            ["H6", "La recuperacion funcional no es binaria (FQS)", "ACTIVA", "**"],
            ["H7", "El RVS predice la satisfaccion del usuario", "ACTIVA", "*"],
            ["H8", "El crossover al 95% es un artefacto del carving limitado", "ACTIVA", "*"],
        ],
        col_widths=[1.5, 8.0, 2.0, 1.5],
    )

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 14: EVIDENCE GATE
    # ═══════════════════════════════════════════════════════════════════════
    h = doc.add_heading("14. Evidence Gate (Control de Lenguaje)", level=1)
    for run in h.runs:
        run.font.color.rgb = c(P["primary"])

    p = doc.add_paragraph()
    run = p.add_run(
        "El Evidence Gate controla el lenguaje permitido para describir un resultado, basandose "
        "en la cantidad y calidad de evidencia acumulada. Nadie puede escribir 'demuestra' hasta "
        "pasar el cuarto nivel. En niveles 1-3, solo se permite: 'observamos', 'es consistente con', "
        "'la evidencia sugiere'. Los niveles son: OBSERVED, REPEATED, REPRODUCIBLE, "
        "EXTERNALLY VALIDATED, HARDWARE VALIDATED."
    )
    run.font.size = Pt(11)

    add_styled_table(
        doc,
        ["Claim", "Titulo", "Nivel", "Hipotesis", "Proximo paso"],
        [
            ["CLAIM-001", "MFT-First > Carving", "OBSERVED", "H1.1", "3+ datasets distintos"],
            ["CLAIM-002", "FQS no es binario", "OBSERVED", "H6", "3+ datasets distintos"],
            ["CLAIM-003", "Tesis > thumbnails (RVS)", "OBSERVED", "H7", "Encuesta de calibracion"],
            ["CLAIM-004", "Crossover 95% es artefacto", "OBSERVED", "H8", "Carving completo"],
            ["CLAIM-005", "Parsers referencia dorada", "OBSERVED", "-", "30 ejecuciones + edge cases"],
        ],
        col_widths=[2.0, 3.0, 2.0, 2.0, 4.0],
    )

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 15: THREE-LEVEL ARCHITECTURE
    # ═══════════════════════════════════════════════════════════════════════
    h = doc.add_heading("15. Arquitectura de Tres Niveles", level=1)
    for run in h.runs:
        run.font.color.rgb = c(P["primary"])

    p = doc.add_paragraph()
    run = p.add_run(
        "Todo se separa en tres niveles: /data (solo datos crudos), /analysis (solo scripts "
        "estadisticos), /claims (solo fichas de claims). Los datos no mienten. Las interpretaciones "
        "si pueden. Separando datos de interpretaciones, cualquier persona puede verificar los datos "
        "sin aceptar las interpretaciones, y desafiar las interpretaciones sin cuestionar los datos."
    )
    run.font.size = Pt(11)

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 16: SEPARATION OF OBSERVATION AND EXPLANATION
    # ═══════════════════════════════════════════════════════════════════════
    h = doc.add_heading("16. Separation of Observation and Explanation (6ta Regla Sagrada)", level=1)
    for run in h.runs:
        run.font.color.rgb = c(P["primary"])

    p = doc.add_paragraph()
    run = p.add_run(
        "Es mas estricta que el Evidence Gate. Incluso usando 'observamos...' todavia es facil colar "
        "interpretacion. La observacion pura solo contiene numeros, conteos, porcentajes y medidas. "
        "Ningun adjetivo calificativo, ningun porque, ningun termino evaluativo. Despues, en otro "
        "parrafo, se puede escribir: 'Esto es consistente con la hipotesis de que...' "
        "Ejemplo: 'Observamos que Motor C elige correctamente' = NO. "
        "Ejemplo: 'En 27/30 ejecuciones Motor C selecciono carving cuando el dano MFT supero X%' = SI."
    )
    run.font.size = Pt(11)

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 17: EVIDENCE LEDGER
    # ═══════════════════════════════════════════════════════════════════════
    h = doc.add_heading("17. Evidence Ledger (Registro de Evidencia)", level=1)
    for run in h.runs:
        run.font.color.rgb = c(P["primary"])

    p = doc.add_paragraph()
    run = p.add_run(
        "Registro extremadamente simple de cada experimento ejecutado. Campos: Evidence ID, Fecha, "
        "Dataset, Seed, Motor, Commit, Resultados, Claims afectados, Threats. Ningun claim puede "
        "citar una evidencia que no exista en el ledger. El ledger es append-only, almacenado en "
        "/data/evidence_ledger.csv. Crea trazabilidad completa: claim → experimento → commit → codigo."
    )
    run.font.size = Pt(11)

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 18: JUDGE API FREEZE
    # ═══════════════════════════════════════════════════════════════════════
    h = doc.add_heading("18. Judge API Freeze (Congelamiento del Judge)", level=1)
    for run in h.runs:
        run.font.color.rgb = c(P["primary"])

    p = doc.add_paragraph()
    run = p.add_run(
        "RVS v1.0, FQS v1.0 y Overall Utility v1.0 estan congelados durante la Fase A. "
        "Si alguna metrica necesita evolucionar, se crea Judge v1.1 y se vuelven a ejecutar "
        "los experimentos afectados. Nunca se comparan resultados de versiones distintas del Judge. "
        "La calibracion de RVS con usuarios probablemente requiera Judge v1.1. Cuando eso ocurra, "
        "se reejecutan todos los experimentos. Esto es un costo, no un problema: es el costo "
        "de la integridad cientifica."
    )
    run.font.size = Pt(11)

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 19: REPRODUCIBILITY CONTRACT
    # ═══════════════════════════════════════════════════════════════════════
    h = doc.add_heading("19. Reproducibility Contract (Contrato de Reproducibilidad)", level=1)
    for run in h.runs:
        run.font.color.rgb = c(P["primary"])

    p = doc.add_paragraph()
    run = p.add_run(
        "Cualquier persona debe poder ejecutar 'git clone ... && python run_all.py' y obtener "
        "exactamente los mismos datasets, CSV, figuras y registro de claims. Sin intervencion humana. "
        "Ese script termina siendo casi tan importante como el laboratorio. Si un resultado no es "
        "reproducible por run_all.py, no es un resultado del laboratorio: es una observacion informal."
    )
    run.font.size = Pt(11)

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 20: REPRODUCIBLE CLAIMS RATIO (RCR)
    # ═══════════════════════════════════════════════════════════════════════
    h = doc.add_heading("20. Reproducible Claims Ratio (RCR) - KPI Primario", level=1)
    for run in h.runs:
        run.font.color.rgb = c(P["primary"])

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(12)
    run = p.add_run("RCR = Claims Reproducibles / Claims Totales")
    run.font.size = Pt(16)
    run.font.color.rgb = c(P["blue"])
    run.bold = True

    p = doc.add_paragraph()
    run = p.add_run(
        "El RCR mide algo mas fundamental que las estrellas: mide la resiliencia de la evidencia "
        "frente a la verificacion externa. Un claim con 3 estrellas que no se puede reproducir es "
        "un claim con 3 estrellas fragiles. Un claim con 2 estrellas que se reproduce consistentemente "
        "es un claim con 2 estrellas solidas. El RCR responde a la pregunta mas importante: "
        "'Que evidencia necesito para que otra persona crea lo que encontre?' "
        "Actual: 0/5 = 0%. Objetivo Fase A: >= 80%."
    )
    run.font.size = Pt(11)

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 21: RVS CALIBRATION EXPERIMENT
    # ═══════════════════════════════════════════════════════════════════════
    h = doc.add_heading("21. Experimento de Calibracion de RVS", level=1)
    for run in h.runs:
        run.font.color.rgb = c(P["primary"])

    p = doc.add_paragraph()
    run = p.add_run(
        "Experimento con sujetos humanos. Metodo Bradley-Terry. 12 pares de archivos. "
        "5 poblaciones x 30+ respuestas = 150+ total. "
        "Pregunta: 'Si solo pudieras recuperar uno de estos archivos, cual elegirias?' "
        "Output: pesos RVS calibrados por poblacion. "
        "Estado: DISSENADO (sin datos reales todavia). "
        "Cuando se complete, probablemente requiera Judge API v1.1 (Seccion 18)."
    )
    run.font.size = Pt(11)

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 22: META-REGLA
    # ═══════════════════════════════════════════════════════════════════════
    h = doc.add_heading("22. Meta-Regla", level=1)
    for run in h.runs:
        run.font.color.rgb = c(P["primary"])

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(16)
    p.paragraph_format.space_after = Pt(12)
    run = p.add_run(
        "No agregar una sola caracteristica nueva\nsi no aumenta la calidad de la evidencia."
    )
    run.font.size = Pt(16)
    run.font.color.rgb = c(P["red"])
    run.bold = True
    run.italic = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(12)
    run = p.add_run(
        "Cada nuevo documento, modulo o algoritmo debe responder:\n"
        "Reduce una deuda de evidencia identificada?"
    )
    run.font.size = Pt(14)
    run.font.color.rgb = c(P["blue"])
    run.bold = True
    run.italic = True

    p = doc.add_paragraph()
    run = p.add_run(
        "Si la respuesta es no, no pertenece a la Fase A. Esa regla mantiene el alcance controlado "
        "y hace que cada avance aumente la credibilidad del proyecto, que es justamente el recurso "
        "mas valioso en la etapa en la que esta. El proyecto ya tiene suficientes modulos. "
        "El tablero ya no mide lineas de codigo, features o modulos. Mide unicamente la calidad "
        "de la evidencia. Y la calidad de la evidencia se mide con el RCR (Seccion 20) y se "
        "rastrea con la Evidence Debt (Seccion 24). Si el RCR no sube y la deuda de evidencia "
        "no baja, el proyecto no avanza. Punto."
    )
    run.font.size = Pt(11)

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 23: DECISION LOG (NUEVO)
    # ═══════════════════════════════════════════════════════════════════════
    h = doc.add_heading("23. Decision Log (Registro de Decisiones)", level=1)
    for run in h.runs:
        run.font.color.rgb = c(P["primary"])

    add_callout_box(
        doc,
        "El Decision Log es distinto del Evidence Ledger.",
        "El Evidence Ledger registra que paso. El Decision Log registra por que se tomo una "
        "decision. Dentro de un ano vas a agradecer muchisimo saber por que se hizo algo, "
        "no solo que se hizo. El Evidence Ledger dice: 'En el experimento EXP-0031, Motor C "
        "obtuvo Overall Utility = 0.73.' El Decision Log dice: 'Decidimos congelar Judge API v1.0 "
        "porque cambiar la forma de medir a mitad de los experimentos hace que comparar resultados "
        "antiguos con nuevos se vuelva mucho mas dificil.' Ambos son necesarios. Ninguno reemplaza "
        "al otro.",
        P["blue"]
    )

    p = doc.add_paragraph()
    run = p.add_run(
        "En un proyecto de investigacion, las decisiones son tan importantes como los resultados. "
        "Un resultado sin contexto decisional es un dato flotante. Un resultado con contexto "
        "decisional es conocimiento. El Decision Log registra cada decision significativa del "
        "proyecto: por que se tomo, que evidencia la soporto, y que alternativas se consideraron. "
        "Esto es invaluable cuando, meses despues, alguien pregunta: 'Por que congelamos el Judge "
        "en vez de iterar?' o 'Por que eliminamos H3 en vez de reformularla?' Sin el Decision Log, "
        "la unica respuesta es la memoria del investigador, que es notoriamente poco confiable."
    )
    run.font.size = Pt(11)

    h2 = doc.add_heading("23.1 Formato del Decision Log", level=2)
    for run in h2.runs:
        run.font.color.rgb = c(P["primary"])

    add_styled_table(
        doc,
        ["ID", "Decision", "Motivo", "Evidencia", "Alternativas consideradas", "Fecha"],
        [
            ["D-001", "Eliminar H3", "Solapaba con H2 y H4; su contenido sustantivo vivo en H4", "CLAIM-004", "Reformular H3 / Mantener como sub-hipotesis", "2026-07-28"],
            ["D-002", "Congelar Judge API v1.0", "Evitar deriva experimental; comparabilidad entre resultados", "Protocol v1.4 S.18", "Iterar sin versionar / No congelar", "2026-07-31"],
            ["D-003", "JPEG/PNG/PDF como referencia dorada", "Mayor confianza actual: 19/19 tests impecables", "Tests 19/19", "Agregar MP4 primero / No congelar formatos", "2026-07-28"],
            ["D-004", "RCR como KPI primario (reemplaza ★★★)", "Mide resiliencia de evidencia, no solo acumulacion interna", "Revision externa ronda 3", "Mantener ★★★ como primario / Usar ambos", "2026-07-31"],
            ["D-005", "Fase A regimen estricto", "El proximo cuello de botella es reproducibilidad, no funcionalidad", "Revision externa ronda 3", "Continuar desarrollo en paralelo", "2026-07-31"],
            ["D-006", "Separar observacion de explicacion", "Incluso 'observamos...' puede colar interpretacion", "Revision externa ronda 3", "Solo Evidence Gate / No separar", "2026-07-31"],
        ],
        col_widths=[1.2, 2.5, 3.5, 2.0, 3.0, 1.5],
    )

    h2 = doc.add_heading("23.2 Reglas del Decision Log", level=2)
    for run in h2.runs:
        run.font.color.rgb = c(P["primary"])

    decision_rules = [
        "Toda decision significativa se registra en el Decision Log. 'Significativa' significa: cualquier decision que afecte el diseno experimental, las metricas, las hipotesis, o la arquitectura del proyecto.",
        "El campo Motivo es obligatorio y debe explicar por que se tomo la decision, no solo que se decidio.",
        "El campo Evidencia vincula la decision con la evidencia que la soporto. Si no hay evidencia, se indica 'Juicio del investigador' explicitamente.",
        "El campo Alternativas consideradas es obligatorio. Toda decision implica alternativas descartadas. Documentarlas muestra que la decision fue informada, no arbitraria.",
        "El Decision Log es append-only. No se editan entradas, solo se agregan. Si una decision se revierte, se agrega una nueva entrada explicando por que.",
        "El Decision Log se almacena en /data/decision_log.csv y es parte del repositorio.",
    ]
    for i, rule in enumerate(decision_rules, 1):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(1.0)
        run = p.add_run(f"{i}. {rule}")
        run.font.size = Pt(11)

    h2 = doc.add_heading("23.3 Decision Log vs Evidence Ledger", level=2)
    for run in h2.runs:
        run.font.color.rgb = c(P["primary"])

    add_styled_table(
        doc,
        ["Aspecto", "Evidence Ledger", "Decision Log"],
        [
            ["Registra", "Que paso (experimentos)", "Por que se decidio (decisiones)"],
            ["Pregunta", "Que se ejecuto? Con que resultado?", "Por que se tomo esta decision?"],
            ["Entrada tipica", "EXP-0031: Motor C, OU=0.73", "D-002: Congelar Judge API v1.0"],
            ["Campos clave", "ID, Fecha, Dataset, Seed, Commit, Resultados", "ID, Decision, Motivo, Evidencia, Alternativas"],
            ["Vincula a", "Claims afectados, Threats", "Evidencia que soporta la decision"],
            ["Uso principal", "Reproducibilidad", "Trazabilidad decisional"],
        ],
        col_widths=[2.5, 4.5, 4.5],
    )

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 24: EVIDENCE DEBT (NUEVO)
    # ═══════════════════════════════════════════════════════════════════════
    h = doc.add_heading("24. Evidence Debt (Deuda de Evidencia)", level=1)
    for run in h.runs:
        run.font.color.rgb = c(P["primary"])

    add_callout_box(
        doc,
        "Asi como existe deuda tecnica, existe deuda de evidencia.",
        "Todo pendiente entra como deuda de evidencia. Esto evita que la lista de TODOs "
        "vuelva a crecer sin criterio. Cada item de deuda tiene: ID, descripcion, impacto, "
        "prioridad y estado. La deuda de evidencia es el inventario de lo que falta para "
        "que las conclusiones del laboratorio sean confiables. Si no se rastrea, se acumula "
        "silenciosamente hasta que el proyecto se vuelve insolvente desde el punto de vista "
        "de la evidencia.",
        P["red"]
    )

    p = doc.add_paragraph()
    run = p.add_run(
        "La deuda de evidencia es el analogo de la deuda tecnica en el dominio de la "
        "investigacion. La deuda tecnica se acumula cuando se toman atajos en el codigo "
        "que despues hay que pagar con refactorizacion. La deuda de evidencia se acumula "
        "cuando se hacen afirmaciones que despues hay que pagar con validacion. Un proyecto "
        "puede morir no porque este equivocado, sino porque se vuelve imposible de mantener "
        "la cantidad de afirmaciones sin respaldo. La Evidence Debt hace visible esa carga "
        "y permite priorizar que deuda pagar primero. La regla es simple: cada nuevo modulo, "
        "documento o algoritmo debe reducir una deuda de evidencia identificada. Si no la "
        "reduce, no pertenece a la Fase A."
    )
    run.font.size = Pt(11)

    h2 = doc.add_heading("24.1 Registro de Evidence Debt", level=2)
    for run in h2.runs:
        run.font.color.rgb = c(P["primary"])

    add_styled_table(
        doc,
        ["ID", "Deuda", "Impacto", "Prioridad", "Estado"],
        [
            ["ED-001", "Falta validacion con hardware real", "Muy alto", "CRITICA", "ABIERTA"],
            ["ED-002", "Falta calibracion de RVS con usuarios", "Alto", "ALTA", "ABIERTA"],
            ["ED-003", "Falta reproducibilidad externa (run_all.py)", "Muy alto", "CRITICA", "EN PROGRESO"],
            ["ED-004", "Solo NTFS evaluado", "Medio", "MEDIA", "ABIERTA"],
            ["ED-005", "Solo datasets sinteticos", "Alto", "ALTA", "ABIERTA"],
            ["ED-006", "Solo 3 formatos de carving", "Medio", "MEDIA", "CONGELADA (Fase C)"],
            ["ED-007", "Umbral empirico no calibrado", "Alto", "ALTA", "ABIERTA"],
            ["ED-008", "Solo 2/15 resultados con 3+ estrellas", "Alto", "ALTA", "ABIERTA"],
            ["ED-009", "RCR = 0% (ningun claim reproducible)", "Muy alto", "CRITICA", "ABIERTA"],
            ["ED-010", "Judge API no versionado formalmente", "Medio", "ALTA", "RESUELTA (v1.0 frozen)"],
        ],
        col_widths=[1.5, 4.5, 2.0, 2.0, 3.0],
    )

    h2 = doc.add_heading("24.2 Reglas de la Evidence Debt", level=2)
    for run in h2.runs:
        run.font.color.rgb = c(P["primary"])

    debt_rules = [
        "Todo pendiente de evidencia entra como deuda. No hay pendientes informales: si falta algo, es deuda.",
        "Cada deuda tiene prioridad: CRITICA (bloquea la graduacion de Fase A), ALTA (debe resolverse en Fase A), MEDIA (puede esperar a Fase B), BAJA (puede esperar a Fase C).",
        "Las deudas CRITICAS deben resolverse antes de que la Fase A pueda graduarse (ver Seccion 25).",
        "Cada nueva funcionalidad, modulo o algoritmo debe reducir al menos una deuda de evidencia. Si no la reduce, no se implementa.",
        "Cuando se paga una deuda, se marca como RESUELTA con la evidencia que la resolvio y la fecha. No se elimina: queda en el registro para trazabilidad.",
        "El total de deuda de evidencia critica es un KPI secundario. Si no baja, el proyecto no avanza.",
        "El Evidence Debt se almacena en /data/evidence_debt.csv y es parte del repositorio.",
    ]
    for i, rule in enumerate(debt_rules, 1):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(1.0)
        run = p.add_run(f"{i}. {rule}")
        run.font.size = Pt(11)

    h2 = doc.add_heading("24.3 Evidence Debt vs Threats to Validity", level=2)
    for run in h2.runs:
        run.font.color.rgb = c(P["primary"])

    add_styled_table(
        doc,
        ["Aspecto", "Threats to Validity", "Evidence Debt"],
        [
            ["Naturaleza", "Riesgo de que las conclusiones sean invalidas", "Carencia de evidencia que respalde las conclusiones"],
            ["Pregunta", "Que podria invalidar nuestros resultados?", "Que falta para que nuestros resultados sean confiables?"],
            ["Orientacion", "Defensiva: identificar debilidades", "Constructiva: priorizar que construir"],
            ["Accion", "Mitigar o aceptar el riesgo", "Pagar la deuda con evidencia nueva"],
            ["Relacion", "Amenazas no mitigadas generan deuda de evidencia", "Deuda de evidencia no resuelta aumenta las amenazas"],
        ],
        col_widths=[2.5, 4.5, 4.5],
    )

    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    run = p.add_run(
        "Las amenazas no mitigadas generan deuda de evidencia. La deuda de evidencia no resuelta "
        "aumenta las amenazas. Ambos mecanismos se refuerzan mutuamente. El Threats to Validity "
        "identifica los riesgos; el Evidence Debt prioriza que hacer al respecto. Juntos, "
        "forman un sistema completo de gestion de la incertidumbre cientifica."
    )
    run.font.size = Pt(11)

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 25: PHASE A GRADUATION CRITERIA (NUEVO)
    # ═══════════════════════════════════════════════════════════════════════
    h = doc.add_heading("25. Phase A Graduation Criteria (Criterio de Graduacion de Fase A)", level=1)
    for run in h.runs:
        run.font.color.rgb = c(P["primary"])

    add_callout_box(
        doc,
        "La Fase A termina unicamente cuando se cumplen TODAS las condiciones simultaneamente.",
        "No importa cuánto codigo exista. Importa cumplir los criterios. Ahora mismo hay "
        "actividades, pero no un criterio de salida. Un proyecto sin criterio de salida "
        "es un proyecto que puede quedar atrapado indefinidamente en la misma fase. Los "
        "criterios de graduacion son la promesa mas importante del protocolo: dicen "
        "exactamente cuando se puede avanzar, y exactamente que falta para hacerlo.",
        P["green"]
    )

    p = doc.add_paragraph()
    run = p.add_run(
        "La Fase A no termina cuando se siente que se hizo suficiente trabajo. Termina cuando "
        "se cumplen criterios objetivos y verificables. Esto es fundamental: sin criterio de "
        "graduacion, la Fase A puede durar indefinidamente, o puede terminarse prematuramente "
        "cuando la presion por agregar funcionalidades sea demasiado fuerte. Los criterios de "
        "graduacion son la defensa contra ambas tentaciones. Son la promesa del protocolo "
        "de que el proyecto no avanzara hasta que la evidencia lo respalde, y de que no se "
        "quedara estancado cuando la evidencia sea suficiente."
    )
    run.font.size = Pt(11)

    h2 = doc.add_heading("25.1 Criterios de Graduacion", level=2)
    for run in h2.runs:
        run.font.color.rgb = c(P["primary"])

    p = doc.add_paragraph()
    run = p.add_run("La Fase A termina unicamente cuando se cumplen SIMULTANEAMENTE las siguientes condiciones:")
    run.bold = True
    run.font.size = Pt(12)
    run.font.color.rgb = c(P["accent"])

    graduation_criteria = [
        ("RCR >= 80%", "Al menos 4 de 5 claims son reproducibles por cualquier persona que ejecute run_all.py. Esto es el indicador mas importante: mide si la evidencia del laboratorio sobrevive la verificacion externa."),
        ("Al menos 5 CLAIMs alcanzan ★★★", "Cinco claims han sido repetidos con datasets distintos y son generalizables. No es suficiente con tener muchos claims preliminares: se necesita un nucleo de claims solidos."),
        ("Judge API permanece estable durante toda la fase", "No se crearon versiones nuevas del Judge durante la Fase A. Si se creo Judge v1.1, todos los experimentos fueron reejecutados y los resultados son consistentes."),
        ("Validacion externa realizada con al menos una herramienta por familia", "Al menos una herramienta de carving (PhotoRec), una de MFT-first (R-Studio/ReclaiMe), una hibrida (DMDE) y una orquestador (UFS Explorer) fueron ejecutadas sobre los mismos datasets y los resultados son comparables."),
        ("Baseline estadistico completo", "Las 30 corridas baseline fueron ejecutadas, el umbral empirico fue calibrado, y la potencia estadistica de los experimentos principales fue calculada."),
        ("Calibracion inicial de RVS completada", "La encuesta de calibracion de RVS con usuarios reales fue ejecutada (150+ respuestas), y los pesos de RVS fueron ajustados. Si los pesos difieren significativamente de los actuales, se creo Judge v1.1 y se reejecutaron los experimentos."),
        ("Evidence Debt critica = 0", "No quedan deudas de evidencia con prioridad CRITICA. Las deudas de prioridad ALTA pueden pasar a Fase B, pero las CRITICAS deben resolverse antes de graduarse."),
    ]

    for i, (criterion, explanation) in enumerate(graduation_criteria, 1):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(6)
        run = p.add_run(f"{i}. {criterion}")
        run.bold = True
        run.font.size = Pt(11)
        run.font.color.rgb = c(P["green"])
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(1.0)
        run = p.add_run(explanation)
        run.font.size = Pt(11)

    h2 = doc.add_heading("25.2 Estado Actual vs Criterios de Graduacion", level=2)
    for run in h2.runs:
        run.font.color.rgb = c(P["primary"])

    add_styled_table(
        doc,
        ["Criterio", "Estado Actual", "Falta", "Prioridad"],
        [
            ["RCR >= 80%", "0%", "Reproducibilidad completa de todos los experimentos", "CRITICA"],
            ["5+ Claims en ★★★", "2/15", "3+ claims necesitan elevarse de 1-2 a 3 estrellas", "ALTA"],
            ["Judge API estable", "v1.0 frozen", "Mantener durante toda la Fase A", "ALTA"],
            ["Validacion externa (4 familias)", "0/4 familias", "Ejecutar 4 herramientas sobre mismos datasets", "ALTA"],
            ["Baseline estadistico completo", "0/30 corridas", "30 corridas baseline + umbral + potencia", "CRITICA"],
            ["RVS calibrado con usuarios", "No", "150+ respuestas + ajuste de pesos", "ALTA"],
            ["Evidence Debt critica = 0", "3 items (ED-001, ED-003, ED-009)", "Resolver las 3 deudas criticas", "CRITICA"],
        ],
        col_widths=[3.5, 2.5, 4.5, 2.0],
    )

    h2 = doc.add_heading("25.3 Implicaciones del Criterio de Graduacion", level=2)
    for run in h2.runs:
        run.font.color.rgb = c(P["primary"])

    p = doc.add_paragraph()
    run = p.add_run(
        "Los criterios de graduacion tienen implicaciones profundas. Primero, hacen que la Fase A "
        "tenga un final definido y verificable. No se trata de una sensacion subjetiva de "
        "completitud: se trata de criterios objetivos que cualquier persona puede verificar. "
        "Segundo, hacen que el progreso sea medible: cada criterio que se cumple es un avance "
        "real, y cada criterio que falta es un trabajo pendiente. Tercero, protegen al proyecto "
        "de la presion de avanzar prematuramente: si los criterios no se cumplen, no se "
        "gradua, sin importar cuantas lineas de codigo se hayan escrito o cuantas funcionalidades "
        "se hayan agregado."
    )
    run.font.size = Pt(11)

    p = doc.add_paragraph()
    run = p.add_run(
        "La graduacion de la Fase A es un evento que se registra en el Decision Log (Seccion 23) "
        "con la evidencia de que cada criterio se cumplio. Es el momento en que el proyecto "
        "pasa de la consolidacion interna a la validacion externa. No es un punto final: "
        "es el inicio de una fase donde la pregunta cambia de 'podemos confiar en nuestros "
        "resultados?' a 'pueden otros confiar en nuestros resultados?'."
    )
    run.font.size = Pt(11)

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 26: RIESGO DE COMPLEJIDAD
    # ═══════════════════════════════════════════════════════════════════════
    h = doc.add_heading("26. Riesgo de Complejidad", level=1)
    for run in h.runs:
        run.font.color.rgb = c(P["primary"])

    p = doc.add_paragraph()
    run = p.add_run(
        "Ya aparecio un riesgo nuevo. No es el sesgo. No es la metodologia. Es la complejidad. "
        "Un proyecto puede morir no porque este equivocado, sino porque se vuelve imposible de "
        "mantener. El RecoveryLab tiene ahora: Dataset Builder, Corruptor, Judge, Carving, "
        "Motor MFT, Motor C, RVS, FQS, Protocol, Confidence Registry, Evidence Gate, Evidence "
        "Ledger, Decision Log, Evidence Debt, Reproducibility Contract, y 25 secciones en el "
        "Research Protocol. Eso es muchisimo. La complejidad es un riesgo real: si el sistema "
        "es tan complejo que nadie puede entenderlo, entonces nadie puede verificarlo, y la "
        "reproducibilidad se vuelve una promesa vacia."
    )
    run.font.size = Pt(11)

    p = doc.add_paragraph()
    run = p.add_run(
        "Por eso la 7ma regla sagrada es: cada nuevo documento, modulo o algoritmo debe reducir "
        "una deuda de evidencia identificada. Si no la reduce, no se agrega. Esta regla no es "
        "solo sobre calidad: es sobre supervivencia. El proyecto ya tiene suficientes mecanismos. "
        "Lo que necesita ahora no es mas mecanismos, sino mas evidencia. La complejidad sin "
        "evidencia es ruido. La simplicidad con evidencia es signal."
    )
    run.font.size = Pt(11)

    add_callout_box(
        doc,
        "No agregar mas hipotesis. Ni mas metricas. Ni mas motores. Ni mas formatos.",
        "Todo eso puede esperar. Si se mantiene la disciplina de que cada nuevo modulo "
        "reduce una deuda de evidencia, el proyecto va a ganar algo mucho mas valioso que "
        "un algoritmo: va a tener resultados que otros puedan revisar, repetir y cuestionar "
        "sobre una base solida. Esa es la transformacion final: de la produccion de software "
        "a la produccion de evidencia reproducible.",
        P["red"]
    )

    # ─── Save ──────────────────────────────────────────────────────────────
    output_path = "/home/z/my-project/download/Research_Protocol_v1.5.docx"
    doc.save(output_path)
    print(f"Research Protocol v1.5 saved to: {output_path}")
    return output_path


if __name__ == "__main__":
    path = build_research_protocol()
    print(f"Generated: {path}")
