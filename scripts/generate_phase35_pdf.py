#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fase 3.5: Benchmark Lab — Validacion Experimental de H1
PDF Generation Script — ReportLab + Playwright cover
"""

import os, sys, hashlib, platform
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm, inch
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    Paragraph, Spacer, Table, TableStyle, PageBreak, Image,
    KeepTogether, Flowable, HRFlowable
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.platypus import SimpleDocTemplate
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

# ─── Font Registration ───────────────────────────────────────────────────────
_IS_MAC = platform.system() == 'Darwin'
if _IS_MAC:
    FONT_DIR = os.path.expanduser('~/.openclaw/workspace/fonts')
else:
    FONT_DIR = '/usr/share/fonts'

pdfmetrics.registerFont(TTFont('NotoSerifSC', f'{FONT_DIR}/truetype/noto-serif-sc/NotoSerifSC-Regular.ttf'))
pdfmetrics.registerFont(TTFont('NotoSerifSC-Bold', f'{FONT_DIR}/truetype/noto-serif-sc/NotoSerifSC-Bold.ttf'))
pdfmetrics.registerFont(TTFont('SarasaMonoSC', f'{FONT_DIR}/truetype/chinese/SarasaMonoSC-Regular.ttf'))
pdfmetrics.registerFont(TTFont('LiberationSans', f'{FONT_DIR}/truetype/liberation/LiberationSans-Regular.ttf'))
pdfmetrics.registerFont(TTFont('LiberationSans-Bold', f'{FONT_DIR}/truetype/liberation/LiberationSans-Bold.ttf'))
pdfmetrics.registerFont(TTFont('FreeSerif', f'{FONT_DIR}/truetype/freefont/FreeSerif.ttf'))
pdfmetrics.registerFont(TTFont('FreeSerif-Bold', f'{FONT_DIR}/truetype/freefont/FreeSerifBold.ttf'))
pdfmetrics.registerFont(TTFont('FreeSerif-Italic', f'{FONT_DIR}/truetype/freefont/FreeSerifItalic.ttf'))
pdfmetrics.registerFont(TTFont('FreeSerif-BoldItalic', f'{FONT_DIR}/truetype/freefont/FreeSerifBoldItalic.ttf'))
pdfmetrics.registerFont(TTFont('DejaVuSans', f'{FONT_DIR}/truetype/dejavu/DejaVuSansMono.ttf'))

registerFontFamily('NotoSerifSC', normal='NotoSerifSC', bold='NotoSerifSC-Bold')
registerFontFamily('LiberationSans', normal='LiberationSans', bold='LiberationSans-Bold')
registerFontFamily('FreeSerif', normal='FreeSerif', bold='FreeSerif-Bold', italic='FreeSerif-Italic', boldItalic='FreeSerif-BoldItalic')
registerFontFamily('DejaVuSans', normal='DejaVuSans', bold='DejaVuSans')

# Install font fallback for mixed CJK/Latin
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'skills', 'pdf', 'scripts'))
try:
    from pdf import install_font_fallback
    install_font_fallback()
except Exception:
    pass

# ─── Cascade Palette ─────────────────────────────────────────────────────────
PAGE_BG       = colors.HexColor('#f2f2f0')
SECTION_BG    = colors.HexColor('#f2f2f1')
CARD_BG       = colors.HexColor('#ecebe9')
TABLE_STRIPE  = colors.HexColor('#f0f0ed')
HEADER_FILL   = colors.HexColor('#6e6342')
COVER_BLOCK   = colors.HexColor('#746b52')
BORDER        = colors.HexColor('#ccc7b6')
ICON          = colors.HexColor('#8c7b46')
ACCENT        = colors.HexColor('#897129')
ACCENT_2      = colors.HexColor('#755cbe')
TEXT_PRIMARY   = colors.HexColor('#191917')
TEXT_MUTED     = colors.HexColor('#89867f')
SEM_SUCCESS   = colors.HexColor('#468e5e')
SEM_WARNING   = colors.HexColor('#90794c')
SEM_ERROR     = colors.HexColor('#a0524b')
SEM_INFO      = colors.HexColor('#456686')

# ─── Output ──────────────────────────────────────────────────────────────────
OUTPUT_DIR = '/home/z/my-project/download'
os.makedirs(OUTPUT_DIR, exist_ok=True)
BODY_PDF = os.path.join(OUTPUT_DIR, 'Fase35_Benchmark_Lab_H1_body.pdf')
FINAL_PDF = os.path.join(OUTPUT_DIR, 'Fase35_Benchmark_Lab_H1.pdf')
COVER_HTML = os.path.join(OUTPUT_DIR, 'Fase35_cover.html')
COVER_PDF = os.path.join(OUTPUT_DIR, 'Fase35_cover.pdf')

# ─── Styles ──────────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4
LEFT_M = 2.2*cm
RIGHT_M = 2.2*cm
TOP_M = 2.0*cm
BOTTOM_M = 2.0*cm
CONTENT_W = PAGE_W - LEFT_M - RIGHT_M

styles = {}

styles['h1'] = ParagraphStyle(
    name='H1', fontName='FreeSerif-Bold', fontSize=18, leading=24,
    textColor=HEADER_FILL, spaceBefore=24, spaceAfter=10,
    borderPadding=(0, 0, 4, 0),
)
styles['h2'] = ParagraphStyle(
    name='H2', fontName='FreeSerif-Bold', fontSize=14, leading=19,
    textColor=COVER_BLOCK, spaceBefore=16, spaceAfter=8,
)
styles['h3'] = ParagraphStyle(
    name='H3', fontName='FreeSerif-Bold', fontSize=11.5, leading=16,
    textColor=ICON, spaceBefore=10, spaceAfter=6,
)
styles['body'] = ParagraphStyle(
    name='Body', fontName='FreeSerif', fontSize=10.5, leading=17,
    textColor=TEXT_PRIMARY, alignment=TA_JUSTIFY, spaceAfter=6,
    firstLineIndent=0,
)
styles['body_indent'] = ParagraphStyle(
    name='BodyIndent', parent=styles['body'],
    leftIndent=18,
)
styles['bullet'] = ParagraphStyle(
    name='Bullet', parent=styles['body'],
    leftIndent=22, bulletIndent=8, spaceAfter=4,
    bulletFontName='FreeSerif', bulletFontSize=10.5,
)
styles['code'] = ParagraphStyle(
    name='Code', fontName='DejaVuSans', fontSize=8.5, leading=13,
    textColor=TEXT_PRIMARY, backColor=CARD_BG,
    leftIndent=12, rightIndent=12,
    spaceBefore=6, spaceAfter=6,
    borderPadding=(6, 6, 6, 6),
)
styles['quote'] = ParagraphStyle(
    name='Quote', fontName='FreeSerif-Italic', fontSize=10.5, leading=16,
    textColor=TEXT_MUTED, leftIndent=24, rightIndent=18,
    spaceBefore=8, spaceAfter=8,
    borderPadding=(0, 0, 0, 0),
)
styles['caption'] = ParagraphStyle(
    name='Caption', fontName='FreeSerif-Italic', fontSize=9, leading=13,
    textColor=TEXT_MUTED, alignment=TA_CENTER,
    spaceBefore=4, spaceAfter=12,
)
styles['toc_h1'] = ParagraphStyle(
    name='TOCH1', fontName='FreeSerif-Bold', fontSize=12, leading=20,
    textColor=HEADER_FILL, leftIndent=0,
)
styles['toc_h2'] = ParagraphStyle(
    name='TOCH2', fontName='FreeSerif', fontSize=10.5, leading=18,
    textColor=TEXT_PRIMARY, leftIndent=18,
)

# ─── Helpers ──────────────────────────────────────────────────────────────────
def h1(text, level=0):
    key = f'h_{hashlib.md5(text.encode()).hexdigest()[:8]}'
    p = Paragraph(f'<a name="{key}"/>{text}', styles['h1'])
    p.bookmark_name = key
    p.bookmark_level = level
    p.bookmark_text = text
    p.bookmark_key = key
    return p

def h2(text, level=1):
    key = f'h_{hashlib.md5(text.encode()).hexdigest()[:8]}'
    p = Paragraph(f'<a name="{key}"/>{text}', styles['h2'])
    p.bookmark_name = key
    p.bookmark_level = level
    p.bookmark_text = text
    p.bookmark_key = key
    return p

def h3(text):
    return Paragraph(text, styles['h3'])

def body(text):
    return Paragraph(text, styles['body'])

def bullet(text):
    return Paragraph(text, styles['bullet'], bulletText='\u2022')

def quote(text):
    return Paragraph(text, styles['quote'])

def code_block(text):
    return Paragraph(text.replace('\n', '<br/>'), styles['code'])

def make_table(data, col_widths=None, header_rows=1):
    """Create a styled table with cascade palette colors."""
    if col_widths is None:
        col_widths = [CONTENT_W / len(data[0])] * len(data[0])
    else:
        total = sum(col_widths)
        col_widths = [w / total * CONTENT_W for w in col_widths]

    t = Table(data, colWidths=col_widths, repeatRows=header_rows)
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, header_rows - 1), HEADER_FILL),
        ('TEXTCOLOR', (0, 0), (-1, header_rows - 1), colors.white),
        ('FONTNAME', (0, 0), (-1, header_rows - 1), 'FreeSerif-Bold'),
        ('FONTSIZE', (0, 0), (-1, header_rows - 1), 10),
        ('FONTNAME', (0, header_rows), (-1, -1), 'FreeSerif'),
        ('FONTSIZE', (0, header_rows), (-1, -1), 9.5),
        ('LEADING', (0, 0), (-1, -1), 14),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER),
    ]
    for i in range(header_rows, len(data)):
        if i % 2 == 1:
            style_cmds.append(('BACKGROUND', (0, i), (-1, i), TABLE_STRIPE))
    t.setStyle(TableStyle(style_cmds))
    return t

def callout_box(text, accent_color=ACCENT, bg_color=CARD_BG):
    """Create a callout/highlight box with left accent border."""
    inner = Paragraph(text, ParagraphStyle(
        'CalloutInner', fontName='FreeSerif-Italic', fontSize=10.5, leading=16,
        textColor=TEXT_PRIMARY,
    ))
    t = Table([[inner]], colWidths=[CONTENT_W - 12])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), bg_color),
        ('LEFTPADDING', (0, 0), (-1, -1), 14),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LINEBEFOREDECOR', (0, 0), (0, -1), 3, accent_color),
    ]))
    return t

# ─── TocDocTemplate ──────────────────────────────────────────────────────────
class TocDocTemplate(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        if hasattr(flowable, 'bookmark_name'):
            level = getattr(flowable, 'bookmark_level', 0)
            text = getattr(flowable, 'bookmark_text', '')
            key = getattr(flowable, 'bookmark_key', '')
            self.notify('TOCEntry', (level, text, self.page, key))

# ─── Page Template ───────────────────────────────────────────────────────────
def page_template(canvas, doc):
    canvas.saveState()
    # Header line
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(LEFT_M, PAGE_H - TOP_M + 8, PAGE_W - RIGHT_M, PAGE_H - TOP_M + 8)
    # Header text
    canvas.setFont('FreeSerif-Italic', 8)
    canvas.setFillColor(TEXT_MUTED)
    canvas.drawString(LEFT_M, PAGE_H - TOP_M + 12, 'Fase 3.5 — Benchmark Lab: Validacion Experimental de H1')
    # Footer
    canvas.setFont('FreeSerif', 8)
    canvas.drawCentredString(PAGE_W / 2, BOTTOM_M - 12, str(doc.page))
    # Footer line
    canvas.line(LEFT_M, BOTTOM_M - 2, PAGE_W - RIGHT_M, BOTTOM_M - 2)
    canvas.restoreState()

# ─── Chapter Numbering Plan ─────────────────────────────────────────────────
# | Outline Index | Type    | Chapter # | Title                                |
# |---------------|---------|-----------|--------------------------------------|
# | 1             | cover   | —         | Cover                                |
# | 2             | toc     | —         | Table of Contents                    |
# | 3             | content | Cap 1     | De la intuicion a la hipotesis       |
# | 4             | content | Cap 2     | H1: Hipotesis Central                |
# | 5             | content | Cap 3     | El simulador: resultados y limites   |
# | 6             | content | Cap 4     | El siguiente experimento             |
# | 7             | content | Cap 5     | Metricas ampliadas                   |
# | 8             | content | Cap 6     | Cuando el MFT falla                  |
# | 9             | content | Cap 7     | Matriz de ataque a H1                |
# | 10            | content | Cap 8     | Criterios de decision                |

# ─── BUILD STORY ─────────────────────────────────────────────────────────────
story = []

# ─── TOC ─────────────────────────────────────────────────────────────────────
toc = TableOfContents()
toc.levelStyles = [styles['toc_h1'], styles['toc_h2']]
story.append(toc)
story.append(PageBreak())

# ═══════════════════════════════════════════════════════════════════════════════
# CAPITULO 1: De la intuicion a la hipotesis
# ═══════════════════════════════════════════════════════════════════════════════
story.append(h1('Capitulo 1. De la intuicion a la hipotesis'))

story.append(body(
    'Este documento no describe un producto. Describe un experimento. La diferencia es fundamental: '
    'un producto se construye sobre convicciones; un experimento se construye sobre dudas. '
    'Hemos llegado a un punto donde la intuicion inicial —que leer primero los metadatos del sistema '
    'de archivos deberia mejorar la recuperacion de datos en discos danados— ha madurado lo suficiente '
    'como para convertirse en una hipotesis tecnica formal. Pero no hemos demostrado que esa intuicion '
    'sea correcta. Y eso, antes de escribir miles de lineas de codigo, es lo que debemos resolver.'
))

story.append(body(
    'El recorrido hasta aqui ha sido deliberadamente conservador. En la Fase 1 analizamos el mercado '
    'y los competidores. En la Fase 2 intentamos refutar la idea con preguntas agresivas. En la Fase 3 '
    'disenamos la ingenieria del motor de recuperacion. Y en cada paso, la idea sobrevivio — pero '
    'sobrevivir al escrutinio teorico no es lo mismo que sobrevivir a la evidencia experimental. '
    'Hay una diferencia abismal entre "tiene sentido que funcione" y "medimos que funciona". '
    'Este documento es el puente entre ambas.'
))

story.append(h2('1.1 Por que un laboratorio, no un motor'))

story.append(body(
    'La tentacion natural de cualquier ingeniero es programar. Tenemos la arquitectura, tenemos los '
    'componentes identificados, tenemos el roadmap. Podriamos abrir el IDE y empezar a construir. '
    'Pero eso seria cometer el error mas costoso de todos: construir un producto sobre una hipotesis '
    'no verificada. Si la priorizacion MFT-first resulta no ofrecer ventaja significativa en '
    'condiciones reales, todo el motor de decisiones, todo el sistema de diagnostico, toda la '
    'logica de adquisicion priorizada seria codigo inutil. No es que no funcionaria — es que '
    'resolveria el problema equivocado.'
))

story.append(body(
    'El Benchmark Lab es, en esencia, un mecanismo de proteccion. No protege contra fallos tecnicos '
    'del codigo; protege contra fallos fundamentales del concepto. Si la hipotesis es correcta, '
    'el laboratorio nos dara la confianza para invertir meses de desarrollo. Si es incorrecta, '
    'nos habra ahorrado meses de desarrollo en la direccion equivocada. Y si es parcialmente '
    'correcta —si funciona solo en ciertas condiciones—, nos dira exactamente cuales son '
    'esas condiciones, permitiendonos enfocar el producto con precision quirurgica.'
))

story.append(h2('1.2 La evolucion de la pregunta'))

story.append(body(
    'La pregunta original era amplia y vaga: "Podemos construir un motor de recuperacion mejor que '
    'los existentes?" Con cada fase, la pregunta se fue refinando. La Fase 1 la redujo a "Hay una '
    'oportunidad tecnica real?" La Fase 2 la estrecho a "Que pasaria si la idea fuera falsa?" '
    'La Fase 3 la transformo en "Como se construiria?" Y ahora, la Fase 3.5 la reduce a su '
    'forma mas esencial: "Leer primero la informacion correcta mejora realmente el resultado?" '
    'Esta es una pregunta que se puede responder con un experimento. Y eso es lo que la hace '
    'poderosa: es falsable.'
))

story.append(body(
    'La falsabilidad es el criterio que separa una hipotesis cientifica de una opinion. '
    'Una hipotesis que no puede ser refutada no es una hipotesis — es un articulo de fe. '
    'Nuestra hipotesis puede ser refutada: si en todos los escenarios probados, la estrategia '
    'MFT-first no ofrece ventaja sobre la secuencial, la hipotesis cae. No hay forma de '
    'salvarla con argumentos teoricos. Los datos diran la verdad. Y esa es exactamente '
    'la clase de hipotesis que queremos tener: una que, si es falsa, nos diga claramente '
    'que lo es, sin dejar espacio para interpretaciones autojustificativas.'
))

# ═══════════════════════════════════════════════════════════════════════════════
# CAPITULO 2: H1 — Hipotesis Central
# ═══════════════════════════════════════════════════════════════════════════════
story.append(h1('Capitulo 2. H1: Hipotesis Central'))

story.append(callout_box(
    '<b>H1:</b> En discos con presupuesto de lectura limitado por degradacion fisica, una estrategia '
    'de adquisicion basada en metadatos recuperables incrementa la cantidad de archivos recuperados '
    'y/o reduce el numero de lecturas necesarias respecto a una estrategia secuencial.'
))

story.append(Spacer(1, 12))

story.append(body(
    'Cada palabra de esta formulacion fue elegida deliberadamente. No es una hipotesis vaga sobre '
    '"mejor recuperacion" — es una afirmacion precisa sobre condiciones especificas, mecanismos '
    'especificos y metricas especificas. Vamos a descomponerla para entender exactamente que '
    'afirma, que no afirma, y bajo que condiciones podria ser verdadera o falsa.'
))

story.append(h2('2.1 Descomposicion de H1'))

story.append(h3('Condicion: "presupuesto de lectura limitado por degradacion fisica"'))

story.append(body(
    'Esta es la condicion habilitante. H1 no afirma que la priorizacion por metadatos sea siempre '
    'mejor. Afirma que es mejor cuando existe una restriccion real en la cantidad de datos que '
    'pueden leerse del disco antes de que este se deteriore irreversiblemente. Esta restriccion '
    'puede provenir de varias fuentes: sectores que se vuelven ilegibles durante la lectura, '
    'un disco que se calienta y falla mas rapido bajo carga sostenida, o un mecanismo de '
    'proteccion interna que limita los reintentos. En un disco sano, sin presupuesto limitado, '
    'ambas estrategias deberian producir resultados equivalentes — y eso es precisamente lo que '
    'esperamos encontrar. Si la priorizacion "ganara" incluso en discos sanos, sospechariamos '
    'un sesgo en el benchmark.'
))

story.append(h3('Mecanismo: "metadatos recuperables"'))

story.append(body(
    'La hipotesis no dice "metadatos" a secas — dice "metadatos recuperables". Esta distincion es '
    'crucial. Si el MFT esta destruido, los metadatos no son recuperables, y el mecanismo que H1 '
    'propone no aplica. En ese escenario, la hipotesis no predice ventaja — y eso es correcto, '
    'no es una debilidad. Es una delimitacion honesta del alcance. El mecanismo funciona cuando '
    'los metadatos estan disponibles; cuando no lo estan, el motor debe recurrir a estrategias '
    'alternativas como carving. Esta transicion —de priorizacion basada en metadatos a carving '
    'cuando los metadatos fallan— es, de hecho, una de las decisiones de diseno mas importantes '
    'que el motor debe tomar, y una de las areas donde mas valor puede aportar.'
))

story.append(h3('Resultado: "incrementa la cantidad de archivos recuperados y/o reduce el numero de lecturas"'))

story.append(body(
    'H1 afirma dos posibles resultados, no solo uno. El primero es cuantitativo: mas archivos '
    'recuperados. El segundo es cualitativo: misma cantidad de archivos, pero con menos lecturas. '
    'El segundo resultado es tan importante como el primero. En un disco inestable, cada lectura '
    'es un riesgo: puede ser la ultima antes de que el disco falle completamente. Si Motor B '
    'recupera los mismos archivos que Motor A pero con un 40% menos de lecturas, eso ya es una '
    'ventaja enorme en la practica clinica de recuperacion de datos. Significa menos estres sobre '
    'el disco, menos probabilidad de dano adicional, y mas margen para reintentos si algo falla. '
    'La formulacion "y/o" es deliberada: cualquiera de los dos resultados basta para validar H1.'
))

story.append(h2('2.2 Lo que H1 NO afirma'))

story.append(body(
    'Es igualmente importante establecer lo que H1 no afirma, para evitar interpretaciones '
    'excesivamente amplias. H1 no afirma que la priorizacion MFT-first sea siempre superior '
    'a la secuencial. No afirma que funcione en todos los sistemas de archivos. No afirma que '
    'funcione cuando el MFT esta destruido. No afirma que la ventaja sea grande — podria ser '
    'modesta, del orden del 3-5%, y aun asi seria valida. H1 no es una promesa de producto; '
    'es una prediccion sobre un mecanismo. Si la prediccion es correcta, el mecanismo se puede '
    'incorporar a un producto. Si no, el mecanismo se descarta y buscamos otro.'
))

story.append(make_table(
    [
        ['H1 SI afirma', 'H1 NO afirma'],
        ['Ventaja con presupuesto limitado', 'Ventaja en todos los escenarios'],
        ['Ventaja cuando MFT es recuperable', 'Ventaja cuando MFT esta destruido'],
        ['Mas archivos O menos lecturas', 'Ambas condiciones simultaneamente'],
        ['Ventaja medible en NTFS', 'Ventaja en todos los filesystems'],
        ['Mecanismo de priorizacion funciona', 'Mecanismo es siempre la mejor opcion'],
    ],
    col_widths=[1, 1],
))

story.append(Spacer(1, 8))

story.append(h2('2.3 Variables de H1'))

story.append(body(
    'Para que H1 sea experimentalmente verificable, necesitamos definir sus variables operativas. '
    'La variable independiente es la estrategia de adquisicion: secuencial (Motor A) vs. basada '
    'en metadatos (Motor B). La variable dependiente principal es la tasa de recuperacion: '
    'porcentaje de archivos recuperados correctamente respecto al total de archivos en el disco. '
    'Las variables dependientes secundarias son el numero total de lecturas realizadas, el tiempo '
    'hasta el primer archivo recuperado, el numero de sectores leidos en vano, y el numero de '
    'reintentos necesarios. Las variables de control incluyen el nivel de dano del disco, el '
    'sistema de archivos utilizado, el tipo de dispositivo (HDD vs SSD), y el presupuesto de '
    'lectura disponible.'
))

story.append(make_table(
    [
        ['Variable', 'Tipo', 'Descripcion'],
        ['Estrategia de adquisicion', 'Independiente', 'Secuencial vs. MFT-first'],
        ['Tasa de recuperacion', 'Dependiente principal', '% archivos recuperados correctamente'],
        ['Numero de lecturas', 'Dependiente secundaria', 'Total de operaciones de lectura'],
        ['Tiempo al primer archivo', 'Dependiente secundaria', 'Segundos hasta primer archivo valido'],
        ['Sectores leidos en vano', 'Dependiente secundaria', 'Lecturas que no contribuyen a recuperacion'],
        ['Reintentos', 'Dependiente secundaria', 'Intentos de lectura fallidos repetidos'],
        ['Nivel de dano', 'Control', '% de sectores danados, % MFT eliminado'],
        ['Filesystem', 'Control', 'NTFS, exFAT, APFS, EXT4'],
        ['Tipo de dispositivo', 'Control', 'HDD SATA, SSD con TRIM'],
        ['Presupuesto de lectura', 'Control', 'Maximo de sectores legibles antes de fallo'],
    ],
    col_widths=[2, 1.5, 3.5],
))

# ═══════════════════════════════════════════════════════════════════════════════
# CAPITULO 3: El simulador — resultados y limites
# ═══════════════════════════════════════════════════════════════════════════════
story.append(h1('Capitulo 3. El simulador: resultados y limites'))

story.append(body(
    'Antes de disenar el siguiente experimento, es esencial entender que nos enseno el simulador '
    'y, mas importante aun, que no nos enseno. El simulador fue el primer paso experimental: '
    'un modelo simplificado que nos permitio probar la hipotesis en condiciones controladas. '
    'Sus resultados fueron prometedores, pero sus limitaciones son significativas. Analizar ambas '
    'cosas con honestidad es la unica forma de disenar el siguiente experimento correctamente.'
))

story.append(h2('3.1 Resultados del simulador'))

story.append(body(
    'El simulador modeloo un disco NTFS con diferentes niveles de dano y presupuesto de lectura. '
    'Comparo dos motores: Motor A (lectura secuencial, sector por sector desde el inicio del disco) '
    'y Motor B (lectura priorizada: primero la MFT, luego los sectores de datos referenciados). '
    'Los resultados mostraron un patron claro y coherente con la fisica del problema.'
))

story.append(make_table(
    [
        ['Escenario', 'Motor A (archivos)', 'Motor B (archivos)', 'Diferencia'],
        ['Disco sano, presupuesto ilimitado', '100%', '100%', '0% (empate)'],
        ['Disco sano, presupuesto limitado', '100%', '100%', '0% (empate)'],
        ['20% sectores danados, presupuesto bajo', '67%', '89%', '+22%'],
        ['40% sectores danados, presupuesto bajo', '34%', '71%', '+37%'],
        ['60% sectores danados, presupuesto bajo', '12%', '54%', '+42%'],
        ['Disco muriendose, presupuesto critico', '0%', '31%', '+31%'],
    ],
    col_widths=[2.5, 1.5, 1.5, 1.5],
))

story.append(Spacer(1, 8))

story.append(body(
    'Estos resultados son consistentes con la prediccion de H1: la ventaja de Motor B aumenta '
    'a medida que el presupuesto de lectura se reduce y el dano al disco es mayor. En escenarios '
    'donde el presupuesto es generoso o el disco esta sano, no hay diferencia — lo cual es '
    'logico y, de hecho, tranquilizador. Si Motor B ganara siempre, sospechariamos un sesgo '
    'en el benchmark. El patron "empate cuando no hay restriccion, ventaja cuando hay restriccion" '
    'es exactamente lo que predice la fisica del problema.'
))

story.append(h2('3.2 El error detectado y corregido'))

story.append(body(
    'Durante la ejecucion del simulador, se detecto un error critico: Motor A recuperaba 0 archivos '
    'en ciertos escenarios, no porque la estrategia secuencial fuera inherentemente incapaz de '
    'recuperar algo, sino porque el modelo no representaba correctamente la realidad. El motor '
    'secuencial no debia recuperar cero archivos — debia recuperar menos que Motor B, pero no cero. '
    'Este error fue detectado y corregido antes de sacar conclusiones, y ese proceso de correccion '
    'es posiblemente mas valioso que los resultados mismos. Detectar que el modelo no representaba '
    'la realidad antes de publicar conclusiones es la diferencia entre ciencia y autoengano.'
))

story.append(body(
    'La correccion del error no cambio la conclusion general — Motor B sigue siendo superior en '
    'escenarios con presupuesto limitado — pero cambio los numeros absolutos. Antes de la '
    'correccion, la diferencia parecia exagerada; despues, la diferencia es mas modesta pero '
    'igualmente significativa. Esto refuerza un principio fundamental: los numeros exactos '
    'importan menos que la direccion del efecto. Si la diferencia es del 3% o del 30%, la '
    'conclusion es la misma — pero solo si la medicion es honesta.'
))

story.append(h2('3.3 Limitaciones del simulador'))

story.append(body(
    'El simulador tiene limitaciones fundamentales que debemos reconocer antes de sobreinterpretar '
    'sus resultados. La primera y mas importante: el simulador asume que Motor B "conoce perfectamente '
    'donde estan los datos importantes". En un disco real, el MFT puede estar parcialmente corrupto, '
    'fragmentado, o ilegible en partes. El simulador no modela esta incertidumbre. La segunda '
    'limitacion es que el simulador modela unicamente NTFS. No sabemos si los resultados se '
    'generalizan a otros filesystems como APFS, EXT4, o exFAT. La tercera limitacion es que '
    'el simulador no modela la fragmentacion de archivos ni la fragmentacion del propio MFT. '
    'En un disco real, un archivo puede estar fragmentado en decenas de extensiones, y el MFT '
    'mismo puede estar fragmentado, lo que complica significativamente la tarea de Motor B.'
))

story.append(make_table(
    [
        ['Limitacion', 'Impacto', 'Se resuelve en proximo experimento?'],
        ['MFT perfectamente conocido', 'Sobrestima ventaja de Motor B', 'Si, con corrupcion controlada'],
        ['Solo NTFS', 'No sabemos si generaliza', 'Parcialmente, con otros FS'],
        ['Sin fragmentacion', 'Simplifica la realidad', 'Si, con imagenes reales'],
        ['Sin journal corrupto', 'Ignora fuente de informacion', 'Si, con corrupcion de journal'],
        ['Sin SSD/TRIM', 'No aplica a SSD', 'No en esta fase'],
    ],
    col_widths=[2, 2.5, 2.5],
))

story.append(Spacer(1, 8))

story.append(body(
    'La pregunta clave que el simulador responde no es la misma que la pregunta original. '
    'La pregunta original era: "Leer primero la informacion correcta mejora la recuperacion?" '
    'La pregunta que el simulador responde es: "Si conocemos perfectamente donde estan los '
    'datos importantes, la priorizacion mejora la recuperacion?" La diferencia entre ambas '
    'preguntas es la distancia entre la simulacion y la realidad. Y esa distancia es '
    'precisamente lo que el siguiente experimento debe reducir.'
))

# ═══════════════════════════════════════════════════════════════════════════════
# CAPITULO 4: El siguiente experimento
# ═══════════════════════════════════════════════════════════════════════════════
story.append(h1('Capitulo 4. El siguiente experimento: imagenes reales'))

story.append(body(
    'El siguiente paso experimental no es tocar un disco fisico. Es usar imagenes reales de disco. '
    'Las imagenes de disco ofrecen la reproducibilidad que un disco fisico no puede ofrecer: '
    'podemos crear una imagen, corromperla de forma controlada, ejecutar ambos motores, y repetir '
    'el experimento exactamente con las mismas condiciones. Con un disco fisico, cada lectura '
    'degrada el disco y hace el experimento irreproducible. Con imagenes, tenemos control total '
    'sobre las variables, y podemos iterar rapidamente.'
))

story.append(h2('4.1 Diseno del experimento'))

story.append(body(
    'El experimento consiste en crear imagenes NTFS con contenido conocido, corromperlas de forma '
    'controlada, y ejecutar dos estrategias de adquisicion sobre cada imagen. La comparacion se '
    'realiza con checksums SHA-256 de cada archivo recuperado, verificando no solo que el archivo '
    'fue "recuperado" sino que fue recuperado correctamente. Un archivo con un solo byte incorrecto '
    'no cuenta como recuperado. Este criterio es mas estricto que el del simulador, y '
    'deliberadamente asi: queremos medir recuperacion real, no aproximaciones.'
))

story.append(h3('Paso 1: Crear imagen NTFS base'))

story.append(body(
    'Se crea una imagen de disco NTFS de 1 GB usando herramientas estandar (mkntfs). Se genera '
    'un conjunto de archivos de prueba con tipos y tamanos variados: documentos de texto, '
    'imagenes JPEG, archivos de oficina, binarios comprimidos. Cada archivo se registra con '
    'su checksum SHA-256, su ruta original, y su ubicacion de sectores en el disco. Este '
    'registro es la "verdad fundamental" (ground truth) contra la cual se medira la '
    'recuperacion. Sin esta verdad fundamental, no podemos medir nada.'
))

story.append(h3('Paso 2: Corromper sectores especificos'))

story.append(body(
    'Se aplican patrones de corrupcion controlados a la imagen. Los patrones son reproducibles '
    'y cubren las dimensiones criticas que el simulador no modelaba: destruccion parcial del MFT '
    '(eliminando entradas especificas), fragmentacion del MFT (forzando que el MFT se extienda '
    'en multiples runs), corrupcion del journal de NTFS ($LogFile), sectores danados en zonas '
    'de datos de usuario, y corrupcion de entradas de directorio (INDX). Cada patron de '
    'corrupcion se identifica con un codigo unico para trazabilidad.'
))

story.append(h3('Paso 3: Ejecutar dos estrategias'))

story.append(body(
    'Se implementan dos motores de lectura minimos. Motor A lee la imagen secuencialmente desde '
    'el sector 0 hasta el final, con un presupuesto de lectura limitado. Motor B lee primero '
    'la MFT (o lo que quede de ella), identifica los sectores de datos referenciados, y los '
    'lee en orden de prioridad. Ambos motores se ejecutan sobre la misma imagen corrompida, '
    'con el mismo presupuesto de lectura. El presupuesto se simula limitando el numero de '
    'sectores que cada motor puede leer antes de "detenerse".'
))

story.append(h3('Paso 4: Comparar resultados'))

story.append(body(
    'La comparacion se realiza en tres niveles. Primero, archivo-recuperado: un archivo se '
    'considera recuperado si su checksum SHA-256 coincide con el ground truth. Segundo, '
    'archivo-parcial: un archivo se considera parcialmente recuperado si se recuperaron mas '
    'del 50% de sus sectores pero el checksum no coincide. Tercero, metricas de eficiencia: '
    'numero de lecturas, sectores desperdiciados, tiempo hasta primer archivo. Este sistema '
    'de tres niveles evita la dicotomia simplista de "recuperado vs no recuperado" y captura '
    'matices que el simulador no podia.'
))

story.append(h2('4.2 Patrones de corrupcion'))

story.append(make_table(
    [
        ['Codigo', 'Patron', 'Descripcion', 'MFT afectado?'],
        ['C01', 'MFT 20% eliminado', 'Entradas aleatorias del MFT borradas', 'Si'],
        ['C02', 'MFT 40% eliminado', 'Entradas aleatorias del MFT borradas', 'Si'],
        ['C03', 'MFT 60% eliminado', 'Entradas aleatorias del MFT borradas', 'Si'],
        ['C04', 'MFT fragmentado', 'MFT en multiples runs no contiguos', 'Si (parcial)'],
        ['C05', 'MFT zona ilegible', 'Parte del MFT en sectores danados', 'Si (parcial)'],
        ['C06', 'Journal corrupto', '$LogFile con datos invalidos', 'No'],
        ['C07', 'Directorios destruidos', 'Entradas INDX corruptas', 'No'],
        ['C08', 'Sectores datos danados', 'Sectores de datos de usuario ilegibles', 'No'],
        ['C09', 'Combinado: MFT+journal', 'C05 + C06 simultaneamente', 'Si'],
        ['C10', 'Combinado: todo', 'C05 + C06 + C07 + C08', 'Si'],
    ],
    col_widths=[0.7, 1.5, 2.5, 1.3],
))

story.append(Spacer(1, 8))

story.append(body(
    'Los patrones C01-C03 replican los escenarios del simulador pero con imagenes reales. '
    'Los patrones C04-C05 abren la dimension de incertidumbre en el MFT que el simulador no '
    'modelaba. Los patrones C06-C07 evaluan fuentes de informacion alternativa (journal, INDX). '
    'Y los patrones C09-C10 combinan multiples formas de dano para aproximarse a la complejidad '
    'de un disco real. Esta progresion de complejidad permite identificar exactamente donde '
    'la ventaja de Motor B comienza a degradarse.'
))

story.append(h2('4.3 Presupuestos de lectura'))

story.append(body(
    'Cada imagen corrompida se prueba con multiples presupuestos de lectura. El presupuesto '
    'se define como un porcentaje del total de sectores del disco. Un presupuesto del 100% '
    'significa que el motor puede leer todo el disco; un presupuesto del 20% significa que '
    'solo puede leer una quinta parte. Los presupuestos elegidos son: 100%, 80%, 60%, 40%, '
    '20% y 10%. Esto permite trazar la curva de rendimiento de cada motor en funcion del '
    'presupuesto disponible, y observar como la ventaja de Motor B cambia con la restriccion.'
))

# ═══════════════════════════════════════════════════════════════════════════════
# CAPITULO 5: Metricas ampliadas
# ═══════════════════════════════════════════════════════════════════════════════
story.append(h1('Capitulo 5. Metricas ampliadas'))

story.append(body(
    'El simulador midio una unica metrica: archivos recuperados. El siguiente experimento debe '
    'medir mucho mas. La razon es doble: primero, porque la recuperacion de datos no es solo '
    'una cuestion de cantidad, sino de eficiencia y seguridad. Segundo, porque la ventaja de '
    'Motor B puede manifestarse en dimensiones que no son capturadas por la tasa de recuperacion '
    'bruta. Si Motor B recupera los mismos archivos que Motor A pero con un 40% menos de '
    'lecturas, eso ya es una ventaja enorme para discos inestables — y es una ventaja que '
    'el simulador no podia detectar.'
))

story.append(h2('5.1 Metricas primarias'))

story.append(make_table(
    [
        ['Metrica', 'Unidad', 'Descripcion'],
        ['Tasa de recuperacion', '%', 'Archivos con checksum correcto / total archivos'],
        ['Tasa de recuperacion parcial', '%', 'Archivos con >50% de sectores correctos / total'],
        ['Integridad de datos', 'Booleano', 'Checksum SHA-256 coincide con ground truth'],
    ],
    col_widths=[2, 1, 4],
))

story.append(Spacer(1, 8))

story.append(body(
    'La tasa de recuperacion es la metrica principal, la que directamente valida o refuta H1. '
    'Pero la tasa de recuperacion parcial es igualmente importante: un archivo parcialmente '
    'recuperado puede ser salvable con tecnicas de reparacion, mientras que un archivo no '
    'recuperado no tiene ninguna posibilidad. La integridad de datos es un filtro de calidad: '
    'un motor que "recupera" archivos con datos incorrectos no esta recuperando, esta corrompiendo. '
    'El checksum SHA-256 es el estandar de la industria para verificar integridad, y su uso '
    'es obligatorio en cada archivo recuperado.'
))

story.append(h2('5.2 Metricas de eficiencia'))

story.append(make_table(
    [
        ['Metrica', 'Unidad', 'Descripcion'],
        ['Lecturas totales', 'Conteo', 'Numero total de operaciones de lectura ejecutadas'],
        ['Sectores desperdiciados', 'Conteo', 'Lecturas que no contribuyen a ningun archivo recuperado'],
        ['Eficiencia de lectura', '%', 'Sectores utiles / sectores totales leidos'],
        ['Tiempo al primer archivo', 'Segundos', 'Tiempo desde inicio hasta primer archivo con checksum correcto'],
        ['Tiempo total', 'Segundos', 'Tiempo desde inicio hasta agotar presupuesto'],
    ],
    col_widths=[2, 1, 4],
))

story.append(Spacer(1, 8))

story.append(body(
    'Las metricas de eficiencia capturan la dimension que el simulador ignoro: el costo de cada '
    'lectura. En un disco inestable, cada lectura es un recurso escaso. Si Motor A necesita 100,000 '
    'lecturas para recuperar 50 archivos, y Motor B necesita 60,000 lecturas para recuperar los '
    'mismos 50 archivos, Motor B es un 40% mas eficiente — y eso significa que tiene 40,000 '
    'lecturas adicionales que podria usar para recuperar mas archivos si el presupuesto lo '
    'permitiera. La eficiencia de lectura es la metrica que conecta directamente con la '
    'experiencia del usuario: un motor eficiente no solo recupera mas, sino que cansa menos '
    'el disco y deja mas margen para operaciones de rescate adicionales.'
))

story.append(h2('5.3 Metricas de estres'))

story.append(make_table(
    [
        ['Metrica', 'Unidad', 'Descripcion'],
        ['Reintentos', 'Conteo', 'Intentos de lectura fallidos repetidos sobre el mismo sector'],
        ['Sectores con error', 'Conteo', 'Sectores que generaron error de lectura'],
        ['Secuencia de errores', 'Lista', 'Patron temporal de errores (para detectar degradacion)'],
        ['Lecturas consecutivas sin error', 'Conteo', 'Maximo de lecturas exitosas seguidas'],
    ],
    col_widths=[2.5, 1, 3.5],
))

story.append(Spacer(1, 8))

story.append(body(
    'Las metricas de estres son relevantes para la futura integracion con el motor de decisiones. '
    'Si el motor puede detectar que el disco esta degradandose (mas errores por unidad de tiempo, '
    'secuencia de errores creciente), puede ajustar su estrategia en tiempo real: priorizar '
    'los archivos mas importantes, reducir los reintentos, o cambiar a un modo de adquisicion '
    'mas conservador. Estas metricas no validan H1 directamente, pero preparan el terreno '
    'para las versiones futuras del motor de decisiones. El motor V1 (reglas expertas) '
    'usara estas metricas como entradas; el motor V2 (red bayesiana) las usara como evidencia; '
    'el motor V3 (ML) las usara como features de entrenamiento.'
))

story.append(h2('5.4 Escenario hipotetico: la ventaja oculta'))

story.append(callout_box(
    'Imaginemos un escenario donde Motor A y Motor B recuperan la misma cantidad de archivos. '
    'A primera vista, H1 no tendria soporte. Pero si miramos las metricas de eficiencia: '
    'Motor A realizo 100,000 lecturas, Motor B realizo 60,000. Motor A desperdicio 45,000 '
    'lecturas en sectores que no contenian datos utiles; Motor B desperdicio solo 5,000. '
    'Motor B llego al primer archivo en 12 segundos; Motor A tardo 180 segundos. En un disco '
    'inestable, esa diferencia de 40,000 lecturas es la diferencia entre un disco que '
    'sobrevive y un disco que muere durante la recuperacion. Este escenario no es hipotetico '
    '— es exactamente lo que esperamos encontrar en discos con presupuesto limitado.',
    accent_color=SEM_INFO,
))

# ═══════════════════════════════════════════════════════════════════════════════
# CAPITULO 6: Cuando el MFT falla
# ═══════════════════════════════════════════════════════════════════════════════
story.append(h1('Capitulo 6. Cuando el MFT falla'))

story.append(body(
    'La mayor debilidad de Motor B es su dependencia del MFT. Si el MFT esta destruido, Motor B '
    'no puede saber que sectores priorizar, y su ventaja desaparece. Pero esta debilidad es, '
    'paradojicamente, una oportunidad. Porque la decision de "cambiar a carving cuando el MFT '
    'falla" puede ser mas valiosa que la priorizacion misma. Un motor que siempre intenta '
    'priorizar basandose en un MFT destruido no solo no obtiene ventaja — obtiene resultados '
    'peores que la lectura secuencial, porque pierde tiempo intentando leer metadatos ilegibles. '
    'Un motor que detecta que el MFT no es confiable y cambia automaticamente a carving esta '
    'tomando una decision inteligente que ningun motor actual toma de forma sistematica.'
))

story.append(h2('6.1 Arbol de decisiones de diagnostico'))

story.append(body(
    'El diagnostico del estado del MFT es el primer paso de cualquier estrategia de recuperacion '
    'inteligente. No se trata de "leer la MFT y priorizar" — se trata de "evaluar si la MFT '
    'es utilizable, y si no lo es, cambiar de estrategia". Este arbol de decisiones es, en '
    'esencia, el embrión del motor de decisiones V1: un conjunto de reglas expertas que '
    'determinan la estrategia de adquisicion en funcion del estado del disco.'
))

story.append(code_block(
    'DIAGNOSTICO INICIAL<br/>'
    '|<br/>'
    '|-- MFT legible al 100%? --&gt; PRIORIZAR MFT<br/>'
    '|   |<br/>'
    '|   |-- MFT fragmentada? --&gt; Leer runs de MFT en orden<br/>'
    '|   |<br/>'
    '|   |-- MFT contigua? --&gt; Leer MFT de una vez<br/>'
    '|<br/>'
    '|-- MFT parcialmente legible (40-99%)?<br/>'
    '|   |<br/>'
    '|   |-- Entradas MFT recuperables? --&gt; PRIORIZAR MFT parcial<br/>'
    '|   |   |<br/>'
    '|   |   |-- Complementar con JOURNAL<br/>'
    '|   |   |-- Complementar con INDX<br/>'
    '|   |   |-- Complementar con BITMAP<br/>'
    '|   |<br/>'
    '|   |-- MFT mayormente ilegible? --&gt; CARVING<br/>'
    '|       |<br/>'
    '|       |-- Usar journal para identificar archivos<br/>'
    '|       |-- Usar INDX para reconstruir directorios<br/>'
    '|<br/>'
    '|-- MFT destruido (&lt;40%)?<br/>'
    '    |<br/>'
    '    |-- CARVING puro<br/>'
    '    |   |<br/>'
    '    |   |-- Buscar firmas de archivo (JPEG, PNG, PDF, DOCX...)<br/>'
    '    |   |-- Reconstruir archivos por extensiones contiguas<br/>'
    '    |<br/>'
    '    |-- Complementar con fuentes secundarias<br/>'
    '        |<br/>'
    '        |-- $LogFile (journal) para operaciones recientes<br/>'
    '        |-- $Bitmap para sectores en uso<br/>'
    '        |-- $Secure para permisos<br/>'
    '        |-- INDX para estructura de directorios'
))

story.append(Spacer(1, 8))

story.append(body(
    'Este arbol de decisiones no es un motor de IA. Es un conjunto de reglas expertas que '
    'codifican el conocimiento de la estructura NTFS. Cada decision se basa en informacion '
    'observable: el motor puede determinar si el MFT es legible intentando leerlo, puede '
    'determinar si esta fragmentado analizando sus runs, y puede determinar si el journal '
    'es utilizable verificando su integridad. No necesita aprender nada — necesita ejecutar '
    'un diagnostico y actuar en consecuencia. Esta es la esencia del motor de decisiones V1: '
    'reglas que capturan el 90% del valor con el 10% del esfuerzo.'
))

story.append(h2('6.2 Fuentes de informacion alternativas'))

story.append(body(
    'NTFS es un filesystem rico en metadatos. El MFT es la fuente primaria, pero no la unica. '
    'Cuando el MFT falla, el motor tiene multiples fuentes de informacion que puede consultar, '
    'cada una con diferente nivel de confiabilidad y utilidad. El journal ($LogFile) contiene '
    'un registro de transacciones recientes, lo que permite identificar archivos que fueron '
    'modificados o creados poco antes del fallo. El bitmap de asignacion ($Bitmap) indica '
    'que clusters estan en uso, lo que permite descartar sectores que no contienen datos. '
    'Las entradas INDX contienen indices de directorios, lo que permite reconstruir la '
    'estructura de carpetas incluso sin MFT. Y $Secure contiene informacion de permisos, '
    'que puede ayudar a identificar la procedencia de los archivos.'
))

story.append(make_table(
    [
        ['Fuente', 'Archivo NTFS', 'Informacion que aporta', 'Disponibilidad tipica'],
        ['MFT', '$MFT', 'Ubicacion de todos los archivos', '80-95% en discos danados'],
        ['Journal', '$LogFile', 'Transacciones recientes', '60-80% (se sobreescribe)'],
        ['INDX', '$INDEX_ALLOCATION', 'Estructura de directorios', '50-70% (fragmentado)'],
        ['Bitmap', '$Bitmap', 'Clusters en uso', '70-90% (simple, resiliente)'],
        ['$Secure', '$Secure', 'Permisos y atributos', '40-60% (a menudo corrupto)'],
    ],
    col_widths=[1, 1.5, 2.5, 2],
))

story.append(Spacer(1, 8))

story.append(body(
    'La jerarquia de fuentes es importante: el motor debe intentar primero la fuente mas '
    'confiable (MFT), y si no esta disponible, recurrir a las secundarias en orden de '
    'confiabilidad. Esta estrategia de "fallback en cascada" es la que diferencia un motor '
    'inteligente de uno que simplemente lee secuencialmente o que depende de una unica fuente '
    'de informacion. El motor de decisiones V1 no necesita IA para tomar esta decision — '
    'necesita una regla simple: "si el MFT es legible al X%, usalo; si no, pasa al journal; '
    'si no, pasa al INDX; si no, haz carving". El valor umbral de X% es un parametro '
    'que el experimento debe determinar.'
))

story.append(h2('6.3 El experimento de degradacion del MFT'))

story.append(body(
    'Para medir el punto exacto donde Motor B pierde su ventaja, necesitamos un experimento '
    'especifico: degradar progresivamente el MFT y medir el rendimiento de ambos motores '
    'en cada nivel de degradacion. Los niveles de degradacion son: 0% (MFT intacto), 10%, '
    '20%, 30%, 40%, 50%, 60%, 70%, 80%, 90%, 100% (MFT completamente destruido). En cada '
    'nivel, medimos la tasa de recuperacion, la eficiencia de lectura, y el tiempo total. '
    'Este experimento nos permite trazar la "curva de degradacion" de Motor B y determinar '
    'el punto de inflexion donde su ventaja se convierte en desventaja.'
))

story.append(body(
    'La hipotesis es que existe un umbral critico — probablemente entre el 40% y el 60% '
    'de degradacion del MFT — donde Motor B debe cambiar a carving. Por debajo de ese '
    'umbral, Motor B es superior; por encima, Motor B pierde tiempo intentando leer un MFT '
    'que no aporta informacion util. Si este umbral existe y es medible, el motor de '
    'decisiones V1 puede usarlo como regla: "si el MFT esta degradado mas del X%, cambiar '
    'a carving". Esta regla simple, derivada de datos experimentales, captura gran parte '
    'del valor que un motor de IA capturaria con un modelo bayesiano, pero con una '
    'fraccion de la complejidad.'
))

# ═══════════════════════════════════════════════════════════════════════════════
# CAPITULO 7: Matriz de ataque a H1
# ═══════════════════════════════════════════════════════════════════════════════
story.append(h1('Capitulo 7. Matriz de ataque a H1'))

story.append(body(
    'Una hipotesis robusta no es aquella que sobrevive a los escenarios favorables, sino la que '
    'sobrevive a los escenarios desfavorables. Esta seccion disena explicitamente escenarios '
    'para intentar destruir H1. Si H1 sobrevive a estos ataques, su credibilidad aumenta '
    'significativamente. Si H1 cae, habremos aprendido algo valioso: los limites exactos '
    'de la hipotesis. En ambos casos, el conocimiento avanza.'
))

story.append(h2('7.1 Escenarios de ataque'))

story.append(make_table(
    [
        ['Ataque', 'Descripcion', 'Por que podria destruir H1'],
        ['A1: MFT muy fragmentada', 'MFT distribuida en 20+ runs no contiguos', 'Motor B pierde lecturas buscando runs de MFT'],
        ['A2: MFT parcialmente ilegible', 'Sectores del MFT en zonas danadas', 'Motor B no puede completar la MFT, informacion incompleta'],
        ['A3: exFAT', 'Filesystem sin MFT, usa FAT', 'No hay MFT que priorizar, mecanismo de H1 no aplica'],
        ['A4: APFS', 'Filesystem con estructura diferente', 'Estructura de metadatos diferente, estrategia no transferible'],
        ['A5: EXT4', 'Filesystem con journal y superblock', 'Estrategia de priorizacion diferente, H1 no generaliza'],
        ['A6: SSD con TRIM', 'SSD que borra bloques automaticamente', 'Datos no referenciados ya no existen fisicamente'],
        ['A7: Journal corrupto', 'No hay fuente secundaria de informacion', 'Motor B no puede complementar MFT parcial'],
        ['A8: Directorios destruidos', 'Entradas INDX corruptas', 'No se puede reconstruir estructura de archivos'],
        ['A9: Fragmentacion extrema', 'Archivos en 50+ fragmentos', 'Motor B necesita muchas lecturas no contiguas'],
        ['A10: MFT y datos mezclados', 'MFT y datos de usuario en mismas zonas', 'Priorizar MFT no aísla datos de usuario'],
    ],
    col_widths=[0.8, 2.5, 3.7],
))

story.append(Spacer(1, 8))

story.append(body(
    'Cada ataque apunta a una debilidad especifica de H1. El ataque A1 (MFT fragmentada) '
    'prueba si la ventaja de priorizacion persiste cuando el mecanismo de priorizacion es '
    'mas costoso. El ataque A3 (exFAT) prueba si H1 es especifica de NTFS o si generaliza '
    'a otros filesystems. El ataque A6 (SSD con TRIM) prueba si la hipotesis siquiera tiene '
    'sentido en un contexto donde el hardware activamente destruye datos no referenciados. '
    'Y el ataque A10 (MFT y datos mezclados) prueba si la separacion entre metadatos y '
    'datos que H1 asume es realista en practica.'
))

story.append(h2('7.2 Priorizacion de ataques'))

story.append(body(
    'No todos los ataques son igualmente urgentes. Los ataques A1 y A2 son prioritarios porque '
    'son extensiones directas del experimento con imagenes NTFS: no requieren un nuevo filesystem '
    'ni un nuevo tipo de dispositivo. Los ataques A3-A5 son prioritarios en un segundo nivel '
    'porque prueban la generalizacion de H1, pero requieren implementar parsers para cada '
    'filesystem. El ataque A6 (SSD con TRIM) es importante pero tecnicamente complejo: simular '
    'el comportamiento de TRIM requiere un modelo de SSD que no tenemos todavia. Los ataques '
    'A7-A10 son variaciones del experimento NTFS que se pueden ejecutar en paralelo con los '
    'ataques principales.'
))

story.append(make_table(
    [
        ['Prioridad', 'Ataques', 'Requisito adicional', 'Esfuerzo estimado'],
        ['Critica', 'A1, A2', 'Ninguno (imagenes NTFS)', '1-2 semanas'],
        ['Alta', 'A3, A4, A5', 'Parsers de filesystem', '3-4 semanas'],
        ['Media', 'A7, A8, A9', 'Patrones de corrupcion adicionales', '1-2 semanas'],
        ['Baja', 'A6, A10', 'Modelo de SSD, analisis de layout', '4-6 semanas'],
    ],
    col_widths=[1, 1.5, 2.5, 2],
))

story.append(Spacer(1, 8))

story.append(h2('7.3 Criterios de resultado por ataque'))

story.append(body(
    'Para cada ataque, definimos explicitamente que resultado refutaria H1, que resultado '
    'la apoyaria, y que resultado seria ambiguo. Esta definicion previa es crucial: si no '
    'la hacemos antes de ejecutar el experimento, es tentador reinterpretar los resultados '
    'para que apoyen la hipotesis. Definir los criterios de antemano es la forma mas '
    'efectiva de evitar el sesgo de confirmacion.'
))

story.append(make_table(
    [
        ['Ataque', 'H1 refutada si', 'H1 apoyada si', 'Ambiguo si'],
        ['A1', 'Motor B peor que A', 'Motor B mejor que A', 'Diferencia < 3%'],
        ['A2', 'Motor B peor que A', 'Motor B mejor que A', 'Diferencia < 3%'],
        ['A3', 'No hay MFT, H1 no aplica', 'Otro metadato funciona', 'Resultados mixtos'],
        ['A4', 'Estrategia no transferible', 'Principio generaliza', 'Solo parcialmente'],
        ['A5', 'Estrategia no transferible', 'Principio generaliza', 'Solo parcialmente'],
        ['A6', 'TRIM destruye datos utiles', 'TRIM no afecta datos en uso', 'Depende del OS'],
        ['A7', 'Motor B no puede recuperar', 'Motor B usa carving', 'Recuperacion parcial'],
        ['A8', 'Estructura irrecuperable', 'INDX parcial funciona', 'Reconstruccion parcial'],
        ['A9', 'Costo de fragmentacion > ventaja', 'Ventaja persiste', 'Ventaja solo en archivos grandes'],
        ['A10', 'MFT y datos mezclados anulan ventaja', 'Separacion suficiente', 'Ventaja reducida'],
    ],
    col_widths=[0.6, 1.8, 2, 2],
))

# ═══════════════════════════════════════════════════════════════════════════════
# CAPITULO 8: Criterios de decision
# ═══════════════════════════════════════════════════════════════════════════════
story.append(h1('Capitulo 8. Criterios de decision'))

story.append(body(
    'El proposito de todo este trabajo experimental es tomar una decision. No una decision '
    'teórica — una decision practica: construimos el motor de recuperacion o no lo construimos? '
    'Y si lo construimos, con que alcance? Esta seccion define los criterios de decision '
    'antes de ejecutar los experimentos, para que los resultados hablen por si mismos.'
))

story.append(h2('8.1 Umbrales de decision'))

story.append(body(
    'Los umbrales se definen en terminos de la metrica principal: diferencia en tasa de '
    'recuperacion entre Motor B y Motor A, en escenarios con presupuesto de lectura limitado '
    'y MFT parcialmente recuperable. Los umbrales son deliberadamente conservadores: '
    'preferimos un falso negativo (descartar una idea que funcionaria) a un falso positivo '
    '(perseguir una idea que no funciona).'
))

story.append(make_table(
    [
        ['Resultado', 'Diferencia en tasa de recuperacion', 'Decision'],
        ['H1 fuertemente apoyada', 'Motor B > Motor A por 10% o mas', 'Construir motor completo, priorizar MFT-first'],
        ['H1 moderadamente apoyada', 'Motor B > Motor A por 3-10%', 'Construir motor con MFT-first como opcion, no unico modo'],
        ['H1 debilmente apoyada', 'Motor B > Motor A por 1-3%', 'Investigar mas, no construir todavia'],
        ['H1 no apoyada', 'Motor B = Motor A (diferencia < 1%)', 'Descartar MFT-first, explorar otras estrategias'],
        ['H1 refutada', 'Motor B < Motor A', 'Descartar hipotesis, replantear enfoque'],
    ],
    col_widths=[1.5, 2.5, 3],
))

story.append(Spacer(1, 8))

story.append(body(
    'Estos umbrales no son arbitrarios. El 10% es el umbral donde la ventaja es '
    'inequivocamente significativa: en un disco con 10,000 archivos, 10% significa 1,000 '
    'archivos adicionales recuperados. El 3% es el umbral donde la ventaja es real pero '
    'modesta: 300 archivos adicionales, que puede no justificar la complejidad de un motor '
    'de priorizacion. Y el 1% es el umbral de ruido: cualquier diferencia menor al 1% '
    'puede deberse a variabilidad estadistica, no a un efecto real. Estos umbrales se '
    'aplican a la tasa de recuperacion; si la ventaja se manifiesta en metricas de '
    'eficiencia (menos lecturas), se aplican umbrales analogos: 40% menos lecturas '
    'es equivalente a 10% mas archivos en terminos de decision.'
))

story.append(h2('8.2 Escenarios de decision'))

story.append(h3('Escenario A: H1 sobrevive todos los ataques'))

story.append(body(
    'Si Motor B es superior a Motor A en todos los escenarios de NTFS con presupuesto limitado '
    'y MFT parcialmente recuperable, y la ventaja persiste en los ataques A1-A2, la decision '
    'es clara: construir el motor de recuperacion con MFT-first como estrategia predeterminada. '
    'El motor de decisiones V1 se implementaria con reglas expertas basadas en los umbrales '
    'de degradacion del MFT identificados en el experimento. El roadmap avanzaria a la Fase 4 '
    '(construccion del motor) con alta confianza. Este es el mejor escenario, pero tambien '
    'el que requiere mayor escrutinio: si H1 sobrevive "demasiado bien", debemos verificar '
    'que no hay un sesgo sistematico en el diseno experimental.'
))

story.append(h3('Escenario B: H1 sobrevive parcialmente'))

story.append(body(
    'Si Motor B es superior en algunos escenarios pero no en otros — por ejemplo, funciona '
    'bien con MFT degradado al 20-40% pero no al 60%+ — la decision es mas matizada. '
    'Construiriamos el motor, pero con un modo hibrido: MFT-first cuando el MFT es '
    'suficientemente recuperable, secuencial o carving cuando no lo es. El motor de '
    'decisiones V1 seria mas complejo pero mas realista: un arbol de decisiones con '
    'multiples ramas, cada una activada por un diagnostico del estado del disco. '
    'Este escenario es probablemente el mas realista, y no es una mala noticia: '
    'significa que H1 es verdadera en un dominio especifico, y que el motor '
    'debe ser inteligente sobre cuando aplicar la priorizacion.'
))

story.append(h3('Escenario C: H1 cae'))

story.append(body(
    'Si Motor B no ofrece ventaja significativa en ningun escenario, o si la ventaja es '
    'consistentemente menor al 3%, la decision es descartar MFT-first como estrategia '
    'principal. Esto no significa que todo el trabajo fue en vano: los datos experimentales '
    'nos dicen algo valioso sobre la naturaleza del problema. Tal vez la priorizacion no '
    'funciona porque la estructura de NTFS no permite suficiente separacion entre metadatos '
    'y datos. Tal vez funciona pero solo con un presupuesto de lectura tan bajo que no es '
    'realista. En cualquier caso, el conocimiento avanza. Y la proxima hipotesis sera '
    'mejor porque esta informada por datos reales, no por intuicion.'
))

story.append(h2('8.3 La metrica de eficiencia como salvavidas'))

story.append(body(
    'Hay un escenario que no esta en la tabla anterior: Motor A y Motor B recuperan la misma '
    'cantidad de archivos, pero Motor B lo hace con significativamente menos lecturas. En '
    'este escenario, H1 no es refutada — la formulacion "y/o" lo cubre explicitamente. '
    'Pero la decision practica es diferente: no construiriamos un motor que prioriza '
    'archivos, sino un motor que prioriza eficiencia. El producto seria diferente — '
    'no "recuperamos mas archivos" sino "recuperamos los mismos archivos con menos '
    'riesgo para el disco". Esta es una proposicion de valor valida, y posiblemente '
    'mas defendible en el mercado: los profesionales de recuperacion de datos valoran '
    'la seguridad del disco tanto como la tasa de recuperacion.'
))

story.append(body(
    'Este escenario es, de hecho, el que yo considero mas probable. La priorizacion '
    'MFT-first probablemente no recupere dramaticamente mas archivos — la diferencia '
    'en tasa de recuperacion puede ser modesta. Pero la diferencia en eficiencia puede '
    'ser enorme: leer solo los sectores que contienen datos utiles vs. leer todo el disco '
    'es la diferencia entre 60,000 y 100,000 lecturas. En un disco inestable, esa '
    'diferencia es la diferencia entre un disco que sobrevive a la recuperacion y uno '
    'que no. Y si este escenario se confirma, la propuesta de valor del producto '
    'se redefine: no "recuperamos mas", sino "recuperamos mejor".'
))

story.append(h2('8.4 Roadmap post-experimento'))

story.append(body(
    'Independientemente del resultado, el Benchmark Lab genera valor. Si H1 es apoyada, '
    'avanzamos a la Fase 4 con confianza. Si H1 es parcialmente apoyada, avanzamos con '
    'un alcance ajustado. Si H1 cae, replanteamos la hipotesis con datos reales. En '
    'ningun caso el trabajo es desperdiciado. El Benchmark Lab es, en este sentido, '
    'una inversion con retorno garantizado: si la hipotesis es correcta, nos da '
    'confianza; si es incorrecta, nos ahorra meses de trabajo en la direccion '
    'equivocada; y si es parcialmente correcta, nos dice exactamente donde '
    'enfocar el esfuerzo.'
))

story.append(make_table(
    [
        ['Resultado', 'Proxima fase', 'Alcance', 'Timeline estimado'],
        ['H1 fuertemente apoyada', 'Fase 4: Construccion del motor', 'Motor completo con MFT-first', '6-8 meses'],
        ['H1 moderadamente apoyada', 'Fase 4: Motor hibrido', 'Motor con MFT-first + carving', '8-10 meses'],
        ['H1 debilmente apoyada', 'Mas experimentos', 'Ampliar metricas y escenarios', '2-3 meses adicionales'],
        ['H1 no apoyada', 'Replanteamiento', 'Explorar otras estrategias', 'Indefinido'],
        ['H1 refutada', 'Replanteamiento', 'Hipotesis nueva, experimento nuevo', 'Indefinido'],
        ['Ventaja en eficiencia (no en tasa)', 'Fase 4: Motor eficiente', 'Motor con priorizacion de lecturas', '6-8 meses'],
    ],
    col_widths=[1.5, 1.5, 2, 2],
))

story.append(Spacer(1, 16))

story.append(callout_box(
    '<b>Conclusion:</b> Este documento no es un plan de producto. Es un protocolo experimental. '
    'La diferencia es fundamental: un plan de producto asume que la idea funciona; un protocolo '
    'experimental asume que no sabemos si funciona y lo verifica. Si H1 sobrevive a los ataques '
    'disenados en la Matriz de Ataque, ya no sera una intuicion — sera una hipotesis tecnica '
    'con evidencia a favor. Y ese es el punto de partida real para construir un producto.',
    accent_color=SEM_SUCCESS,
))

# ─── BUILD PDF ───────────────────────────────────────────────────────────────
doc = TocDocTemplate(
    BODY_PDF,
    pagesize=A4,
    leftMargin=LEFT_M,
    rightMargin=RIGHT_M,
    topMargin=TOP_M,
    bottomMargin=BOTTOM_M,
    title='Fase 3.5: Benchmark Lab — Validacion Experimental de H1',
    author='Z.ai',
    subject='Benchmark Lab para validacion experimental de la hipotesis de adquisicion basada en metadatos',
)

doc.multiBuild(story, onLaterPages=page_template, onFirstPage=page_template)
print(f'Body PDF generated: {BODY_PDF}')

# ─── COVER HTML ──────────────────────────────────────────────────────────────
cover_html = '''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  @page { size: 794px 1123px; margin: 0; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { width: 794px; height: 1123px; overflow: hidden; }
  .cover {
    position: relative;
    width: 794px;
    height: 1123px;
    background: linear-gradient(165deg, #1a1710 0%, #2d2820 35%, #3d3528 65%, #1a1710 100%);
    font-family: 'Noto Serif SC', 'Noto Serif', Georgia, serif;
    color: #f0ece4;
    margin: 0;
    padding: 0;
  }
  /* Layer 1: Background decorative */
  .cover-bg-layer {
    position: absolute;
    inset: 0;
    overflow: hidden;
    z-index: 1;
  }
  .geo-line {
    position: absolute;
    border: 1px solid rgba(142, 115, 36, 0.15);
  }
  .geo-line-1 { top: 180px; left: 0; right: 0; }
  .geo-line-2 { top: 420px; left: 0; right: 0; }
  .geo-line-3 { top: 750px; left: 0; right: 0; }
  .geo-circle {
    position: absolute;
    border-radius: 50%;
    border: 1px solid rgba(142, 115, 36, 0.1);
  }
  .geo-circle-1 { width: 300px; height: 300px; top: 100px; right: -80px; }
  .geo-circle-2 { width: 200px; height: 200px; bottom: 200px; left: -60px; }
  /* Layer 2: Structure */
  .cover-layer-2 {
    position: absolute;
    inset: 0;
    z-index: 2;
  }
  .accent-line {
    position: absolute;
    left: 60px;
    width: 4px;
    background: rgba(142, 115, 36, 0.6);
  }
  .accent-line-1 { top: 260px; height: 80px; }
  .accent-line-2 { top: 400px; height: 40px; }
  /* Layer 3: Content */
  .cover-layer-3 {
    position: absolute;
    inset: 0;
    z-index: 3;
    padding: 60px;
  }
  .badge {
    display: inline-block;
    font-size: 13px;
    letter-spacing: 4px;
    color: rgba(142, 115, 36, 0.7);
    text-transform: uppercase;
    margin-bottom: 8px;
    font-weight: 300;
  }
  .phase-num {
    position: absolute;
    top: 60px;
    right: 60px;
    font-size: 120px;
    font-weight: 100;
    color: rgba(142, 115, 36, 0.08);
    line-height: 1;
  }
  .title {
    font-size: 42px;
    font-weight: 700;
    line-height: 1.15;
    margin-top: 220px;
    color: #f0ece4;
    max-width: 600px;
  }
  .subtitle {
    font-size: 18px;
    font-weight: 300;
    line-height: 1.6;
    margin-top: 24px;
    color: rgba(240, 236, 228, 0.7);
    max-width: 480px;
  }
  .hypothesis-box {
    margin-top: 40px;
    padding: 20px 24px;
    border-left: 3px solid rgba(142, 115, 36, 0.6);
    background: rgba(142, 115, 36, 0.06);
    max-width: 520px;
  }
  .hypothesis-label {
    font-size: 11px;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: rgba(142, 115, 36, 0.8);
    margin-bottom: 8px;
  }
  .hypothesis-text {
    font-size: 13px;
    font-style: italic;
    line-height: 1.6;
    color: rgba(240, 236, 228, 0.85);
  }
  .meta-block {
    position: absolute;
    bottom: 60px;
    left: 60px;
    right: 60px;
  }
  .meta-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0;
    border-top: 1px solid rgba(240, 236, 228, 0.08);
  }
  .meta-label {
    font-size: 11px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: rgba(240, 236, 228, 0.4);
  }
  .meta-value {
    font-size: 13px;
    color: rgba(240, 236, 228, 0.7);
  }
</style>
</head>
<body>
<div class="cover">
  <div class="cover-bg-layer">
    <div class="geo-line geo-line-1"></div>
    <div class="geo-line geo-line-2"></div>
    <div class="geo-line geo-line-3"></div>
    <div class="geo-circle geo-circle-1"></div>
    <div class="geo-circle geo-circle-2"></div>
  </div>
  <div class="cover-layer-2">
    <div class="accent-line accent-line-1"></div>
    <div class="accent-line accent-line-2"></div>
  </div>
  <div class="cover-layer-3">
    <div class="phase-num">3.5</div>
    <div class="badge">Benchmark Lab</div>
    <div class="title">Validacion Experimental de H1</div>
    <div class="subtitle">
      De la intuicion a la hipotesis. De la hipotesis al experimento.
      Del experimento a la evidencia.
    </div>
    <div class="hypothesis-box">
      <div class="hypothesis-label">Hipotesis Central</div>
      <div class="hypothesis-text">
        En discos con presupuesto de lectura limitado por degradacion fisica,
        una estrategia de adquisicion basada en metadatos recuperables incrementa
        la cantidad de archivos recuperados y/o reduce el numero de lecturas
        necesarias respecto a una estrategia secuencial.
      </div>
    </div>
    <div class="meta-block">
      <div class="meta-row">
        <span class="meta-label">Proyecto</span>
        <span class="meta-value">Motor de Recuperacion de Datos</span>
      </div>
      <div class="meta-row">
        <span class="meta-label">Fase</span>
        <span class="meta-value">3.5 — Benchmark Lab</span>
      </div>
      <div class="meta-row">
        <span class="meta-label">Fecha</span>
        <span class="meta-value">Julio 2026</span>
      </div>
    </div>
  </div>
</div>
</body>
</html>'''

with open(COVER_HTML, 'w', encoding='utf-8') as f:
    f.write(cover_html)
print(f'Cover HTML written: {COVER_HTML}')

# ─── RENDER COVER ────────────────────────────────────────────────────────────
import subprocess
# Use html2poster.js for cover rendering
skill_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'skills', 'pdf')
html2poster = os.path.join(skill_dir, 'scripts', 'html2poster.js')

result = subprocess.run(
    ['node', html2poster, COVER_HTML, '--output', COVER_PDF, '--width', '794px'],
    capture_output=True, text=True, timeout=60
)
if result.returncode != 0:
    print(f'Cover render error: {result.stderr}')
    # Fallback: use Playwright directly
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(f'file://{COVER_HTML}')
            page.pdf(path=COVER_PDF, width='794px', height='1123px', print_background=True, margin={'top': '0', 'right': '0', 'bottom': '0', 'left': '0'})
            browser.close()
        print(f'Cover PDF rendered via Playwright fallback: {COVER_PDF}')
    except Exception as e2:
        print(f'Cover render fallback also failed: {e2}')
else:
    print(f'Cover PDF rendered: {COVER_PDF}')

# ─── MERGE COVER + BODY ─────────────────────────────────────────────────────
from pypdf import PdfWriter, PdfReader

writer = PdfWriter()

# Add cover
cover_reader = PdfReader(COVER_PDF)
cover_page = cover_reader.pages[0]
# Scale cover to body dimensions
body_reader = PdfReader(BODY_PDF)
body_w = float(body_reader.pages[0].mediabox.width)
body_h = float(body_reader.pages[0].mediabox.height)
cover_page.scale_to(body_w, body_h)
writer.add_page(cover_page)

# Add body pages
for page in body_reader.pages:
    writer.add_page(page)

# Add metadata
writer.add_metadata({
    '/Title': 'Fase 3.5: Benchmark Lab - Validacion Experimental de H1',
    '/Author': 'Z.ai',
    '/Subject': 'Benchmark Lab para validacion experimental de la hipotesis de adquisicion basada en metadatos',
    '/Creator': 'Z.ai ReportLab Pipeline',
})

# Write final
with open(FINAL_PDF, 'wb') as f:
    writer.write(f)

print(f'Final PDF: {FINAL_PDF}')
print(f'Total pages: {len(writer.pages)}')

# Cleanup intermediate files
for f in [BODY_PDF, COVER_PDF]:
    if os.path.exists(f):
        os.remove(f)
        print(f'Removed intermediate: {f}')
