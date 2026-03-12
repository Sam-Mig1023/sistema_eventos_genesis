import streamlit as st
import pandas as pd
from auth.roles import requiere_rol
from cu1_contratos import model_cliente
from shared.utils import validate_email, exportar_pdf

TIPOS_CLIENTE = ["Persona Natural", "Empresa", "Institución"]
ESTADOS_CLIENTE = ["Activo", "Inactivo"]

def show():
    requiere_rol(['Administrador', 'Secretaria de Eventos', 'Jefe de Eventos'])
    st.title("👥 Gestión de Clientes")
    tab1, tab2, tab3 = st.tabs(["📋 Listado y Búsqueda", "➕ Nuevo Cliente", "✏️ Editar Cliente"])

    # ── Listado y búsqueda ────────────────────────────────────
    with tab1:
        f1, f2, f3, f4, f5 = st.columns(5)
        nombres_opciones = ["Todos"] + sorted([r[1] for r in model_cliente.get_all()])
        filtro_nombre = f1.selectbox("Nombre", nombres_opciones, key="pc_fil_nombre")
        filtro_tipo   = f2.selectbox("Tipo", ["Todos"] + TIPOS_CLIENTE, key="pc_fil_tipo")
        filtro_email  = f3.text_input("Email", key="pc_fil_email")
        filtro_fecha  = f4.date_input("Fecha de registro (desde)", value=None, key="pc_fil_fecha")
        filtro_estado = f5.selectbox("Estado", ["Todos", "Activo", "Inactivo"], key="pc_fil_estado")

        rows_all = model_cliente.get_all()
        cols_all = ["ID", "Nombre", "Tipo", "Dirección", "Email", "Teléfono", "Fecha Reg.", "Estado"]

        if rows_all:
            df = pd.DataFrame(rows_all, columns=cols_all)
            if filtro_nombre != "Todos":
                df = df[df["Nombre"] == filtro_nombre]
            if filtro_tipo != "Todos":
                df = df[df["Tipo"] == filtro_tipo]
            if filtro_email:
                df = df[df["Email"].str.contains(filtro_email, case=False, na=False)]
            if filtro_fecha:
                df["Fecha Reg."] = pd.to_datetime(df["Fecha Reg."], errors="coerce")
                df = df[df["Fecha Reg."].dt.date >= filtro_fecha]
            if filtro_estado != "Todos":
                df = df[df["Estado"] == filtro_estado]

            if not df.empty:
                page_size = 10
                total = len(df)
                total_pages = max(1, (total + page_size - 1) // page_size)

                pg_col1, pg_col2, pg_col3 = st.columns([1, 2, 1])
                if "pc_page" not in st.session_state:
                    st.session_state["pc_page"] = 1

                with pg_col1:
                    if st.button("◀ Anterior", key="pc_prev", disabled=st.session_state["pc_page"] <= 1):
                        st.session_state["pc_page"] -= 1
                with pg_col3:
                    if st.button("Siguiente ▶", key="pc_next", disabled=st.session_state["pc_page"] >= total_pages):
                        st.session_state["pc_page"] += 1

                pg = st.session_state["pc_page"]
                start = (pg - 1) * page_size
                df_pag = df.iloc[start:start + page_size]

                with pg_col2:
                    st.markdown(f"<div style='text-align:center;padding-top:6px'>Página <b>{pg}</b> de <b>{total_pages}</b> ({total} registros)</div>", unsafe_allow_html=True)

                st.dataframe(df_pag, use_container_width=True, hide_index=True)

                df_exp = df.copy()
                df_exp["Fecha Reg."] = df_exp["Fecha Reg."].astype(str)
                exportar_pdf(
                    titulo="Listado de Clientes - Sistema Genesis",
                    columnas=list(df_exp.columns),
                    datos=[list(r) for r in df_exp.values.tolist()],
                    filename="clientes.pdf"
                )
            else:
                st.info("No se encontraron clientes con esos filtros.")
        else:
            st.info("No hay clientes registrados.")

    # ── Nuevo cliente ─────────────────────────────────────────
    with tab2:
        with st.form("form_nuevo_cliente"):
            st.subheader("Registrar Nuevo Cliente")
            c1, c2 = st.columns(2)
            nombre       = c1.text_input("Nombre *")
            tipo_cliente = c2.selectbox("Tipo de cliente *", TIPOS_CLIENTE)
            email        = c1.text_input("Email *")
            telefono     = c2.text_input("Teléfono")
            direccion    = st.text_area("Dirección")
            submitted    = st.form_submit_button("Registrar Cliente")

        if submitted:
            if not nombre or not email:
                st.error("Nombre y email son obligatorios.")
            elif not validate_email(email):
                st.error("Email inválido.")
            else:
                if model_cliente.create(nombre, tipo_cliente, direccion, email, telefono):
                    st.success(f"Cliente '{nombre}' registrado exitosamente.")
                    st.rerun()

    # ── Editar cliente ────────────────────────────────────────
    with tab3:
        st.subheader("✏️ Editar Cliente")
        clientes_todos = model_cliente.get_all()
        if clientes_todos:
            cli_nombres = {f"{r[1]} (ID:{r[0]})": r[0] for r in clientes_todos}
            cli_sel_edit = st.selectbox("Seleccionar cliente a editar", list(cli_nombres.keys()), key="pc_edit_sel")
            id_cli_edit = cli_nombres[cli_sel_edit]
            cli_data = model_cliente.get_by_id(id_cli_edit)

            if cli_data:
                with st.form("form_editar_cliente_pc"):
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
        else:
            st.info("No hay clientes registrados.")
