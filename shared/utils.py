import re
from fpdf import FPDF
from datetime import datetime
import streamlit as st

def validate_email(email: str) -> bool:
    pattern = r'^[^@\s]+@[^@\s]+\.[^@\s]+$'
    return bool(re.match(pattern, email))

def format_currency(value) -> str:
    if value is None:
        return "S/ 0.00"
    return f"S/ {float(value):,.2f}"

def format_date(d) -> str:
    if d is None:
        return ""
    if isinstance(d, str):
        return d
    return d.strftime("%d/%m/%Y")

def generar_nro_contrato(correlativo: int) -> str:
    today = datetime.now().strftime("%Y%m%d")
    return f"CTR-{today}-{correlativo:03d}"

def paginate_dataframe(df, page_size=20):
    if df is None or len(df) == 0:
        return df, 1, 1

    total_pages = max(1, (len(df) + page_size - 1) // page_size)
    page = st.number_input("Página", min_value=1, max_value=total_pages, value=1, step=1)
    start = (page - 1) * page_size
    end = start + page_size
    st.caption(f"Mostrando {start + 1}–{min(end, len(df))} de {len(df)} registros | Página {page}/{total_pages}")
    return df.iloc[start:end], page, total_pages

def exportar_pdf(titulo, columnas, datos, filename="reporte.pdf"):
    """
    Genera un PDF con una tabla de datos.
    :param titulo: Título del reporte
    :param columnas: Lista de nombres de columnas
    :param datos: Lista de tuplas o listas con los datos
    :param filename: Nombre del archivo de descarga
    """
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, titulo, ln=True, align='C')
    pdf.ln(5)
    
    pdf.set_font("Arial", 'B', 10)
    # Calcular ancho de columnas (distribución equitativa para empezar)
    page_width = pdf.w - 2 * pdf.l_margin
    col_width = page_width / len(columnas)
    
    # Cabecera
    pdf.set_fill_color(200, 200, 200)
    for col in columnas:
        pdf.cell(col_width, 10, str(col), border=1, align='C', fill=True)
    pdf.ln()
    
    # Datos
    pdf.set_font("Arial", size=9)
    for row in datos:
        # Calcular altura necesaria para la fila (basado en el contenido más largo)
        row_height = 8
        for item in row:
            # Limpiar caracteres Unicode no soportados por fuentes estándar de FPDF
            clean_text = str(item).replace('\u2014', '-').replace('\u2013', '-')
            # Reemplazar otros caracteres comunes si es necesario
            clean_text = clean_text.encode('latin-1', 'replace').decode('latin-1')
            
            pdf.cell(col_width, row_height, clean_text[:30], border=1)
        pdf.ln()
        
    pdf_output = pdf.output(dest='S')
    # Manejar salida de fpdf (puede ser str o bytes dependiendo de la versión/config)
    if isinstance(pdf_output, str):
        pdf_bytes = pdf_output.encode('latin-1')
    else:
        pdf_bytes = bytes(pdf_output)
        
    return st.download_button(
        label="📄 Descargar en PDF",
        data=pdf_bytes,
        file_name=filename,
        mime="application/pdf",
        key=f"btn_pdf_{filename}"
    )
