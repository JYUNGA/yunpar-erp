import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import PyPDF2
import time

LOCAL_TZ = pytz.timezone('America/Guayaquil')

# ==========================================
# UTILIDADES Y LECTORES
# ==========================================
def obtener_fecha_actual():
    return datetime.now(LOCAL_TZ).date()

def generar_codigo_vd(supabase):
    try:
        res = supabase.table('ordenes').select('codigo_orden').ilike('codigo_orden', 'VD-%').order('codigo_orden', desc=True).limit(1).execute()
        if res.data:
            numero = int(res.data[0]['codigo_orden'].split('-')[1])
            return f"VD-{numero + 1:04d}"
        return "VD-0001"
    except Exception as e:
        return f"VD-{int(datetime.now().timestamp())}"

def extraer_metadata_pdf(uploaded_file):
    """Extrae nombre y suma las dimensiones de TODAS las páginas de un PDF en metros"""
    try:
        reader = PyPDF2.PdfReader(uploaded_file)
        alto_total_m = 0.0
        ancho_m = 0.0
        for page in reader.pages:
            box = page.mediabox
            if ancho_m == 0.0:
                ancho_m = float(box.width) * 0.352778 / 1000
            alto_total_m += float(box.height) * 0.352778 / 1000
        return uploaded_file.name, round(ancho_m, 2), round(alto_total_m, 2)
    except Exception as e:
        return uploaded_file.name, 0.0, 0.0

# ==========================================
# FUNCIÓN PRINCIPAL RENDER
# ==========================================
def render(supabase):
    if 'rol' not in st.session_state or st.session_state['rol'] not in ["GERENTE", "VENDEDORA"]:
        st.error("🔒 Acceso denegado.")
        st.stop()

    # Inicialización de variables en memoria
    if 'carrito_vd' not in st.session_state: 
        st.session_state['carrito_vd'] = []
    if 'temp_archivos_impresion' not in st.session_state:
        st.session_state['temp_archivos_impresion'] = []
    if 'last_prod_sel' not in st.session_state:
        st.session_state['last_prod_sel'] = None
    if 'vd_cliente_id' not in st.session_state: 
        st.session_state['vd_cliente_id'] = None
    if 'uploader_key_vd' not in st.session_state:
        st.session_state['uploader_key_vd'] = str(datetime.now().timestamp())

    st.title("🛍️ Ventas")
    
    tab1, tab2 = st.tabs(["🛒 Nueva Venta", "🧾 Historial de Ventas del Día"])

    # ==============================================================================
    # TAB 1: NUEVA VENTA Y CARRITO
    # ==============================================================================
    with tab1:
        col_busqueda, col_resumen = st.columns([1.5, 1])

        with col_busqueda:
            st.subheader("1. Selección de Cliente")
            
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                clis = supabase.table('clientes').select("id, nombre_completo, cedula_ruc").execute().data
                mapa_cli = {f"{c['nombre_completo']} | {c['cedula_ruc']}": c['id'] for c in clis}
                
                idx_sel = 0
                if st.session_state.get('vd_cliente_id'):
                    found = next((k for k, v in mapa_cli.items() if v == st.session_state['vd_cliente_id']), None)
                    if found in list(mapa_cli.keys()): 
                        idx_sel = list(mapa_cli.keys()).index(found) + 1 

                sel_cli = c1.selectbox("Cliente", ["Consumidor Final"] + list(mapa_cli.keys()), index=idx_sel, label_visibility="collapsed")
                
                if sel_cli != "Consumidor Final" and sel_cli:
                    st.session_state['vd_cliente_id'] = mapa_cli[sel_cli]
                    cliente_id = mapa_cli[sel_cli]
                else:
                    st.session_state['vd_cliente_id'] = None
                    cliente_id = None

                with c2.popover("➕ Crear Cliente Nuevo", use_container_width=True):
                    with st.form("vd_nc_full", clear_on_submit=True):
                        st.markdown("##### Nuevo Cliente")
                        f_ruc = st.text_input("RUC/CI *", key="vd_new_cli_ruc")
                        f_nom = st.text_input("Nombre *", key="vd_new_cli_nom")
                        f_tel = st.text_input("Telf", key="vd_new_cli_tel")
                        f_ema = st.text_input("Email", key="vd_new_cli_ema")
                        f_ciu = st.text_input("Ciudad", key="vd_new_cli_ciu")
                        f_tip = st.selectbox("Tipo", ["Cliente Final", "Escuela", "Empresa", "Fiscal"], key="vd_new_cli_tip")
                        f_gen = st.selectbox("Género", ["Masculino", "Femenino", "Otro"], key="vd_new_cli_gen")
                        
                        if st.form_submit_button("Guardar Cliente"):
                            if f_ruc and f_nom:
                                res_c = supabase.table('clientes').insert({
                                    "cedula_ruc": f_ruc, "nombre_completo": f_nom.upper(), "telefono": f_tel,
                                    "email": f_ema, "ciudad": f_ciu, "tipo_institucion": f_tip, "genero": f_gen
                                }).execute()
                                if res_c.data:
                                    st.session_state['vd_cliente_id'] = res_c.data[0]['id']
                                    st.success("Cliente guardado")
                                    time.sleep(0.5)
                                    st.rerun()
                            else: 
                                st.error("RUC y Nombre obligatorios")

            st.write("---")
            st.subheader("2. Agregar Productos")
            
            with st.expander("🔍 Filtros de Búsqueda (Catálogo)", expanded=True):
                prods_raw = supabase.table('productos_catalogo').select("*").eq('activo', True).execute().data
                df_p = pd.DataFrame(prods_raw)
                
                if not df_p.empty:
                    cf1, cf2, cf3 = st.columns(3)
                    tp = cf1.selectbox("Prenda/Tipo", ["Todos"] + sorted(list(df_p['tipo_prenda'].dropna().unique())))
                    
                    df_filtrado_cat = df_p if tp == "Todos" else df_p[df_p['tipo_prenda'] == tp]
                    cat = cf2.selectbox("Categoría", ["Todos"] + sorted(list(df_filtrado_cat['linea_categoria'].dropna().unique())))
                    eda = cf3.selectbox("Edad", ["Todos"] + sorted(list(df_p['grupo_edad'].dropna().unique())))
                    
                    txt_p = st.text_input("Buscar texto...", placeholder="Cód o Nombre de producto")

                    df_fin = df_p.copy()
                    if tp != "Todos": df_fin = df_fin[df_fin['tipo_prenda'] == tp]
                    if cat != "Todos": df_fin = df_fin[df_fin['linea_categoria'] == cat]
                    if eda != "Todos": df_fin = df_fin[df_fin['grupo_edad'] == eda]
                    if txt_p: df_fin = df_fin[df_fin['descripcion'].str.contains(txt_p, case=False) | df_fin['codigo_referencia'].str.contains(txt_p, case=False)]

                    mapa_p = {f"{r['codigo_referencia']} | {r['descripcion']}": r for r in df_fin.to_dict('records')}
                    sel_p_key = st.selectbox("Seleccione el producto:", list(mapa_p.keys()))
                    prod_obj = mapa_p.get(sel_p_key, None)
                else:
                    st.warning("Catálogo vacío.")
                    prod_obj = None

            # --- LÓGICA DE TARIFAS E IMPRESIÓN ---
            if prod_obj:
                if st.session_state['last_prod_sel'] != prod_obj['id']:
                    st.session_state['last_prod_sel'] = prod_obj['id']
                    st.session_state['temp_archivos_impresion'] = []

                c1, c2 = st.columns(2)
                tarifa_sel = c1.selectbox("Tarifa", ["Unitario", "Docena", "Mayorista", "Manual"])
                
                precio_base = float(prod_obj.get('precio_unitario', 0))
                if tarifa_sel == "Docena": precio_base = float(prod_obj.get('precio_docena', 0))
                elif tarifa_sel == "Mayorista": precio_base = float(prod_obj.get('precio_mayorista', 0))
                
                precio_final = c2.number_input("Precio Final ($)", value=precio_base, format="%.2f", disabled=(tarifa_sel != "Manual"))

                cat_upper = str(prod_obj.get('linea_categoria','')).upper()
                tipo_upper = str(prod_obj.get('tipo_prenda','')).upper()
                es_impresion = ("IMPRESI" in cat_upper) or ("IMPRESI" in tipo_upper) or (tipo_upper in ["ICT", "ICD"])
                
                archivos_metadata = []
                edited_archivos = pd.DataFrame()

                if es_impresion:
                    st.info("🖨️ **Servicio de Impresión.** Configura los archivos para calcular el cobro.")
                    
                    try:
                        res_telas_bd = supabase.table("insumos").select("nombre").execute()
                        lista_telas_db = [t['nombre'] for t in res_telas_bd.data] if res_telas_bd.data else ["Estándar"]
                    except:
                        lista_telas_db = ["Estándar"]
                    lista_perfiles = ["Plotter 1", "Plotter 2", "DTF"]

                    # 1. Subida Automática
                    st.markdown("**1. Subir PDFs, Excel o CSV en lote**")
                    st.info("💡 **Tip:** Límite 200MB. Para archivos más pesados, usa el script local y sube aquí solo el archivo Excel/CSV.")
                    
                    archivos = st.file_uploader("Arrastra aquí los archivos:", type=["pdf", "xlsx", "csv"], accept_multiple_files=True, key=st.session_state['uploader_key_vd'])
                    
                    if st.button("📥 Procesar Archivos Subidos", use_container_width=True):
                        if archivos:
                            peso_total_mb = sum([f.size for f in archivos]) / (1024 * 1024)
                            
                            if peso_total_mb > 200.0:
                                st.error(f"🛑 **¡ALERTA DE SOBRECARGA!** Peso total: {peso_total_mb:.1f} MB. Máximo permitido: 200 MB.")
                            else:
                                for archivo in archivos:
                                    nombre_archivo = archivo.name.lower()
                                    if nombre_archivo.endswith('.pdf'):
                                        nom, anc, lar = extraer_metadata_pdf(archivo)
                                        st.session_state['temp_archivos_impresion'].append({
                                            "Nombre": nom, "Perfil": "Plotter 1", "Tela": lista_telas_db[0],
                                            "Ancho (m)": anc, "Largo (m)": lar, "Cantidad": 1, "Notas": ""
                                        })
                                    elif nombre_archivo.endswith('.csv') or nombre_archivo.endswith('.xlsx'):
                                        try:
                                            df_local = pd.read_csv(archivo) if nombre_archivo.endswith('.csv') else pd.read_excel(archivo)
                                            for _, row in df_local.iterrows():
                                                st.session_state['temp_archivos_impresion'].append({
                                                    "Nombre": str(row.get('Nombre', 'Desconocido')),
                                                    "Perfil": "Plotter 1", "Tela": lista_telas_db[0],
                                                    "Ancho (m)": float(row.get('Ancho en metros', 0.0)),
                                                    "Largo (m)": float(row.get('Largo en metros', 0.0)),
                                                    "Cantidad": 1, "Notas": "Vía Excel/CSV"
                                                })
                                        except Exception as e:
                                            st.warning(f"Error leyendo Excel: {e}")
                                
                                st.session_state['uploader_key_vd'] = str(datetime.now().timestamp())
                                st.rerun()
                        else:
                            st.warning("⚠️ No has seleccionado ningún archivo para procesar.")

                    # 2. Carga Manual
                    with st.expander("➕ 2. Cargar datos de archivo manualmente"):
                        with st.form("form_manual_ventas", clear_on_submit=True):
                            col_m1, col_m2, col_m_tela = st.columns(3)
                            col_m3, col_m4, col_m5 = st.columns([1, 1, 1]) 
                            
                            n_in = col_m1.text_input("Nombre del Archivo")
                            p_in = col_m2.selectbox("Perfil", lista_perfiles)
                            t_in = col_m_tela.selectbox("Tela a Usar", lista_telas_db)
                            
                            a_in = col_m3.number_input("Ancho (m)", min_value=0.0, step=0.01)
                            l_in = col_m4.number_input("Largo (m)", min_value=0.0, step=0.01)
                            c_in = col_m5.number_input("Cant", min_value=1, step=1, value=1)
                            no_in = st.text_input("Notas")
                            
                            if st.form_submit_button("Guardar Manualmente"):
                                if n_in and l_in > 0:
                                    st.session_state['temp_archivos_impresion'].append({
                                        "Nombre": n_in.strip(), "Perfil": p_in, "Tela": t_in,
                                        "Ancho (m)": a_in, "Largo (m)": l_in, "Cantidad": c_in, "Notas": no_in.strip()
                                    })
                                    st.rerun()
                                else:
                                    st.warning("Nombre y Largo requeridos.")

                    # 3. Editor Visual Dinámico
                    st.markdown("**3. Revisa y edita los archivos:**")
                    df_archivos_vd = pd.DataFrame(st.session_state['temp_archivos_impresion'])
                    
                    if not df_archivos_vd.empty:
                        df_archivos_vd['Eliminar'] = False 
                        
                        edited_archivos = st.data_editor(
                            df_archivos_vd,
                            column_config={
                                "Nombre": "Nombre",
                                "Perfil": st.column_config.SelectboxColumn("Perfil", options=lista_perfiles),
                                "Tela": st.column_config.SelectboxColumn("Tela", options=lista_telas_db),
                                "Ancho (m)": st.column_config.NumberColumn("Ancho (m)", format="%.2f"),
                                "Largo (m)": st.column_config.NumberColumn("Largo (m)", format="%.2f"),
                                "Cantidad": st.column_config.NumberColumn("Cant.", min_value=1, step=1),
                                "Notas": "Notas",
                                "Eliminar": st.column_config.CheckboxColumn("🗑️ Eliminar", default=False)
                            },
                            use_container_width=True, hide_index=True, key=f"editor_vd_{prod_obj['id']}"
                        )
                        
                        if st.button("🔄 Borrar Seleccionados y Actualizar", use_container_width=True):
                            df_kept = edited_archivos[~edited_archivos['Eliminar']].copy().drop(columns=['Eliminar'])
                            st.session_state['temp_archivos_impresion'] = df_kept.to_dict('records')
                            st.rerun()
                            
                        largo_total_calculado = (edited_archivos['Largo (m)'] * edited_archivos['Cantidad']).sum()
                    else:
                        st.info("No hay archivos en la lista.")
                        largo_total_calculado = 0.0

                    cantidad_cobro = st.number_input("Total Metros a Cobrar", value=float(largo_total_calculado), min_value=0.0, step=0.1)
                else:
                    cantidad_cobro = st.number_input("Cantidad", min_value=1.0, value=1.0, step=1.0)

                st.write("")
                if st.button("➕ Agregar al Carrito", type="primary"):
                    if es_impresion and not edited_archivos.empty:
                        df_final = edited_archivos[~edited_archivos['Eliminar']] if 'Eliminar' in edited_archivos.columns else edited_archivos
                        for _, r in df_final.iterrows():
                            archivos_metadata.append({
                                "nombre": r["Nombre"], "perfil": r["Perfil"], "tela": r["Tela"],
                                "ancho": r["Ancho (m)"], "largo": r["Largo (m)"], "cantidad": r["Cantidad"], "notas": r["Notas"]
                            })

                    st.session_state['carrito_vd'].append({
                        "id_prod": prod_obj['id'], "descripcion": prod_obj['descripcion'],
                        "precio": precio_final, "cantidad": cantidad_cobro, "es_impresion": es_impresion,
                        "archivos": archivos_metadata, "subtotal": cantidad_cobro * precio_final
                    })
                    st.session_state['temp_archivos_impresion'] = []
                    st.rerun()

        # ==============================
        # COLUMNA DERECHA: CARRITO Y COBRO
        # ==============================
        with col_resumen:
            st.subheader("🛒 Resumen de Venta")
            
            if not st.session_state['carrito_vd']:
                st.info("El carrito está vacío.")
            else:
                total_venta = 0.0
                for i, item in enumerate(st.session_state['carrito_vd']):
                    total_venta += item['subtotal']
                    unidad = "m" if item['es_impresion'] else "u"
                    
                    col_det, col_btn = st.columns([5, 1])
                    col_det.markdown(f"**{item['descripcion']}**\n{item['cantidad']} {unidad} x ${item['precio']:.2f} = **${item['subtotal']:.2f}**")
                    if col_btn.button("❌", key=f"del_{i}"):
                        st.session_state['carrito_vd'].pop(i)
                        st.rerun()
                    
                    if item['archivos']:
                        st.caption(f"📎 {len(item['archivos'])} archivos listos para plotter.")
                    st.divider()

                st.metric("Total a Pagar", f"${total_venta:.2f}")

                with st.container(border=True):
                    st.markdown("💰 **Finanzas**")
                    tipo_flujo = st.radio("Destino de la Orden", ["Entrega Inmediata", "Pasa a Cola de Producción/Impresión"])
                    
                    # --- NUEVO: Selector de Modalidad de Pago ---
                    modalidad_pago = st.radio("Modalidad de Pago Inicial", ["Pago Total (100%)", "Abono Parcial", "Crédito / Sin Abono ($0)"], horizontal=True)
                    
                    if modalidad_pago == "Pago Total (100%)":
                        abono = st.number_input("Monto Recibido ($)", value=float(total_venta), disabled=True)
                    elif modalidad_pago == "Crédito / Sin Abono ($0)":
                        abono = st.number_input("Monto Recibido ($)", value=0.0, disabled=True)
                    else:
                        abono = st.number_input("Monto Recibido ($)", value=0.0, min_value=0.0, max_value=float(total_venta), step=1.0)
                    
                    col_metodo, col_banco = st.columns(2)
                    metodo_pago = col_metodo.selectbox("Método de Pago", ["Efectivo", "Transferencia", "Tarjeta", "Otro"])
                    
                    banco = None
                    if metodo_pago != "Efectivo":
                        banco = col_banco.selectbox("Banco Destino", ["Seleccionar...", "JEP", "Pichincha", "Pacifico", "Austro"])

                    if st.button("✅ Procesar Venta", use_container_width=True, type="primary"):
                        # Validamos el banco solo si realmente está ingresando dinero
                        if abono > 0 and metodo_pago != "Efectivo" and banco == "Seleccionar...":
                            st.error("⚠️ Debes seleccionar a qué banco ingresó el dinero.")
                            st.stop()
                            
                        codigo_vd = generar_codigo_vd(supabase)
                        # --- CAMBIO: El estado ahora es "Listo para Impresión" para que el plotter lo vea ---
                        estado_orden = "Entregado" if tipo_flujo == "Entrega Inmediata" else "Listo para Impresión"
                        
                        try:
                            with st.spinner("Registrando venta y enviando archivos..."):
                                data_orden = {
                                    "codigo_orden": codigo_vd,
                                    "cliente_id": cliente_id,
                                    "total_estimado": total_venta,
                                    "abono_inicial": abono,
                                    "saldo_pendiente": total_venta - abono,
                                    "estado": estado_orden,
                                    "fecha_entrega": obtener_fecha_actual().isoformat(),
                                    "creado_por_id": st.session_state.get('id_usuario', None)
                                }
                                res_orden = supabase.table('ordenes').insert(data_orden).execute()
                                id_orden = res_orden.data[0]['id']

                                for item in st.session_state['carrito_vd']:
                                    supabase.table('detalles_orden').insert({
                                        "orden_id": str(id_orden),
                                        "producto_id": item['id_prod'],
                                        "precio_aplicado": item['precio'],
                                        "cantidad": int(item['cantidad']) if not item['es_impresion'] else 1 
                                    }).execute()
                                    
                                    if item['es_impresion'] and item['archivos']:
                                        payloads_plotter = []
                                        for arch in item['archivos']:
                                            payloads_plotter.append({
                                                "orden_id": id_orden,
                                                "nombre_archivo": arch['nombre'],
                                                "ancho_metros": arch['ancho'],
                                                "longitud_metros": arch['largo'],
                                                "estado_impresion": "Pendiente",
                                                "cantidad": arch.get('cantidad', 1),
                                                "perfil_color": arch.get('perfil', 'Plotter 1'),
                                                "tela": arch.get('tela', 'Estándar'),
                                                "notas_disenador": arch.get('notas', '')
                                            })
                                        supabase.table('archivos_impresion').insert(payloads_plotter).execute()

                                if abono > 0:
                                    supabase.table('pagos').insert({
                                        "orden_id": id_orden,
                                        "cliente_id": cliente_id,
                                        "monto": abono,
                                        "metodo_pago": metodo_pago,
                                        "banco_destino": banco,
                                        "fecha_pago": obtener_fecha_actual().isoformat()
                                    }).execute()

                            st.session_state['carrito_vd'] = []
                            st.success(f"🎉 Venta registrada. Código: **{codigo_vd}**")
                            st.balloons()
                            time.sleep(1.5)
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"❌ Error al procesar: {e}")

    # ==============================================================================
    # TAB 2: HISTORIAL
    # ==============================================================================
    with tab2:
        st.subheader(f"Ventas Rápidas del Día")
        try:
            res_hist = supabase.table('ordenes').select('codigo_orden, total_estimado, abono_inicial, saldo_pendiente, estado').ilike('codigo_orden', 'VD-%').execute()
            df_historial = pd.DataFrame(res_hist.data)
            
            if not df_historial.empty:
                for col in ['total_estimado', 'abono_inicial', 'saldo_pendiente']:
                    df_historial[col] = df_historial[col].apply(lambda x: f"${x:,.2f}")
                st.dataframe(df_historial, use_container_width=True, hide_index=True)
            else:
                st.info("No hay ventas directas hoy.")
        except Exception as e:
            st.error(f"Error al cargar historial: {e}")
