import streamlit as st
import pandas as pd
from fpdf import FPDF
from fpdf.fonts import FontFace 
from datetime import datetime
import io

# ==========================================
# 1. UTILIDADES Y FORMATEO
# ==========================================
def formatear_fecha_es(fecha_str):
    if not fecha_str: return "Fecha no definida"
    try:
        if 'T' in fecha_str: fecha_str = fecha_str.split('T')[0]
        d = datetime.strptime(fecha_str, '%Y-%m-%d')
        meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
        dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        return f"{dias[d.weekday()]}, {d.day} de {meses[d.month-1]} del {d.year}"
    except: return fecha_str

def orden_talla(talla):
    """Enseña al sistema a ordenar tallas lógicamente (Niños -> Adultos)"""
    if not talla: return 99
    t = str(talla).strip().upper()
    mapping = {
        "2": 1, "4": 2, "6": 3, "8": 4, "10": 5, "12": 6, "14": 7, "16": 8, "18": 9,
        "20": 10, "22": 11, "24": 12, "26": 13, "28": 14, "30": 15, "32": 16, "34": 17, "36": 18, "38": 19, "40": 20,
        "4-6": 21, "6-8": 22, "8-10": 23, "10-12": 24,
        "TXS": 29, "XS": 30, "S": 31, "M": 32, "L": 33, "XL": 34, "2XL": 35, "XXL": 35, "3XL": 36, "XXXL": 36, "4XL": 37, "5XL": 38
    }
    return mapping.get(t, 99) 

def agrupar_items_financiero(items):
    agrupados = {}
    for item in items:
        prod = str(item.get('nombre_producto', '')).strip()
        tela = str(item.get('nombre_tela', '')).strip()
        fam = str(item.get('familia_producto', '')).strip()
        precio = round(float(item.get('precio_aplicado', 0.0)), 2)
        key = f"{prod}|{tela}|{fam}|{precio}"

        if key not in agrupados:
            agrupados[key] = {
                'nombre_producto': prod, 'nombre_tela': tela, 'familia_producto': fam,
                'precio_aplicado': precio, 'cantidad_total': int(item.get('cantidad_total', 0)),
                'especificaciones_producto': list(item.get('especificaciones_producto', []))
            }
        else:
            agrupados[key]['cantidad_total'] += int(item.get('cantidad_total', 0))
            agrupados[key]['especificaciones_producto'].extend(item.get('especificaciones_producto', []))
    return list(agrupados.values())

def agrupar_items_taller(items):
    agrupados = {}
    for item in items:
        prod = str(item.get('nombre_producto', '')).strip()
        tela = str(item.get('nombre_tela', '')).strip()
        fam = str(item.get('familia_producto', '')).strip()
        key = f"{prod}|{tela}|{fam}" 

        if key not in agrupados:
            agrupados[key] = {
                'nombre_producto': prod, 'nombre_tela': tela, 'familia_producto': fam,
                'cantidad_total': int(item.get('cantidad_total', 0)),
                'especificaciones_producto': list(item.get('especificaciones_producto', []))
            }
        else:
            agrupados[key]['cantidad_total'] += int(item.get('cantidad_total', 0))
            agrupados[key]['especificaciones_producto'].extend(item.get('especificaciones_producto', []))
    return list(agrupados.values())

# ==========================================
# 2. LÓGICA DE BASE DE DATOS
# ==========================================
def obtener_ultimas_ordenes(supabase_client):
    try:
        res = supabase_client.table('ordenes').select('codigo_orden, estado, fecha_entrega, total_estimado').order('created_at', desc=True).limit(10).execute()
        return res.data
    except: return []

def obtener_datos_orden(supabase_client, busqueda):
    try:
        termino = busqueda.strip()
        res_orden = supabase_client.table('ordenes').select('*').ilike('codigo_orden', f'%{termino}%').order('created_at', desc=True).execute()
        if not res_orden.data: return None
        orden_data = res_orden.data[0]
        orden_id = orden_data['id']

        if orden_data.get('cliente_id'):
            res_cliente = supabase_client.table('clientes').select('*').eq('id', orden_data['cliente_id']).execute()
            orden_data['clientes'] = res_cliente.data[0] if res_cliente.data else {}
        else: orden_data['clientes'] = {}

        if orden_data.get('creado_por_id'):
            res_creador = supabase_client.table('usuarios').select('nombre_completo').eq('id', orden_data['creado_por_id']).execute()
            orden_data['creador'] = res_creador.data[0].get('nombre_completo', 'Desconocido') if res_creador.data else "Desconocido"
        else: orden_data['creador'] = "No registrado"

        res_items = supabase_client.table('items_orden').select('*').eq('orden_id', orden_id).execute()
        items = res_items.data

        for item in items:
            if item.get('producto_id'):
                try:
                    res_prod = supabase_client.table('productos_catalogo').select('descripcion').eq('id', item['producto_id']).execute()
                    item['nombre_producto'] = res_prod.data[0]['descripcion'] if res_prod.data else item.get('familia_producto')
                except: item['nombre_producto'] = item.get('familia_producto')
            else: item['nombre_producto'] = item.get('familia_producto')
                
            id_tela = item.get('insumo_base_id')
            if id_tela:
                try:
                    res_tela = supabase_client.table('insumos').select('nombre').eq('id', id_tela).execute()
                    item['nombre_tela'] = res_tela.data[0]['nombre'] if res_tela.data else "Estándar"
                except: item['nombre_tela'] = "Estándar"
            else: item['nombre_tela'] = "Estándar"
                
            res_esp = supabase_client.table('especificaciones_producto').select('*').eq('item_orden_id', item['id']).execute()
            item['especificaciones_producto'] = res_esp.data

        orden_data['items'] = items
        
        try:
            res_pagos = supabase_client.table('pagos').select('*').eq('orden_id', orden_id).execute()
            orden_data['pagos'] = res_pagos.data
        except: orden_data['pagos'] = []
            
        return orden_data
    except Exception as e:
        st.error(f"Error base de datos: {str(e)}")
        return None

def buscar_lista_ordenes(supabase_client, codigo="", cliente="", fechas=None):
    try:
        query = supabase_client.table('ordenes').select('codigo_orden, estado, fecha_entrega, total_estimado, cliente_id, created_at')
        if codigo: query = query.ilike('codigo_orden', f'%{codigo.strip()}%')
        if fechas and len(fechas) == 2:
            inicio = fechas[0].strftime("%Y-%m-%d")
            fin = fechas[1].strftime("%Y-%m-%d")
            query = query.gte('created_at', f"{inicio}T00:00:00").lte('created_at', f"{fin}T23:59:59")
            
        res = query.order('created_at', desc=True).limit(100).execute()
        data = res.data
        if not data: return []

        cliente_ids = list(set([d['cliente_id'] for d in data if d.get('cliente_id')]))
        mapa_clientes = {}
        if cliente_ids:
            res_cli = supabase_client.table('clientes').select('*').in_('id', cliente_ids).execute()
            for c in res_cli.data: mapa_clientes[c['id']] = c.get('nombre_completo', c.get('nombre', 'Desconocido'))

        lista_limpia = []
        termino_cli = cliente.lower().strip() if cliente else ""
        for d in data:
            nom_cli = mapa_clientes.get(d.get('cliente_id'), 'Consumidor Final')
            if termino_cli and termino_cli not in nom_cli.lower(): continue
            lista_limpia.append({
                "Código": d.get('codigo_orden'),
                "Cliente": nom_cli,
                "Estado": d.get('estado'),
                "Entrega": d.get('fecha_entrega'),
                "Total": f"${d.get('total_estimado', 0):.2f}"
            })
        return lista_limpia
    except: return []

# ==========================================
# 3. MOTORES DE PDF (CLIENTE VS TALLER)
# ==========================================
class PDFComprobante(FPDF):
    def header(self):
        try: self.image("FONDOYUNPAR.png", x=0, y=0, w=210, h=297)
        except: pass 
        self.set_y(50)

    def footer(self):
        self.set_y(-10); self.set_x(120)  
        self.set_font("helvetica", "B", 8); self.set_text_color(255, 255, 255) 
        fecha_imp = datetime.now().strftime('%d/%m/%Y %H:%M')
        self.cell(0, 10, f"Impreso el: {fecha_imp}  |  Página {self.page_no()}/{{nb}}", align="L")
        self.set_text_color(0, 0, 0) 

class PDFTaller(FPDF):
    def header(self):
        try:
            # Insertamos el logo en la esquina superior izquierda
            self.image("Logo_Yunpar.png", x=10, y=8, w=60)
        except:
            pass 
        
        # Obligamos a que todo el contenido de TODAS las páginas empiece más abajo
        # para no chocar ni superponerse con la imagen del logo
        self.set_y(35)

    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8); self.set_text_color(100, 100, 100)
        self.cell(0, 10, f"Documento Interno de Producción  |  Página {self.page_no()}/{{nb}}", align="C")
        self.set_text_color(0, 0, 0)
        
def generar_comprobante_cliente(orden):
    pdf = PDFComprobante()
    pdf.add_page()
    items_financieros = agrupar_items_financiero(orden['items']) 
    items_anexo_taller = agrupar_items_taller(orden['items']) 
    
    # --- HOJA 1: COMPROBANTE ---
    pdf.set_font("helvetica", "B", 24)
    pdf.set_text_color(0, 51, 153) 
    pdf.cell(0, 12, f"{orden['codigo_orden']}", new_x="LMARGIN", new_y="NEXT", align="L")
    pdf.set_text_color(0, 0, 0) 
    pdf.ln(5)

    pdf.set_font("helvetica", "B", 10)
    cli = orden.get('clientes', {})
    nombre_cliente = cli.get('nombre_completo', cli.get('nombre', 'Consumidor Final'))
    telefono = cli.get('telefono', cli.get('celular', 'No registrado'))
    correo = cli.get('correo', cli.get('email', 'No registrado'))
    creador = orden.get('creador', 'No registrado')
    disenador = orden.get('disenador_asignado', 'No asignado')

    ancho_etiqueta1 = 27; ancho_valor1 = 70; ancho_etiqueta2 = 31 
    
    pdf.cell(ancho_etiqueta1, 6, "Cliente:", border=False); pdf.set_font("helvetica", "", 10)
    pdf.cell(ancho_valor1, 6, f"{nombre_cliente}", border=False); pdf.set_font("helvetica", "B", 10)
    pdf.cell(ancho_etiqueta2, 6, "Fecha Pedido:", border=False); pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 6, f"{formatear_fecha_es(orden.get('created_at'))}", border=False, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("helvetica", "B", 10)
    pdf.cell(ancho_etiqueta1, 6, "Teléfono:", border=False); pdf.set_font("helvetica", "", 10)
    pdf.cell(ancho_valor1, 6, f"{telefono}  /  {correo}", border=False); pdf.set_font("helvetica", "B", 10)
    pdf.cell(ancho_etiqueta2, 6, "Fecha Entrega:", border=False); pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 6, f"{formatear_fecha_es(orden.get('fecha_entrega'))}", border=False, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("helvetica", "B", 10)
    pdf.cell(ancho_etiqueta1, 6, "Atendido por:", border=False); pdf.set_font("helvetica", "", 10)
    pdf.cell(ancho_valor1, 6, f"{creador}", border=False); pdf.set_font("helvetica", "B", 10)
    pdf.cell(ancho_etiqueta2, 6, "Diseñador:", border=False); pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 6, f"{disenador}", border=False, new_x="LMARGIN", new_y="NEXT"); pdf.ln(8)

    pdf.set_font("helvetica", "", 10)
    with pdf.table(col_widths=(115, 20, 25, 30), text_align=("LEFT", "CENTER", "RIGHT", "RIGHT")) as table:
        estilo_cabecera = FontFace(fill_color=(0, 51, 153), color=(255, 255, 255), emphasis="B")
        row = table.row(style=estilo_cabecera)
        for header in ["Producto", "Cantidad", "Precio Unit.", "Subtotal"]: row.cell(header)
        estilo_datos = FontFace(fill_color=(255, 255, 255), color=(0, 0, 0), emphasis="")
        
        for item in items_financieros:
            row = table.row(style=estilo_datos)
            nombre_prod = str(item.get('nombre_producto', 'Producto no definido')).replace('│', '|').replace('—', '-') 
            row.cell(nombre_prod); row.cell(str(item.get('cantidad_total', 0)))
            precio = item.get('precio_aplicado', 0)
            row.cell(f"${precio:.2f}"); row.cell(f"${item.get('cantidad_total', 0) * precio:.2f}")

    pdf.ln(5); pdf.set_font("helvetica", "B", 12)
    x_offset = 145 
    pdf.set_x(x_offset); pdf.cell(30, 8, "Total:", align="R"); pdf.cell(25, 8, f"${orden.get('total_estimado', 0):.2f}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(x_offset); pdf.cell(30, 8, "Abono:", align="R"); pdf.cell(25, 8, f"${orden.get('abono_inicial', 0):.2f}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(x_offset); pdf.cell(30, 8, "Saldo:", align="R"); pdf.set_text_color(200, 0, 0) 
    pdf.cell(25, 8, f"${orden.get('saldo_pendiente', 0):.2f}", align="R", new_x="LMARGIN", new_y="NEXT"); pdf.set_text_color(0, 0, 0) 
    
    pdf.ln(10)
    # --- 1. LÓGICA ESTRICTA DE PRIORIDAD DE IMÁGENES ---
    arte = str(orden.get('url_arte_final') or '').strip()
    boceto = str(orden.get('url_boceto_vendedora') or '').strip()
    
    if arte and arte.lower() not in ['none', 'null']:
        url_imagen = arte
    elif boceto and boceto.lower() not in ['none', 'null']:
        url_imagen = boceto
    else:
        url_imagen = None
        
    pagos = orden.get('pagos', [])
    
    if url_imagen and pagos:
        pdf.set_font("helvetica", "B", 10)
        pdf.cell(0, 10, "Referencia de Diseño e Historial de Pagos:", align="L", new_x="LMARGIN", new_y="NEXT")
        start_y = pdf.get_y()
        try:
            # AJUSTE: Reduje la imagen a 95mm (antes 105) para dar más espacio a la tabla
            pdf.image(url_imagen, w=95)
            end_image_y = pdf.get_y()
        except:
            pdf.set_font("helvetica", "I", 9); pdf.cell(95, 10, "(Imagen no disponible)"); end_image_y = pdf.get_y()
            
        pdf.set_y(start_y)
        
        # --------------------------------------------------------------------------
        # AQUÍ HACES EL AJUSTE MANUAL DE LA TABLA:
        # 'set_left_margin' empuja la tabla a la derecha. Antes era 120, lo subí a 135.
        # Puedes jugar con este valor (ej: 140), pero cuida que no se salga de la hoja.
        # --------------------------------------------------------------------------
        pdf.set_left_margin(150) 
        
        pdf.set_font("helvetica", "", 9)
        estilo_cabecera_pagos = FontFace(fill_color=(0, 51, 153), color=(255, 255, 255), emphasis="B")
        estilo_datos_pagos = FontFace(fill_color=(255, 255, 255), color=(0, 0, 0), emphasis="")
        
        # AJUSTE: Reduje ligeramente el ancho de las columnas (20, 35, 15) que suman 70mm.
        # Así, Margen(135) + Tabla(70) = 205mm. Entra perfecto en la A4 (210mm).
        with pdf.table(col_widths=(20, 35, 15), text_align=("CENTER", "LEFT", "RIGHT")) as t_pagos:
            row = t_pagos.row(style=estilo_cabecera_pagos)
            for h in ["Fecha", "Banco", "Monto"]: row.cell(h)
            for p in pagos:
                row = t_pagos.row(style=estilo_datos_pagos)
                f_pago = p.get('fecha_pago', '')
                if f_pago and len(f_pago) >= 10: f_pago = f"{f_pago[8:10]}/{f_pago[5:7]}/{f_pago[2:4]}" # Acorté el año a 2 dígitos para ahorrar espacio
                banco = p.get('banco_destino') or p.get('metodo_pago') or 'Efectivo'
                row.cell(f_pago); row.cell(str(banco)[:15]); row.cell(f"${float(p.get('monto', 0)):.2f}")
                
        end_table_y = pdf.get_y()
        pdf.set_left_margin(10); pdf.set_y(max(end_table_y, end_image_y) + 5)
        
    elif url_imagen and not pagos:
        pdf.set_font("helvetica", "B", 10)
        pdf.cell(0, 10, "Referencia de Diseño:", align="L", new_x="LMARGIN", new_y="NEXT")
        try: pdf.image(url_imagen, w=160, x="CENTER")
        except: pass
        
    elif not url_imagen and pagos:
        pdf.set_font("helvetica", "B", 10)
        pdf.cell(0, 10, "Historial de Pagos / Abonos:", align="L", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("helvetica", "", 9)
        estilo_cabecera_pagos = FontFace(fill_color=(0, 51, 153), color=(255, 255, 255), emphasis="B")
        estilo_datos_pagos = FontFace(fill_color=(255, 255, 255), color=(0, 0, 0), emphasis="")
        with pdf.table(col_widths=(40, 80, 40), text_align=("CENTER", "LEFT", "RIGHT")) as t_pagos:
            row = t_pagos.row(style=estilo_cabecera_pagos)
            for h in ["Fecha", "Banco/Método", "Monto"]: row.cell(h)
            for p in pagos:
                row = t_pagos.row(style=estilo_datos_pagos)
                f_pago = p.get('fecha_pago', '')
                if f_pago and len(f_pago) >= 10: f_pago = f"{f_pago[8:10]}/{f_pago[5:7]}/{f_pago[0:4]}"
                banco = p.get('banco_destino') or p.get('metodo_pago') or 'Efectivo'
                row.cell(f_pago); row.cell(str(banco)); row.cell(f"${float(p.get('monto', 0)):.2f}")

    # --- HOJA 2: ANEXO DE TÉRMINOS Y ESPECIFICACIONES ---
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.set_text_color(0, 51, 153)
    pdf.cell(0, 10, "ANEXO: DETALLE TÉCNICO APROBADO", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0); pdf.ln(2)

    pdf.set_font("helvetica", "", 9)
    pdf.multi_cell(0, 5, "El presente anexo detalla las especificaciones exactas (tallas, nombres, números y materiales) solicitadas para la orden. Por favor, verifique que la información detallada a continuación sea correcta.")
    pdf.ln(5)

    estilo_cabecera_anexo = FontFace(fill_color=(0, 51, 153), color=(255, 255, 255), emphasis="B")
    estilo_datos_anexo = FontFace(fill_color=(255, 255, 255), color=(0, 0, 0), emphasis="")

    for item in items_anexo_taller:
        nombre_prod = str(item.get('nombre_producto', 'Producto')).replace('│', '|').replace('—', '-')
        tela = item.get('nombre_tela', 'Estándar')
        familia = item.get('familia_producto', 'GENERICO')
        especificaciones = item.get('especificaciones_producto', [])
        
        if familia in ['UNIFORME COMPLETO', 'PRENDA SUPERIOR']:
            especificaciones.sort(key=lambda x: (orden_talla(x.get('talla_superior')), orden_talla(x.get('talla_inferior'))))
        elif familia == 'PANTALONETA':
            especificaciones.sort(key=lambda x: orden_talla(x.get('talla_inferior')))

        pdf.set_font("helvetica", "B", 10); pdf.set_fill_color(230, 230, 230)
        titulo_prod = f" PRODUCTO: {nombre_prod}   |   CANTIDAD TOTAL: {item.get('cantidad_total', 0)}\n TELA: {tela}"
        pdf.multi_cell(0, 6, titulo_prod, border=1, fill=True, align="L")

        if not especificaciones:
            pdf.set_font("helvetica", "I", 9); pdf.cell(0, 8, "  Sin lista de detalles para este producto.", border=1, new_x="LMARGIN", new_y="NEXT"); pdf.ln(5)
            continue

        pdf.set_font("helvetica", "", 9)
        tiene_polines = any(bool(esp.get('talla_polines')) for esp in especificaciones) if familia == 'UNIFORME COMPLETO' else False
        
        if familia == 'UNIFORME COMPLETO' and tiene_polines:
            cols = (10, 20, 60, 12, 28, 20, 40)
            headers = ["Cant", "Talla", "Nombre / Referencia", "Num", "Cuello", "Polín", "Observación"]
        elif familia in ['UNIFORME COMPLETO', 'PRENDA SUPERIOR']:
            cols = (12, 23, 65, 15, 30, 45)
            headers = ["Cant", "Talla", "Nombre / Referencia", "Num", "Cuello", "Observación"]
        elif familia == 'PANTALONETA':
            cols = (15, 25, 30, 120); headers = ["Cant", "Talla Inf.", "Num", "Observación"]
        else:
            cols = (15, 25, 150); headers = ["Cant", "Talla", "Observaciones"]

        with pdf.table(col_widths=cols, text_align=("CENTER", "CENTER", "LEFT", "CENTER", "LEFT", "CENTER", "LEFT") if tiene_polines else ("CENTER", "CENTER", "LEFT", "CENTER", "LEFT", "LEFT")) as t_anexo:
            row = t_anexo.row(style=estilo_cabecera_anexo)
            for h in headers: row.cell(h)
            for esp in especificaciones:
                row = t_anexo.row(style=estilo_datos_anexo)
                cant = "1"
                talla_s = str(esp.get('talla_superior') or '').strip() or '-'
                talla_i = str(esp.get('talla_inferior') or '').strip() or '-'
                nom = str(esp.get('nombre_jugador') or '').strip()
                num = str(esp.get('numero_dorsal') or '').strip()
                cuello = str(esp.get('tipo_cuello_texto') or '').strip()
                obs = str(esp.get('observacion_individual') or '').strip()
                polin = str(esp.get('talla_polines') or '').strip() or '-' 
                
                if familia == 'UNIFORME COMPLETO': talla = f"{talla_s} / {talla_i}"
                elif familia == 'PRENDA SUPERIOR': talla = talla_s
                elif familia == 'PANTALONETA': talla = talla_i
                else: talla = "-"

                if familia == 'UNIFORME COMPLETO' and tiene_polines:
                    row.cell(cant); row.cell(talla); row.cell(nom); row.cell(num); row.cell(cuello); row.cell(polin); row.cell(obs)
                elif familia in ['UNIFORME COMPLETO', 'PRENDA SUPERIOR']:
                    row.cell(cant); row.cell(talla); row.cell(nom); row.cell(num); row.cell(cuello); row.cell(obs)
                elif familia == 'PANTALONETA':
                    row.cell(cant); row.cell(talla); row.cell(num); row.cell(obs)
                else:
                    row.cell(cant); row.cell(talla); row.cell(obs)
        pdf.ln(8)

    if pdf.get_y() > 220: pdf.add_page(); pdf.set_y(50)

    pdf.ln(10); pdf.set_font("helvetica", "B", 9)
    pdf.multi_cell(0, 5, "DECLARACIÓN DE APROBACIÓN: Revisé detalladamente y apruebo que los nombres, números, tallas, cuellos, telas y observaciones detalladas en este anexo son correctas para el inicio de la producción.")
    pdf.ln(25); start_firma_y = pdf.get_y()
    
    pdf.set_x(25); pdf.line(25, start_firma_y, 85, start_firma_y); pdf.set_x(25)
    pdf.cell(60, 5, "Firma del Cliente", align="C", new_x="LMARGIN", new_y="NEXT"); pdf.set_x(25)
    pdf.set_font("helvetica", "", 8); pdf.cell(60, 5, f"{nombre_cliente}", align="C")

    pdf.set_y(start_firma_y); pdf.set_x(125)
    pdf.line(125, start_firma_y, 185, start_firma_y); pdf.set_x(125)
    pdf.set_font("helvetica", "B", 9); pdf.cell(60, 5, "Firma del Asesor / Vendedor", align="C", new_x="LMARGIN", new_y="NEXT"); pdf.set_x(125)
    pdf.set_font("helvetica", "", 8); pdf.cell(60, 5, f"{creador}", align="C")

    return bytes(pdf.output())

# ==========================================
# 4. HOJA DE PRODUCCIÓN TALLER (SOLUCIÓN DEFINITIVA DE TABLAS AISLADAS)
# ==========================================
def generar_hoja_produccion(orden):
    pdf = PDFTaller() 
    pdf.add_page()
    items_taller = agrupar_items_taller(orden['items'])
    
    # --- 1. CABECERA TALLER ---
    pdf.set_font("helvetica", "B", 26)
    pdf.cell(100, 12, f"ORDEN: {orden['codigo_orden']}", border=False)
    
    pdf.set_font("helvetica", "B", 14)
    pdf.set_text_color(200, 0, 0)
    pdf.cell(0, 12, f"ENTREGA: {formatear_fecha_es(orden.get('fecha_entrega'))}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    
    pdf.set_font("helvetica", "", 10)
    creador = orden.get('creador', 'No registrado')
    disenador = orden.get('disenador_asignado', 'No asignado')
    pdf.cell(0, 6, f"Diseñador: {disenador}  |  Asesor: {creador}", new_x="LMARGIN", new_y="NEXT")
    
    if orden.get('alerta_cambios'):
        pdf.ln(2); pdf.set_font("helvetica", "B", 12); pdf.set_fill_color(255, 200, 200)
        pdf.cell(0, 10, " ¡ATENCIÓN: ESTA ORDEN HA TENIDO CAMBIOS RECIENTES!", fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # --- 2. CÁLCULO DEL RESUMEN GLOBAL ---
    resumen_sup = {}
    resumen_inf = {}
    resumen_polines = {}
    
    for item in items_taller:
        fam = str(item.get('familia_producto', '')).strip().upper() 
        for esp in item.get('especificaciones_producto', []):
            
            # Conteo de Camisetas
            if fam in ['UNIFORME COMPLETO', 'PRENDA SUPERIOR']:
                t_sup = str(esp.get('talla_superior') or '').strip().upper()
                if t_sup and t_sup != '-' and t_sup != 'NONE': 
                    resumen_sup[t_sup] = resumen_sup.get(t_sup, 0) + 1
            
            # Conteo de Pantalonetas
            if fam in ['UNIFORME COMPLETO', 'PANTALONETA']:
                t_inf = str(esp.get('talla_inferior') or '').strip().upper()
                if t_inf and t_inf != '-' and t_inf != 'NONE': 
                    resumen_inf[t_inf] = resumen_inf.get(t_inf, 0) + 1
            
            # Conteo de Polines
            if fam == 'UNIFORME COMPLETO':
                t_pol = str(esp.get('talla_polines') or '').strip().upper()
                if t_pol and t_pol != '-' and t_pol != 'NONE':
                    c_pol = str(esp.get('color_polines') or 'Sin Color').strip()
                    k = (t_pol, c_pol)
                    resumen_polines[k] = resumen_polines.get(k, 0) + 1

    # --- 3. IMAGEN MAXIMIZADA ---
    arte = str(orden.get('url_arte_final') or '').strip()
    boceto = str(orden.get('url_boceto_vendedora') or '').strip()
    
    if arte and arte.lower() not in ['none', 'null']:
        url_imagen = arte
    elif boceto and boceto.lower() not in ['none', 'null']:
        url_imagen = boceto
    else:
        url_imagen = None
    
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 8, "REFERENCIA VISUAL DE CORTE Y CONFECCIÓN", align="C", new_x="LMARGIN", new_y="NEXT")
    
    if url_imagen:
        try:
            pdf.image(url_imagen, w=190, h=130, keep_aspect_ratio=True, x="CENTER") 
        except:
            pdf.set_font("helvetica", "I", 10)
            pdf.cell(0, 10, "(La imagen no pudo ser cargada)", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # --- 4. LAS 3 TABLAS DE RESUMEN AISLADAS Y CON BORDES EXACTOS ---
    if resumen_sup or resumen_inf or resumen_polines:
        pdf.set_font("helvetica", "B", 12)
        pdf.cell(0, 8, "RESUMEN GLOBAL DE CORTE", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        
        start_y = pdf.get_y()
        max_y = start_y
        
        # Colores RGB
        fill_cab = (150, 150, 150)
        fill_tot = (220, 220, 220)

        # TABLA 1: CAMISETAS (Izquierda Absoluta X=20)
        if resumen_sup:
            pdf.set_y(start_y)
            pdf.set_x(20)
            pdf.set_font("helvetica", "B", 9)
            pdf.cell(30, 6, "CAMISETAS", align="C", new_x="LMARGIN", new_y="NEXT")
            
            # Cabecera
            pdf.set_x(20)
            pdf.set_fill_color(*fill_cab)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(15, 6, "Talla", border=1, align="C", fill=True)
            pdf.cell(15, 6, "Cant", border=1, align="C", fill=True, new_x="LMARGIN", new_y="NEXT")
            
            # Datos
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("helvetica", "", 9)
            tot_cam = 0
            for t, cant in sorted(resumen_sup.items(), key=lambda x: orden_talla(x[0])):
                pdf.set_x(20)
                pdf.cell(15, 6, str(t), border=1, align="C")
                pdf.cell(15, 6, str(cant), border=1, align="C", new_x="LMARGIN", new_y="NEXT")
                tot_cam += cant
                
            # Fila Total
            pdf.set_x(20)
            pdf.set_font("helvetica", "B", 9)
            pdf.set_fill_color(*fill_tot)
            pdf.cell(15, 6, "TOTAL", border=1, align="C", fill=True)
            pdf.cell(15, 6, str(tot_cam), border=1, align="C", fill=True, new_x="LMARGIN", new_y="NEXT")
            max_y = max(max_y, pdf.get_y())

        # TABLA 2: PANTALONETAS (Centro Absoluto X=90)
        if resumen_inf:
            pdf.set_y(start_y)
            pdf.set_x(90)
            pdf.set_font("helvetica", "B", 9)
            pdf.cell(30, 6, "PANTALONETAS", align="C", new_x="LMARGIN", new_y="NEXT")
            
            # Cabecera
            pdf.set_x(90)
            pdf.set_fill_color(*fill_cab)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(15, 6, "Talla", border=1, align="C", fill=True)
            pdf.cell(15, 6, "Cant", border=1, align="C", fill=True, new_x="LMARGIN", new_y="NEXT")
            
            # Datos
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("helvetica", "", 9)
            tot_pan = 0
            for t, cant in sorted(resumen_inf.items(), key=lambda x: orden_talla(x[0])):
                pdf.set_x(90)
                pdf.cell(15, 6, str(t), border=1, align="C")
                pdf.cell(15, 6, str(cant), border=1, align="C", new_x="LMARGIN", new_y="NEXT")
                tot_pan += cant
                
            # Fila Total
            pdf.set_x(90)
            pdf.set_font("helvetica", "B", 9)
            pdf.set_fill_color(*fill_tot)
            pdf.cell(15, 6, "TOTAL", border=1, align="C", fill=True)
            pdf.cell(15, 6, str(tot_pan), border=1, align="C", fill=True, new_x="LMARGIN", new_y="NEXT")
            max_y = max(max_y, pdf.get_y())

        # TABLA 3: POLINES (Derecha Absoluta X=145)
        if resumen_polines:
            pdf.set_y(start_y)
            pdf.set_x(145)
            pdf.set_font("helvetica", "B", 9)
            pdf.cell(50, 6, "POLINES", align="C", new_x="LMARGIN", new_y="NEXT")
            
            # Cabecera
            pdf.set_x(145)
            pdf.set_fill_color(*fill_cab)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(15, 6, "Talla", border=1, align="C", fill=True)
            pdf.cell(20, 6, "Color", border=1, align="C", fill=True)
            pdf.cell(15, 6, "Cant", border=1, align="C", fill=True, new_x="LMARGIN", new_y="NEXT")
            
            # Datos
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("helvetica", "", 9)
            tot_pol = 0
            for (t, c), cant in sorted(resumen_polines.items(), key=lambda x: (orden_talla(x[0][0]), x[0][1])):
                pdf.set_x(145)
                pdf.cell(15, 6, str(t), border=1, align="C")
                pdf.cell(20, 6, str(c), border=1, align="C")
                pdf.cell(15, 6, str(cant), border=1, align="C", new_x="LMARGIN", new_y="NEXT")
                tot_pol += cant
                
            # Fila Total
            pdf.set_x(145)
            pdf.set_font("helvetica", "B", 9)
            pdf.set_fill_color(*fill_tot)
            pdf.cell(35, 6, "TOTAL", border=1, align="C", fill=True) # Colspan manual sumando anchos (15+20)
            pdf.cell(15, 6, str(tot_pol), border=1, align="C", fill=True, new_x="LMARGIN", new_y="NEXT")
            max_y = max(max_y, pdf.get_y())

        # RESTAURAR VARIABLES GLOBALES
        pdf.set_y(max_y + 8)
        pdf.set_left_margin(10)
        pdf.set_right_margin(10)
        pdf.set_text_color(0, 0, 0)

    # --- 5. LISTADO DETALLADO (SALTO FORZADO PARA ORDEN) ---
    pdf.add_page() 
    
    pdf.set_font("helvetica", "B", 14)
    pdf.cell(0, 10, "LISTADO DETALLADO POR PRODUCTO", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    estilo_cabecera_taller = FontFace(fill_color=(50, 50, 50), color=(255, 255, 255), emphasis="B")
    estilo_datos_taller = FontFace(fill_color=(255, 255, 255), color=(0, 0, 0), emphasis="")

    for item in items_taller:
        familia = item.get('familia_producto', 'GENERICO').upper()
        nombre_prod = str(item.get('nombre_producto', familia)).replace('│', '|').replace('—', '-')
        especificaciones = item.get('especificaciones_producto', [])
        tela = item.get('nombre_tela', 'Estándar') 
        
        # ORDENAMIENTO ESTRICTO DE LA LISTA LARGA
        if familia in ['UNIFORME COMPLETO', 'PRENDA SUPERIOR']:
            especificaciones.sort(key=lambda x: (orden_talla(x.get('talla_superior')), orden_talla(x.get('talla_inferior'))))
        elif familia == 'PANTALONETA':
            especificaciones.sort(key=lambda x: orden_talla(x.get('talla_inferior')))

        pdf.set_font("helvetica", "B", 11)
        pdf.set_fill_color(220, 220, 220)
        titulo_prod = f" PRODUCTO: {nombre_prod}   |   CANTIDAD TOTAL: {item.get('cantidad_total', 0)}\n TELA A USAR: {tela}"
        pdf.multi_cell(0, 7, titulo_prod, border=1, fill=True, align="L")

        if not especificaciones:
            pdf.set_font("helvetica", "I", 9); pdf.cell(0, 8, "  Sin lista de detalles.", border=1, new_x="LMARGIN", new_y="NEXT"); pdf.ln(5)
            continue

        pdf.set_font("helvetica", "", 10)
        tiene_polines = any(bool(esp.get('talla_polines')) for esp in especificaciones) if familia == 'UNIFORME COMPLETO' else False

        if familia == 'UNIFORME COMPLETO' and tiene_polines:
            cols = (15, 15, 60, 15, 30, 20, 35)
            headers = ["T. Sup", "T. Inf", "Nombre / Ref.", "Num", "Cuello", "Polín", "Obs"]
        elif familia in ['UNIFORME COMPLETO', 'PRENDA SUPERIOR']:
            cols = (20, 20, 65, 15, 30, 40)
            headers = ["T. Sup", "T. Inf", "Nombre / Ref.", "Num", "Cuello", "Observación"] if familia == 'UNIFORME COMPLETO' else ["T. Sup", "-", "Nombre / Ref.", "Num", "Cuello", "Observación"]
        elif familia == 'PANTALONETA':
            cols = (30, 30, 130); headers = ["Talla Inf.", "Num", "Observación"]
        elif familia == 'IMPRESION':
            cols = (30, 30, 50, 80); headers = ["Ancho (m)", "Largo (m)", "Acabado", "Obs / Calandrado"]
        else:
            cols = (20, 50, 120); headers = ["Cant", "Acabado", "Observación"]

        with pdf.table(col_widths=cols, text_align=("CENTER", "CENTER", "LEFT", "CENTER", "LEFT", "CENTER", "LEFT") if tiene_polines else ("CENTER", "CENTER", "LEFT", "CENTER", "LEFT", "LEFT")) as table:
            row = table.row(style=estilo_cabecera_taller)
            for h in headers: row.cell(h)
                
            for esp in especificaciones:
                row = table.row(style=estilo_datos_taller)
                if familia == 'UNIFORME COMPLETO':
                    row.cell(str(esp.get('talla_superior') or '-').strip() or '-'); row.cell(str(esp.get('talla_inferior') or '-').strip() or '-')
                    row.cell(str(esp.get('nombre_jugador') or '').strip()); row.cell(str(esp.get('numero_dorsal') or '').strip())
                    row.cell(str(esp.get('tipo_cuello_texto') or '').strip())
                    if tiene_polines: row.cell(str(esp.get('talla_polines') or '-').strip() or '-')
                    row.cell(str(esp.get('observacion_individual') or '').strip())
                elif familia == 'PRENDA SUPERIOR':
                    row.cell(str(esp.get('talla_superior') or '-').strip() or '-'); row.cell("-")
                    row.cell(str(esp.get('nombre_jugador') or '').strip()); row.cell(str(esp.get('numero_dorsal') or '').strip())
                    row.cell(str(esp.get('tipo_cuello_texto') or '').strip()); row.cell(str(esp.get('observacion_individual') or '').strip())
                elif familia == 'PANTALONETA':
                    row.cell(str(esp.get('talla_inferior') or '-').strip() or '-'); row.cell(str(esp.get('numero_dorsal') or '').strip())
                    row.cell(str(esp.get('observacion_individual') or '').strip())
                elif familia == 'IMPRESION':
                    row.cell(f"{esp.get('ancho_cm', 0) / 100:.2f} m" if esp.get('ancho_cm') else "-")
                    row.cell(f"{esp.get('alto_cm', 0) / 100:.2f} m" if esp.get('alto_cm') else "-")
                    row.cell(str(esp.get('acabado') or '').strip()); row.cell(str(esp.get('observacion_individual') or '').strip())
                else:
                    row.cell("1"); row.cell(str(esp.get('acabado') or '').strip()); row.cell(str(esp.get('observacion_individual') or '').strip())
        pdf.ln(5)

    return bytes(pdf.output())


# ==========================================
# MÓDULO NUEVO: GENERADOR DE ETIQUETAS DE EMPAQUE
# ==========================================
def generar_etiquetas(orden):
    # Usamos orientación "L" (Landscape/Horizontal) para A4 (297x210 mm)
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=False) # Apagamos el salto automático para controlarlo nosotros
    
    # -------------------------------------------------------------
    # 🛠️ ZONA DE AJUSTE MANUAL (COORDENADAS MILIMÉTRICAS) 🛠️
    # Juega con estos valores hasta que el texto calce en tu diseño
    # -------------------------------------------------------------
    
    # 1. Distancias de la cuadrícula (El salto entre etiquetas)
    # Si la A4 tiene 297mm de ancho, cada tercio mide aprox 99mm.
    PASO_X = 98.0  # Cuántos milímetros hay que moverse a la derecha para la siguiente columna
    PASO_Y = 70.0  # Cuántos milímetros hay que bajar para la siguiente fila (210mm / 3)
    
    # 2. Origen de la primera etiqueta (Arriba a la Izquierda)
    ORIGEN_X = 0   # Punto de inicio X de toda la cuadrícula
    ORIGEN_Y = 0   # Punto de inicio Y de toda la cuadrícula
    
    # 3. Posiciones internas relativas (Dentro de cada caja de etiqueta individual)
    # Suma estos valores al ORIGEN para colocar el texto en las cajas blancas
    OFFSET_X_TALLA  = 29.0    # Movimiento hacia la derecha para la Talla
    OFFSET_Y_TALLA  = 40.0    # Movimiento hacia abajo para la Talla
    
    OFFSET_X_NUMERO = 75.0    # Movimiento hacia la derecha para el Número
    OFFSET_Y_NUMERO = 40.0    # Movimiento hacia abajo para el Número
    
    OFFSET_X_NOMBRE = 38.0    # Movimiento hacia la derecha para el Nombre
    OFFSET_Y_NOMBRE = 52.0    # Movimiento hacia abajo para el Nombre
    
    # Tamaño de la fuente
    TAMANO_FUENTE = 14
    # -------------------------------------------------------------

    # Recopilar la data: Extraemos todos los nombres y tallas de la orden
    datos_etiquetas = []
    for item in orden.get('items', []):
        fam = str(item.get('familia_producto', '')).strip().upper()
        # Solo sacamos etiquetas para prendas personalizadas
        if fam in ['UNIFORME COMPLETO', 'PRENDA SUPERIOR', 'PANTALONETA']:
            for esp in item.get('especificaciones_producto', []):
                talla_s = str(esp.get('talla_superior') or '').strip()
                talla_i = str(esp.get('talla_inferior') or '').strip()
                
                # Inteligencia de Tallas (Para ahorrar espacio visual en la etiqueta)
                talla = ""
                if fam == 'UNIFORME COMPLETO':
                    if talla_s and talla_i and talla_s != '-' and talla_i != '-' and talla_s != talla_i:
                        talla = f"{talla_s}/{talla_i}"
                    else:
                        talla = talla_s if talla_s != '-' else talla_i
                elif fam == 'PRENDA SUPERIOR':
                    talla = talla_s
                elif fam == 'PANTALONETA':
                    talla = talla_i
                    
                if talla == '-': talla = ""
                
                numero = str(esp.get('numero_dorsal') or '').strip()
                nombre = str(esp.get('nombre_jugador') or '').strip()
                
                # Si al menos tiene un dato, creamos su etiqueta
                if talla or numero or nombre:
                    datos_etiquetas.append({
                        'talla': talla,
                        'numero': numero,
                        'nombre': nombre
                    })

    # Si no hay datos, creamos un PDF con un mensaje de aviso
    if not datos_etiquetas:
        pdf.add_page()
        pdf.set_font("helvetica", "B", 16)
        pdf.cell(0, 20, "NO HAY DATOS DE PERSONALIZACIÓN PARA GENERAR ETIQUETAS", align="C")
        return bytes(pdf.output())

    # Motor de dibujo de la cuadrícula (3x3)
    for i, data in enumerate(datos_etiquetas):
        # Cada 9 etiquetas (0, 9, 18...) creamos una nueva página y ponemos el fondo
        if i % 9 == 0:
            pdf.add_page()
            try:
                # Fondo estirado a todo el A4 Horizontal (w=297, h=210)
                pdf.image("ETIQUETAS-UNIFORMES.png", x=0, y=0, w=297, h=210)
            except Exception:
                pass # Si no encuentra la imagen, dibujará sobre blanco para poder depurar

        # Matemáticas de la Matriz (0 a 8)
        posicion_en_hoja = i % 9
        columna = posicion_en_hoja % 3   # Resultados: 0, 1, 2
        fila = posicion_en_hoja // 3     # Resultados: 0, 1, 2
        
        # Calcular la esquina superior izquierda de LA etiqueta actual
        base_x = ORIGEN_X + (columna * PASO_X)
        base_y = ORIGEN_Y + (fila * PASO_Y)
        
        # Dibujar los Textos
        pdf.set_font("helvetica", "B", TAMANO_FUENTE)
        
        # (Se usa pdf.text porque permite coordenadas absolutas libres sin crear celdas rígidas)
        if data['talla']:
            pdf.text(x=base_x + OFFSET_X_TALLA, y=base_y + OFFSET_Y_TALLA, txt=data['talla'])
            
        if data['numero']:
            pdf.text(x=base_x + OFFSET_X_NUMERO, y=base_y + OFFSET_Y_NUMERO, txt=data['numero'])
            
        if data['nombre']:
            pdf.text(x=base_x + OFFSET_X_NOMBRE, y=base_y + OFFSET_Y_NOMBRE, txt=data['nombre'])

    return bytes(pdf.output())


# ==========================================
# 5. INTERFAZ STREAMLIT
# ==========================================
def render_modulo_reportes(supabase_client):
    st.header("🖨️ Módulo de Reportes y Producción")

    if 'orden_actual' not in st.session_state:
        st.session_state.orden_actual = None

    with st.expander("🔍 Buscador Avanzado", expanded=True):
        with st.form("buscar_orden_form"):
            col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
            busqueda_cod = col1.text_input("Código de Orden", placeholder="Ej: 001")
            busqueda_cli = col2.text_input("Parte del nombre del Cliente", placeholder="Ej: Fra")
            busqueda_fechas = col3.date_input("Rango de Fechas (Pedido)", value=[], format="DD/MM/YYYY")
            
            st.write("") 
            submit_search = col4.form_submit_button("Filtrar Repositorio", use_container_width=True)

    if 'lista_ordenes' not in st.session_state or submit_search:
        with st.spinner("Cargando repositorio de órdenes..."):
            if submit_search: st.session_state.lista_ordenes = buscar_lista_ordenes(supabase_client, busqueda_cod, busqueda_cli, busqueda_fechas)
            else: st.session_state.lista_ordenes = buscar_lista_ordenes(supabase_client) 

    st.subheader("📚 Repositorio de Órdenes")
    if st.session_state.lista_ordenes:
        st.caption("📌 **Selecciona cualquier orden de la lista para ver su detalle y generar los PDFs:**")
        df_resultados = pd.DataFrame(st.session_state.lista_ordenes)
        
        evento = st.dataframe(
            df_resultados, use_container_width=True, hide_index=True,
            on_select="rerun", selection_mode="single-row"  
        )
        
        if len(evento.selection.rows) > 0:
            indice_seleccionado = evento.selection.rows[0]
            codigo_seleccionado = df_resultados.iloc[indice_seleccionado]["Código"]
            
            if not st.session_state.orden_actual or st.session_state.orden_actual['codigo_orden'] != codigo_seleccionado:
                with st.spinner(f"Cargando detalle de {codigo_seleccionado}..."):
                    datos = obtener_datos_orden(supabase_client, codigo_seleccionado)
                    st.session_state.orden_actual = datos
                    st.rerun() 
        else:
            # NUEVO: Si desmarcan la fila, limpiamos la vista previa
            if st.session_state.orden_actual is not None:
                st.session_state.orden_actual = None
                st.rerun()
                
    else: st.info("No hay órdenes registradas o no se encontraron coincidencias con los filtros.")
        
    st.divider()

    if st.session_state.orden_actual:
        orden = st.session_state.orden_actual
        
        st.subheader(f"Vista Previa: {orden['codigo_orden']}")
        col_info, col_finanzas = st.columns(2)
        with col_info:
            cliente_data = orden.get('clientes', {})
            nombre_cliente = cliente_data.get('nombre_completo', cliente_data.get('nombre', 'Cliente sin nombre registrado'))
            
            st.write(f"**Cliente:** {nombre_cliente}")
            st.write(f"**Estado:** {orden.get('estado', 'N/A')}")
            st.write(f"**Fecha Entrega:** {orden.get('fecha_entrega', 'N/A')}")
        with col_finanzas:
            st.write(f"**Total:** ${orden.get('total_estimado', 0)}")
            st.write(f"**Saldo:** ${orden.get('saldo_pendiente', 0)}")

        st.divider()
        
        st.markdown("### 🖨️ Acciones de Generación")
        col_pdf1, col_pdf2, col_pdf3 = st.columns(3)
        
        with col_pdf1:
            if st.button("📄 Generar Comprobante", use_container_width=True):
                pdf_bytes = generar_comprobante_cliente(orden)
                st.download_button(
                    label="⬇️ Descargar Comprobante",
                    data=pdf_bytes, file_name=f"Comprobante_{orden['codigo_orden']}.pdf",
                    mime="application/pdf", use_container_width=True
                )

        with col_pdf2:
            if st.button("🏭 Generar Producción", type="primary", use_container_width=True):
                pdf_bytes = generar_hoja_produccion(orden)
                st.download_button(
                    label="⬇️ Descargar Hoja de Producción",
                    data=pdf_bytes, file_name=f"Produccion_{orden['codigo_orden']}.pdf",
                    mime="application/pdf", use_container_width=True
                )
                
        with col_pdf3:
            # BOTÓN NUEVO DE ETIQUETAS
            if st.button("🏷️ Generar Etiquetas", type="secondary", use_container_width=True):
                pdf_bytes = generar_etiquetas(orden)
                st.download_button(
                    label="⬇️ Descargar Etiquetas",
                    data=pdf_bytes, file_name=f"Etiquetas_{orden['codigo_orden']}.pdf",
                    mime="application/pdf", use_container_width=True
                )
