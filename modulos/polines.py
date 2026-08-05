import streamlit as st
import pandas as pd
import time

def render(supabase):
    st.header("🧦 Consolidación y Compra de Polines")
    st.markdown("Agrupa los polines de diferentes órdenes, normaliza los colores escritos por las vendedoras y marca la compra como realizada.")

    # 1. EXTRACCIÓN DE DATOS ESTRICTA EN CASCADA
    with st.spinner("Cargando requerimientos de polines..."):
        # A. Usuarios (Para mapear a la vendedora)
        res_usu = supabase.table('usuarios').select('id, nombre_completo').execute()
        mapa_usu = {u['id']: u['nombre_completo'] for u in res_usu.data} if res_usu.data else {}

        # B. Órdenes (Traemos las recientes para filtrarlas implacablemente en memoria)
        # [Seguro]: Agregamos 'saldo_pendiente' a la consulta
        res_ord = supabase.table('ordenes').select('id, codigo_orden, estado, saldo_pendiente, creado_por_id, clientes(nombre_completo)').order('created_at', desc=True).limit(1000).execute()
        df_ord = pd.DataFrame(res_ord.data)
        
        if df_ord.empty:
            st.success("No hay órdenes en la base de datos.")
            return
            
        # [Seguro]: Purgamos con Pandas los estados terminados evadiendo errores tipográficos
        estados_excluidos = ['ENTREGADO', 'ENTREGADA', 'FINALIZADO', 'FINALIZADA', 'LISTA PARA ENTREGA', 'ANULADO', 'ANULADA']
        df_ord['estado_limpio'] = df_ord['estado'].fillna('').astype(str).str.strip().str.upper()
        df_ord = df_ord[~df_ord['estado_limpio'].isin(estados_excluidos)]
        
        # [Probable]: Aplicamos el filtro financiero para excluir órdenes con saldo $0.00
        # Forzamos la conversión a float para evitar colapsos por tipos de datos
        df_ord['saldo_pendiente'] = df_ord['saldo_pendiente'].fillna(0).astype(float)
        df_ord = df_ord[df_ord['saldo_pendiente'] > 0]
        
        if df_ord.empty:
            st.success("Todas las órdenes recientes ya fueron finalizadas, entregadas o están pagadas al 100%.")
            return
            
        df_ord['Vendedora'] = df_ord['creado_por_id'].map(lambda x: mapa_usu.get(x, 'Desconocido'))
        df_ord['Cliente'] = df_ord['clientes'].apply(lambda x: x.get('nombre_completo', 'S/N') if isinstance(x, dict) else 'S/N')

        # Aislamos los IDs de las órdenes estrictamente validadas
        ids_ordenes_pendientes = df_ord['id'].tolist()

        # C. Ítems (Búsqueda por lotes para evitar el error "URL Too Long" del servidor)
        items_data = []
        tamanio_lote = 150
        
        for i in range(0, len(ids_ordenes_pendientes), tamanio_lote):
            lote_ids = ids_ordenes_pendientes[i:i+tamanio_lote]
            res_lote = supabase.table('items_orden').select('id, orden_id, familia_producto').in_('familia_producto', ['UNIFORME COMPLETO', 'POLIN']).in_('orden_id', lote_ids).execute()
            if res_lote.data: items_data.extend(res_lote.data)
                
        df_itm = pd.DataFrame(items_data)
        
        if df_itm.empty:
            st.info("No hay uniformes completos ni polines en las órdenes pendientes.")
            return
            
        ids_items_pendientes = df_itm['id'].tolist()

        # D. Especificaciones (Filtradas estrictamente por los ítems detectados)
        especs_data = []
        
        for i in range(0, len(ids_items_pendientes), tamanio_lote):
            lote_items = ids_items_pendientes[i:i+tamanio_lote]
            
            # [Probable]: Extraemos en paralelo lo Falso y lo Nulo
            res_f = supabase.table('especificaciones_producto').select('id, item_orden_id, talla_polines, color_polines').in_('item_orden_id', lote_items).eq('polines_comprados', False).execute()
            if res_f.data: especs_data.extend(res_f.data)
            
            res_n = supabase.table('especificaciones_producto').select('id, item_orden_id, talla_polines, color_polines').in_('item_orden_id', lote_items).is_('polines_comprados', 'null').execute()
            if res_n.data: especs_data.extend(res_n.data)
            
        df_esp = pd.DataFrame(especs_data)
        
        if not df_esp.empty:
            df_esp = df_esp.dropna(subset=['talla_polines'])
            
        if df_esp.empty:
            st.success("🎉 ¡Todo al día! No hay polines pendientes de compra.")
            return

    # 2. CONSOLIDACIÓN DE DATOS (JOIN DE PANDAS)
    # Limpiamos basuras de tipeo
    df_esp = df_esp[~df_esp['talla_polines'].isin(['', '-', 'NONE', 'N/A'])]
    if df_esp.empty:
        st.success("No hay polines válidos pendientes.")
        return

    # Unimos: Especificaciones -> Items -> Órdenes
    df_join = pd.merge(df_esp, df_itm, left_on='item_orden_id', right_on='id', suffixes=('_esp', '_itm'))
    df_join = pd.merge(df_join, df_ord, left_on='orden_id', right_on='id', suffixes=('', '_ord'))

    # Renombramos y limpiamos la vista
    df_join['color_polines'] = df_join['color_polines'].fillna('SIN COLOR').astype(str).str.strip().str.upper()
    df_join['color_polines'] = df_join['color_polines'].replace({'': 'SIN COLOR', 'NONE': 'SIN COLOR'})
    
    # 3. FILTROS INTERACTIVOS
    st.markdown("### 🔍 1. Filtros de Búsqueda")
    col1, col2 = st.columns(2)
    
    lista_vendedoras = ["Todas"] + sorted(df_join['Vendedora'].unique().tolist())
    vendedora_sel = col1.selectbox("👤 Filtrar por Vendedora", lista_vendedoras)
    
    if vendedora_sel != "Todas":
        df_join = df_join[df_join['Vendedora'] == vendedora_sel]

    lista_ordenes = df_join['codigo_orden'].unique().tolist()
    ordenes_sel = col2.multiselect("📦 Filtrar por Órdenes Específicas", lista_ordenes, default=lista_ordenes)
    
    df_join = df_join[df_join['codigo_orden'].isin(ordenes_sel)]

    if df_join.empty:
        st.warning("No hay datos para los filtros seleccionados.")
        return

    # 4. HOMOGENEIZACIÓN DE COLORES Y RESPONSABLES
    st.divider()
    st.markdown("### 🎨 2. Normalización de Colores")
    st.caption("Verifica quién solicitó cada color y corrige la columna 'Color a Comprar' para unificar pedidos.")
    
    # [Seguro]: Agrupamos clientes y vendedoras involucradas por cada color escrito
    df_info_colores = df_join.groupby('color_polines').agg({
        'Cliente': lambda x: ' | '.join(x.unique()),
        'Vendedora': lambda x: ' | '.join(x.unique())
    }).reset_index()

    df_map = pd.DataFrame({
        "Cliente(s)": df_info_colores['Cliente'],
        "Color Original": df_info_colores['color_polines'],
        "Color a Comprar": df_info_colores['color_polines'],
        "Vendedora(s)": df_info_colores['Vendedora']
    })

    # Tabla editable protegida en los bordes
    df_map_edit = st.data_editor(
        df_map, 
        disabled=["Cliente(s)", "Color Original", "Vendedora(s)"], 
        use_container_width=True, 
        hide_index=True
    )

    mapa_colores = dict(zip(df_map_edit['Color Original'], df_map_edit['Color a Comprar'].str.strip().str.upper()))
    
    # Aplicamos la corrección a la tabla principal
    df_join['Color Consolidado'] = df_join['color_polines'].map(mapa_colores)

    # 5. RESUMEN FINAL Y BOTÓN DE COMPRA
    st.divider()
    st.markdown("### 🛒 3. Resumen de Compra")
    
    col_tabla, col_accion = st.columns([2, 1])
    
    # Agrupamos por Talla y el Color Corregido. Como cada fila es 1 unidad física, usamos size()
    df_resumen = df_join.groupby(['talla_polines', 'Color Consolidado']).size().reset_index(name='Cantidad a Comprar')
    df_resumen = df_resumen.rename(columns={'talla_polines': 'Talla'})
    
    with col_tabla:
        st.dataframe(df_resumen, use_container_width=True, hide_index=True)
        
        st.markdown("##### 📦 Desglose para el proveedor:")
        # [Probable]: Calculamos la división entera (//) y el residuo (%) para obtener docenas exactas
        resumen_tallas = df_resumen.groupby('Talla')['Cantidad a Comprar'].sum().reset_index()
        
        for _, row in resumen_tallas.iterrows():
            talla = row['Talla']
            total = row['Cantidad a Comprar']
            docenas = total // 12
            sueltos = total % 12
            
            texto_docenas = f"{docenas} docena(s)" if docenas > 0 else ""
            texto_sueltos = f"{sueltos} par(es)" if sueltos > 0 else ""
            
            if docenas > 0 and sueltos > 0:
                texto_final = f"{texto_docenas} + {texto_sueltos}"
            else:
                texto_final = texto_docenas or texto_sueltos
                
            st.info(f"**Talla {talla}:** {total} pares en total ➔ (**{texto_final}**)")

    with col_accion:
        st.markdown("#### Ejecución")
        st.caption(f"Se marcarán **{len(df_join)}** pares de polines como 'Comprados' en la base de datos.")
        
        if st.button("✅ Registrar Compra Realizada", type="primary", use_container_width=True):
            try:
                with st.spinner("Actualizando base de datos..."):
                    # Extraemos los IDs de las especificaciones que están en pantalla
                    ids_a_marcar = df_join['id'].tolist()
                    
                    # Supabase requiere hacer updates en lotes si son muchos, o un in_
                    # Hacemos el update masivo:
                    supabase.table('especificaciones_producto').update(
                        {"polines_comprados": True}
                    ).in_('id', ids_a_marcar).execute()
                    
                    st.success("¡Compra registrada exitosamente! Los polines han sido retirados de la lista.")
                    time.sleep(1.5)
                    st.rerun()
                    
            except Exception as e:
                st.error(f"Error al registrar la compra: {e}")