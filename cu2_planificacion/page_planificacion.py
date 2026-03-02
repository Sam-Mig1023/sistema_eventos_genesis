import streamlit as st
import pandas as pd
from datetime import date
from io import BytesIO
from docx import Document
from fpdf import FPDF
from auth.roles import requiere_rol, check_rol
from cu2_planificacion import model_evento, model_plan_evento, model_requerimiento, model_cotizacion
from cu3_recursos import model_proveedor, model_recurso, model_orden_compra
from shared.utils import format_currency

def show():
    requiere_rol(['Administrador', 'Jefe de Planificación', 'Jefe de Eventos'])
    st.title("📋 Gestión de Planificación de Eventos")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📅 Eventos", "📝 Plan del Evento", "📦 Requerimientos", "💰 Cotizaciones", "🧭 Asistente"])

    # ── TAB 1: Eventos ────────────────────────────────────────
    with tab1:
        st.subheader("Registrar Nuevo Evento")
        clientes_rows = []
        from cu1_contratos import model_cliente
        clientes_rows = model_cliente.get_activos()
        cli_opciones = {f"{c[1]} (ID:{c[0]})": c[0] for c in clientes_rows}

        with st.form("form_evento"):
            c1, c2 = st.columns(2)
            nombre       = c1.text_input("Nombre del evento *")
            tipo_evento  = c2.selectbox("Tipo de evento", ["Corporativo","Social","Institucional","Cultural","Deportivo","Otro"])
            lugar_evento = c1.text_input("Lugar")
            fecha_evento = c2.date_input("Fecha del evento")
            monto_evento = st.number_input("Monto estimado S/", min_value=0.0)
            cliente_sel  = st.selectbox("Cliente *", list(cli_opciones.keys()) if cli_opciones else ["Sin clientes"])
            if st.form_submit_button("Registrar Evento"):
                if not nombre or not cli_opciones:
                    st.error("Nombre y cliente son obligatorios.")
                else:
                    id_cli = cli_opciones[cliente_sel]
                    if model_evento.create(nombre, tipo_evento, lugar_evento, fecha_evento, monto_evento, id_cli):
                        st.success(f"Evento '{nombre}' registrado.")
                        st.rerun()

        st.divider()
        st.subheader("Listado de Eventos")
        rows = model_evento.get_all()
        if rows:
            st.subheader("Buscar evento")
            q = st.text_input("ID o nombre", key="ev_q")
            filtered = rows
            if q:
                qq = q.strip().lower()
                if qq.isdigit():
                    filtered = [r for r in rows if str(r[0]) == qq]
                else:
                    filtered = [r for r in rows if qq in str(r[1]).lower()]
            st.subheader("Listado de eventos")
            hdr = st.columns([1, 3, 2, 3, 2, 2, 2, 1])
            hdr[0].markdown("**ID**")
            hdr[1].markdown("**Nombre**")
            hdr[2].markdown("**Tipo**")
            hdr[3].markdown("**Lugar**")
            hdr[4].markdown("**Fecha**")
            hdr[5].markdown("**Monto**")
            hdr[6].markdown("**Estado**")
            hdr[7].markdown("**Acciones**")
            for r in filtered:
                cols = st.columns([1, 3, 2, 3, 2, 2, 2, 1])
                cols[0].write(str(r[0]))
                cols[1].write(str(r[1]))
                cols[2].write(str(r[2]))
                cols[3].write(str(r[3] or ""))
                cols[4].write(str(r[4]))
                cols[5].write(format_currency(r[5] or 0))
                cols[6].write(str(r[6]))
                if cols[7].button("✏️ Editar", key=f"ev_row_edit_{r[0]}"):
                    st.session_state[f"ev_row_editing_{r[0]}"] = True
                    st.session_state[f"ev_row_nombre_{r[0]}"] = r[1]
                    st.session_state[f"ev_row_tipo_{r[0]}"] = r[2]
                    st.session_state[f"ev_row_lugar_{r[0]}"] = r[3] or ""
                    st.session_state[f"ev_row_fecha_{r[0]}"] = r[4]
                    st.session_state[f"ev_row_monto_{r[0]}"] = float(r[5] or 0)
                    st.rerun()
                if st.session_state.get(f"ev_row_editing_{r[0]}", False):
                    with st.expander(f"Editar Evento ID {r[0]} - {r[1]}", expanded=True):
                        f1, f2 = st.columns(2)
                        nombre_e = f1.text_input("Nombre", value=st.session_state.get(f"ev_row_nombre_{r[0]}", r[1]), key=f"ev_row_nombre_input_{r[0]}")
                        tipos = ["Corporativo","Social","Institucional","Cultural","Deportivo","Otro"]
                        idx = tipos.index(st.session_state.get(f"ev_row_tipo_{r[0]}", r[2])) if st.session_state.get(f"ev_row_tipo_{r[0]}", r[2]) in tipos else 0
                        tipo_e = f2.selectbox("Tipo", tipos, index=idx, key=f"ev_row_tipo_input_{r[0]}")
                        lugar_e = f1.text_input("Lugar", value=st.session_state.get(f"ev_row_lugar_{r[0]}", r[3] or ""), key=f"ev_row_lugar_input_{r[0]}")
                        fecha_e = f2.date_input("Fecha", value=st.session_state.get(f"ev_row_fecha_{r[0]}", date.today()), key=f"ev_row_fecha_input_{r[0]}")
                        monto_e = st.number_input("Monto S/", min_value=0.0, value=st.session_state.get(f"ev_row_monto_{r[0]}", float(r[5] or 0)), key=f"ev_row_monto_input_{r[0]}")
                        if st.button("Guardar cambios", key=f"ev_row_save_{r[0]}"):
                            if model_evento.update(r[0], nombre_e, tipo_e, lugar_e, fecha_e, monto_e):
                                st.success("Evento actualizado.")
                                st.session_state.pop(f"ev_row_editing_{r[0]}", None)
                                st.rerun()

            if check_rol(['Administrador','Jefe de Eventos']):
                st.subheader("Cambiar Estado del Evento")
                from config import ESTADOS_EVENTO
                id_ev = st.number_input("ID del evento", min_value=1, step=1, key="ev_estado_id")
                nuevo_est = st.selectbox("Nuevo estado", ESTADOS_EVENTO, key="ev_estado_sel")
                if st.button("Actualizar Estado"):
                    if model_evento.cambiar_estado(int(id_ev), nuevo_est):
                        st.success("Estado actualizado.")
                        st.rerun()

    # ── TAB 2: Plan del Evento ────────────────────────────────
    with tab2:
        eventos_activos = model_evento.get_activos()
        if not eventos_activos:
            st.warning("No hay eventos activos.")
        else:
            ev_opciones = {f"{e[1]} (ID:{e[0]})": e[0] for e in eventos_activos}
            ev_sel = st.selectbox("Seleccionar Evento", list(ev_opciones.keys()), key="plan_ev_sel")
            id_ev_sel = ev_opciones[ev_sel]

            planes = model_plan_evento.get_by_evento(id_ev_sel)
            if planes:
                st.subheader("Planes registrados")
                hdr_p = st.columns([1, 2, 2, 2, 3, 1])
                hdr_p[0].markdown("**ID**")
                hdr_p[1].markdown("**Fecha Elab.**")
                hdr_p[2].markdown("**Presupuesto**")
                hdr_p[3].markdown("**Estado**")
                hdr_p[4].markdown("**Descripción**")
                hdr_p[5].markdown("**Acciones**")
                for row in planes:
                    cols_p = st.columns([1, 2, 2, 2, 3, 1])
                    cols_p[0].write(str(row[0]))
                    cols_p[1].write(str(row[1]))
                    cols_p[2].write(format_currency(row[2] or 0))
                    cols_p[3].write(str(row[3]))
                    desc_txt = str(row[4] or "")
                    cols_p[4].write(desc_txt if len(desc_txt) <= 80 else desc_txt[:80] + "…")
                    ac1, ac2 = cols_p[5].columns(2)
                    if ac1.button("👁️ Mostrar", key=f"plan_row_show_{row[0]}"):
                        st.session_state[f"plan_row_showing_{row[0]}"] = True
                        st.session_state[f"plan_row_desc_view_{row[0]}"] = desc_txt
                        st.rerun()
                    if ac2.button("✏️ Editar", key=f"plan_row_edit_{row[0]}"):
                        st.session_state[f"plan_row_editing_{row[0]}"] = True
                        st.session_state[f"plan_row_fecha_{row[0]}"] = row[1]
                        st.session_state[f"plan_row_pres_{row[0]}"] = float(row[2] or 0)
                        st.session_state[f"plan_row_desc_{row[0]}"] = row[4] or ""
                        st.rerun()
                    if st.session_state.get(f"plan_row_editing_{row[0]}", False):
                        with st.expander(f"Editar Plan ID {row[0]}", expanded=True):
                            f1, f2 = st.columns(2)
                            fecha_elab_e = f1.date_input("Fecha elaboración", value=st.session_state.get(f"plan_row_fecha_{row[0]}", date.today()), key=f"plan_row_fecha_input_{row[0]}")
                            presupuesto_e = f2.number_input("Presupuesto S/", min_value=0.0, step=100.0, value=st.session_state.get(f"plan_row_pres_{row[0]}", float(row[2] or 0)), key=f"plan_row_pres_input_{row[0]}")
                            descripcion_e = st.text_area("Descripción", value=st.session_state.get(f"plan_row_desc_{row[0]}", row[4] or ""), key=f"plan_row_desc_input_{row[0]}")
                            if st.button("Guardar cambios", key=f"plan_row_save_{row[0]}"):
                                if model_plan_evento.update(row[0], fecha_elab_e, presupuesto_e, descripcion_e):
                                    st.success("Plan actualizado.")
                                    st.session_state.pop(f"plan_row_editing_{row[0]}", None)
                                    st.rerun()
                for row in planes:
                    if st.session_state.get(f"plan_row_showing_{row[0]}", False):
                        left, center, right = st.columns([1, 2, 1])
                        with center:
                            st.subheader("Descripción del Plan")
                            cur_desc = st.session_state.get(f"plan_row_desc_view_{row[0]}", str(row[4] or ""))
                            desc_input_key = f"plan_desc_input_{row[0]}"
                            desc_val = st.text_area("Descripción", value=cur_desc, key=desc_input_key, height=300)
                            up = st.file_uploader("Importar .docx", type=["docx"], key=f"plan_docx_upload_{row[0]}")
                            if up:
                                d = Document(up)
                                txt = "\n".join([p.text for p in d.paragraphs])
                                st.session_state[desc_input_key] = txt
                                st.rerun()
                            c1, c2, c3 = st.columns(3)
                            if c1.button("Guardar cambios", key=f"plan_desc_save_{row[0]}"):
                                cur = model_plan_evento.get_by_id(row[0])
                                if cur and model_plan_evento.update(row[0], cur[2], cur[3], st.session_state.get(desc_input_key, cur_desc)):
                                    st.success("Descripción actualizada.")
                                    st.session_state.pop(f"plan_row_showing_{row[0]}", None)
                                    st.rerun()
                            doc_buf = BytesIO()
                            docx = Document()
                            docx.add_heading(f"Plan ID {row[0]}", 0)
                            docx.add_paragraph(desc_val or "")
                            docx.save(doc_buf)
                            doc_buf.seek(0)
                            c2.download_button("Exportar DOCX", data=doc_buf, file_name=f"Plan_{row[0]}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                            pdf = FPDF()
                            pdf.add_page()
                            pdf.set_auto_page_break(auto=True, margin=15)
                            pdf.set_font("Arial", size=12)
                            for line in (desc_val or "").splitlines():
                                pdf.multi_cell(0, 8, line)
                            pdf_bytes = pdf.output(dest="S").encode("latin-1")
                            c3.download_button("Exportar PDF", data=pdf_bytes, file_name=f"Plan_{row[0]}.pdf", mime="application/pdf")
                            if st.button("Cerrar", key=f"plan_desc_close_{row[0]}"):
                                st.session_state.pop(f"plan_row_showing_{row[0]}", None)
                                st.rerun()

                id_plan = st.number_input("ID del plan a gestionar", min_value=1, step=1)
                plan = model_plan_evento.get_by_id(int(id_plan))
                if plan:
                    (pid, pev, pfecha, ppres, pest, pdesc) = plan
                    st.info(f"Estado actual: **{pest}**")
                    col1, col2, col3, col4 = st.columns(4)
                    if pest == 'Borrador':
                        if col1.button("📤 Enviar a Revisión"):
                            model_plan_evento.cambiar_estado(pid, 'En Revisión')
                            st.rerun()
                    if pest == 'En Revisión' and check_rol(['Administrador','Jefe de Eventos']):
                        if col2.button("✅ Aprobar Plan"):
                            model_plan_evento.cambiar_estado(pid, 'Aprobado')
                            model_evento.cambiar_estado(pev, 'Plan Aprobado')
                            st.success("Plan aprobado.")
                            st.rerun()
                        if col3.button("🔄 Solicitar Ajustes"):
                            model_plan_evento.cambiar_estado(pid, 'Rechazado')
                            st.warning("Se solicitaron ajustes al plan.")
                            st.rerun()
                    if pest == 'Aprobado':
                        if col4.button("📌 Confirmar Planificación"):
                            model_plan_evento.cambiar_estado(pid, 'Registrado')
                            model_evento.cambiar_estado(pev, 'Confirmada')
                            st.success("Planificación confirmada. Evento listo para ejecución.")
                            st.rerun()

            st.divider()
            st.subheader("Elaborar Nuevo Plan")
            with st.form("form_nuevo_plan"):
                fecha_elab  = st.date_input("Fecha de elaboración", value=date.today())
                presupuesto = st.number_input("Presupuesto S/", min_value=0.0, step=100.0)
                descripcion = st.text_area("Descripción del plan")
                if st.form_submit_button("Guardar Plan"):
                    if model_plan_evento.create(id_ev_sel, fecha_elab, presupuesto, descripcion):
                        st.success("Plan creado.")
                        st.rerun()

    # ── TAB 3: Requerimientos ─────────────────────────────────
    with tab3:
        eventos_r = model_evento.get_activos()
        if not eventos_r:
            st.warning("No hay eventos activos.")
        else:
            ev_op_r = {f"{e[1]} (ID:{e[0]})": e[0] for e in eventos_r}
            ev_sel_r = st.selectbox("Evento", list(ev_op_r.keys()), key="req_ev_sel")
            id_ev_r  = ev_op_r[ev_sel_r]

            reqs = model_requerimiento.get_by_evento(id_ev_r)
            if reqs:
                st.subheader("Requerimientos registrados")
                hdr_r = st.columns([1, 5, 2, 2, 2])
                hdr_r[0].markdown("**ID**")
                hdr_r[1].markdown("**Descripción**")
                hdr_r[2].markdown("**Tipo**")
                hdr_r[3].markdown("**Cantidad**")
                hdr_r[4].markdown("**Acciones**")
                for req in reqs:
                    rid, rdesc, rtipo, rcant = req
                    cols_r = st.columns([1, 5, 2, 2, 2])
                    cols_r[0].write(str(rid))
                    cols_r[1].write(str(rdesc))
                    cols_r[2].write(str(rtipo))
                    cols_r[3].write(str(rcant))
                    ac1, ac2 = cols_r[4].columns(2)
                    if ac1.button("✏️ Editar", key=f"req_row_edit_{rid}"):
                        st.session_state[f"req_row_editing_{rid}"] = True
                        st.session_state[f"req_row_desc_{rid}"] = rdesc or ""
                        st.session_state[f"req_row_tipo_{rid}"] = rtipo
                        st.session_state[f"req_row_cant_{rid}"] = int(rcant)
                        st.rerun()
                    if ac2.button("🗑️ Eliminar", key=f"req_row_delete_{rid}"):
                        if model_requerimiento.delete(rid):
                            st.success("Requerimiento eliminado.")
                            st.rerun()
                    if st.session_state.get(f"req_row_editing_{rid}", False):
                        with st.expander(f"Editar Requerimiento ID {rid}", expanded=True):
                            e1, e2 = st.columns(2)
                            desc_new = e1.text_input("Descripción", value=st.session_state.get(f"req_row_desc_{rid}", rdesc or ""), key=f"req_row_desc_input_{rid}")
                            tipos = model_requerimiento.TIPOS_RECURSO
                            idx_t = tipos.index(st.session_state.get(f"req_row_tipo_{rid}", rtipo)) if st.session_state.get(f"req_row_tipo_{rid}", rtipo) in tipos else 0
                            tipo_new = e2.selectbox("Tipo", tipos, index=idx_t, key=f"req_row_tipo_input_{rid}")
                            cant_new = st.number_input("Cantidad", min_value=1, step=1, value=st.session_state.get(f"req_row_cant_{rid}", int(rcant)), key=f"req_row_cant_input_{rid}")
                            if st.button("Guardar cambios", key=f"req_row_save_{rid}"):
                                if model_requerimiento.update(rid, desc_new, tipo_new, int(cant_new)):
                                    st.success("Requerimiento actualizado.")
                                    st.session_state.pop(f"req_row_editing_{rid}", None)
                                    st.rerun()

                # Verificar disponibilidad
                st.subheader("Verificar Disponibilidad Interna")
                for req in reqs:
                    disponibles = model_recurso.get_disponibles_por_tipo(req[2])
                    total_disp = sum(int(r[3]) for r in disponibles)
                    if total_disp >= req[3]:
                        st.success(f"✅ {req[1]}: {total_disp} disponibles (necesita {req[3]})")
                    else:
                        st.warning(f"⚠️ {req[1]}: solo {total_disp} disponibles (necesita {req[3]}) — considerar cotización")
            else:
                st.info("No hay requerimientos para este evento.")

            st.divider()
            with st.form("form_nuevo_req"):
                st.subheader("Agregar Requerimiento")
                desc_r   = st.text_input("Descripción *")
                tipo_r   = st.selectbox("Tipo de recurso", model_requerimiento.TIPOS_RECURSO)
                cant_r   = st.number_input("Cantidad", min_value=1, step=1)
                if st.form_submit_button("Agregar"):
                    if not desc_r:
                        st.error("La descripción es obligatoria.")
                    elif model_requerimiento.create(id_ev_r, desc_r, tipo_r, cant_r):
                        st.success("Requerimiento agregado.")
                        st.rerun()

    # ── TAB 4: Cotizaciones ───────────────────────────────────
    with tab4:
        eventos_c = model_evento.get_activos()
        ev_op_c   = {f"{e[1]} (ID:{e[0]})": e[0] for e in eventos_c}
        ev_sel_c  = st.selectbox("Evento", list(ev_op_c.keys()), key="cot_ev_sel")
        id_ev_c   = ev_op_c[ev_sel_c]

        cots = model_cotizacion.get_by_evento(id_ev_c)
        if cots:
            df_cot = pd.DataFrame(cots, columns=["ID","Proveedor","Fecha","Monto","Estado","Descripción"])
            df_cot["Monto"] = df_cot["Monto"].apply(format_currency)
            st.dataframe(df_cot, use_container_width=True)

            id_cot = st.number_input("ID cotización", min_value=1, step=1)
            cot = model_cotizacion.get_by_id(int(id_cot))
            if cot and cot[5] == 'Pendiente':
                c1, c2 = st.columns(2)
                if c1.button("✅ Aceptar Cotización"):
                    model_cotizacion.cambiar_estado(id_cot, 'Aceptada')
                    st.success("Cotización aceptada. Puedes generar la OC en el módulo de Recursos.")
                    st.rerun()
                if c2.button("❌ Rechazar Cotización"):
                    model_cotizacion.cambiar_estado(id_cot, 'Rechazada')
                    st.warning("Cotización rechazada.")
                    st.rerun()

        st.divider()
        proveedores = model_proveedor.get_all()
        prov_op = {f"{p[1]} (ID:{p[0]})": p[0] for p in proveedores}
        with st.form("form_nueva_cot"):
            st.subheader("Registrar Cotización")
            prov_sel = st.selectbox("Proveedor *", list(prov_op.keys()))
            fecha_c  = st.date_input("Fecha", value=date.today())
            monto_c  = st.number_input("Monto S/", min_value=0.0)
            desc_c   = st.text_area("Descripción")
            if st.form_submit_button("Guardar Cotización"):
                id_prov_c = prov_op[prov_sel]
                if model_cotizacion.create(id_prov_c, id_ev_c, fecha_c, monto_c, desc_c):
                    st.success("Cotización registrada.")
                    st.rerun()

    with tab5:
        eventos = model_evento.get_activos()
        if not eventos:
            st.warning("No hay eventos activos.")
        else:
            ev_ops = {f"{e[1]} (ID:{e[0]})": e[0] for e in eventos}
            ev_label = st.selectbox("Seleccionar Evento", list(ev_ops.keys()), key="asist_ev")
            id_ev = ev_ops[ev_label]
            info_ev = model_evento.get_by_id(id_ev)
            planes_ev = model_plan_evento.get_by_evento(id_ev)
            reqs_ev = model_requerimiento.get_by_evento(id_ev)
            cots_ev = model_cotizacion.get_by_evento(id_ev)
            st.subheader("Resumen")
            col_a, col_b = st.columns(2)
            with col_a:
                if info_ev:
                    st.metric("Evento", info_ev[1])
                    st.metric("Estado", info_ev[6])
                    st.metric("Fecha", str(info_ev[4]))
                    st.metric("Monto", format_currency(info_ev[5] or 0))
            with col_b:
                st.metric("Planes", len(planes_ev))
                st.metric("Requerimientos", len(reqs_ev))
                st.metric("Cotizaciones", len(cots_ev))
            st.divider()
            st.subheader("Asignar")
            exp1 = st.expander("Nuevo Plan")
            with exp1:
                f1, f2 = st.columns(2)
                fecha_elab = f1.date_input("Fecha elaboración", value=date.today(), key="as_plan_fecha")
                presupuesto = f2.number_input("Presupuesto S/", min_value=0.0, step=100.0, key="as_plan_pres")
                desc = st.text_area("Descripción del plan", key="as_plan_desc")
                if st.button("Guardar Plan", key="as_plan_btn"):
                    if model_plan_evento.create(id_ev, fecha_elab, presupuesto, desc):
                        st.success("Plan creado.")
                        st.rerun()
            exp2 = st.expander("Nuevo Requerimiento")
            with exp2:
                d1, d2 = st.columns(2)
                desc_r = d1.text_input("Descripción *", key="as_req_desc")
                tipo_r = d2.selectbox("Tipo de recurso", model_requerimiento.TIPOS_RECURSO, key="as_req_tipo")
                cant_r = st.number_input("Cantidad", min_value=1, step=1, key="as_req_cant")
                if st.button("Agregar Requerimiento", key="as_req_btn"):
                    if desc_r and model_requerimiento.create(id_ev, desc_r, tipo_r, cant_r):
                        st.success("Requerimiento agregado.")
                        st.rerun()
            exp3 = st.expander("Nueva Cotización")
            with exp3:
                provs = model_proveedor.get_all()
                prov_ops = {f"{p[1]} (ID:{p[0]})": p[0] for p in provs}
                prov_label = st.selectbox("Proveedor *", list(prov_ops.keys()) if prov_ops else ["Sin proveedores"], key="as_cot_prov")
                fecha_c = st.date_input("Fecha", value=date.today(), key="as_cot_fecha")
                monto_c = st.number_input("Monto S/", min_value=0.0, key="as_cot_monto")
                desc_c = st.text_area("Descripción", key="as_cot_desc")
                if st.button("Guardar Cotización", key="as_cot_btn"):
                    if prov_ops and model_cotizacion.create(prov_ops[prov_label], id_ev, fecha_c, monto_c, desc_c):
                        st.success("Cotización registrada.")
                        st.rerun()
            st.divider()
            st.subheader("Listados")
            if planes_ev:
                df_p = pd.DataFrame(planes_ev, columns=["ID","Fecha","Presupuesto","Estado","Descripción"])
                df_p["Presupuesto"] = df_p["Presupuesto"].apply(lambda x: format_currency(x or 0))
                st.dataframe(df_p, use_container_width=True)
            else:
                st.info("Sin planes.")
            if reqs_ev:
                df_r = pd.DataFrame(reqs_ev, columns=["ID","Descripción","Tipo","Cantidad"])
                st.dataframe(df_r, use_container_width=True)
            else:
                st.info("Sin requerimientos.")
            if cots_ev:
                df_c = pd.DataFrame(cots_ev, columns=["ID","Proveedor","Fecha","Monto","Estado","Descripción"])
                df_c["Monto"] = df_c["Monto"].apply(lambda x: format_currency(x or 0))
                st.dataframe(df_c, use_container_width=True)
            else:
                st.info("Sin cotizaciones.")
            st.divider()
            doc = Document()
            doc.add_heading("Planificación de Evento", 0)
            if info_ev:
                p = doc.add_paragraph()
                p.add_run("Evento: ").bold = True
                p.add_run(str(info_ev[1]))
                p = doc.add_paragraph()
                p.add_run("Estado: ").bold = True
                p.add_run(str(info_ev[6]))
                p = doc.add_paragraph()
                p.add_run("Fecha: ").bold = True
                p.add_run(str(info_ev[4]))
                p = doc.add_paragraph()
                p.add_run("Monto: ").bold = True
                p.add_run(str(format_currency(info_ev[5] or 0)))
            doc.add_heading("Planes", level=1)
            if planes_ev:
                table_p = doc.add_table(rows=1, cols=5)
                hdr = table_p.rows[0].cells
                hdr[0].text = "ID"
                hdr[1].text = "Fecha"
                hdr[2].text = "Presupuesto"
                hdr[3].text = "Estado"
                hdr[4].text = "Descripción"
                for row in planes_ev:
                    cells = table_p.add_row().cells
                    cells[0].text = str(row[0])
                    cells[1].text = str(row[1])
                    cells[2].text = str(format_currency(row[2] or 0))
                    cells[3].text = str(row[3])
                    cells[4].text = str(row[4] or "")
            doc.add_heading("Requerimientos", level=1)
            if reqs_ev:
                table_r = doc.add_table(rows=1, cols=4)
                hdr = table_r.rows[0].cells
                hdr[0].text = "ID"
                hdr[1].text = "Descripción"
                hdr[2].text = "Tipo"
                hdr[3].text = "Cantidad"
                for row in reqs_ev:
                    cells = table_r.add_row().cells
                    cells[0].text = str(row[0])
                    cells[1].text = str(row[1])
                    cells[2].text = str(row[2])
                    cells[3].text = str(row[3])
            doc.add_heading("Cotizaciones", level=1)
            if cots_ev:
                table_c = doc.add_table(rows=1, cols=6)
                hdr = table_c.rows[0].cells
                hdr[0].text = "ID"
                hdr[1].text = "Proveedor"
                hdr[2].text = "Fecha"
                hdr[3].text = "Monto"
                hdr[4].text = "Estado"
                hdr[5].text = "Descripción"
                for row in cots_ev:
                    cells = table_c.add_row().cells
                    cells[0].text = str(row[0])
                    cells[1].text = str(row[1])
                    cells[2].text = str(row[2])
                    cells[3].text = str(format_currency(row[3] or 0))
                    cells[4].text = str(row[4])
                    cells[5].text = str(row[5] or "")
            buf = BytesIO()
            doc.save(buf)
            buf.seek(0)
            st.download_button("📥 Exportar a Word", data=buf, file_name=f"Planificacion_Evento_{id_ev}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
