import streamlit as st
import pandas as pd
import datetime
import time
import uuid
import requests
import os


# ==============================================================================
# GRUPO A: FUNCIONES AUXILIARES Y UTILIDADES
# ==============================================================================

def subir_img(supabase, archivo_streamlit, carpeta="bocetos"):
    try:
        file_bytes = archivo_streamlit.getvalue()
        nombre = f"{carpeta}/{int(time.time())}_{uuid.uuid4()}.jpg"
        supabase.storage.from_("ordenes_produccion").upload(
            path=nombre, 
            file=file_bytes, 
            file_options={"content-type": "image/jpeg"}
        )
        return supabase.storage.from_("ordenes_produccion").get_public_url(nombre)
    except Exception as e: 
        st.error(f"Error subida imagen: {e}")
        return None

def cod_ord(supabase):
    try:
        res = supabase.table('ordenes').select("codigo_orden").execute()
        codigos = [d['codigo_orden'] for d in res.data if d.get('codigo_orden')]
        max_num = 6404  
        for c in codigos:
            partes = c.split('-') 
            if len(partes) == 2 and partes[1].isdigit():
                num = int(partes[1])
                if num > max_num:
                    max_num = num
        return f"ORD-{str(max_num + 1).zfill(4)}"
    except Exception as e: 
        return "ORD-6405" 

def limpiar_texto_pdf(texto):
    if not texto: return ""
    reemplazos = {"│": "|", "–": "-", "“": '"', "”": '"', "’": "'", "‘": "'", "Ñ": "N", "ñ": "n", "°": " degrees", "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u"}
    t = str(texto)
    for k, v in reemplazos.items(): t = t.replace(k, v)
    return t.encode('latin-1', 'replace').decode('latin-1')

def borrar_img(supabase, url_archivo):
    """Borra un archivo del bucket de Supabase usando su URL pública"""
    if not url_archivo: return
    try:
        ruta_relativa = url_archivo.split("/ordenes_produccion/")[-1]
        supabase.storage.from_("ordenes_produccion").remove([ruta_relativa])
    except Exception as e:
        print(f"No se pudo borrar imagen antigua: {e}")


# ==============================================================================
# GRUPO C: LÓGICA PRINCIPAL (RENDER)
# ==============================================================================

def render(supabase):
    st.title("🏭 Producción y Órdenes")

    # --- INICIALIZACIÓN DE ESTADOS ---
    if 'vista_prod' not in st.session_state: st.session_state['vista_prod'] = "LISTA"
    if 'prod_items' not in st.session_state: st.session_state['prod_items'] = []
    if 'form_data_cache' not in st.session_state: st.session_state['form_data_cache'] = None
    if 'reset_matrix_key' not in st.session_state: st.session_state['reset_matrix_key'] = 0
    if 'url_boceto_view' not in st.session_state: st.session_state['url_boceto_view'] = None
    if 'url_diseno_view' not in st.session_state: st.session_state['url_diseno_view'] = None
    if 'editando_cliente_id' not in st.session_state: st.session_state['editando_cliente_id'] = None
    if 'editando_orden_id' not in st.session_state: st.session_state['editando_orden_id'] = None
    if 'editando_orden_cod' not in st.session_state: st.session_state['editando_orden_cod'] = None

    # --------------------------------------------------------------------------
    # C.1: VISTA 1 - TABLERO DE ÓRDENES (LISTA)
    # --------------------------------------------------------------------------
    if st.session_state['vista_prod'] == "LISTA":
        st.subheader("Tablero de Producción")
        
        with st.container(border=True):
            c_new, c_txt, c_des, c_has = st.columns([1.2, 2, 1, 1])
            
            if c_new.button("➕ NUEVA ORDEN", type="primary", use_container_width=True):
                st.session_state['editando_orden_id'] = None
                st.session_state['prod_items'] = []
                st.session_state['url_boceto_view'] = None
                st.session_state['url_diseno_view'] = None
                st.session_state['editando_cliente_id'] = None
                st.session_state['fecha_entrega_edit'] = datetime.date.today() 
                st.session_state['editando_obs_g'] = "" # <--- NUEVO: Limpiamos la memoria de las observaciones
                st.session_state['vista_prod'] = "EDITOR"
                st.rerun()
            txt_bus = c_txt.text_input("Buscar", placeholder="Cliente / Código Orden", label_visibility="collapsed")
            f_des = c_des.date_input("Desde", value=datetime.date.today()-datetime.timedelta(days=30))
            f_has = c_has.date_input("Hasta", value=datetime.date.today())

        q = supabase.table('ordenes').select("*, clientes(id, nombre_completo, cedula_ruc, telefono)").order('created_at', desc=True)
        q = q.gte('created_at', str(f_des)).lte('created_at', str(f_has)+" 23:59:59")
        
        with st.spinner("Cargando órdenes..."):
            res = q.execute()
            df_todas = pd.DataFrame(res.data)
        
        row_seleccionada = None 

        if not df_todas.empty:
            df_todas['Cliente'] = df_todas['clientes'].apply(lambda x: x['nombre_completo'] if x else 'S/N')
            df_todas['estado'] = df_todas['estado'].fillna("PENDIENTE DISEÑO")

            if txt_bus: 
                df_todas = df_todas[
                    df_todas['codigo_orden'].str.contains(txt_bus, case=False, na=False) | 
                    df_todas['Cliente'].str.contains(txt_bus, case=False, na=False)
                ]
            
            cols_mostrar = ['codigo_orden', 'Cliente', 'fecha_entrega', 'estado', 'total_estimado', 'saldo_pendiente']
            cfg_df = {"use_container_width": True, "hide_index": True, "on_select": "rerun", "selection_mode": "single-row"}

            df_todas["saldo_pendiente"] = df_todas["saldo_pendiente"].astype(float)

            estados_nuevas = ["PENDIENTE DISEÑO", "EN DISEÑO"]
            df_nuevas = df_todas[(df_todas["saldo_pendiente"] > 0) & (df_todas["estado"].str.upper().isin(estados_nuevas))].copy()
            df_proceso = df_todas[(df_todas["saldo_pendiente"] > 0) & (~df_todas["estado"].str.upper().isin(estados_nuevas))].copy()
            df_finalizadas = df_todas[df_todas["saldo_pendiente"] <= 0].copy()

            st.write("") 
            
            t_nue, t_pro, t_fin = st.tabs([
                f"🆕 Nuevas ({len(df_nuevas)})", 
                f"⚙️ En Proceso ({len(df_proceso)})", 
                f"✅ Finalizadas ({len(df_finalizadas)})"
            ])

            with t_nue:
                sel_nue = st.dataframe(df_nuevas[cols_mostrar], key="grid_nuevas", **cfg_df)
            
            with t_pro:
                sel_pro = st.dataframe(df_proceso[cols_mostrar], key="grid_proceso", **cfg_df)
            
            with t_fin:
                sel_fin = st.dataframe(df_finalizadas[cols_mostrar], key="grid_finalizadas", **cfg_df)

            df_origen = None
            idx_sel = None

            if sel_nue.selection.rows:
                df_origen = df_nuevas
                idx_sel = sel_nue.selection.rows[0]
            elif sel_pro.selection.rows:
                df_origen = df_proceso
                idx_sel = sel_pro.selection.rows[0]
            elif sel_fin.selection.rows:
                df_origen = df_finalizadas
                idx_sel = sel_fin.selection.rows[0]

            if df_origen is not None and idx_sel is not None:
                row_seleccionada = df_origen.iloc[idx_sel]
        
        else:
            st.info("No se encontraron órdenes en el rango de fechas seleccionado.")

        if row_seleccionada is not None:
            st.divider()
            c_edit, c_del, c_sp = st.columns([2, 2, 4]) 

            id_s = int(row_seleccionada['id'])
            cod_on = row_seleccionada['codigo_orden']

            if c_del.button(f"🗑️ Eliminar Orden {cod_on}", type="secondary", use_container_width=True):
                try:
                    try:
                        abono = float(row_seleccionada.get('abono_inicial', 0))
                    except:
                        abono = 0.0
                    
                    if abono > 0:
                        try:
                            cliente_id_val = int(row_seleccionada['cliente_id'])
                        except:
                            cliente_id_val = None
                        
                        supabase.table('pagos').insert({
                            "orden_id": None, 
                            "cliente_id": cliente_id_val,
                            "monto": -abono, 
                            "metodo_pago": "DEVOLUCION",
                            "fecha_pago": str(datetime.date.today()), 
                            "numero_referencia": f"Devolución Orden Eliminada {cod_on}"
                        }).execute()
                    
                    supabase.table('pagos').update({"orden_id": None}).eq('orden_id', id_s).execute()

                    borrar_img(supabase, row_seleccionada.get('url_boceto_vendedora'))
                    borrar_img(supabase, row_seleccionada.get('url_arte_final'))
                    
                    items_actuales = supabase.table('items_orden').select('id').eq('orden_id', id_s).execute().data
                    ids_items = [item['id'] for item in items_actuales]
                    
                    if ids_items:
                        supabase.table('especificaciones_producto').delete().in_('item_orden_id', ids_items).execute()
                    
                    supabase.table('items_orden').delete().eq('orden_id', id_s).execute()
                    supabase.table('ordenes').delete().eq('id', id_s).execute()
                    
                    st.success(f"Orden {cod_on} eliminada correctamente.")
                    time.sleep(1.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error crítico al eliminar: {e}")
            
            if c_edit.button(f"📝 Editar Orden {cod_on}", type="primary", use_container_width=True):
                with st.spinner("Cargando datos de la orden..."):
                    items_db = supabase.table('items_orden').select("*, productos_catalogo(*)").eq('orden_id', id_s).execute().data
                    recup = []
                    
                    for i in items_db:
                        sp = supabase.table('especificaciones_producto').select("*").eq('item_orden_id', i['id']).execute().data
                        
                        det_f = []
                        for s in sp:
                            d = {
                                "talla_superior": s.get('talla_superior'),
                                "talla_inferior": s.get('talla_inferior'),
                                "nombre_jugador": s.get('nombre_jugador'),
                                "numero_dorsal": s.get('numero_dorsal'),
                                "talla_polines": s.get('talla_polines'),
                                "color_polines": s.get('color_polines'),
                                "es_arquero": s.get('es_arquero'),
                                "genero": s.get('genero'),
                                "observacion_individual": s.get('observacion_individual'),
                                "tipo_cuello_texto": s.get('tipo_cuello_texto', ""),
                                "ancho_cm": float(s.get('ancho_cm', 0.0) or 0.0),
                                "alto_cm": float(s.get('alto_cm', 0.0) or 0.0),
                                "acabado": s.get('acabado', ""),
                                "calandra_si_no": s.get('calandra_si_no', False)
                            }
                            det_f.append(d)
                        
                        recup.append({
                            "familia": i['familia_producto'],
                            "obj_p": i['productos_catalogo'],
                            "id_tela": i['insumo_base_id'],
                            "precio_venta": float(i['precio_aplicado']),
                            "detalles": det_f
                        })
                    
                    st.session_state['prod_items'] = recup
                    st.session_state['editando_orden_id'] = id_s
                    st.session_state['editando_orden_cod'] = cod_on
                    st.session_state['url_boceto_view'] = row_seleccionada['url_boceto_vendedora']
                    st.session_state['url_diseno_view'] = row_seleccionada.get('url_arte_final')
                    st.session_state['editando_cliente_id'] = row_seleccionada['cliente_id'] 
                    st.session_state['editando_obs_g'] = row_seleccionada.get('observaciones_generales', "")
                    
                    try:
                        f_db = row_seleccionada.get('fecha_entrega')
                        if f_db:
                            st.session_state['fecha_entrega_edit'] = datetime.datetime.strptime(f_db, "%Y-%m-%d").date()
                        else:
                            st.session_state['fecha_entrega_edit'] = datetime.date.today()
                    except:
                        st.session_state['fecha_entrega_edit'] = datetime.date.today()
                    
                    st.session_state['vista_prod'] = "EDITOR"
                    st.rerun()

    # --------------------------------------------------------------------------
    # C.2: VISTA 2 - EDITOR DE ORDEN (NUEVO/EDITAR)
    # --------------------------------------------------------------------------
    elif st.session_state['vista_prod'] == "EDITOR":
        c_h1, c_h2 = st.columns([1, 5])
        if c_h1.button("⬅️ Volver"): st.session_state['vista_prod']="LISTA"; st.rerun()
        tit = f"Editando: {st.session_state['editando_orden_cod']}" if st.session_state.get('editando_orden_id') else "Nueva Orden"
        c_h2.header(tit)
        
        # 1. CLIENTE Y ENCABEZADO DE ORDEN (CON DISEÑADOR Y CREADOR)
        with st.container(border=True):
            # Fila 1: Selección de Cliente (Igual que antes)
            c1, c2 = st.columns([3, 1])
            clis = supabase.table('clientes').select("id, nombre_completo, cedula_ruc").execute().data
            mapa_cli = {f"{c['nombre_completo']} | {c['cedula_ruc']}": c['id'] for c in clis}
            
            idx_sel = 0
            if st.session_state.get('editando_cliente_id'):
                found = next((k for k, v in mapa_cli.items() if v == st.session_state['editando_cliente_id']), None)
                if found in list(mapa_cli.keys()): idx_sel = list(mapa_cli.keys()).index(found) + 1

            sel_cli = c1.selectbox("Cliente", [""] + list(mapa_cli.keys()), index=idx_sel)
            if sel_cli: st.session_state['editando_cliente_id'] = mapa_cli[sel_cli]

            # Botón Nuevo Cliente (Mantenemos tu lógica existente)
            with c2.popover("➕ Crear Cliente Nuevo", use_container_width=True):
                with st.form("nc_full", clear_on_submit=True):
                    st.markdown("##### Nuevo Cliente")
                    f_ruc = st.text_input("RUC/CI *", key="new_cli_ruc")
                    f_nom = st.text_input("Nombre *", key="new_cli_nom")
                    f_tel = st.text_input("Telf")
                    f_ema = st.text_input("Email")
                    f_ciu = st.text_input("Ciudad")
                    f_tip = st.selectbox("Tipo", ["Cliente Final", "Escuela", "Empresa", "Fiscal"])
                    f_gen = st.selectbox("Género", ["Masculino", "Femenino", "Otro"])
                    
                    if st.form_submit_button("Guardar Cliente"):
                        if f_ruc and f_nom:
                            res_c = supabase.table('clientes').insert({
                                "cedula_ruc": f_ruc, "nombre_completo": f_nom.upper(), "telefono": f_tel, 
                                "email": f_ema, "ciudad": f_ciu, "tipo_institucion": f_tip, "genero": f_gen
                            }).execute()
                            if res_c.data:
                                st.session_state['editando_cliente_id'] = res_c.data[0]['id']
                                st.success("Cliente guardado"); time.sleep(0.5); st.rerun()
                        else: st.error("RUC y Nombre obligatorios")

            # --- SECCIÓN: RESPONSABLES Y FECHA DE ENTREGA ---
            st.write("---")
            c_dis, c_fec, c_usu = st.columns([2, 1, 1])
            
            # 1. Selector de Diseñador
            LISTA_DISENADORES = ["DISEÑADOR 1", "DISEÑADOR 2", "POR ASIGNAR"]
            disenador_sel = c_dis.selectbox("🎨 Diseñador Asignado", LISTA_DISENADORES)
            
            # 2. Selector de Fecha (Con Validación de Domingo)
            val_fec = st.session_state.get('fecha_entrega_edit', datetime.date.today())
            f_entrega = c_fec.date_input("📅 Fecha Entrega", value=val_fec, format="DD/MM/YYYY")
            
            # Lógica de bloqueo visual para Domingos (weekday 6)
            es_domingo = False
            if f_entrega.weekday() == 6:
                es_domingo = True
                c_fec.error("⛔ Domingo no laborable")
            
            # 3. Generado Por
            usuario_logueado = st.session_state.get('nombre_usuario', 'Usuario Actual') 
            c_usu.text_input("👤 Generado Por", value=usuario_logueado, disabled=True)

        # --- SECCIÓN: GESTIÓN DE ARCHIVOS (CORREGIDO: SIN DUPLICADOS) ---
        st.subheader("Archivos del Pedido")
        c_boc, c_art = st.columns(2)
        
        # 1. BOCETO
        with c_boc:
            st.info("📌 Boceto Original")
            if st.session_state.get('url_boceto_view'):
                st.image(st.session_state['url_boceto_view'], width=200)
                if st.button("🗑️ Eliminar Boceto", key="d_boc"):
                    # Borrar de la nube
                    borrar_img(supabase, st.session_state['url_boceto_view'])
                    # Borrar de memoria
                    st.session_state['url_boceto_view'] = None
                    # Actualizar BD si estamos editando
                    if st.session_state.get('editando_orden_id'):
                        supabase.table('ordenes').update({'url_boceto_vendedora': None}).eq('id', st.session_state['editando_orden_id']).execute()
                    st.rerun()
            else:
                boceto_file = st.file_uploader("Subir Boceto", type=["jpg", "png", "pdf"], key="up_boc")
                if boceto_file:
                    url_b = subir_img(supabase, boceto_file, "bocetos")
                    if url_b:
                        st.session_state['url_boceto_view'] = url_b
                        st.success("Subido correctamente"); time.sleep(0.5); st.rerun()
        
        # 2. DISEÑO FINAL
        with c_art:
            st.success("🎨 Diseño Final")
            if st.session_state.get('url_diseno_view'):
                st.image(st.session_state['url_diseno_view'], width=200)
                if st.button("🗑️ Eliminar Diseño", key="d_art"):
                    # Borrar de la nube
                    borrar_img(supabase, st.session_state['url_diseno_view'])
                    st.session_state['url_diseno_view'] = None
                    if st.session_state.get('editando_orden_id'):
                        supabase.table('ordenes').update({'url_arte_final': None}).eq('id', st.session_state['editando_orden_id']).execute()
                    st.rerun()
            else:
                arte_file = st.file_uploader("Cargar Diseño Final", type=["jpg", "png", "pdf"], key="up_art")
                if arte_file:
                    url_a = subir_img(supabase, arte_file, "artes")
                    if url_a:
                        st.session_state['url_diseno_view'] = url_a
                        st.success("Subido correctamente"); time.sleep(0.5); st.rerun()

        # --- SECCIÓN: BÚSQUEDA DE PRODUCTOS (CORREGIDO: MEMORIA PERSISTENTE) ---
        st.write("---")
        st.subheader("Detalle Productos")
        cache = st.session_state['form_data_cache']
        
        with st.container(border=True):
            fam = st.selectbox("Familia", ["UNIFORME COMPLETO", "PRENDA SUPERIOR", "PANTALONETA", "IMPRESION", "GENERICO"])
            
            with st.expander("🔍 Filtros de Búsqueda (Catálogo)", expanded=True):
                prods_raw = supabase.table('productos_catalogo').select("*").eq('activo', True).execute().data
                df_p = pd.DataFrame(prods_raw)
                
                # --- LÓGICA DE AUTO-SELECCIÓN (RESTAURACIÓN) ---
                idx_p_def = 0; idx_t_def = 0; idx_cat_def = 0; idx_tp_def = 0
                
                # Recuperamos la memoria (IMPORTANTE: NO LA BORRAMOS AQUÍ)
                restore_pid = st.session_state.get('restore_product_id')
                
                if restore_pid:
                    prod_row = df_p[df_p['id'] == restore_pid]
                    if not prod_row.empty:
                        prod_data = prod_row.iloc[0]
                        # Restaurar indices de filtros
                        list_tp = ["Todos"] + sorted(list(df_p['tipo_prenda'].dropna().unique()))
                        if prod_data['tipo_prenda'] in list_tp: idx_tp_def = list_tp.index(prod_data['tipo_prenda'])
                        
                        cat_temp = sorted(list(df_p[df_p['tipo_prenda'] == prod_data['tipo_prenda']]['linea_categoria'].unique()))
                        list_cat = ["Todos"] + cat_temp
                        if prod_data['linea_categoria'] in list_cat: idx_cat_def = list_cat.index(prod_data['linea_categoria'])
                # -----------------------------------------------

                cf1, cf2, cf3 = st.columns(3)
                tp = cf1.selectbox("Prenda", ["Todos"] + sorted(list(df_p['tipo_prenda'].dropna().unique())), index=idx_tp_def)
                
                df_filtrado_cat = df_p if tp == "Todos" else df_p[df_p['tipo_prenda'] == tp]
                cat = cf2.selectbox("Categoría", ["Todos"] + sorted(list(df_filtrado_cat['linea_categoria'].dropna().unique())), index=idx_cat_def)
                eda = cf3.selectbox("Edad", ["Todos"] + sorted(list(df_p['grupo_edad'].dropna().unique())))
                
                ck1, ck2, ck3, ck4 = st.columns([1,1,1,2])
                s_sub = ck1.checkbox("Solo Sublimado")
                s_dtf = ck2.checkbox("Solo DTF")
                s_bor = ck3.checkbox("Solo Bordado")
                txt_p = ck4.text_input("Buscar texto...", placeholder="Cód o Nombre")

                df_fin = df_p.copy()
                if tp != "Todos": df_fin = df_fin[df_fin['tipo_prenda'] == tp]
                if cat != "Todos": df_fin = df_fin[df_fin['linea_categoria'] == cat]
                if eda != "Todos": df_fin = df_fin[df_fin['grupo_edad'] == eda]
                if s_sub: df_fin = df_fin[df_fin['requiere_sublimado'] == True]
                if s_dtf: df_fin = df_fin[df_fin['requiere_dtf'] == True]
                if s_bor: df_fin = df_fin[df_fin['requiere_bordado'] == True]
                if txt_p: df_fin = df_fin[df_fin['descripcion'].str.contains(txt_p, case=False) | df_fin['codigo_referencia'].str.contains(txt_p, case=False)]

                mapa_p = {f"{r['codigo_referencia']} | {r['descripcion']}": r for r in df_fin.to_dict('records')}
                
                # Restaurar selección de producto
                idx_prod_sel = 0
                if restore_pid:
                    for k, v in mapa_p.items():
                        if v['id'] == restore_pid:
                            idx_prod_sel = list(mapa_p.keys()).index(k); break
                
                sel_p_key = st.selectbox("Seleccione el producto filtrado", list(mapa_p.keys()), index=idx_prod_sel)
                prod_obj = mapa_p[sel_p_key] if sel_p_key else None
                
                # --- CONFIGURACIÓN DE TELA (INSUMOS) ---
                if prod_obj:
                    st.markdown("##### Configuración de Materiales")
                    try:
                        insumos_db = supabase.table('insumos').select("*").eq('activo', True).execute().data
                        df_ins = pd.DataFrame(insumos_db)
                        df_telas = df_ins[df_ins['categoria'].str.contains("TELA", case=False, na=False)]
                        if not df_telas.empty:
                            mapa_telas = {row['nombre']: row['id'] for _, row in df_telas.iterrows()}
                            lista_telas = ["Seleccionar..."] + sorted(list(mapa_telas.keys()))
                            
                            idx_tela_sel = 0
                            restore_fid = st.session_state.get('restore_fabric_id')
                            if restore_fid:
                                nombre_tela = next((k for k, v in mapa_telas.items() if v == restore_fid), None)
                                if nombre_tela in lista_telas: idx_tela_sel = lista_telas.index(nombre_tela)

                            sel_t = st.selectbox("🧶 Seleccionar Tela", lista_telas, index=idx_tela_sel)
                            id_t = mapa_telas[sel_t] if sel_t != "Seleccionar..." else None
                        else:
                            st.warning("No hay telas en Insumos"); id_t = None
                    except: id_t = None

            # --- SECCIÓN: CONFIGURACIÓN DE PRECIO (MANTENIDA) ---
            if prod_obj:
                c1, c2, c3 = st.columns(3)
                
                # 1. Selector de Tarifa con Deducción Inteligente
                tarifa_sel_def = 0 # Unitario por defecto
                
                restore_price = st.session_state.get('restore_price')
                if restore_price is not None:
                    if float(restore_price) == float(prod_obj.get('precio_unitario', 0)): tarifa_sel_def = 0
                    elif float(restore_price) == float(prod_obj.get('precio_docena', 0)): tarifa_sel_def = 1
                    elif float(restore_price) == float(prod_obj.get('precio_mayorista', 0)): tarifa_sel_def = 2
                    else: tarifa_sel_def = 3 # Manual
                
                # --- NUEVO: Agregamos la opción de Obsequio ---
                opciones_tarifa = ["Unitario", "Docena", "Mayorista", "Manual", "Obsequio / Cortesía"]
                
                # Para que al editar reconozca si era obsequio
                if restore_price is not None and float(restore_price) == 0.0 and tarifa_sel_def == 3:
                    tarifa_sel_def = 4 # Índice de "Obsequio"
                
                tarifa_sel = c1.selectbox(
                    "Tarifa", 
                    opciones_tarifa, 
                    index=tarifa_sel_def, 
                    key=f"tar_sel_{prod_obj['id']}"
                )
                
                # 2. Cálculo del Precio Base
                precio_base = 0.0
                es_manual = False
                
                restore_price = st.session_state.get('restore_price')
                
                if tarifa_sel == "Unitario": precio_base = float(prod_obj.get('precio_unitario', 0))
                elif tarifa_sel == "Docena": precio_base = float(prod_obj.get('precio_docena', 0))
                elif tarifa_sel == "Mayorista": precio_base = float(prod_obj.get('precio_mayorista', 0))
                elif tarifa_sel == "Obsequio / Cortesía": 
                    precio_base = 0.0
                    es_manual = False # Se bloquea en $0.00 automáticamente
                else: 
                    es_manual = True
                    if restore_price is not None and tarifa_sel_def != 4:
                        precio_base = float(restore_price)
                    else:
                        precio_base = st.session_state.get(f'p_man_val_{prod_obj["id"]}', float(prod_obj.get('precio_unitario', 0)))

                # 3. Input de Precio
                if not es_manual:
                    # Si venimos de editar y el precio coincide, perfecto. Si no, manda la tarifa.
                    prec = c2.number_input("Precio Final", value=precio_base, format="%.2f", disabled=True, key=f"p_auto_{prod_obj['id']}_{tarifa_sel}")
                else:
                    prec = c2.number_input("Precio Final (Manual)", value=precio_base, format="%.2f", disabled=False, key=f"p_man_{prod_obj['id']}")
                    st.session_state[f'p_man_val_{prod_obj["id"]}'] = prec

                # 4. PIN
                auto = True
                if es_manual:
                    pin = c3.text_input("PIN Autorización", type="password", key=f"pin_{prod_obj['id']}")
                    if pin == "1234":
                        c3.success("OK"); auto = True
                    else:
                        c3.warning("Requiere PIN"); auto = False

            # ==============================================================================
            # BLOQUE: MATRIZ DE DATOS DINÁMICA (CORREGIDA: ORDEN DE COLUMNAS)
            # ==============================================================================
            if prod_obj:
                # 1. Listas
                LISTA_TALLAS = ["24","26","28","30","32","34","36","38","40","42","XS","S","M","L","XL","2XL","3XL","4XL","5XL","6XL","7XL"]
                TALLAS_POLIN = ["4-6", "6-8", "8-10", "10-12"]
                
                # 2. Configuración de Visibilidad (Banderas)
                ver_cam = False; ver_short = False; ver_polin = False; ver_arq = False
                ver_cuello = False; ver_nombre = True; ver_medidas = False; ver_calandra = False; ver_cant = True
                ver_genero = True; ver_acabado = False
                
                if fam == "UNIFORME COMPLETO":
                    ver_cam = True; ver_short = True; ver_polin = True; ver_arq = True
                    ver_cuello = True 
                elif fam == "PRENDA SUPERIOR":
                    ver_cam = True; ver_arq = True
                    ver_cuello = True 
                elif fam == "PANTALONETA":
                    ver_short = True
                    ver_nombre = False
                elif fam == "IMPRESION":
                    ver_nombre = False 
                    ver_medidas = True; ver_calandra = True
                    ver_genero = False; ver_acabado = True
                elif fam == "GENERICO":
                    ver_nombre = False
                    ver_cant = True 
                    ver_genero = False; ver_acabado = True
                
                # 3. Inicialización de la Matriz
                if "df_temp_matriz" not in st.session_state or st.session_state.get('reset_matrix_key_trigger') or st.session_state.get('last_fam') != fam:
                    filas = []
                    for _ in range(10):
                        filas.append({
                            "Cantidad": 1, 
                            "Camiseta": None, "Pantaloneta": None, 
                            "Tipo Cuello": "", 
                            "Ancho (m)": 0.0, "Largo (m)": 0.0, "Calandrar": False,
                            "Nombre": "", "Numero": "", 
                            "Talla Polin": None, "Color Polin": "", 
                            "Arquero": False, "Genero": None, "Acabado": "", "Obs": ""
                        })
                    st.session_state['df_temp_matriz'] = pd.DataFrame(filas)
                    st.session_state['reset_matrix_key_trigger'] = False
                    st.session_state['last_fam'] = fam

                # 4. Configuración Visual de Columnas
                cols_cfg = {
                    "Nombre": st.column_config.TextColumn("Nombre Jugador", width="medium"),
                    "Numero": st.column_config.TextColumn("Dorsal", width="small"),
                    "Genero": st.column_config.SelectboxColumn("Género", options=["Masculino", "Femenino", "BVD-Hombre", "BVD-Mujer"]),
                    "Acabado": st.column_config.TextColumn("Acabado"),
                    "Obs": st.column_config.TextColumn("Observación"),
                    "Tipo Cuello": st.column_config.TextColumn("Tipo Cuello", width="small"),
                    "Ancho (m)": st.column_config.NumberColumn("Ancho (m)", format="%.2f", min_value=0.0),
                    "Largo (m)": st.column_config.NumberColumn("Largo (m)", format="%.2f", min_value=0.0), 
                    "Calandrar": st.column_config.CheckboxColumn("¿Calandra?"),
                    "Cantidad": st.column_config.NumberColumn("Cant.", min_value=1, step=1)
                }
                
                # Armamos el orden de columnas dinámicamente
                columnas_orden = []
                
                if ver_cant: columnas_orden.append("Cantidad")
                
                if ver_cam: 
                    cols_cfg["Camiseta"] = st.column_config.SelectboxColumn("Talla Sup.", options=LISTA_TALLAS)
                    columnas_orden.append("Camiseta")
                
                if ver_short: 
                    cols_cfg["Pantaloneta"] = st.column_config.SelectboxColumn("Talla Inf.", options=LISTA_TALLAS)
                    columnas_orden.append("Pantaloneta")
                
                if ver_medidas: columnas_orden.extend(["Ancho (m)", "Largo (m)"])
                if ver_calandra: columnas_orden.append("Calandrar")
                
                if ver_nombre: columnas_orden.extend(["Nombre", "Numero"])
                
                if ver_polin:
                    cols_cfg["Talla Polin"] = st.column_config.SelectboxColumn("Polín", options=TALLAS_POLIN)
                    cols_cfg["Color Polin"] = st.column_config.TextColumn("Color P.")
                    columnas_orden.extend(["Talla Polin", "Color Polin"])
                
                if ver_arq:
                    cols_cfg["Arquero"] = st.column_config.CheckboxColumn("¿Arq?")
                    columnas_orden.append("Arquero")
                
                if ver_genero: columnas_orden.append("Genero")
                if ver_acabado: columnas_orden.append("Acabado")
                
                if ver_cuello: columnas_orden.append("Tipo Cuello")
                
                columnas_orden.append("Obs")

                # Renderizar Editor
                st.info(f"📋 **Llenando datos para:** {fam}")
                edit_df = st.data_editor(
                    st.session_state['df_temp_matriz'], 
                    column_order=columnas_orden, 
                    column_config=cols_cfg, 
                    num_rows="dynamic", 
                    use_container_width=True,
                    key=f"ed_{st.session_state['reset_matrix_key']}"
                )

                # 5. Validación y Guardado
                col_btn, col_check = st.columns([2, 2])
                permitir_dups = col_check.checkbox("⚠️ Autorizar duplicados")
                
                if col_btn.button("➕ Agregar al Resumen", use_container_width=True):
                    # Filtro inteligente
                    condicion = pd.Series([False] * len(edit_df))
                    
                    # Validamos si llenaron Tallas, Medidas o Nombres
                    if ver_cam: condicion |= edit_df['Camiseta'].notna()
                    if ver_short: condicion |= edit_df['Pantaloneta'].notna()
                    if ver_medidas: condicion |= edit_df['Largo (m)'] > 0 
                    if ver_nombre: condicion |= edit_df['Nombre'].str.strip() != ""
                    
                    # Si es Genérico (no usa tallas ni nombres), validamos solo por la cantidad
                    if fam == "GENERICO": condicion |= edit_df['Cantidad'] > 0
                    
                    df_final = edit_df[condicion].copy()
                    
                    if df_final.empty:
                        st.error("⚠️ Debe ingresar datos válidos (Tallas, Largo o Cantidad) para continuar.")
                    else:
                        errores = []
                        if ver_nombre:
                            nombres = df_final[df_final['Nombre'].str.strip() != ""]['Nombre']
                            if nombres.duplicated().any(): errores.append(f"Nombres repetidos: {set(nombres[nombres.duplicated()].tolist())}")
                        
                        if errores and not permitir_dups:
                            st.error("⛔ ERROR DE DUPLICADOS:")
                            for e in errores: st.write(f"- {e}")
                        else:
                            # Cálculo de cantidad
                            cantidad_grupo = 0.0
                            if ver_medidas: cantidad_grupo = df_final['Largo (m)'].sum()
                            elif ver_cant: cantidad_grupo = df_final['Cantidad'].sum()
                            else: cantidad_grupo = len(df_final)

                          # --- MAPEO A BASE DE DATOS (CON SANITIZACIÓN DE NAN) ---
                            detalles_db = []
                            for _, r in df_final.iterrows():
                                # Limpiamos los NaN de Pandas que causan el error crítico
                                cant = r.get("Cantidad", 1)
                                cant = 1 if pd.isna(cant) else int(cant)
                                
                                ancho = r.get("Ancho (m)", 0.0)
                                ancho = 0.0 if pd.isna(ancho) else float(ancho)
                                
                                alto = r.get("Largo (m)", 0.0)
                                alto = 0.0 if pd.isna(alto) else float(alto)
                                
                                detalles_db.append({
                                    "talla_superior": None if pd.isna(r.get("Camiseta")) else r.get("Camiseta"),
                                    "talla_inferior": None if pd.isna(r.get("Pantaloneta")) else r.get("Pantaloneta"),
                                    "nombre_jugador": "" if pd.isna(r.get("Nombre")) else r.get("Nombre", ""), 
                                    "numero_dorsal": "" if pd.isna(r.get("Numero")) else r.get("Numero", ""),
                                    "talla_polines": None if pd.isna(r.get("Talla Polin")) else r.get("Talla Polin"),
                                    "color_polines": "" if pd.isna(r.get("Color Polin")) else r.get("Color Polin", ""),
                                    "es_arquero": False if pd.isna(r.get("Arquero")) else r.get("Arquero", False),
                                    "genero": None if pd.isna(r.get("Genero")) else r.get("Genero"),
                                    "observacion_individual": "" if pd.isna(r.get("Obs")) else r.get("Obs", ""),
                                    "tipo_cuello_texto": "" if pd.isna(r.get("Tipo Cuello")) else r.get("Tipo Cuello", ""),
                                    "ancho_cm": ancho, 
                                    "alto_cm": alto,  
                                    "calandra_si_no": False if pd.isna(r.get("Calandrar")) else r.get("Calandrar", False),
                                    "acabado": "" if pd.isna(r.get("Acabado")) else r.get("Acabado", ""),
                                    "_cantidad_manual": cant 
                                })

                            st.session_state['prod_items'].append({
                                "familia": fam, "obj_p": prod_obj, "id_tela": id_t, 
                                "detalles": detalles_db, "precio_venta": prec,
                                "cantidad_total_cobro": cantidad_grupo 
                            })
                            
                            st.session_state['restore_product_id'] = None
                            st.session_state['restore_fabric_id'] = None
                            st.session_state['restore_price'] = None
                            
                            st.session_state['reset_matrix_key_trigger'] = True
                            st.session_state['reset_matrix_key'] += 1
                            st.rerun()

        # ==============================================================================
        # BLOQUE 4: RESUMEN Y GUARDADO (CON EDICIÓN CORREGIDA)
        # ==============================================================================
        if st.session_state['prod_items']:
            st.divider()
            st.subheader("📋 Resumen de la Orden")
            
            tot = 0.0
            
            # Iteramos sobre los items guardados
            for i, it in enumerate(st.session_state['prod_items']):
                # USAMOS LA CANTIDAD CALCULADA (Metros o Unidades)
                cant = it.get('cantidad_total_cobro', len(it['detalles']))
                sub = cant * float(it['precio_venta'])
                tot += sub
                
                # Etiqueta inteligente
                unidad_txt = "u"
                if "IMPRESION" in it['familia']: unidad_txt = "m"
                
                titulo_item = f"📦 {it['obj_p']['descripcion']} ({cant:.2f} {unidad_txt}) - ${sub:.2f}"
                
                with st.expander(titulo_item, expanded=False):
                    df_resumen = pd.DataFrame(it['detalles'])
                    
                    # 1. Renombrar columnas
                    renombres = {
                        "_cantidad_manual": "Cant.",
                        "talla_superior": "T. Sup",
                        "talla_inferior": "T. Inf",
                        "nombre_jugador": "Nombre",
                        "numero_dorsal": "Dorsal",
                        "talla_polines": "Polín",
                        "color_polines": "Color Polín",
                        "es_arquero": "¿Arq?",
                        "genero": "Género",
                        "tipo_cuello_texto": "Cuello",
                        "ancho_cm": "Ancho (m)",
                        "alto_cm": "Largo (m)",
                        "acabado": "Acabado",
                        "calandra_si_no": "¿Calandra?",
                        "observacion_individual": "Obs."
                    }
                    df_resumen = df_resumen.rename(columns=renombres)
                    
                    # 2. Filtrar columnas según familia
                    fam_resumen = str(it.get('familia', 'GENERICO')).strip().upper()
                    cols_permitidas = ["Cant."] 
                    
                    if fam_resumen == "UNIFORME COMPLETO":
                        cols_permitidas.extend(["T. Sup", "T. Inf", "Nombre", "Dorsal", "Polín", "Color Polín", "¿Arq?", "Género", "Cuello"])
                    elif fam_resumen == "PRENDA SUPERIOR":
                        cols_permitidas.extend(["T. Sup", "Nombre", "Dorsal", "¿Arq?", "Género", "Cuello"])
                    elif fam_resumen == "PANTALONETA":
                        cols_permitidas.extend(["T. Inf", "Dorsal"])
                    elif fam_resumen == "IMPRESION":
                        cols_permitidas.extend(["Ancho (m)", "Largo (m)", "Acabado", "¿Calandra?"])
                    else: # GENERICO
                        cols_permitidas.extend(["Acabado"])
                        
                    cols_permitidas.append("Obs.")
                    
                    # 3. Aplicar el filtro base
                    cols_finales = [c for c in cols_permitidas if c in df_resumen.columns]
                    df_resumen_filtrado = df_resumen[cols_finales].copy()
                    
                    # 4. SUPER FILTRO: Eliminar columnas 100% vacías (Evita errores de UI en Streamlit)
                    df_resumen_filtrado = df_resumen_filtrado.replace(["", "None", "NaN", "nan", None], pd.NA)
                    df_resumen_filtrado = df_resumen_filtrado.dropna(axis=1, how='all')
                    df_resumen_filtrado = df_resumen_filtrado.fillna("") 
                    
                    # 5. Renderizamos el dataframe ya bonito, filtrado y pulido
                    # --- NUEVO: RESALTADO AMARILLO PARA ARQUEROS ---
                    def resaltar_arquero(row):
                        # Si la columna existe y la casilla está marcada (True)
                        if '¿Arq?' in row.index and row['¿Arq?'] == True:
                            return ['background-color: #FFF2CC; color: black'] * len(row) # Amarillo suave
                        return [''] * len(row)
                        
                    # Aplicamos el estilo al dataframe antes de renderizarlo
                    df_estilizado = df_resumen_filtrado.style.apply(resaltar_arquero, axis=1)
                    st.dataframe(df_estilizado, use_container_width=True)
                    
                    col_edit, col_del = st.columns([1, 5])
                    
                    # --- BOTÓN EDITAR (RECUPERACIÓN COMPLETA INCLUYENDO ACABADO) ---
                    if col_edit.button("✏️ Editar", key=f"btn_edit_{i}"):
                        # 1. Recuperar Metadata
                        st.session_state['restore_product_id'] = it['obj_p']['id']
                        st.session_state['restore_fabric_id'] = it['id_tela']
                        st.session_state['restore_price'] = it['precio_venta']
                        
                        # 2. Recuperar Datos de Filas
                        datos_recuperados = []
                        for row in it['detalles']:
                            datos_recuperados.append({
                                "Camiseta": row.get('talla_superior'),
                                "Pantaloneta": row.get('talla_inferior'),
                                "Nombre": row.get('nombre_jugador'),
                                "Numero": row.get('numero_dorsal'),
                                "Talla Polin": row.get('talla_polines'),
                                "Color Polin": row.get('color_polines'),
                                "Arquero": row.get('es_arquero'),
                                "Genero": row.get('genero'),
                                "Obs": row.get('observacion_individual'),
                                "Tipo Cuello": row.get('tipo_cuello_texto', ""),
                                "Ancho (m)": row.get('ancho_cm', 0.0),
                                "Largo (m)": row.get('alto_cm', 0.0),
                                "Calandrar": row.get('calandra_si_no', False),
                                "Acabado": row.get('acabado', ""), # RECUPERAR ACABADO
                                "Cantidad": row.get('_cantidad_manual', 1)
                            })
                        
                        # Rellenar vacíos
                        while len(datos_recuperados) < 10:
                            datos_recuperados.append({
                                "Cantidad": 1, "Camiseta": None, "Pantaloneta": None, 
                                "Tipo Cuello": "", "Ancho (m)": 0.0, "Largo (m)": 0.0, "Calandrar": False,
                                "Nombre": "", "Numero": "", "Talla Polin": None, "Color Polin": "", 
                                "Arquero": False, "Genero": None, "Acabado": "", "Obs": ""
                            })

                        # 3. Cargar
                        st.session_state['df_temp_matriz'] = pd.DataFrame(datos_recuperados)
                        st.session_state['prod_items'].pop(i)
                        
                        # 4. Recargar
                        st.session_state['reset_matrix_key'] += 1
                        st.toast("Datos cargados para edición.", icon="✏️")
                        time.sleep(0.5)
                        st.rerun()

                    # --- NUEVO: BOTÓN ELIMINAR ---
                    if col_del.button("🗑️ Eliminar Grupo", type="primary", key=f"btn_del_item_{i}"):
                        st.session_state['prod_items'].pop(i)
                        st.toast("Productos eliminados del resumen", icon="🗑️")
                        st.rerun()

            
            # ==========================================
            # SECCIÓN FINANZAS Y OBSERVACIONES
            # ==========================================
            st.divider()
            
            es_edicion_ui = True if st.session_state.get('editando_orden_id') else False
            
            c_fin, c_obs = st.columns([1.5, 2])
            
            # --- VARIABLES POR DEFECTO PARA LA BASE DE DATOS ---
            metodo_pago = "Efectivo"
            banco_destino = None
            num_ref = None
            detalle_cambios_txt = ""

            with c_fin:
                st.markdown("### 💰 Finanzas de la Orden")
                
                mnt = st.number_input(
                    "Abono Inicial ($)", 
                    value=0.0, 
                    max_value=float(tot),
                    disabled=es_edicion_ui, 
                    help="Los pagos adicionales se registran en Finanzas." if es_edicion_ui else ""
                )
                
                # Total y Saldo dinámicos
                saldo_restante = tot - mnt
                col_t, col_s = st.columns(2)
                col_t.metric("Total Orden", f"${tot:.2f}")
                col_s.metric("Saldo Pendiente", f"${saldo_restante:.2f}")

                # --- NUEVO: DETALLES DEL PAGO (Solo en creacion y con dinero) ---
                if mnt > 0 and not es_edicion_ui:
                    metodo_pago = st.selectbox("Método de Pago", ["Efectivo", "Transferencia", "Depósito", "Tarjeta", "Otro"])
                    if metodo_pago in ["Transferencia", "Depósito"]:
                        b_col1, b_col2 = st.columns(2)
                        banco_destino = b_col1.selectbox("Banco Destino", ["Pichincha", "Guayaquil", "Pacífico", "Produbanco", "Bolivariano", "Otro"])
                        num_ref = b_col2.text_input("Núm. Comprobante")

            with c_obs:
                st.markdown("### 📝 Notas y Actualizaciones")
                val_obs = st.session_state.get('editando_obs_g', "")
                obs_g = st.text_area(
                    "Observaciones Generales de la Orden", 
                    value=val_obs, 
                    height=100,
                    placeholder="Escriba aquí notas de confección o instrucciones generales..."
                )
                
                # --- NUEVO: MOTIVO DE EDICIÓN ---
                if es_edicion_ui:
                    st.warning("⚠️ Estás editando una orden existente.")
                    detalle_cambios_txt = st.text_area(
                        "¿Qué cambios realizaste? (Obligatorio para notificar a diseño)",
                        placeholder="Ej: Se cambió la talla del jugador X, o se cambió el cuello...",
                        height=100
                    )

            # Lógica de bloqueo (Domingo o falta justificar cambio)
            btn_disabled = False
            if locals().get('es_domingo'): 
                btn_disabled = True
            if es_edicion_ui and not detalle_cambios_txt.strip():
                btn_disabled = True # Obliga a la vendedora a escribir algo si está editando

            if st.button("💾 GUARDAR ORDEN", type="primary", use_container_width=True, disabled=btn_disabled):
                try:
                    # 1. Definir si es NUEVA o EDICIÓN
                    es_edicion = True if st.session_state.get('editando_orden_id') else False
                    cod = st.session_state['editando_orden_cod'] if es_edicion else cod_ord(supabase)
                    
                    fecha_final = str(f_entrega) if 'f_entrega' in locals() else str(datetime.date.today())
                    
                    # 2. Datos Base (Comunes para ambas acciones)
                    cab = {
                        "codigo_orden": cod, 
                        "cliente_id": st.session_state['editando_cliente_id'], 
                        "fecha_entrega": fecha_final, 
                        "total_estimado": tot, 
                        "abono_inicial": mnt, 
                        "saldo_pendiente": tot - mnt, 
                        "observaciones_generales": obs_g,
                        "disenador_asignado": disenador_sel,
                        "url_boceto_vendedora": st.session_state.get('url_boceto_view'),
                        "url_arte_final": st.session_state.get('url_diseno_view')
                    }
                    
                    # 3. Lógica Diferenciada (AQUÍ ESTÁ LA MAGIA)
                    if es_edicion:
                        id_o = st.session_state['editando_orden_id']
                        cab["alerta_cambios"] = True 
                        cab["detalle_cambios"] = detalle_cambios_txt.strip() # --- NUEVO: GUARDAR DETALLE ---
                        
                        # --- NUEVO: RECALCULAR SALDO PENDIENTE REAL ---
                        res_pagos = supabase.table('pagos').select('monto').eq('orden_id', id_o).execute()
                        total_pagado = sum([float(p['monto']) for p in res_pagos.data]) if res_pagos.data else 0.0
                        
                        cab["saldo_pendiente"] = tot - total_pagado
                        cab.pop("abono_inicial", None)
                        
                        supabase.table('ordenes').update(cab).eq('id', id_o).execute()
                        
                        # --- CORRECCIÓN ERROR 400: Borrar en cascada manual ---
                        items_actuales = supabase.table('items_orden').select('id').eq('orden_id', id_o).execute().data
                        ids_items = [item['id'] for item in items_actuales]
                        
                        if ids_items:
                            supabase.table('especificaciones_producto').delete().in_('item_orden_id', ids_items).execute()
                        
                        supabase.table('items_orden').delete().eq('orden_id', id_o).execute()
                    else:
                        id_o = st.session_state.get('id_usuario', 1) 
                        
                        cab["estado"] = "Pendiente"
                        cab["alerta_cambios"] = False
                        cab["detalle_cambios"] = ""
                        cab["creado_por_id"] = id_o
                        
                        res_o = supabase.table('ordenes').insert(cab).execute()
                        id_o = res_o.data[0]['id']

                        # 🟢 INTEGRACIÓN FINANZAS: Registrar el Abono completo en Pagos
                        if mnt > 0:
                            supabase.table('pagos').insert({
                                "orden_id": id_o,
                                "cliente_id": st.session_state['editando_cliente_id'],
                                "monto": mnt,
                                "metodo_pago": metodo_pago, # Guardamos Transferencia, Tarjeta, etc
                                "banco_destino": banco_destino, # Guardamos Banco
                                "numero_referencia": num_ref, # Guardamos Referencia
                                "fecha_pago": fecha_final
                            }).execute()

                    # 4. Guardar Items y Especificaciones
                    for it in st.session_state['prod_items']:
                        
                        # A. Calculamos la cantidad real sumando la columna Cantidad de la matriz
                        cantidad_real_prendas = sum(int(d.get("_cantidad_manual", 1) if pd.notna(d.get("_cantidad_manual")) else 1) for d in it['detalles'])

                        item_data = {
                            "orden_id": id_o, 
                            "producto_id": it['obj_p']['id'], 
                            "familia_producto": it['familia'], 
                            "insumo_base_id": it['id_tela'], 
                            "cantidad_total": cantidad_real_prendas, # Usamos la cantidad multiplicada
                            "precio_aplicado": it['precio_venta']
                        }
                        ri = supabase.table('items_orden').insert(item_data).execute()
                        ii = ri.data[0]['id']
                        
                        batch_especs = []
                        for d in it['detalles']:
                            # B. Obtenemos cuántas veces debemos repetir esta fila
                            cantidad_fila = int(d.get("_cantidad_manual", 1) if pd.notna(d.get("_cantidad_manual")) else 1)
                            
                            # C. Bucle multiplicador (Opción B)
                            for _ in range(cantidad_fila):
                                esp = {
                                    "item_orden_id": ii, 
                                    "nombre_jugador": d.get("nombre_jugador"), 
                                    "numero_dorsal": str(d.get("numero_dorsal")) if d.get("numero_dorsal") else None, 
                                    "talla_superior": d.get("talla_superior"), 
                                    "talla_inferior": d.get("talla_inferior"), 
                                    "talla_polines": d.get("talla_polines"), 
                                    "color_polines": d.get("color_polines"), 
                                    "es_arquero": d.get("es_arquero"), 
                                    "genero": d.get("genero"), 
                                    "observacion_individual": d.get("observacion_individual"),
                                    # --- CORRECCIÓN: Agregamos los campos que faltaban ---
                                    "tipo_cuello_texto": d.get("tipo_cuello_texto"),
                                    "ancho_cm": d.get("ancho_cm"),
                                    "alto_cm": d.get("alto_cm"),
                                    "calandra_si_no": d.get("calandra_si_no"),
                                    "acabado": d.get("acabado")
                                }
                                batch_especs.append(esp)
                        
                        # Insertamos todas las filas generadas de golpe (Bulk Insert)
                        if batch_especs:
                            supabase.table('especificaciones_producto').insert(batch_especs).execute()

                    # 5. Éxito y Salida
                    st.success(f"✅ Orden {cod} Guardada correctamente.")
                    st.info("💡 Para imprimir el contrato, vaya al módulo de 'Reportes'.")
                    
                    time.sleep(1.5)
                    st.session_state['vista_prod'] = "LISTA"
                    # ---> NUEVO: LIMPIAR MEMORIA DEL MÓDULO DE REPORTES <---
                    st.session_state.pop('lista_ordenes', None)
                    st.session_state.pop('orden_actual', None)
                    st.rerun()
                    
                except Exception as e: 
                    st.error(f"Error crítico al guardar: {e}")
