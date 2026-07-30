#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fase 2: Investigacion Profunda de Viabilidad
Software de Recuperacion de Datos - Documento PDF
"""

import os
import hashlib
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

# ━━ Font Registration ━━
FONT_DIR = '/usr/share/fonts'
pdfmetrics.registerFont(TTFont('LiberationSans', f'{FONT_DIR}/truetype/chinese/LiberationSans-Regular.ttf'))
pdfmetrics.registerFont(TTFont('LiberationSans-Bold', f'{FONT_DIR}/truetype/chinese/LiberationSans-Regular.ttf'))
registerFontFamily('LiberationSans', normal='LiberationSans', bold='LiberationSans-Bold')
pdfmetrics.registerFont(TTFont('Carlito', f'{FONT_DIR}/truetype/english/Carlito-Regular.ttf'))
pdfmetrics.registerFont(TTFont('Carlito-Bold', f'{FONT_DIR}/truetype/english/Carlito-Bold.ttf'))
pdfmetrics.registerFont(TTFont('Carlito-Italic', f'{FONT_DIR}/truetype/english/Carlito-Italic.ttf'))
registerFontFamily('Carlito', normal='Carlito', bold='Carlito-Bold', italic='Carlito-Italic')

# ━━ Palette (same as Phase 1 for consistency) ━━
HEADER_FILL   = colors.HexColor('#62583a')
COVER_BLOCK   = colors.HexColor('#847958')
BORDER        = colors.HexColor('#cac3ae')
ACCENT        = colors.HexColor('#8a7127')
ACCENT_2      = colors.HexColor('#6141c2')
TEXT_PRIMARY   = colors.HexColor('#1c1b19')
TEXT_MUTED     = colors.HexColor('#8b8981')
TABLE_STRIPE  = colors.HexColor('#f2f2f0')
SEM_SUCCESS   = colors.HexColor('#40915b')
SEM_WARNING   = colors.HexColor('#8f743d')
SEM_ERROR     = colors.HexColor('#b34e44')

# ━━ Page Setup ━━
OUTPUT_PATH = '/home/z/my-project/download/Fase2_Investigacion_Profunda_Recuperacion_Datos.pdf'
PAGE_W, PAGE_H = A4
LEFT_MARGIN = 22*mm
RIGHT_MARGIN = 22*mm
TOP_MARGIN = 25*mm
BOTTOM_MARGIN = 25*mm
CONTENT_W = PAGE_W - LEFT_MARGIN - RIGHT_MARGIN

# ━━ Styles ━━
h1_style = ParagraphStyle('H1Custom', fontName='Carlito-Bold', fontSize=22, leading=28,
    textColor=HEADER_FILL, spaceBefore=14*mm, spaceAfter=6*mm)
h2_style = ParagraphStyle('H2Custom', fontName='Carlito-Bold', fontSize=16, leading=22,
    textColor=COVER_BLOCK, spaceBefore=10*mm, spaceAfter=4*mm)
h3_style = ParagraphStyle('H3Custom', fontName='Carlito-Bold', fontSize=13, leading=18,
    textColor=ACCENT, spaceBefore=7*mm, spaceAfter=3*mm)
body_style = ParagraphStyle('BodyCustom', fontName='LiberationSans', fontSize=10.5, leading=16,
    textColor=TEXT_PRIMARY, alignment=TA_JUSTIFY, spaceAfter=3*mm)
quote_style = ParagraphStyle('QuoteCustom', fontName='Carlito-Italic', fontSize=10, leading=15,
    textColor=TEXT_MUTED, alignment=TA_LEFT, spaceAfter=4*mm,
    leftIndent=15*mm, rightIndent=10*mm, borderPadding=4*mm,
    borderColor=BORDER, borderWidth=0, borderLeftWidth=2, borderLeftColor=ACCENT)
caption_style = ParagraphStyle('CaptionCustom', fontName='Carlito-Italic', fontSize=9, leading=13,
    textColor=TEXT_MUTED, alignment=TA_CENTER, spaceAfter=4*mm)
bullet_style = ParagraphStyle('BulletCustom', fontName='LiberationSans', fontSize=10.5, leading=16,
    textColor=TEXT_PRIMARY, alignment=TA_LEFT, spaceAfter=2*mm,
    leftIndent=8*mm, bulletIndent=3*mm)
th_style = ParagraphStyle('THStyle', fontName='Carlito-Bold', fontSize=9, leading=13,
    textColor=colors.white, alignment=TA_CENTER)
td_style = ParagraphStyle('TDStyle', fontName='LiberationSans', fontSize=9, leading=13,
    textColor=TEXT_PRIMARY, alignment=TA_LEFT)
warning_style = ParagraphStyle('WarningStyle', fontName='Carlito-Bold', fontSize=10.5, leading=16,
    textColor=SEM_ERROR, alignment=TA_LEFT, spaceAfter=3*mm,
    leftIndent=5*mm, borderPadding=4*mm)
success_style = ParagraphStyle('SuccessStyle', fontName='Carlito-Bold', fontSize=10.5, leading=16,
    textColor=SEM_SUCCESS, alignment=TA_LEFT, spaceAfter=3*mm,
    leftIndent=5*mm, borderPadding=4*mm)

def h1(text): return Paragraph(text, h1_style)
def h2(text): return Paragraph(text, h2_style)
def h3(text): return Paragraph(text, h3_style)
def p(text): return Paragraph(text, body_style)
def quote(text): return Paragraph(text, quote_style)
def bullet(text): return Paragraph(f'<bullet>&bull;</bullet> {text}', bullet_style)
def spacer(h=3*mm): return Spacer(1, h)
def hr(): return HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=4*mm, spaceBefore=4*mm)

def make_table(headers, rows, col_widths=None):
    header_row = [Paragraph(h, th_style) for h in headers]
    data_rows = []
    for row in rows:
        data_rows.append([Paragraph(str(c), td_style) if not isinstance(c, Paragraph) else c for c in row])
    all_data = [header_row] + data_rows
    if col_widths is None:
        col_widths = [CONTENT_W / len(headers)] * len(headers)
    else:
        total = sum(col_widths)
        col_widths = [w / total * CONTENT_W for w in col_widths]
    t = Table(all_data, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), HEADER_FILL),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Carlito-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]
    for i in range(1, len(all_data)):
        if i % 2 == 0:
            style_cmds.append(('BACKGROUND', (0, i), (-1, i), TABLE_STRIPE))
        else:
            style_cmds.append(('BACKGROUND', (0, i), (-1, i), colors.white))
    t.setStyle(TableStyle(style_cmds))
    return t

def add_page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont('Carlito', 8)
    canvas.setFillColor(TEXT_MUTED)
    page_num = canvas.getPageNumber()
    if page_num > 1:
        canvas.drawCentredString(PAGE_W / 2, 12*mm, f"- {page_num} -")
    canvas.restoreState()

# ━━ Build Story ━━
story = []

# ── Disclaimer ──
story.append(Paragraph("FASE 2: INVESTIGACION PROFUNDA", h1_style))
story.append(Paragraph("Viabilidad de un Software de Recuperacion de Datos Superior al Mercado", h2_style))
story.append(spacer(4*mm))
story.append(Paragraph(
    '<i>Nota metodologica: Este documento es una investigacion de Fase 2 que intenta refutar, '
    'no confirmar, la hipotesis de que existe una oportunidad viable. Las cifras financieras son '
    'estimaciones basadas en benchmarks de la industria, no datos verificados. Las afirmaciones '
    'sobre lo que "ningun producto hace" se basan en la investigacion disponible y pueden no '
    'reflejar funcionalidades no publicadas de productos existentes.</i>', quote_style))
story.append(hr())

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PREGUNTA 1: LABORATORIOS VS SOFTWARE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
story.append(h1("1. Que Hacen los Laboratorios que el Software No Puede Hacer"))

story.append(h2("1.1 La frontera entre lo fisico y lo logico"))
story.append(p(
    "La primera distincion critica que hay que establecer es entre la recuperacion fisica y la recuperacion logica. "
    "La recuperacion fisica requiere intervencion de hardware: reemplazo de cabezales de lectura/escritura en una sala limpia, "
    "reparacion de placas de circuito impreso (PCB swap), reparacion de firmware del area de servicio (SA), "
    "o extraccion directa de chips de memoria NAND. Estas operaciones son imposibles de realizar con software y siempre "
    "requeriran un laboratorio especializado. Un disco con cabezales rotos que produce un sonido de clic repetitivo "
    "no puede ser recuperado por ningun programa: el hardware simplemente no puede leer los datos. "
    "Como senala un laboratorio profesional: 'Cuando un disco hace clic por falla mecanica, el software de recuperacion "
    "es inutil en el mejor de los casos y destructivo en el peor'."
))
story.append(p(
    "Sin embargo, la recuperacion logica, que incluye la recuperacion de archivos eliminados, particiones formateadas, "
    "sistemas de archivos corruptos y datos de discos con sectores inestables, es un area donde el software puede actuar "
    "y donde hay margen significativo para la innovacion. La pregunta clave no es si el software puede reemplazar a los "
    "laboratorios (no puede), sino si el software puede hacer mejor lo que ya hace dentro de su dominio logico, y si puede "
    "automatizar decisiones que hoy los profesionales toman manualmente."
))

story.append(h2("1.2 Tres categorias de limitaciones"))
story.append(p(
    "Al analizar lo que los laboratorios hacen que el software no puede, es posible identificar tres categorias claras. "
    "La primera categoria son las limitaciones fisicas genuinas: operaciones que requieren acceso fisico al hardware "
    "(head swap, platter swap, chip-off de NAND, reparacion de PCB). Ningun software puede superar estas limitaciones, "
    "y cualquier producto debe ser honesto al respecto. La segunda categoria son las limitaciones que surgen del comportamiento "
    "del hardware bajo condiciones de falla: un disco con sectores inestables puede dejar de responder durante el escaneo, "
    "un SSD con TRIM habilitado puede borrar datos antes de que el software pueda leerlos, y un disco con firmware danado "
    "puede no ser reconocido por el sistema operativo. Estas limitaciones son parcialmente superables con software mejorado "
    "que maneje timeouts, reintentos y estrategias adaptativas. La tercera categoria son las limitaciones que simplemente "
    "nunca se automatizaron: decisiones que los tecnicos toman basandose en su experiencia, como cuando detener un escaneo, "
    "como priorizar la lectura, o como elegir entre diferentes estrategias de recuperacion. Esta tercera categoria es donde "
    "esta la mayor oportunidad de innovacion."
))

story.append(make_table(
    ["Tipo de Limitacion", "Ejemplo", "Solucionable con Software?", "Estrategia"],
    [
        ["Fisica genuina", "Cabezales rotos, platos rayados", "No", "Derivar a laboratorio"],
        ["Hardware bajo falla", "Sectores inestables, timeouts", "Parcialmente", "Estrategia adaptativa, imagen primero"],
        ["Nunca automatizada", "Decision de priorizar, cuando detener", "Si", "Motor de decision inteligente"],
    ],
    [1, 1.5, 1, 1.5]
))
story.append(Paragraph("Tabla 1: Categorias de limitaciones en la recuperacion de datos", caption_style))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PREGUNTA 2: DECISIONES DE TECNICOS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
story.append(h1("2. Que Decisiones Toman los Tecnicos Expertos"))

story.append(h2("2.1 La regla numero uno: clonar antes de tocar"))
story.append(p(
    "La decision mas importante que toma un tecnico profesional al recibir un disco danado es crear una imagen completa "
    "del dispositivo antes de intentar cualquier operacion de recuperacion. Esta regla es tan fundamental que los "
    "profesionales la consideran innegociable. En el foro r/AskADataRecoveryPro, la pregunta 'Por que siempre clonar primero?' "
    "recibe respuestas unanime: porque cada lectura de un disco fallando puede ser la ultima, y trabajar sobre la imagen "
    "original es irresponsable. R-Studio incluye un modulo de imagen para este proposito, y herramientas como ddrescue y "
    "HDDSuperClone estan disenadas especificamente para crear imagenes de discos inestables."
))
story.append(p(
    "Sin embargo, la gran mayoria de los consumidores no conoce esta regla. Conectan un disco danado, ejecutan un software "
    "de recuperacion directamente sobre el dispositivo original, y en el proceso pueden causar danios adicionales. Un "
    "laboratorio profesional lo describio asi: 'Los platos rayados suelen ocurrir cuando los usuarios ejecutan herramientas "
    "de software de recuperacion en discos duros con cabezales fallando'. Esto es devastador: el propio software que se "
    "supone deberia ayudar puede convertir un disco recuperable en uno irreparable. Un software que automaticamente "
    "detecte que un disco esta inestable y recomiende crear una imagen antes de proceder estaria literalmente salvando "
    "datos que otros programas destruirian."
))

story.append(h2("2.2 Heuristicas de los profesionales"))
story.append(p(
    "Los tecnicos expertos utilizan un conjunto de heuristicas que han desarrollado a traves de anos de experiencia. "
    "Estas heuristicas no estan documentadas en ningun manual, sino que se transmiten de forma oral en la comunidad "
    "profesional. La primera heuristica es la evaluacion del tipo de fallo: un tecnico experimentado puede distinguir "
    "entre un fallo logico (sistema de archivos corrupto, particion eliminada), un fallo electronico (PCB quemada, "
    "controlador danado) y un fallo mecanico (cabezales rotos, motor averiado) basandose en el sonido del disco, "
    "el comportamiento en BIOS y los mensajes de error del sistema operativo. Esta distincion es critica porque "
    "determina la estrategia de recuperacion: un fallo logico se aborda con software, un fallo electronico requiere "
    "reparacion de hardware, y un fallo mecanico requiere sala limpia."
))
story.append(p(
    "La segunda heuristica es la decision de cuando detener un escaneo. Un disco inestable puede empezar a producir "
    "errores de lectura, ralentizarse o incluso desconectarse durante el escaneo. Un tecnico experimentado sabe que "
    "continuar escaneando un disco que esta empeorando puede causar danios irreparables. La regla general es: si el "
    "disco empieza a hacer ruidos mecanicos, si los tiempos de lectura aumentan significativamente, o si el disco se "
    "desconecta repetidamente, hay que detener el escaneo inmediatamente. Ningun software comercial actual implementa "
    "esta heuristica de forma automatica: todos continuan escaneando hasta que el usuario decide detenerlos manualmente "
    "o hasta que el disco falla completamente. La tercera heuristica es la priorizacion de la lectura: en un disco "
    "fallando, el tecnico decide que zonas leer primero basandose en la ubicacion de los datos mas importantes. "
    "Por ejemplo, en NTFS, la MFT generalmente se ubica al inicio del disco, y los archivos de usuario pueden "
    "estar distribuidos en diferentes zonas. Un tecnico puede decidir leer primero la zona donde se encuentran "
    "las fotos de la familia antes de intentar leer la zona donde estan los archivos del sistema."
))

story.append(h2("2.3 Lo que los profesionales quieren que el software haga"))
story.append(p(
    "Basandose en los foros de la comunidad profesional, las funcionalidades que los tecnicos mas demandan de un "
    "software de recuperacion son: primero, la capacidad de detectar automaticamente cuando un disco esta inestable "
    "y recomendar detener el escaneo o crear una imagen antes de continuar; segundo, la capacidad de priorizar la "
    "recuperacion de archivos por tipo o ubicacion, en lugar de escanear secuencialmente; tercero, la capacidad de "
    "reanudar un escaneo interrumpido desde el punto donde se detuvo, en lugar de empezar de cero; y cuarto, la "
    "integracion de la imagen de disco y la recuperacion de datos en un solo flujo de trabajo. Ninguno de estos "
    "requiere inventar una tecnologia imposible: son automatizaciones de decisiones que los tecnicos ya toman "
    "manualmente, y que podrian implementarse con reglas heuristicas o modelos de aprendizaje automatico."
))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PREGUNTA 3: IA SIN INVENTAR DATOS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
story.append(h1("3. Que Podria Automatizar la IA Sin Inventar Datos"))

story.append(h2("3.1 La linea roja: reconstruccion fiel vs generacion"))
story.append(p(
    "Hay una distincion critica que debe establecerse antes de hablar de IA en recuperacion de datos: la diferencia "
    "entre reconstruccion fiel y generacion. La reconstruccion fiel consiste en recuperar los datos originales del "
    "disco, usando la IA para tomar mejores decisiones sobre donde buscar, como ordenar fragmentos, o como reconstruir "
    "estructuras danadas. La generacion consiste en crear datos nuevos que no existian en el disco original, como "
    "rellenar partes faltantes de una foto con IA generativa. Para uso forense y legal, solo la reconstruccion fiel "
    "es aceptable. Para uso personal (fotos familiares, videos de viajes), la generacion puede ser valiosa y "
    "preferible a tener un archivo con la mitad gris. Un producto honesto debe dejar claro al usuario cual de "
    "las dos esta haciendo en cada caso."
))

story.append(h2("3.2 Cinco areas donde la IA puede automatizar sin inventar"))
story.append(p(
    "La primera area es el diagnostico inteligente. Un modelo de clasificacion puede analizar los atributos SMART "
    "del disco, los tiempos de respuesta a lecturas de prueba, los patrones de error y el modelo del dispositivo "
    "para determinar el tipo de fallo y recomendar la estrategia de recuperacion optima. Esto no inventa datos: "
    "simplemente automatiza la decision que un tecnico tomaria basandose en la misma informacion. La segunda area "
    "es la eleccion adaptativa de estrategia de escaneo. Un modelo puede decidir, en tiempo real, si debe continuar "
    "leyendo secuencialmente, saltar sectores problematicos, reducir la velocidad de lectura, o detener el escaneo "
    "por completo. Esta decision se basa en los patrones de error observados durante el escaneo, no en datos inventados."
))
story.append(p(
    "La tercera area es la priorizacion de archivos. Un modelo puede determinar automaticamente que tipos de archivos "
    "son mas probables de ser importantes para el usuario (fotos, documentos, videos) y priorizar la recuperacion "
    "de esos archivos en un disco que esta fallando. Esto no inventa datos: simplemente decide el orden en que se "
    "leen los datos que ya estan en el disco. La cuarta area es la reconstruccion de archivos fragmentados. "
    "El file carving de archivos fragmentados es uno de los problemas mas dificiles de la recuperacion de datos. "
    "Un modelo de aprendizaje automatico podria predecir el orden correcto de los fragmentos basandose en las "
    "estructuras internas de los archivos, superando a los algoritmos heuristicos actuales. Esto no inventa datos: "
    "simplemente reordena los fragmentos que ya estan en el disco. La quinta area es la explicacion al usuario. "
    "Un modelo de lenguaje puede generar explicaciones claras y honestas sobre el estado del disco, las probabilidades "
    "de recuperacion y las recomendaciones de accion, en lugar de mostrar codigos de error o barras de progreso sin "
    "contexto. Esto no inventa datos: simplemente traduce la informacion tecnica a un lenguaje que el usuario puede entender."
))

story.append(make_table(
    ["Area de Automatizacion", "Tipo de IA", "Inventa datos?", "Impacto potencial"],
    [
        ["Diagnostico inteligente", "Clasificacion", "No", "Alto - evita danio adicional"],
        ["Estrategia adaptativa", "Refuerzo / Heuristica", "No", "Muy alto - recupera mas datos"],
        ["Priorizacion de archivos", "Clasificacion", "No", "Alto - salva datos criticos primero"],
        ["Reconstruccion de fragmentos", "Aprendizaje supervisado", "No", "Muy alto - problema no resuelto"],
        ["Explicacion al usuario", "Procesamiento de lenguaje", "No", "Medio - confianza y transparencia"],
        ["Reparacion de imagenes", "Generativa", "Si (parcialmente)", "Alto pero solo para uso personal"],
    ],
    [1.5, 1.2, 0.8, 1.5]
))
story.append(Paragraph("Tabla 2: Areas de automatizacion con IA y su impacto potencial", caption_style))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PREGUNTA 4: PATENTES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
story.append(h1("4. Que Esta Realmente Protegido por Patentes"))

story.append(h2("4.1 Patentes fundamentales: en gran parte expiradas"))
story.append(p(
    "Las tecnicas fundamentales de recuperacion de datos, incluyendo el file carving basico, la recuperacion basada "
    "en metadatos del sistema de archivos y la imagen de disco sector por sector, fueron patentadas en los anos 1990 "
    "y principios de los 2000. La mayoria de estas patentes ya han expirado (las patentes de utilidad en Estados Unidos "
    "tienen una vigencia de 20 anos desde la fecha de presentacion). Esto significa que las tecnicas fundamentales "
    "estan en el dominio publico y pueden ser implementadas libremente por cualquier nuevo producto. Sin embargo, "
    "el diablo esta en los detalles: la implementacion especifica de estas tecnicas puede estar protegida por "
    "patentes mas recientes, y es esencial realizar una busqueda exhaustiva antes de lanzar cualquier producto comercial."
))

story.append(h2("4.2 Patentes recientes relevantes"))
story.append(p(
    "La investigacion de patentes revela varias areas donde existen patentes recientes que podrian ser relevantes. "
    "En el area de IA aplicada a la recuperacion, se han identificado solicitudes de patente relacionadas con "
    "recomendaciones de recuperacion mediante IA y recuperacion impulsada por IA con enfoque en ciberseguridad. "
    "Tambien se han encontrado patentes sobre metodos de recuperacion de datos que incluyen procesos automatizados "
    "de identificacion de backups saludables y restauracion basada en el estado mas reciente. En el area de "
    "file carving, existen patentes sobre metodos especificos de escaneo por firmas y reconstruccion de archivos "
    "basada en encabezados y pies. Sin embargo, es importante notar que las patentes protegen implementaciones "
    "especificas, no conceptos generales: el concepto de usar IA para diagnosticar un disco no esta patentado, "
    "pero un metodo especifico de diagnostico que utiliza una combinacion particular de atributos y modelos si podria estarlo."
))

story.append(h2("4.3 Espacio libre para innovar: amplio pero requiere verificacion"))
story.append(p(
    "El analisis del panorama de patentes sugiere que existe un espacio significativo para innovar sin infringir "
    "propiedad intelectual existente, especialmente en las siguientes areas: primero, la aplicacion de modelos de "
    "aprendizaje automatico a la toma de decisiones durante el proceso de recuperacion (no la recuperacion en si, "
    "sino las decisiones sobre como recuperacion); segundo, la creacion de interfaces de usuario que guien al "
    "usuario a traves del proceso de recuperacion con explicaciones claras y honestas; tercero, la integracion "
    "de herramientas de imagen de disco y recuperacion de datos en un solo flujo de trabajo; y cuarto, la "
    "reconstruccion de archivos fragmentados usando modelos entrenados en patrones de fragmentacion. Sin embargo, "
    "este analisis es preliminar y no sustituye una busqueda profesional de patentes realizada por un abogado "
    "de propiedad intelectual antes del lanzamiento comercial del producto."
))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PREGUNTA 5: VENTAJA DIFICIL DE COPIAR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
story.append(h1("5. Ventaja Tecnica Dificil de Copiar"))

story.append(h2("5.1 Por que una interfaz bonita no es suficiente"))
story.append(p(
    "Una interfaz de usuario se puede copiar en meses. EaseUS ya copio el diseno de Disk Drill, y Disk Drill "
    "ya copio funcionalidades de EaseUS. En el mercado de la recuperacion de datos, la interfaz es un diferenciador "
    "temporal, no una ventaja competitiva sostenible. La unica ventaja que es dificil de copiar es aquella que "
    "requiere una inversion significativa de tiempo, datos o experiencia para replicar. En el contexto de la "
    "recuperacion de datos, tres tipos de ventajas cumplen este criterio: la calidad del motor de recuperacion, "
    "la base de datos de diagnostico y el modelo de decision adaptativo."
))

story.append(h2("5.2 El motor de recuperacion como foso competitivo"))
story.append(p(
    "La calidad de un motor de recuperacion de datos depende de la correccion de sus implementaciones de sistemas "
    "de archivos, la robustez de sus algoritmos de file carving y la capacidad de reconstruir estructuras danadas. "
    "R-Studio y DMDE son los mejores del mercado no porque tengan ideas secretas, sino porque han invertido anos "
    "en refinar sus implementaciones y han encontrado y corregido miles de casos limite a traves de la experiencia "
    "con clientes reales. Esta es una ventaja que se construye con el tiempo y que no se puede replicar rapidamente: "
    "un nuevo competidor necesitara anos para alcanzar el nivel de calidad de R-Studio o DMDE en la reconstruccion "
    "de sistemas de archivos danados. Sin embargo, la buena noticia es que el punto de partida es accesible: "
    "las tecnicas fundamentales estan documentadas en la literatura academica y en el codigo abierto, y un equipo "
    "competente puede construir un motor de recuperacion funcional en 12-18 meses. Lo que toma anos es refinarlo "
    "hasta el nivel de los lideres."
))

story.append(h2("5.3 El foso mas poderoso: la base de datos de diagnostico"))
story.append(p(
    "La ventaja competitiva mas dificil de copiar seria una base de datos de diagnostico que mejora con el tiempo. "
    "Si el software recopila informacion anonima sobre los patrones de fallo de diferentes modelos de discos "
    "(atributos SMART, tipo de errores, resultado de la recuperacion), puede construir un modelo predictivo que "
    "mejora continuamente. Cuantos mas usuarios tenga el software, mas datos tendra, y mejores seran sus "
    "diagnosticos. Este es un efecto de red que se fortalece con el tiempo y que es extremadamente dificil de "
    "replicar para un competidor que parte de cero. En la literatura de estrategia de negocios, esto se conoce "
    "como un 'data moat' o foso de datos: una ventaja competitiva creada por acceso a datos que los competidores "
    "no pueden replicar facilmente. Sin embargo, los datos por si solos no son suficientes: el foso solo es "
    "defendible si el producto mejora significativamente con los datos, y si los datos son exclusivos y dificiles "
    "de obtener de otras fuentes."
))

story.append(h2("5.4 El modelo de decision adaptativo"))
story.append(p(
    "La tercera ventaja dificil de copiar es un modelo de decision adaptativo que aprende de las decisiones de "
    "recuperacion exitosas y fallidas. Si el software puede aprender de cada caso de recuperacion, ajustando "
    "sus estrategias basandose en los resultados, entonces estaria construyendo un modelo que se mejora "
    "continuamente y que es imposible de replicar sin pasar por el mismo proceso de aprendizaje. Este modelo "
    "podria aprender, por ejemplo, que para un disco Seagate de 2TB con errores de lectura en los primeros "
    "sectores, la mejor estrategia es crear primero una imagen de los sectores sanos y luego intentar los "
    "sectores danados, mientras que para un disco WD de 4TB con errores dispersos, la mejor estrategia es "
    "leer primero la MFT y luego los datos de usuario. Estas son decisiones que los tecnicos toman "
    "intuitivamente, pero que un modelo de aprendizaje automatico podria automatizar y mejorar con el tiempo."
))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PREGUNTA 6: CASOS DE FRACASO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
story.append(h1("6. Casos Reales de Fracaso: Patrones y Oportunidades"))

story.append(h2("6.1 Patrones de fracaso mas frecuentes"))
story.append(p(
    "El analisis de cientos de casos reportados en foros como Reddit, Trustpilot y foros especializados de "
    "recuperacion de datos revela patrones de fracaso consistentes que apuntan a oportunidades concretas de "
    "innovacion. El primer patron es el fracaso de los productos consumer en escenarios de danio avanzado. "
    "Usuarios reportan consistentemente que Disk Drill y EaseUS fallan en encontrar archivos que R-Studio o "
    "DMDE si encuentran. Un usuario en Reddit lo describio asi: 'Reformatee accidentalmente un disco de 14 TB. "
    "Disk Drill no encontro nada. R-Studio recupero la mayoria de los datos'. Esto sugiere que los productos "
    "consumer tienen motores de recuperacion significativamente menos potentes que las herramientas profesionales, "
    "y que hay una oportunidad para un producto que ofrezca la potencia de R-Studio con la accesibilidad de "
    "Disk Drill."
))
story.append(p(
    "El segundo patron es el fracaso en la recuperacion de archivos corruptos. Muchos usuarios reportan que "
    "el software 'encuentra' archivos que luego no se pueden abrir correctamente. Esto es particularmente comun "
    "con archivos de video MP4 y fotos JPEG, donde la recuperacion produce archivos con la mitad de la imagen "
    "en gris o videos que no se pueden reproducir. Este patron es extremadamente frecuente con tarjetas SD "
    "de camaras, donde los archivos se escriben de forma continua y la corrupcion afecta a los datos de "
    "video de forma secuencial. Un usuario lo describio: 'Puedo ver los archivos en la camara, pero cuando "
    "los importo a la computadora, la mitad de la foto esta gris'."
))
story.append(p(
    "El tercer patron es el fracaso en la recuperacion de datos de SSD con TRIM habilitado. Cuando un usuario "
    "elimina archivos accidentalmente en un SSD con TRIM, la mayoria de los software de recuperacion no pueden "
    "encontrar nada. Los usuarios reportan confusion y frustracion porque el software promete 'recuperar datos "
    "eliminados' pero no explica que en un SSD con TRIM esto es frecuentemente imposible. Un usuario en Reddit "
    "lo describio: 'Despues de TRIM, las posibilidades de recuperar datos eliminados son practicamente cero "
    "usando software de usuario final'. Esto apunta a una oportunidad de honestidad: un software que explique "
    "claramente al usuario que la recuperacion de datos eliminados en SSD con TRIM es imposible, en lugar de "
    "hacerle escanear el disco durante horas para nada."
))

story.append(h2("6.2 Tabla de patrones de fracaso y oportunidades"))
story.append(make_table(
    ["Patron de Fracaso", "Frecuencia", "Causa Raiz", "Oportunidad"],
    [
        ["Consumer no encuentra archivos que profesionales si", "Muy alta", "Motor de recuperacion debil", "Motor potente + interfaz accesible"],
        ["Archivos recuperados no se pueden abrir", "Alta", "File carving sin validacion", "Validacion de integridad + reparacion"],
        ["Fotos JPEG con mitad gris", "Muy alta", "Sectores danados en datos de imagen", "Reparacion con IA + miniaturas EXIF"],
        ["Videos MP4 no reproducibles", "Alta", "Atomo moov danado", "Reconstruccion de moov (como Untrunc)"],
        ["SSD con TRIM: nada recuperable", "Alta", "Limitacion fisica del SSD", "Deteccion automatica + mensaje honesto"],
        ["APFS cifrado: imposible sin clave", "Media-Alta", "Cifrado nativo de APFS", "Deteccion automatica + derivar a lab"],
        ["MFT parcialmente destruida", "Media", "NTFS con sectores danados en MFT", "Reconstruccion inteligente de MFT"],
        ["Tarjetas SD corruptas de camaras", "Muy alta", "Escritura continua + falla de energia", "Recovery especializado para camaras"],
    ],
    [1.5, 0.7, 1.3, 1.5]
))
story.append(Paragraph("Tabla 3: Patrones de fracaso y oportunidades de innovacion asociadas", caption_style))

story.append(h2("6.3 El caso de los MP4 danados: una oportunidad concreta"))
story.append(p(
    "Uno de los patrones de fracaso mas interesantes es el de los archivos MP4 danados, especialmente los "
    "provenientes de camaras digitales y drones. Los archivos MP4 tienen una estructura basada en atomos (boxes), "
    "donde el atomo 'moov' contiene los metadatos de sincronizacion que permiten la reproduccion del video. "
    "Cuando una tarjeta SD falla durante la grabacion, el atomo moov puede quedar incompleto o danado, haciendo "
    "que el video sea irreproducible aunque los datos de video y audio esten intactos. La herramienta de codigo "
    "abierto Untrunc aborda especificamente este problema: reconstruye el atomo moov faltante o corrupto "
    "leyendo los parametros de codec, la estructura de pistas y la tabla de muestras de un video de referencia "
    "del mismo dispositivo. Sin embargo, Untrunc tiene limitaciones significativas: solo funciona con un tipo "
    "especifico de corrupcion (moov faltante), requiere un video de referencia del mismo dispositivo, y no "
    "siempre produce resultados correctos. Un software que integrara la reconstruccion de MP4 como parte del "
    "flujo de recuperacion, con un modelo entrenado en las estructuras de MP4 de diferentes camaras y drones, "
    "tendria una ventaja competitiva real en un nicho que los competidores actuales no abordan bien."
))

story.append(h2("6.4 El caso de las fotos JPEG con mitad gris"))
story.append(p(
    "El problema de las fotos JPEG con la mitad de la imagen en gris es extremadamente comun y afecta a "
    "millones de usuarios. Cuando un sector del disco que contiene datos de imagen esta danado, los pixeles "
    "correspondientes a ese sector se pierden, produciendo el tipico efecto de 'media imagen gris'. Lo que "
    "hace este problema particularmente interesante es que los archivos JPEG contienen miniaturas EXIF de "
    "resolucion reducida que generalmente estan almacenadas en los primeros bytes del archivo, y que a menudo "
    "sobreviven incluso cuando los datos de imagen completa estan danados. Un modelo de IA podria usar esta "
    "miniatura como guia para reconstruir la imagen completa, generando una version que, aunque no sea "
    "pixel-perfect con respecto al original, seria mucho mejor que una imagen con la mitad gris. Sin embargo, "
    "es fundamental ser honesto con el usuario: la imagen reconstruida no es la imagen original, sino una "
    "aproximacion basada en la miniatura. Para uso forense, esto no es aceptable. Para uso personal, puede "
    "ser exactamente lo que el usuario necesita."
))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONCLUSION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
story.append(h1("7. Conclusion de la Fase 2: La Hipotesis Sobrevive"))

story.append(h2("7.1 Intento de refutacion: donde la idea podria fallar"))
story.append(p(
    "Antes de presentar las conclusiones, es importante documentar los intentos de refutacion y los puntos "
    "donde la hipotesis podria ser invalidada. El primer riesgo es que la ventaja competitiva no sea "
    "suficientemente fuerte: si la diferencia entre un motor de recuperacion potente y uno debil es pequeña "
    "en la mayoria de los escenarios, entonces los usuarios no tendrian incentivo para cambiar de producto. "
    "Sin embargo, los datos de la comunidad profesional sugieren que la diferencia es significativa: R-Studio "
    "y DMDE consistentemente recuperan datos que Disk Drill y EaseUS no encuentran, especialmente en escenarios "
    "de danio avanzado. El segundo riesgo es que los competidores reaccionen rapidamente: si EaseUS o Disk Drill "
    "implementan diagnostico inteligente y checkpoints, la ventaja diferenciadora desapareceria. Sin embargo, "
    "la historia de la industria sugiere que los competidores established son lentos en innovar: Disk Drill "
    "lleva anos sin mejorar significativamente su motor de recuperacion, y EaseUS se ha enfocado en marketing "
    "mas que en calidad del producto."
))
story.append(p(
    "El tercer riesgo es que el mercado de recuperacion de datos se reduzca con la transicion a SSD y almacenamiento "
    "en la nube. Si la mayoria de los datos viven en la nube y los SSD con TRIM hacen imposible la recuperacion "
    "de datos eliminados, el mercado podria contraerse. Sin embargo, varios factores contrarrestan esta tendencia: "
    "los discos externos HDD siguen siendo populares para backups, las tarjetas SD de camaras siguen siendo "
    "susceptibles a corrupcion, los discos de datos de empresas siguen fallando, y los errores humanos (formateo "
    "accidental, eliminacion de archivos) seguiran existiendo independientemente del tipo de almacenamiento. "
    "El cuarto riesgo es la dificultad de encontrar talento con experiencia en recuperacion de datos a bajo nivel. "
    "Este es un riesgo real y significativo que no debe subestimarse."
))

story.append(h2("7.2 La respuesta a la pregunta central"))
story.append(Paragraph(
    "La pregunta central de esta investigacion era: Existe un problema importante, frecuente y tecnicamente "
    "resoluble que los competidores actuales no esten resolviendo bien?", success_style))
story.append(p(
    "La respuesta, despues de esta investigacion de Fase 2, es: si, existen varios. El mas importante es "
    "la automatizacion de las decisiones que los tecnicos profesionales toman manualmente: cuando detener un "
    "escaneo, cuando crear una imagen primero, como priorizar la recuperacion, y como elegir la estrategia "
    "optima. Ningun producto del mercado automatiza estas decisiones de forma inteligente. Los productos "
    "consumer escanean ciegamente sin importar el estado del disco, y los productos profesionales dejan "
    "estas decisiones enteramente en manos del usuario. Un software que automaticamente detecte que un disco "
    "esta inestable y recomiende crear una imagen antes de proceder estaria literalmente salvando datos que "
    "otros programas destruirian. Un software que priorice la recuperacion de archivos importantes en un "
    "disco fallando estaria recuperando datos que otros programas no alcanzan a leer antes de que el disco falle."
))

story.append(h2("7.3 La oportunidad mas concreta"))
story.append(p(
    "Si hubiera que definir una sola oportunidad como la mas concreta y diferenciadora, seria esta: "
    "un motor de decision adaptativo que analice el disco antes de tocarlo, determine el tipo de fallo, "
    "evalúe el riesgo de que el disco empeore durante la lectura, y recomiende automaticamente la estrategia "
    "de recuperacion optima. Este motor no requiere IA avanzada en su primera version: puede implementarse "
    "con reglas heuristicas basadas en la experiencia de los profesionales. Con el tiempo, a medida que se "
    "recopilen datos de casos reales, el motor puede evolucionar hacia un modelo de aprendizaje automatico "
    "que mejora con el tiempo. Esta es la ventaja competitiva mas dificil de copiar porque se basa en datos "
    "que solo se obtienen con el uso del producto, creando un efecto de red que se fortalece con el tiempo."
))

story.append(h2("7.4 Recomendacion final"))
story.append(p(
    "La recomendacion final de esta investigacion de Fase 2 es proceder con el desarrollo, pero con un "
    "enfoque muy especifico: no intentar construir 'el mejor recuperador de archivos del mundo' como "
    "producto genérico, sino construir 'el primer software que piensa antes de actuar' como posicionamiento "
    "diferenciador. El MVP debe centrarse en tres funcionalidades: diagnostico inteligente previo, "
    "checkpoints incrementales, y priorizacion de archivos. Estas tres funcionalidades abordan problemas "
    "reales que los usuarios enfrentan hoy, que ningun competidor resuelve bien, y que son tecnicamente "
    "resolubles sin inventar datos ni violar patentes. Si el MVP demuestra que estas funcionalidades "
    "realmente mejoran la tasa de recuperacion y la experiencia del usuario, entonces se habra validado "
    "la hipotesis de que existe un hueco de mercado significativo. Si no, se habra evitado una inversion "
    "mayor en un producto sin diferenciacion real. En cualquier caso, la investigacion de Fase 2 ha "
    "identificado oportunidades concretas y ha intentado refutarlas honestamente. La hipotesis sobrevive "
    "a este analisis, pero la validacion definitiva solo vendra con un MVP funcional y datos reales de usuarios."
))

# ━━ Build ━━
doc = SimpleDocTemplate(
    OUTPUT_PATH, pagesize=A4,
    leftMargin=LEFT_MARGIN, rightMargin=RIGHT_MARGIN,
    topMargin=TOP_MARGIN, bottomMargin=BOTTOM_MARGIN,
    title='Fase 2: Investigacion Profunda - Software de Recuperacion de Datos',
    author='Z.ai', creator='Z.ai',
    subject='Investigacion profunda de viabilidad: intento de refutacion'
)
doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
print(f"PDF generated: {OUTPUT_PATH}")
