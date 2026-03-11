"""
CU4 – Gestionar Ejecución y Cierre del Evento
===============================================
Actor principal: Jefe de Eventos

Funcionalidades:
  1. Registrar estado de evento
  2. Registrar cumplimiento de servicios contratados
  3. Registrar estado de los recursos
  4. Registrar incidencia  (+extend: Generar reporte PDF)
  5. Registrar encuesta de satisfacción
  «include» transversal: Seleccionar cliente → evento (combobox)
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date
from fpdf import FPDF

from auth.roles import requiere_rol
from cu4_ejecucion import model_incidencia, model_encuesta
from cu2_planificacion import model_evento
from cu1_contratos import model_contrato, model_cliente
from cu3_recursos import model_asignacion
from shared.utils import format_currency
from database.connection import execute_query

# ─── Máquina de estados del evento ───────────────────────────
TRANSICIONES_ESTADO = {
    "Registrada":        ["En Planificación", "Cancelada"],
    "En Planificación":  ["Plan Aprobado", "Cancelada"],
    "Plan Aprobado":     ["Confirmada", "Cancelada"],
    "Confirmada":        ["En Ejecución", "Cancelada"],
    "En Ejecución":      ["Cerrada"],
}

BADGE_ESTADO = {
    "Registrada": "🔵", "En Planificación": "🟡", "Plan Aprobado": "🟠",
    "Confirmada": "🟣", "En Ejecución": "🟢", "Cerrada": "⚫", "Cancelada": "🔴",
}

BADGE_INC = {
    "Abierta": "🔴", "En Proceso": "🟡", "Resuelta": "🟢", "Cerrada": "⚫",
}

STAR_OPTIONS = ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"]
STAR_TO_INT  = {"⭐": 1, "⭐⭐": 2, "⭐⭐⭐": 3, "⭐⭐⭐⭐": 4, "⭐⭐⭐⭐⭐": 5}


def show():
    requiere_rol(["Administrador", "Jefe de Eventos"])
    st.title("🚀 Ejecución y Cierre de Eventos")

    # ── Selector global: Cliente → Evento ────────────────────
    id_cliente, id_ev, ev = _selector_contexto()
    if id_ev is None:
        return

    # ── Ficha informativa del evento ─────────────────────────
    _ficha_evento(ev)
    st.divider()

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📌 Estado del Evento",
        "✅ Cumplimiento de Servicios",
        "📦 Estado de Recursos",
        "🔥 Incidencias",
        "⭐ Encuesta de Satisfacción",
    ])

    with tab1:
        _tab_estado_evento(id_ev, ev)
    with tab2:
        _tab_cumplimiento_servicios(id_ev)
    with tab3:
        _tab_estado_recursos(id_ev)
    with tab4:
        _tab_incidencias(id_ev, ev[1])
    with tab5:
        _tab_encuestas(id_ev, ev)


# ══════════════════════════════════════════════════════════════
# SELECTOR GLOBAL: Cliente → Evento (combobox)
# ══════════════════════════════════════════════════════════════

def _selector_contexto():
    """
    Muestra dos combobox en columnas:
      1. Cliente (carga todos los clientes activos)
      2. Evento  (carga los eventos del cliente seleccionado)
    Devuelve (id_cliente, id_evento, ev_tuple) o (None, None, None).
    """
    clientes = model_cliente.get_all()
    # get_all devuelve: (id_cliente, nombre, tipo_cliente, direccion, email, telefono, fecha_registro, estado)
    opciones_cli = {f"{c[1]}  —  {c[2]}": c[0] for c in clientes}
    lista_cli = ["— Selecciona un cliente —"] + list(opciones_cli.keys())

    col1, col2 = st.columns(2)
    sel_cli = col1.selectbox("👤 Cliente", lista_cli, key="ctx_cliente")

    if sel_cli == "— Selecciona un cliente —":
        col2.info("Selecciona un cliente para ver sus eventos.")
        return None, None, None

    id_cliente = opciones_cli[sel_cli]

    # Todos los eventos del cliente (sin filtro de estado)
    eventos = execute_query(
        "SELECT id_evento, nombre, estado FROM eventos WHERE id_cliente = %s ORDER BY fecha_evento DESC",
        (id_cliente,)
    ) or []

    if not eventos:
        col2.warning("Este cliente no tiene eventos registrados.")
        return id_cliente, None, None

    opciones_ev = {f"{e[1]}  [{BADGE_ESTADO.get(e[2], '⚪')} {e[2]}]": e[0] for e in eventos}
    sel_ev = col2.selectbox("📅 Evento", list(opciones_ev.keys()), key="ctx_evento")
    id_ev = opciones_ev[sel_ev]

    ev = model_evento.get_by_id(id_ev)
    return id_cliente, id_ev, ev


# ─── Ficha readonly del evento ────────────────────────────────

def _ficha_evento(ev):
    """Tarjeta informativa del evento. Solo lectura."""
    # ev = (id, nombre, tipo, lugar, fecha, monto, estado, id_cliente)
    estado = ev[6]
    badge = BADGE_ESTADO.get(estado, "⚪")
    with st.container(border=True):
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📋 Tipo", ev[2] or "—")
        col2.metric("📍 Lugar", ev[3] or "—")
        col3.metric("📅 Fecha", str(ev[4]) if ev[4] else "—")
        col4.metric("💰 Monto", format_currency(ev[5]))
        st.markdown(f"**Estado actual:** {badge} **{estado}**")


# ══════════════════════════════════════════════════════════════
# TAB 1 — Registrar estado de evento
# ══════════════════════════════════════════════════════════════

def _tab_estado_evento(id_ev, ev):
    st.subheader("📌 Cambiar Estado del Evento")

    estado_actual = ev[6]
    posibles = TRANSICIONES_ESTADO.get(estado_actual, [])

    if not posibles:
        st.success(
            f"El evento ya se encuentra en estado final: "
            f"{BADGE_ESTADO.get(estado_actual, '⚪')} **{estado_actual}**."
        )
        return

    st.info(
        f"Estado actual: {BADGE_ESTADO.get(estado_actual, '⚪')} **{estado_actual}**  "
        f"→  Puedes avanzar a: **{' / '.join(posibles)}**"
    )

    col1, col2 = st.columns([3, 1])
    nuevo_estado = col1.selectbox("Nuevo estado", posibles, key="nuevo_est_ev")
    if col2.button("💾 Actualizar", key="btn_est_ev", use_container_width=True):
        if model_evento.cambiar_estado(id_ev, nuevo_estado):
            st.success(f"Estado actualizado a {BADGE_ESTADO.get(nuevo_estado, '')} **{nuevo_estado}**.")
            st.rerun()


# ══════════════════════════════════════════════════════════════
# TAB 2 — Cumplimiento de servicios contratados
# ══════════════════════════════════════════════════════════════

def _tab_cumplimiento_servicios(id_ev):
    st.subheader("✅ Contratos del Evento")

    contratos = model_contrato.get_by_evento(id_ev)
    if not contratos:
        st.info("Este evento no tiene contratos registrados.")
        return

    df = pd.DataFrame(contratos, columns=["ID", "Nro. Contrato", "Estado", "Monto", "Firma Digital"])
    df["Monto"] = df["Monto"].apply(format_currency)
    df["Firma Digital"] = df["Firma Digital"].map({True: "✅ Sí", False: "❌ No"})
    st.dataframe(df, use_container_width=True, hide_index=True)

    contratos_nc = [c for c in contratos if c[2] != "Cumplido"]
    if not contratos_nc:
        st.success("✅ Todos los contratos ya están marcados como cumplidos.")
        return

    st.divider()
    st.markdown("**Confirmar cumplimiento de un contrato:**")
    opciones_ct = {f"{c[1]}  —  Estado: {c[2]}": c[0] for c in contratos_nc}
    col1, col2 = st.columns([4, 1])
    ct_sel = col1.selectbox("Contrato", list(opciones_ct.keys()), key="ct_cum")
    id_ct = opciones_ct[ct_sel]
    if col2.button("✅ Confirmar", key="btn_cum_ct", use_container_width=True):
        if model_contrato.confirmar_cumplimiento(id_ct):
            st.success("Cumplimiento del contrato registrado.")
            st.rerun()


# ══════════════════════════════════════════════════════════════
# TAB 3 — Estado de los recursos
# ══════════════════════════════════════════════════════════════

def _tab_estado_recursos(id_ev):
    st.subheader("📦 Recursos Asignados al Evento")

    asignaciones = model_asignacion.get_by_evento(id_ev)
    if not asignaciones:
        st.info("No hay recursos asignados a este evento.")
        return

    # asignaciones: (id_asignacion, nombre_recurso, cantidad, fecha_asig, estado)
    df = pd.DataFrame(asignaciones, columns=["ID Asig.", "Recurso", "Cantidad", "Fecha Asig.", "Estado"])
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("**Actualizar estado de una asignación:**")
    opciones_as = {f"{a[1]}  (Cant: {a[2]})  —  {a[4]}": a[0] for a in asignaciones}
    col1, col2, col3 = st.columns([3, 2, 1])
    as_sel = col1.selectbox("Asignación", list(opciones_as.keys()), key="as_rec")
    id_asig = opciones_as[as_sel]
    nuevo_est_as = col2.selectbox("Nuevo estado", ["Pendiente", "Confirmada", "Cancelada"], key="nuevo_est_as")
    if col3.button("💾 Guardar", key="btn_est_rec", use_container_width=True):
        if model_asignacion.cambiar_estado(id_asig, nuevo_est_as):
            st.success(f"Estado actualizado a **{nuevo_est_as}**.")
            st.rerun()


# ══════════════════════════════════════════════════════════════
# TAB 4 — Incidencias (CRUD completo)
# ══════════════════════════════════════════════════════════════

def _tab_incidencias(id_ev, nombre_ev):

    # ─────────────────────────────────────────────────────────
    # SECCIÓN A — Listado de incidencias
    # ─────────────────────────────────────────────────────────
    st.subheader("🔥 Incidencias del Evento")
    incidencias = model_incidencia.get_by_evento(id_ev)

    if incidencias:
        df_inc = pd.DataFrame(
            incidencias,
            columns=["ID", "Tipo", "Descripción", "Fecha Registro", "Estado"]
        )
        st.dataframe(df_inc, use_container_width=True, hide_index=True)

        # ─────────────────────────────────────────────────────
        # SECCIÓN B — Reporte PDF
        # ─────────────────────────────────────────────────────
        st.divider()
        pdf_bytes = _generar_pdf_incidencias(id_ev, nombre_ev, incidencias)
        st.download_button(
            "📄 Descargar Reporte de Incidencias (PDF)",
            data=pdf_bytes,
            file_name=f"incidencias_evento_{id_ev}.pdf",
            mime="application/pdf",
            key="dl_pdf_inc",
        )
    else:
        st.info("No hay incidencias registradas para este evento.")

    # ─────────────────────────────────────────────────────────
    # SECCIÓN D — Registrar nueva incidencia
    # ─────────────────────────────────────────────────────────
    st.divider()
    st.markdown("#### ➕ Registrar Nueva Incidencia")
    with st.form("form_nueva_inc"):
        col1, col2 = st.columns(2)
        tipo_inc = col1.selectbox("Tipo de incidencia", model_incidencia.TIPOS_INCIDENCIA)
        desc_inc = st.text_area("Descripción de la incidencia *")
        desc_det_ini = st.text_area("Detalle inicial / Acción tomada (opcional)")
        if st.form_submit_button("✅ Registrar Incidencia"):
            if not desc_inc.strip():
                st.error("La descripción es obligatoria.")
            else:
                id_nueva = model_incidencia.create(id_ev, tipo_inc, desc_inc)
                if id_nueva:
                    if desc_det_ini.strip():
                        model_incidencia.create_detalle(id_nueva, desc_inc, desc_det_ini)
                    st.success("Incidencia registrada exitosamente.")
                    st.rerun()


# ══════════════════════════════════════════════════════════════
# TAB 5 — Encuesta de satisfacción
# ══════════════════════════════════════════════════════════════

def _tab_encuestas(id_ev, ev):
    st.subheader("⭐ Encuesta de Satisfacción del Evento")

    estado_ev      = ev[6] if ev else "—"
    cliente        = model_cliente.get_by_id(ev[7]) if ev else None
    nombre_cliente = cliente[1] if cliente else "—"

    # ── Encuestas existentes ──────────────────────────────────
    encuestas_ev = model_encuesta.get_by_evento(id_ev)
    if encuestas_ev:
        df_enc = pd.DataFrame(
            encuestas_ev,
            columns=["ID", "Fecha", "Satisfacción (1-5)", "Estado", "Comentarios"]
        )
        st.dataframe(df_enc, use_container_width=True, hide_index=True)

        opciones_enc = {f"Encuesta #{e[0]}  —  {e[3]}": e[0] for e in encuestas_ev}
        enc_sel = st.selectbox("Ver detalle de encuesta", list(opciones_enc.keys()), key="sel_enc_det")
        id_enc  = opciones_enc[enc_sel]

        detalles_enc = model_encuesta.get_detalles(id_enc)
        if detalles_enc:
            dimensiones = [d[1] for d in detalles_enc]
            valores     = [d[2] for d in detalles_enc]
            colores_bar = ["#4C78A8", "#72B7B2", "#54A24B", "#EECA3B"]

            fig = go.Figure(go.Bar(
                x=valores,
                y=dimensiones,
                orientation="h",
                marker_color=colores_bar[:len(dimensiones)],
                text=[f"{v}/5  {'⭐' * v}" for v in valores],
                textposition="inside",
                textfont=dict(size=12, color="white"),
            ))
            fig.update_layout(
                title="Evaluación de Satisfacción por Dimensión",
                xaxis=dict(range=[0, 5], tickvals=[0, 1, 2, 3, 4, 5], title="Puntuación"),
                yaxis=dict(title=""),
                height=280,
                margin=dict(l=10, r=10, t=50, b=20),
            )
            prom = sum(valores) / len(valores)
            col_g, col_m = st.columns([4, 1])
            col_g.plotly_chart(fig, use_container_width=True)
            col_m.metric("Promedio", f"{prom:.1f} / 5")
            col_m.markdown("⭐" * round(prom))

            # PDF de encuesta
            enc_data = model_encuesta.get_by_id(id_enc)
            pdf_enc  = _generar_pdf_encuesta(id_ev, ev[1], nombre_cliente, enc_data, detalles_enc)
            st.download_button(
                "📄 Descargar Reporte de Encuesta (PDF)",
                data=pdf_enc,
                file_name=f"encuesta_{id_ev}_{id_enc}.pdf",
                mime="application/pdf",
                key="dl_pdf_enc",
            )

    # ── Nueva encuesta ────────────────────────────────────────
    st.divider()
    if estado_ev not in ("En Ejecución", "Cerrada"):
        st.warning(
            f"Solo se pueden registrar encuestas para eventos en estado "
            f"**En Ejecución** o **Cerrada**. Estado actual: "
            f"{BADGE_ESTADO.get(estado_ev, '⚪')} **{estado_ev}**."
        )
        return

    st.markdown("#### ➕ Registrar Nueva Encuesta")
    with st.form("form_nueva_enc"):
        col1, col2 = st.columns(2)
        fecha_enc      = col1.date_input("Fecha de evaluación", value=date.today())
        nivel_gen_star = col2.select_slider(
            "Satisfacción general", options=STAR_OPTIONS, value="⭐⭐⭐⭐"
        )
        nivel_gen   = STAR_TO_INT[nivel_gen_star]
        comentarios = st.text_area("Comentarios generales")

        st.markdown("**Evaluación por dimensión:**")
        cols_dim   = st.columns(len(model_encuesta.DIMENSIONES))
        respuestas = {}
        for i, dim in enumerate(model_encuesta.DIMENSIONES):
            star_sel        = cols_dim[i].select_slider(dim, options=STAR_OPTIONS, value="⭐⭐⭐⭐", key=f"dim_{i}")
            respuestas[dim] = STAR_TO_INT[star_sel]

        if st.form_submit_button("✅ Guardar Encuesta"):
            id_enc_nuevo = model_encuesta.create(id_ev, fecha_enc, nivel_gen, comentarios)
            if id_enc_nuevo:
                for dim, resp in respuestas.items():
                    model_encuesta.create_detalle(id_enc_nuevo, dim, resp)
                model_encuesta.completar_encuesta(id_enc_nuevo)
                st.success("Encuesta de satisfacción registrada y completada.")
                st.rerun()


# ══════════════════════════════════════════════════════════════
# PDF — Reporte de Incidencias
# ══════════════════════════════════════════════════════════════

def _generar_pdf_incidencias(id_evento, nombre_evento, incidencias):
    """Reporte PDF de incidencias con diseño mejorado."""
    pdf = FPDF()
    pdf.set_margins(15, 15, 15)
    pdf.add_page()
    lm = pdf.l_margin
    pw = pdf.w - pdf.l_margin - pdf.r_margin

    # ── Encabezado ────────────────────────────────────────────
    pdf.set_fill_color(30, 80, 140)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_x(lm)
    pdf.cell(pw, 14, "REPORTE DE INCIDENCIAS", ln=True, align="C", fill=True)
    pdf.set_fill_color(0, 120, 90)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_x(lm)
    pdf.cell(pw, 8, f"Evento: {nombre_evento}", ln=True, align="L", fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    pdf.set_font("Helvetica", size=9)
    pdf.set_x(lm)
    pdf.cell(pw / 2, 6, f"Fecha de emision: {date.today().strftime('%d/%m/%Y')}", ln=False)
    pdf.cell(pw / 2, 6, f"Total incidencias: {len(incidencias)}", ln=True, align="R")
    pdf.ln(4)

    # ── Tabla resumen ─────────────────────────────────────────
    col_w = [12, 30, 28, 42, 68]
    headers = ["#", "Tipo", "Estado", "Fecha", "Descripcion"]
    pdf.set_fill_color(200, 220, 245)
    pdf.set_font("Helvetica", "B", 9)
    for i, h in enumerate(headers):
        pdf.set_x(lm + sum(col_w[:i]))
        pdf.cell(col_w[i], 7, h, border=1, fill=True, align="C")
    pdf.ln()

    fill = False
    for row in incidencias:
        inc_id, tipo, desc, fecha, estado = row
        pdf.set_fill_color(238, 245, 255) if fill else pdf.set_fill_color(255, 255, 255)
        pdf.set_font("Helvetica", size=8)
        valores_fila = [
            str(inc_id), tipo, estado,
            str(fecha)[:16] if fecha else "—",
            desc[:65] + "..." if len(desc) > 65 else desc,
        ]
        for i, v in enumerate(valores_fila):
            pdf.set_x(lm + sum(col_w[:i]))
            pdf.cell(col_w[i], 6, v, border=1, fill=True, align="C" if i < 4 else "L")
        pdf.ln()
        fill = not fill

    pdf.ln(6)

    # ── Detalle por incidencia ────────────────────────────────
    pdf.set_fill_color(30, 80, 140)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_x(lm)
    pdf.cell(pw, 8, "DETALLE DE INCIDENCIAS", ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    for row in incidencias:
        inc_id, tipo, desc, fecha, estado = row
        pdf.set_fill_color(220, 235, 255)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_x(lm)
        pdf.cell(pw, 7, f"Incidencia #{inc_id}  |  {tipo}  |  Estado: {estado}", ln=True, fill=True)
        pdf.set_font("Helvetica", size=9)
        pdf.set_x(lm)
        pdf.cell(pw, 5, f"Registrada: {str(fecha)[:19] if fecha else '—'}", ln=True)
        pdf.set_x(lm)
        pdf.multi_cell(pw, 5, f"Descripcion: {desc}")
        detalles = model_incidencia.get_detalles(inc_id)
        if detalles:
            for det in detalles:
                pdf.set_x(lm + 4)
                pdf.multi_cell(pw - 4, 5, f"- {det[1]}")
                if det[2]:
                    pdf.set_x(lm + 8)
                    pdf.multi_cell(pw - 8, 5, f"  Accion: {det[2]}")
        pdf.ln(3)

    pdf.set_y(-18)
    pdf.set_font("Helvetica", size=8)
    pdf.set_text_color(140, 140, 140)
    pdf.set_x(lm)
    pdf.cell(pw, 5,
             f"Reporte generado el {date.today().strftime('%d/%m/%Y')} -- Sistema Genesis",
             align="C")
    return bytes(pdf.output())


# ══════════════════════════════════════════════════════════════
# PDF — Reporte de Encuesta de Satisfacción
# ══════════════════════════════════════════════════════════════

def _generar_pdf_encuesta(id_evento, nombre_evento, nombre_cliente, enc_data, detalles):
    """Reporte PDF de encuesta de satisfaccion con diseno atractivo."""
    # enc_data: (id, id_evento, fecha_evaluacion, nivel_satisfaccion, estado_evaluacion, comentarios)
    pdf = FPDF()
    pdf.set_margins(15, 15, 15)
    pdf.add_page()
    lm = pdf.l_margin
    pw = pdf.w - pdf.l_margin - pdf.r_margin

    # ── Encabezado ────────────────────────────────────────────
    pdf.set_fill_color(15, 100, 80)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_x(lm)
    pdf.cell(pw, 15, "ENCUESTA DE SATISFACCION", ln=True, align="C", fill=True)
    pdf.set_fill_color(240, 255, 245)
    pdf.set_text_color(0, 80, 60)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_x(lm)
    pdf.cell(pw, 8, nombre_evento[:80], ln=True, align="C", fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)

    # ── Ficha informativa ─────────────────────────────────────
    pdf.set_fill_color(245, 248, 252)
    for label, valor in [
        ("Cliente",          nombre_cliente),
        ("Fecha evaluacion", str(enc_data[2]) if enc_data else "-"),
        ("Estado",           enc_data[4] if enc_data else "-"),
    ]:
        pdf.set_x(lm)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(45, 7, f"{label}:", border="B", fill=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(pw - 45, 7, str(valor), border="B", fill=True, ln=True)
    pdf.ln(6)

    # ── Satisfacción general ──────────────────────────────────
    nivel = int(enc_data[3]) if enc_data else 0
    stars_txt = ("*" * nivel).ljust(5, ".") + f"  ({nivel}/5)"
    pdf.set_fill_color(255, 200, 0)
    pdf.set_text_color(60, 40, 0)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_x(lm)
    pdf.cell(pw, 10, f"Satisfaccion General: {stars_txt}", ln=True, align="C", fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)

    # ── Evaluación por dimensión con barras de progreso ───────
    pdf.set_fill_color(30, 80, 140)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_x(lm)
    pdf.cell(pw, 8, "EVALUACION POR DIMENSION", ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    COLORES_DIM = [(74, 120, 168), (114, 183, 178), (84, 162, 75), (238, 202, 59)]
    lbl_w     = 62
    score_w   = 38
    bar_total = pw - lbl_w - score_w - 3

    for idx, det in enumerate(detalles):
        dim_nombre = det[1]
        dim_valor  = int(det[2])
        r, g, b    = COLORES_DIM[idx % len(COLORES_DIM)]
        bar_fill   = int((dim_valor / 5) * bar_total)
        bar_empty  = bar_total - bar_fill

        pdf.set_x(lm)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(lbl_w, 8, dim_nombre, ln=False)
        pdf.set_fill_color(r, g, b)
        if bar_fill > 0:
            pdf.cell(bar_fill, 8, "", fill=True, ln=False)
        pdf.set_fill_color(220, 220, 220)
        if bar_empty > 0:
            pdf.cell(bar_empty, 8, "", fill=True, ln=False)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_fill_color(255, 255, 255)
        pdf.cell(3, 8, "", fill=True, ln=False)
        stars_dim = ("*" * dim_valor).ljust(5, ".") + f" ({dim_valor}/5)"
        pdf.cell(score_w, 8, stars_dim, ln=True)
        pdf.ln(1)

    # ── Promedio ──────────────────────────────────────────────
    if detalles:
        prom = sum(int(d[2]) for d in detalles) / len(detalles)
        pdf.ln(3)
        pdf.set_fill_color(15, 100, 80)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_x(lm)
        pdf.cell(pw, 8, f"Promedio de Satisfaccion: {prom:.2f} / 5", ln=True, align="C", fill=True)
        pdf.set_text_color(0, 0, 0)

    # ── Comentarios ───────────────────────────────────────────
    if enc_data and enc_data[5]:
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_x(lm)
        pdf.cell(pw, 6, "Comentarios:", ln=True)
        pdf.set_fill_color(250, 250, 240)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_x(lm)
        pdf.multi_cell(pw, 5, enc_data[5], fill=True)

    # ── Pie de página ─────────────────────────────────────────
    pdf.set_y(-18)
    pdf.set_font("Helvetica", size=8)
    pdf.set_text_color(140, 140, 140)
    pdf.set_x(lm)
    pdf.cell(pw, 5,
             f"Reporte generado el {date.today().strftime('%d/%m/%Y')} -- Sistema Genesis",
             align="C")
    return bytes(pdf.output())

