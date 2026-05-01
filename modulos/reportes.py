import streamlit as st
import pandas as pd
from fpdf import FPDF
from fpdf.fonts import FontFace 
from datetime import datetime
import io

# ==========================================
# 1. UTILIDADES Y FORMATEO
# ==========================================

def limpiar_texto_pdf(texto):
    """Elimina emojis y caracteres especiales no soportados por FPDF (Helvetica)"""
    if not texto: return ""
    # El ignore elimina cualquier símbolo que rompa la codificación latin-1 del PDF
    return str(texto).encode('latin-1', 'ignore').decode('latin-1')

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
                    # NUEVO: Traemos también el tipo_prenda
                    res_prod = supabase_client.table('productos_catalogo').select('descripcion, tipo_prenda').eq('id', item['producto_id']).execute()
                    if res_prod.data:
                        item['nombre_producto'] = res_prod.data[0]['descripcion']
                        item['tipo_prenda'] = res_prod.data[0].get('tipo_prenda', '')
                    else:
                        item['nombre_producto'] = item.get('familia_producto')
                        item['tipo_prenda'] = ''
                except: 
                    item['nombre_producto'] = item.get('familia_producto')
                    item['tipo_prenda'] = ''
            else: 
                item['nombre_producto'] = item.get('familia_producto')
                item['tipo_prenda'] = ''
                
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
        # Añadimos saldo_pendiente a la consulta principal
        query = supabase_client.table('ordenes').select('codigo_orden, estado, fecha_entrega, total_estimado, cliente_id, created_at, saldo_pendiente')
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
                "Estado": d.get('estado', 'N/A'),
                "Entrega": d.get('fecha_entrega'),
                "Total": f"${d.get('total_estimado', 0):.2f}",
                "Saldo_Num": float(d.get('saldo_pendiente', 0)) # Campo oculto que usaremos para la lógica
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

    ancho_etiqueta1 = 27; ancho_valor1 = 75; ancho_etiqueta2 = 31 # Aumentamos 5mm al ancho_valor1 para separar la columna 
    
    pdf.cell(ancho_etiqueta1, 6, "Cliente:", border=False); pdf.set_font("helvetica", "", 10)
    pdf.cell(ancho_valor1, 6, f"{nombre_cliente}", border=False); pdf.set_font("helvetica", "B", 10)
    pdf.cell(ancho_etiqueta2, 6, "Fecha Pedido:", border=False); pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 6, f"{formatear_fecha_es(orden.get('created_at'))}", border=False, new_x="LMARGIN", new_y="NEXT")

    # Fila 2: Teléfono y Fecha de Entrega
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(ancho_etiqueta1, 6, "Teléfono:", border=False); pdf.set_font("helvetica", "", 10)
    pdf.cell(ancho_valor1, 6, f"{telefono}", border=False); pdf.set_font("helvetica", "B", 10)
    pdf.cell(ancho_etiqueta2, 6, "Fecha Entrega:", border=False); pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 6, f"{formatear_fecha_es(orden.get('fecha_entrega'))}", border=False, new_x="LMARGIN", new_y="NEXT")

    # Fila 3: Correo (Nueva línea para evitar que se monte) y Diseñador
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(ancho_etiqueta1, 6, "Correo:", border=False); pdf.set_font("helvetica", "", 10)
    pdf.cell(ancho_valor1, 6, f"{correo}", border=False); pdf.set_font("helvetica", "B", 10)
    pdf.cell(ancho_etiqueta2, 6, "Diseñador:", border=False); pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 6, f"{disenador}", border=False, new_x="LMARGIN", new_y="NEXT")

    # Fila 4: Atendido por
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(ancho_etiqueta1, 6, "Atendido por:", border=False); pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 6, f"{creador}", border=False, new_x="LMARGIN", new_y="NEXT"); pdf.ln(6)

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
            
            precio = float(item.get('precio_aplicado', 0))
            if precio <= 0:
                row.cell("OBSEQUIO"); row.cell("$0.00")
            else:
                row.cell(f"${precio:.2f}"); row.cell(f"${item.get('cantidad_total', 0) * precio:.2f}")

    pdf.ln(2); pdf.set_font("helvetica", "B", 10) # Letra más pequeña y menos salto
    x_offset = 150 
    pdf.set_x(x_offset); pdf.cell(25, 5, "Total:", align="R"); pdf.cell(20, 5, f"${orden.get('total_estimado', 0):.2f}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(x_offset); pdf.cell(25, 5, "Abono:", align="R"); pdf.cell(20, 5, f"${orden.get('abono_inicial', 0):.2f}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(x_offset); pdf.cell(25, 5, "Saldo:", align="R"); pdf.set_text_color(200, 0, 0) 
    pdf.cell(20, 5, f"${orden.get('saldo_pendiente', 0):.2f}", align="R", new_x="LMARGIN", new_y="NEXT"); pdf.set_text_color(0, 0, 0) 
    
    pdf.ln(2) # Reducido de 10 a 2 para pegar la tabla de pagos hacia arriba
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
    
    necesita_nueva_hoja_anexo = True

    if url_imagen and pagos:
        pdf.set_font("helvetica", "B", 10)
        pdf.cell(0, 8, "Historial de Pagos y Notas Generales:", align="L", new_x="LMARGIN", new_y="NEXT")
        
        start_y = pdf.get_y()
        
        # 1. Dibujamos la tabla de pagos a la IZQUIERDA
        pdf.set_font("helvetica", "", 8)
        estilo_cabecera_pagos = FontFace(fill_color=(0, 51, 153), color=(255, 255, 255), emphasis="B")
        estilo_datos_pagos = FontFace(fill_color=(255, 255, 255), color=(0, 0, 0), emphasis="")
        
        with pdf.table(width=85, align="LEFT", col_widths=(20, 45, 20), text_align=("CENTER", "LEFT", "RIGHT")) as t_pagos:
            row = t_pagos.row(style=estilo_cabecera_pagos)
            for h in ["Fecha", "Banco/Método", "Monto"]: row.cell(h)
            for p in pagos:
                row = t_pagos.row(style=estilo_datos_pagos)
                f_pago = p.get('fecha_pago', '')
                if f_pago and len(f_pago) >= 10: f_pago = f"{f_pago[8:10]}/{f_pago[5:7]}/{f_pago[2:4]}"
                banco = p.get('banco_destino') or p.get('metodo_pago') or 'Efectivo'
                row.cell(f_pago); row.cell(str(banco)[:20]); row.cell(f"${float(p.get('monto', 0)):.2f}")
        
        y_after_table = pdf.get_y()
        
        # 2. Dibujamos las OBSERVACIONES a la DERECHA de la tabla
        pdf.set_xy(110, start_y)
        pdf.set_font("helvetica", "B", 9)
        pdf.cell(85, 6, "Observaciones de la Orden:", border=False)
        
        pdf.set_xy(110, start_y + 6)
        pdf.set_font("helvetica", "", 8)
        observaciones = str(orden.get('observaciones_generales') or 'Ninguna').strip()
        pdf.multi_cell(85, 4, observaciones)
        y_after_obs = pdf.get_y()
        
        # 3. Retomamos el flujo en el punto más bajo
        pdf.set_y(max(y_after_table, y_after_obs) + 4)
        
        # 4. LÓGICA INFALIBLE PARA LA IMAGEN
        pdf.set_font("helvetica", "B", 10)
        pdf.cell(0, 8, "Referencia de Diseño:", align="L", new_x="LMARGIN", new_y="NEXT")
        
        y_actual = pdf.get_y()
        espacio_restante = 282 - y_actual
        
        if espacio_restante >= 70:
            # Opción A: Cabe en la hoja 1
            try:
                # TRUCO MAESTRO: Al pasarle 'y=y_actual', obligamos a FPDF a anclar la imagen
                # como coordenada absoluta, impidiendo que decida saltar de hoja.
                # También limitamos el alto máximo a 90mm para que no se vea gigante.
                alto_imagen = min(espacio_restante - 5, 90)
                pdf.image(url_imagen, x="CENTER", y=y_actual, w=190, h=alto_imagen, keep_aspect_ratio=True)
            except:
                pdf.set_font("helvetica", "I", 9); pdf.cell(0, 10, "(Imagen no disponible)", align="C")
            necesita_nueva_hoja_anexo = True # La hoja 1 se llenó con la imagen, el anexo va a la hoja 2
        else:
            # Opción B: No cabe en la hoja 1, la mandamos a la hoja 2
            pdf.add_page()
            try:
                pdf.image(url_imagen, x="CENTER", w=190, h=110, keep_aspect_ratio=True)
                pdf.set_y(pdf.get_y() + 5)
            except:
                pass
            necesita_nueva_hoja_anexo = False # El anexo va en esta MISMA hoja 2, debajo de la imagen

    elif url_imagen and not pagos:
        pdf.set_font("helvetica", "B", 10)
        pdf.cell(0, 10, "Referencia de Diseño:", align="L", new_x="LMARGIN", new_y="NEXT")
        
        y_actual = pdf.get_y()
        espacio_restante = 282 - y_actual
        
        if espacio_restante >= 70:
            try: 
                # Hacemos el mismo anclaje de Y absoluto aquí
                alto_imagen = min(espacio_restante - 5, 90)
                pdf.image(url_imagen, x="CENTER", y=y_actual, w=190, h=alto_imagen, keep_aspect_ratio=True)
            except: pass
            necesita_nueva_hoja_anexo = True
        else:
            pdf.add_page()
            try: 
                pdf.image(url_imagen, x="CENTER", w=190, h=110, keep_aspect_ratio=True)
                pdf.set_y(pdf.get_y() + 5)
            except: pass
            necesita_nueva_hoja_anexo = False
            
        pdf.set_auto_page_break(auto=True, margin=15)
        
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
        necesita_nueva_hoja_anexo = True

    # --- ANEXO DE TÉRMINOS Y ESPECIFICACIONES ---
    if necesita_nueva_hoja_anexo:
        pdf.add_page()
    else:
        pdf.ln(5) # Un pequeño margen de separación visual si comparte hoja con la imagen
        
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
        especificaciones_crudas = item.get('especificaciones_producto', [])
        
        # AGRUPACIÓN DE IDÉNTICOS PARA AHORRAR ESPACIO
        agrupadas = {}
        for esp in especificaciones_crudas:
            key = (
                str(esp.get('talla_superior') or '').strip(),
                str(esp.get('talla_inferior') or '').strip(),
                str(esp.get('nombre_jugador') or '').strip(),
                str(esp.get('numero_dorsal') or '').strip(),
                str(esp.get('tipo_cuello_texto') or '').strip(),
                str(esp.get('talla_polines') or '').strip(),
                str(esp.get('observacion_individual') or '').strip(),
                bool(esp.get('es_arquero', False)) # Añadimos el booleano para no mezclar arqueros con jugadores
            )
            if key not in agrupadas:
                agrupadas[key] = {**esp, 'cant_fila': 1}
            else:
                agrupadas[key]['cant_fila'] += 1
        
        especificaciones = list(agrupadas.values())
        
        if familia in ['UNIFORME COMPLETO', 'PRENDA SUPERIOR']:
            especificaciones.sort(key=lambda x: (orden_talla(x.get('talla_superior')), orden_talla(x.get('talla_inferior'))))
        if familia == 'PANTALONETA':
            especificaciones.sort(key=lambda x: orden_talla(x.get('talla_inferior')))

        # Letra más pequeña (8) y unimos todo en una sola línea horizontal
        pdf.set_font("helvetica", "B", 8); pdf.set_fill_color(230, 230, 230)
        titulo_prod = f" PRODUCTO: {nombre_prod}   |   CANTIDAD: {item.get('cantidad_total', 0)}   |   TELA: {tela}"
        pdf.multi_cell(0, 5, titulo_prod, border=1, fill=True, align="L")

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
                cant = str(esp.get('cant_fila', 1)) # <--- REEMPLAZAMOS EL "1" FIJO POR EL VALOR CALCULADO DINÁMICAMENTE
                talla_s = str(esp.get('talla_superior') or '').strip() or '-'
                talla_i = str(esp.get('talla_inferior') or '').strip() or '-'
                nom = limpiar_texto_pdf(str(esp.get('nombre_jugador') or '').strip())
                num = limpiar_texto_pdf(str(esp.get('numero_dorsal') or '').strip())
                cuello = limpiar_texto_pdf(str(esp.get('tipo_cuello_texto') or '').strip())
                obs = limpiar_texto_pdf(str(esp.get('observacion_individual') or '').strip())
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
    
    # Dibujo Cliente
    pdf.set_y(start_firma_y - 8); pdf.set_x(25)
    pdf.set_font("times", "I", 14); pdf.set_text_color(0, 0, 100) # Simula firma en azul
    pdf.cell(60, 5, f"{nombre_cliente}", align="C")
    pdf.set_text_color(0, 0, 0) # Restaurar color
    pdf.set_y(start_firma_y); pdf.set_x(25)
    pdf.line(25, start_firma_y, 85, start_firma_y); pdf.set_x(25)
    pdf.set_font("helvetica", "B", 9)
    pdf.cell(60, 5, "Firma del Cliente", align="C", new_x="LMARGIN", new_y="NEXT"); pdf.set_x(25)
    pdf.set_font("helvetica", "", 8); pdf.cell(60, 5, f"C.I: ________________", align="C")

    # Dibujo Asesor
    pdf.set_y(start_firma_y - 8); pdf.set_x(125)
    pdf.set_font("times", "I", 14); pdf.set_text_color(0, 0, 100)
    pdf.cell(60, 5, f"{creador}", align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(start_firma_y); pdf.set_x(125)
    pdf.line(125, start_firma_y, 185, start_firma_y); pdf.set_x(125)
    pdf.set_font("helvetica", "B", 9); pdf.cell(60, 5, "Firma del Asesor / Vendedor", align="C", new_x="LMARGIN", new_y="NEXT")

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
    cli = orden.get('clientes', {})
    nombre_cliente = cli.get('nombre_completo', cli.get('nombre', 'Consumidor Final'))
    pdf.cell(0, 6, f"Diseñador: {disenador}  |  Asesor: {creador}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Cliente: {nombre_cliente}", new_x="LMARGIN", new_y="NEXT")
    
    if orden.get('alerta_cambios'):
        pdf.ln(2); pdf.set_font("helvetica", "B", 12); pdf.set_fill_color(255, 200, 200)
        pdf.cell(0, 10, " ¡ATENCIÓN: ESTA ORDEN HA TENIDO CAMBIOS RECIENTES!", fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # --- 2. CÁLCULO DEL RESUMEN GLOBAL DINÁMICO ---
    resumenes_dinamicos = {}
    resumen_polines = {}
    
    for item in items_taller:
        fam = str(item.get('familia_producto', '')).strip().upper() 
        tipo_prenda = str(item.get('tipo_prenda') or '').strip().upper()
        if not tipo_prenda: tipo_prenda = fam
        
        for esp in item.get('especificaciones_producto', []):
            t_sup = str(esp.get('talla_superior') or '').strip().upper()
            t_inf = str(esp.get('talla_inferior') or '').strip().upper()
            es_arq = bool(esp.get("es_arquero", False))
            
            # Conteo Superior Dinámico
            if fam in ['UNIFORME COMPLETO', 'PRENDA SUPERIOR'] and t_sup not in ['-', 'NONE', '']: 
                titulo_sup = f"{tipo_prenda} (SUPERIOR)" if fam == 'UNIFORME COMPLETO' else f"{tipo_prenda}"
                if es_arq: titulo_sup += " (ARQ)"
                if titulo_sup not in resumenes_dinamicos: resumenes_dinamicos[titulo_sup] = {}
                resumenes_dinamicos[titulo_sup][t_sup] = resumenes_dinamicos[titulo_sup].get(t_sup, 0) + 1
            
            # Conteo Inferior Dinámico
            if fam in ['UNIFORME COMPLETO', 'PANTALONETA'] and t_inf not in ['-', 'NONE', '']: 
                titulo_inf = f"{tipo_prenda}" if fam == 'PANTALONETA' else f"{tipo_prenda} (INFERIOR)"
                if es_arq: titulo_inf += " (ARQ)"
                if titulo_inf not in resumenes_dinamicos: resumenes_dinamicos[titulo_inf] = {}
                resumenes_dinamicos[titulo_inf][t_inf] = resumenes_dinamicos[titulo_inf].get(t_inf, 0) + 1
            
            # Conteo Polines
            if fam == 'UNIFORME COMPLETO':
                t_pol = str(esp.get('talla_polines') or '').strip().upper()
                if t_pol not in ['-', 'NONE', '']:
                    c_pol = str(esp.get('color_polines') or 'Sin Color').strip()
                    k = (t_pol, c_pol)
                    resumen_polines[k] = resumen_polines.get(k, 0) + 1

    # --- 3. IMAGEN MAXIMIZADA ---
    # MODIFICACIÓN: Mostrar ÚNICAMENTE el boceto inicial de la vendedora en producción
    boceto = str(orden.get('url_boceto_vendedora') or '').strip()
    
    if boceto and boceto.lower() not in ['none', 'null']:
        url_imagen = boceto
    else:
        url_imagen = None
    
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 8, "REFERENCIA VISUAL DE CORTE Y CONFECCIÓN", align="C", new_x="LMARGIN", new_y="NEXT")
    
    if url_imagen:
        try:
            # Reducimos h=100 para evitar que empuje las tablas a la siguiente hoja
            pdf.image(url_imagen, w=190, h=100, keep_aspect_ratio=True, x="CENTER") 
        except:
            pdf.set_font("helvetica", "I", 10)
            pdf.cell(0, 10, "(La imagen no pudo ser cargada)", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # --- 4. MOTOR DINÁMICO DE TABLAS DE RESUMEN FPDF ---
    if resumenes_dinamicos or resumen_polines:
        pdf.set_font("helvetica", "B", 12)
        pdf.cell(0, 8, "RESUMEN GLOBAL DE CORTE", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        
        start_y = pdf.get_y()
        max_y = start_y
        
        fill_cab = (150, 150, 150)
        fill_tot = (220, 220, 220)
        
        # 1. Empaquetar todas las tablas a dibujar
        tablas_a_dibujar = []
        for titulo, tallas_dict in resumenes_dinamicos.items():
            if tallas_dict: tablas_a_dibujar.append({"titulo": titulo, "datos": tallas_dict, "tipo": "normal"})
        if resumen_polines:
            tablas_a_dibujar.append({"titulo": "POLINES", "datos": resumen_polines, "tipo": "polin"})
            
        # 2. Coordenadas X para 4 tablas por fila (repartidas equitativamente)
        posiciones_x = [15, 60, 105, 150] 
        col_actual = 0
        y_actual = start_y
        
        # 3. Dibujar cada tabla iterativamente
        for tabla in tablas_a_dibujar:
            # Si pasamos de 4 columnas, bajamos de línea
            if col_actual >= 4: 
                col_actual = 0
                y_actual = max_y + 8 # Bajamos un poco respecto al final de la tabla más larga
                pdf.set_y(y_actual)
            
            x = posiciones_x[col_actual]
            pdf.set_xy(x, y_actual)
            
            # Prevención de salto de página
            if y_actual > 250:
                pdf.add_page()
                y_actual = pdf.get_y()
                max_y = y_actual
                pdf.set_xy(x, y_actual)
            
            # DIBUJAR TÍTULO (CORREGIDO: CÁLCULO DE LÍNEAS DINÁMICO)
            pdf.set_font("helvetica", "B", 8)
            ancho_tabla = 50 if tabla["tipo"] == "polin" else 40
            
            # Guardamos la posición Y de la fila para alinear cabeceras gris después
            y_base_fila = y_actual
            
            # 1. Obtenemos el texto del título sin recortar
            tit_completo = tabla["titulo"]
            
            # 2. Matemáticas: Calculamos cuánto espacio Y ocupa el título con multi_cell
            # 'h' es la altura de cada línea (3.5mm)
            altura_linea = 3.5
            pdf.set_xy(x, y_base_fila)
            pdf.multi_cell(ancho_tabla, altura_linea, tit_completo, align="C")
            
            # 3. Forzamos la Y de la cabecera gris:
            # Damos 9.5 mm para que las dos líneas entren perfectas sin chocar con lo gris
            pdf.set_xy(x, y_base_fila + 9.5)
            
            # DIBUJAR CABECERA (CON COLOR DINÁMICO)
            if "(INFERIOR)" in tabla["titulo"]:
                pdf.set_fill_color(80, 130, 180) # Azul acero para diferenciar prendas inferiores
            elif tabla["tipo"] == "polin":
                pdf.set_fill_color(100, 100, 100) # Gris oscuro para polines
            else:
                pdf.set_fill_color(*fill_cab) # Gris original para superiores
                
            pdf.set_text_color(255, 255, 255)
            
            if tabla["tipo"] == "normal":
                pdf.cell(20, 6, "Talla", border=1, align="C", fill=True)
                pdf.cell(20, 6, "Cant", border=1, align="C", fill=True, new_x="LMARGIN", new_y="NEXT")
            else:
                pdf.cell(15, 6, "Talla", border=1, align="C", fill=True)
                pdf.cell(20, 6, "Color", border=1, align="C", fill=True)
                pdf.cell(15, 6, "Cant", border=1, align="C", fill=True, new_x="LMARGIN", new_y="NEXT")
                
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("helvetica", "", 8)
                        
            # DIBUJAR DATOS Y FILAS
            tot_cant = 0
            if tabla["tipo"] == "normal":
                datos_ord = sorted(tabla["datos"].items(), key=lambda x: orden_talla(x[0]))
                for t, cant in datos_ord:
                    pdf.set_x(x)
                    pdf.cell(20, 6, str(t), border=1, align="C")
                    pdf.cell(20, 6, str(cant), border=1, align="C", new_x="LMARGIN", new_y="NEXT")
                    tot_cant += cant
            else:
                datos_ord = sorted(tabla["datos"].items(), key=lambda x: (orden_talla(x[0][0]), x[0][1]))
                for (t, c), cant in datos_ord:
                    pdf.set_x(x)
                    pdf.cell(15, 6, str(t), border=1, align="C")
                    color_str = str(c)[:10] + "." if len(str(c)) > 10 else str(c)
                    pdf.cell(20, 6, color_str, border=1, align="C")
                    pdf.cell(15, 6, str(cant), border=1, align="C", new_x="LMARGIN", new_y="NEXT")
                    tot_cant += cant
                    
            # DIBUJAR FILA TOTAL (CON COLOR DINÁMICO)
            pdf.set_x(x)
            pdf.set_font("helvetica", "B", 8)
            
            if "(INFERIOR)" in tabla["titulo"]:
                pdf.set_fill_color(176, 196, 222) # Azul claro para la fila total inferior
            else:
                pdf.set_fill_color(*fill_tot) # Gris original para las demás

            if tabla["tipo"] == "normal":
                pdf.cell(20, 6, "TOTAL", border=1, align="C", fill=True)
                pdf.cell(20, 6, str(tot_cant), border=1, align="C", fill=True, new_x="LMARGIN", new_y="NEXT")
            else:
                pdf.cell(35, 6, "TOTAL", border=1, align="C", fill=True)
                pdf.cell(15, 6, str(tot_cant), border=1, align="C", fill=True, new_x="LMARGIN", new_y="NEXT")
                
            # Registrar el punto más bajo al que llegó esta tabla
            max_y = max(max_y, pdf.get_y())
            col_actual += 1

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
    
    # NUEVO ESTILO: Resaltado amarillo soft para arqueros (fill amarillo, texto negro)
    estilo_datos_arquero = FontFace(fill_color=(255, 255, 102), color=(0, 0, 0), emphasis="") 

    for item in items_taller:
        familia = item.get('familia_producto', 'GENERICO').upper()
        nombre_prod = str(item.get('nombre_producto', familia)).replace('│', '|').replace('—', '-')
        especificaciones_crudas = item.get('especificaciones_producto', [])
        tela = item.get('nombre_tela', 'Estándar') 
        
        # AGRUPACIÓN DE IDÉNTICOS PARA AHORRAR ESPACIO
        agrupadas = {}
        for esp in especificaciones_crudas:
            key = (
                str(esp.get('talla_superior') or '').strip(),
                str(esp.get('talla_inferior') or '').strip(),
                str(esp.get('nombre_jugador') or '').strip(),
                str(esp.get('numero_dorsal') or '').strip(),
                str(esp.get('tipo_cuello_texto') or '').strip(),
                str(esp.get('talla_polines') or '').strip(),
                str(esp.get('observacion_individual') or '').strip()
            )
            if key not in agrupadas:
                agrupadas[key] = {**esp, 'cant_fila': 1}
            else:
                agrupadas[key]['cant_fila'] += 1
        
        especificaciones = list(agrupadas.values())
        
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

        pdf.set_font("helvetica", "", 8) # Letra más pequeña para ahorrar hojas
        tiene_polines = any(bool(esp.get('talla_polines')) for esp in especificaciones) if familia == 'UNIFORME COMPLETO' else False

        # Incluimos columna "C." (Cantidad)
        if familia == 'UNIFORME COMPLETO' and tiene_polines:
            cols = (10, 15, 15, 50, 15, 30, 20, 35) 
            headers = ["C.", "T. Sup", "T. Inf", "Nombre / Ref.", "Num", "Cuello", "Polín", "Obs"]
        elif familia in ['UNIFORME COMPLETO', 'PRENDA SUPERIOR']:
            cols = (10, 20, 20, 55, 15, 30, 40)
            headers = ["C.", "T. Sup", "T. Inf", "Nombre / Ref.", "Num", "Cuello", "Observación"] if familia == 'UNIFORME COMPLETO' else ["C.", "T. Sup", "-", "Nombre / Ref.", "Num", "Cuello", "Observación"]
        elif familia == 'PANTALONETA':
            cols = (15, 25, 25, 125); headers = ["C.", "Talla Inf.", "Num", "Observación"]
        elif familia == 'IMPRESION':
            cols = (10, 30, 30, 40, 80); headers = ["C.", "Ancho (m)", "Largo (m)", "Acabado", "Obs / Calandrado"]
        else:
            cols = (15, 50, 125); headers = ["C.", "Acabado", "Observación"]

        with pdf.table(col_widths=cols, text_align=("CENTER", "CENTER", "CENTER", "LEFT", "CENTER", "LEFT", "CENTER", "LEFT") if tiene_polines and familia == 'UNIFORME COMPLETO' else ("CENTER", "CENTER", "CENTER", "LEFT", "CENTER", "LEFT", "LEFT"), cell_fill_mode="ROWS") as table:
            row = table.row(style=estilo_cabecera_taller)
            for h in headers: row.cell(h)
                
            for esp in especificaciones:
                # LÓGICA CONDICIONAL REAL: Leer el campo booleano 'es_arquero' de la BD
                es_arquero_bd = esp.get('es_arquero', False)
                
                # Opcional: Mantenemos la búsqueda en texto por si alguna vez lo escriben en las observaciones y olvidan marcar el check
                obs_limpia = str(esp.get('observacion_individual') or '').strip().upper()
                
                if es_arquero_bd or "ARQUERO" in obs_limpia:
                    estilo_fila_actual = estilo_datos_arquero
                else:
                    estilo_fila_actual = estilo_datos_taller
                
                # Aplicamos el estilo condicional a la fila entera
                row = table.row(style=estilo_fila_actual)
                c_fila = str(esp.get('cant_fila', 1))
                
                nom_limpio = limpiar_texto_pdf(str(esp.get('nombre_jugador') or '').strip())
                num_limpio = limpiar_texto_pdf(str(esp.get('numero_dorsal') or '').strip())
                cuello_limpio = limpiar_texto_pdf(str(esp.get('tipo_cuello_texto') or '').strip())
                obs_limpia_txt = limpiar_texto_pdf(str(esp.get('observacion_individual') or '').strip())
                
                if familia == 'UNIFORME COMPLETO':
                    row.cell(c_fila)
                    row.cell(str(esp.get('talla_superior') or '-').strip() or '-'); row.cell(str(esp.get('talla_inferior') or '-').strip() or '-')
                    row.cell(nom_limpio); row.cell(num_limpio)
                    row.cell(cuello_limpio)
                    if tiene_polines: row.cell(str(esp.get('talla_polines') or '-').strip() or '-')
                    row.cell(obs_limpia_txt)
                elif familia == 'PRENDA SUPERIOR':
                    row.cell(c_fila)
                    row.cell(str(esp.get('talla_superior') or '-').strip() or '-'); row.cell("-")
                    row.cell(nom_limpio); row.cell(num_limpio)
                    row.cell(cuello_limpio); row.cell(obs_limpia_txt)
                elif familia == 'PANTALONETA':
                    row.cell(c_fila)
                    row.cell(str(esp.get('talla_inferior') or '-').strip() or '-'); row.cell(num_limpio)
                    row.cell(obs_limpia_txt)
                elif familia == 'IMPRESION':
                    row.cell(c_fila)
                    ancho_val = esp.get('ancho_cm')
                    alto_val = esp.get('alto_cm')
                    row.cell(f"{float(ancho_val):.2f} m" if ancho_val else "-")
                    row.cell(f"{float(alto_val):.2f} m" if alto_val else "-")
                    row.cell(limpiar_texto_pdf(str(esp.get('acabado') or '').strip())); row.cell(obs_limpia_txt)
                else:
                    row.cell(c_fila); row.cell(limpiar_texto_pdf(str(esp.get('acabado') or '').strip())); row.cell(obs_limpia_txt)
        pdf.ln(5)

    # --- 6. OBSERVACIONES GENERALES DE LA ORDEN ---
    observaciones = limpiar_texto_pdf(str(orden.get('observaciones_generales') or '').strip())
    if observaciones and observaciones.lower() not in ['none', 'null', '', 'ninguna']:
        # Evaluamos si hay espacio suficiente al final de la hoja para que no quede cortado el cuadro
        if pdf.get_y() > 240:
            pdf.add_page()
        else:
            pdf.ln(5)
            
        # Dibujamos un cuadro llamativo para que el taller lo lea obligatoriamente
        pdf.set_font("helvetica", "B", 12)
        pdf.set_fill_color(255, 230, 150) # Un fondo amarillo cálido para llamar la atención
        pdf.cell(0, 8, " NOTAS Y OBSERVACIONES GENERALES PARA PRODUCCIÓN", border=1, fill=True, align="L", new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_font("helvetica", "B", 11) # Texto en negrita
        # multi_cell permite que el texto baje de línea automáticamente si es muy largo
        pdf.multi_cell(0, 8, f" {observaciones}", border=1, align="L")
        pdf.ln(5)

    return bytes(pdf.output())


# ==========================================
# MÓDULO NUEVO: GENERADOR DE ETIQUETAS DE EMPAQUE (MODO LOTE)
# ==========================================
def extraer_datos_etiquetas(ordenes):
    """Extrae y cuenta las etiquetas válidas de una o varias órdenes."""
    datos_completos = []
    resumen_por_orden = {}
    
    def es_talla_valida(t):
        if not t: return False
        t_str = str(t).strip().upper()
        if t_str in ['', '-', 'NONE', 'NULL', 'N/A', 'NAN', '0']: return False
        return True

    for orden in ordenes:
        cod_orden = orden.get('codigo_orden', 'SIN-CODIGO')
        etiquetas_orden = []
        
        for item in orden.get('items', []):
            fam = str(item.get('familia_producto', '')).strip().upper()
            if fam == 'UNIFORME COMPLETO':
                for esp in item.get('especificaciones_producto', []):
                    talla_s = esp.get('talla_superior')
                    talla_i = esp.get('talla_inferior')
                    
                    if not (es_talla_valida(talla_s) and es_talla_valida(talla_i)):
                        continue 
                    
                    t_sup_str = str(talla_s).strip().upper()
                    t_inf_str = str(talla_i).strip().upper()
                    
                    talla = f"{t_sup_str}/{t_inf_str}" if t_sup_str != t_inf_str else t_sup_str 
                    numero = str(esp.get('numero_dorsal') or '').strip()
                    nombre = str(esp.get('nombre_jugador') or '').strip()
                    
                    if talla or numero or nombre:
                        etiquetas_orden.append({
                            'talla': talla,
                            'numero': numero,
                            'nombre': nombre,
                            'codigo': cod_orden # <-- Guardamos el código de orden aquí
                        })
                        
        if etiquetas_orden:
            datos_completos.extend(etiquetas_orden)
            resumen_por_orden[cod_orden] = len(etiquetas_orden)
            
    return datos_completos, resumen_por_orden

def generar_etiquetas_pdf(datos_etiquetas):
    """Genera el PDF físico a partir de una lista plana de datos de etiquetas."""
    if not datos_etiquetas: return None
    
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=False)
    
    PASO_X = 98.0  
    PASO_Y = 70.0  
    ORIGEN_X = 0   
    ORIGEN_Y = 0   
    OFFSET_X_TALLA  = 29.0   
    OFFSET_Y_TALLA  = 40.0   
    OFFSET_X_NUMERO = 75.0   
    OFFSET_Y_NUMERO = 40.0   
    OFFSET_X_NOMBRE = 38.0   
    OFFSET_Y_NOMBRE = 52.0
    # Nueva coordenada para el código de orden (esquina inferior derecha)
    OFFSET_X_CODIGO = 65.0   
    OFFSET_Y_CODIGO = 62.0   
    TAMANO_FUENTE = 14

    for i, data in enumerate(datos_etiquetas):
        if i % 9 == 0:
            pdf.add_page()
            try:
                pdf.image("ETIQUETAS-UNIFORMES.png", x=0, y=0, w=297, h=210)
            except Exception:
                pass 

        posicion_en_hoja = i % 9
        columna = posicion_en_hoja % 3   
        fila = posicion_en_hoja // 3     
        
        base_x = ORIGEN_X + (columna * PASO_X)
        base_y = ORIGEN_Y + (fila * PASO_Y)
        
        pdf.set_font("helvetica", "B", TAMANO_FUENTE)
        
        if data['talla']: pdf.text(x=base_x + OFFSET_X_TALLA, y=base_y + OFFSET_Y_TALLA, txt=limpiar_texto_pdf(data['talla']))
        if data['numero']: pdf.text(x=base_x + OFFSET_X_NUMERO, y=base_y + OFFSET_Y_NUMERO, txt=limpiar_texto_pdf(data['numero']))
        if data['nombre']: pdf.text(x=base_x + OFFSET_X_NOMBRE, y=base_y + OFFSET_Y_NOMBRE, txt=limpiar_texto_pdf(data['nombre']))
        
        # Dibujamos el código de la orden (Arriba del número, fondo azul, letra blanca)
        if data.get('codigo'):
            pdf.set_fill_color(0, 80, 160) 
            pdf.set_text_color(255, 255, 255) 
            pdf.set_font("helvetica", "B", 11) # Un punto menos para que encaje elegante en el nuevo ancho
            
            # Ajuste de coordenadas: Movimos X a 62 para centrarlo, y reducimos el ancho (w) de 38 a 28
            pdf.set_xy(base_x + 62, base_y + 24)
            pdf.cell(w=28, h=7, txt=data['codigo'], border=0, align="C", fill=True)
            
            pdf.set_text_color(0, 0, 0)

    return bytes(pdf.output())


# ==========================================
# 5. INTERFAZ STREAMLIT
# ==========================================
def render_modulo_reportes(supabase_client):
    st.header("🖨️ Módulo de Reportes y Producción")

    if 'ordenes_actuales' not in st.session_state:
        st.session_state.ordenes_actuales = []
    if 'ultima_seleccion' not in st.session_state:
        st.session_state.ultima_seleccion = {"evt1": [], "evt2": [], "evt3": []}

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
        df_todas = pd.DataFrame(st.session_state.lista_ordenes)
        
        # --- CORRECCIÓN DE CACHÉ: Si no existe Saldo_Num, forzamos la recarga ---
        if "Saldo_Num" not in df_todas.columns:
            with st.spinner("Actualizando estructura de datos..."):
                # Forzamos a que traiga los datos frescos con la nueva estructura
                st.session_state.lista_ordenes = buscar_lista_ordenes(supabase_client)
                df_todas = pd.DataFrame(st.session_state.lista_ordenes)
                
        # Verificamos de nuevo por seguridad
        if "Saldo_Num" not in df_todas.columns:
             # Si por alguna razón extrema sigue sin existir, la creamos con valor 1 para que no crashee
             df_todas["Saldo_Num"] = 1.0
        
        # --- 1. LÓGICA DE DIVISION DE GRUPOS ---
        # GRUPO 3 (Entregadas): Saldo es cero o menor
        df_pagadas = df_todas[df_todas["Saldo_Num"] <= 0].copy()
        
        # GRUPO 1 (Nuevas): Saldo > 0 Y Estado es PENDIENTE DISEÑO o EN DISEÑO
        estados_nuevas = ["PENDIENTE DISEÑO", "EN DISEÑO"]
        
        # OJO: Validamos que la columna 'Estado' exista y no tenga nulos para evitar errores con .str.upper()
        if "Estado" in df_todas.columns:
            df_todas["Estado"] = df_todas["Estado"].fillna("N/A")
            df_nuevas = df_todas[(df_todas["Saldo_Num"] > 0) & (df_todas["Estado"].str.upper().isin(estados_nuevas))].copy()
            df_proceso = df_todas[(df_todas["Saldo_Num"] > 0) & (~df_todas["Estado"].str.upper().isin(estados_nuevas))].copy()
        else:
            # Plan B si no hay estado
            df_nuevas = df_todas[df_todas["Saldo_Num"] > 0].copy()
            df_proceso = pd.DataFrame(columns=df_todas.columns)
        
        # GRUPO 2 (En Proceso): Saldo > 0 Y Estado ya fue tomado por alguien
        df_proceso = df_todas[(df_todas["Saldo_Num"] > 0) & (~df_todas["Estado"].str.upper().isin(estados_nuevas))].copy()
        
        # Quitamos la columna oculta "Saldo_Num" para que no estorbe visualmente al usuario
        df_nuevas = df_nuevas.drop(columns=["Saldo_Num"])
        df_proceso = df_proceso.drop(columns=["Saldo_Num"])
        df_pagadas = df_pagadas.drop(columns=["Saldo_Num"])

        st.caption("📌 **Navega por las pestañas y selecciona cualquier orden para ver su detalle y generar PDFs:**")
        
        # --- 2. RENDER DE PESTAÑAS (TABS) ---
        tab1, tab2, tab3 = st.tabs([
            f"🆕 Nuevas ({len(df_nuevas)})", 
            f"⚙️ En Proceso ({len(df_proceso)})", 
            f"✅ Entregadas / Pagadas ({len(df_pagadas)})"
        ])
        
        with tab1:
            evt1 = st.dataframe(df_nuevas, width="stretch", hide_index=True, on_select="rerun", selection_mode="multi-row", key="evt_nuevas")
        with tab2:
            evt2 = st.dataframe(df_proceso, width="stretch", hide_index=True, on_select="rerun", selection_mode="multi-row", key="evt_proceso")
        with tab3:
            evt3 = st.dataframe(df_pagadas, width="stretch", hide_index=True, on_select="rerun", selection_mode="multi-row", key="evt_pagadas")
            
        # --- 3. LÓGICA DE SELECCIÓN GLOBAL (MULTIPLE MODO LOTE) ---
        codigos_seleccionados = []
        
        actual_evt1 = evt1.selection.rows
        actual_evt2 = evt2.selection.rows
        actual_evt3 = evt3.selection.rows
        
        if actual_evt1 != st.session_state.ultima_seleccion["evt1"]:
            codigos_seleccionados = df_nuevas.iloc[actual_evt1]["Código"].tolist() if len(actual_evt1) > 0 else []
            st.session_state.ultima_seleccion["evt1"] = actual_evt1
        elif actual_evt2 != st.session_state.ultima_seleccion["evt2"]:
            codigos_seleccionados = df_proceso.iloc[actual_evt2]["Código"].tolist() if len(actual_evt2) > 0 else []
            st.session_state.ultima_seleccion["evt2"] = actual_evt2
        elif actual_evt3 != st.session_state.ultima_seleccion["evt3"]:
            codigos_seleccionados = df_pagadas.iloc[actual_evt3]["Código"].tolist() if len(actual_evt3) > 0 else []
            st.session_state.ultima_seleccion["evt3"] = actual_evt3
        else:
            if len(actual_evt1) > 0: codigos_seleccionados = df_nuevas.iloc[actual_evt1]["Código"].tolist()
            elif len(actual_evt2) > 0: codigos_seleccionados = df_proceso.iloc[actual_evt2]["Código"].tolist()
            elif len(actual_evt3) > 0: codigos_seleccionados = df_pagadas.iloc[actual_evt3]["Código"].tolist()

        if codigos_seleccionados:
            codigos_en_memoria = [o.get('codigo_orden') for o in st.session_state.ordenes_actuales]
            if set(codigos_seleccionados) != set(codigos_en_memoria):
                # SOLUCIÓN: Eliminamos el st.spinner(). Al no haber elementos visuales 
                # apareciendo y desapareciendo de golpe, React ya no perderá el hilo.
                datos_cargados = []
                for cod in codigos_seleccionados:
                    datos = obtener_datos_orden(supabase_client, cod)
                    if datos: datos_cargados.append(datos)
                st.session_state.ordenes_actuales = datos_cargados
        else:
            if st.session_state.ordenes_actuales:
                st.session_state.ordenes_actuales = []
                
    else: 
        st.info("No hay órdenes registradas o no se encontraron coincidencias con los filtros.")
        
    st.divider()

    # ANCLA VISUAL DEFINITIVA: st.empty() obliga a React a destruir y recrear el bloque limpio
    espacio_detalle = st.empty()
    
    with espacio_detalle.container():
        if st.session_state.ordenes_actuales:
            # --- EXTRAEMOS LOS DATOS DE ETIQUETAS GLOBALES ---
            datos_etiquetas, resumen_ordenes = extraer_datos_etiquetas(st.session_state.ordenes_actuales)
            total_etiq = len(datos_etiquetas)
            hojas = (total_etiq + 8) // 9
            vacios = (hojas * 9) - total_etiq

            if len(st.session_state.ordenes_actuales) == 1:
                orden = st.session_state.ordenes_actuales[0]
                cod = orden['codigo_orden']
                st.subheader(f"Vista Previa: {cod}")
                
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
                
                if total_etiq > 0:
                    st.info(f"🏷️ **Resumen de Etiquetas:** {total_etiq} etiquetas ocuparán {hojas} hoja(s) | ⬜ {vacios} espacios vacíos al final.")
                
                st.markdown("### 🖨️ Acciones de Generación")
                col_pdf1, col_pdf2, col_pdf3 = st.columns(3)
                
                # LA SOLUCIÓN: Usar variables de estado (session_state) para NO anidar botones
                with col_pdf1:
                    if st.session_state.get('rol') != 'IMPRESION':
                        if st.button("📄 Generar Comprobante", width="stretch", key=f"btn_comp_{cod}"):
                            with st.spinner("Generando..."):
                                st.session_state[f"pdf_comp_{cod}"] = generar_comprobante_cliente(orden)
                        if f"pdf_comp_{cod}" in st.session_state:
                            st.download_button(label="⬇️ Descargar Comprobante", data=st.session_state[f"pdf_comp_{cod}"], file_name=f"Comprobante_{cod}.pdf", mime="application/pdf", width="stretch", key=f"dl_comp_{cod}")
                    else:
                        st.info("🔒 Comprobantes exclusivos")

                with col_pdf2:
                    if st.button("🏭 Generar Producción", type="primary", width="stretch", key=f"btn_prod_{cod}"):
                        with st.spinner("Generando..."):
                            st.session_state[f"pdf_prod_{cod}"] = generar_hoja_produccion(orden)
                    if f"pdf_prod_{cod}" in st.session_state:
                        st.download_button(label="⬇️ Descargar Producción", data=st.session_state[f"pdf_prod_{cod}"], file_name=f"Produccion_{cod}.pdf", mime="application/pdf", width="stretch", key=f"dl_prod_{cod}")
                        
                with col_pdf3:
                    if total_etiq > 0:
                        # Las etiquetas locales se generan tan rápido que ponemos el botón de descarga directamente
                        pdf_etiq = generar_etiquetas_pdf(datos_etiquetas)
                        st.download_button(label="🏷️ Descargar Etiquetas", data=pdf_etiq, file_name=f"Etiquetas_{cod}.pdf", mime="application/pdf", type="secondary", width="stretch", key=f"dl_etiq_{cod}")
                    else:
                        st.warning("⚠️ Sin uniformes para etiquetar.")
                        
            else:
                # --- MODO LOTE (VARIAS ÓRDENES) ---
                st.subheader(f"📦 Modo Lote: {len(st.session_state.ordenes_actuales)} órdenes seleccionadas")
                
                if total_etiq > 0:
                    col_res1, col_res2 = st.columns([2, 1])
                    with col_res1:
                        st.success(f"**Total a Imprimir:** {total_etiq} etiquetas ocuparán {hojas} hoja(s).\n\n**Espacios vacíos al final (retazos salvados):** {vacios}")
                        desglose = " | ".join([f"{cod}: {cant}" for cod, cant in resumen_ordenes.items()])
                        st.caption(f"Desglose por orden: {desglose}")
                        
                    with col_res2:
                        st.markdown("<br>", unsafe_allow_html=True)
                        # SOLUCIÓN LOTE: El motor FPDF local es súper rápido, armamos el botón directo. Cero errores.
                        pdf_lote = generar_etiquetas_pdf(datos_etiquetas)
                        st.download_button(
                            label="⬇️ Descargar Lote de Etiquetas", 
                            data=pdf_lote, 
                            file_name=f"Lote_Etiquetas_{len(st.session_state.ordenes_actuales)}_ordenes.pdf", 
                            mime="application/pdf", 
                            type="primary", 
                            width="stretch",
                            key="dl_lote_global"
                        )
                else:
                     st.warning("⚠️ Ninguna de las órdenes seleccionadas contiene uniformes válidos para etiquetar.")