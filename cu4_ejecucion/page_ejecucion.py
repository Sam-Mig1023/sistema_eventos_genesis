"""
CU4 – Gestionar Ejecución y Cierre del Evento
===============================================
Actor principal: Jefe de Eventos

Funcionalidades (según diagrama de CU):
  1. Registrar estado de evento
  2. Registrar cumplimiento de servicios contratados
  3. Registrar estado de los recursos
  4. Registrar incidencia  (+extend: Generar reporte)
  5. Registrar encuesta de satisfacción
  «include» transversal: Buscar cliente
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
from cu3_recursos import model_asignacion, model_recurso
from shared.utils import format_currency

# ─── Estados válidos del ciclo de vida del evento ────────────
TRANSICIONES_ESTADO = {
    "Registrada":        ["En Planificación", "Cancelada"],
    "En Planificación":  ["Plan Aprobado", "Cancelada"],
    "Plan Aprobado":     ["Confirmada", "Cancelada"],
    "Confirmada":        ["En Ejecución", "Cancelada"],
    "En Ejecución":      ["Cerrada"],
}


def show():
    requiere_rol(["Administrador", "Jefe de Eventos"])

    st.title("🚀 Gestión de Ejecución y Cierre de Eventos")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📌 Estado de Evento",
        "✅ Cumplimiento de Servicios",
        "📦 Estado de Recursos",
        "🔥 Incidencias",
        "⭐ Encuesta de Satisfacción",
    ])

    # ──────────────────────────────────────────────────────────
    # TAB 1 — Registrar estado de evento  (include: Buscar cliente)
    # ──────────────────────────────────────────────────────────
    with tab1:
        _tab_estado_evento()

    # ──────────────────────────────────────────────────────────
    # TAB 2 — Registrar cumplimiento de servicios contratados
    # ──────────────────────────────────────────────────────────
    with tab2:
        _tab_cumplimiento_servicios()

    # ──────────────────────────────────────────────────────────
    # TAB 3 — Registrar estado de los recursos
    # ──────────────────────────────────────────────────────────
    with tab3:
        _tab_estado_recursos()

    # ──────────────────────────────────────────────────────────
    # TAB 4 — Registrar incidencia  (+extend: Generar reporte)
    # ──────────────────────────────────────────────────────────
    with tab4:
        _tab_incidencias()

    # ──────────────────────────────────────────────────────────
    # TAB 5 — Registrar encuesta de satisfacción
    # ──────────────────────────────────────────────────────────
    with tab5:
        _tab_encuestas()


# ══════════════════════════════════════════════════════════════
# FUNCIONES AUXILIARES DE CADA TAB
# ══════════════════════════════════════════════════════════════

def _buscar_cliente(key_prefix):
    """«include» Buscar cliente — devuelve id_cliente seleccionado o None."""
    st.subheader("🔍 Buscar Cliente")
    busqueda = st.text_input("Buscar por nombre o email del cliente", key=f"buscar_cli_{key_prefix}")
    if busqueda:
        resultados = model_cliente.search(busqueda)
        if resultados:
            opciones = {f"{r[1]} — {r[3]} (ID:{r[0]})": r[0] for r in resultados}
            sel = st.selectbox("Seleccionar cliente", list(opciones.keys()), key=f"sel_cli_{key_prefix}")
            return opciones[sel]
        else:
            st.warning("No se encontró ningún cliente con ese criterio.")
    return None


def _selector_evento(key_prefix, solo_activos=True):
    """Devuelve (label, id_evento) del evento seleccionado,
       filtrando opcionalmente por cliente encontrado."""
    id_cliente = _buscar_cliente(key_prefix)

    if id_cliente:
        if solo_activos:
            eventos = model_evento.get_activos()
            # filtrar por cliente
            eventos_filtrados = []
            for ev in eventos:
                ev_full = model_evento.get_by_id(ev[0])
                if ev_full and ev_full[7] == id_cliente:
                    eventos_filtrados.append(ev)
            eventos = eventos_filtrados
        else:
            from database.connection import execute_query
            eventos = execute_query(
                "SELECT id_evento, nombre, estado FROM eventos WHERE id_cliente = %s ORDER BY nombre",
                (id_cliente,)
            ) or []
    else:
        eventos = model_evento.get_activos() if solo_activos else (
            model_evento.get_activos()
        )

    if not eventos:
        st.info("No hay eventos disponibles para este criterio.")
        return None, None

    opciones = {f"{e[1]} [{e[2]}] (ID:{e[0]})": e[0] for e in eventos}
    sel = st.selectbox("Seleccionar Evento", list(opciones.keys()), key=f"{key_prefix}_ev")
    return sel, opciones[sel]


# ──────────────────────────────────────────────────────────────
# TAB 1 — Registrar estado de evento
# ──────────────────────────────────────────────────────────────
def _tab_estado_evento():
    st.subheader("📌 Registrar Estado de Evento")

    label_ev, id_ev = _selector_evento("est", solo_activos=False)
    if id_ev is None:
        return

    ev = model_evento.get_by_id(id_ev)
    if not ev:
        st.error("No se pudo cargar el evento.")
        return

    # ev = (id, nombre, tipo, lugar, fecha, monto, estado, id_cliente)
    estado_actual = ev[6]
    cliente = model_cliente.get_by_id(ev[7])
    nombre_cliente = cliente[1] if cliente else "—"

    col1, col2, col3 = st.columns(3)
    col1.metric("Estado Actual", estado_actual)
    col2.metric("Tipo", ev[2])
    col3.metric("Cliente", nombre_cliente)

    st.markdown(f"**Lugar:** {ev[3] or '—'}  |  **Fecha:** {ev[4] or '—'}  |  **Monto:** {format_currency(ev[5])}")
    st.divider()

    # Posibles transiciones
    posibles = TRANSICIONES_ESTADO.get(estado_actual, [])
    if not posibles:
        st.success(f"El evento ya se encuentra en estado final: **{estado_actual}**.")
        return

    nuevo_estado = st.selectbox("Nuevo estado", posibles, key="nuevo_est_ev")
    if st.button("💾 Actualizar Estado del Evento", key="btn_est_ev"):
        if model_evento.cambiar_estado(id_ev, nuevo_estado):
            st.success(f"Estado del evento actualizado a **{nuevo_estado}**.")
            st.rerun()


# ──────────────────────────────────────────────────────────────
# TAB 2 — Registrar cumplimiento de servicios contratados
# ──────────────────────────────────────────────────────────────
def _tab_cumplimiento_servicios():
    st.subheader("✅ Cumplimiento de Servicios Contratados")

    label_ev, id_ev = _selector_evento("cum")
    if id_ev is None:
        return

    contratos = model_contrato.get_by_evento(id_ev)
    if not contratos:
        st.info("Este evento no tiene contratos registrados.")
        return

    # Tabla de contratos
    df = pd.DataFrame(contratos, columns=[
        "ID", "Nro. Contrato", "Estado", "Monto", "Firma Digital"
    ])
    df["Monto"] = df["Monto"].apply(format_currency)
    df["Firma Digital"] = df["Firma Digital"].map({True: "✅ Sí", False: "❌ No"})
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Selección de contrato para confirmar cumplimiento
    contratos_no_cumplidos = [c for c in contratos if c[2] != "Cumplido"]
    if not contratos_no_cumplidos:
        st.success("Todos los contratos de este evento ya están marcados como cumplidos.")
        return

    opciones_ct = {f"{c[1]} — Estado: {c[2]} (ID:{c[0]})": c[0] for c in contratos_no_cumplidos}
    ct_sel = st.selectbox("Contrato a confirmar cumplimiento", list(opciones_ct.keys()), key="ct_cum")
    id_ct = opciones_ct[ct_sel]

    if st.button("✅ Confirmar Cumplimiento del Contrato", key="btn_cum_ct"):
        if model_contrato.confirmar_cumplimiento(id_ct):
            st.success("Cumplimiento del contrato registrado correctamente.")
            st.rerun()


# ──────────────────────────────────────────────────────────────
# TAB 3 — Registrar estado de los recursos
# ──────────────────────────────────────────────────────────────
def _tab_estado_recursos():
    st.subheader("📦 Estado de Recursos del Evento")

    label_ev, id_ev = _selector_evento("rec")
    if id_ev is None:
        return

    asignaciones = model_asignacion.get_by_evento(id_ev)
    if not asignaciones:
        st.info("No hay recursos asignados a este evento.")
        return

    # asignaciones: (id_asignacion, nombre_recurso, cantidad, fecha_asig, estado)
    df = pd.DataFrame(asignaciones, columns=[
        "ID Asig.", "Recurso", "Cantidad", "Fecha Asig.", "Estado"
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("**Actualizar estado de una asignación de recurso:**")

    opciones_as = {
        f"{a[1]} — Cant: {a[2]} — Estado: {a[4]} (ID:{a[0]})": a[0]
        for a in asignaciones
    }
    as_sel = st.selectbox("Seleccionar asignación", list(opciones_as.keys()), key="as_rec")
    id_asig = opciones_as[as_sel]

    ESTADOS_ASIGNACION = ["Pendiente", "Confirmada", "Cancelada"]
    nuevo_estado_as = st.selectbox("Nuevo estado", ESTADOS_ASIGNACION, key="nuevo_est_as")

    if st.button("💾 Actualizar Estado del Recurso", key="btn_est_rec"):
        if model_asignacion.cambiar_estado(id_asig, nuevo_estado_as):
            st.success(f"Estado de la asignación actualizado a **{nuevo_estado_as}**.")
            st.rerun()


# ──────────────────────────────────────────────────────────────
# TAB 4 — Registrar incidencia  (+extend: Generar reporte)
# ──────────────────────────────────────────────────────────────
def _tab_incidencias():
    st.subheader("🔥 Incidencias del Evento")

    label_ev, id_ev = _selector_evento("inc")
    if id_ev is None:
        return

    # ── Listado de incidencias existentes ─────────────────────
    incidencias = model_incidencia.get_by_evento(id_ev)

    if incidencias:
        df_inc = pd.DataFrame(incidencias, columns=[
            "ID", "Tipo", "Descripción", "Fecha Registro", "Estado"
        ])
        st.dataframe(df_inc, use_container_width=True, hide_index=True)

        # Seleccionar incidencia para ver detalle / cambiar estado
        opciones_inc = {
            f"[{i[0]}] {i[1]} — {i[4]}": i[0] for i in incidencias
        }
        inc_sel = st.selectbox("Seleccionar incidencia", list(opciones_inc.keys()), key="sel_inc")
        id_inc = opciones_inc[inc_sel]

        inc_data = model_incidencia.get_by_id(id_inc)
        if inc_data:
            st.markdown(f"**Tipo:** {inc_data[2]} | **Estado:** {inc_data[5]}")
            st.markdown(f"**Descripción:** {inc_data[3]}")

            # Detalles
            detalles = model_incidencia.get_detalles(id_inc)
            if detalles:
                st.markdown("**Detalles registrados:**")
                df_det = pd.DataFrame(detalles, columns=[
                    "ID Det.", "Descripción", "Acción Tomada", "Fecha"
                ])
                st.dataframe(df_det, use_container_width=True, hide_index=True)

            # Cambiar estado
            col_a, col_b = st.columns(2)
            estados_inc = ["En Proceso", "Resuelta", "Cerrada"]
            nuevo_est = col_a.selectbox("Nuevo estado de incidencia", estados_inc, key="n_est_inc")
            if col_b.button("Cambiar Estado", key="btn_est_inc"):
                if model_incidencia.cambiar_estado(id_inc, nuevo_est):
                    st.success(f"Estado de incidencia actualizado a **{nuevo_est}**.")
                    st.rerun()

            # Agregar detalle a incidencia existente
            with st.expander("➕ Agregar detalle a esta incidencia"):
                with st.form("form_det_inc"):
                    desc_det = st.text_area("Descripción del detalle")
                    accion = st.text_area("Acción tomada")
                    if st.form_submit_button("Guardar Detalle"):
                        if desc_det:
                            if model_incidencia.create_detalle(id_inc, desc_det, accion):
                                st.success("Detalle agregado correctamente.")
                                st.rerun()
                        else:
                            st.error("La descripción del detalle es obligatoria.")

        # ── «extend»: Generar reporte de incidencias ─────────
        st.divider()
        if st.button("📄 Generar Reporte de Incidencias (PDF)", key="btn_pdf_inc"):
            pdf_bytes = _generar_pdf_incidencias(id_ev, label_ev, incidencias)
            st.download_button(
                "⬇️ Descargar Reporte PDF",
                data=pdf_bytes,
                file_name=f"reporte_incidencias_evento_{id_ev}.pdf",
                mime="application/pdf",
            )
    else:
        st.info("No hay incidencias registradas para este evento.")

    # ── Registrar nueva incidencia ────────────────────────────
    st.divider()
    with st.form("form_nueva_inc"):
        st.subheader("➕ Registrar Nueva Incidencia")
        tipo_inc = st.selectbox("Tipo de incidencia", model_incidencia.TIPOS_INCIDENCIA)
        desc_inc = st.text_area("Descripción de la incidencia *")
        desc_det_ini = st.text_area("Detalle inicial / Acción tomada (opcional)")
        if st.form_submit_button("Registrar Incidencia"):
            if not desc_inc:
                st.error("La descripción es obligatoria.")
            else:
                id_nueva = model_incidencia.create(id_ev, tipo_inc, desc_inc)
                if id_nueva:
                    if desc_det_ini:
                        model_incidencia.create_detalle(id_nueva, desc_inc, desc_det_ini)
                    st.success("Incidencia registrada exitosamente.")
                    st.rerun()


# ──────────────────────────────────────────────────────────────
# TAB 5 — Registrar encuesta de satisfacción
# ──────────────────────────────────────────────────────────────
def _tab_encuestas():
    st.subheader("⭐ Encuesta de Satisfacción")

    # Para encuestas mostramos también eventos cerrados
    label_ev, id_ev = _selector_evento("enc", solo_activos=False)
    if id_ev is None:
        return

    ev = model_evento.get_by_id(id_ev)
    estado_ev = ev[6] if ev else "—"

    # ── Encuestas existentes ──────────────────────────────────
    encuestas_ev = model_encuesta.get_by_evento(id_ev)
    if encuestas_ev:
        st.markdown("**Encuestas registradas:**")
        df_enc = pd.DataFrame(encuestas_ev, columns=[
            "ID", "Fecha", "Satisfacción (1-5)", "Estado", "Comentarios"
        ])
        st.dataframe(df_enc, use_container_width=True, hide_index=True)

        # Detalle con gráfico radar
        opciones_enc = {f"Encuesta #{e[0]} — {e[3]}": e[0] for e in encuestas_ev}
        enc_sel = st.selectbox("Ver detalle de encuesta", list(opciones_enc.keys()), key="sel_enc_det")
        id_enc = opciones_enc[enc_sel]

        detalles_enc = model_encuesta.get_detalles(id_enc)
        if detalles_enc:
            dimensiones = [d[1] for d in detalles_enc]
            valores = [d[2] for d in detalles_enc]

            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(
                r=valores + [valores[0]],
                theta=dimensiones + [dimensiones[0]],
                fill="toself",
                name="Satisfacción",
            ))
            fig.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 5])),
                title="Radar de Satisfacción",
                height=400,
            )
            st.plotly_chart(fig, use_container_width=True)
            prom = sum(valores) / len(valores)
            st.metric("Promedio de satisfacción", f"{prom:.1f} / 5")

    # ── Nueva encuesta (solo si evento Cerrada o En Ejecución)
    st.divider()
    if estado_ev not in ("En Ejecución", "Cerrada"):
        st.warning(
            f"Solo se pueden registrar encuestas para eventos en estado "
            f"**En Ejecución** o **Cerrada**. Estado actual: **{estado_ev}**."
        )
        return

    with st.form("form_nueva_enc"):
        st.subheader("➕ Registrar Nueva Encuesta de Satisfacción")
        fecha_enc = st.date_input("Fecha de evaluación", value=date.today())
        nivel_gen = st.slider("Nivel de satisfacción general (1-5)", 1, 5, 4)
        comentarios = st.text_area("Comentarios generales")

        st.markdown("**Evaluación por dimensión:**")
        respuestas = {}
        for dim in model_encuesta.DIMENSIONES:
            respuestas[dim] = st.slider(dim, 1, 5, 4, key=f"dim_{dim}")

        if st.form_submit_button("Guardar Encuesta"):
            id_enc_nuevo = model_encuesta.create(id_ev, fecha_enc, nivel_gen, comentarios)
            if id_enc_nuevo:
                for dim, resp in respuestas.items():
                    model_encuesta.create_detalle(id_enc_nuevo, dim, resp)
                model_encuesta.completar_encuesta(id_enc_nuevo)
                st.success("Encuesta de satisfacción registrada y completada.")
                st.rerun()


# ══════════════════════════════════════════════════════════════
# «extend» Generar reporte de incidencia — PDF
# ══════════════════════════════════════════════════════════════

def _generar_pdf_incidencias(id_evento, nombre_evento, incidencias):
    """Genera un reporte PDF de las incidencias de un evento."""
    pdf = FPDF()
    pdf.add_page()

    # Título
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Reporte de Incidencias", ln=True, align="C")
    pdf.ln(4)

    # Info del evento
    pdf.set_font("Arial", size=11)
    pdf.cell(0, 7, f"Evento: {nombre_evento}", ln=True)
    pdf.cell(0, 7, f"Fecha de generacion: {date.today().strftime('%d/%m/%Y')}", ln=True)
    pdf.cell(0, 7, f"Total de incidencias: {len(incidencias)}", ln=True)
    pdf.ln(4)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 7, "=" * 70, ln=True)
    pdf.ln(2)

    for row in incidencias:
        inc_id, tipo, desc, fecha, estado = row

        # Cabecera de incidencia
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 7, f"Incidencia #{inc_id}  |  Tipo: {tipo}  |  Estado: {estado}", ln=True)
        pdf.set_font("Arial", size=10)
        pdf.cell(0, 6, f"Fecha: {fecha}", ln=True)
        pdf.multi_cell(0, 6, f"Descripcion: {desc}")

        # Detalles de la incidencia
        detalles = model_incidencia.get_detalles(inc_id)
        if detalles:
            pdf.set_font("Arial", "I", 9)
            for det in detalles:
                pdf.multi_cell(0, 5, f"  - Detalle: {det[1]}")
                if det[2]:
                    pdf.multi_cell(0, 5, f"    Accion tomada: {det[2]}")

        pdf.ln(3)
        pdf.set_font("Arial", size=8)
        pdf.cell(0, 4, "-" * 70, ln=True)
        pdf.ln(2)

    pdf_output = pdf.output(dest="S")
    if isinstance(pdf_output, str):
        return pdf_output.encode("latin-1")
    return bytes(pdf_output)
