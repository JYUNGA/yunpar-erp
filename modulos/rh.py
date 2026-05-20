import streamlit as st
import pandas as pd
from datetime import datetime, date
import pytz
import re
import io
import time
import os
import zipfile
from fpdf import FPDF

LOCAL_TZ = pytz.timezone('America/Guayaquil')
DIAS_TEXTO = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

# Diccionario traductor para mostrar nombres de meses legibles
MESES_ESP = {
    "01": "Enero", "02": "Febrero", "03": "Marzo", "04": "Abril", "05": "Mayo", "06": "Junio",
    "07": "Julio", "08": "Agosto", "09": "Septiembre", "10": "Octubre", "11": "Noviembre", "12": "Diciembre"
}

def traducir_periodo(mes_anio_txt):
    """Transforma '2025-10' en 'Octubre 2025'"""
    try:
        yyyy, mm = mes_anio_txt.split('-')
        return f"{MESES_ESP.get(mm, mm)} {yyyy}"
    except:
        return mes_anio_txt

def extraer_mes_anio(contenido_texto):
    match = re.search(r'Made Date:(\d{4}/\d{2})', contenido_texto)
    if match:
        return match.group(1).replace('/', '-')
    return f"{datetime.now().year}-{datetime.now().month:02d}"

def calcular_horas_netas(marcas_str, es_sabado):
    meta_diaria = 4.5 if es_sabado else 8.5
    
    if pd.isna(marcas_str) or str(marcas_str).strip() == "":
        return 0.0, 0.0, meta_diaria, True
    
    tiempos = re.findall(r'\d{2}:\d{2}', str(marcas_str))
    if len(tiempos) < 2:
        return 0.0, 0.0, meta_diaria, True
    
    t_objs = [datetime.strptime(t, "%H:%M") for t in tiempos]
    t_objs.sort()
    
    total_segundos = 0
    if len(t_objs) % 2 == 0:
        for i in range(0, len(t_objs), 2):
            total_segundos += (t_objs[i+1] - t_objs[i]).total_seconds()
    else:
        total_segundos += (t_objs[-1] - t_objs[0]).total_seconds()
        
    horas_totales = total_segundos / 3600.0
    
    horas_extras = max(0.0, horas_totales - meta_diaria)
    horas_descuento = max(0.0, meta_diaria - horas_totales)
    
    return round(horas_totales, 2), round(horas_extras, 2), round(horas_descuento, 2), (horas_totales == 0)

def render(supabase):
    if 'rol' not in st.session_state or st.session_state['rol'] not in ["GERENTE"]:
        st.error("🔒 Acceso denegado.")
        st.stop()

    # --- INICIALIZACIÓN DE VARIABLES DE ESTADO ---
    if 'rh_version' not in st.session_state: st.session_state['rh_version'] = 1
    if 'df_master_rh' not in st.session_state: st.session_state['df_master_rh'] = pd.DataFrame()
    if 'periodo_cargado' not in st.session_state: st.session_state['periodo_cargado'] = None
    if 'mes_anio_txt' not in st.session_state: st.session_state['mes_anio_txt'] = None
    if 'uploader_key' not in st.session_state: st.session_state['uploader_key'] = 0

    st.header("👥 Recursos Humanos y Nómina", divider="blue")
    
    tab_cfg, tab_auditoria, tab_pago = st.tabs(["⚙️ Configuración Personal", "📥 Subir Biométrico (Auditoría Interactiva)", "💸 Liquidación y Pagos"])

    # --- PESTAÑA 1: CONFIGURACIÓN ---
    with tab_cfg:
        col1, col2 = st.columns([1, 1.8])
        with col1:
            st.subheader("Registrar Colaborador")
            with st.form("form_rh_emp", clear_on_submit=True):
                nom = st.text_input("Nombre Completo").upper()
                bio_id = st.number_input("ID Biométrico (Código Reloj)", min_value=1, step=1)
                s_base = st.number_input("Sueldo Base ($)", value=485.00, min_value=0.0)
                if st.form_submit_button("Guardar Parámetros", type="primary"):
                    if nom:
                        try:
                            supabase.table('rh_empleados').insert({
                                "nombre_completo": nom, "biometrico_id": int(bio_id), "sueldo_base": float(s_base)
                            }).execute()
                            st.success("Configuración guardada exitosamente.")
                            time.sleep(0.5)
                            st.rerun()
                        except Exception as e: st.error(f"Error: {e}")
        with col2:
            st.subheader("Parámetros del Personal Activo")
            st.caption("💡 Doble clic sobre cualquier celda para corregir nombres o sueldos directamente.")
            emps = supabase.table('rh_empleados').select('*').eq('activo', True).order('id').execute().data
            if emps:
                df_emps = pd.DataFrame(emps)
                df_editor = st.data_editor(
                    df_emps[['id', 'biometrico_id', 'nombre_completo', 'sueldo_base']],
                    column_config={
                        "id": None, 
                        "biometrico_id": st.column_config.NumberColumn("ID Reloj", step=1),
                        "nombre_completo": st.column_config.TextColumn("Nombre en Sistema"),
                        "sueldo_base": st.column_config.NumberColumn("Sueldo Configurado ($)", format="%.2f")
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="director_emp_editor"
                )
                
                if st.button("💾 Guardar Cambios en Directorio", type="secondary", use_container_width=True):
                    with st.spinner("Actualizando parámetros..."):
                        try:
                            for _, r in df_editor.iterrows():
                                supabase.table('rh_empleados').update({
                                    "nombre_completo": str(r['nombre_completo']).upper(),
                                    "biometrico_id": int(r['biometrico_id']),
                                    "sueldo_base": float(r['sueldo_base'])
                                }).eq('id', int(r['id'])).execute()
                            st.success("¡Directorio actualizado!")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e: st.error(f"Error: {e}")
            else:
                st.info("No hay empleados registrados.")

    # --- PESTAÑA 2: AUDITORÍA INTERACTIVA ---
    with tab_auditoria:
        st.subheader("Bandeja de Corrección y Control de Marcas")
        archivo_bio = st.file_uploader("Cargar archivo de asistencia:", type=["csv", "xls", "xlsx"], key=f"bio_uploader_{st.session_state['uploader_key']}")
        
        if archivo_bio:
            try:
                nombre_archivo = archivo_bio.name.lower()
                
                if st.session_state['periodo_cargado'] != nombre_archivo:
                    with st.spinner("Analizando estructura de asistencia..."):
                        df_raw = pd.DataFrame()
                        mes_anio_txt = f"{datetime.now().year}-{datetime.now().month:02d}"
                        
                        if nombre_archivo.endswith('.xls') or nombre_archivo.endswith('.xlsx'):
                            excel_file = pd.ExcelFile(archivo_bio)
                            hoja_usar = 'Attendance Record' if 'Attendance Record' in excel_file.sheet_names else excel_file.sheet_names[0]
                            df_inspect = pd.read_excel(archivo_bio, sheet_name=hoja_usar, nrows=15, header=None)
                            header_idx = -1
                            for idx, row in df_inspect.iterrows():
                                if 'Employee ID' in str(row.values) and 'Name' in str(row.values):
                                    header_idx = idx; break
                            for row in df_inspect.values:
                                for cell in row:
                                    if isinstance(cell, str) and 'Made Date:' in cell:
                                        match = re.search(r'Made Date:(\d{4}/\d{2})', cell)
                                        if match: mes_anio_txt = match.group(1).replace('/', '-')
                            df_raw = pd.read_excel(archivo_bio, sheet_name=hoja_usar, skiprows=header_idx) if header_idx != -1 else pd.read_excel(archivo_bio, sheet_name=hoja_usar)
                            df_raw.columns = df_raw.columns.astype(str).str.strip()
                        else:
                            try: contenido = archivo_bio.getvalue().decode('utf-8')
                            except UnicodeDecodeError: contenido = archivo_bio.getvalue().decode('latin-1')
                            if contenido:
                                mes_anio_txt = extraer_mes_anio(contenido)
                                lineas = contenido.splitlines()
                                header_idx = next((i for i, l in enumerate(lineas) if 'Employee ID' in l and 'Name' in l), -1)
                                if header_idx != -1:
                                    df_raw = pd.read_csv(io.StringIO('\n'.join(lineas[header_idx:])), sep=',', engine='python', on_bad_lines='skip')
                                else:
                                    archivo_bio.seek(0)
                                    df_raw = pd.read_csv(archivo_bio, sep=',', engine='python', on_bad_lines='skip')
                                df_raw.columns = df_raw.columns.astype(str).str.strip()
                        
                        if df_raw.empty or 'Employee ID' not in df_raw.columns or 'Name' not in df_raw.columns:
                            st.error("🚨 La estructura de este archivo no coincide con las columnas esperadas.")
                            st.stop()
                            
                        cols_dias = [str(i) for i in range(1, 32) if str(i) in df_raw.columns]
                        df_melt = df_raw.melt(id_vars=['Employee ID', 'Name'], value_vars=cols_dias, var_name='Dia', value_name='Marcas')
                        df_melt = df_melt.dropna(subset=['Marcas'])
                        df_melt = df_melt[df_melt['Marcas'].astype(str).str.strip() != ""]
                        df_melt = df_melt[pd.to_numeric(df_melt['Employee ID'], errors='coerce').notnull()] 
                        
                        map_emps = {e['biometrico_id']: e['nombre_completo'] for e in emps} if emps else {}
                        lista_asistencia = []
                        
                        for _, row in df_melt.iterrows():
                            bio_id_file = int(float(row['Employee ID']))
                            if bio_id_file not in map_emps: continue 
                            
                            try:
                                yyyy, mm = mes_anio_txt.split('-')
                                fecha_real = date(int(yyyy), int(mm), int(row['Dia']))
                            except: fecha_real = date.today()
                            
                            if fecha_real.weekday() == 6: continue 
                            
                            es_sabado = fecha_real.weekday() == 5
                            h_tot, h_ext, h_des, es_falta = calcular_horas_netas(row['Marcas'], es_sabado)
                            nombre_dia = DIAS_TEXTO[fecha_real.weekday()]
                            meta_diaria = 4.5 if es_sabado else 8.5
                            
                            lista_asistencia.append({
                                "id_bio": bio_id_file,
                                "Empleado": map_emps[bio_id_file],
                                "Fecha_BD": str(fecha_real),
                                "Día de la Semana": f"{nombre_dia} {row['Dia']}",
                                "Marcaciones": str(row['Marcas']).replace('\n', ' | '),
                                "Horas Requeridas": float(meta_diaria),
                                "Horas Trabajadas": float(h_tot),
                                "Horas Extras": float(h_ext),
                                "Horas Atraso": float(h_des),
                                "¿Falta Injustificada?": bool(es_falta)
                            })
                        
                        st.session_state['df_master_rh'] = pd.DataFrame(lista_asistencia)
                        st.session_state['periodo_cargado'] = nombre_archivo
                        st.session_state['mes_anio_txt'] = mes_anio_txt
                        st.session_state['rh_version'] = 1

                df_master = st.session_state['df_master_rh']
                mes_anio_txt_seguro = st.session_state['mes_anio_txt']
                periodo_legible = traducir_periodo(mes_anio_txt_seguro)
                st.success(f"📅 Periodo de Trabajo Detectado: **{periodo_legible}**")
                
                if df_master.empty:
                    st.info("No hay datos para el personal configurado.")
                else:
                    st.markdown("#### 🛠️ Panel de Modificación por Empleado")
                    empleados_unicos = df_master['Empleado'].unique()
                    diccionario_editados = {}
                    
                    if st.button("🔄 APLICAR CAMBIOS Y RECALCULAR PANEL", type="secondary", use_container_width=True):
                        with st.spinner("Procesando fórmulas matemáticas..."):
                            for emp in empleados_unicos:
                                editor_key = f"editor_rh_{emp}_{st.session_state['rh_version']}"
                                if editor_key in st.session_state:
                                    cambios = st.session_state[editor_key].get("edited_rows", {})
                                    df_emp_indices = df_master[df_master['Empleado'] == emp].index.tolist()
                                    
                                    for local_idx_str, columnas in cambios.items():
                                        local_idx = int(local_idx_str)
                                        global_idx = df_emp_indices[local_idx]
                                        
                                        if "Horas Trabajadas" in columnas:
                                            nuevo_valor = float(columnas["Horas Trabajadas"])
                                            df_master.at[global_idx, "Horas Trabajadas"] = nuevo_valor
                                            
                                            meta = float(df_master.at[global_idx, "Horas Requeridas"])
                                            extras = max(0.0, nuevo_valor - meta)
                                            atrasos = max(0.0, meta - nuevo_valor)
                                            
                                            df_master.at[global_idx, "Horas Extras"] = round(extras, 2)
                                            df_master.at[global_idx, "Horas Atraso"] = round(atrasos, 2)
                                            df_master.at[global_idx, "¿Falta Injustificada?"] = (nuevo_valor == 0.0)
                            
                            st.session_state['df_master_rh'] = df_master
                            st.session_state['rh_version'] += 1
                            st.success("¡Operación completada! Todas las alertas y métricas se han actualizado.")
                            time.sleep(0.5)
                            st.rerun()

                    for emp in empleados_unicos:
                        df_emp_especifico = df_master[df_master['Empleado'] == emp].copy().reset_index(drop=True)
                        num_alertas = len(df_emp_especifico[df_emp_especifico['Horas Trabajadas'] == 0])
                        label_expander = f"👤 {emp} — ({num_alertas} Alertas/Marcas incompletas)"
                        
                        with st.expander(label_expander, expanded=(num_alertas > 0)):
                            editor_key = f"editor_rh_{emp}_{st.session_state['rh_version']}"
                            df_editado = st.data_editor(
                                df_emp_especifico[["Fecha_BD", "Día de la Semana", "Marcaciones", "Horas Requeridas", "Horas Trabajadas", "Horas Extras", "Horas Atraso", "¿Falta Injustificada?"]],
                                column_config={
                                    "Fecha_BD": None, 
                                    "Día de la Semana": st.column_config.TextColumn("Día/Fecha", disabled=True),
                                    "Marcaciones": st.column_config.TextColumn("Marcas Reloj (Incompletas)", disabled=True),
                                    "Horas Requeridas": st.column_config.NumberColumn("Debe Trabajar", format="%.2f", disabled=True),
                                    "Horas Trabajadas": st.column_config.NumberColumn("Horas Reales (Edita aquí)", format="%.2f", min_value=0.0, max_value=24.0),
                                    "Horas Extras": st.column_config.NumberColumn("Extras", format="%.2f", disabled=True),
                                    "Horas Atraso": st.column_config.NumberColumn("Atrasos", format="%.2f", disabled=True),
                                    "¿Falta Injustificada?": st.column_config.CheckboxColumn("Falta", disabled=True)
                                },
                                hide_index=True,
                                use_container_width=True,
                                key=editor_key
                            )
                            diccionario_editados[emp] = df_editado
                            
                            st.markdown("<br>", unsafe_allow_html=True)
                            c_m1, c_m2, c_m3, c_m4 = st.columns(4)
                            total_req = df_editado['Horas Requeridas'].sum()
                            total_calc = df_editado['Horas Trabajadas'].sum()
                            total_ext = df_editado['Horas Extras'].sum()
                            total_atr = df_editado['Horas Atraso'].sum()
                            
                            c_m1.metric("Horas Requeridas Mes", f"{total_req:.2f} hrs")
                            c_m2.metric("Horas Calculadas Fichero", f"{total_calc:.2f} hrs")
                            c_m3.metric("Horas Extras (Actualizado)", f"{total_ext:.2f} hrs", delta_color="normal")
                            c_m4.metric("Horas Atraso (Actualizado)", f"{total_atr:.2f} hrs", delta_color="inverse")
                    
                    st.write("---")
                    if st.button("💾 GUARDAR ASISTENCIA AUDITADA EN BASE DE DATOS", type="primary", use_container_width=True):
                        with st.spinner("Guardando datos depurados..."):
                            map_ids_internos = {e['nombre_completo']: e['id'] for e in emps}
                            payload_final = []
                            
                            for _, r in st.session_state['df_master_rh'].iterrows():
                                emp_id_interno = map_ids_internos.get(r['Empleado'])
                                if emp_id_interno:
                                    payload_final.append({
                                        "empleado_id": int(emp_id_interno),
                                        "fecha": str(r['Fecha_BD']),
                                        "horas_trabajadas": float(r['Horas Trabajadas']),
                                        "horas_extras": float(r['Horas Extras']),
                                        "horas_descuento": float(r['Horas Atraso']),
                                        "es_falta": bool(r['¿Falta Injustificada?']),
                                        "observaciones": str(r['Marcaciones']) 
                                    })
                            try:
                                supabase.table('rh_asistencia').upsert(payload_final, on_conflict="empleado_id, fecha").execute()
                                
                                st.session_state['df_master_rh'] = pd.DataFrame()
                                st.session_state['periodo_cargado'] = None
                                st.session_state['mes_anio_txt'] = None
                                st.session_state['uploader_key'] += 1 
                                
                                st.success("¡Todo el archivo mensual ha sido guardado y archivado con éxito! El panel se ha limpiado.")
                                time.sleep(1.2)
                                st.rerun()
                            except Exception as e: st.error(f"Error al archivar: {e}")
            except Exception as e: st.error(f"Error al procesar: {e}")
        else:
            st.info("A la espera de un fichero del reloj biométrico para iniciar la auditoría.")

    # --- PESTAÑA 3: LIQUIDACIÓN COMPLETA ---
    with tab_pago:
        st.subheader("Liquidación de Nómina y Enlace Contable")
        
        meses_disponibles = []
        try:
            res_meses = supabase.table('rh_asistencia').select('fecha').execute().data
            if res_meses:
                df_m = pd.DataFrame(res_meses)
                df_m['mes'] = df_m['fecha'].apply(lambda x: x[:7]) 
                meses_disponibles = sorted(df_m['mes'].unique().tolist(), reverse=True)
        except Exception as e:
            pass
            
        if not meses_disponibles:
            meses_disponibles = [datetime.now().strftime("%Y-%m")]
            
        mes_pago = st.selectbox("Seleccione el Mes con datos a Liquidar:", meses_disponibles)
        
        if st.button("🔄 Calcular Nómina del Mes Seleccionado", use_container_width=True):
            try:
                yyyy, mm = map(int, mes_pago.split('-'))
                inicio_mes = f"{mes_pago}-01"
                fin_mes = f"{yyyy}-{mm+1:02d}-01" if mm < 12 else f"{yyyy+1}-01-01"
                
                res_asist = supabase.table('rh_asistencia').select('*, observaciones, rh_empleados(nombre_completo, sueldo_base)').gte('fecha', inicio_mes).lt('fecha', fin_mes).execute().data
            except Exception as e:
                st.error(f"Error al estructurar fechas de consulta: {e}")
                res_asist = []

            if res_asist:
                df_asist = pd.DataFrame(res_asist)
                df_asist['Nombre'] = df_asist['rh_empleados'].apply(lambda x: x['nombre_completo'])
                df_asist['Sueldo Base'] = df_asist['rh_empleados'].apply(lambda x: float(x['sueldo_base']))
                
                resumen = df_asist.groupby(['empleado_id', 'Nombre', 'Sueldo Base']).agg({
                    'horas_trabajadas': 'sum', 'horas_extras': 'sum', 'horas_descuento': 'sum', 'es_falta': 'sum'
                }).reset_index()
                
                resumen['Valor Hora'] = resumen['Sueldo Base'] / 240.0
                resumen['Bono Extras ($)'] = resumen['horas_extras'] * (resumen['Valor Hora'] * 1.5)
                resumen['Descuentos ($)'] = resumen['horas_descuento'] * resumen['Valor Hora']
                resumen['Neto a Pagar ($)'] = resumen['Sueldo Base'] + resumen['Bono Extras ($)'] - resumen['Descuentos ($)']
                
                df_mostrar = resumen[['Nombre', 'Sueldo Base', 'horas_trabajadas', 'horas_extras', 'Bono Extras ($)', 'Descuentos ($)', 'Neto a Pagar ($)']]
                df_mostrar.columns = ['Empleado', 'Sueldo Base ($)', 'Horas Reales', 'Horas Extras', 'Bono Extras (+ $)', 'Descuentos Atraso (- $)', 'Neto Total a Recibir ($)']
                
                st.markdown(f"### 📋 Reporte de Pagos para el periodo: {traducir_periodo(mes_pago)}")
                
                st.dataframe(df_mostrar.style.format({
                    'Sueldo Base ($)': "{:.2f}", 'Horas Reales': "{:.2f}", 'Horas Extras': "{:.2f}",
                    'Bono Extras (+ $)': "{:.2f}", 'Descuentos Atraso (- $)': "{:.2f}", 'Neto Total a Recibir ($)': "{:.2f}"
                }), use_container_width=True, hide_index=True)
                
                # --- NUEVA LÓGICA: GENERACIÓN DE ARCHIVO ZIP CONFIDENCIAL ---
                st.write("")
                try:
                    zip_bytes = generar_zip_roles(resumen, df_asist, traducir_periodo(mes_pago))
                    st.download_button(
                        label="📦 Descargar Todos los Roles de Pago (Archivo ZIP de PDFs Separados)",
                        data=zip_bytes,
                        file_name=f"Roles_Pago_Yunpar_{mes_pago}.zip",
                        mime="application/zip",
                        use_container_width=True,
                        type="secondary"
                    )
                except Exception as e:
                    st.error(f"Error generando el archivo comprimido: {e}")
                
                st.write("---")
                if st.button("💰 Liquidar Mes y Enviar a Finanzas", type="primary", use_container_width=True):
                    with st.spinner("Registrando egresos individuales..."):
                        for _, row in resumen.iterrows():
                            supabase.table('rh_liquidaciones').insert({
                                "empleado_id": int(row['empleado_id']), "mes_anio": mes_pago, "total_pagado": float(row['Neto a Pagar ($)']), "enlazado_caja": True
                            }).execute()
                            
                            supabase.table('egresos').insert({
                                "fecha": str(datetime.now(LOCAL_TZ).date()),
                                "categoria": "Nómina / Sueldos",
                                "descripcion": f"Pago Nómina {mes_pago} - {row['Nombre']}",
                                "monto": float(row['Neto a Pagar ($)']),
                                "metodo_pago": "Transferencia"
                            }).execute()
                        st.success(f"¡Éxito! La nómina de {mes_pago} ha sido procesada de manera correcta.")
            else: st.info(f"No hay registros archivados para {mes_pago}.")
    
def generar_zip_roles(resumen_df, df_diario, mes_pago):
    """Genera un archivo ZIP en memoria conteniendo PDFs individuales por empleado"""
    zip_buffer = io.BytesIO()
    logo_path = "Logo_Yunpar.png"
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for _, row in resumen_df.iterrows():
            emp_id = row['empleado_id']
            nombre = row['Nombre']
            
            # Instancia un PDF único exclusivo para este trabajador
            pdf = FPDF()
            pdf.add_page()
            
            # --- ENCABEZADO ---
            if os.path.exists(logo_path):
                pdf.image(logo_path, 10, 10, 32)
                pdf.set_x(46)
                pdf.set_font("Arial", 'B', 16)
                pdf.cell(0, 10, "YUNPAR", ln=True, align='L')
                pdf.set_x(46)
                pdf.set_font("Arial", 'B', 11)
                pdf.cell(0, 6, "FABRICA DE UNIFORMES", ln=True, align='L')
            else:
                pdf.set_font("Arial", 'B', 16)
                pdf.cell(0, 10, "YUNPAR - FABRICA DE UNIFORMES", ln=True, align='C')
                
            pdf.set_font("Arial", 'I', 10)
            pdf.cell(0, 6, f"Comprobante Mensual de Liquidacion | Periodo: {mes_pago}", ln=True, align='R')
            pdf.ln(12)
            
            # --- DATOS DEL COLABORADOR ---
            pdf.set_font("Arial", 'B', 11)
            pdf.cell(40, 8, "Empleado / Operario:", border=1)
            pdf.set_font("Arial", '', 11)
            pdf.cell(0, 8, f" {nombre}", border=1, ln=True)
            
            pdf.set_font("Arial", 'B', 11)
            pdf.cell(40, 8, "Sueldo Nominal:", border=1)
            pdf.set_font("Arial", '', 11)
            pdf.cell(0, 8, f" ${row['Sueldo Base']:.2f}", border=1, ln=True)
            pdf.ln(6)
            
            # --- RESUMEN MONETARIO ---
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, "RUBROS ASOCIADOS AL PAGO", ln=True)
            pdf.set_font("Arial", '', 11)
            
            pdf.cell(120, 8, "Sueldo Base Mensual Acordado:")
            pdf.cell(0, 8, f"${row['Sueldo Base']:.2f}", align='R', ln=True)
            
            pdf.cell(120, 8, f"Bono por Horas Extras Acumuladas ({row['horas_extras']:.2f} hrs):")
            pdf.cell(0, 8, f"+ ${row['Bono Extras ($)']:.2f}", align='R', ln=True)
            
            pdf.set_text_color(200, 0, 0)
            pdf.cell(120, 8, f"Descuento por Atrasos e Inconsistencias ({row['horas_descuento']:.2f} hrs):")
            pdf.cell(0, 8, f"- ${row['Descuentos ($)']:.2f}", align='R', ln=True)
            pdf.set_text_color(0, 0, 0)
            
            # Total Neto Liquido
            pdf.set_font("Arial", 'B', 12)
            pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y())
            pdf.cell(120, 10, "NETO LIQUIDO A RECIBIR:")
            pdf.cell(0, 10, f"${row['Neto a Pagar ($)']:.2f}", align='R', ln=True)
            pdf.ln(8)
            
            # --- ANEXO DIARIO ---
            df_emp_diario = df_diario[df_diario['empleado_id'] == emp_id].sort_values(by='fecha')
            if not df_emp_diario.empty:
                pdf.set_font("Arial", 'B', 11)
                pdf.cell(0, 8, "ANEXO COMPLETO: Registro Diario de Asistencia y Tiempos", ln=True)
                
                pdf.set_font("Arial", 'B', 9)
                pdf.cell(24, 6, "Fecha", border=1, align='C')
                pdf.cell(64, 6, "Marcaciones Reales Reloj", border=1, align='C')
                pdf.cell(34, 6, "Horas Calculadas", border=1, align='C')
                pdf.cell(34, 6, "Sobretiempo (+)", border=1, align='C')
                pdf.cell(34, 6, "Descuento (-)", border=1, align='C', ln=True)
                
                pdf.set_font("Arial", '', 9)
                for _, d_row in df_emp_diario.iterrows():
                    pdf.cell(24, 6, str(d_row['fecha']), border=1, align='C')
                    marcas_reales = str(d_row.get('observaciones', '---'))
                    if marcas_reales == "None" or marcas_reales.strip() == "":
                        marcas_reales = "---"
                    
                    pdf.cell(64, 6, f" {marcas_reales}", border=1)
                    pdf.cell(34, 6, f"{d_row['horas_trabajadas']:.2f} hrs", border=1, align='C')
                    pdf.cell(34, 6, f"{d_row['horas_extras']:.2f} hrs", border=1, align='C')
                    pdf.cell(34, 6, f"{d_row['horas_descuento']:.2f} hrs", border=1, align='C', ln=True)
            
            # Firmas
            pdf.ln(25)
            pdf.set_font("Arial", '', 10)
            pdf.cell(95, 5, "___________________________", align='C')
            pdf.cell(95, 5, "___________________________", align='C', ln=True)
            pdf.cell(95, 5, "Firma Autorizada Gerencia", align='C')
            pdf.cell(95, 5, "Recibi Conforme Colaborador", align='C', ln=True)
            
            # Convierte el PDF a bytes e inyecta al archivo ZIP con un nombre limpio
            pdf_bytes = bytes(pdf.output())
            nombre_limpio = nombre.replace(" ", "_")
            zip_file.writestr(f"Rol_Pago_{nombre_limpio}_{mes_pago}.pdf", pdf_bytes)
            
    return zip_buffer.getvalue()