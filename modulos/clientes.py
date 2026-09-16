import streamlit as st
import pandas as pd
import datetime
import time
from io import BytesIO


def render(supabase):
    st.title("👥 Gestión de Clientes")
    # Verificamos el rol actual para condicionar la vista
    rol_actual = st.session_state.get("rol", "VENDEDORA").upper()

    if rol_actual == "GERENTE":
        tabs = st.tabs(
            [
                "🔍 Directorio y Edición",
                "➕ Nuevo (Manual)",
                "📂 Importar / Exportar",
                "⚙️ Configuración",
            ]
        )
        tab1, tab2, tab3, tab4 = tabs[0], tabs[1], tabs[2], tabs[3]
    else:
        # Si es vendedora, solo ve 3 pestañas
        tabs = st.tabs(
            ["🔍 Directorio y Edición", "➕ Nuevo (Manual)", "📂 Importar / Exportar"]
        )
        tab1, tab2, tab3 = tabs[0], tabs[1], tabs[2]
        tab4 = None  # Neutralizamos la cuarta pestaña

    def obtener_tipos_cliente():
        try:
            res = (
                supabase.table("catalogo_tipos_cliente")
                .select("nombre")
                .eq("activo", True)
                .order("nombre")
                .execute()
            )
            return [t["nombre"] for t in res.data] if res.data else ["Cliente Final"]
        except:
            return ["Cliente Final"]

    opciones_dinamicas_tipo = obtener_tipos_cliente()

    # ==============================================================================
    # TAB 1: DIRECTORIO, EDICIÓN, ELIMINACIÓN Y WHATSAPP
    # ==============================================================================
    with tab1:
        st.subheader("🔍 Directorio de Clientes")

        # 1. Cargar Datos
        response = (
            supabase.table("clientes").select("*").order("nombre_completo").execute()
        )
        df_clientes = pd.DataFrame(response.data)

        if not df_clientes.empty:
            # 2. Filtros de búsqueda
            busqueda = st.text_input("Filtrar lista:", placeholder="Nombre o Cédula...")

            if busqueda:
                df_filtrado = df_clientes[
                    df_clientes["nombre_completo"].str.contains(
                        busqueda, case=False, na=False
                    )
                    | df_clientes["cedula_ruc"].str.contains(
                        busqueda, case=False, na=False
                    )
                ]
            else:
                df_filtrado = df_clientes

            # 3. Tabla Interactiva
            evento = st.dataframe(
                df_filtrado[
                    [
                        "cedula_ruc",
                        "nombre_completo",
                        "telefono",
                        "ciudad",
                        "tipo_institucion",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
                selection_mode="single-row",
                on_select="rerun",
            )

            # 4. Formulario de Edición Completo
            if evento.selection.rows:
                idx = evento.selection.rows[0]
                datos = df_filtrado.iloc[idx]

                st.divider()
                st.markdown(f"### ✏️ Editando a: :blue[{datos['nombre_completo']}]")

                with st.form("form_edicion_cli"):
                    # Fila 1: Identificación
                    c1, c2 = st.columns(2)
                    new_ced = c1.text_input("Cédula/RUC", value=datos["cedula_ruc"])
                    new_nom = c2.text_input(
                        "Nombre Completo", value=datos["nombre_completo"]
                    )

                    # Fila 2: Contacto
                    c3, c4, c5 = st.columns(3)
                    new_tel = c3.text_input(
                        "Teléfono", value=datos["telefono"] if datos["telefono"] else ""
                    )
                    new_email = c4.text_input(
                        "Email", value=datos["email"] if datos["email"] else ""
                    )
                    new_ciu = c5.text_input(
                        "Ciudad", value=datos["ciudad"] if datos["ciudad"] else ""
                    )

                    # Fila 3: Detalles Demográficos y Clasificación
                    c6, c7, c8 = st.columns(3)

                    # Manejo de Fecha (evitar errores si es None)
                    val_fecha = None
                    if datos["fecha_nacimiento"]:
                        try:
                            val_fecha = datetime.datetime.strptime(
                                str(datos["fecha_nacimiento"]), "%Y-%m-%d"
                            ).date()
                        except:
                            val_fecha = None
                    new_nac = c6.date_input(
                        "Fecha Nacimiento",
                        value=val_fecha,
                        min_value=datetime.date(1920, 1, 1),
                    )

                    # Listas desplegables inteligentes (seleccionan el valor actual si existe)
                    opc_gen = ["Masculino", "Femenino", "Otro/Empresa"]
                    idx_gen = (
                        opc_gen.index(datos["genero"])
                        if datos["genero"] in opc_gen
                        else 0
                    )
                    new_gen = c7.selectbox("Género", opc_gen, index=idx_gen)

                    # REEMPLAZO LIMPIO UTILIZANDO LA NUEVA VARIABLE DINÁMICA
                    idx_tipo = (
                        opciones_dinamicas_tipo.index(datos["tipo_institucion"])
                        if datos["tipo_institucion"] in opciones_dinamicas_tipo
                        else 0
                    )
                    new_tipo = c8.selectbox(
                        "Tipo Institución", opciones_dinamicas_tipo, index=idx_tipo
                    )

                    st.write("---")

                    # --- BOTÓN DE WHATSAPP ---
                    if new_tel:
                        # Limpiar número (quitar guiones, espacios)
                        tel_clean = "".join(filter(str.isdigit, str(new_tel)))
                        # Agregar código país si falta (Ecuador 593 por defecto)
                        if len(tel_clean) > 0 and not tel_clean.startswith("593"):
                            tel_clean = "593" + (
                                tel_clean[1:]
                                if tel_clean.startswith("0")
                                else tel_clean
                            )

                        msg = f"Hola {new_nom}, saludos de YUNPAR."
                        link_wa = (
                            f"https://wa.me/{tel_clean}?text={msg.replace(' ', '%20')}"
                        )
                        st.link_button(
                            f"📲 Chatear por WhatsApp con {new_nom}", link_wa
                        )
                    else:
                        st.caption("⚠️ Ingresa un teléfono para habilitar WhatsApp.")

                    st.write("---")

                    # Botones de Acción (Actualizar y Eliminar)
                    col_update, col_delete = st.columns([1, 1])

                    # LOGICA ACTUALIZAR
                    if col_update.form_submit_button(
                        "💾 Guardar Cambios", type="primary"
                    ):
                        try:
                            supabase.table("clientes").update(
                                {
                                    "cedula_ruc": new_ced,
                                    "nombre_completo": new_nom.upper(),
                                    "telefono": new_tel,
                                    "email": new_email,
                                    "ciudad": new_ciu,
                                    "fecha_nacimiento": (
                                        str(new_nac) if new_nac else None
                                    ),
                                    "genero": new_gen,
                                    "tipo_institucion": new_tipo,
                                }
                            ).eq("id", int(datos["id"])).execute()
                            st.success("✅ Cliente actualizado correctamente.")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al actualizar: {e}")

                    # LOGICA ELIMINAR
                    if col_delete.form_submit_button("🗑️ Eliminar Cliente"):
                        try:
                            supabase.table("clientes").delete().eq(
                                "id", int(datos["id"])
                            ).execute()
                            st.warning(
                                f"Cliente {datos['nombre_completo']} eliminado permanentemente."
                            )
                            time.sleep(1.5)
                            st.rerun()
                        except Exception as e:
                            st.error(
                                f"No se puede eliminar: Probablemente tiene órdenes o cotizaciones asociadas. Error: {e}"
                            )

    # ==============================================================================
    # TAB 2: NUEVO CLIENTE (FORMULARIO COMPLETO)
    # ==============================================================================
    with tab2:
        if "form_id" not in st.session_state:
            st.session_state["form_id"] = 0
        with st.form(key=f"form_cli_{st.session_state['form_id']}"):
            st.subheader("Registrar Nuevo Cliente")
            c1, c2 = st.columns(2)
            ced = c1.text_input("Cédula/RUC *")
            nom = c2.text_input("Nombre Completo *")

            c3, c4 = st.columns(2)
            tel = c3.text_input("Teléfono")
            email = c4.text_input("Email")

            c5, c6 = st.columns(2)
            ciu = c5.text_input("Ciudad")
            tipo = c6.selectbox("Tipo", opciones_dinamicas_tipo)

            c7, c8 = st.columns(2)
            genero = c7.selectbox("Género", ["Masculino", "Femenino", "Otro/Empresa"])
            nacimiento = c8.date_input(
                "Fecha Nacimiento", value=None, min_value=datetime.date(1900, 1, 1)
            )

            if st.form_submit_button("💾 Guardar Cliente Nuevo"):
                if ced and nom:
                    try:
                        supabase.table("clientes").insert(
                            {
                                "cedula_ruc": ced,
                                "nombre_completo": nom.upper(),
                                "telefono": tel,
                                "email": email,
                                "ciudad": ciu,
                                "tipo_institucion": tipo,
                                "genero": genero,
                                "fecha_nacimiento": (
                                    str(nacimiento) if nacimiento else None
                                ),
                            }
                        ).execute()
                        st.success("Guardado")
                        st.session_state["form_id"] += 1
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.error("Cédula y Nombre son obligatorios")

    # ==============================================================================
    # TAB 3: IMPORTAR / EXPORTAR
    # ==============================================================================
    with tab3:
        c_imp, c_exp = st.columns(2)

        # EXPORTAR (BACKUP)
        with c_exp:
            st.subheader("📤 Copia de Seguridad")
            st.write("Descarga toda tu base de clientes actual.")
            if st.button("🔄 Generar Excel Clientes"):
                try:
                    res = supabase.table("clientes").select("*").execute()
                    df_backup = pd.DataFrame(res.data)

                    if not df_backup.empty:
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine="openpyxl") as writer:
                            df_backup.to_excel(
                                writer, index=False, sheet_name="Clientes"
                            )

                        st.download_button(
                            label="💾 Descargar Excel (.xlsx)",
                            data=output.getvalue(),
                            file_name=f"Respaldo_Clientes_{datetime.date.today()}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    else:
                        st.warning("No hay datos para exportar.")
                except Exception as e:
                    st.error(f"Error al exportar: {e}")

        # IMPORTAR (CARGA MASIVA)
        with c_imp:
            st.subheader("📥 Carga Masiva")
            st.info(
                "Sube un Excel con columnas: cedula, nombre, telefono, email, ciudad"
            )
            archivo = st.file_uploader("Arrastra tu archivo aquí", type=["xlsx"])

            if archivo and st.button("🚀 Procesar Carga"):
                try:
                    df = pd.read_excel(archivo, dtype=str)
                    df.columns = df.columns.str.strip().str.lower()
                    df = df.where(pd.notnull(df), None)  # Convertir NaN a None

                    exitos = 0
                    for i, row in df.iterrows():
                        try:
                            # Preparar datos básicos
                            raw_ced = str(row.get("cedula", "")).split(".")[0]
                            data_insert = {
                                "cedula_ruc": raw_ced,
                                "nombre_completo": str(row.get("nombre", "SN")).upper(),
                                "telefono": str(row.get("telefono", "")).split(".")[0],
                                "email": row.get("email"),
                                "ciudad": str(row.get("ciudad", "")).title(),
                            }
                            supabase.table("clientes").insert(data_insert).execute()
                            exitos += 1
                        except:
                            pass

                    st.success(f"Carga finalizada. {exitos} registros insertados.")
                    time.sleep(2)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    # ==============================================================================
    # TAB 4: CONFIGURACIÓN DE CATÁLOGOS
    # ==============================================================================
    if tab4 is not None:
        with tab4:
            st.subheader("⚙️ Gestión de Tipos de Cliente")
            st.caption(
                "Agrega nuevas categorías para clasificar a tus clientes. Los cambios se reflejarán inmediatamente en los formularios."
            )

            col_form, col_tabla = st.columns([1, 1])

            with col_form:
                with st.form("form_nuevo_tipo", clear_on_submit=True):
                    nuevo_tipo = st.text_input(
                        "Nombre de la nueva categoría (Ej. Mayorista)"
                    )
                    if st.form_submit_button("➕ Agregar Categoría", type="primary"):
                        if nuevo_tipo.strip():
                            try:
                                supabase.table("catalogo_tipos_cliente").insert(
                                    {"nombre": nuevo_tipo.strip().title()}
                                ).execute()
                                st.success(
                                    f"Categoría '{nuevo_tipo}' agregada con éxito."
                                )
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(
                                    "Error al agregar. Es posible que el nombre ya exista."
                                )
                        else:
                            st.warning("El nombre no puede estar vacío.")

            with col_tabla:
                # Mostramos los tipos actuales
                res_tipos_tabla = (
                    supabase.table("catalogo_tipos_cliente")
                    .select("*")
                    .order("nombre")
                    .execute()
                )
                if res_tipos_tabla.data:
                    df_tipos = pd.DataFrame(res_tipos_tabla.data)
                    # Ocultamos columnas técnicas y mostramos solo lo relevante
                    st.dataframe(
                        df_tipos[["nombre", "activo"]],
                        hide_index=True,
                        use_container_width=True,
                    )
                else:
                    st.info("No hay categorías registradas.")
