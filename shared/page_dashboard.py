import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from database.connection import execute_query, execute_query_one
from shared.utils import exportar_pdf, format_currency

def show():
    st.title("📊 Dashboard — Sistema de Gestión de Eventos")

    # ── KPIs ──────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)

    total_activos = (execute_query_one(
        "SELECT COUNT(*) FROM eventos WHERE estado NOT IN ('Cerrada','Cancelada')"
    ) or [0])[0]

    contratos_pend = (execute_query_one(
        "SELECT COUNT(*) FROM contratos WHERE estado_contrato = 'Pendiente'"
    ) or [0])[0]

    recursos_disp = (execute_query_one(
        "SELECT COUNT(*) FROM recursos WHERE estado = 'Disponible'"
    ) or [0])[0]

    sat_prom = execute_query_one(
        "SELECT ROUND(AVG(nivel_satisfaccion) * 20, 1) FROM encuestas WHERE estado_evaluacion = 'Completada'"
    )
    sat_prom = sat_prom[0] if sat_prom and sat_prom[0] else 0

    with col1:
        st.metric("🎪 Eventos Activos", total_activos)
    with col2:
        st.metric("📄 Contratos Pendientes", contratos_pend,
                  delta="⚠️ Revisar" if contratos_pend > 0 else None,
                  delta_color="inverse")
    with col3:
        st.metric("📦 Recursos Disponibles", recursos_disp)
    with col4:
        st.metric("⭐ Satisfacción Promedio", f"{sat_prom}%")

    st.divider()

    # ── Gráficos ──────────────────────────────────────────────
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("📈 Eventos por Estado")
        rows = execute_query("SELECT estado, COUNT(*) FROM eventos GROUP BY estado")
        if rows:
            df_est = pd.DataFrame(rows, columns=["Estado", "Cantidad"])
            color_map = {
                "Planificación": "#3B82F6",
                "En Ejecución": "#10B981",
                "Cerrada": "#6B7280",
                "Cancelada": "#EF4444",
                "Pendiente": "#F59E0B",
            }
            fig = px.bar(df_est, x="Estado", y="Cantidad", color="Estado",
                         color_discrete_map=color_map, text="Cantidad", template="plotly_white")
            fig.update_traces(textposition="outside", marker_line_width=0)
            fig.update_layout(showlegend=False, height=360,
                               plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                               xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="#F0F0F0"),
                               margin=dict(t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sin datos de eventos.")

    with col_b:
        st.subheader("🍩 Distribución por Tipo de Evento")
        rows2 = execute_query("SELECT tipo_evento, COUNT(*) FROM eventos GROUP BY tipo_evento")
        if rows2:
            df_tipo = pd.DataFrame(rows2, columns=["Tipo", "Cantidad"])
            fig2 = px.pie(df_tipo, names="Tipo", values="Cantidad", hole=0.45,
                          color_discrete_sequence=["#6366F1","#10B981","#F59E0B","#EF4444","#3B82F6","#8B5CF6"],
                          template="plotly_white")
            fig2.update_traces(textposition="inside", textinfo="percent+label")
            fig2.update_layout(height=360, showlegend=True,
                                legend=dict(orientation="v", x=1.0, y=0.5),
                                paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=20, b=20))
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Sin datos de tipos.")

    st.divider()

    col_c, col_d = st.columns(2)

    with col_c:
        st.subheader("📊 Contratos por Estado")
        rows_ct = execute_query("SELECT estado_contrato, COUNT(*) FROM contratos GROUP BY estado_contrato")
        if rows_ct:
            df_ct = pd.DataFrame(rows_ct, columns=["Estado", "Cantidad"])
            color_ct = {"Pendiente":"#F59E0B","Aprobado":"#3B82F6","Rechazado":"#EF4444","Cumplido":"#10B981","Firmado":"#6366F1"}
            fig3 = px.bar(df_ct, x="Cantidad", y="Estado", orientation="h",
                          color="Estado", color_discrete_map=color_ct, text="Cantidad", template="plotly_white")
            fig3.update_traces(textposition="outside", marker_line_width=0)
            fig3.update_layout(showlegend=False, height=300,
                                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                                xaxis=dict(showgrid=True, gridcolor="#F0F0F0"), yaxis=dict(showgrid=False),
                                margin=dict(t=20, b=20))
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("Sin datos de contratos.")

    with col_d:
        st.subheader("💰 Monto por Tipo de Evento (S/)")
        rows_monto = execute_query(
            "SELECT tipo_evento, COALESCE(SUM(monto_evento),0) FROM eventos GROUP BY tipo_evento ORDER BY 2 DESC"
        )
        if rows_monto:
            df_monto = pd.DataFrame(rows_monto, columns=["Tipo", "Monto"])
            fig4 = px.bar(df_monto, x="Tipo", y="Monto", color="Tipo",
                          color_discrete_sequence=["#6366F1","#10B981","#F59E0B","#EF4444","#3B82F6","#8B5CF6"],
                          text_auto=".2s", template="plotly_white")
            fig4.update_traces(textposition="outside", marker_line_width=0)
            fig4.update_layout(showlegend=False, height=300,
                                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                                xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="#F0F0F0", tickprefix="S/ "),
                                margin=dict(t=20, b=20))
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("Sin datos de montos.")

    st.divider()

    # ── Próximos eventos ──────────────────────────────────────
    st.subheader("📅 Próximos Eventos")
    rows3 = execute_query(
        """SELECT e.nombre, e.tipo_evento, e.lugar_evento, e.fecha_evento,
                  e.estado, c.nombre AS cliente, e.monto_evento
           FROM eventos e
           JOIN clientes c ON e.id_cliente = c.id_cliente
           WHERE e.fecha_evento >= CURRENT_DATE
             AND e.estado NOT IN ('Cerrada','Cancelada')
           ORDER BY e.fecha_evento
           LIMIT 10"""
    )
    if rows3:
        df_prox = pd.DataFrame(rows3, columns=["Evento","Tipo","Lugar","Fecha","Estado","Cliente","Monto"])
        df_prox["Monto"] = df_prox["Monto"].apply(format_currency)
        df_prox["Fecha"] = pd.to_datetime(df_prox["Fecha"]).dt.strftime("%d/%m/%Y")
        st.dataframe(df_prox, use_container_width=True, hide_index=True)

        exportar_pdf(
            titulo="Proximos Eventos - Sistema Genesis",
            columnas=["Evento","Tipo","Lugar","Fecha","Estado","Cliente","Monto"],
            datos=[list(r) for r in df_prox.values.tolist()],
            filename="proximos_eventos.pdf"
        )
    else:
        st.info("No hay próximos eventos registrados.")

    st.divider()

    # ── Alertas mejoradas ─────────────────────────────────────
    st.subheader("🔔 Centro de Alertas")

    alerta1 = execute_query("SELECT nro_contrato, monto FROM contratos WHERE estado_contrato = 'Pendiente'")
    alerta2 = execute_query("SELECT id_orden_compra FROM ordenes_compra WHERE estado = 'Pendiente'")
    alerta3 = execute_query(
        "SELECT nombre, fecha_evento FROM eventos WHERE fecha_evento BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days' AND estado NOT IN ('Cerrada','Cancelada')"
    )
    alerta4 = execute_query("SELECT nombre FROM recursos WHERE estado = 'Mantenimiento'")

    hay_alertas = bool(alerta1 or alerta2 or alerta3 or alerta4)

    if not hay_alertas:
        st.success("✅ Todo en orden. No hay alertas pendientes.")
    else:
        col_al1, col_al2 = st.columns(2)

        with col_al1:
            if alerta1:
                st.markdown('<div style="background:#FFF7ED;border-left:4px solid #F97316;padding:12px 16px;border-radius:6px;margin-bottom:12px;"><b>⚠️ Contratos Pendientes de Aprobación</b></div>', unsafe_allow_html=True)
                for r in alerta1:
                    st.markdown(f"&nbsp;&nbsp;• **{r[0]}** — {format_currency(r[1])}")
                st.markdown("")

            if alerta3:
                st.markdown('<div style="background:#FFF1F2;border-left:4px solid #F43F5E;padding:12px 16px;border-radius:6px;margin-bottom:12px;"><b>📅 Eventos en los próximos 7 días</b></div>', unsafe_allow_html=True)
                for r in alerta3:
                    fecha_str = r[1].strftime("%d/%m/%Y") if hasattr(r[1], "strftime") else str(r[1])
                    st.markdown(f"&nbsp;&nbsp;• **{r[0]}** — {fecha_str}")

        with col_al2:
            if alerta2:
                st.markdown('<div style="background:#FFFBEB;border-left:4px solid #EAB308;padding:12px 16px;border-radius:6px;margin-bottom:12px;"><b>🛒 Órdenes de Compra Pendientes</b></div>', unsafe_allow_html=True)
                for r in alerta2:
                    st.markdown(f"&nbsp;&nbsp;• Orden ID: **{r[0]}**")
                st.markdown("")

            if alerta4:
                st.markdown('<div style="background:#F0F9FF;border-left:4px solid #0EA5E9;padding:12px 16px;border-radius:6px;margin-bottom:12px;"><b>🔧 Recursos en Mantenimiento</b></div>', unsafe_allow_html=True)
                for r in alerta4:
                    st.markdown(f"&nbsp;&nbsp;• {r[0]}")
