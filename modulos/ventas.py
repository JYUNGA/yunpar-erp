import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import PyPDF2
import io

LOCAL_TZ = pytz.timezone('America/Guayaquil')

# ==========================================
# UTILIDADES Y LECTORES (Adaptados de tu Diseñador)
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

    if 'carrito_vd' not in st.session_state: 
        st.session_state['carrito_vd'] = []

    st.title("🛍️ Ventas Directas y Mostrador")
    
    tab1, tab2 = st.tabs(["🛒 Nueva Venta", "🧾 Historial de Ventas del Día"])

    # ==============================================================================
    # TAB 1: NUEVA VENTA Y CARRITO
    # ==============================================================================
    with tab1:
        col_busqueda, col_resumen = st.columns([1.5, 1])

        with col_busqueda:
            st.subheader("1. Selección de Cliente")
            clis = supabase.table('clientes').select("id, nombre_completo, cedula_ruc").execute().data
            mapa_cli = {f"{c['nombre_completo']} | {c['cedula_ruc']}": c['id'] for c in clis}
            cliente_sel = st.selectbox("Buscar Cliente", ["Consumidor Final"] + list(mapa_cli.keys()))
            cliente_id = mapa_cli.get(cliente_sel, None)

            st.write("---")
            st.subheader("2. Agregar Productos")
            
            # --- MISMO BUSCADOR DE PRODUCCIÓN ---
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
                c1, c2 = st.columns(2)
                tarifa_sel = c1.selectbox("Tarifa", ["Unitario", "Docena", "Mayorista", "Manual"])
                
                precio_base = float(prod_obj.get('precio_unitario', 0))
                if tarifa_sel == "Docena": precio_base = float(prod_obj.get('precio_docena', 0))
                elif tarifa_sel == "Mayorista": precio_base = float(prod_obj.get('precio_mayorista', 0))
                
                precio_final = c2.number_input("Precio Final ($)", value=precio_base, format="%.2f", disabled=(tarifa_sel != "Manual"))

                # Detectar si es de la familia de impresión
                es_impresion = "IMPRESI" in str(prod_obj.get('linea_categoria','')).upper() or "IMPRESI" in str(prod_obj.get('tipo_prenda','')).upper()

                cantidad_cobro = 1.0
                archivos_metadata = []

                if es_impresion:
                    st.info("🖨️ **Servicio de Impresión Detectado.** Sube los archivos para calcular los metros automáticamente.")
                    archivos = st.file_uploader("Subir PDFs o Excel", type=["pdf", "xlsx", "csv"], accept_multiple_files=True)
                    
                    largo_total_calculado = 0.0
                    if archivos:
                        for archivo in archivos:
                            nombre_archivo = archivo.name.lower()
                            if nombre_archivo.endswith('.pdf'):
                                nom, anc, lar = extraer_metadata_pdf(archivo)
                                largo_total_calculado += lar
                                archivos_metadata.append({"nombre": nom, "ancho": anc, "largo": lar})
                            elif nombre_archivo.endswith('.csv') or nombre_archivo.endswith('.xlsx'):
                                try:
                                    df_local = pd.read_csv(archivo) if nombre_archivo.endswith('.csv') else pd.read_excel(archivo)
                                    for _, row in df_local.iterrows():
                                        lar = float(row.get('Largo en metros', 0.0))
                                        anc = float(row.get('Ancho en metros', 0.0))
                                        largo_total_calculado += lar
                                        archivos_metadata.append({"nombre": str(row.get('Nombre', 'Desconocido')), "ancho": anc, "largo": lar})
                                except Exception as e:
                                    st.warning(f"Error leyendo Excel: {e}")
                                    
                    cantidad_cobro = st.number_input("Total Metros (Calculado o Manual)", value=float(largo_total_calculado), min_value=0.01)
                else:
                    cantidad_cobro = st.number_input("Cantidad", min_value=1.0, value=1.0, step=1.0)

                if st.button("➕ Agregar al Carrito", type="primary"):
                    st.session_state['carrito_vd'].append({
                        "id_prod": prod_obj['id'],
                        "descripcion": prod_obj['descripcion'],
                        "precio": precio_final,
                        "cantidad": cantidad_cobro,
                        "es_impresion": es_impresion,
                        "archivos": archivos_metadata,
                        "subtotal": cantidad_cobro * precio_final
                    })
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
                    
                    abono = st.number_input("Monto Recibido ($)", value=total_venta, max_value=total_venta)
                    metodo_pago = st.selectbox("Método de Pago", ["Efectivo", "Transferencia", "Tarjeta", "Otro"])
                    banco = st.text_input("Banco / Ref.") if metodo_pago in ["Transferencia", "Otro"] else None

                    if st.button("✅ Procesar Venta", use_container_width=True, type="primary"):
                        codigo_vd = generar_codigo_vd(supabase)
                        estado_orden = "Entregado" if tipo_flujo == "Entrega Inmediata" else "Pendiente Impresión"
                        
                        try:
                            with st.spinner("Registrando venta y enviando archivos..."):
                                # 1. Cabecera
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

                                # 2. Detalles, Items y Archivos
                                for item in st.session_state['carrito_vd']:
                                    # Lo registramos en detalles_orden
                                    supabase.table('detalles_orden').insert({
                                        "orden_id": str(id_orden),
                                        "producto_id": item['id_prod'],
                                        "precio_aplicado": item['precio'],
                                        "cantidad": int(item['cantidad']) if not item['es_impresion'] else 1 # Adaptación
                                    }).execute()
                                    
                                    # Si es impresión y tiene archivos, a la cola del plotter directamente
                                    if item['es_impresion'] and item['archivos']:
                                        payloads_plotter = []
                                        for arch in item['archivos']:
                                            payloads_plotter.append({
                                                "orden_id": id_orden,
                                                "nombre_archivo": arch['nombre'],
                                                "ancho_metros": arch['ancho'],
                                                "longitud_metros": arch['largo'],
                                                "estado_impresion": "Pendiente",
                                                "cantidad": 1,
                                                "perfil_color": "Plotter 1",
                                                "tela": "Estándar"
                                            })
                                        supabase.table('archivos_impresion').insert(payloads_plotter).execute()

                                # 3. Pagos
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
