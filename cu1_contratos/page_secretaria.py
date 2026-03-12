"""
P�gina exclusiva para la Secretaria de Eventos.
CU1 completo + requerimientos con todas las mejoras solicitadas.
"""
import streamlit as st
import pandas as pd
from datetime import date
from auth.roles import requiere_rol
from cu1_contratos import model_cliente, model_contrato
from cu2_planificacion import model_evento
from cu2_planificacion.model_requerimiento import (
    get_by_evento, get_by_id as get_req_by_id,
    create as create_req, delete as delete_req,
    update as update_req, TIPOS_RECURSO, get_all as get_all_reqs
)
from cu3_recursos import model_proveedor
from shared.utils import validate_email, format_currency, generar_nro_contrato, paginate_dataframe, exportar_pdf

TIPOS_CLIENTE = ["Persona Natural", "Empresa", "Institución"]
TIPOS_EVENTO  = ["Corporativo", "Social", "Institucional", "Cultural", "Deportivo", "Otro"]
ESTADOS_CLIENTE = ["Activo", "Inactivo"]


def show():
    requiere_rol(['Secretaria de Eventos', 'Administrador'])
    st.title("🗂️ Gestión de Clientes, Eventos y Contratos")

    tab1, tab2, tab3, tab4 = st.tabs([
        "👥 Clientes",
        "📅 Eventos",
        "📦 Requerimientos",
        "📄 Contratos",
    ])

    # ──────────────────────────────────────────────────────────
    # TAB 1 — CLIENTES
    # ──────────────────────────────────────────────────────────
    with tab1:
        st.subheader("🔍 Buscar Clientes")

        # Filtros con combobox
        rows_all = model_cliente.get_all()
        cols_all = ["ID", "Nombre", "Tipo", "Dirección", "Email", "Teléfono", "Fecha Reg.", "Estado"]

        # Filtros con combobox
        f1, f2, f3, f4, f5 = st.columns(5)
        nombres_cli     = ["Todos"] + sorted([r[1] for r in rows_all]) if rows_all else ["Todos"]
        filtro_nombre   = f1.selectbox("Nombre", nombres_cli, key="fil_nombre")
        filtro_tipo     = f2.selectbox("Tipo", ["Todos"] + TIPOS_CLIENTE, key="fil_tipo")
        filtro_email    = f3.text_input("Email", key="fil_email")
        filtro_fecha    = f4.date_input("Fecha de registro (desde)", value=None, key="fil_fecha")
        filtro_estado   = f5.selectbox("Estado", ["Todos", "Activo", "Inactivo"], key="fil_estado")

        if rows_all:
            df_cli = pd.DataFrame(rows_all, columns=cols_all)
            if filtro_nombre != "Todos":
                df_cli = df_cli[df_cli["Nombre"] == filtro_nombre]
            if filtro_tipo != "Todos":
                df_cli = df_cli[df_cli["Tipo"] == filtro_tipo]
            if filtro_email:
                df_cli = df_cli[df_cli["Email"].str.contains(filtro_email, case=False, na=False)]
            if filtro_fecha:
                df_cli["Fecha Reg."] = pd.to_datetime(df_cli["Fecha Reg."], errors="coerce")
                df_cli = df_cli[df_cli["Fecha Reg."].dt.date >= filtro_fecha]
            if filtro_estado != "Todos":
                df_cli = df_cli[df_cli["Estado"] == filtro_estado]

            if not df_cli.empty:
                # Paginación (10 por página)
                page_size = 10
                total = len(df_cli)
                total_pages = max(1, (total + page_size - 1) // page_size)

                pg_col1, pg_col2, pg_col3 = st.columns([1, 2, 1])
                if "cli_page" not in st.session_state:
                    st.session_state["cli_page"] = 1

                with pg_col1:
                    if st.button("◀ Anterior", key="cli_prev", disabled=st.session_state["cli_page"] <= 1):
                        st.session_state["cli_page"] -= 1
                with pg_col3:
                    if st.button("Siguiente ▶", key="cli_next", disabled=st.session_state["cli_page"] >= total_pages):
                        st.session_state["cli_page"] += 1

                pg = st.session_state["cli_page"]
                start = (pg - 1) * page_size
                df_pag = df_cli.iloc[start:start + page_size]

                with pg_col2:
                    st.markdown(f"<div style='text-align:center;padding-top:6px'>Página <b>{pg}</b> de <b>{total_pages}</b> &nbsp;({total} registros)</div>", unsafe_allow_html=True)

                st.dataframe(df_pag, use_container_width=True, hide_index=True)

                # Exportar tabla filtrada a PDF
                df_export = df_cli.copy()
                df_export["Fecha Reg."] = df_export["Fecha Reg."].astype(str)
                exportar_pdf(
                    titulo="Listado de Clientes - Sistema Genesis",
                    columnas=list(df_export.columns),
                    datos=[list(r) for r in df_export.values.tolist()],
                    filename="clientes.pdf"
                )
            else:
                st.info("No se encontraron clientes con esos filtros.")
        else:
            st.info("No hay clientes registrados.")

        st.divider()
        st.subheader("➕ Registrar Nuevo Cliente")
        with st.form("form_nuevo_cliente_sec"):
            c1, c2 = st.columns(2)
            nombre_c       = c1.text_input("Nombre *")
            tipo_cliente_c = c2.selectbox("Tipo de cliente *", TIPOS_CLIENTE)
            email_c        = c1.text_input("Email *")
            telefono_c     = c2.text_input("Teléfono")
            direccion_c    = st.text_area("Dirección")
            if st.form_submit_button("Registrar Cliente"):
                if not nombre_c or not email_c:
                    st.error("Nombre y email son obligatorios.")
                elif not validate_email(email_c):
                    st.error("Formato de email inválido.")
                else:
                    if model_cliente.create(nombre_c, tipo_cliente_c, direccion_c, email_c, telefono_c):
                        st.success(f"✅ Cliente '{nombre_c}' registrado exitosamente.")
                        st.rerun()

        st.divider()
        st.subheader("✏️ Editar Cliente")
        clientes_todos = model_cliente.get_all()
        if clientes_todos:
            cli_nombres = {f"{r[1]} (ID:{r[0]})": r[0] for r in clientes_todos}
            cli_sel_edit = st.selectbox("Seleccionar cliente a editar", list(cli_nombres.keys()), key="cli_edit_sel")
            id_cli_edit = cli_nombres[cli_sel_edit]
            cli_data = model_cliente.get_by_id(id_cli_edit)

            if cli_data:
                # cli_data: id, nombre, tipo_cliente, direccion, email, telefono, estado
                with st.form("form_editar_cliente"):
                    c1e, c2e = st.columns(2)
                    nombre_e    = c1e.text_input("Nombre *", value=cli_data[1])
                    tipo_e      = c2e.selectbox("Tipo de cliente *", TIPOS_CLIENTE,
                                                 index=TIPOS_CLIENTE.index(cli_data[2]) if cli_data[2] in TIPOS_CLIENTE else 0)
                    email_e     = c1e.text_input("Email *", value=cli_data[4] or "")
                    telefono_e  = c2e.text_input("Teléfono", value=cli_data[5] or "")
                    direccion_e = st.text_area("Dirección", value=cli_data[3] or "")
                    estado_e    = st.selectbox("Estado", ESTADOS_CLIENTE,
                                               index=ESTADOS_CLIENTE.index(cli_data[6]) if cli_data[6] in ESTADOS_CLIENTE else 0)
                    if st.form_submit_button("💾 Guardar Cambios"):
                        if not nombre_e or not email_e:
                            st.error("Nombre y email son obligatorios.")
                        elif not validate_email(email_e):
                            st.error("Formato de email inválido.")
                        else:
                            if model_cliente.update(id_cli_edit, nombre_e, tipo_e, direccion_e, email_e, telefono_e, estado_e):
                                st.success("✅ Cliente actualizado correctamente.")
                                st.rerun()

    # ──────────────────────────────────────────────────────────
    # TAB 2 — EVENTOS
    # ──────────────────────────────────────────────────────────
    with tab2:
        st.subheader("📋 Listado de Eventos")
        rows_ev = model_evento.get_all()
        if rows_ev:
            df_ev = pd.DataFrame(
                rows_ev,
                columns=["ID", "Nombre", "Tipo", "Lugar", "Fecha", "Monto", "Estado", "Cliente"]
            )

            # Filtros
            fe1, fe2, fe3 = st.columns(3)
            fe4, fe5, fe6, fe7 = st.columns(4)
            nombres_ev_fil  = ["Todos"] + sorted([r[1] for r in rows_ev])
            tipos_ev_fil    = ["Todos"] + sorted(list({r[2] for r in rows_ev}))
            lugares_ev_fil  = ["Todos"] + sorted(list({r[3] for r in rows_ev if r[3]}))
            estados_ev_fil  = ["Todos"] + sorted(list({r[6] for r in rows_ev}))
            clientes_ev_fil = ["Todos"] + sorted(list({r[7] for r in rows_ev}))

            fil_ev_nombre  = fe1.selectbox("Nombre", nombres_ev_fil, key="ev_fil_nombre")
            fil_ev_tipo    = fe2.selectbox("Tipo", tipos_ev_fil, key="ev_fil_tipo")
            fil_ev_lugar   = fe3.selectbox("Lugar", lugares_ev_fil, key="ev_fil_lugar")
            fil_ev_fecha   = fe4.date_input("Fecha desde", value=None, key="ev_fil_fecha")
            fil_ev_mmin    = fe5.number_input("Monto mín.", min_value=0.0, value=0.0, step=100.0, key="ev_fil_mmin")
            fil_ev_mmax    = fe6.number_input("Monto máx.", min_value=0.0, value=0.0, step=100.0, key="ev_fil_mmax")
            fil_ev_estado  = fe7.selectbox("Estado", estados_ev_fil, key="ev_fil_estado")

            # Aplicar filtros
            if fil_ev_nombre != "Todos":
                df_ev = df_ev[df_ev["Nombre"] == fil_ev_nombre]
            if fil_ev_tipo != "Todos":
                df_ev = df_ev[df_ev["Tipo"] == fil_ev_tipo]
            if fil_ev_lugar != "Todos":
                df_ev = df_ev[df_ev["Lugar"] == fil_ev_lugar]
            if fil_ev_fecha:
                df_ev["Fecha"] = pd.to_datetime(df_ev["Fecha"], errors="coerce")
                df_ev = df_ev[df_ev["Fecha"].dt.date >= fil_ev_fecha]
            if fil_ev_mmin > 0:
                df_ev = df_ev[df_ev["Monto"].astype(float) >= fil_ev_mmin]
            if fil_ev_mmax > 0:
                df_ev = df_ev[df_ev["Monto"].astype(float) <= fil_ev_mmax]
            if fil_ev_estado != "Todos":
                df_ev = df_ev[df_ev["Estado"] == fil_ev_estado]

            if not df_ev.empty:
                df_show = df_ev.drop(columns=["ID"])
                st.dataframe(df_show, use_container_width=True, hide_index=True)

                df_pdf = df_show.copy()
                df_pdf["Fecha"] = df_pdf["Fecha"].astype(str)
                df_pdf["Monto"] = df_pdf["Monto"].apply(format_currency)
                exportar_pdf(
                    titulo="Listado de Eventos - Sistema Genesis",
                    columnas=list(df_pdf.columns),
                    datos=[list(r) for r in df_pdf.values.tolist()],
                    filename="eventos.pdf"
                )
            else:
                st.info("No se encontraron eventos con esos filtros.")
        else:
            st.info("Aún no hay eventos registrados.")
            
        st.divider()
        st.subheader("➕ Registrar Nuevo Evento")
        clientes_activos = model_cliente.get_activos()
        if not clientes_activos:
            st.warning("⚠️ No hay clientes activos. Registra un cliente primero.")
        else:
            cli_op = {c[1]: c[0] for c in clientes_activos}
            with st.form("form_nuevo_evento_sec"):
                c1, c2 = st.columns(2)
                nombre_ev   = c1.text_input("Nombre del evento *")
                tipo_ev     = c2.selectbox("Tipo de evento", TIPOS_EVENTO)
                lugar_ev    = c1.text_input("Lugar")
                fecha_ev    = c2.date_input("Fecha del evento")
                monto_ev    = st.number_input("Monto estimado S/", min_value=0.0, step=100.0)
                cliente_sel = st.selectbox("Cliente *", list(cli_op.keys()))
                if st.form_submit_button("Registrar Evento"):
                    if not nombre_ev:
                        st.error("El nombre del evento es obligatorio.")
                    else:
                        id_cli = cli_op[cliente_sel]
                        if model_evento.create(nombre_ev, tipo_ev, lugar_ev, fecha_ev, monto_ev, id_cli):
                            st.success(f"✅ Evento '{nombre_ev}' registrado exitosamente.")
                            st.rerun()

        st.divider()
        st.subheader("✏️ Actualizar Evento")
        eventos_todos = model_evento.get_all()
        if eventos_todos:
            ev_nombres = {f"{r[1]}": r[0] for r in eventos_todos}
            ev_sel_upd = st.selectbox("Seleccionar evento a editar", list(ev_nombres.keys()), key="ev_edit_sel")
            id_ev_upd = ev_nombres[ev_sel_upd]
            ev_data = model_evento.get_by_id(id_ev_upd)

            if ev_data:
                # ev_data: id, nombre, tipo, lugar, fecha, monto, estado, id_cliente
                with st.form("form_editar_evento"):
                    c1u, c2u = st.columns(2)
                    nombre_eu = c1u.text_input("Nombre del evento *", value=ev_data[1])
                    tipo_eu   = c2u.selectbox("Tipo de evento", TIPOS_EVENTO,
                                               index=TIPOS_EVENTO.index(ev_data[2]) if ev_data[2] in TIPOS_EVENTO else 0)
                    lugar_eu  = c1u.text_input("Lugar", value=ev_data[3] or "")
                    fecha_eu  = c2u.date_input("Fecha del evento", value=ev_data[4])
                    monto_eu  = st.number_input("Monto estimado S/", value=float(ev_data[5] or 0), min_value=0.0, step=100.0)
                    if st.form_submit_button("💾 Guardar Cambios"):
                        if not nombre_eu:
                            st.error("El nombre es obligatorio.")
                        elif model_evento.update(id_ev_upd, nombre_eu, tipo_eu, lugar_eu, fecha_eu, monto_eu):
                            st.success("✅ Evento actualizado correctamente.")
                            st.rerun()

    # ──────────────────────────────────────────────────────────
    # TAB 3 — REQUERIMIENTOS
    # ──────────────────────────────────────────────────────────
    with tab3:
        st.subheader("📦 Requerimientos del Evento")
        eventos_act = model_evento.get_activos()
        if not eventos_act:
            st.warning("No hay eventos activos.")
        else:
            # Combobox sin ID
            ev_op_r = {e[1]: e[0] for e in eventos_act}
            ev_sel_r = st.selectbox("Seleccionar Evento", list(ev_op_r.keys()), key="req_ev_sec")
            id_ev_r  = ev_op_r[ev_sel_r]

            reqs = get_by_evento(id_ev_r)
            if reqs:
                df_req = pd.DataFrame(reqs, columns=["ID", "Descripción", "Tipo Recurso", "Cantidad"])
                df_req_show = df_req.drop(columns=["ID"])
                st.dataframe(df_req_show, use_container_width=True, hide_index=True)

                # Exportar requerimientos a PDF
                exportar_pdf(
                    titulo=f"Requerimientos - {ev_sel_r}",
                    columnas=["Descripción", "Tipo Recurso", "Cantidad"],
                    datos=[list(r) for r in df_req_show.values.tolist()],
                    filename="requerimientos.pdf"
                )

                st.divider()
                st.subheader("🗑️ Eliminar Requerimiento")
                col_f1, col_f2 = st.columns(2)
                # Selectbox con todos los requerimientos del evento
                desc_opciones = ["Todos"] + list({r[1] for r in reqs})
                fil_desc = col_f1.selectbox("Descripción", desc_opciones, key="req_fil_desc")
                fil_tipo = col_f2.selectbox("Tipo de recurso", ["Todos"] + TIPOS_RECURSO, key="req_fil_tipo")

                # Filtrar requerimientos según selección
                reqs_filtrados = [
                    r for r in reqs
                    if (fil_desc == "Todos" or r[1] == fil_desc)
                    and (fil_tipo == "Todos" or r[2] == fil_tipo)
                ]

                if reqs_filtrados:
                    st.caption(f"{len(reqs_filtrados)} requerimiento(s) encontrado(s)")
                    # Checkbox "Seleccionar todos"
                    sel_todos = st.checkbox("Seleccionar todos", key="req_del_sel_todos")
                    ids_a_eliminar = []
                    for r in reqs_filtrados:
                        label = f"{r[1]} — {r[2]} (Cantidad: {r[3]})"
                        checked = st.checkbox(label, value=sel_todos, key=f"req_chk_{r[0]}")
                        if checked:
                            ids_a_eliminar.append(r[0])

                    if st.button("🗑️ Eliminar Requerimiento(s) Seleccionado(s)"):
                        if not ids_a_eliminar:
                            st.warning("Selecciona al menos un requerimiento.")
                        else:
                            errores = 0
                            for id_del in ids_a_eliminar:
                                if not delete_req(id_del):
                                    errores += 1
                            if errores == 0:
                                st.success(f"✅ {len(ids_a_eliminar)} requerimiento(s) eliminado(s).")
                            else:
                                st.warning(f"Se eliminaron {len(ids_a_eliminar) - errores}, pero {errores} fallaron.")
                            st.rerun()
                else:
                    st.info("No hay requerimientos con esos filtros.")

                st.divider()
                st.subheader("✏️ Actualizar Requerimiento")
                req_upd_op = {f"{r[1]} ({r[2]})": r[0] for r in reqs}
                req_upd_sel = st.selectbox("Seleccionar requerimiento a editar", list(req_upd_op.keys()), key="req_upd_sel")
                id_req_upd = req_upd_op[req_upd_sel]
                req_data = get_req_by_id(id_req_upd)

                if req_data:
                    # req_data: id, id_evento, descripcion, tipo_recurso, cantidad
                    with st.form("form_editar_req"):
                        desc_upd = st.text_input("Descripción *", value=req_data[2])
                        tipo_upd = st.selectbox("Tipo de recurso", TIPOS_RECURSO,
                                                 index=TIPOS_RECURSO.index(req_data[3]) if req_data[3] in TIPOS_RECURSO else 0)
                        cant_upd = st.number_input("Cantidad", min_value=1, step=1, value=int(req_data[4]))
                        if st.form_submit_button("💾 Guardar Cambios"):
                            if not desc_upd:
                                st.error("La descripción es obligatoria.")
                            elif update_req(id_req_upd, desc_upd, tipo_upd, cant_upd):
                                st.success("✅ Requerimiento actualizado.")
                                st.rerun()
            else:
                st.info("Este evento aún no tiene requerimientos registrados.")

            st.divider()
            st.subheader("➕ Agregar Requerimiento")
            with st.form("form_nuevo_req_sec"):
                desc_r = st.text_input("Descripción *")
                tipo_r = st.selectbox("Tipo de recurso", TIPOS_RECURSO)
                cant_r = st.number_input("Cantidad", min_value=1, step=1, value=1)
                if st.form_submit_button("Agregar Requerimiento"):
                    if not desc_r:
                        st.error("La descripción es obligatoria.")
                    elif create_req(id_ev_r, desc_r, tipo_r, cant_r):
                        st.success("✅ Requerimiento agregado.")
                        st.rerun()

    # ──────────────────────────────────────────────────────────
    # TAB 4 — CONTRATOS
    # ──────────────────────────────────────────────────────────
    with tab4:
        st.subheader("📋 Contratos Registrados")

        rows_ct = model_contrato.get_all()

        # Filtros
        fc1, fc2, fc3, fc4, fc5, fc6 = st.columns(6)
        nros_opciones = ["Todos"] + sorted([r[1] for r in rows_ct]) if rows_ct else ["Todos"]
        ev_ct_opciones = ["Todos"] + sorted(list({r[2] for r in rows_ct})) if rows_ct else ["Todos"]
        fil_nro       = fc1.selectbox("Nro. Contrato", nros_opciones, key="ct_fil_nro")
        fil_ev_ct     = fc2.selectbox("Evento", ev_ct_opciones, key="ct_fil_ev")
        fil_fecha_ct  = fc3.date_input("Fecha desde", value=None, key="ct_fil_fecha")
        fil_estado_ct = fc4.selectbox("Estado", ["Todos","Pendiente","Aprobado","Rechazado","Cumplido","Firmado"], key="ct_fil_est")
        fil_monto_min = fc5.number_input("Monto mín.", min_value=0.0, value=0.0, step=100.0, key="ct_fil_mmin")
        fil_monto_max = fc6.number_input("Monto máx.", min_value=0.0, value=0.0, step=100.0, key="ct_fil_mmax")

        if rows_ct:
            df_ct = pd.DataFrame(
                rows_ct,
                columns=["ID","Nro. Contrato","Evento","Proveedor","Fecha","Estado","Monto","Firma Digital"]
            )
            # Aplicar filtros
            if fil_nro != "Todos":
                df_ct = df_ct[df_ct["Nro. Contrato"] == fil_nro]
            if fil_ev_ct != "Todos":
                df_ct = df_ct[df_ct["Evento"] == fil_ev_ct]
            if fil_fecha_ct:
                df_ct["Fecha"] = pd.to_datetime(df_ct["Fecha"], errors="coerce")
                df_ct = df_ct[df_ct["Fecha"].dt.date >= fil_fecha_ct]
            if fil_estado_ct != "Todos":
                df_ct = df_ct[df_ct["Estado"] == fil_estado_ct]
            if fil_monto_min > 0:
                df_ct = df_ct[df_ct["Monto"].astype(float) >= fil_monto_min]
            if fil_monto_max > 0:
                df_ct = df_ct[df_ct["Monto"].astype(float) <= fil_monto_max]

            if not df_ct.empty:
                df_ct_show = df_ct.drop(columns=["ID"]).copy()
                df_ct_show["Monto"] = df_ct_show["Monto"].apply(format_currency)
                df_ct_show["Fecha"] = df_ct_show["Fecha"].astype(str)
                st.dataframe(df_ct_show, use_container_width=True, hide_index=True)

                # Exportar lo filtrado a PDF
                exportar_pdf(
                    titulo="Listado de Contratos - Sistema Genesis",
                    columnas=list(df_ct_show.columns),
                    datos=[list(r) for r in df_ct_show.values.tolist()],
                    filename="contratos.pdf"
                )
            else:
                st.info("No hay contratos con esos filtros.")
        else:
            st.info("No hay contratos registrados.")

        st.divider()
        st.subheader("➕ Generar Nuevo Contrato")
        eventos_ct  = model_evento.get_activos()
        proveedores = model_proveedor.get_all()

        if not eventos_ct:
            st.warning("⚠️ No hay eventos activos para asociar un contrato.")
        elif not proveedores:
            st.warning("⚠️ No hay proveedores registrados. Pide al Jefe de Logística que los registre.")
        else:
            # Sin ID en combobox de eventos
            ev_op_ct   = {e[1]: e[0] for e in eventos_ct}
            prov_op_ct = {f"{p[1]} — {p[2]}": p[0] for p in proveedores}

            ev_sel_ct = st.selectbox("Evento *", list(ev_op_ct.keys()), key="ct_ev_sel")
            id_ev_ct  = ev_op_ct[ev_sel_ct]

            # Mostrar cliente asociado al evento seleccionado (fuera del form para actualización dinámica)
            ev_data = model_evento.get_by_id(id_ev_ct)
            if ev_data and len(ev_data) > 7:
                cliente = model_cliente.get_by_id(ev_data[7])
                if cliente:
                    st.info(f"🧑 **Cliente asociado:** {cliente[1]} &nbsp;|&nbsp; 📧 {cliente[4]} &nbsp;|&nbsp; 📱 {cliente[5] or '-'}")

            with st.form("form_nuevo_contrato_sec"):
                prov_sel_ct = st.selectbox("Proveedor *", list(prov_op_ct.keys()))
                id_prov_ct  = prov_op_ct[prov_sel_ct]

                c1, c2 = st.columns(2)
                fecha_ct = c1.date_input("Fecha del contrato *", value=date.today())
                monto_ct = c2.number_input("Monto S/ *", min_value=0.01, step=100.0)
                desc_ct  = st.text_area("Descripción del contrato *")
                firma_ct = st.checkbox("Firma digital confirmada *")

                corr = model_contrato.get_next_correlativo()
                nro  = generar_nro_contrato(corr)
                st.info(f"📝 Nro. de contrato generado: **{nro}**")

                if st.form_submit_button("Generar Contrato"):
                    errores = []
                    if monto_ct <= 0:
                        errores.append("El monto debe ser mayor a 0.")
                    if not desc_ct.strip():
                        errores.append("La descripción es obligatoria.")
                    if not firma_ct:
                        errores.append("Debe confirmar la firma digital.")
                    if errores:
                        for e in errores:
                            st.error(e)
                    else:
                        if model_contrato.create(nro, id_ev_ct, id_prov_ct, fecha_ct, monto_ct, desc_ct, firma_ct):
                            st.success(f"✅ Contrato **{nro}** generado exitosamente. Pendiente de aprobación.")
                            st.rerun()

        st.divider()
        st.subheader("✏️ Modificar Contrato")
        rows_ct_mod = model_contrato.get_all()
        if rows_ct_mod:
            ct_op = {f"{r[1]} — {r[2]} ({r[5]})": r[0] for r in rows_ct_mod}
            ct_sel_mod = st.selectbox("Seleccionar contrato a modificar", list(ct_op.keys()), key="ct_mod_sel")
            id_ct_mod  = ct_op[ct_sel_mod]
            ct_data    = model_contrato.get_by_id(id_ct_mod)

            if ct_data:
                # ct_data: id, nro, id_evento, id_proveedor, fecha, estado, monto, descripcion, firma
                st.info(f"Estado actual: **{ct_data[5]}** | Nro: **{ct_data[1]}**")
                with st.form("form_mod_contrato_sec"):
                    c1m, c2m = st.columns(2)
                    nuevo_monto = c1m.number_input("Monto S/", value=float(ct_data[6] or 0), min_value=0.01, step=100.0)
                    nueva_fecha = c2m.date_input("Fecha del contrato", value=ct_data[4])
                    nueva_desc  = st.text_area("Descripción", value=ct_data[7] or "")
                    nueva_firma = st.checkbox("Firma digital confirmada", value=bool(ct_data[8]))
                    if st.form_submit_button("💾 Guardar Cambios"):
                        if model_contrato.update(id_ct_mod, nuevo_monto, nueva_desc, nueva_fecha, nueva_firma):
                            st.success("✅ Contrato modificado correctamente.")
                            st.rerun()
