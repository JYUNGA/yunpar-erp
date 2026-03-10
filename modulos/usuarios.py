import streamlit as st
import pandas as pd
import time

def render(supabase):
    st.header("👥 Gestión de Usuarios del Sistema", divider="blue")
    
    # Validación de seguridad: Solo el GERENTE entra aquí
    if st.session_state.get('rol') != 'GERENTE':
        st.error("No tienes permisos para ver este módulo.")
        st.stop()

    tab_lista, tab_nuevo, tab_seguridad = st.tabs(["📋 Lista de Usuarios", "➕ Nuevo Usuario", "🔐 Seguridad"])

    # --- PESTAÑA 1: LISTA Y EDICIÓN RÁPIDA ---
    with tab_lista:
        st.subheader("Usuarios Registrados")
        st.info("💡 Para quitarle el acceso a alguien sin borrar su historial de trabajo, simplemente desmarca la casilla '¿Activo?' y guarda los cambios.")
        
        try:
            res = supabase.table('usuarios').select("*").order('id').execute()
            if res.data:
                df_usuarios = pd.DataFrame(res.data)
                
                columnas_config = {
                    "id": None, 
                    "password_hash": None, 
                    "nombre_completo": st.column_config.TextColumn("Nombre Completo", required=True),
                    "usuario": st.column_config.TextColumn("Usuario (Login)", disabled=True),
                    "rol": st.column_config.SelectboxColumn("Rol", options=["GERENTE", "VENDEDORA", "IMPRESION", "DISEÑADOR"], required=True),
                    "activo": st.column_config.CheckboxColumn("¿Activo?")
                }
                
                df_editado = st.data_editor(
                    df_usuarios, column_config=columnas_config, hide_index=True, use_container_width=True, key="editor_usuarios"
                )

                if st.button("💾 Guardar Cambios en Usuarios", type="primary"):
                    with st.spinner("Actualizando base de datos..."):
                        for index, row in df_editado.iterrows():
                            supabase.table('usuarios').update({
                                "nombre_completo": row['nombre_completo'],
                                "rol": row['rol'],
                                "activo": row['activo']
                            }).eq('id', row['id']).execute()
                        st.success("¡Cambios guardados correctamente!")
                        time.sleep(1); st.rerun()
            else:
                st.info("No hay usuarios registrados.")
        except Exception as e:
            st.error(f"Error al cargar usuarios: {e}")

    # --- PESTAÑA 2: CREAR NUEVO USUARIO ---
    with tab_nuevo:
        st.subheader("Crear Credenciales de Acceso")
        with st.form("form_nuevo_usuario", clear_on_submit=True):
            col1, col2 = st.columns(2)
            n_nombre = col1.text_input("Nombre y Apellido *")
            n_usuario = col2.text_input("Nombre de Usuario (Para el login) *")
            
            col3, col4 = st.columns(2)
            n_pass = col3.text_input("Contraseña temporal *", type="password")
            n_rol = col4.selectbox("Asignar Rol *", ["VENDEDORA", "IMPRESION", "DISEÑADOR", "GERENTE"])
            
            if st.form_submit_button("Crear Usuario", use_container_width=True):
                if n_nombre and n_usuario and n_pass:
                    try:
                        nuevo_user = {
                            "nombre_completo": n_nombre.strip(),
                            "usuario": n_usuario.strip().lower(),
                            "password_hash": n_pass, 
                            "rol": n_rol,
                            "activo": True
                        }
                        supabase.table('usuarios').insert(nuevo_user).execute()
                        st.success(f"¡Usuario {n_usuario} creado exitosamente!")
                        time.sleep(1); st.rerun()
                    except Exception as e:
                        st.error(f"Error al crear el usuario. Probablemente el usuario ya exista. Detalles: {e}")
                else:
                    st.warning("Completa todos los campos obligatorios (*).")

    # --- PESTAÑA 3: SEGURIDAD (CONTRASEÑAS Y ELIMINACIÓN) ---
    with tab_seguridad:
        st.subheader("Administración de Credenciales")
        
        # Consultamos nuevamente los usuarios para el selector
        res_sec = supabase.table('usuarios').select("id, nombre_completo, usuario").order('nombre_completo').execute()
        
        if res_sec.data:
            opciones = {u['id']: f"{u['nombre_completo']} ({u['usuario']})" for u in res_sec.data}
            usuario_seleccionado = st.selectbox("Selecciona el usuario a administrar:", options=list(opciones.keys()), format_func=lambda x: opciones[x])
            
            st.divider()
            
            # --- ZONA: RESTABLECER CONTRASEÑA ---
            st.markdown("#### 🔑 Restablecer Contraseña")
            nueva_pass = st.text_input("Escribe la nueva contraseña:", type="password")
            if st.button("Actualizar Contraseña"):
                if nueva_pass:
                    try:
                        supabase.table('usuarios').update({"password_hash": nueva_pass}).eq('id', usuario_seleccionado).execute()
                        st.success(f"Contraseña de {opciones[usuario_seleccionado]} actualizada exitosamente.")
                    except Exception as e:
                        st.error(f"Error al actualizar: {e}")
                else:
                    st.warning("Debes escribir una contraseña nueva antes de actualizar.")
            
            st.divider()
            
            # --- ZONA: ELIMINAR USUARIO ---
            st.markdown("#### ⚠️ Zona de Peligro")
            st.warning("Si este usuario ya ha creado clientes, órdenes o cobros, borrarlo causará errores en el sistema. Te recomendamos ir a la pestaña 'Lista de Usuarios' y simplemente quitarle el check de '¿Activo?'.")
            
            if st.button("🗑️ Eliminar Usuario Definitivamente", type="secondary"):
                try:
                    supabase.table('usuarios').delete().eq('id', usuario_seleccionado).execute()
                    st.success("Usuario eliminado de la base de datos.")
                    time.sleep(1); st.rerun()
                except Exception as e:
                    st.error(f"No se pudo eliminar el usuario porque tiene registros asociados en el sistema. Error: {e}")
        else:
            st.info("No hay usuarios para administrar.")