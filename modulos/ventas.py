import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import PyPDF2
import time
import os
import qrcode
import tempfile
from fpdf import FPDF
from num2words import num2words

# Solo importamos el extractor de datos, el PDF lo generaremos nosotros mismos aquí
from modulos.reportes import obtener_datos_orden

LOCAL_TZ = pytz.timezone('America/Guayaquil')

# ==========================================
# MOTORES DE PDF Y UTILIDADES
# ==========================================
class PDFVenta(FPDF):
    def __init__(self, datos_cabecera=None, ruta_fondo="PROFORMA.png"):
        super().__init__()
        self.datos_cabecera = datos_cabecera 
        self.ruta_fondo = ruta_fondo

    def header(self):
        # 1. FONDO (Carga directa, sin procesamientos lentos)
        if self.ruta_fondo and os.path.exists(self.ruta_fondo):
            self.image(self.ruta_fondo, x=0, y=0, w=210, h=297)
        
        # 2. LLENADO DE DATOS
        if self.datos_cabecera:
            self.set_font('Arial', 'B', 10)
            self.set_text_color(60, 60, 60)
            
            self.set_xy(68, 78) 
            self.cell(40, 5, self.datos_cabecera.get('codigo', ''), 0, 0, 'L')
            
            self.set_xy(80, 86)
            self.cell(90, 5, limpiar_texto_pdf(self.datos_cabecera.get('cliente_nombre', '')), 0, 0, 'L')
            
            self.set_xy(78, 92)
            self.cell(40, 5, self.datos_cabecera.get('fecha', ''), 0, 0, 'L')
            
            self.set_xy(161, 85)
            self.cell(50, 5, self.datos_cabecera.get('telefono', ''), 0, 0, 'L')
            
            self.set_xy(160, 93) 
            self.set_font('Arial', '', 9)
            tipo = self.datos_cabecera.get('tipo', '')
            self.cell(38, 5, limpiar_texto_pdf(tipo[:18]), 0, 0, 'C')

        self.set_y(105) 
        self.set_left_margin(52) 
        self.set_right_margin(10)

    def footer(self):
        self.set_y(-10)
        self.set_text_color(255, 255, 255)
        self.set_font('Arial', '', 7)
        self.cell(0, 10, f'Pag {self.page_no()}', 0, 0, 'R')

def limpiar_texto_pdf(texto):
    if not texto: return ""
    reemplazos = {"│": "|", "–": "-", "“": '"', "”": '"', "’": "'", "‘": "'", "Ñ": "N", "ñ": "n", "°": " degrees", "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u"}
    t = str(texto)
    for k, v in reemplazos.items(): t = t.replace(k, v)
    return t.encode('latin-1', 'replace').decode('latin-1')

def generar_pdf_venta(datos_venta):
    cli = datos_venta.get('clientes', {})
    cabecera = {
        "codigo": datos_venta.get('codigo_orden', ''),
        "cliente_nombre": cli.get('nombre_completo', cli.get('nombre', 'Consumidor Final')),
        "telefono": cli.get('telefono', cli.get('celular', 'No registrado')),
        "fecha": str(datos_venta.get('created_at', ''))[:10],
        "tipo": cli.get('tipo_institucion', '')
    }
    
    pdf = PDFVenta(datos_cabecera=cabecera)
    pdf.add_page()
    
    pdf.set_fill_color(245, 166, 35) 
    pdf.set_text_color(255, 255, 255) 
    pdf.set_font("Arial", 'B', 9)
    
    w_cod, w_desc, w_cant, w_unit, w_tot = 18, 65, 15, 18, 20
    
    pdf.cell(w_cod, 8, "Codigo", 1, 0, 'C', True)
    pdf.cell(w_desc, 8, "Descripcion", 1, 0, 'C', True)
    pdf.cell(w_cant, 8, "Cant", 1, 0, 'C', True)
    pdf.cell(w_unit, 8, "P.Unit", 1, 0, 'C', True)
    pdf.cell(w_tot, 8, "Total", 1, 1, 'C', True)
    pdf.ln(8)
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 9)
    
    total = float(datos_venta.get('total_estimado', 0))
    abono = float(datos_venta.get('abono_inicial', 0))
    saldo = float(datos_venta.get('saldo_pendiente', 0))
    
    qr_data_string = f"VD: {cabecera['codigo']}\nCLIENTE: {cabecera['cliente_nombre']}\nTOTAL: ${total:.2f}\n"
    
    for item in datos_venta.get('items', []):
        x_start, y_start = pdf.get_x(), pdf.get_y()
        desc = limpiar_texto_pdf(item.get('nombre_producto', 'Producto Genérico'))
        
        pdf.set_xy(x_start + w_cod, y_start)
        pdf.multi_cell(w_desc, 6, desc, 0, 'L')
        row_height = max(8, pdf.get_y() - y_start)
        
        pdf.set_xy(x_start, y_start)
        pdf.cell(w_cod, row_height, "VD-ITM", 0, 0, 'C')
        
        cx, cy = pdf.get_x(), pdf.get_y()
        pdf.multi_cell(w_desc, 6, desc, 0, 'L')
        pdf.set_xy(cx + w_desc, cy)
        
        cant = float(item.get('cantidad_total', 1))
        c_txt = f"{int(cant)}" if cant.is_integer() else f"{cant:.2f}"
        precio = float(item.get('precio_aplicado', 0))
        subt = cant * precio
        
        pdf.cell(w_cant, row_height, c_txt, 0, 0, 'C')
        pdf.cell(w_unit, row_height, f"${precio:.2f}", 0, 0, 'R')
        pdf.cell(w_tot, row_height, f"${subt:.2f}", 0, 1, 'R')
        
        pdf.set_draw_color(220, 220, 220)
        pdf.line(52, pdf.get_y(), 52 + w_cod + w_desc + w_cant + w_unit + w_tot, pdf.get_y())
        pdf.set_draw_color(0,0,0)
        qr_data_string += f"- {desc} ({c_txt})\n"

    pdf.ln(5)
    y = pdf.get_y()
    if y > 220: 
        pdf.add_page()
        y = pdf.get_y()

    pdf.set_xy(52, y)
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(10, 5, "SON:", 0, 0)
    pdf.set_font("Arial", 'I', 8)
    
    try: total_letras = num2words(total, lang='es').upper() + " DÓLARES"
    except: total_letras = f"{total} DÓLARES"
        
    pdf.multi_cell(110, 5, limpiar_texto_pdf(total_letras), 0)
    
    x_totales = 140
    pdf.set_xy(x_totales, y) 
    pdf.set_font("Arial", '', 10)
    subt_calc = total / 1.15
    iva_calc = total - subt_calc
    pdf.cell(20, 5, "Subtotal:", 0, 0, 'R'); pdf.cell(25, 5, f"${subt_calc:.2f}", 0, 1, 'R')
    pdf.set_x(x_totales)
    pdf.cell(20, 5, "IVA (15%):", 0, 0, 'R'); pdf.cell(25, 5, f"${iva_calc:.2f}", 0, 1, 'R')
    pdf.set_x(x_totales)
    pdf.set_font("Arial", 'B', 11)
    pdf.set_text_color(18, 38, 122)
    pdf.cell(20, 6, "TOTAL:", 0, 0, 'R'); pdf.cell(25, 6, f"${total:.2f}", 0, 1, 'R')
    
    pdf.set_x(x_totales)
    pdf.set_font("Arial", '', 10)
    pdf.set_text_color(0, 100, 0)
    pdf.cell(20, 5, "Abono:", 0, 0, 'R'); pdf.cell(25, 5, f"${abono:.2f}", 0, 1, 'R')
    pdf.set_x(x_totales)
    pdf.set_text_color(200, 0, 0)
    pdf.cell(20, 5, "Saldo:", 0, 0, 'R'); pdf.cell(25, 5, f"${saldo:.2f}", 0, 1, 'R')
    
    pdf.set_text_color(0,0,0)
    pdf.ln(5)
    
    qr = qrcode.QRCode(version=1, box_size=5, border=1)
    try: qr.add_data(qr_data_string.encode('utf-8').decode('latin-1'))
    except: qr.add_data("Datos Venta")
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white")
    temp_qr_path = tempfile.mktemp(suffix='.png')
    img_qr.save(temp_qr_path)
    pdf.image(temp_qr_path, x=52, y=pdf.get_y() + 2, w=25)
    
    pdf.set_xy(75, pdf.get_y() + 7); pdf.set_font("Arial", '', 7); pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(65, 4, "Escanea para verificar\ndetalles de la compra.", 0, 'L')
    pdf.set_text_color(0, 0, 0)

    pos_firma = 263
    if pdf.get_y() > 245: pdf.add_page(); pdf.set_y(pos_firma)
    pdf.set_y(pos_firma); pdf.set_font('Arial', '', 8)
    pdf.set_xy(55, pos_firma); pdf.cell(50, 0, '_______________________', 0, 1, 'C')
    pdf.set_xy(55, pos_firma); pdf.cell(50, 5, 'Dpto. Ventas / Caja', 0, 0, 'C')
    pdf.set_xy(120, pos_firma); pdf.cell(50, 0, '_______________________', 0, 1, 'C')
    pdf.set_xy(120, pos_firma); pdf.cell(50, 5, 'Cliente Conforme', 0, 1, 'C')
    pdf.set_xy(120, pos_firma + 4); pdf.set_font('Arial', 'B', 7)
    pdf.cell(50, 5, limpiar_texto_pdf(cabecera['cliente_nombre'][:30]), 0, 1, 'C')
    
    return bytes(pdf.output())

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
            # --- NUEVO: Fila superior con Fecha de Venta y Fecha de Entrega ---
            col_fec1, col_fec2 = st.columns(2)
            fecha_venta_seleccionada = col_fec1.date_input("🗓️ Fecha de Registro (Venta y Pago)", value=obtener_fecha_actual())
            fecha_entrega_seleccionada = col_fec2.date_input("📅 Fecha de Entrega Estimada", value=obtener_fecha_actual())

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
                # 1. Traemos TODOS los productos activos (Evitamos que la API ignore filtros)
                prods_raw = supabase.table('productos_catalogo').select("*").eq('activo', True).execute().data
                df_p = pd.DataFrame(prods_raw)
                
                # 2. PURIFICACIÓN PANDAS EXTREMA
                if not df_p.empty and 'grupo_edad' in df_p.columns:
                    # Convertimos a texto, borramos espacios fantasma y forzamos mayúsculas
                    df_p['grupo_edad'] = df_p['grupo_edad'].fillna('').astype(str).str.strip().str.upper()
                    # Dejamos pasar ÚNICAMENTE las filas que digan exactamente 'VENTA'
                    df_p = df_p[df_p['grupo_edad'] == 'VENTA']
                
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
                                    # --- CAMBIO: Usar las fechas de los calendarios ---
                                    "fecha_entrega": fecha_entrega_seleccionada.isoformat(),
                                    "created_at": f"{fecha_venta_seleccionada.isoformat()}T12:00:00",
                                    "creado_por_id": st.session_state.get('id_usuario', None)
                                }
                                res_orden = supabase.table('ordenes').insert(data_orden).execute()
                                id_orden = res_orden.data[0]['id']

                                for item in st.session_state['carrito_vd']:
                                    # CORRECCIÓN: Guardamos directamente en 'items_orden' para unificar con Producción
                                    supabase.table('items_orden').insert({
                                        "orden_id": id_orden,
                                        "producto_id": item['id_prod'],
                                        "precio_aplicado": item['precio'],
                                        "cantidad_total": item['cantidad'], # Guardamos la cantidad cobrable real
                                        "familia_producto": "IMPRESION" if item['es_impresion'] else "GENERICO"
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
                                        # --- CAMBIO: Fecha de pago igual a la fecha de registro ---
                                        "fecha_pago": fecha_venta_seleccionada.isoformat()
                                    }).execute()

                            st.session_state['carrito_vd'] = []
                            st.success(f"🎉 Venta registrada. Código: **{codigo_vd}**")
                            st.balloons()
                            time.sleep(1.5)
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"❌ Error al procesar: {e}")

    # ==============================================================================
    # TAB 2: HISTORIAL Y AUDITORÍA DE VENTAS
    # ==============================================================================
    with tab2:
        st.subheader("🧾 Historial de Ventas (Auditoría)")
        
        # 1. Filtros de Gerencia
        col_f1, col_f2, col_bus = st.columns([1, 1, 2])
        f_desde = col_f1.date_input("Desde", value=obtener_fecha_actual(), key="vd_f_des")
        f_hasta = col_f2.date_input("Hasta", value=obtener_fecha_actual(), key="vd_f_has")
        txt_bus = col_bus.text_input("🔍 Buscar Venta", placeholder="Código VD o Nombre...")

        try:
            # Consultamos las ventas (VD-%) filtrando por fechas
            query = supabase.table('ordenes').select('id, codigo_orden, total_estimado, abono_inicial, saldo_pendiente, estado, clientes(nombre_completo)').ilike('codigo_orden', 'VD-%')
            query = query.gte('created_at', f"{f_desde}T00:00:00").lte('created_at', f"{f_hasta}T23:59:59")
            
            res_hist = query.order('created_at', desc=True).execute()

            if res_hist.data:
                lista_ventas = []
                for d in res_hist.data:
                    nom_cli = d.get('clientes', {}).get('nombre_completo') if d.get('clientes') else "Consumidor Final"
                    
                    # Filtro de texto por código o cliente
                    if txt_bus and txt_bus.lower() not in d['codigo_orden'].lower() and txt_bus.lower() not in nom_cli.lower():
                        continue

                    lista_ventas.append({
                        "Código": d['codigo_orden'],
                        "Cliente": nom_cli,
                        "Estado": d['estado'],
                        "Total": f"${float(d['total_estimado']):.2f}",
                        "Abono": f"${float(d['abono_inicial']):.2f}",
                        "Saldo": f"${float(d['saldo_pendiente']):.2f}"
                    })

                if lista_ventas:
                    df_historial = pd.DataFrame(lista_ventas)
                    # La tabla ahora es clickeable
                    evt_vd = st.dataframe(df_historial, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")

                    # 2. Desglose y Auditoría de la Venta Seleccionada
                    if len(evt_vd.selection.rows) > 0:
                        cod_sel = df_historial.iloc[evt_vd.selection.rows[0]]["Código"]
                        st.divider()
                        st.markdown(f"### 🔎 Detalle de Venta: {cod_sel}")

                        with st.spinner("Cargando detalles de la caja..."):
                            # Reutilizamos la función de reportes.py
                            datos_venta = obtener_datos_orden(supabase, cod_sel)

                        if datos_venta:
                            c_info, c_btn = st.columns([2, 1])

                            with c_info:
                                st.write("**📦 Productos Entregados/Cobrados:**")
                                for it in datos_venta.get('items', []):
                                    precio = float(it.get('precio_aplicado', 0))
                                    cant = float(it.get('cantidad_total', 1))
                                    # Si es entero, lo mostramos sin decimales (ej: 2). Si es metro, con decimales (ej: 1.5)
                                    cant_str = int(cant) if cant.is_integer() else f"{cant:.2f}m"
                                    st.caption(f"- {cant_str}x {it.get('nombre_producto', 'Producto')} | Subtotal: ${cant*precio:.2f}")

                                st.write("**💳 Trazabilidad del Pago:**")
                                pagos = datos_venta.get('pagos', [])
                                if pagos:
                                    for p in pagos:
                                        banco = p.get('banco_destino') or p.get('metodo_pago') or 'Efectivo'
                                        ref = p.get('numero_referencia') or 'N/A'
                                        st.caption(f"- ${float(p['monto']):.2f} recibidos en {banco} (Ref: {ref})")
                                else:
                                    st.caption("- Venta a Crédito / Sin abono inicial registrado.")

                            with c_btn:
                                st.info("📄 Re-impresión de Recibo")
                                # Generamos el PDF usando el nuevo motor basado en el diseño de cotizaciones
                                pdf_bytes = generar_pdf_venta(datos_venta)
                                st.download_button(
                                    label="⬇️ Descargar Comprobante",
                                    data=pdf_bytes,
                                    file_name=f"Comprobante_{cod_sel}.pdf",
                                    mime="application/pdf",
                                    use_container_width=True,
                                    type="primary"
                                )
                else:
                    st.info("No hay ventas que coincidan con tu búsqueda en este rango de fechas.")
            else:
                st.info("No hay ventas registradas en este rango de fechas.")
        except Exception as e:
            st.error(f"Error al cargar historial: {e}")
