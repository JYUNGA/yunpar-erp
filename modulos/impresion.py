import streamlit as st
import pandas as pd
from datetime import datetime

# ==========================================
# UTILIDADES
# ==========================================
def formatear_fecha_espanol(fecha_str):
    """Convierte una fecha YYYY-MM-DD a un formato amigable en español"""
    if not fecha_str or pd.isna(fecha_str): 
        return "Sin fecha"
    try:
        # Extraer solo la parte de la fecha por si viene con hora
        fecha_limpia = str(fecha_str).split("T")[0]
        dt = datetime.strptime(fecha_limpia, "%Y-%m-%d")
        
        dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
        
        nombre_dia = dias[dt.weekday()]
        nombre_mes = meses[dt.month - 1]
        
        return f"{nombre_dia}, {dt.day} de {nombre_mes} del {dt.year}"
    except Exception:
        return str(fecha_str)

# ==========================================
# FUNCIÓN PRINCIPAL
# ==========================================
def render(supabase):
    st.header("🖨️ Estación de Impresión (Plotter)", divider="blue")

    if 'orden_impresion_actual' not in st.session_state:
        st.session_state['orden_impresion_actual'] = None

    # ==========================================
    # 1. BUSCADOR AVANZADO Y BANDEJA
    # ==========================================
    with st.expander("🔍 Buscador Avanzado (Bandeja de Pendientes)", expanded=True):
        with st.form("buscar_orden_impresion_form"):
            col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
            busqueda_cod = col1.text_input("Código de Orden", placeholder="Ej: 001")
            busqueda_cli = col2.text_input("Nombre del Cliente", placeholder="Ej: Fra")
            busqueda_fechas = col3.date_input("Rango de Fechas (Pedido)", value=[], format="DD/MM/YYYY")
            
            st.write("") 
            submit_search = col4.form_submit_button("Filtrar Bandeja", use_container_width=True)

    try:
        # Traemos órdenes listas para impresión, en impresión o con alertas
        res_ordenes = supabase.table("ordenes") \
            .select("id, codigo_orden, estado, fecha_entrega, alerta_cambios, cliente_id, created_at, url_arte_final") \
            .or_("estado.eq.Listo para Impresión,estado.eq.En Impresión,alerta_cambios.eq.true") \
            .order("created_at", desc=True) \
            .execute()
        ordenes_data = res_ordenes.data
    except Exception as e:
        st.error(f"Error al conectar con Supabase: {e}")
        return

    if not ordenes_data:
        st.success("🎉 ¡Bandeja limpia! No hay órdenes pendientes por imprimir.")
        return

    # Mapear nombres de clientes
    cliente_ids = list(set([d['cliente_id'] for d in ordenes_data if d.get('cliente_id')]))
    mapa_clientes = {}
    if cliente_ids:
        res_cli = supabase.table('clientes').select('id, nombre_completo').in_('id', cliente_ids).execute()
        for c in res_cli.data: mapa_clientes[c['id']] = c.get('nombre_completo', 'Desconocido')

    df_ordenes = pd.DataFrame(ordenes_data)
    df_ordenes['Cliente'] = df_ordenes['cliente_id'].map(lambda x: mapa_clientes.get(x, 'Consumidor Final'))
    
    # Aplicar filtros del buscador
    if busqueda_cod: df_ordenes = df_ordenes[df_ordenes['codigo_orden'].str.contains(busqueda_cod, case=False, na=False)]
    if busqueda_cli: df_ordenes = df_ordenes[df_ordenes['Cliente'].str.contains(busqueda_cli, case=False, na=False)]
    if len(busqueda_fechas) == 2:
        inicio = pd.to_datetime(busqueda_fechas[0])
        fin = pd.to_datetime(busqueda_fechas[1]).replace(hour=23, minute=59, second=59)
        fechas_creacion = pd.to_datetime(df_ordenes['created_at'])
        df_ordenes = df_ordenes[(fechas_creacion >= inicio) & (fechas_creacion <= fin)]

    st.subheader("📥 Repositorio de Pendientes")
    st.caption("📌 **Selecciona cualquier orden para empezar a imprimir:**")
    
    # Preparar DataFrame para visualización
    df_display = df_ordenes[['codigo_orden', 'Cliente', 'estado', 'fecha_entrega', 'alerta_cambios']].copy()
    df_display.columns = ['Código', 'Cliente', 'Estado', 'Fecha Entrega', '⚠️ Alertas']
    
    # Tabla interactiva con selección
    evento = st.dataframe(df_display, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")

    # Actualizar estado de sesión si se selecciona una fila
    if len(evento.selection.rows) > 0:
        indice = evento.selection.rows[0]
        st.session_state['orden_impresion_actual'] = df_ordenes.iloc[indice].to_dict()

    # ==========================================
    # 2. VISTA DE DETALLE DE LA ORDEN
    # ==========================================
    if st.session_state.get('orden_impresion_actual'):
        orden_actual = st.session_state['orden_impresion_actual']
        order_id = orden_actual['id']

        st.divider()
        col_inf1, col_inf2, col_inf3 = st.columns(3)
        col_inf1.markdown(f"**Código de Orden:** `{orden_actual['codigo_orden']}`\n\n**Cliente:** {orden_actual['Cliente']}")
        col_inf2.markdown(f"**Estado:** {orden_actual['estado']}")
        
        # Fecha de entrega grande y formateada
        fecha_formateada = formatear_fecha_espanol(orden_actual['fecha_entrega'])
        col_inf3.markdown("**Fecha de Entrega:**")
        col_inf3.markdown(f"<h3 style='color: #1f77b4; margin-top: -10px;'>{fecha_formateada}</h3>", unsafe_allow_html=True)

        if orden_actual['alerta_cambios']:
            st.warning("⚠️ Esta orden tiene una Alerta de Cambios activa. Revisa bien las notas.")
            
        # Pasar a "En Impresión" si estaba "Listo para Impresión"
        if orden_actual['estado'] == "Listo para Impresión":
            if st.button("Iniciar Impresión (Pasar a 'En Impresión')", type="primary"):
                supabase.table("ordenes").update({"estado": "En Impresión"}).eq("id", order_id).execute()
                # Actualizar el estado local para no recargar todo de cero
                st.session_state['orden_impresion_actual']['estado'] = 'En Impresión'
                st.rerun()

        # Mostrar Arte Final en tamaño muy grande
        st.markdown("### 🖼️ Arte Final de Referencia")
        if orden_actual['url_arte_final']:
            st.image(orden_actual['url_arte_final'], use_container_width=True, caption="Arte Final para Impresión")
        else:
            st.info("No se adjuntó un Arte Final visual para esta orden.")

        st.divider()

        # ==========================================
        # 3. PANEL DEL PLOTTER (GESTOR DE ARCHIVOS)
        # ==========================================
        st.subheader("📄 Archivos a Imprimir")
        
        try:
            res_archivos = supabase.table('archivos_impresion').select('*').eq('orden_id', order_id).execute()
            archivos_data = res_archivos.data
            
            if not archivos_data:
                st.warning("No se encontraron archivos de impresión asociados a esta orden.")
            else:
                # Preparar el DataFrame
                df_archivos = pd.DataFrame(archivos_data)
                
                # --- 1. PROTECCIÓN DE COLUMNAS ---
                if 'estado_impresion' not in df_archivos.columns: df_archivos['estado_impresion'] = 'Pendiente'
                if 'longitud_impresa' not in df_archivos.columns: df_archivos['longitud_impresa'] = None
                if 'motivo_reimpresion' not in df_archivos.columns: df_archivos['motivo_reimpresion'] = ""
                
                # --- 2. CONVERSIÓN ESTRICTA A NÚMEROS DECIMALES ---
                # Forzamos a que sean floats para que las sumas jamás fallen
                df_archivos['longitud_metros'] = pd.to_numeric(df_archivos['longitud_metros'], errors='coerce').fillna(0.0)
                df_archivos['longitud_impresa'] = pd.to_numeric(df_archivos['longitud_impresa'], errors='coerce')
                
                # --- 3. VALORES POR DEFECTO ---
                df_archivos['chk_impreso'] = df_archivos['estado_impresion'] == 'Impreso'
                # Copiamos la longitud exacta del diseño si no hay una impresa registrada
                df_archivos['longitud_impresa'] = df_archivos['longitud_impresa'].fillna(df_archivos['longitud_metros'])
                df_archivos['motivo_reimpresion'] = df_archivos['motivo_reimpresion'].fillna("")

                # --- 4. CONFIGURAR TABLA INTERACTIVA ---
                column_config = {
                    "id": None, "orden_id": None, "estado_impresion": None,
                    "nombre_archivo": st.column_config.TextColumn("Nombre Archivo", disabled=True),
                    "perfil_color": st.column_config.TextColumn("Perfil de Color", disabled=True),
                    "ancho_metros": st.column_config.NumberColumn("Ancho (m)", disabled=True, format="%.2f"),
                    "longitud_metros": st.column_config.NumberColumn("Long. Diseño (m)", disabled=True, format="%.2f"),
                    "notas_disenador": st.column_config.TextColumn("Notas del Diseñador", disabled=True),
                    "chk_impreso": st.column_config.CheckboxColumn("¿Impreso?", default=False),
                    
                    # CORRECCIÓN AQUÍ: step=0.01 para que respete los dos decimales exactos
                    "longitud_impresa": st.column_config.NumberColumn("Long. Impresa Real (m)", min_value=0.0, format="%.2f", step=0.01),
                    
                    "motivo_reimpresion": st.column_config.TextColumn("Motivo Desperdicio")
                }

                column_order = [
                    "chk_impreso", "nombre_archivo", "perfil_color", "ancho_metros", 
                    "longitud_metros", "longitud_impresa", "motivo_reimpresion", "notas_disenador"
                ]

                st.write("Edita la cantidad de papel real gastado y marca los archivos completados:")
                
                df_editado = st.data_editor(
                    df_archivos,
                    column_config=column_config,
                    column_order=column_order,
                    hide_index=True,
                    use_container_width=True,
                    key="editor_archivos_impresion"
                )

                # --- MÉTRICAS Y GUARDADO ---
                col_met1, col_met2 = st.columns(2)
                total_estimado = df_archivos['longitud_metros'].sum()
                total_real = df_editado['longitud_impresa'].sum()
                
                delta_color = "normal" if total_real <= total_estimado else "inverse"
                col_met1.metric("Papel Estimado (Total Diseño)", f"{total_estimado:.2f} m")
                col_met2.metric("Papel Real Gastado", f"{total_real:.2f} m", delta=f"{total_real - total_estimado:.2f} m extra", delta_color=delta_color)

                if st.button("💾 Guardar Avances de Impresión", use_container_width=True):
                    errores_validacion = False
                    for _, fila in df_editado.iterrows():
                        if fila['longitud_impresa'] > fila['longitud_metros'] and not str(fila['motivo_reimpresion']).strip():
                            st.error(f"El archivo '{fila['nombre_archivo']}' tiene un gasto extra de papel. Debes ingresar un 'Motivo Desperdicio'.")
                            errores_validacion = True
                    
                    if not errores_validacion:
                        try:
                            with st.spinner("Guardando información..."):
                                for _, fila in df_editado.iterrows():
                                    nuevo_estado_str = "Impreso" if fila['chk_impreso'] else "Pendiente"
                                    motivo_val = str(fila['motivo_reimpresion']).strip()
                                    
                                    # Intentamos guardar (fallará si no has creado las columnas en supabase)
                                    supabase.table('archivos_impresion').update({
                                        "estado_impresion": nuevo_estado_str,
                                        "longitud_impresa": fila['longitud_impresa'],
                                        "motivo_reimpresion": motivo_val if motivo_val else None
                                    }).eq('id', fila['id']).execute()
                                    
                            st.success("✅ Avances guardados correctamente.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al guardar en base de datos. ¿Aseguraste de crear las columnas 'longitud_impresa' y 'motivo_reimpresion' en Supabase? Error: {str(e)}")

                st.markdown("<br><br>", unsafe_allow_html=True)

                # --- FINALIZAR ORDEN ---
                st.warning("Asegúrate de haber impreso y guardado todos los archivos antes de continuar.")
                if st.button("🚀 Completar Impresión y Enviar a Sublimación", type="primary", use_container_width=True):
                    if not df_editado['chk_impreso'].all():
                        st.error("❌ Error: Debes marcar todos los archivos como 'Impresos' en la tabla superior y Guardar Avances primero.")
                    else:
                        try:
                            with st.spinner("Enviando a sublimación..."):
                                supabase.table('ordenes').update({
                                    "estado": "En Sublimación",
                                    "alerta_cambios": False
                                }).eq('id', order_id).execute()
                                
                                st.success("🎉 ¡Orden completada con éxito! Ha sido enviada al área de Sublimación.")
                                st.session_state['orden_impresion_actual'] = None
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error al enviar la orden a sublimación: {str(e)}")

        except Exception as e:
            st.error(f"Error crítico en el panel de archivos: {str(e)}")