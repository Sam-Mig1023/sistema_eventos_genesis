import streamlit as st
import pandas as pd
from datetime import date
from auth.roles import requiere_rol
from cu1_contratos import model_contrato, model_cliente
from cu3_recursos import model_proveedor
from cu2_planificacion import model_evento
from shared.utils import format_currency, generar_nro_contrato, exportar_pdf

def show():
    requiere_rol(['Administrador', 'Jefe de Eventos'])
    st.title("📄 Gestión de Contratos")
    tab1, tab2 = st.tabs(["📋 Contratos Existentes", "➕ Nuevo Contrato"])

    # ── Contratos existentes ──────────────────────────────────
    with tab1:
        # Filtros
        fc1, fc2, fc3, fc4, fc5, fc6 = st.columns(6)
        numero_contrato = ["Todos"] + sorted([r[1] for r in model_contrato.get_all()])
        fil_nro      = fc1.selectbox("Nro. Contrato", numero_contrato, key="jf_fil_nro")
        eventos_opciones = ["Todos"] + sorted(list({r[2] for r in model_contrato.get_all()}))
        fil_ev       = fc2.selectbox("Evento", eventos_opciones, key="jf_fil_ev")
        fil_fecha    = fc3.date_input("Fecha desde", value=None, key="jf_fil_fecha")
        fil_estado   = fc4.selectbox("Estado", ["Todos","Pendiente","Aprobado","Rechazado","Cumplido","Firmado"], key="jf_fil_est")
        fil_min      = fc5.number_input("Monto mín.", min_value=0.0, value=0.0, step=100.0, key="jf_fil_mmin")
        fil_max      = fc6.number_input("Monto máx.", min_value=0.0, value=0.0, step=100.0, key="jf_fil_mmax")

        rows = model_contrato.get_all()
        if rows:
            df = pd.DataFrame(rows, columns=["ID","Nro. Contrato","Evento","Proveedor","Fecha","Estado","Monto","Firma Digital"])
            if fil_nro!= "Todos":
                df = df[df["Nro. Contrato"]==fil_nro]
            if fil_ev != "Todos":
                df = df[df["Evento"] == fil_ev]
            if fil_fecha:
                df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
                df = df[df["Fecha"].dt.date >= fil_fecha]
            if fil_estado != "Todos":
                df = df[df["Estado"] == fil_estado]
            if fil_min > 0:
                df = df[df["Monto"].astype(float) >= fil_min]
            if fil_max > 0:
                df = df[df["Monto"].astype(float) <= fil_max]

            if not df.empty:
                df_show = df.drop(columns=["ID"]).copy()
                df_show["Monto"] = df_show["Monto"].apply(lambda x: format_currency(x))
                df_show["Fecha"] = df_show["Fecha"].astype(str)
                st.dataframe(df_show, use_container_width=True, hide_index=True)

                exportar_pdf(
                    titulo="Listado de Contratos - Sistema Genesis",
                    columnas=list(df_show.columns),
                    datos=[list(r) for r in df_show.values.tolist()],
                    filename="contratos_jefe.pdf"
                )
            else:
                st.info("No hay contratos con esos filtros.")
        else:
            st.info("No hay contratos registrados.")

        st.divider()
        st.subheader("Gestionar Contrato")

        rows_all = model_contrato.get_all()
        if rows_all:
            ct_op = {f"{r[1]} — {r[2]} ({r[5]})": r[0] for r in rows_all}
            ct_sel = st.selectbox("Seleccionar contrato", list(ct_op.keys()), key="jf_ct_sel")
            id_ct  = ct_op[ct_sel]
            contrato = model_contrato.get_by_id(int(id_ct))
        else:
            contrato = None

        if contrato:
            (cid, nro, id_ev, id_prov, fecha, estado, monto, desc, firma) = contrato
            st.info(f"**Contrato:** {nro} | **Estado:** {estado} | **Monto:** {format_currency(monto)}")

            c1, c2, c3, c4 = st.columns(4)
            if estado == 'Pendiente':
                if c1.button("✅ Aprobar"):
                    if model_contrato.cambiar_estado(cid, 'Aprobado'):
                        st.success("Contrato aprobado.")
                        st.rerun()
                if c2.button("❌ Rechazar"):
                    if model_contrato.cambiar_estado(cid, 'Rechazado'):
                        st.warning("Contrato rechazado.")
                        st.rerun()

            if estado in ('Aprobado', 'Firmado'):
                if c3.button("🤝 Confirmar Cumplimiento"):
                    model_contrato.confirmar_cumplimiento(cid)
                    st.success("Contrato marcado como Cumplido.")
                    st.rerun()

            with st.expander("✏️ Modificar Contrato"):
                with st.form("form_mod_contrato"):
                    c1m, c2m = st.columns(2)
                    nuevo_monto = c1m.number_input("Monto", value=float(monto or 0), min_value=0.0)
                    nueva_fecha = c2m.date_input("Fecha", value=fecha)
                    nueva_desc  = st.text_area("Descripción", value=desc or "")
                    nueva_firma = st.checkbox("Firma digital", value=firma)
                    if st.form_submit_button("Guardar Cambios"):
                        model_contrato.update(cid, nuevo_monto, nueva_desc, nueva_fecha, nueva_firma)
                        st.success("Contrato modificado.")
                        st.rerun()

    # ── Nuevo contrato ────────────────────────────────────────
    with tab2:
        eventos    = model_evento.get_activos()
        proveedores = model_proveedor.get_all()

        if not eventos:
            st.warning("No hay eventos activos.")
            return
        if not proveedores:
            st.warning("No hay proveedores registrados.")
            return

        # Sin ID en combobox
        ev_opciones   = {e[1]: e[0] for e in eventos}
        prov_opciones = {f"{p[1]} - {p[2]}": p[0] for p in proveedores}

        ev_sel = st.selectbox("Evento *", list(ev_opciones.keys()), key="jf_ev_new")
        id_ev_sel = ev_opciones[ev_sel]

        # Cliente dinámico (fuera del form)
        ev_data = model_evento.get_by_id(id_ev_sel)
        if ev_data and len(ev_data) > 7:
            cliente = model_cliente.get_by_id(ev_data[7])
            if cliente:
                st.info(f"🧑 **Cliente:** {cliente[1]} &nbsp;|&nbsp; 📧 {cliente[4]} &nbsp;|&nbsp; 📱 {cliente[5] or '-'}")

        with st.form("form_nuevo_contrato"):
            st.subheader("Generar Nuevo Contrato")
            prov_sel    = st.selectbox("Proveedor *", list(prov_opciones.keys()))
            id_prov_sel = prov_opciones[prov_sel]

            c1, c2 = st.columns(2)
            fecha_contrato = c1.date_input("Fecha del contrato *", value=date.today())
            monto          = c2.number_input("Monto *", min_value=0.01, step=100.0)
            descripcion    = st.text_area("Descripción del contrato *")
            firma_digital  = st.checkbox("Firma digital confirmada *")

            corr = model_contrato.get_next_correlativo()
            nro  = generar_nro_contrato(corr)
            st.info(f"Nro. de contrato generado: **{nro}**")

            if st.form_submit_button("Generar Contrato"):
                errores = []
                if monto <= 0:
                    errores.append("El monto debe ser mayor a 0.")
                if not descripcion.strip():
                    errores.append("La descripción es obligatoria.")
                if not firma_digital:
                    errores.append("Debe confirmar la firma digital.")
                if errores:
                    for e in errores:
                        st.error(e)
                else:
                    if model_contrato.create(nro, id_ev_sel, id_prov_sel, fecha_contrato, monto, descripcion, firma_digital):
                        st.success(f"Contrato **{nro}** creado exitosamente.")
                        st.rerun()
