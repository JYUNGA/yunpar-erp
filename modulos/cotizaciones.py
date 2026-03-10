import streamlit as st
import pandas as pd
import datetime
import time
import urllib.parse
import os
import qrcode
import tempfile
from fpdf import FPDF
from num2words import num2words

# --- CLASE PDF CON PLANTILLA VISUAL ---
class PDFCotizacion(FPDF):
    def __init__(self, datos_cabecera=None, ruta_fondo=None):
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
            
            # N° Cotización
            self.set_xy(68, 78) 
            self.cell(40, 5, self.datos_cabecera.get('codigo', ''), 0, 0, 'L')
            
            # Cliente
            self.set_xy(80, 86)
            self.cell(90, 5, limpiar_texto_pdf(self.datos_cabecera.get('cliente_nombre', '')), 0, 0, 'L')
            
            # Fecha
            self.set_xy(78, 92)
            self.cell(40, 5, self.datos_cabecera.get('fecha', ''), 0, 0, 'L')
            
            # Contacto/Teléfono
            self.set_xy(161, 85)
            self.cell(50, 5, self.datos_cabecera.get('telefono', ''), 0, 0, 'L')
            
            # Cliente Tipo
            self.set_xy(160, 93) 
            self.set_font('Arial', '', 9)
            tipo = self.datos_cabecera.get('tipo', '')
            self.cell(38, 5, limpiar_texto_pdf(tipo[:18]), 0, 0, 'C')

        # 3. MÁRGENES DE TABLA
        self.set_y(105) 
        self.set_left_margin(52) 
        self.set_right_margin(10)

    def footer(self):
        self.set_y(-10)
        self.set_text_color(255, 255, 255)
        self.set_font('Arial', '', 7)
        self.cell(0, 10, f'Pag {self.page_no()}', 0, 0, 'R')

# --- FUNCIONES AUXILIARES ---
def limpiar_texto_pdf(texto):
    if not texto: return ""
    reemplazos = {"│": "|", "–": "-", "“": '"', "”": '"', "’": "'", "‘": "'", "Ñ": "N", "ñ": "n", "°": " degrees", "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u"}
    t = str(texto)
    for k, v in reemplazos.items(): t = t.replace(k, v)
    return t.encode('latin-1', 'replace').decode('latin-1')

def generar_siguiente_codigo_cot(supabase):
    try:
        resp = supabase.table('cotizaciones').select("codigo_cotizacion").execute()
        codigos = [d['codigo_cotizacion'] for d in resp.data]
        max_num = 0
        for c in codigos:
            if c.startswith("COT-") and c[4:].isdigit():
                num = int(c[4:])
                if num > max_num: max_num = num
        return f"COT-{str(max_num + 1).zfill(4)}"
    except: return "COT-0001"

def generar_pdf_final(cabecera, items, observaciones, vigencia_fecha, total_letras):
    ruta_fondo = "PROFORMA.png"
    pdf = PDFCotizacion(datos_cabecera=cabecera, ruta_fondo=ruta_fondo)
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
    
    qr_data_string = f"COT: {cabecera['codigo']}\nCLIENTE: {cabecera['cliente_nombre']}\nTOTAL: ${cabecera['total']:.2f}\n"
    
    for item in items:
        x_start, y_start = pdf.get_x(), pdf.get_y()
        desc = limpiar_texto_pdf(item['descripcion'])
        pdf.set_xy(x_start + w_cod, y_start)
        pdf.multi_cell(w_desc, 6, desc, 0, 'L')
        row_height = max(8, pdf.get_y() - y_start)
        
        pdf.set_xy(x_start, y_start)
        pdf.cell(w_cod, row_height, limpiar_texto_pdf(str(item['codigo'])), 0, 0, 'C')
        
        cx, cy = pdf.get_x(), pdf.get_y()
        pdf.multi_cell(w_desc, 6, desc, 0, 'L')
        pdf.set_xy(cx + w_desc, cy)
        
        c_txt = f"{int(item['cantidad'])}" if item['cantidad'] % 1 == 0 else f"{item['cantidad']:.2f}"
        pdf.cell(w_cant, row_height, c_txt, 0, 0, 'C')
        pdf.cell(w_unit, row_height, f"${float(item['precio']):.2f}", 0, 0, 'R')
        pdf.cell(w_tot, row_height, f"${float(item['subtotal']):.2f}", 0, 1, 'R')
        
        pdf.set_draw_color(220, 220, 220)
        pdf.line(52, pdf.get_y(), 52 + w_cod + w_desc + w_cant + w_unit + w_tot, pdf.get_y())
        pdf.set_draw_color(0,0,0)
        qr_data_string += f"- {item['codigo']} ({c_txt})\n"

    pdf.ln(5)
    y = pdf.get_y()
    if y > 230: 
        pdf.add_page()
        y = pdf.get_y()

    pdf.set_xy(52, y)
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(10, 5, "SON:", 0, 0)
    pdf.set_font("Arial", 'I', 8)
    pdf.multi_cell(110, 5, limpiar_texto_pdf(total_letras), 0)
    
    x_totales = 140
    pdf.set_xy(x_totales, y) 
    pdf.set_font("Arial", '', 10)
    pdf.cell(20, 5, "Subtotal:", 0, 0, 'R'); pdf.cell(25, 5, f"${float(cabecera['subtotal']):.2f}", 0, 1, 'R')
    pdf.set_x(x_totales)
    pdf.cell(20, 5, "IVA (15%):", 0, 0, 'R'); pdf.cell(25, 5, f"${float(cabecera['iva']):.2f}", 0, 1, 'R')
    pdf.set_x(x_totales)
    pdf.set_font("Arial", 'B', 12)
    pdf.set_text_color(18, 38, 122)
    pdf.cell(20, 8, "TOTAL:", 0, 0, 'R'); pdf.cell(25, 8, f"${float(cabecera['total']):.2f}", 0, 1, 'R')
    pdf.set_text_color(0,0,0)
    pdf.ln(5)
    
    if observaciones:
        pdf.set_x(52); pdf.set_font("Arial", 'B', 9); pdf.cell(0, 6, "OBSERVACIONES / CONDICIONES:", 0, 1)
        pdf.set_x(52); pdf.set_font("Arial", '', 8); pdf.multi_cell(140, 5, limpiar_texto_pdf(observaciones), 1)
        pdf.ln(3)
        
    pdf.set_x(52); pdf.set_font("Arial", 'I', 9); pdf.set_text_color(200, 0, 0)
    pdf.cell(0, 6, f"Oferta valida hasta: {vigencia_fecha}", 0, 1)
    pdf.set_text_color(0, 0, 0)
    
    qr = qrcode.QRCode(version=1, box_size=5, border=1)
    try: qr.add_data(qr_data_string.encode('utf-8').decode('latin-1'))
    except: qr.add_data("Datos Cotizacion")
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white")
    temp_qr_path = tempfile.mktemp(suffix='.png')
    img_qr.save(temp_qr_path)
    pdf.image(temp_qr_path, x=52, y=pdf.get_y() + 2, w=25)
    
    pdf.set_xy(75, pdf.get_y() + 7); pdf.set_font("Arial", '', 7); pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(65, 4, "Escanea para verificar\ndetalles originales.", 0, 'L')
    pdf.set_text_color(0, 0, 0)

    pos_firma = 258
    if pdf.get_y() > 240: pdf.add_page()
    pdf.set_y(pos_firma); pdf.set_font('Arial', '', 8)
    pdf.set_xy(55, pos_firma); pdf.cell(50, 0, '_______________________', 0, 1, 'C')
    pdf.set_xy(55, pos_firma); pdf.cell(50, 5, 'Dpto. Ventas', 0, 0, 'C')
    pdf.set_xy(120, pos_firma); pdf.cell(50, 0, '_______________________', 0, 1, 'C')
    pdf.set_xy(120, pos_firma); pdf.cell(50, 5, 'Cliente Conforme', 0, 1, 'C')
    pdf.set_xy(120, pos_firma + 4); pdf.set_font('Arial', 'B', 7)
    pdf.cell(50, 5, limpiar_texto_pdf(cabecera['cliente_nombre'][:30]), 0, 1, 'C')
    
    # CORRECCIÓN: fpdf moderno ya devuelve un bytearray. 
    # Solo lo casteamos a bytes para compatibilidad estricta con st.download_button
    return bytes(pdf.output())

# --- RENDER PRINCIPAL ---
def render(supabase):
    if 'vista_cot' not in st.session_state: st.session_state['vista_cot'] = "LISTA"
    if 'cot_items' not in st.session_state: st.session_state['cot_items'] = []
    
    if st.session_state['vista_cot'] == "LISTA":
        c_tit, c_btn = st.columns([3, 1])
        c_tit.title("📑 Cotizaciones")
        if c_btn.button("➕ NUEVA COTIZACIÓN", type="primary", use_container_width=True):
            st.session_state['vista_cot'] = "EDITOR"
            st.session_state['modo_edicion_cot'] = False
            st.session_state['cot_items'] = []
            st.session_state['cot_obs_temp'] = ""
            st.session_state['cliente_id_edicion'] = None
            st.rerun()

        with st.container(border=True):
            col_fil1, col_fil2, col_fil3 = st.columns(3)
            h_f_txt = col_fil1.text_input("🔍 Buscar Cliente / Código")
            h_f_ini = col_fil2.date_input("Desde", value=datetime.date.today() - datetime.timedelta(days=30))
            h_f_fin = col_fil3.date_input("Hasta", value=datetime.date.today())

        query = supabase.table('cotizaciones').select("*").order('created_at', desc=True)
        query = query.gte('created_at', str(h_f_ini)).lte('created_at', str(h_f_fin) + " 23:59:59")
        resp_cots = query.execute()
        df_cots = pd.DataFrame(resp_cots.data)

        if not df_cots.empty:
            ids_cli = df_cots['cliente_id'].unique().tolist()
            if ids_cli:
                resp_clis = supabase.table('clientes').select("id, nombre_completo").in_("id", ids_cli).execute()
                mapa_cli = {c['id']: c['nombre_completo'] for c in resp_clis.data}
                df_cots['Cliente'] = df_cots['cliente_id'].map(mapa_cli)
            
            if h_f_txt:
                df_cots = df_cots[df_cots['codigo_cotizacion'].str.contains(h_f_txt, case=False) | df_cots['Cliente'].str.contains(h_f_txt, case=False, na=False)]

            st.dataframe(df_cots[['codigo_cotizacion', 'fecha_emision', 'Cliente', 'total', 'estado']], use_container_width=True, hide_index=True, selection_mode="single-row", on_select="rerun", key="grid_cot_hist")
            
            if st.session_state.grid_cot_hist.selection.rows:
                idx = st.session_state.grid_cot_hist.selection.rows[0]
                row_sel = df_cots.iloc[idx]
                with st.container(border=True):
                    st.markdown(f"#### ⚙️ {row_sel['codigo_cotizacion']} - {row_sel['Cliente']}")
                    b1, b2, b3, b4 = st.columns(4)
                    
                    if b1.button("✏️ EDITAR", use_container_width=True):
                        detalles = supabase.table('detalles_cotizacion').select("*").eq('cotizacion_id', int(row_sel['id'])).execute().data
                        items_load = []
                        for d in detalles:
                            try:
                                prod = supabase.table('productos_catalogo').select("*").eq('id', d['producto_id']).single().execute().data
                                items_load.append({
                                    "id": d['producto_id'], "codigo": prod['codigo_referencia'],
                                    "descripcion": d['descripcion_snapshot'], "cantidad": float(d['cantidad']),
                                    "precio": float(d['precio_unitario']), "subtotal": float(d['subtotal']),
                                    "obj_raw": prod 
                                })
                            except: pass
                        st.session_state['cot_items'] = items_load
                        st.session_state['modo_edicion_cot'] = True
                        st.session_state['id_cot_edicion'] = int(row_sel['id'])
                        st.session_state['cliente_id_edicion'] = int(row_sel['cliente_id']) 
                        st.session_state['codigo_edicion'] = row_sel['codigo_cotizacion']
                        st.session_state['cot_obs_temp'] = row_sel['observaciones']
                        st.session_state['vista_cot'] = "EDITOR"
                        st.rerun()

                    if b2.button("📄 PDF", use_container_width=True):
                        detalles = supabase.table('detalles_cotizacion').select("*").eq('cotizacion_id', int(row_sel['id'])).execute().data
                        items_pdf = []
                        for d in detalles:
                            prod = supabase.table('productos_catalogo').select("codigo_referencia").eq('id', d['producto_id']).single().execute().data
                            items_pdf.append({"codigo": prod['codigo_referencia'], "descripcion": d['descripcion_snapshot'], "cantidad": d['cantidad'], "precio": d['precio_unitario'], "subtotal": d['subtotal']})
                        
                        cli_data = supabase.table('clientes').select("*").eq('id', int(row_sel['cliente_id'])).single().execute().data
                        tl = num2words(row_sel['total'], lang='es').upper() + " DÓLARES"
                        
                        try:
                            f_em = datetime.datetime.strptime(row_sel['fecha_emision'], '%Y-%m-%d').date()
                            days_val = row_sel['validez_dias'] if row_sel['validez_dias'] else 30
                            str_val = str(f_em + datetime.timedelta(days=days_val))
                        except: str_val = str(datetime.date.today() + datetime.timedelta(days=30))

                        pdf_bytes = generar_pdf_final(
                            cabecera={
                                "cliente_nombre": cli_data['nombre_completo'], "cliente_ruc": cli_data['cedula_ruc'], 
                                "telefono": cli_data['telefono'], "fecha": str(row_sel['fecha_emision']), 
                                "codigo": row_sel['codigo_cotizacion'], "subtotal": float(row_sel['total'])/1.15, 
                                "iva": float(row_sel['total']) - (float(row_sel['total'])/1.15), "total": row_sel['total'],
                                "tipo": cli_data.get('tipo_institucion', '')
                            },
                            items=items_pdf, observaciones=row_sel['observaciones'], vigencia_fecha=str_val, total_letras=tl
                        )
                        st.download_button("⬇️ Bajar", pdf_bytes, f"{row_sel['codigo_cotizacion']}.pdf", "application/pdf")

                    if b3.button("🗑️ Borrar", use_container_width=True):
                        supabase.table('cotizaciones').delete().eq('id', int(row_sel['id'])).execute()
                        st.toast("Eliminado"); time.sleep(1); st.rerun()

                    tel_cl = ""
                    try: tel_cl = supabase.table('clientes').select("telefono").eq('id', int(row_sel['cliente_id'])).single().execute().data['telefono']
                    except: pass
                    if tel_cl:
                        tc = ''.join(filter(str.isdigit, str(tel_cl)))
                        if len(tc)>0 and not tc.startswith("593"): tc = "593"+tc
                        lnk = f"https://wa.me/{tc}?text=Cotizacion%20{row_sel['codigo_cotizacion']}%20Total:{row_sel['total']}"
                        b4.link_button("📲 WA", lnk, use_container_width=True)
                    else: b4.button("No Telf", disabled=True)
        else: st.info("Sin registros.")

    elif st.session_state['vista_cot'] == "EDITOR":
        c_b, c_h = st.columns([1, 6])
        if c_b.button("🔙 Volver", use_container_width=True):
            st.session_state['vista_cot'] = "LISTA"; st.rerun()
        
        c_h.header(f"✏️ Editando: {st.session_state.get('codigo_edicion', 'Nueva Cotización')}")
        st.divider()

        # 1. CLIENTE
        c_cli, c_dat = st.columns([2, 1])
        with c_cli:
            try:
                cli_db = supabase.table('clientes').select("*").execute().data
                opciones_cli = {f"{c['nombre_completo']} | {c['cedula_ruc']}": c for c in cli_db}
                claves_cli = list(opciones_cli.keys())
            except: opciones_cli = {}; claves_cli = []
            
            idx_sel = 0
            if st.session_state.get('cliente_id_edicion'):
                curr = st.session_state['cliente_id_edicion']
                for i, v in enumerate(opciones_cli.values()):
                    if v['id'] == curr: idx_sel = i + 1; break
            
            sel = st.selectbox("Cliente", [""]+claves_cli, index=idx_sel)
            sel_id = opciones_cli[sel]['id'] if sel else None
            
            with st.popover("➕ Crear Cliente Nuevo"):
                with st.form("new_c"):
                    nc1, nc2 = st.columns(2)
                    ruc, nom = nc1.text_input("RUC/CI *"), nc2.text_input("Nombre *")
                    nc3, nc4 = st.columns(2)
                    tel, mail = nc3.text_input("Telf"), nc4.text_input("Email")
                    ciu = st.text_input("Ciudad")
                    nc_tipo = st.selectbox("Tipo", ["Cliente Final", "Escuela Fútbol", "Empresa", "Fiscal", "Particular"])
                    nc_gen = st.selectbox("Género", ["Masculino", "Femenino", "Otro"])
                    if st.form_submit_button("Guardar"):
                        if ruc and nom:
                            try:
                                res = supabase.table('clientes').insert({"cedula_ruc":ruc, "nombre_completo":nom.upper(), "telefono":tel, "email":mail, "ciudad":ciu, "tipo_institucion": nc_tipo, "genero": nc_gen}).execute()
                                st.session_state['cliente_id_edicion'] = res.data[0]['id']
                                st.success("Creado!"); st.rerun()
                            except Exception as e: st.error(f"Error: {e}")
        
        with c_dat:
            f_em = st.date_input("Fecha", value=datetime.date.today())
            
        # 2. PRODUCTOS (Buscador mejorado según imagen)
        st.markdown("---")
        with st.container(border=True):
            st.markdown("🔍 **Filtros de Búsqueda (Catálogo)**")
            prods = supabase.table('productos_catalogo').select("*").eq('activo', True).execute().data
            df_p = pd.DataFrame(prods)
            
            if not df_p.empty:
                # Fila 1: Selectores
                f1, f2, f3 = st.columns(3)
                tp = f1.selectbox("Prenda", ["Todos"]+sorted(df_p['tipo_prenda'].unique().tolist()))
                cat = f2.selectbox("Categoría", ["Todos"]+sorted(df_p['linea_categoria'].unique().tolist()))
                edad = f3.selectbox("Edad", ["Todos"]+sorted(df_p['grupo_edad'].unique().tolist()))
                
                # Fila 2: Checkboxes de Características
                st.markdown("**Características de Producción:**")
                c1, c2, c3, c_search = st.columns([1, 1, 1, 2.5])
                solo_sub = c1.checkbox("Solo Sublimado")
                solo_dtf = c2.checkbox("Solo DTF")
                solo_bor = c3.checkbox("Solo Bordado")
                txt_busq = c_search.text_input("Buscar texto...", placeholder="Cód o Nombre")
                
                # Aplicar Filtros
                df_f = df_p
                if tp != "Todos": df_f = df_f[df_f['tipo_prenda']==tp]
                if cat != "Todos": df_f = df_f[df_f['linea_categoria']==cat]
                if edad != "Todos": df_f = df_f[df_f['grupo_edad']==edad]
                if solo_sub: df_f = df_f[df_f['requiere_sublimado']==True]
                if solo_dtf: df_f = df_f[df_f['requiere_dtf']==True]
                if solo_bor: df_f = df_f[df_f['requiere_bordado']==True]
                if txt_busq: 
                    df_f = df_f[df_f['descripcion'].str.contains(txt_busq, case=False) | df_f['codigo_referencia'].str.contains(txt_busq, case=False)]
                
                st.markdown("Seleccione el producto de la lista filtrada")
                map_p = {f"{r['codigo_referencia']} | {r['descripcion']}": r for r in df_f.to_dict('records')}
                
                if map_p:
                    k_sel = st.selectbox("Resultado", list(map_p.keys()), label_visibility="collapsed")
                    obj = map_p[k_sel]
                    
                    # Área de inserción de cantidad y precio
                    st.markdown("<br>", unsafe_allow_html=True)
                    col_k, col_t, col_pr, col_bt = st.columns([1, 1.5, 1, 1])
                    
                    cant = col_k.number_input("Cant", 1.0, step=1.0)
                    tarifa = col_t.selectbox("Tarifa", ["Auto", "Unit", "Docena", "Mayorista"])
                    
                    # Lógica de Precios
                    p_base = obj['precio_unitario']
                    req_pin = False
                    if tarifa == "Auto":
                        if cant >= 25: p_base = obj['precio_mayorista']
                        elif cant >= 12: p_base = obj['precio_docena']
                    elif tarifa == "Docena":
                        p_base = obj['precio_docena']
                        if cant < 12: req_pin = True
                    elif tarifa == "Mayorista":
                        p_base = obj['precio_mayorista']
                        if cant < 25: req_pin = True
                    
                    final_p = col_pr.number_input("Precio", value=float(p_base))
                    
                    add_ready = True
                    if req_pin:
                        pin = st.text_input("🔑 Autorización Requerida", type="password")
                        if pin != "1234": # Pin de ejemplo, ajustar según secrets
                            st.warning("Requiere PIN para aplicar tarifa de volumen con pocas unidades")
                            add_ready = False
                    
                    if col_bt.button("➕ AGREGAR", type="primary", use_container_width=True):
                        if add_ready:
                            st.session_state['cot_items'].append({
                                "id": obj['id'], "codigo": obj['codigo_referencia'], "descripcion": obj['descripcion'],
                                "cantidad": cant, "precio": final_p, "subtotal": cant*final_p, "obj_raw": obj 
                            })
                            st.rerun()

# 3. DETALLE DE LA COTIZACIÓN (Edición de cantidad y eliminación habilitada)
        if st.session_state['cot_items']:
            st.markdown("### Detalle de Items")
            st.info("💡 Para eliminar un ítem: Selecciona el recuadro a la izquierda del código y presiona la tecla 'Suprimir' o 'Delete' en tu teclado.")
            
            # Preparar datos
            df_original = pd.DataFrame(st.session_state['cot_items'])
            
            # Editor con eliminación dinámica habilitada
            edited_df = st.data_editor(
                df_original[['codigo', 'descripcion', 'cantidad', 'precio', 'subtotal']],
                column_config={
                    "codigo": st.column_config.TextColumn("Código", disabled=True),
                    "descripcion": st.column_config.TextColumn("Descripción", disabled=True),
                    "cantidad": st.column_config.NumberColumn("Cant.", min_value=1.0, step=1.0, format="%d"),
                    "precio": st.column_config.NumberColumn("P. Unit", format="$ %.2f", disabled=True),
                    "subtotal": st.column_config.NumberColumn("Total", format="$ %.2f", disabled=True)
                },
                num_rows="dynamic", # ESTA LÍNEA PERMITE ELIMINAR FILAS
                use_container_width=True,
                key="grid_cot_edit",
                hide_index=True
            )
            
            # Lógica de Sincronización: Detecta si se borró una fila o se cambió un valor
            if not edited_df.equals(df_original[['codigo', 'descripcion', 'cantidad', 'precio', 'subtotal']]):
                new_items = []
                # Reconstruimos la lista basándonos en lo que quedó en el editor
                for index, row in edited_df.iterrows():
                    # Buscamos el objeto original por índice para no perder IDs ni obj_raw
                    if index < len(st.session_state['cot_items']):
                        orig = st.session_state['cot_items'][index]
                        nueva_cant = float(row['cantidad'])
                        
                        new_items.append({
                            "id": orig['id'],
                            "codigo": orig['codigo'],
                            "descripcion": orig['descripcion'],
                            "cantidad": nueva_cant,
                            "precio": orig['precio'],
                            "subtotal": nueva_cant * orig['precio'],
                            "obj_raw": orig.get('obj_raw')
                        })
                
                st.session_state['cot_items'] = new_items
                st.rerun()

            # --- El resto de tu lógica de totales y guardado se mantiene igual ---
            tot = sum([x['subtotal'] for x in st.session_state['cot_items']])
            st.markdown(f"### Total Cotizado: :green[${tot:.2f}]")
            
            obs = st.text_area("Observaciones de la Cotización", value=st.session_state.get('cot_obs_temp',''))
            
            if st.button("💾 GUARDAR COTIZACIÓN", type="primary", use_container_width=True):
                if sel_id:
                    try:
                        cod = st.session_state.get('codigo_edicion') or generar_siguiente_codigo_cot(supabase)
                        data_head = {
                            "codigo_cotizacion": cod, "cliente_id": sel_id, 
                            "subtotal": tot/1.15, "iva": tot - (tot/1.15), "total": tot,
                            "observaciones": obs, "fecha_emision": str(f_em),
                            "estado": "BORRADOR", "creado_por_id": st.session_state.get('id_usuario', 1)
                        }
                        
                        if st.session_state.get('modo_edicion_cot'):
                            supabase.table('cotizaciones').update(data_head).eq('id', st.session_state['id_cot_edicion']).execute()
                            cot_id = st.session_state['id_cot_edicion']
                            supabase.table('detalles_cotizacion').delete().eq('cotizacion_id', cot_id).execute()
                        else:
                            res = supabase.table('cotizaciones').insert(data_head).execute()
                            cot_id = res.data[0]['id']
                        
                        detalles = []
                        for i in st.session_state['cot_items']:
                            detalles.append({
                                "cotizacion_id": cot_id, "producto_id": i['id'],
                                "cantidad": i['cantidad'], "precio_unitario": i['precio'],
                                "subtotal": i['subtotal'], "descripcion_snapshot": i['descripcion']
                            })
                        supabase.table('detalles_cotizacion').insert(detalles).execute()
                        
                        st.success(f"Cotización {cod} guardada con éxito")
                        st.session_state['vista_cot'] = "LISTA"
                        time.sleep(1); st.rerun()
                    except Exception as e: st.error(f"Error al guardar: {e}")
                else: st.error("Debe seleccionar un cliente antes de guardar.")