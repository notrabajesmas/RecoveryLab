#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Investigación de Viabilidad: Software de Recuperación de Datos
Documento PDF profesional - ReportLab
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
    PageBreak, KeepTogether, Image, HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

# ━━ Font Registration ━━
FONT_DIR = '/usr/share/fonts'

pdfmetrics.registerFont(TTFont('LiberationSans', f'{FONT_DIR}/truetype/chinese/LiberationSans-Regular.ttf'))
pdfmetrics.registerFont(TTFont('LiberationSans-Bold', f'{FONT_DIR}/truetype/chinese/LiberationSans-Regular.ttf'))  # Use same, we'll use bold tag
registerFontFamily('LiberationSans', normal='LiberationSans', bold='LiberationSans-Bold')

pdfmetrics.registerFont(TTFont('Carlito', f'{FONT_DIR}/truetype/english/Carlito-Regular.ttf'))
pdfmetrics.registerFont(TTFont('Carlito-Bold', f'{FONT_DIR}/truetype/english/Carlito-Bold.ttf'))
pdfmetrics.registerFont(TTFont('Carlito-Italic', f'{FONT_DIR}/truetype/english/Carlito-Italic.ttf'))
registerFontFamily('Carlito', normal='Carlito', bold='Carlito-Bold', italic='Carlito-Italic')

# ━━ Cascade Palette ━━
PAGE_BG       = colors.HexColor('#f6f6f5')
SECTION_BG    = colors.HexColor('#f0f0ef')
CARD_BG       = colors.HexColor('#e8e7e2')
TABLE_STRIPE  = colors.HexColor('#f2f2f0')
HEADER_FILL   = colors.HexColor('#62583a')
COVER_BLOCK   = colors.HexColor('#847958')
BORDER        = colors.HexColor('#cac3ae')
ICON          = colors.HexColor('#b09543')
ACCENT        = colors.HexColor('#8a7127')
ACCENT_2      = colors.HexColor('#6141c2')
TEXT_PRIMARY   = colors.HexColor('#1c1b19')
TEXT_MUTED     = colors.HexColor('#8b8981')
SEM_SUCCESS   = colors.HexColor('#40915b')
SEM_WARNING   = colors.HexColor('#8f743d')
SEM_ERROR     = colors.HexColor('#b34e44')
SEM_INFO      = colors.HexColor('#487099')

# ━━ Page Setup ━━
OUTPUT_PATH = '/home/z/my-project/download/Investigacion_Recuperacion_Datos.pdf'
PAGE_W, PAGE_H = A4
LEFT_MARGIN = 22*mm
RIGHT_MARGIN = 22*mm
TOP_MARGIN = 25*mm
BOTTOM_MARGIN = 25*mm
CONTENT_W = PAGE_W - LEFT_MARGIN - RIGHT_MARGIN

# ━━ Styles ━━
styles = getSampleStyleSheet()

# Cover styles
cover_title = ParagraphStyle(
    'CoverTitle', fontName='Carlito-Bold', fontSize=28, leading=34,
    textColor=colors.white, alignment=TA_LEFT, spaceAfter=8*mm
)
cover_subtitle = ParagraphStyle(
    'CoverSubtitle', fontName='Carlito', fontSize=14, leading=20,
    textColor=colors.HexColor('#d4cfc0'), alignment=TA_LEFT, spaceAfter=6*mm
)
cover_meta = ParagraphStyle(
    'CoverMeta', fontName='Carlito-Italic', fontSize=10, leading=14,
    textColor=colors.HexColor('#b0a890'), alignment=TA_LEFT
)

# Body styles
h1_style = ParagraphStyle(
    'H1Custom', fontName='Carlito-Bold', fontSize=22, leading=28,
    textColor=HEADER_FILL, spaceBefore=14*mm, spaceAfter=6*mm,
    borderPadding=0
)
h2_style = ParagraphStyle(
    'H2Custom', fontName='Carlito-Bold', fontSize=16, leading=22,
    textColor=COVER_BLOCK, spaceBefore=10*mm, spaceAfter=4*mm
)
h3_style = ParagraphStyle(
    'H3Custom', fontName='Carlito-Bold', fontSize=13, leading=18,
    textColor=ACCENT, spaceBefore=7*mm, spaceAfter=3*mm
)
body_style = ParagraphStyle(
    'BodyCustom', fontName='LiberationSans', fontSize=10.5, leading=16,
    textColor=TEXT_PRIMARY, alignment=TA_JUSTIFY, spaceAfter=3*mm,
    firstLineIndent=0
)
body_indent = ParagraphStyle(
    'BodyIndent', parent=body_style, leftIndent=12*mm
)
quote_style = ParagraphStyle(
    'QuoteCustom', fontName='Tinos-Italic', fontSize=10, leading=15,
    textColor=TEXT_MUTED, alignment=TA_LEFT, spaceAfter=4*mm,
    leftIndent=15*mm, rightIndent=10*mm, borderPadding=4*mm,
    borderColor=BORDER, borderWidth=0, borderLeftWidth=2,
    borderLeftColor=ACCENT
)
caption_style = ParagraphStyle(
    'CaptionCustom', fontName='Carlito-Italic', fontSize=9, leading=13,
    textColor=TEXT_MUTED, alignment=TA_CENTER, spaceAfter=4*mm
)
toc_style = ParagraphStyle(
    'TOCEntry', fontName='LiberationSans', fontSize=11, leading=18,
    textColor=TEXT_PRIMARY, spaceAfter=2*mm
)
toc_sub_style = ParagraphStyle(
    'TOCSubEntry', fontName='LiberationSans', fontSize=10, leading=16,
    textColor=TEXT_MUTED, leftIndent=8*mm, spaceAfter=1.5*mm
)
bullet_style = ParagraphStyle(
    'BulletCustom', fontName='LiberationSans', fontSize=10.5, leading=16,
    textColor=TEXT_PRIMARY, alignment=TA_LEFT, spaceAfter=2*mm,
    leftIndent=8*mm, bulletIndent=3*mm
)

# Table cell styles
th_style = ParagraphStyle(
    'THStyle', fontName='Carlito-Bold', fontSize=9, leading=13,
    textColor=colors.white, alignment=TA_CENTER
)
td_style = ParagraphStyle(
    'TDStyle', fontName='LiberationSans', fontSize=9, leading=13,
    textColor=TEXT_PRIMARY, alignment=TA_LEFT
)
td_center = ParagraphStyle(
    'TDCenter', fontName='LiberationSans', fontSize=9, leading=13,
    textColor=TEXT_PRIMARY, alignment=TA_CENTER
)

# ━━ Helper Functions ━━
def h1(text):
    return Paragraph(text, h1_style)

def h2(text):
    return Paragraph(text, h2_style)

def h3(text):
    return Paragraph(text, h3_style)

def p(text):
    return Paragraph(text, body_style)

def p_indent(text):
    return Paragraph(text, body_indent)

def quote(text):
    return Paragraph(text, quote_style)

def bullet(text):
    return Paragraph(f'<bullet>&bull;</bullet> {text}', bullet_style)

def spacer(h=3*mm):
    return Spacer(1, h)

def hr():
    return HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=4*mm, spaceBefore=4*mm)

def make_table(headers, rows, col_widths=None):
    """Create a styled table with cascade palette colors."""
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

# ━━ Cover Page (HTML via Playwright) ━━
COVER_HTML = '''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
@page { size: 210mm 297mm; margin: 0; }
* { margin: 0; padding: 0; box-sizing: border-box; }
body { width: 210mm; height: 297mm; background: #2a2518; font-family: 'Carlito', sans-serif; position: relative; overflow: hidden; }
.cover { width: 100%; height: 100%; position: relative; }
.bg-accent { position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: linear-gradient(135deg, #2a2518 0%, #3d3520 50%, #2a2518 100%); }
.deco-line { position: absolute; left: 0; width: 100%; height: 1px; background: rgba(138,113,39,0.3); }
.deco-line-1 { top: 25%; }
.deco-line-2 { top: 72%; }
.deco-bar { position: absolute; left: 0; top: 0; width: 8px; height: 100%; background: #8a7127; }
.content { position: absolute; top: 0; left: 0; width: 100%; height: 100%; display: flex; flex-direction: column; justify-content: center; padding: 60px 55px 60px 50px; }
.tag { font-size: 11px; color: #b09543; letter-spacing: 4px; text-transform: uppercase; margin-bottom: 20px; }
.title { font-size: 32px; font-weight: 700; color: #ffffff; line-height: 1.25; margin-bottom: 16px; max-width: 85%; }
.subtitle { font-size: 15px; color: #c4b896; line-height: 1.5; margin-bottom: 40px; max-width: 75%; }
.meta { font-size: 10px; color: #8b8981; line-height: 1.6; }
.meta span { margin-right: 20px; }
.bottom-bar { position: absolute; bottom: 0; left: 0; width: 100%; height: 4px; background: #8a7127; }
</style>
</head>
<body>
<div class="cover">
  <div class="bg-accent"></div>
  <div class="deco-line deco-line-1"></div>
  <div class="deco-line deco-line-2"></div>
  <div class="deco-bar"></div>
  <div class="content">
    <div class="tag">Informe de Investigacion</div>
    <div class="title">Viabilidad de un Software de Recuperacion de Datos Superior al Mercado</div>
    <div class="subtitle">Analisis exhaustivo del mercado, la competencia, la ingenieria, la ciencia y las oportunidades reales para construir un producto diferenciador</div>
    <div class="meta">
      <span>Fecha: Julio 2026</span>
      <span>Version: 1.0</span>
      <span>Clasificacion: Confidencial</span>
    </div>
  </div>
  <div class="bottom-bar"></div>
</div>
</body>
</html>
'''

# ━━ Page Number Footer ━━
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

# ── TOC ──
story.append(Paragraph("Indice", h1_style))
story.append(spacer(4*mm))

toc_entries = [
    ("1", "El Mercado de la Recuperacion de Datos"),
    ("2", "Analisis de Competidores"),
    ("3", "Ingenieria: Como Funcionan los Recuperadores"),
    ("4", "Investigacion Cientifica y Academica"),
    ("5", "Panorama de Patentes"),
    ("6", "La Comunidad Profesional"),
    ("7", "Oportunidades Reales de Innovacion"),
    ("8", "Conclusion: Vale la Pena?"),
]

for num, title in toc_entries:
    story.append(Paragraph(f'<b>{num}.</b>  {title}', toc_style))

story.append(PageBreak())

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BLOQUE 1: MERCADO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
story.append(h1("1. El Mercado de la Recuperacion de Datos"))

story.append(h2("1.1 Tamano del mercado global"))
story.append(p(
    "El mercado global de software de recuperacion de datos ha experimentado un crecimiento sostenido en la ultima decada, impulsado por la explosion en la cantidad de datos generados tanto por consumidores como por empresas. Segun estimaciones de la industria recopiladas de multiples fuentes de investigacion de mercado, el segmento de software de recuperacion de datos fue valorado en aproximadamente 14.700 millones de dolares en 2025, con proyecciones que indican que podria alcanzar los 31.600 millones para 2034, creciendo a una tasa compuesta anual (CAGR) del 8,9%. Estos numeros incluyen tanto el software de recuperacion como los servicios profesionales asociados, lo que significa que el segmento puramente de software es una fraccion de ese total, estimado entre 3.000 y 5.000 millones de dolares anuales."
))
story.append(p(
    "Es importante distinguir entre el mercado de software de recuperacion de datos (el que nos ocupa) y el mercado mas amplio de proteccion y recuperacion de datos, que incluye soluciones de backup, disaster recovery y continuidad de negocio. Este ultimo mercado es significativamente mayor, valorado en 6.700 millones de dolares en 2023 con proyecciones de 18.800 millones para 2030, pero corresponde a un segmento completamente diferente que no compite directamente con un producto de recuperacion de archivos perdidos o eliminados."
))
story.append(p(
    "El mercado de almacenamiento de siguiente generacion, que incluye SSDs, NVMe y soluciones cloud, fue valorado en 62.800 millones de dolares en 2023 y se proyecta a 116.700 millones para 2030, con un CAGR del 9,8%. Este crecimiento en dispositivos de almacenamiento es directamente proporcional a la demanda de software de recuperacion: a mas datos almacenados, mas datos se pierden, y mas se necesita software capaz de recuperarlos."
))

story.append(h2("1.2 Segmentos del mercado"))
story.append(p(
    "El mercado de recuperacion de datos se divide en tres segmentos principales que presentan dinamicas muy diferentes entre si. El primero es el segmento de consumidores, que representa aproximadamente el 60% de las unidades vendidas pero solo el 30% de los ingresos. Estos usuarios buscan soluciones simples y economicas para recuperar fotos, documentos y videos personales de discos duros, memorias USB y tarjetas SD. El segundo segmento es el de pequenas y medianas empresas (PyMEs), que representa el 25% de los ingresos y busca soluciones mas robustas con soporte para multiples sistemas de archivos y la capacidad de recuperar datos de servidores y RAID basico. El tercer segmento es el profesional y empresarial, que incluye laboratorios de recuperacion de datos, peritos forenses y grandes corporaciones, representando el 45% de los ingresos totales. Este segmento demanda herramientas de alta precision con capacidad de imagen de disco, soporte para RAID avanzado y cadena de custodia."
))

story.append(make_table(
    ["Segmento", "Participacion en Ingresos", "Precio Promedio", "Complejidad Requerida"],
    [
        ["Consumidores", "30%", "$50 - $100", "Baja - Interfaz simple"],
        ["PyMEs", "25%", "$100 - $300", "Media - Multi-filesystem"],
        ["Profesional / Forense", "45%", "$300 - $1.000+", "Alta - RAID, cadena custodia"],
    ],
    [1, 1.2, 1, 1.5]
))
story.append(Paragraph("Tabla 1: Segmentacion del mercado de recuperacion de datos por tipo de usuario", caption_style))

story.append(h2("1.3 Modelos de negocio predominantes"))
story.append(p(
    "La industria de la recuperacion de datos ha adoptado varios modelos de negocio que vale la pena analizar en detalle. El modelo mas comun es el de licencia anual con suscripcion, que se ha impuesto en los ultimos anos sobre el modelo de pago unico. EaseUS, por ejemplo, ofrece su producto Data Recovery Wizard Pro a $69,95 mensuales o $99,95 anuales, mientras que Disk Drill cobra $89 anuales por su licencia Pro. Stellar Data Recovery ofrece tres niveles: Standard a $59,99 anuales, Professional a $89,99 y Premium a $199,99. El modelo freemium tambien es muy popular: la mayoria de los productos ofrecen una version gratuita que permite escanear y ver archivos recuperables, pero limita la recuperacion a unos pocos megabytes (Disk Drill limita a 100 MB, EaseUS a 2 GB) para incentivar la compra de la licencia completa."
))
story.append(p(
    "Un modelo emergente y muy interesante es el de 'pago por resultado', donde el usuario solo paga si efectivamente recupera los archivos que necesita. Este modelo genera una confianza enorme en el consumidor, ya que elimina el riesgo de pagar por un producto que quizas no pueda recuperar lo que necesita. Sin embargo, tambien presenta desafios comerciales: los usuarios con datos menos valiosos pueden optar por no pagar, y los que tienen datos criticos pueden sentirse presionados por la urgencia. R-Studio ofrece un modelo diferente: licencias perpetuas que van desde $49,99 para la version estandar hasta $899 para la version Technician, que incluye soporte forense y recuperacion en red. Este modelo de licencia perpetua es cada vez menos comun en la industria, pero sigue siendo muy valorado por los profesionales que no quieren depender de suscripciones."
))

story.append(h2("1.4 Tendencias clave del mercado"))
story.append(p(
    "Varias tendencias estan redefiniendo el mercado de la recuperacion de datos y creando tanto oportunidades como amenazas para nuevos entrantes. La primera y mas significativa es la transicion de discos duros mecanicos (HDD) a unidades de estado solido (SSD). Los SSD presentan un desafio fundamental para la recuperacion de datos: el comando TRIM, que borra inmediatamente los bloques de datos no utilizados para mantener el rendimiento, hace que la recuperacion de archivos eliminados sea practicamente imposible en la mayoria de los casos. Si el garbage collection del SSD ya se ejecuto, ningun software puede recuperar esos datos. Esto significa que el mercado de recuperacion de datos eliminados se esta reduciendo gradualmente, aunque el mercado de recuperacion por corrupcion de sistema de archivos, formateo accidental o fallo del controlador del SSD sigue siendo robusto."
))
story.append(p(
    "La segunda tendencia es la creciente adopcion de almacenamiento en la nube. Cuando los datos viven en Google Drive, iCloud o Dropbox, la recuperacion de datos depende de los mecanismos de la propia plataforma, no de un software de terceros. Sin embargo, muchos usuarios siguen manteniendo datos locales en discos externos, memorias USB y tarjetas SD, especialmente en paises con conectividad limitada o para datos de gran tamano como videos 4K. La tercera tendencia es la demanda creciente de recuperacion de datos de dispositivos moviles, particularamente telefonos Android y iPhones. EaseUS ha lanzado MobiSaver, Disk Drill tiene soporte para Android, y Stellar ofrece versiones especificas para dispositivos moviles. Este es un segmento de alto crecimiento pero con barreras tecnicas significativas, ya que los sistemas operativos moviles restringen el acceso a bajo nivel al almacenamiento."
))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BLOQUE 2: COMPETIDORES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
story.append(h1("2. Analisis de Competidores"))

story.append(h2("2.1 Disk Drill (CleverFiles)"))
story.append(p(
    "Disk Drill, desarrollado por CleverFiles, es probablemente el competidor mas conocido en el segmento de consumidores. Fundado en Ucrania y ahora con sede en Estados Unidos, Disk Drill se ha posicionado como la solucion 'facil de usar' para recuperacion de datos, con una interfaz limpia y un flujo de trabajo que incluso un usuario sin conocimientos tecnicos puede seguir sin dificultad. Su modelo de precios es de $89 anuales por la licencia Pro, con una version gratuita que permite recuperar hasta 100 MB de datos. En las pruebas de rendimiento, Disk Drill muestra un rendimiento solido en escenarios de eliminacion accidental y formateo rapido, pero sufre en escenarios de danio severo del sistema de archivos, donde su escaneo profundo tiende a producir muchos archivos con nombres genericos como archivo0001.jpg, archivo0002.jpg, etc."
))
story.append(p(
    "Las fortalezas de Disk Drill incluyen su excelente interfaz de usuario, la capacidad de previsualizar archivos antes de recuperarlos, soporte para multiples sistemas de archivos (NTFS, FAT32, exFAT, HFS+, APFS, EXT), y funciones adicionales como la recuperacion de datos de dispositivos moviles y la proteccion de datos mediante Recovery Vault, que guarda metadatos de archivos eliminados para facilitar su recuperacion futura. Entre sus debilidades se encuentran la lentitud del escaneo profundo en discos grandes, la incapacidad de reconstruir la estructura de carpetas original cuando el sistema de archivos esta severamente danado, y la falta de herramientas avanzadas para profesionales como imagen de disco a nivel de sectores o soporte para RAID. Los usuarios en foros como Reddit y Trustpilot elogian su facilidad de uso pero se quejan frecuentemente del limite de 100 MB en la version gratuita y de que el escaneo profundo no siempre encuentra archivos que otros programas si encuentran."
))

story.append(h2("2.2 EaseUS Data Recovery Wizard"))
story.append(p(
    "EaseUS Data Recovery Wizard es probablemente el competidor con mayor cuota de mercado en el segmento de consumidores, en gran parte gracias a una agresiva estrategia de marketing y posicionamiento SEO que hace que su producto aparezca en casi cualquier busqueda relacionada con recuperacion de datos. La empresa, con sede en China, ofrece una version gratuita que permite recuperar hasta 2 GB de datos, lo que es significativamente mas generoso que el limite de 100 MB de Disk Drill. Su estructura de precios incluye un plan mensual a $69,95, un plan anual a $99,95 y una licencia perpetua que ya no se promociona activamente."
))
story.append(p(
    "En terminos de capacidades tecnicas, EaseUS Data Recovery Wizard ofrece un escaneo rapido y un escaneo profundo, soporte para NTFS, FAT, exFAT, HFS+, APFS y EXT, y la capacidad de recuperar datos de particiones perdidas y discos formateados. Sin embargo, las criticas de usuarios son particularmente severas con EaseUS: muchos reportan que el software encuentra archivos que luego no pueden abrirse correctamente, que el soporte tecnico es deficiente, y que el modelo de suscripcion se siente como una trampa. En Reddit, multiples usuarios advierten contra EaseUS, describiendolo como 'marketing agresivo con un producto mediocre'. Esto es relevante porque indica que existe un hueco de mercado significativo: los usuarios quieren un producto que realmente funcione mejor, no solo uno que aparezca primero en Google."
))

story.append(h2("2.3 Stellar Data Recovery"))
story.append(p(
    "Stellar Information Technology, con sede en India, es uno de los actores mas grandes del mercado, con una gama de productos que abarca desde la recuperacion de datos para consumidores hasta soluciones empresariales para servidores Exchange, SQL y bases de datos. Su producto principal, Stellar Data Recovery, se ofrece en tres niveles: Standard a $59,99 anuales (recuperacion basica de archivos eliminados), Professional a $89,99 (agrega recuperacion de particiones perdidas y soporte para sistemas no arrancables) y Premium a $199,99 (agrega reparacion de fotos y videos danados). Esta estructura de precios por niveles es interesante porque permite a Stellar capturar consumidores en diferentes puntos de precio, aunque la revision de usuarios sugiere que el nivel Premium a $199,99 se percibe como caro en comparacion con lo que ofrece."
))
story.append(p(
    "La fortaleza principal de Stellar es su capacidad para manejar escenarios complejos de recuperacion, incluyendo bases de datos danadas, correos electronicos de Outlook y archivos de servidor. Tambien ofrecen servicios profesionales de recuperacion en laboratorio, lo que les permite capturar ingresos tanto de software como de servicios. Sin embargo, la interfaz de usuario de Stellar es menos pulida que la de Disk Drill o EaseUS, y su rendimiento en escenarios de recuperacion simple (archivos eliminados de un disco con sistema de archivos intacto) no es notablemente mejor que el de la competencia. Un punto critico mencionado por usuarios es que Stellar a veces no puede recuperar archivos que otros programas si encuentran, lo que sugiere que su motor de recuperacion puede no ser tan robusto como el de R-Studio o DMDE."
))

story.append(h2("2.4 R-Studio (R-TT)"))
story.append(p(
    "R-Studio, desarrollado por R-TT Inc., es ampliamente considerado como el estandar de la industria para la recuperacion profesional de datos. Con un precio que va desde $49,99 para la version estandar hasta $899 para la version Technician, R-Studio no compite en el segmento de consumidores casuales sino en el de profesionales y laboratorios de recuperacion. Su interfaz es tecnica y poco amigable para usuarios no experimentados, pero su motor de recuperacion es extraordinariamente potente. R-Studio soporta practicamente todos los sistemas de archivos existentes (NTFS, FAT12/16/32, exFAT, HFS+, APFS, Ext2/3/4, UFS, ReiserFS, Btrfs), puede reconstruir RAID de forma automatica, permite recuperacion en red, y ofrece un modo forense que genera hashes de verificacion y mantiene un registro de todas las operaciones realizadas."
))
story.append(p(
    "En los foros de profesionales de recuperacion de datos, R-Studio es consistentemente mencionado como una de las herramientas indispensables. Un tecnico en Reddit lo describio como 'una de las herramientas mas utilizadas para recuperacion logica en laboratorios de recuperacion de datos'. Sin embargo, R-Studio tiene debilidades importantes: su interfaz es intimidante para usuarios no tecnicos, su modelo de licencias se ha vuelto mas restrictivo con el tiempo (lo que ha generado quejas de usuarios que solian recomendarlo), y su escaneo profundo puede ser muy lento en discos grandes. Ademas, R-Studio no ofrece funcionalidades de IA ni diagnosticos inteligentes: es una herramienta puramente tecnica que requiere que el usuario sepa interpretar los resultados."
))

story.append(h2("2.5 UFS Explorer"))
story.append(p(
    "UFS Explorer, desarrollado por SysDev Laboratories (con sede en Ucrania), es una herramienta profesional de alto nivel que se posiciona como una de las mas sofisticadas del mercado para recuperacion de datos complejos. Ofrece multiples ediciones que van desde la version Standard Recovery hasta la version RAID Recovery, con precios que oscilan entre $55 y $500 aproximadamente. UFS Explorer se destaca por su capacidad de manejar sistemas de archivos poco comunes, soporte para RAID de nivel empresarial, y la capacidad de trabajar con dispositivos de almacenamiento que presentan danios logicos severos. Las revisiones de 2025 y 2026 indican que UFS Explorer muestra excelentes resultados en la recuperacion de datos de discos formateados y corruptos, y que su velocidad de escaneo es razonablemente rapida."
))
story.append(p(
    "Sin embargo, UFS Explorer tambien tiene criticas significativas. Las revisiones lo describen como 'funcional pero no el software mas agradable de usar', senalando que carece de muchas funciones de calidad de vida que los usuarios modernos esperan. Su interfaz es densa y tecnica, orientada a profesionales que entienden la estructura de los sistemas de archivos, lo que lo hace poco accesible para usuarios comunes. Ademas, su documentacion es limitada y la curva de aprendizaje es pronunciada. Para un nuevo competidor, esto representa una oportunidad: si se pudiera ofrecer la potencia de UFS Explorer con una interfaz moderna y accesible, se tendria un producto diferenciador significativo."
))

story.append(h2("2.6 ReclaiMe Data Recovery"))
story.append(p(
    "ReclaiMe Data Recovery es una herramienta especializada que ha ganado una reputacion solida entre los profesionales de recuperacion de datos. En los foros de Reddit, especialmente en r/datarecovery y r/AskADataRecoveryPro, ReclaiMe es frecuentemente recomendado como una herramienta muy completa que soporta muchos sistemas de archivos y tecnologias de almacenamiento avanzadas, incluyendo RAID y numerosas tecnicas de cifrado. Su enfoque es mas tecnico y orientado a profesionales que a consumidores, lo que lo posiciona en un nicho similar al de R-Studio y UFS Explorer. Sin embargo, la informacion disponible sugiere que ReclaiMe ha tenido periodos de desarrollo mas lento, y algunos usuarios han expresado preocupacion sobre si el producto sigue siendo mantenido activamente con la misma frecuencia que la competencia."
))

story.append(h2("2.7 TestDisk y PhotoRec (codigo abierto)"))
story.append(p(
    "TestDisk y PhotoRec, ambos desarrollados por CGSecurity, son las herramientas de recuperacion de datos de codigo abierto mas utilizadas en el mundo. TestDisk esta disenado para recuperar particiones perdidas y reparar tablas de particiones danadas, mientras que PhotoRec se enfoca en la recuperacion de archivos mediante la tecnica de 'file carving', que consiste en buscar firmas de archivos (magic numbers) directamente en el contenido binario del disco, sin depender del sistema de archivos. Esta ultima tecnica es particularmente poderosa cuando el sistema de archivos esta completamente destruido, ya que PhotoRec puede seguir encontrando archivos por sus firmas intrinsecas."
))
story.append(p(
    "La fortaleza fundamental de TestDisk y PhotoRec es que son completamente gratuitos y de codigo abierto, lo que significa que cualquier persona puede usarlos, auditarlos y contribuir a su desarrollo. Ademas, al no depender del sistema de archivos, PhotoRec puede recuperar datos en situaciones donde las herramientas comerciales fallan. Sin embargo, sus debilidades son igualmente significativas: ambas herramientas tienen una interfaz de linea de comandos que las hace inaccesibles para la mayoria de los usuarios, no pueden reconstruir la estructura de carpetas original (PhotoRec devuelve archivos con nombres genericos), y no ofrecen previsualizacion de archivos antes de la recuperacion. Estas limitaciones son exactamente las que un nuevo producto podria abordar: ofrecer la potencia del file carving de PhotoRec con una interfaz moderna que permita reconstruir la estructura de carpetas y previsualizar los archivos."
))

story.append(h2("2.8 DMDE (DM Disk Editor and Data Recovery)"))
story.append(p(
    "DMDE es una herramienta que ha ganado una reputacion notable en los ultimos anos como una de las opciones mas potentes y economicas para la recuperacion de datos. Las revisiones de 2025 y 2026 lo describen como 'una herramienta potente y asequible que entrega donde importa', con un motor de recuperacion confiable, un precio honesto y funciones avanzadas como escaneo de firmas personalizadas, edicion de disco y ensamblaje de RAID. La version gratuita de DMDE ofrece funciones como editor de disco, gestor de particiones simple, y la capacidad de crear imagenes y clones de disco, lo que es mas generoso que la mayoria de las versiones gratuitas de la competencia."
))
story.append(p(
    "En los foros de profesionales, DMDE es frecuentemente mencionado junto a R-Studio como una de las herramientas esenciales para la recuperacion de datos. Un usuario en Reddit lo describio como 'el motor de recuperacion mas confiable que he usado, con un precio honesto'. Sin embargo, DMDE comparte las limitaciones de interfaz de las herramientas profesionales: su diseno es tecnico y funcional, pero no esta pensado para usuarios que no tienen conocimientos de sistemas de archivos. Ademas, la version gratuita tiene limites en la cantidad de archivos que se pueden recuperar simultaneamente. Para un nuevo competidor, DMDE representa un benchmark importante: si se puede igualar su potencia de recuperacion con una interfaz significativamente mejor, se tendria un producto con potencial de mercado."
))

story.append(h2("2.9 Tabla comparativa de competidores"))
story.append(make_table(
    ["Software", "Precio", "Interfaz", "Potencia", "Filesystems", "RAID", "Forense"],
    [
        ["Disk Drill", "$89/anio", "Excelente", "Media", "NTFS, FAT, exFAT, HFS+, APFS, EXT", "Basico", "No"],
        ["EaseUS", "$70-100/anio", "Buena", "Media", "NTFS, FAT, exFAT, HFS+, APFS, EXT", "No", "No"],
        ["Stellar", "$60-200/anio", "Regular", "Media-Alta", "NTFS, FAT, exFAT, HFS+, APFS, EXT", "No", "No"],
        ["R-Studio", "$50-900", "Tecnica", "Muy Alta", "12+ sistemas", "Avanzado", "Si"],
        ["UFS Explorer", "$55-500", "Tecnica", "Muy Alta", "12+ sistemas", "Avanzado", "Parcial"],
        ["ReclaiMe", "$100-400", "Basica", "Alta", "Multiples", "Si", "No"],
        ["TestDisk/PhotoRec", "Gratuito", "Consola", "Alta (carving)", "Independiente", "No", "No"],
        ["DMDE", "$20-100", "Tecnica", "Muy Alta", "NTFS, FAT, exFAT, HFS+, EXT", "Si", "No"],
    ],
    [1, 0.8, 0.7, 0.7, 1.5, 0.6, 0.6]
))
story.append(Paragraph("Tabla 2: Comparativa de los principales competidores del mercado de recuperacion de datos", caption_style))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BLOQUE 3: INGENIERIA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
story.append(h1("3. Ingenieria: Como Funcionan los Recuperadores"))

story.append(h2("3.1 Tecnicas fundamentales de recuperacion"))
story.append(p(
    "La recuperacion de datos se basa en un conjunto de tecnicas fundamentales que todos los productos del mercado utilizan en mayor o menor medida. La primera y mas basica es la recuperacion basada en metadatos del sistema de archivos, que consiste en buscar y reconstruir las entradas del sistema de archivos que apuntan a los archivos eliminados. En NTFS, por ejemplo, cuando se elimina un archivo, la entrada en la Master File Table (MFT) se marca como eliminada pero los datos del archivo permanecen en el disco hasta que son sobrescritos. Un software de recuperacion puede buscar estas entradas marcadas como eliminadas y reconstruir los archivos a partir de ellas, siempre que los clusters de datos no hayan sido reutilizados. Esta tecnica es la mas rapida y la que produce mejores resultados (nombres originales, estructura de carpetas, fechas), pero solo funciona cuando el sistema de archivos esta relativamente intacto."
))
story.append(p(
    "La segunda tecnica fundamental es el file carving o escaneo por firmas, que es la tecnica que utilizan herramientas como PhotoRec cuando el sistema de archivos esta completamente destruido. El file carving consiste en escanear el contenido binario del disco buscando firmas de archivos conocidos (magic numbers): por ejemplo, los archivos JPEG comienzan con los bytes FF D8 FF, los archivos PNG con 89 50 4E 47, los archivos PDF con 25 50 44 46, etc. Cuando el software encuentra una firma, intenta determinar el tamano del archivo y extraerlo completo. Esta tecnica es extremadamente poderosa porque no depende del sistema de archivos, pero tiene limitaciones importantes: no puede recuperar los nombres originales de los archivos (ya que esos nombres estan en el sistema de archivos, no en el contenido del archivo), no puede reconstruir la estructura de carpetas, y para archivos fragmentados (cuyos bloques no estan contiguos en el disco) la tasa de exito es baja."
))
story.append(p(
    "La tercera tecnica es la reconstruccion de sistemas de archivos, que es la mas compleja y la que diferencia a las herramientas profesionales de las consumer. Esta tecnica consiste en analizar los restos del sistema de archivos danado y reconstruir la estructura logica a partir de fragmentos: por ejemplo, reconstruir la MFT de NTFS a partir de entradas dispersas, o reconstruir el catalogo de APFS a partir de nodos B-tree residuales. R-Studio y DMDE son particularmente fuertes en esta tecnica, lo que explica por que son las herramientas preferidas por los profesionales. La reconstruccion de sistemas de archivos es fundamentalmente un problema de inteligencia de patrones: encontrar fragmentos que encajan entre si para reconstruir la estructura original, y aqui es donde la inteligencia artificial podria tener un impacto significativo."
))

story.append(h2("3.2 Sistemas de archivos y su recuperabilidad"))
story.append(p(
    "La facilidad con la que se pueden recuperar datos depende en gran medida del sistema de archivos utilizado. NTFS, el sistema de archivos predominante de Windows, es considerado el mas recuperable y resiliente. La razon es que NTFS mantiene una Master File Table (MFT) que registra metadatos detallados de cada archivo, incluyendo su nombre, tamano, ubicacion en disco, fechas de creacion y modificacion, y permisos. Cuando se elimina un archivo en NTFS, la entrada de la MFT se marca como libre pero los datos del archivo permanecen intactos hasta que los clusters son reasignados. Esto significa que, en condiciones normales, la recuperacion de archivos eliminados en NTFS tiene una tasa de exito muy alta, especialmente si se realiza pronto despues de la eliminacion."
))
story.append(p(
    "APFS, el sistema de archivos de Apple introducido en 2017, presenta desafios significativos para la recuperacion. APFS utiliza un diseno basado en contenedores con volumenes compartidos que comparten el espacio de almacenamiento, lo que significa que la relacion entre archivos y bloques fisicos es mas compleja que en NTFS. Ademas, APFS tiene cifrado nativo que, cuando esta activado (como lo esta por defecto en Mac con chip Apple Silicon), hace que la recuperacion de datos sin la clave de cifrado sea imposible. En terminos de recuperacion de archivos eliminados, APFS es mas agresivo que NTFS en la reutilizacion de espacio, lo que reduce la ventana de oportunidad para la recuperacion. Sin embargo, en escenarios de formateo accidental o corrupcion del sistema de archivos, la recuperacion en APFS sigue siendo factible con las herramientas adecuadas."
))
story.append(p(
    "Los sistemas de archivos Linux (ext2/3/4, Btrfs, XFS) presentan sus propios desafios. ext4, el mas comun, elimina los punteros a los bloques de datos cuando se borra un archivo, lo que hace que la recuperacion por metadatos sea muy dificil. Sin embargo, el file carving puede funcionar bien en ext4 porque los datos del archivo suelen permanecer intactos hasta que los bloques son reasignados. Btrfs y XFS presentan desafios adicionales debido a sus estructuras mas complejas (copy-on-write, subvolumenes, checksums). En general, la recuperacion en sistemas de archivos Linux es mas dificil que en NTFS, pero no imposible. La clave para un nuevo producto seria ofrecer un soporte de calidad para todos estos sistemas de archivos, algo que pocos competidores hacen bien simultaneamente."
))

story.append(make_table(
    ["Sistema de Archivos", "Recuperabilidad", "Dificultad", "Notas Clave"],
    [
        ["NTFS", "Alta", "Baja", "MFT conserva metadatos; el mas recuperable"],
        ["FAT32/exFAT", "Media", "Baja", "Estructura simple; nombres accesibles"],
        ["APFS", "Baja-Media", "Alta", "Cifrado nativo; reutilizacion agresiva"],
        ["HFS+", "Media-Alta", "Media", "Catalogo B-tree; buena recuperacion sin cifrado"],
        ["ext2/3/4", "Baja-Media", "Alta", "Punteros eliminados; file carving necesario"],
        ["Btrfs", "Baja", "Muy Alta", "Copy-on-write; complejidad de subvolumenes"],
    ],
    [1, 0.8, 0.8, 2]
))
story.append(Paragraph("Tabla 3: Recuperabilidad por sistema de archivos", caption_style))

story.append(h2("3.3 El desafio de los SSD y TRIM"))
story.append(p(
    "El desafio mas significativo que enfrenta la industria de la recuperacion de datos es la transicion de HDD a SSD. Los SSD utilizan un comando llamado TRIM que informa al controlador del disco cuales bloques de datos ya no estan en uso y pueden ser borrados fisicamente. Cuando un sistema operativo elimina un archivo en un SSD con TRIM habilitado (que es el comportamiento por defecto en Windows, macOS y Linux modernos), el sistema envia inmediatamente un comando TRIM al SSD, indicando que los bloques del archivo pueden ser borrados. El controlador del SSD, durante su proceso de garbage collection, borrara fisicamente esos bloques para mantener el rendimiento del disco. Una vez que los bloques han sido borrados fisicamente, la recuperacion es imposible: no hay datos que recuperar, ni siquiera en un laboratorio profesional."
))
story.append(p(
    "Sin embargo, esto no significa que la recuperacion de datos en SSD sea imposible en todos los casos. Hay varios escenarios donde la recuperacion sigue siendo factible: primero, cuando el SSD tiene TRIM deshabilitado (algunos usuarios lo desactivan para preservar la posibilidad de recuperacion, aunque esto puede afectar el rendimiento); segundo, cuando la perdida de datos se debe a corrupcion del sistema de archivos o formateo accidental y el TRIM no se ha ejecutado todavia; tercero, cuando el SSD tiene un fallo del controlador que hace que el disco sea inaccesible pero los datos siguen estando en los chips NAND; y cuarto, cuando el sistema operativo no envia comandos TRIM (por ejemplo, en algunos sistemas RAID o cuando el SSD esta conectado via USB con un adaptador que no soporta TRIM). Para un nuevo producto, esto es importante porque significa que el mercado de recuperacion de datos no va a desaparecer con los SSD, sino que va a cambiar de naturaleza: la recuperacion de archivos eliminados sera mas dificil, pero la recuperacion de datos de discos danados o corruptos seguira siendo necesaria."
))

story.append(h2("3.4 Imagen de disco: la practica esencial que pocos consumidores conocen"))
story.append(p(
    "Una de las practicas mas importantes en la recuperacion profesional de datos es la creacion de una imagen de disco completa antes de intentar cualquier operacion de recuperacion. Una imagen de disco es una copia bit a bit de todo el contenido del dispositivo de almacenamiento, incluyendo sectores danados, espacios vacios y datos residuales. La razon para crear una imagen antes de trabajar es simple: si el disco esta fallando, cada lectura puede ser la ultima. Un disco con cabezales danados puede fallar completamente durante el proceso de recuperacion, haciendo que los datos que no se hayan copiado se pierdan definitivamente. Al crear una imagen primero, se trabaja sobre la copia, no sobre el disco original, eliminando el riesgo de danio adicional."
))
story.append(p(
    "HDDSuperClone y OpenSuperClone son las herramientas de codigo abierto mas recomendadas para la imagen de discos fallidos. Ambas herramientas pueden pausar, reanudar y trabajar alrededor de sectores danados, y soportan multiples pases de lectura para maximizar la cantidad de datos recuperados del disco danado. La estrategia tipica es realizar un primer pase rapido que lee los sectores sanos, un segundo pase que reintenta los sectores con errores de lectura, y un tercer pase que intenta lecturas mas lentas y agresivas en los sectores mas danados. R-Studio y DMDE pueden trabajar con las imagenes creadas por estas herramientas, combinando la capacidad de imagen de disco con la potencia de recuperacion logica. Para un nuevo producto, la integracion de la imagen de disco con la recuperacion de datos en un solo flujo de trabajo seria una ventaja diferenciadora significativa, ya que hoy en dia los usuarios necesitan usar herramientas separadas para cada paso."
))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BLOQUE 4: INVESTIGACION CIENTIFICA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
story.append(h1("4. Investigacion Cientifica y Academica"))

story.append(h2("4.1 Estado del arte en algoritmos de recuperacion"))
story.append(p(
    "La investigacion academica en recuperacion de datos se ha centrado historicamente en tres areas principales: la mejora de los algoritmos de file carving, la reconstruccion de sistemas de archivos danados, y la recuperacion de archivos fragmentados. El file carving tradicional funciona bien para archivos contiguos, pero falla significativamente con archivos fragmentados, que son aquellos cuyos bloques de datos no estan almacenados en posiciones consecutivas del disco. La fragmentacion es un problema comun en discos que han estado en uso durante mucho tiempo, y los estudios academicos estiman que entre el 5% y el 20% de los archivos en un disco tipico pueden estar fragmentados, dependiendo del sistema de archivos y del patron de uso. Varios investigadores han propuesto algoritmos avanzados de file carving que intentan reconstruir archivos fragmentados analizando las estructuras internas de los archivos (por ejemplo, la estructura de un documento JPEG o un archivo MP4) para determinar el orden correcto de los fragmentos."
))
story.append(p(
    "La reconstruccion de sistemas de archivos danados es otro area activa de investigacion. Los investigadores han desarrollado tecnicas para reconstruir la MFT de NTFS a partir de entradas dispersas, para reconstruir el catalogo B-tree de HFS+ y APFS a partir de nodos residuales, y para reconstruir la tabla de inodos de ext4 a partir de descriptores de grupo supervivientes. Estas tecnicas son fundamentales para la recuperacion de datos en escenarios de formateo accidental o corrupcion severa del sistema de archivos, y representan el limite actual de lo que el software de recuperacion puede lograr sin recurrir al file carving. La mayoria de las herramientas comerciales implementan versiones de estas tecnicas, pero la calidad de la implementacion varia significativamente entre productos, lo que explica por que R-Studio y DMDE superan a la competencia en escenarios complejos."
))

story.append(h2("4.2 Inteligencia artificial aplicada a la recuperacion"))
story.append(p(
    "La aplicacion de inteligencia artificial a la recuperacion de datos es un campo emergente con potencial significativo pero que todavia esta en sus primeras etapas. Las areas donde la IA podria tener mayor impacto son: la reconstruccion de archivos fragmentados (donde los modelos de aprendizaje automatico podrian predecir el orden correcto de los fragmentos basandose en patrones aprendidos de millones de archivos), la reparacion de archivos danados (donde los modelos generativos podrian reconstruir partes faltantes de imagenes, videos o documentos), y el diagnostico inteligente de dispositivos (donde los modelos de clasificacion podrian determinar el tipo de fallo y recomendar la estrategia de recuperacion optima)."
))
story.append(p(
    "En el area de reparacion de imagenes, la investigacion en 'image inpainting' usando redes neuronales ha mostrado resultados impresionantes. Los modelos de deep learning pueden reconstruir partes faltantes de una imagen con un realismo sorprendente, basandose en el contexto visual circundante. Sin embargo, existe una distincion critica entre la reconstruccion estetica (que crea una imagen visualmente plausible) y la reconstruccion fiel (que recupera los datos originales). Para la recuperacion de datos forense o legal, solo la reconstruccion fiel es aceptable, ya que la reconstruccion estetica podria introducir informacion falsa. Para la recuperacion de datos personales (fotos familiares, por ejemplo), la reconstruccion estetica puede ser completamente aceptable e incluso preferible, ya que el usuario prefiere una foto parcialmente reconstruida a una foto con la mitad gris."
))
story.append(p(
    "Una aplicacion particularmente interesante de la IA es la reconstruccion de imagenes JPEG que tienen miniaturas (thumbnails) intactas pero datos de imagen completa danados. Cuando se recuperan archivos de un disco danado, es comun que las miniaturas de los archivos JPEG (que estan almacenadas en una estructura llamada EXIF al principio del archivo) esten intactas pero que los datos de la imagen de resolucion completa esten corruptos. Un modelo de IA podria usar la miniatura como guia para reconstruir la imagen completa, generando una version que, aunque no sea pixel-perfect con respecto al original, seria mucho mejor que una imagen con la mitad gris. Varios investigadores han propuesto este enfoque, pero hasta la fecha no hay productos comerciales que lo implementen de forma robusta."
))

story.append(h2("4.3 Reconstruccion de archivos danados"))
story.append(p(
    "La reconstruccion de archivos danados es un problema que va mas alla de la recuperacion de datos: incluso cuando los datos se han recuperado exitosamente del disco, los archivos pueden estar corruptos porque algunos sectores estaban danados y no pudieron ser leidos. En el caso de los archivos JPEG, esto produce el tipico efecto de 'media imagen gris' donde la parte del archivo que estaba en los sectores danados se pierde. En el caso de los archivos MP4, la corrupcion del contenedor puede hacer que el video sea irreproducible aunque los datos de video y audio esten intactos. En el caso de los documentos de Office (DOCX, XLSX, PPTX), que son en realidad archivos ZIP que contienen XML, la corrupcion de la estructura ZIP puede hacer que el documento sea imposible de abrir."
))
story.append(p(
    "La reconstruccion de archivos MP4 es particularmente interesante porque los archivos MP4 tienen una estructura basada en 'atomos' (tambien llamados 'boxes') que contienen metadatos y datos de video/audio. Si el atomo 'moov' (que contiene los metadatos de sincronizacion) esta danado, el video no se puede reproducir aunque los datos de video esten intactos. Varios investigadores han propuesto tecnicas para reconstruir el atomo moov basandose en los datos de video disponibles, y herramientas como el proyecto Untrunc de codigo abierto intentan hacer exactamente esto. Sin embargo, la calidad de la reconstruccion varia significativamente, y no hay productos comerciales que ofrezcan una reconstruccion confiable de MP4 danados. Este es un area donde la IA podria tener un impacto transformador: un modelo entrenado en millones de estructuras MP4 podria aprender a reconstruir atomos moov danados con una precision mucho mayor que los algoritmos heuristicos actuales."
))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BLOQUE 5: PATENTES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
story.append(h1("5. Panorama de Patentes"))

story.append(h2("5.1 Patentes clave en recuperacion de datos"))
story.append(p(
    "El panorama de patentes en el campo de la recuperacion de datos es complejo y merece un analisis detallado porque afecta directamente la viabilidad de desarrollar un producto comercial sin infringir propiedad intelectual existente. Las patentes mas relevantes se concentran en varias areas: algoritmos de file carving y escaneo por firmas, tecnicas de reconstruccion de sistemas de archivos, metodos de imagen de disco y recuperacion de datos de dispositivos danados, y tecnicas de recuperacion de datos de dispositivos de almacenamiento solido (SSD). Es importante senalar que muchas de las patentes mas antiguas en este campo ya han expirado o estan proximas a expirar, ya que las tecnicas fundamentales de recuperacion de datos se patentaron en los anos 1990 y principios de los 2000. Las patentes de file carving basico, por ejemplo, son en gran parte de dominio publico ahora."
))
story.append(p(
    "Sin embargo, existen patentes mas recientes que cubren tecnicas especificas de implementacion que podrian ser relevantes. Las grandes empresas de recuperacion de datos como Stellar, EaseUS y otras han patentado aspectos de sus productos, incluyendo metodos de interfaz de usuario, algoritmos de reconstruccion especificos y tecnicas de reparacion de archivos. La Oficina de Patentes y Marcas de Estados Unidos (USPTO) tiene un portal de datos abiertos que permite buscar patentes existentes, y cualquier nuevo producto deberia realizar una busqueda exhaustiva de patentes antes de su lanzamiento. Lo que es importante entender es que las patentes protegen implementaciones especificas, no ideas generales: el concepto de file carving no esta patentado, pero un metodo especifico de file carving que utiliza una tecnica particular de hashing o de reconstruccion de fragmentos si podria estarlo."
))

story.append(h2("5.2 Espacio libre para innovar"))
story.append(p(
    "El analisis del panorama de patentes revela que existe un espacio significativo para la innovacion sin infringir propiedad intelectual existente. Las areas donde hay mas libertad para innovar incluyen: la aplicacion de inteligencia artificial y aprendizaje automatico a la recuperacion de datos (un campo que apenas esta emergiendo y donde hay pocas patentes), la creacion de interfaces de usuario innovadoras que guien al usuario a traves del proceso de recuperacion (las patentes existentes cubren interfaces tecnicas, no interfaces orientadas al usuario), el diagnostico inteligente de dispositivos de almacenamiento que recomiende estrategias de recuperacion basadas en el tipo de fallo detectado, y la integracion de herramientas de imagen de disco y recuperacion de datos en un solo flujo de trabajo coherente. La clave para navegar el panorama de patentes es enfocarse en la innovacion de procesos y experiencias de usuario, no en los algoritmos fundamentales de recuperacion de datos, que en su mayoria son de dominio publico."
))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BLOQUE 6: COMUNIDAD PROFESIONAL
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
story.append(h1("6. La Comunidad Profesional"))

story.append(h2("6.1 Que usan los profesionales"))
story.append(p(
    "Los profesionales de la recuperacion de datos forman una comunidad relativamente pequena pero extremadamente bien informada, que se congrega principalmente en foros como r/datarecovery, r/AskADataRecoveryPro y r/computerforensics en Reddit, asi como en foros especializados como el de My Hard Drive Died. A diferencia de los consumidores, los profesionales no se dejan impresionar por interfaces bonitas ni por marketing agresivo: ellos juzgan las herramientas por su eficacia en escenarios reales de recuperacion. Cuando se pregunta a los profesionales que herramientas utilizan, las respuestas son notablemente consistentes: R-Studio y DMDE son mencionados como herramientas esenciales por practicamente todos los profesionales, seguidos por UFS Explorer y ReclaiMe para escenarios especializados. Para la imagen de discos fallidos, HDDSuperClone y OpenSuperClone son las herramientas de referencia."
))
story.append(p(
    "Es revelador que las herramientas mas recomendadas por profesionales (R-Studio, DMDE, HDDSuperClone) son tambien las que tienen las interfaces mas tecnicas y menos amigables. Esto sugiere que los profesionales valoran la potencia y la fiabilidad por encima de la experiencia de usuario, lo que crea una oportunidad clara para un producto que ofrezca la potencia de estas herramientas con una interfaz moderna y accesible. Sin embargo, tambien es una senal de advertencia: los profesionales no adoptaran un producto que sacrifique funcionalidad por estetica. Cualquier nuevo producto debe ser tan potente como R-Studio o DMDE en su motor de recuperacion antes de intentar mejorar la interfaz."
))

story.append(h2("6.2 Quejas y demandas de la comunidad"))
story.append(p(
    "Las quejas mas frecuentes de los profesionales de recuperacion de datos revelan patrones interesantes que un nuevo producto podria abordar. La primera queja es la falta de herramientas que combinen la imagen de disco y la recuperacion de datos en un solo flujo de trabajo. Hoy en dia, los profesionales necesitan usar HDDSuperClone para crear la imagen del disco danado, y luego usar R-Studio o DMDE para recuperar los datos de la imagen. Un producto que integre ambos pasos en un solo flujo de trabajo seria enormemente valorado. La segunda queja es la lentitud del escaneo profundo en discos grandes. Los discos de 18 TB o mas pueden tardar 40 horas en escanearse, y si se interrumpe el proceso, hay que empezar de cero. La tercera queja es la falta de checkpoints o puntos de guardado durante el escaneo, que permitan reanudar el proceso desde donde se interrumpio."
))
story.append(p(
    "La cuarta queja es la incapacidad de la mayoria de las herramientas para priorizar la recuperacion de archivos importantes. Cuando un profesional necesita recuperar datos de un disco que esta fallando, cada lectura puede ser la ultima, y quiza solo haya tiempo para recuperar una fraccion de los datos antes de que el disco falle completamente. En esa situacion, seria ideal poder decirle al software: 'recupera primero las fotos, luego los documentos, y si queda tiempo, los videos'. Ningun producto del mercado ofrece esta capacidad de priorizacion de forma automatica. La quinta queja es la falta de diagnostico inteligente: los profesionales quieren que el software les diga que tipo de fallo tiene el disco y cual es la mejor estrategia de recuperacion, en lugar de tener que determinarlo por si mismos basandose en su experiencia."
))
story.append(p(
    "Un tecnico de recuperacion de datos en un AMA (Ask Me Anything) en Reddit lo describio asi: 'La recuperacion de datos es por naturaleza un negocio muy secreto. Hay mucha informacion propietaria, muchas cosas que no se comparten'. Esta cultura de secretismo es una barrera para la innovacion, pero tambien es una oportunidad: un producto que sea transparente, que comparta conocimiento y que haga accesibles las tecnicas de recuperacion avanzada a un publico mas amplio tendria una ventaja competitiva unica en un mercado donde la opacidad es la norma."
))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BLOQUE 7: OPORTUNIDADES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
story.append(h1("7. Oportunidades Reales de Innovacion"))

story.append(h2("7.1 Innovaciones con alto impacto y viabilidad"))
story.append(p(
    "Despues de analizar el mercado, la competencia, la ingenieria y la comunidad profesional, es posible identificar las innovaciones que tendrian mayor impacto y son mas viables de implementar. La primera y mas importante es el diagnostico inteligente previo a la recuperacion: un modulo que analice el disco durante 20-30 segundos antes de comenzar cualquier operacion, determine el tipo de fallo, evalúe el riesgo de que el disco empeore durante la lectura, y recomiende automaticamente la estrategia de recuperacion optima. Este modulo no requiere IA avanzada: se puede implementar con reglas heuristicas basadas en la lectura de atributos SMART, el analisis de patrones de errores y la identificacion del modelo del disco. El impacto seria enorme porque abordaria una de las quejas mas comunes de los profesionales y porque educaria a los consumidores sobre la importancia de crear una imagen antes de intentar la recuperacion."
))
story.append(p(
    "La segunda innovacion de alto impacto es la implementacion de checkpoints y recuperacion incremental durante el escaneo. Esto permite que un escaneo que se interrumpe (por corte de energia, fallo del disco, o decision del usuario) pueda reanudarse desde el ultimo punto guardado en lugar de empezar de cero. La implementacion es tecnicamente factible: consiste en guardar periodicamente el estado del escaneo (sectores ya procesados, archivos encontrados, posiciones de reintentos) en un archivo de progreso que se puede cargar al reanudar. El impacto es enorme porque los escaneos de discos grandes pueden tardar decenas de horas, y la posibilidad de perder todo el progreso por una interrupcion es una de las frustraciones mas grandes de los usuarios actuales."
))
story.append(p(
    "La tercera innovacion es la priorizacion inteligente de archivos durante la recuperacion. En lugar de escanear secuencialmente y recuperar todos los archivos al final, el software podria permitir al usuario definir prioridades (por ejemplo, 'fotos primero, luego documentos, luego videos') y comenzar a recuperar archivos apenas los encuentra, sin esperar a que termine el escaneo completo. Esto es especialmente valioso en discos que estan fallando, donde cada lectura puede ser la ultima. La implementacion es relativamente directa: se necesita un sistema de colas de prioridad que ordene los archivos encontrados segun las preferencias del usuario y un modulo de recuperacion que pueda trabajar en paralelo con el escaneo."
))

story.append(h2("7.2 Innovaciones con alto impacto pero mayor complejidad"))
story.append(p(
    "Existen innovaciones que tendrian un impacto transformador pero que requieren una inversion significativa en investigacion y desarrollo. La primera es la reconstruccion inteligente de archivos fragmentados usando IA. Los algoritmos de file carving actuales funcionan bien para archivos contiguos pero fallan con archivos fragmentados. Un modelo de aprendizaje automatico entrenado en millones de archivos podria aprender a predecir el orden correcto de los fragmentos basandose en las estructuras internas de los archivos, superando significativamente a los algoritmos heuristicos actuales. Sin embargo, la implementacion requiere un dataset de entrenamiento masivo (millones de archivos fragmentados con sus soluciones), lo que es dificil de obtener sin acceso a un laboratorio de recuperacion de datos."
))
story.append(p(
    "La segunda innovacion de alta complejidad es la reconstruccion de archivos danados usando IA generativa. Como se menciono anteriormente, la reconstruccion de imagenes JPEG con miniaturas intactas, la reparacion de archivos MP4 con atomos moov danados, y la reconstruccion de documentos de Office con estructura ZIP corrupta son problemas que la IA generativa podria abordar. Sin embargo, la implementacion requiere modelos especializados para cada tipo de archivo, lo que aumenta significativamente la complejidad y el costo de desarrollo. La tercera innovacion es la reconstruccion automatica de la estructura de carpetas original. Cuando el sistema de archivos esta danado, los archivos recuperados mediante file carving aparecen como una lista plana sin estructura de carpetas. Un algoritmo que pudiera reconstruir la estructura original basandose en pistas como las fechas de los archivos, los metadatos EXIF de las fotos, y los patrones de nomenclatura tendria un valor enorme para los usuarios."
))

story.append(h2("7.3 Lo que es puro marketing"))
story.append(p(
    "Es importante identificar las funcionalidades que los competidores promocionan como innovaciones pero que en realidad son caracteristicas de marketing con poco valor real. La primera es la 'recuperacion profunda' que promocionan EaseUS y Disk Drill: en la practica, la mayoria de los productos de recuperacion utilizan las mismas tecnicas fundamentales (escaneo por metadatos + file carving), y la diferencia entre un escaneo rapido y un escaneo profundo es simplemente el nivel de esfuerzo que el software dedica a buscar archivos, no una tecnica diferente. La segunda es la 'recuperacion de datos de dispositivos moviles' que muchas herramientas promocionan: en la practica, la recuperacion de datos de telefonos Android e iPhones esta severamente limitada por las restricciones del sistema operativo, y la mayoria de las herramientas solo pueden recuperar datos de la tarjeta SD o de copias de seguridad, no del almacenamiento interno del dispositivo."
))
story.append(p(
    "La tercera funcionalidad de marketing es la 'reparacion de videos' que ofrecen productos como Stellar y Wondershare Recoverit: en muchos casos, la 'reparacion' consiste simplemente en reconstruir los encabezados del contenedor MP4, lo que solo funciona si los datos de video estan intactos. Si los datos de video estan danados, la 'reparacion' no produce resultados utiles. La cuarta es la promocion de 'tasas de recuperacion del 99%' que algunas herramientas afirman: la tasa de recuperacion real depende enteramente de las condiciones del disco y del tipo de fallo, no del software, y ninguna herramienta puede garantizar una tasa de recuperacion del 99% en todos los escenarios. Un nuevo producto deberia ser honesto sobre sus limitaciones en lugar de hacer promesas exageradas, lo que en si mismo seria un diferenciador en un mercado donde la deshonestidad en el marketing es comun."
))

story.append(h2("7.4 Ventaja competitiva sostenible"))
story.append(p(
    "La pregunta mas importante para cualquier nuevo producto es: puede construir una ventaja competitiva que sea dificil de copiar? En el mercado de la recuperacion de datos, las barreras de entrada son relativamente bajas para las tecnicas fundamentales: el file carving, la recuperacion basada en metadatos y la reconstruccion de sistemas de archivos son tecnicas bien conocidas y documentadas. Sin embargo, hay varias areas donde si es posible construir una ventaja competitiva sostenible. La primera es la calidad del motor de recuperacion: implementar correctamente las tecnicas de reconstruccion de sistemas de archivos requiere anos de experiencia y miles de casos de prueba, y la diferencia entre una implementacion correcta y una incorrecta se manifiesta en tasas de recuperacion significativamente diferentes. La segunda es la base de datos de diagnostico: si el software recopila informacion anonima sobre los patrones de fallo de diferentes modelos de discos, puede mejorar continuamente sus diagnosticos y recomendaciones, creando un efecto de red que se fortalece con el tiempo."
))
story.append(p(
    "La tercera ventaja competitiva sostenible es la experiencia de usuario. Si bien la UX puede ser copiada, la combinacion de una interfaz intuitiva con un motor de recuperacion potente es dificil de replicar porque requiere que el equipo de desarrollo entienda tanto la recuperacion de datos como el diseno de producto. Ninguno de los competidores actuales ha logrado esta combinacion: las herramientas con buena interfaz (Disk Drill, EaseUS) tienen motores de recuperacion mediocres, y las herramientas con motores potentes (R-Studio, DMDE) tienen interfaces tecnicas. Un producto que combine ambos tendria una posicion unica en el mercado. La cuarta ventaja es la integracion del flujo de trabajo: si el software combina imagen de disco, diagnostico, recuperacion y reparacion de archivos en un solo producto, los usuarios no necesitan cambiar entre herramientas diferentes, lo que crea un ecosistema cerrado que es dificil de desplazar una vez adoptado."
))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BLOQUE 8: CONCLUSION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
story.append(h1("8. Conclusion: Vale la Pena?"))

story.append(h2("8.1 Veredicto: si, con condiciones"))
story.append(p(
    "Despues de analizar exhaustivamente el mercado, la competencia, la ingenieria, la ciencia y las oportunidades, la conclusion es que si existe una oportunidad real para construir un software de recuperacion de datos que sea significativamente mejor que los lideres del mercado, pero esta oportunidad viene con condiciones importantes. La primera condicion es que el producto debe ofrecer una mejora real en la tasa de recuperacion, no solo una interfaz mas bonita. Los profesionales y los usuarios avanzados pueden detectar rapidamente cuando un producto sacrifica potencia por estetica, y ningun producto puede tener exito a largo plazo si no ofrece resultados tangibles. La segunda condicion es que el equipo de desarrollo debe incluir al menos una persona con experiencia profunda en recuperacion de datos a bajo nivel: alguien que entienda como funcionan los sistemas de archivos a nivel de bytes, como se estructuran los discos a nivel de sectores, y como se implementan los algoritmos de recuperacion."
))
story.append(p(
    "La tercera condicion es que el producto debe abordar un hueco real del mercado, no una necesidad percibida. El analisis de la competencia muestra que los consumidores tienen herramientas con buena interfaz pero motores mediocres, mientras que los profesionales tienen herramientas con motores potentes pero interfaces deficientes. El hueco esta en el medio: un producto que ofrezca la potencia de R-Studio o DMDE con la accesibilidad de Disk Drill. La cuarta condicion es que el producto debe ser honesto sobre sus limitaciones. En un mercado donde la deshonestidad en el marketing es comun, la honestidad puede ser un diferenciador poderoso. Decirle al usuario 'este disco esta fisicamente danado, hay un 35% de riesgo de que empeore durante la lectura, te recomiendo crear primero una imagen completa' genera confianza y credibilidad, algo que ningun competidor esta haciendo hoy."
))

story.append(h2("8.2 Estimacion de inversion y equipo"))
story.append(p(
    "El desarrollo de un software de recuperacion de datos de calidad profesional requiere una inversion significativa, tanto en capital como en talento. El costo de desarrollo de un software personalizado de complejidad media-alta oscila entre $100.000 y $500.000, segun el nivel de funcionalidad y la calidad del equipo. Para un producto de recuperacion de datos que aspire a competir con los lideres del mercado, la inversion necesaria es probablemente de $200.000 a $400.000 para el primer ano de desarrollo, que incluye la creacion del motor de recuperacion, la interfaz de usuario, el modulo de diagnostico y las pruebas exhaustivas con diferentes sistemas de archivos y escenarios de fallo."
))
story.append(p(
    "El equipo minimo necesario incluye: un ingeniero de software con experiencia en recuperacion de datos a bajo nivel (la posicion mas critica y dificil de cubrir), un desarrollador de interfaces de usuario con experiencia en aplicaciones de escritorio, un ingeniero de IA si se planean funcionalidades de diagnostico inteligente o reconstruccion de archivos, y un experto en calidad que pueda crear y ejecutar pruebas exhaustivas. La dificultad principal es encontrar al ingeniero de recuperacion de datos: este es un nicho muy especializado, y las personas con esta experiencia son escasas y suelen estar empleadas por las empresas existentes. Una estrategia alternativa es contratar a un ingeniero de sistemas con experiencia en desarrollo de bajo nivel (kernel, drivers, filesystems) y capacitarlo en las tecnicas de recuperacion."
))

story.append(make_table(
    ["Concepto", "Rango de Inversion", "Notas"],
    [
        ["Equipo de desarrollo (4-5 personas, 12 meses)", "$150.000 - $300.000", "Incluye salarios, equipamiento, infraestructura"],
        ["Infraestructura de pruebas", "$20.000 - $50.000", "Discos de diferentes tipos, modelos y estados de danio"],
        ["Investigacion y desarrollo de IA", "$30.000 - $80.000", "Solo si se incluyen funcionalidades de IA"],
        ["Marketing y lanzamiento", "$30.000 - $60.000", "SEO, contenido, partnerships"],
        ["Legal y patentes", "$10.000 - $20.000", "Busqueda de patentes, registro de marca"],
        ["Total estimado (primer ano)", "$240.000 - $510.000", "Depende del alcance del MVP"],
    ],
    [2, 1.2, 2]
))
story.append(Paragraph("Tabla 4: Estimacion de inversion para el primer ano de desarrollo", caption_style))

story.append(h2("8.3 Modelo de ingresos proyectado"))
story.append(p(
    "El modelo de ingresos recomendado para un nuevo producto de recuperacion de datos es un modelo freemium con tres niveles de suscripcion, combinado con una licencia profesional para tecnicos. El nivel gratuito permite escanear y previsualizar archivos recuperables, pero limita la recuperacion a 500 MB, lo que es mas generoso que Disk Drill (100 MB) pero menos que EaseUS (2 GB). El nivel personal, a $69 anuales, permite recuperacion ilimitada para un usuario doméstico. El nivel profesional, a $149 anuales, agrega soporte para RAID, imagen de disco, diagnostico avanzado y priorizacion de recuperacion. La licencia para tecnicos, a $499 anuales, incluye todas las funciones mas soporte forense, API para automatizacion y soporte tecnico prioritario."
))
story.append(p(
    "Con este modelo de precios, y asumiendo un lanzamiento con buena visibilidad en el mercado, las proyecciones de ingresos son modestas pero realistas. El primer ano podria generar entre $50.000 y $150.000 en ingresos, dependiendo de la calidad del marketing y de la diferenciacion del producto. El segundo ano, con reseñas positivas y una base de usuarios creciente, los ingresos podrian alcanzar $200.000 - $500.000. El tercer ano, con el producto establecido y el efecto de las recomendaciones de boca a boca, los ingresos podrian llegar a $500.000 - $1.000.000. Estas proyecciones asumen que el producto realmente ofrece una ventaja significativa sobre la competencia y que la estrategia de marketing es efectiva. El punto de equilibrio se alcanzaria probablemente entre el mes 18 y el mes 30 despues del lanzamiento, dependiendo del nivel de inversion inicial."
))

story.append(make_table(
    ["Periodo", "Usuarios Pagos (est.)", "Ingresos Estimados", "Notas"],
    [
        ["Ano 1", "500 - 2.000", "$50.000 - $150.000", "Lanzamiento, adquisicion inicial"],
        ["Ano 2", "2.000 - 5.000", "$200.000 - $500.000", "Crecimiento organico, reseñas"],
        ["Ano 3", "5.000 - 10.000", "$500.000 - $1.000.000", "Base instalada, renovaciones"],
        ["Ano 4+", "10.000+", "$1.000.000+", "Escalabilidad, mercado empresarial"],
    ],
    [1, 1.2, 1.2, 1.5]
))
story.append(Paragraph("Tabla 5: Proyeccion de ingresos por suscripcion", caption_style))

story.append(h2("8.4 MVP realista"))
story.append(p(
    "El producto minimo viable (MVP) para validar la idea de un software de recuperacion de datos superior al mercado deberia enfocarse en tres capacidades diferenciadoras y ejecutarlas de manera impecable, en lugar de intentar ofrecer todas las funcionalidades de los competidores desde el primer dia. Las tres capacidades del MVP son: primero, un modulo de diagnostico inteligente que analice el disco antes de la recuperacion y recomiende la mejor estrategia; segundo, un sistema de checkpoints que permita reanudar escaneos interrumpidos; y tercero, una interfaz de usuario que priorice la honestidad y la claridad sobre las promesas exageradas. El motor de recuperacion del MVP debe soportar al menos NTFS, FAT32, exFAT, APFS y ext4, y debe ofrecer tanto recuperacion basada en metadatos como file carving basico."
))
story.append(p(
    "El MVP no necesita incluir funcionalidades de IA avanzada, reconstruccion de archivos danados, soporte para RAID, ni herramientas forenses. Estas funcionalidades se pueden agregar en versiones posteriores una vez que el motor de recuperacion basico haya demostrado su eficacia. El objetivo del MVP es validar que existe un mercado para un producto que 'piensa antes de actuar' y que es honesto con el usuario, no competir en funcionalidades con productos que tienen anos de desarrollo. Si el MVP logra una tasa de recuperacion comparable a DMDE o R-Studio en escenarios comunes (eliminacion accidental, formateo, corrupcion del sistema de archivos), y ofrece una experiencia de usuario significativamente mejor, entonces habra validado la hipotesis de que es posible construir un producto superior al mercado."
))

story.append(h2("8.5 Riesgos y mitigacion"))
story.append(p(
    "Los principales riesgos de este proyecto son: primero, la dificultad de encontrar talento con experiencia en recuperacion de datos a bajo nivel, que es un nicho muy especializado. La mitigacion es contratar ingenieros de sistemas con experiencia en desarrollo de bajo nivel y capacitarlos en las tecnicas de recuperacion. Segundo, el riesgo de que los competidores respondan rapidamente copiando las funcionalidades diferenciadoras. La mitigacion es construir una base de usuarios fiel antes de que los competidores puedan reaccionar, y enfocarse en la calidad del motor de recuperacion, que es dificil de replicar rapidamente. Tercero, el riesgo de que el mercado de recuperacion de datos se reduzca con la transicion a SSD y almacenamiento en la nube. La mitigacion es ofrecer un producto que aborde tanto la recuperacion de datos como la prevencion de perdidas (diagnostico, alertas, recomendaciones), posicionandose como un 'medico digital' para dispositivos de almacenamiento en lugar de un simple recuperador de archivos."
))
story.append(p(
    "En resumen, la investigacion concluye que existe una oportunidad real y significativa para construir un software de recuperacion de datos superior al mercado. La oportunidad no esta en inventar una tecnologia imposible, sino en combinar tecnicas de recuperacion ya conocidas con una experiencia de usuario muy superior, automatizacion inteligente y diagnostico previo. El hueco de mercado esta en la interseccion entre la potencia de las herramientas profesionales y la accesibilidad de las herramientas de consumo. Si se puede construir un producto que ocupe esa posicion, con un motor de recuperacion de calidad y una interfaz que priorice la honestidad y la claridad, entonces si vale la pena crear esta empresa. Si no se puede garantizar la calidad del motor de recuperacion, entonces es mejor no intentarlo, porque en este mercado los resultados hablan mas alto que el marketing."
))

# ━━ Build Document ━━
doc = SimpleDocTemplate(
    OUTPUT_PATH,
    pagesize=A4,
    leftMargin=LEFT_MARGIN,
    rightMargin=RIGHT_MARGIN,
    topMargin=TOP_MARGIN,
    bottomMargin=BOTTOM_MARGIN,
    title='Investigacion de Viabilidad - Software de Recuperacion de Datos',
    author='Z.ai',
    creator='Z.ai',
    subject='Analisis exhaustivo del mercado, la competencia y las oportunidades para construir un software de recuperacion de datos superior'
)

doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
print(f"PDF generated: {OUTPUT_PATH}")
