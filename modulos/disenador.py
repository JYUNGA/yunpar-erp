import streamlit as st
import pandas as pd
from datetime import datetime
import PyPDF2
import io

# ==========================================
# UTILIDADES
# ==========================================
def orden_talla(talla):
    """Enseña al sistema a ordenar tallas lógicamente"""
    if not talla or pd.isna(talla): return 99
    t = str(talla).strip().upper()
    mapping = {
        "2": 1, "4": 2, "6": 3, "8": 4, "10": 5, "12": 6, "14": 7, "16": 8, "18": 9,
        "20": 10, "22": 11, "24": 12, "26": 13, "28": 14, "30": 15, "32": 16, "34": 17, "36": 18, "38": 19, "40": 20,
        "4-6": 21, "6-8": 22, "8-10": 23, "10-12": 24,
        "TXS": 29, "XS": 30, "S": 31, "M": 32, "L": 33, "XL": 34, "2XL": 35, "XXL": 35, "3XL": 36, "XXXL": 36, "4XL": 37, "5XL": 38
    }
    return mapping.get(t, 99)

def extraer_metadata_pdf(uploaded_file):
    """Extrae nombre y suma las dimensiones de TODAS las páginas de un PDF en metros"""
    try:
        reader = PyPDF2.PdfReader(uploaded_file)
        alto_total_m = 0.0
        ancho_m = 0.0
        
        for page in reader.pages:
            box = page.mediabox
            # Calculamos el ancho solo de la primera página
            if ancho_m == 0.0:
                ancho_m = float(box.width) * 0.352778 / 1000
            
            # Sumamos el alto de cada página encontrada
            alto_total_m += float(box.height) * 0.352778 / 1000
            
        return uploaded_file.name, round(ancho_m, 2), round(alto_total_m, 2)
    except Exception as e:
        st.warning(f"No se pudieron extraer las medidas de {uploaded_file.name}: {e}")
        return uploaded_file.name, 0.0, 0.0

# ==========================================
# FUNCIÓN PRINCIPAL
# ==========================================
def render(supabase):
    st.header("🎨 Módulo de Diseño", divider="blue")

    if 'orden_diseno_actual' not in st.session_state:
        st.session_state['orden_diseno_actual'] = None

    # ==========================================
    # 1. BUSCADOR AVANZADO
    # ==========================================
    with st.expander("🔍 Buscador Avanzado (Bandeja de Pendientes)", expanded=True):
        with st.form("buscar_orden_diseno_form"):
            col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
            busqueda_cod = col1.text_input("Código de Orden", placeholder="Ej: 001")
            busqueda_cli = col2.text_input("Nombre del Cliente", placeholder="Ej: Fra")
            busqueda_fechas = col3.date_input("Rango de Fechas (Pedido)", value=[], format="DD/MM/YYYY")
            
            st.write("") 
            submit_search = col4.form_submit_button("Filtrar Bandeja", use_container_width=True)

    # CÓDIGO NUEVO (Reemplazar por esto)
    try:
        res_ordenes = supabase.table("ordenes") \
            .select("id, codigo_orden, estado, fecha_entrega, alerta_cambios, detalle_cambios, cliente_id, created_at, url_boceto_vendedora, url_arte_final, url_diseno_final, observaciones_generales") \
            .or_("estado.eq.Pendiente,estado.eq.En Diseño,alerta_cambios.eq.true") \
            .order("created_at", desc=True) \
            .execute()
        ordenes_data = res_ordenes.data
    except Exception as e:
        st.error(f"Error al conectar con Supabase: {e}")
        return

    if not ordenes_data:
        st.success("🎉 ¡Bandeja limpia! No hay órdenes pendientes por diseñar.")
        return

    cliente_ids = list(set([d['cliente_id'] for d in ordenes_data if d.get('cliente_id')]))
    mapa_clientes = {}
    if cliente_ids:
        res_cli = supabase.table('clientes').select('id, nombre_completo').in_('id', cliente_ids).execute()
        for c in res_cli.data: mapa_clientes[c['id']] = c.get('nombre_completo', 'Desconocido')

    df_ordenes = pd.DataFrame(ordenes_data)
    df_ordenes['Cliente'] = df_ordenes['cliente_id'].map(lambda x: mapa_clientes.get(x, 'Consumidor Final'))
    
    if busqueda_cod: df_ordenes = df_ordenes[df_ordenes['codigo_orden'].str.contains(busqueda_cod, case=False, na=False)]
    if busqueda_cli: df_ordenes = df_ordenes[df_ordenes['Cliente'].str.contains(busqueda_cli, case=False, na=False)]
    if len(busqueda_fechas) == 2:
        inicio = pd.to_datetime(busqueda_fechas[0])
        fin = pd.to_datetime(busqueda_fechas[1]).replace(hour=23, minute=59, second=59)
        fechas_creacion = pd.to_datetime(df_ordenes['created_at'])
        df_ordenes = df_ordenes[(fechas_creacion >= inicio) & (fechas_creacion <= fin)]

    st.subheader("📥 Repositorio de Pendientes")
    st.caption("📌 **Selecciona cualquier orden para empezar a trabajar:**")
    
    df_display = df_ordenes[['codigo_orden', 'Cliente', 'estado', 'fecha_entrega', 'alerta_cambios']].copy()
    df_display.columns = ['Código', 'Cliente', 'Estado', 'Fecha Entrega', '⚠️ Alertas']
    
    evento = st.dataframe(df_display, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")

    if len(evento.selection.rows) > 0:
        indice = evento.selection.rows[0]
        st.session_state['orden_diseno_actual'] = df_ordenes.iloc[indice].to_dict()
    else:
        # Si no hay selección, pero la memoria aún tiene datos guardados, limpiamos y FORZAMOS un reinicio visual
        if st.session_state.get('orden_diseno_actual') is not None:
            st.session_state['orden_diseno_actual'] = None
            st.rerun() # El truco mágico para borrar la pantalla fantasma

    # ==========================================
    # 2. VISTA DE DETALLE DE LA ORDEN
    # ==========================================
    if st.session_state.get('orden_diseno_actual'):
        orden = st.session_state['orden_diseno_actual']
        order_id = orden['id']

        st.divider()
        col_i1, col_i2, col_i3 = st.columns(3)
        col_i1.markdown(f"**Orden:** `{orden['codigo_orden']}`\n\n**Cliente:** {orden['Cliente']}")
        col_i2.markdown(f"**Estado:** {orden['estado']}\n\n**Entrega:** {orden['fecha_entrega']}")
        
        with col_i3:
            if orden['alerta_cambios']: 
                # Ahora mostramos exactamente QUÉ cambió según lo que escribió el vendedor
                st.error(f"🚨 **ALERTA DE CAMBIO:** {orden.get('detalle_cambios', 'Se hizo una modificación sin especificar.')}")
                
            if orden['estado'] == "Pendiente":
                if st.button("Tomar Orden (Pasar a 'En Diseño')", type="primary"):
                    supabase.table("ordenes").update({"estado": "En Diseño"}).eq("id", order_id).execute()
                    st.rerun()

        # --- IMÁGENES DE REFERENCIA ---
        st.markdown("### 🖼️ Referencias Visuales")
        col_img1, col_img2 = st.columns(2)
        with col_img1:
            st.caption("Boceto Vendedora")
            if orden.get('url_boceto_vendedora'): st.image(orden['url_boceto_vendedora'], use_container_width=True)
            else: st.info("No hay boceto registrado.")
        # CÓDIGO NUEVO
        with col_img2:
            st.caption("Arte Final / Diseño")
            # Obtenemos la URL de cualquiera de las dos columnas que tenga datos
            url_imagen_final = orden.get('url_arte_final') or orden.get('url_diseno_final')
            
            if url_imagen_final: 
                st.image(url_imagen_final, use_container_width=True)
            else: 
                st.info("No hay arte final registrado en la base de datos.")
            
        # CÓDIGO NUEVO (Reemplazar por esto)
        # --- NUEVO: OBSERVACIONES GENERALES DE LA ORDEN ---
        st.markdown("### 📝 Observaciones Generales de la Orden")
        if orden.get('observaciones_generales'):
            st.info(f"**Nota del cliente/comercial:** {orden['observaciones_generales']}")
        else:
            st.warning("No hay observaciones generales registradas para esta orden.")
        st.divider()

        try:
            res_items = supabase.table("items_orden").select("*").eq("orden_id", order_id).execute()
            items = res_items.data
            for item in items:
                if item.get('producto_id'):
                    res_p = supabase.table("productos_catalogo").select("descripcion").eq("id", item['producto_id']).execute()
                    item['nombre_producto'] = res_p.data[0]['descripcion'] if res_p.data else item.get('familia_producto')
                else: item['nombre_producto'] = item.get('familia_producto')
                
                if item.get('insumo_base_id'):
                    res_t = supabase.table("insumos").select("nombre").eq("id", item['insumo_base_id']).execute()
                    item['nombre_tela'] = res_t.data[0]['nombre'] if res_t.data else "Estándar"
                else: item['nombre_tela'] = "Estándar"

                res_esp = supabase.table("especificaciones_producto").select("*").eq("item_orden_id", item['id']).execute()
                item['especificaciones_producto'] = res_esp.data
        except:
            items = []

        resumen_sup = {}; resumen_inf = {}; resumen_polines = {}
        specs_list = []

        for item in items:
            fam = str(item.get('familia_producto', '')).strip().upper()
            prod = item['nombre_producto']
            tela = item['nombre_tela']
            
            for esp in item.get('especificaciones_producto', []):
                t_sup = str(esp.get('talla_superior') or '').strip().upper()
                t_inf = str(esp.get('talla_inferior') or '').strip().upper()
                
                if fam in ['UNIFORME COMPLETO', 'PRENDA SUPERIOR'] and t_sup not in ['-', 'NONE', '']: 
                    resumen_sup[t_sup] = resumen_sup.get(t_sup, 0) + 1
                if fam in ['UNIFORME COMPLETO', 'PANTALONETA'] and t_inf not in ['-', 'NONE', '']: 
                    resumen_inf[t_inf] = resumen_inf.get(t_inf, 0) + 1
                if fam == 'UNIFORME COMPLETO':
                    t_pol = str(esp.get('talla_polines') or '').strip().upper()
                    if t_pol not in ['-', 'NONE', '']:
                        k = (t_pol, str(esp.get('color_polines') or 'Sin Color').strip())
                        resumen_polines[k] = resumen_polines.get(k, 0) + 1
                
                # Leemos el cuello y limpiamos la palabra "EMPTY" si existe
                cuello_db = esp.get("tipo_cuello_texto", "-")
                cuello_limpio = "-" if cuello_db == "EMPTY" else cuello_db

                specs_list.append({
                    "Producto": prod,
                    "Tela": tela,
                    "Género": esp.get("genero", "-"),
                    "Cuello": cuello_limpio,                     
                    "Talla Sup.": t_sup if t_sup != 'NONE' else "-",
                    "Talla Inf.": t_inf if t_inf != 'NONE' else "-",
                    "Jugador": esp.get("nombre_jugador", "-"),
                    "Dorsal": esp.get("numero_dorsal", "-"),
                    "Arquero": bool(esp.get("es_arquero", False)), # <-- NUEVO CAMPO AGREGADO
                    "Notas": esp.get("observacion_individual", "")
                })

        # --- CÁLCULO DE TABLAS RESUMEN (Camisetas, Pantalonetas, Polines) ---
        st.markdown("### 📊 Tablas de Resumen de Corte")
        col_res1, col_res2, col_res3 = st.columns(3)
        
        with col_res1:
            if resumen_sup:
                df_sup = pd.DataFrame(list(resumen_sup.items()), columns=['Talla', 'Cantidad'])
                df_sup['Orden'] = df_sup['Talla'].apply(orden_talla)
                df_sup = df_sup.sort_values('Orden').drop(columns=['Orden']).reset_index(drop=True)
                
                total_sup = df_sup['Cantidad'].sum()
                fila_total = pd.DataFrame([{'Talla': 'TOTAL', 'Cantidad': total_sup}])
                df_sup = pd.concat([df_sup, fila_total], ignore_index=True)
                
                st.markdown("**👕 CAMISETAS**")
                st.dataframe(df_sup, hide_index=True, use_container_width=True)
                
        with col_res2:
            if resumen_inf:
                df_inf = pd.DataFrame(list(resumen_inf.items()), columns=['Talla', 'Cantidad'])
                df_inf['Orden'] = df_inf['Talla'].apply(orden_talla)
                df_inf = df_inf.sort_values('Orden').drop(columns=['Orden']).reset_index(drop=True)
                
                total_inf = df_inf['Cantidad'].sum()
                fila_total = pd.DataFrame([{'Talla': 'TOTAL', 'Cantidad': total_inf}])
                df_inf = pd.concat([df_inf, fila_total], ignore_index=True)
                
                st.markdown("**🩳 PANTALONETAS**")
                st.dataframe(df_inf, hide_index=True, use_container_width=True)
                
        with col_res3:
            if resumen_polines:
                df_pol = pd.DataFrame([{'Talla': t, 'Color': c, 'Cantidad': cant} for (t, c), cant in resumen_polines.items()])
                df_pol['Orden'] = df_pol['Talla'].apply(orden_talla)
                df_pol = df_pol.sort_values('Orden').drop(columns=['Orden']).reset_index(drop=True)
                
                total_pol = df_pol['Cantidad'].sum()
                fila_total = pd.DataFrame([{'Talla': 'TOTAL', 'Color': '-', 'Cantidad': total_pol}])
                df_pol = pd.concat([df_pol, fila_total], ignore_index=True)
                
                st.markdown("**🧦 POLINES**")
                st.dataframe(df_pol, hide_index=True, use_container_width=True)
                
                
        # --- TABLA DETALLADA CON LOS 4 FILTROS ---
        st.markdown("### 📋 Listado Detallado de Prendas")
        if specs_list:
            df_specs = pd.DataFrame(specs_list)
            
            col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns([2, 2, 1.5, 1.5, 1])
            
            lista_productos = ["Todos"] + list(df_specs['Producto'].unique())
            lista_telas_filtro = ["Todos"] + list(df_specs['Tela'].unique())
            lista_tsup = ["Todos"] + [t for t in df_specs['Talla Sup.'].unique() if t != "-"]
            lista_tinf = ["Todos"] + [t for t in df_specs['Talla Inf.'].unique() if t != "-"]
            
            filtro_prod = col_f1.selectbox("Producto:", lista_productos)
            filtro_tela = col_f2.selectbox("Tela:", lista_telas_filtro)
            filtro_tsup = col_f3.selectbox("Talla Sup:", lista_tsup)
            filtro_tinf = col_f4.selectbox("Talla Inf:", lista_tinf)
            
            df_filtrado = df_specs.copy()
            if filtro_prod != "Todos": df_filtrado = df_filtrado[df_filtrado['Producto'] == filtro_prod]
            if filtro_tela != "Todos": df_filtrado = df_filtrado[df_filtrado['Tela'] == filtro_tela]
            if filtro_tsup != "Todos": df_filtrado = df_filtrado[df_filtrado['Talla Sup.'] == filtro_tsup]
            if filtro_tinf != "Todos": df_filtrado = df_filtrado[df_filtrado['Talla Inf.'] == filtro_tinf]
            
            col_f5.metric("👕 Prendas en vista:", len(df_filtrado))
            
            # --- NUEVO: FUNCIÓN DE ESTILIZADO CONDICIONAL ---
            def resaltar_arqueros(row):
                # Aplica un fondo amarillo pastel si la columna 'Arquero' es True
                if row['Arquero'] == True:
                    return ['background-color: #FFF2CC; color: #000000;'] * len(row)
                return [''] * len(row)

            # Aplicamos el estilo al DataFrame
            df_estilizado = df_filtrado.style.apply(resaltar_arqueros, axis=1)
            
            # Mostramos el DataFrame estilizado (Streamlit renderizará los booleanos como casillas de verificación)
            st.dataframe(df_estilizado, use_container_width=True, hide_index=True)
        else:
            st.info("No se encontraron especificaciones registradas para esta orden.")

        # ==========================================
        # 3. GESTOR MULTIPLE DE ARCHIVOS DE IMPRESIÓN
        # ==========================================
        st.divider()
        st.subheader("🖨️ Gestor de Archivos de Impresión")
        
        # OBTENER TELAS DISPONIBLES DESDE LA BASE DE DATOS
        try:
            res_telas_bd = supabase.table("insumos").select("nombre").execute()
            lista_telas_db = [t['nombre'] for t in res_telas_bd.data] if res_telas_bd.data else ["Estándar"]
        except Exception:
            lista_telas_db = ["Estándar"]

        lista_perfiles = ["Plotter 1", "Plotter 2", "DTF"] 

        st.markdown("**1. Subir PDFs en lote (Extrae medidas automáticamente)**")
        archivos_pdf = st.file_uploader("Arrastra aquí los archivos PDF de tu diseño (Puedes seleccionar varios a la vez):", type=["pdf"], accept_multiple_files=True)
        
        if archivos_pdf:
            st.success(f"✅ Se han detectado {len(archivos_pdf)} archivo(s) PDF.")
            
            archivos_extraidos = []
            tela_por_defecto = lista_telas_db[0] if lista_telas_db else "Estándar"

            for pdf in archivos_pdf:
                nombre_auto, ancho_auto, largo_auto = extraer_metadata_pdf(pdf)
                archivos_extraidos.append({
                    "Nombre": nombre_auto,
                    "Tela": tela_por_defecto,
                    "Ancho": ancho_auto,
                    "Largo": largo_auto,
                    "Cantidad": 1,         # <-- NUEVO CAMPO
                    "Perfil": "Plotter 1", 
                    "Notas": ""
                })
            
            st.markdown("**2. Revisa y asigna perfiles y telas a los archivos detectados:**")
            df_nuevos = pd.DataFrame(archivos_extraidos)
            
            edited_nuevos = st.data_editor(
                df_nuevos,
                column_config={
                    "Perfil": st.column_config.SelectboxColumn("Perfil", options=lista_perfiles),
                    "Tela": st.column_config.SelectboxColumn("Tela a Usar", options=lista_telas_db, required=True),
                    "Ancho": st.column_config.NumberColumn("Ancho (m)", format="%.2f"),
                    "Largo": st.column_config.NumberColumn("Largo Unitario (m)", format="%.2f"),
                    "Cantidad": st.column_config.NumberColumn("Cantidad", min_value=1, step=1), # <-- NUEVA COLUMNA
                },
                use_container_width=True,
                hide_index=True,
                key="editor_nuevos_archivos"
            )
            
            if st.button("💾 Guardar todos los archivos", type="primary"):
                try:
                    payloads = []
                    for _, row in edited_nuevos.iterrows():
                        payloads.append({
                            "orden_id": order_id,
                            "nombre_archivo": row['Nombre'].strip(),
                            "tela": row['Tela'], 
                            "perfil_color": row['Perfil'],
                            "ancho_metros": row['Ancho'], 
                            "longitud_metros": row['Largo'],
                            "cantidad": row['Cantidad'], # <-- GUARDAR EN BD
                            "estado_impresion": "Pendiente",
                            "notas_disenador": str(row['Notas']).strip() if pd.notna(row['Notas']) else ""
                        })
                    
                    supabase.table("archivos_impresion").insert(payloads).execute()
                    st.success("¡Todos los archivos fueron registrados exitosamente en la base de datos!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al guardar. ¡Asegúrate de haber creado la columna 'tela' y 'ancho_metros' en Supabase! Detalles del error: {e}")
        else:
            st.info("Arrastra PDFs arriba, o registra manualmente un archivo usando el botón de abajo.")
            with st.expander("➕ Registro Manual (Sin PDF)"):
                with st.form("form_registro_manual", clear_on_submit=True):
                    col_m1, col_m2, col_m_tela = st.columns(3)
                    col_m3, col_m4, col_m5 = st.columns([1, 1, 1]) # Modificado para hacer espacio
                    
                    nombre_input = col_m1.text_input("Nombre del Archivo")
                    perfil_input = col_m2.selectbox("Perfil de Color", lista_perfiles)
                    tela_input = col_m_tela.selectbox("Tela a Usar", lista_telas_db)
                    
                    ancho_input = col_m3.number_input("Ancho (m)", min_value=0.0, step=0.01)
                    largo_input = col_m4.number_input("Largo Unitario (m)", min_value=0.0, step=0.01)
                    cantidad_input = col_m5.number_input("Cantidad", min_value=1, step=1, value=1) # <-- NUEVO
                    notas_input = st.text_input("Notas")
                    
                    if st.form_submit_button("Guardar Registro Manual"):
                        if nombre_input and largo_input > 0:
                            try:
                                payload = {
                                    "orden_id": order_id, "nombre_archivo": nombre_input.strip(),
                                    "perfil_color": perfil_input, "tela": tela_input,
                                    "ancho_metros": ancho_input, "longitud_metros": largo_input, 
                                    "cantidad": cantidad_input, # <-- GUARDAR EN BD
                                    "estado_impresion": "Pendiente", "notas_disenador": notas_input.strip()
                                }
                                supabase.table("archivos_impresion").insert(payload).execute()
                                st.success("Guardado.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
                        else: st.warning("Nombre y largo requeridos.")

        # --- Tabla Editable de Archivos ya Registrados ---
        st.markdown("**3. Historial de archivos listos para plotter (Edita o marca para eliminar)**")
        res_archivos = supabase.table("archivos_impresion").select("*").eq("orden_id", order_id).execute()
        df_archivos = pd.DataFrame(res_archivos.data)

        if not df_archivos.empty:
            if 'ancho_metros' not in df_archivos.columns: df_archivos['ancho_metros'] = 0.0
            if 'tela' not in df_archivos.columns: df_archivos['tela'] = lista_telas_db[0] if lista_telas_db else "Estándar"
           if 'cantidad' not in df_archivos.columns: df_archivos['cantidad'] = 1
            
            df_edit = df_archivos[['id', 'nombre_archivo', 'perfil_color', 'tela', 'ancho_metros', 'longitud_metros', 'cantidad', 'notas_disenador']].copy()
            df_edit['Eliminar'] = False 
            
            edited_df = st.data_editor(
                df_edit,
                column_config={
                    "id": None, 
                    "nombre_archivo": "Nombre",
                    "perfil_color": st.column_config.SelectboxColumn("Perfil", options=lista_perfiles),
                    "tela": st.column_config.SelectboxColumn("Tela", options=lista_telas_db, required=True),
                    "ancho_metros": st.column_config.NumberColumn("Ancho (m)", format="%.2f"),
                    "longitud_metros": st.column_config.NumberColumn("Largo Unitario (m)", format="%.2f"),
                    "cantidad": st.column_config.NumberColumn("Cantidad", min_value=1, step=1), # <-- MOSTRAR AQUÍ
                    "notas_disenador": "Notas",
                    "Eliminar": st.column_config.CheckboxColumn("🗑️ Eliminar", default=False)
                },
               
                disabled=["id"], hide_index=True, use_container_width=True
            )

            if st.button("🔄 Sincronizar Cambios de la Tabla"):
                try:
                    for index, row in edited_df.iterrows():
                        fila_id = row['id']
                        if row['Eliminar']:
                            supabase.table("archivos_impresion").delete().eq("id", fila_id).execute()
                        else:
                            supabase.table("archivos_impresion").update({
                                "nombre_archivo": row['nombre_archivo'], 
                                "perfil_color": row['perfil_color'],
                                "tela": row['tela'],
                                "ancho_metros": row['ancho_metros'], 
                                "longitud_metros": row['longitud_metros'],
                                "cantidad": row['cantidad'], # <-- FALTABA AGREGAR ESTA LÍNEA AQUÍ
                                "notas_disenador": row['notas_disenador']
                            }).eq("id", fila_id).execute()
                    st.success("Cambios sincronizados correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al sincronizar: {e}")
        else:
            st.info("Aún no hay archivos registrados para impresión.")

        # ==========================================
        # 4. BOTÓN DE ENVÍO A PLOTTER
        # ==========================================
        st.divider()
        st.info("Al enviar a impresión, la orden saldrá de tu bandeja y pasará al área de plotter.")
        
        if st.button("🚀 Finalizar Diseño y Enviar a Impresión", type="primary", use_container_width=True):
            try:
                supabase.table("ordenes").update({"estado": "Listo para Impresión", "alerta_cambios": False}).eq("id", order_id).execute()
                st.session_state['orden_diseno_actual'] = None
                st.success("¡Orden enviada exitosamente a Impresión!")
                st.rerun()
            except Exception as e:
                st.error(f"Error al intentar enviar la orden a impresión: {e}")
