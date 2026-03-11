import streamlit as st
import pandas as pd
from datetime import date
from auth.roles import requiere_rol
from cu3_recursos import model_proveedor, model_recurso, model_asignacion, model_calificacion
from cu2_planificacion import model_evento
from shared.utils import format_currency, exportar_pdf

def show():
    requiere_rol(['Administrador', 'Jefe de Logística'])
    st.title("📦 Gestión de Recursos y Proveedores")
    tab1, tab2, tab3 = st.tabs(["🏢 Proveedores", "📦 Recursos", "🔗 Asignaciones"])

    # ── TAB 1: Proveedores ────────────────────────────────────
    with tab1:
        rows_p = model_proveedor.get_all()
        if rows_p:
            df_p = pd.DataFrame(rows_p, columns=["ID","Nombre","Tipo Servicio","Disponible","Email","Teléfono"])
            
            # Estadísticas de Proveedores
            st.subheader("📊 Estadísticas de Proveedores")
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Proveedores", len(df_p))
            c2.metric("Disponibles", len(df_p[df_p["Disponible"] == True]))
            c3.metric("Tipos de Servicio", df_p["Tipo Servicio"].nunique())
            
            st.dataframe(df_p, use_container_width=True)
            exportar_pdf("Listado de Proveedores", df_p.columns.tolist(), rows_p, "proveedores.pdf")
        else:
            st.info("No hay proveedores.")

        col_a, col_b = st.columns(2)
        with col_a:
            with st.form("form_nuevo_prov"):
                st.subheader("Nuevo Proveedor")
                nombre_p = st.text_input("Nombre *")
                tipo_s   = st.text_input("Tipo de servicio *")
                disp     = st.checkbox("Disponible", value=True)
                email_p  = st.text_input("Email")
                tel_p    = st.text_input("Teléfono")
                if st.form_submit_button("Registrar"):
                    if not nombre_p or not tipo_s:
                        st.error("Nombre y tipo de servicio son obligatorios.")
                    elif model_proveedor.create(nombre_p, tipo_s, disp, email_p, tel_p):
                        st.success("Proveedor registrado.")
                        st.rerun()

        with col_b:
            with st.form("form_edit_prov"):
                st.subheader("Editar Proveedor")
                id_prov = st.number_input("ID del proveedor", min_value=1, step=1)
                prov = model_proveedor.get_by_id(int(id_prov))
                if prov:
                    n_nombre = st.text_input("Nombre", value=prov[1])
                    n_tipo   = st.text_input("Tipo servicio", value=prov[2])
                    n_disp   = st.checkbox("Disponible", value=bool(prov[3]))
                    n_email  = st.text_input("Email", value=prov[4] or "")
                    n_tel    = st.text_input("Teléfono", value=prov[5] or "")
                    if st.form_submit_button("Guardar"):
                        model_proveedor.update(id_prov, n_nombre, n_tipo, n_disp, n_email, n_tel)
                        st.success("Proveedor actualizado.")
                        st.rerun()

    # ── TAB 2: Recursos ───────────────────────────────────────
    with tab2:
        rows_r = model_recurso.get_all()
        if rows_r:
            df_r = pd.DataFrame(rows_r, columns=["ID","Nombre","Tipo","Cantidad","Disponible","Estado","Proveedor"])
            
            # Estadísticas de Recursos
            st.subheader("📊 Estadísticas de Recursos")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Items", len(df_r))
            c2.metric("Stock Total", f"{int(df_r['Cantidad'].sum()):,}")
            c3.metric("Stock Disponible", f"{int(df_r['Disponible'].sum()):,}")
            c4.metric("Tipos Únicos", df_r["Tipo"].nunique())
            
            st.dataframe(df_r, use_container_width=True)
            exportar_pdf("Listado de Recursos", df_r.columns.tolist(), rows_r, "recursos.pdf")

        col_a, col_b = st.columns(2)
        proveedores = model_proveedor.get_all()
        prov_op = {"— Sin proveedor —": None}
        prov_op.update({f"{p[1]} (ID:{p[0]})": p[0] for p in proveedores})

        with col_a:
            with st.form("form_nuevo_rec"):
                st.subheader("Nuevo Recurso")
                nombre_r  = st.text_input("Nombre *")
                tipo_r    = st.selectbox("Tipo", model_recurso.TIPOS_RECURSO)
                cantidad  = st.number_input("Cantidad", min_value=0, step=1)
                estado_r  = st.selectbox("Estado", model_recurso.ESTADOS_RECURSO)
                prov_sel  = st.selectbox("Proveedor", list(prov_op.keys()))
                if st.form_submit_button("Registrar"):
                    if not nombre_r:
                        st.error("El nombre es obligatorio.")
                    else:
                        id_p = prov_op[prov_sel]
                        if model_recurso.create(nombre_r, tipo_r, cantidad, estado_r, id_p):
                            st.success("Recurso registrado.")
                            st.rerun()

        with col_b:
            with st.form("form_estado_rec"):
                st.subheader("Cambiar Estado de Recurso")
                id_rec  = st.number_input("ID del recurso", min_value=1, step=1)
                n_est_r = st.selectbox("Nuevo estado", model_recurso.ESTADOS_RECURSO)
                if st.form_submit_button("Actualizar Estado"):
                    model_recurso.cambiar_estado(int(id_rec), n_est_r)
                    st.success("Estado actualizado.")
                    st.rerun()

    # ── TAB 3: Asignaciones ───────────────────────────────────
    with tab3:
        rows_a = model_asignacion.get_all()
        if rows_a:
            df_a = pd.DataFrame(rows_a, columns=["ID","Evento","Recurso","Cantidad","Fecha Asig.","Estado"])
            
            # Estadísticas de Asignaciones
            st.subheader("📊 Estadísticas de Asignaciones")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Asignaciones", len(df_a))
            c2.metric("Items Asignados", f"{int(df_a['Cantidad'].sum()):,}")
            c3.metric("Promedio Cantidad", f"{df_a['Cantidad'].mean():.1f}")
            c4.metric("Máx. Asignado", f"{int(df_a['Cantidad'].max()):,}")
            
            st.dataframe(df_a, use_container_width=True)
            exportar_pdf("Listado de Asignaciones", df_a.columns.tolist(), rows_a, "asignaciones.pdf")

        eventos_act = model_evento.get_activos()
        recursos_disp = [r for r in model_recurso.get_all() if r[5] == 'Disponible']

        if eventos_act and recursos_disp:
            ev_op_a  = {f"{e[1]} (ID:{e[0]})": e[0] for e in eventos_act}
            rec_op_a = {f"{r[1]} - Disp:{r[4]} (ID:{r[0]})": r[0] for r in recursos_disp}

            with st.form("form_asignacion"):
                st.subheader("Nueva Asignación")
                ev_sel_a  = st.selectbox("Evento", list(ev_op_a.keys()))
                rec_sel_a = st.selectbox("Recurso disponible", list(rec_op_a.keys()))
                cant_a    = st.number_input("Cantidad a asignar", min_value=1, step=1)
                fecha_a   = st.date_input("Fecha de asignación", value=date.today())
                if st.form_submit_button("Confirmar Asignación"):
                    id_ev_a  = ev_op_a[ev_sel_a]
                    id_rec_a = rec_op_a[rec_sel_a]
                    if model_asignacion.create(id_ev_a, id_rec_a, cant_a, fecha_a):
                        model_recurso.cambiar_estado(id_rec_a, 'Asignado')
                        st.success("Asignación confirmada y recurso marcado como Asignado.")
                        st.rerun()

            st.subheader("Proveedores ordenados por calificación")
            ranking = model_calificacion.get_ranking_proveedores()
            if ranking:
                df_rank = pd.DataFrame(ranking, columns=["Proveedor","Promedio","Calificaciones"])
                st.dataframe(df_rank, use_container_width=True)
                exportar_pdf("Proveedores ordenados por calificación", df_rank.columns.tolist(), ranking, "ranking_proveedores.pdf")

            with st.form("form_devolucion"):
                st.subheader("Devolución de Recurso y Calificación")
                id_asig = st.number_input("ID de la asignación", min_value=1, step=1)
                calif   = st.slider("Calificación del proveedor (1-10)", 1, 10, 5)
                if st.form_submit_button("Registrar devolución"):
                    if model_asignacion.devolver(int(id_asig)):
                        id_prov = model_calificacion.resolve_proveedor_for_asignacion(int(id_asig))
                        if id_prov:
                            if model_calificacion.create(id_prov, int(id_asig), int(calif), date.today()):
                                st.success("Devolución registrada, estado actualizado y calificación guardada.")
                                st.rerun()

