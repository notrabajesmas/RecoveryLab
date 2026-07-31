# VAL-0001 — Validación Individual de Parsers

**Date**: 2026-07-30 22:32
**Protocol**: v1.5 | **Judge**: N/A
**Pregunta**: ¿Los parsers individuales funcionan correctamente?

---

## 1. Resumen por Formato

| Formato | Generados | Carved | Match Exacto | Truncados | Faltantes | FP | Tasa Match | Tasa Carve |
|---------|-----------|--------|-------------|-----------|-----------|-----|-----------|------------|
| JPEG | 100 | 53 | 1 | 50 | 99 | 52 | 1.00% | 53.00% |
| PNG | 100 | 71 | 70 | 0 | 30 | 1 | 70.00% | 71.00% |
| PDF | 100 | 81 | 0 | 80 | 100 | 81 | 0.00% | 81.00% |
| ZIP | 100 | 18 | 17 | 0 | 83 | 1 | 17.00% | 18.00% |
| DOCX | 100 | 41 | 40 | 0 | 60 | 1 | 40.00% | 41.00% |

## 2. Detalle por Formato

### JPEG

- Archivos generados: 100
- Archivos carved: 53
- Match exacto (SHA-256): 1
- Truncados: 50
- Faltantes: 99
- Falsos positivos: 52
- Firmas encontradas: {'JPEG': 99, 'BMP': 2}
- Tasa de match exacto: 1.00%
- Tasa de carve: 53.00%

**Detalle de falsos positivos/truncados:**

- `carved_0001.jpg` (size=63101): TRUNCATED — missing 865081 bytes (gt: `jpg_0001.jpg`, size=928182)
- `carved_0002.jpg` (size=206994): TRUNCATED — missing 923229 bytes (gt: `jpg_0002.jpg`, size=1130223)
- `carved_0001.bmp` (size=52428800): FALSE POSITIVE — no ground truth match
- `carved_0003.jpg` (size=4726): TRUNCATED — missing 141042 bytes (gt: `jpg_0033.jpg`, size=145768)
- `carved_0004.jpg` (size=44121): TRUNCATED — missing 1462162 bytes (gt: `jpg_0034.jpg`, size=1506283)
- `carved_0005.jpg` (size=117319): TRUNCATED — missing 2691528 bytes (gt: `jpg_0035.jpg`, size=2808847)
- `carved_0006.jpg` (size=38644): TRUNCATED — missing 2468090 bytes (gt: `jpg_0036.jpg`, size=2506734)
- `carved_0007.jpg` (size=493): TRUNCATED — missing 1386609 bytes (gt: `jpg_0037.jpg`, size=1387102)
- `carved_0008.jpg` (size=85835): TRUNCATED — missing 888916 bytes (gt: `jpg_0038.jpg`, size=974751)
- `carved_0009.jpg` (size=147544): TRUNCATED — missing 108706 bytes (gt: `jpg_0039.jpg`, size=256250)
- `carved_0010.jpg` (size=116001): TRUNCATED — missing 2211307 bytes (gt: `jpg_0040.jpg`, size=2327308)
- `carved_0011.jpg` (size=97547): TRUNCATED — missing 1957574 bytes (gt: `jpg_0041.jpg`, size=2055121)
- `carved_0012.jpg` (size=31094): TRUNCATED — missing 2776190 bytes (gt: `jpg_0042.jpg`, size=2807284)
- `carved_0013.jpg` (size=84166): TRUNCATED — missing 488588 bytes (gt: `jpg_0043.jpg`, size=572754)
- `carved_0014.jpg` (size=25295): TRUNCATED — missing 2301693 bytes (gt: `jpg_0044.jpg`, size=2326988)
- `carved_0015.jpg` (size=127259): TRUNCATED — missing 1779195 bytes (gt: `jpg_0045.jpg`, size=1906454)
- `carved_0016.jpg` (size=57004): TRUNCATED — missing 2856454 bytes (gt: `jpg_0046.jpg`, size=2913458)
- `carved_0017.jpg` (size=146657): TRUNCATED — missing 1847099 bytes (gt: `jpg_0047.jpg`, size=1993756)
- `carved_0018.jpg` (size=39966): TRUNCATED — missing 1812075 bytes (gt: `jpg_0048.jpg`, size=1852041)
- `carved_0019.jpg` (size=34628): TRUNCATED — missing 1349513 bytes (gt: `jpg_0049.jpg`, size=1384141)
- `carved_0020.jpg` (size=12230): TRUNCATED — missing 1245028 bytes (gt: `jpg_0050.jpg`, size=1257258)
- `carved_0021.jpg` (size=170657): TRUNCATED — missing 466504 bytes (gt: `jpg_0051.jpg`, size=637161)
- `carved_0022.jpg` (size=11509): TRUNCATED — missing 2860496 bytes (gt: `jpg_0052.jpg`, size=2872005)
- `carved_0023.jpg` (size=7064): TRUNCATED — missing 1295054 bytes (gt: `jpg_0053.jpg`, size=1302118)
- `carved_0024.jpg` (size=57247): TRUNCATED — missing 923189 bytes (gt: `jpg_0054.jpg`, size=980436)
- `carved_0025.jpg` (size=133816): TRUNCATED — missing 1474619 bytes (gt: `jpg_0055.jpg`, size=1608435)
- `carved_0026.jpg` (size=14200): TRUNCATED — missing 323453 bytes (gt: `jpg_0056.jpg`, size=337653)
- `carved_0027.jpg` (size=264950): TRUNCATED — missing 2597576 bytes (gt: `jpg_0057.jpg`, size=2862526)
- `carved_0028.jpg` (size=1617): TRUNCATED — missing 2082772 bytes (gt: `jpg_0058.jpg`, size=2084389)
- `carved_0029.jpg` (size=284850): TRUNCATED — missing 1649081 bytes (gt: `jpg_0059.jpg`, size=1933931)
- `carved_0030.jpg` (size=573): TRUNCATED — missing 2137871 bytes (gt: `jpg_0060.jpg`, size=2138444)
- `carved_0031.jpg` (size=215939): TRUNCATED — missing 2320525 bytes (gt: `jpg_0061.jpg`, size=2536464)
- `carved_0033.jpg` (size=136317): TRUNCATED — missing 893839 bytes (gt: `jpg_0063.jpg`, size=1030156)
- `carved_0034.jpg` (size=55991): TRUNCATED — missing 2300850 bytes (gt: `jpg_0064.jpg`, size=2356841)
- `carved_0035.jpg` (size=19435): TRUNCATED — missing 2013607 bytes (gt: `jpg_0066.jpg`, size=2033042)
- `carved_0036.jpg` (size=77820): TRUNCATED — missing 1080190 bytes (gt: `jpg_0067.jpg`, size=1158010)
- `carved_0037.jpg` (size=87212): TRUNCATED — missing 1987314 bytes (gt: `jpg_0068.jpg`, size=2074526)
- `carved_0038.jpg` (size=7288): TRUNCATED — missing 1121161 bytes (gt: `jpg_0069.jpg`, size=1128449)
- `carved_0039.jpg` (size=11108): TRUNCATED — missing 1366382 bytes (gt: `jpg_0070.jpg`, size=1377490)
- `carved_0040.jpg` (size=80860): TRUNCATED — missing 1709759 bytes (gt: `jpg_0071.jpg`, size=1790619)
- `carved_0041.jpg` (size=30711): TRUNCATED — missing 980170 bytes (gt: `jpg_0072.jpg`, size=1010881)
- `carved_0042.jpg` (size=24617): TRUNCATED — missing 2223745 bytes (gt: `jpg_0073.jpg`, size=2248362)
- `carved_0043.jpg` (size=156220): TRUNCATED — missing 345868 bytes (gt: `jpg_0074.jpg`, size=502088)
- `carved_0044.jpg` (size=122823): TRUNCATED — missing 2539642 bytes (gt: `jpg_0075.jpg`, size=2662465)
- `carved_0045.jpg` (size=54649): TRUNCATED — missing 2094015 bytes (gt: `jpg_0076.jpg`, size=2148664)
- `carved_0046.jpg` (size=7696): TRUNCATED — missing 2149262 bytes (gt: `jpg_0077.jpg`, size=2156958)
- `carved_0047.jpg` (size=98651): TRUNCATED — missing 2363448 bytes (gt: `jpg_0078.jpg`, size=2462099)
- `carved_0048.jpg` (size=124171): TRUNCATED — missing 958454 bytes (gt: `jpg_0079.jpg`, size=1082625)
- `carved_0049.jpg` (size=2405): TRUNCATED — missing 2940561 bytes (gt: `jpg_0080.jpg`, size=2942966)
- `carved_0050.jpg` (size=5375): TRUNCATED — missing 2736647 bytes (gt: `jpg_0081.jpg`, size=2742022)
- `carved_0051.jpg` (size=66499): TRUNCATED — missing 936193 bytes (gt: `jpg_0082.jpg`, size=1002692)
- `carved_0002.bmp` (size=52428800): FALSE POSITIVE — no ground truth match

### PNG

- Archivos generados: 100
- Archivos carved: 71
- Match exacto (SHA-256): 70
- Truncados: 0
- Faltantes: 30
- Falsos positivos: 1
- Firmas encontradas: {'PNG': 100, 'BMP': 2}
- Tasa de match exacto: 70.00%
- Tasa de carve: 71.00%

**Detalle de falsos positivos/truncados:**

- `carved_0001.bmp` (size=52428800): FALSE POSITIVE — no ground truth match

### PDF

- Archivos generados: 100
- Archivos carved: 81
- Match exacto (SHA-256): 0
- Truncados: 80
- Faltantes: 100
- Falsos positivos: 81
- Firmas encontradas: {'PDF': 100, 'BMP': 1}
- Tasa de match exacto: 0.00%
- Tasa de carve: 81.00%

**Detalle de falsos positivos/truncados:**

- `carved_0001.pdf` (size=480667): TRUNCATED — missing 1 bytes (gt: `pdf_0001.pdf`, size=480668)
- `carved_0002.pdf` (size=458351): TRUNCATED — missing 1 bytes (gt: `pdf_0002.pdf`, size=458352)
- `carved_0003.pdf` (size=321714): TRUNCATED — missing 1 bytes (gt: `pdf_0003.pdf`, size=321715)
- `carved_0004.pdf` (size=306333): TRUNCATED — missing 1 bytes (gt: `pdf_0004.pdf`, size=306334)
- `carved_0005.pdf` (size=415175): TRUNCATED — missing 1 bytes (gt: `pdf_0005.pdf`, size=415176)
- `carved_0006.pdf` (size=184957): TRUNCATED — missing 1 bytes (gt: `pdf_0006.pdf`, size=184958)
- `carved_0007.pdf` (size=373574): TRUNCATED — missing 1 bytes (gt: `pdf_0007.pdf`, size=373575)
- `carved_0008.pdf` (size=410961): TRUNCATED — missing 1 bytes (gt: `pdf_0008.pdf`, size=410962)
- `carved_0009.pdf` (size=143063): TRUNCATED — missing 1 bytes (gt: `pdf_0009.pdf`, size=143064)
- `carved_0010.pdf` (size=475343): TRUNCATED — missing 1 bytes (gt: `pdf_0010.pdf`, size=475344)
- `carved_0011.pdf` (size=152498): TRUNCATED — missing 1 bytes (gt: `pdf_0011.pdf`, size=152499)
- `carved_0012.pdf` (size=383545): TRUNCATED — missing 1 bytes (gt: `pdf_0012.pdf`, size=383546)
- `carved_0013.pdf` (size=96836): TRUNCATED — missing 1 bytes (gt: `pdf_0013.pdf`, size=96837)
- `carved_0014.pdf` (size=435962): TRUNCATED — missing 1 bytes (gt: `pdf_0014.pdf`, size=435963)
- `carved_0015.pdf` (size=312950): TRUNCATED — missing 1 bytes (gt: `pdf_0015.pdf`, size=312951)
- `carved_0016.pdf` (size=100266): TRUNCATED — missing 1 bytes (gt: `pdf_0016.pdf`, size=100267)
- `carved_0017.pdf` (size=113276): TRUNCATED — missing 1 bytes (gt: `pdf_0017.pdf`, size=113277)
- `carved_0018.pdf` (size=305956): TRUNCATED — missing 1 bytes (gt: `pdf_0018.pdf`, size=305957)
- `carved_0019.pdf` (size=185067): TRUNCATED — missing 1 bytes (gt: `pdf_0019.pdf`, size=185068)
- `carved_0020.pdf` (size=178525): TRUNCATED — missing 1 bytes (gt: `pdf_0020.pdf`, size=178526)
- `carved_0021.pdf` (size=437431): TRUNCATED — missing 1 bytes (gt: `pdf_0021.pdf`, size=437432)
- `carved_0022.pdf` (size=213812): TRUNCATED — missing 1 bytes (gt: `pdf_0022.pdf`, size=213813)
- `carved_0023.pdf` (size=74081): TRUNCATED — missing 1 bytes (gt: `pdf_0023.pdf`, size=74082)
- `carved_0024.pdf` (size=133143): TRUNCATED — missing 1 bytes (gt: `pdf_0024.pdf`, size=133144)
- `carved_0025.pdf` (size=249940): TRUNCATED — missing 1 bytes (gt: `pdf_0025.pdf`, size=249941)
- `carved_0026.pdf` (size=313358): TRUNCATED — missing 1 bytes (gt: `pdf_0026.pdf`, size=313359)
- `carved_0027.pdf` (size=350271): TRUNCATED — missing 1 bytes (gt: `pdf_0027.pdf`, size=350272)
- `carved_0028.pdf` (size=447253): TRUNCATED — missing 1 bytes (gt: `pdf_0028.pdf`, size=447254)
- `carved_0029.pdf` (size=454129): TRUNCATED — missing 1 bytes (gt: `pdf_0029.pdf`, size=454130)
- `carved_0030.pdf` (size=346401): TRUNCATED — missing 1 bytes (gt: `pdf_0030.pdf`, size=346402)
- `carved_0031.pdf` (size=210657): TRUNCATED — missing 1 bytes (gt: `pdf_0031.pdf`, size=210658)
- `carved_0032.pdf` (size=231872): TRUNCATED — missing 1 bytes (gt: `pdf_0032.pdf`, size=231873)
- `carved_0033.pdf` (size=12970): TRUNCATED — missing 1 bytes (gt: `pdf_0033.pdf`, size=12971)
- `carved_0034.pdf` (size=183034): TRUNCATED — missing 1 bytes (gt: `pdf_0034.pdf`, size=183035)
- `carved_0035.pdf` (size=345854): TRUNCATED — missing 1 bytes (gt: `pdf_0035.pdf`, size=345855)
- `carved_0036.pdf` (size=308090): TRUNCATED — missing 1 bytes (gt: `pdf_0036.pdf`, size=308091)
- `carved_0037.pdf` (size=168136): TRUNCATED — missing 1 bytes (gt: `pdf_0037.pdf`, size=168137)
- `carved_0038.pdf` (size=116592): TRUNCATED — missing 1 bytes (gt: `pdf_0038.pdf`, size=116593)
- `carved_0039.pdf` (size=26780): TRUNCATED — missing 1 bytes (gt: `pdf_0039.pdf`, size=26781)
- `carved_0040.pdf` (size=285662): TRUNCATED — missing 1 bytes (gt: `pdf_0040.pdf`, size=285663)
- `carved_0041.pdf` (size=251639): TRUNCATED — missing 1 bytes (gt: `pdf_0041.pdf`, size=251640)
- `carved_0042.pdf` (size=345659): TRUNCATED — missing 1 bytes (gt: `pdf_0042.pdf`, size=345660)
- `carved_0043.pdf` (size=66343): TRUNCATED — missing 1 bytes (gt: `pdf_0043.pdf`, size=66344)
- `carved_0044.pdf` (size=389196): TRUNCATED — missing 1 bytes (gt: `pdf_0044.pdf`, size=389197)
- `carved_0045.pdf` (size=440203): TRUNCATED — missing 1 bytes (gt: `pdf_0045.pdf`, size=440204)
- `carved_0046.pdf` (size=474012): TRUNCATED — missing 1 bytes (gt: `pdf_0046.pdf`, size=474013)
- `carved_0047.pdf` (size=243968): TRUNCATED — missing 1 bytes (gt: `pdf_0047.pdf`, size=243969)
- `carved_0048.pdf` (size=226254): TRUNCATED — missing 1 bytes (gt: `pdf_0048.pdf`, size=226255)
- `carved_0049.pdf` (size=167766): TRUNCATED — missing 1 bytes (gt: `pdf_0049.pdf`, size=167767)
- `carved_0050.pdf` (size=151906): TRUNCATED — missing 1 bytes (gt: `pdf_0050.pdf`, size=151907)
- `carved_0051.pdf` (size=74394): TRUNCATED — missing 1 bytes (gt: `pdf_0051.pdf`, size=74395)
- `carved_0052.pdf` (size=427763): TRUNCATED — missing 1 bytes (gt: `pdf_0052.pdf`, size=427764)
- `carved_0053.pdf` (size=157513): TRUNCATED — missing 1 bytes (gt: `pdf_0053.pdf`, size=157514)
- `carved_0054.pdf` (size=117303): TRUNCATED — missing 1 bytes (gt: `pdf_0054.pdf`, size=117304)
- `carved_0055.pdf` (size=195803): TRUNCATED — missing 1 bytes (gt: `pdf_0055.pdf`, size=195804)
- `carved_0056.pdf` (size=36955): TRUNCATED — missing 1 bytes (gt: `pdf_0056.pdf`, size=36956)
- `carved_0057.pdf` (size=401478): TRUNCATED — missing 1 bytes (gt: `pdf_0057.pdf`, size=401479)
- `carved_0058.pdf` (size=255297): TRUNCATED — missing 1 bytes (gt: `pdf_0058.pdf`, size=255298)
- `carved_0059.pdf` (size=236490): TRUNCATED — missing 1 bytes (gt: `pdf_0059.pdf`, size=236491)
- `carved_0060.pdf` (size=262054): TRUNCATED — missing 1 bytes (gt: `pdf_0060.pdf`, size=262055)
- `carved_0061.pdf` (size=311807): TRUNCATED — missing 1 bytes (gt: `pdf_0061.pdf`, size=311808)
- `carved_0062.pdf` (size=5727): TRUNCATED — missing 1 bytes (gt: `pdf_0062.pdf`, size=5728)
- `carved_0063.pdf` (size=123518): TRUNCATED — missing 1 bytes (gt: `pdf_0063.pdf`, size=123519)
- `carved_0064.pdf` (size=289354): TRUNCATED — missing 1 bytes (gt: `pdf_0064.pdf`, size=289355)
- `carved_0065.pdf` (size=115230): TRUNCATED — missing 1 bytes (gt: `pdf_0065.pdf`, size=115231)
- `carved_0066.pdf` (size=248879): TRUNCATED — missing 1 bytes (gt: `pdf_0066.pdf`, size=248880)
- `carved_0067.pdf` (size=139500): TRUNCATED — missing 1 bytes (gt: `pdf_0067.pdf`, size=139501)
- `carved_0068.pdf` (size=254064): TRUNCATED — missing 1 bytes (gt: `pdf_0068.pdf`, size=254065)
- `carved_0069.pdf` (size=135805): TRUNCATED — missing 1 bytes (gt: `pdf_0069.pdf`, size=135806)
- `carved_0070.pdf` (size=166935): TRUNCATED — missing 1 bytes (gt: `pdf_0070.pdf`, size=166936)
- `carved_0071.pdf` (size=218576): TRUNCATED — missing 1 bytes (gt: `pdf_0071.pdf`, size=218577)
- `carved_0072.pdf` (size=475915): TRUNCATED — missing 1 bytes (gt: `pdf_0072.pdf`, size=475916)
- `carved_0073.pdf` (size=275794): TRUNCATED — missing 1 bytes (gt: `pdf_0073.pdf`, size=275795)
- `carved_0074.pdf` (size=57510): TRUNCATED — missing 1 bytes (gt: `pdf_0074.pdf`, size=57511)
- `carved_0075.pdf` (size=379509): TRUNCATED — missing 1 bytes (gt: `pdf_0075.pdf`, size=379510)
- `carved_0076.pdf` (size=263332): TRUNCATED — missing 1 bytes (gt: `pdf_0076.pdf`, size=263333)
- `carved_0077.pdf` (size=396335): TRUNCATED — missing 1 bytes (gt: `pdf_0077.pdf`, size=396336)
- `carved_0078.pdf` (size=450416): TRUNCATED — missing 1 bytes (gt: `pdf_0078.pdf`, size=450417)
- `carved_0079.pdf` (size=130077): TRUNCATED — missing 1 bytes (gt: `pdf_0079.pdf`, size=130078)
- `carved_0080.pdf` (size=362619): TRUNCATED — missing 1 bytes (gt: `pdf_0080.pdf`, size=362620)
- `carved_0001.bmp` (size=52428800): FALSE POSITIVE — no ground truth match

### ZIP

- Archivos generados: 100
- Archivos carved: 18
- Match exacto (SHA-256): 17
- Truncados: 0
- Faltantes: 83
- Falsos positivos: 1
- Firmas encontradas: {'ZIP': 100, 'DOCX': 100, 'XLSX': 100, 'BMP': 2}
- Tasa de match exacto: 17.00%
- Tasa de carve: 18.00%

**Detalle de falsos positivos/truncados:**

- `carved_0001.bmp` (size=52428800): FALSE POSITIVE — no ground truth match

### DOCX

- Archivos generados: 100
- Archivos carved: 41
- Match exacto (SHA-256): 40
- Truncados: 0
- Faltantes: 60
- Falsos positivos: 1
- Firmas encontradas: {'ZIP': 100, 'DOCX': 100, 'XLSX': 100, 'BMP': 2}
- Tasa de match exacto: 40.00%
- Tasa de carve: 41.00%

**Detalle de falsos positivos/truncados:**

- `carved_0001.bmp` (size=52428800): FALSE POSITIVE — no ground truth match

## 3. Observación Pura (para Evidence Ledger)

> En VAL-0001, bajo las condiciones evaluadas (100 archivos por formato,
> sin corrupción, sin Judge, Protocol v1.5),
> los parsers de carving produjeron:
>
> - JPEG: 1/100 match exacto, 53 carved, 99 faltantes, 52 FP
> - PNG: 70/100 match exacto, 71 carved, 30 faltantes, 1 FP
> - PDF: 0/100 match exacto, 81 carved, 100 faltantes, 81 FP
> - ZIP: 17/100 match exacto, 18 carved, 83 faltantes, 1 FP
> - DOCX: 40/100 match exacto, 41 carved, 60 faltantes, 1 FP
>
> Esta es una observación pura. No contiene interpretación.

## 4. Referencia Cruzada con DIAG-0001

| Formato | DIAG-0001 OU | VAL-0001 Match Rate | Consistente? |
|---------|-------------|--------------------:|:------------:|
| JPEG | 0.0 | 1.00% | Si |
| PNG | 0.8709 | 70.00% | Si |
| PDF | 0.0 | 0.00% | Si |
| ZIP | 1.0 | 17.00% | Verificar |
| DOCX | 1.0 | 40.00% | Verificar |

## 5. Notas Metodológicas

- **No se uso Judge**: Este experimento valida parsers, no motores.
- **No se uso corrupcion**: Los archivos estan intactos en la imagen.
- **No se uso MFT**: El parser de carving no accede al MFT por diseno.
- **No se uso RVS/FQS**: No hay scoring de valor o calidad.
- **No hay hipotesis**: Este experimento solo observa, no interpreta.
- **Observacion pura**: Los resultados son hechos, no conclusiones.
- **N=100 por formato**: Mas archivos que DIAG-0001 (N=15) para mayor confianza estadistica.

*Experiment ID: VAL-0001 | Protocol: v1.5 | Judge: N/A*