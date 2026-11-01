# Cargador Ecosearch (Well Log + Well Log Image)

Programa en Python con interfaz **CustomTkinter** que completa las dos plantillas de carga a Ecosearch
a partir de las plantillas de la plataforma (solo con los *Resource Path*) y de los `.las` del pozo.
La interfaz usa el mismo estilo de DATA INTEGRATION (marca teal de Bond, logo `LOGO BOND.png` junto a
`app.py`, solo modo claro).

## Instalación (VS Code)
```bash
python -m venv .venv
.venv\Scripts\activate          # Windows   (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
python app.py                   # abre la interfaz
```
En Linux, Tkinter puede requerir `sudo apt install python3-tk`.

## Uso
1. **Plantilla Well Log** y **Plantilla Well Log Image** (las que exporta la plataforma).
2. **.las del pozo**: de ahí salen Well Name, UWI, Datum (EKB) y el Step. Se leen solo los encabezados (no
   importa que pesen MB). Si no adjunta alguno, su Step se asume por tipo y queda avisado.
3. **ECP Transmittal** (cambia por pozo): escriba `1348` o use «Último de la hoja Ref».
4. **Service Type**: PRESION-TEMPERATURA, ILT, PRODUCCION-PLT, PLT, REGISTRO CORRELACION o
   REGISTRO MEMORIZADO (todos existen en la hoja `RefServiceType`).
5. **Validar / Vista previa** → revise las pestañas *Avisos*, *Well Log* y *Well Log Image*. Las dos
   últimas muestran **todas las columnas** de cada Excel (títulos de la fila 2). **Doble clic** en una
   celda la cambia (Enter guarda, Esc cancela; fechas en dd/mm/aaaa); la fila queda resaltada y el
   cambio se usa al generar y se anota en el reporte. Los cambios se conservan al volver a validar;
   *Descartar cambios* los borra.
6. **Generar plantillas** → crea `WL-template-external_delivery_WellLog_<POZO>.xlsx`,
   `...WellLogImage_<POZO>.xlsx` y `REPORTE_<POZO>.txt`.

Línea de comandos equivalente: `python cli.py --help`.

## Reglas que aplica
- **Well Log:** tope/base/unidad/MD-TIME/fecha salen del nombre del archivo (POOH descendente → Top = menor);
  dlis mixto (profundidad + tiempo) → TIME; Log Type PROCESSED; Well Type DEFINITIVO; PDAT
  `Rotary Table (RT)`; Null -999.25; Step del `.las` (si falta: TIME 1.0, UP -0.5, resto 0.5).
- **Well Log Image:** una fila por log; las imágenes se reparten en ciclo (ninguna sin uso); Well Log Filename
  = nombre del log; Scale `ESC200` → `ESC-200` validada contra `RefScale`; Drill 8.5, Casing 7.
- **Imágenes solo en tiempo** (nombre con `TIME`, p. ej. `..._0-300_S_TIME.pdf`, o con `ESC60`): Scale
  `ESC-60/TIME` (`time_scale` en `config.json`). Si la plantilla trae imágenes de profundidad y de
  tiempo, los logs TIME ciclan sobre las de tiempo y el resto sobre las de profundidad.
- **Log Run Date** siempre con el formato integrado **Fecha corta** de Excel (se ve dd/mm/aaaa en
  español).
- **Bloquea (error)** si las rutas de las plantillas son de otro pozo, si falta Well/UWI/Datum, si una escala no
  existe en `RefScale` o si un nombre de log no se puede interpretar.
- **Avisa** si STRT/STOP, fecha o RUN del `.las` difieren del nombre (se usa el nombre), si hay Step asumido, o si
  transmittal/pozo/UWI no están en las hojas Ref (el rojo de la plataforma no implica error).
- Las constantes están en `config.json`.

## Cuidado técnico importante
Las plantillas **no se regraban con openpyxl** (la plataforma no las lee si cambia el formato interno): se edita
directamente el XML de la hoja 1 y se reempaqueta el zip; solo cambia `sheet1.xml` (y `styles.xml` si falta el
estilo de fecha corta). Hojas Ref* y formato condicional se conservan (extendido a las filas nuevas).

## Pruebas
```bash
pytest
```
Regenera las plantillas de LIBERTAD NORTE-11 y las compara celda a celda con las de referencia.

## Crear un .exe (opcional)
`pip install pyinstaller` y
`pyinstaller --noconfirm --windowed --collect-all customtkinter --add-data "config.json;." --add-data "LOGO BOND.png;." app.py`
