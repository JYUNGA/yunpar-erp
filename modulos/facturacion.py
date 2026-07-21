import streamlit as st
import pandas as pd
from datetime import datetime
import time

# Reutilizamos tu excelente extractor de datos del módulo de reportes
from modulos.reportes import obtener_datos_orden

def render(supabase):
    st.header("🧾 Control de Facturación", divider="blue")
    st.info("Módulo puente para extraer datos de órdenes y vincularlas a tus facturas electrónicas.")

    tab1, tab2 = st.tabs(["⏳ Pendientes de Facturar", "✅ Historial de Facturadas"])

    # ==============================================================================
    # TAB 1: BANDEJA DE PENDIENTES
    # ==============================================================================
    with tab1:
        st.subheader("Órdenes Listas para Facturar")
        
        # [Seguro]: Inyectamos los controles de búsqueda con llaves (keys) únicas para no chocar con la Tab 2.
        col_p1, col_p2, col_p3 = st.columns([1.5, 1.5, 3])
        # [Suposición]: Para pendientes, retrocedemos al inicio del año por defecto para capturar rezagadas
        f_inicio_pend = col_p1.date_input("Desde", value=datetime.today().replace(month=1, day=1), key="pend_f_ini")
        f_fin_pend = col_p2.date_input("Hasta", value=datetime.today(), key="pend_f_fin")
        txt_bus_pend = col_p3.text_input("🔍 Buscar", placeholder="Orden, RUC o Nombre de Cliente...", key="pend_txt_bus")
        
        try:
            # [Seguro]: Eliminamos el .limit(50) y usamos los filtros de fecha directamente en la BD
            res_pendientes = supabase.table('ordenes').select('id, codigo_orden, created_at, total_estimado, saldo_pendiente, clientes(nombre_completo, cedula_ruc), estado_facturacion').is_('estado_facturacion', False).gte('created_at', f"{f_inicio_pend}T00:00:00").lte('created_at', f"{f_fin_pend}T23:59:59").order('created_at', desc=True).execute()
            
            res_nulas = supabase.table('ordenes').select('id, codigo_orden, created_at, total_estimado, saldo_pendiente, clientes(nombre_completo, cedula_ruc), estado_facturacion').is_('estado_facturacion', 'null').gte('created_at', f"{f_inicio_pend}T00:00:00").lte('created_at', f"{f_fin_pend}T23:59:59").order('created_at', desc=True).execute()
            
            datos_combinados = (res_pendientes.data if res_pendientes.data else []) + (res_nulas.data if res_nulas.data else [])
            
            # --- FILTRO DE AUDITORÍA FINANCIERA ---
            if datos_combinados:
                datos_combinados = [d for d in datos_combinados if float(d.get('saldo_pendiente', 0) or 0) <= 0]
            
            if datos_combinados:
                lista_pend = []
                for d in datos_combinados:
                    nom_cli = d.get('clientes', {}).get('nombre_completo') if d.get('clientes') else "Consumidor Final"
                    ruc_cli = d.get('clientes', {}).get('cedula_ruc') if d.get('clientes') else "9999999999999"
                    
                    lista_pend.append({
                        "Código": d['codigo_orden'],
                        "Fecha": str(d['created_at'])[:10],
                        "Cliente": nom_cli,
                        "RUC/CI": ruc_cli,
                        "Total": f"${float(d['total_estimado']):.2f}"
                    })
                    
                df_pend = pd.DataFrame(lista_pend).drop_duplicates(subset=['Código'])
                
                # [Seguro]: Aplicamos el filtro de texto interactivo de Pandas
                if txt_bus_pend:
                    df_pend = df_pend[
                        df_pend['Código'].str.contains(txt_bus_pend, case=False, na=False) |
                        df_pend['RUC/CI'].str.contains(txt_bus_pend, case=False, na=False) |
                        df_pend['Cliente'].str.contains(txt_bus_pend, case=False, na=False)
                    ]
                
                # Validamos que el dataframe filtrado no quede vacío antes de pintarlo
                if not df_pend.empty:
                    # Tabla interactiva para seleccionar qué facturar
                    evt_pend = st.dataframe(df_pend, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
                    
                if len(evt_pend.selection.rows) > 0:
                    cod_sel = df_pend.iloc[evt_pend.selection.rows[0]]["Código"]
                    st.divider()
                    st.markdown(f"### 📋 Detalles para Facturar: `{cod_sel}`")
                    
                    with st.spinner("Extrayendo y agrupando datos de la orden..."):
                        datos_orden = obtener_datos_orden(supabase, cod_sel)
                        
                    if datos_orden:
                        col_cli, col_prod = st.columns([1, 1.5])
                        
                        # --- COLUMNA 1: DATOS PARA COPIAR AL FACTURADOR ---
                        with col_cli:
                            st.markdown("#### 👤 Datos del Cliente")
                            st.caption("💡 Pasa el mouse sobre el recuadro para copiar rápidamente.")
                            cli = datos_orden.get('clientes', {})
                            
                            # Utilizamos st.code para texto negro legible y botón de copiado nativo
                            st.write("Razón Social / Nombre:")
                            st.code(cli.get('nombre_completo', cli.get('nombre', 'Consumidor Final')), language=None)
                            
                            st.write("RUC / CI:")
                            st.code(cli.get('cedula_ruc', '9999999999999'), language=None)
                            
                            st.write("Correo:")
                            st.code(cli.get('email', cli.get('correo', 'Sin correo registrado')), language=None)
                            
                            st.write("Teléfono:")
                            st.code(cli.get('telefono', cli.get('celular', 'Sin teléfono registrado')), language=None)
                            
                            st.write("Dirección:")
                            st.code(cli.get('ciudad', 'Sin dirección registrada'), language=None)
                            
                            # [Seguro]: Extraemos los pagos para la nueva auditoría
                            pagos = datos_orden.get('pagos', [])
                            
                        # --- COLUMNA 2: RESUMEN DE PRODUCTOS A FACTURAR ---
                        with col_prod:
                            st.markdown("#### 🛒 Resumen de Productos")
                            
                            # Extraer IDs de productos para buscar sus códigos en la base de datos
                            ids_productos = [item.get('producto_id') for item in datos_orden.get('items', []) if item.get('producto_id')]
                            mapa_codigos = {}
                            if ids_productos:
                                try:
                                    res_cods = supabase.table('productos_catalogo').select('id, codigo_referencia').in_('id', ids_productos).execute()
                                    mapa_codigos = {c['id']: c.get('codigo_referencia', 'S/C') for c in res_cods.data}
                                except: pass
                            
                            # Agrupamos los items incluyendo el código de producto
                            agrupados = {}
                            for item in datos_orden.get('items', []):
                                nombre = str(item.get('nombre_producto', 'Producto')).replace('│', '|')
                                precio = float(item.get('precio_aplicado', 0))
                                cant = float(item.get('cantidad_total', 1))
                                prod_id = item.get('producto_id')
                                codigo = mapa_codigos.get(prod_id, "GEN") # Extraemos el código
                                
                                key = f"{codigo}|{nombre}|{precio}"
                                if key not in agrupados:
                                    agrupados[key] = {"codigo": codigo, "nombre": nombre, "precio": precio, "cant": cant}
                                else:
                                    agrupados[key]["cant"] += cant
                                    
                            for v in agrupados.values():
                                subt = v['cant'] * v['precio']
                                cant_str = int(v['cant']) if v['cant'].is_integer() else f"{v['cant']:.2f}"
                                st.info(f"**[{v['codigo']}]** - {v['nombre']} \n\n **{cant_str}x** a ${v['precio']:.2f} c/u \t **Total Lín: ${subt:.2f}**")
                                
                            total_factura = float(datos_orden.get('total_estimado', 0))
                            st.metric("Total a Facturar", f"${total_factura:.2f}")
                            
                        # ==========================================================
                        # NUEVA SECCIÓN: AUDITORÍA Y CORRECCIÓN DE PAGOS
                        # ==========================================================
                        st.divider()
                        st.markdown("#### 💳 Auditoría y Corrección de Pagos")
                        st.caption("Verifica que los cobros registrados coincidan con la realidad. Modifica, agrega o elimina pagos si el asesor cometió un error al registrar el abono/saldo.")
                        
                        # [Probable]: Preparar los datos financieros en un formato amigable para edición
                        lista_pagos = []
                        for p in pagos:
                            f_pago_str = p.get('fecha_pago') or str(datetime.today().date())
                            # Transformamos el texto a objeto Date desde el principio para evitar el colapso
                            try:
                                fecha_obj = datetime.strptime(f_pago_str[:10], "%Y-%m-%d").date()
                            except:
                                fecha_obj = datetime.today().date()
                                
                            lista_pagos.append({
                                "id_oculto": p.get("id"),
                                "Fecha": fecha_obj,
                                "Método": p.get("metodo_pago", "Efectivo"),
                                "Banco": p.get("banco_destino", ""),
                                "Referencia": p.get("numero_referencia", ""),
                                "Monto ($)": float(p.get("monto", 0))
                            })
                        
                        df_pagos = pd.DataFrame(lista_pagos)
                        if df_pagos.empty:
                            df_pagos = pd.DataFrame(columns=["id_oculto", "Fecha", "Método", "Banco", "Referencia", "Monto ($)"])
                            # [Seguro]: Si la orden no tiene pagos, forzamos la columna vacía a tipo DateTime
                            df_pagos["Fecha"] = pd.to_datetime(df_pagos["Fecha"]).dt.date
                            
                        # El editor dinámico permite borrar filas enteras o agregar nuevas
                        pagos_editados = st.data_editor(
                            df_pagos,
                            num_rows="dynamic",
                            hide_index=True,
                            use_container_width=True,
                            column_config={
                                "id_oculto": None, # Se oculta para no confundir al usuario
                                "Fecha": st.column_config.DateColumn("Fecha", required=True),
                                "Método": st.column_config.SelectboxColumn("Método", options=["Efectivo", "Transferencia", "Tarjeta", "Otro"], required=True),
                                "Banco": st.column_config.SelectboxColumn("Banco", options=["", "JEP", "Pichincha", "Pacifico", "Austro", "Otro"]),
                                "Referencia": st.column_config.TextColumn("Ref/Comprobante"),
                                "Monto ($)": st.column_config.NumberColumn("Monto ($)", min_value=0.01, format="%.2f", required=True)
                            },
                            key=f"editor_pagos_{cod_sel}"
                        )
                        
                        # Matemáticas de Validación
                        total_pagado = pagos_editados["Monto ($)"].sum() if not pagos_editados.empty else 0.0
                        descuadre = total_factura - total_pagado
                        
                        col_val1, col_val2 = st.columns([2, 1])
                        
                        with col_val1:
                            if descuadre > 0:
                                st.error(f"⚠️ Faltan pagos por registrar: **${descuadre:.2f}** pendientes de cobro.")
                            elif descuadre < 0:
                                st.warning(f"⚠️ Sobrecobro detectado: Hay **${abs(descuadre):.2f}** cobrados de más.")
                            else:
                                st.success("✅ Los pagos cubren el 100% de la orden exactamente.")
                                
                        with col_val2:
                            # [Seguro]: El botón solo se activa si Streamlit detecta una modificación real en la tabla
                            hubo_cambios = not df_pagos.equals(pagos_editados)
                            if st.button("💾 Guardar Correcciones", type="secondary", disabled=not hubo_cambios, use_container_width=True):
                                try:
                                    with st.spinner("Actualizando libros contables..."):
                                        # 1. Purga total del historial viejo de esta orden
                                        supabase.table('pagos').delete().eq('orden_id', datos_orden['id']).execute()
                                        
                                        # 2. Inserción de la nueva realidad financiera
                                        nuevos_pagos_db = []
                                        for _, r in pagos_editados.iterrows():
                                            nuevos_pagos_db.append({
                                                "orden_id": datos_orden['id'],
                                                "cliente_id": datos_orden['cliente_id'],
                                                "monto": r["Monto ($)"],
                                                "metodo_pago": r["Método"],
                                                "banco_destino": r["Banco"] if r["Banco"] else None,
                                                "numero_referencia": str(r["Referencia"]) if r.get("Referencia") else None,
                                                "fecha_pago": str(r["Fecha"])
                                            })
                                        if nuevos_pagos_db:
                                            supabase.table('pagos').insert(nuevos_pagos_db).execute()
                                            
                                        # 3. Corrección del saldo general de la orden
                                        nuevo_saldo = descuadre if descuadre > 0 else 0.0
                                        supabase.table('ordenes').update({"saldo_pendiente": nuevo_saldo}).eq('id', datos_orden['id']).execute()
                                        
                                        st.toast("Finanzas actualizadas", icon="✅")
                                        time.sleep(1)
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"Error actualizando pagos: {e}")

                        st.markdown("---")
                        st.markdown("#### ✅ Confirmación de Emisión")
                        st.caption("Ingresa aquí el número de factura para limpiar esta orden de la bandeja. (El botón se bloquea si hay deudas).")
                        
                        col_emit1, col_emit2 = st.columns([2, 1])
                        num_factura = col_emit1.text_input("N° de Factura (Ej: 001-001-000012345)", label_visibility="collapsed", placeholder="N° de Factura (Ej: 001-001-000012345)")
                        
                        # [Suposición]: Asumo que no deseas facturar órdenes incompletas. El botón se bloquea si 'descuadre > 0'.
                        if col_emit2.button("Marcar como FACTURADA", type="primary", use_container_width=True, disabled=(descuadre > 0)):
                            if num_factura.strip():
                                try:
                                    supabase.table('ordenes').update({
                                        "estado_facturacion": True,
                                        "numero_factura": num_factura.strip()
                                    }).eq('id', datos_orden['id']).execute()
                                    st.success(f"¡Listo! Orden {cod_sel} vinculada a la factura {num_factura}.")
                                    time.sleep(1.5)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error al guardar en base de datos: {e}")
                            else:
                                st.warning("⚠️ Debes ingresar el número de la factura para poder continuar.")
            else:
                st.success("🎉 ¡No hay órdenes pendientes de facturar!")
        except Exception as e:
            st.error(f"Error al cargar la bandeja de pendientes: {e}")

    # ==============================================================================
    # TAB 2: HISTORIAL DE FACTURADAS
    # ==============================================================================
    with tab2:
        st.subheader("Auditoría de Órdenes Facturadas")
        
        # Agregamos la barra de búsqueda junto a las fechas
        col_b1, col_b2, col_b3 = st.columns([1.5, 1.5, 3])
        f_inicio = col_b1.date_input("Desde", value=datetime.today().replace(day=1), key="fac_f_ini")
        f_fin = col_b2.date_input("Hasta", value=datetime.today(), key="fac_f_fin")
        txt_bus_hist = col_b3.text_input("🔍 Buscar", placeholder="Orden, Factura o Nombre de Cliente...")
        
        try:
            res_fact = supabase.table('ordenes').select('codigo_orden, numero_factura, created_at, total_estimado, clientes(nombre_completo)').eq('estado_facturacion', True).gte('created_at', f"{f_inicio}T00:00:00").lte('created_at', f"{f_fin}T23:59:59").order('created_at', desc=True).execute()
            
            if res_fact.data:
                lista_f = []
                for d in res_fact.data:
                    nom_cli = d.get('clientes', {}).get('nombre_completo') if d.get('clientes') else "Consumidor Final"
                    lista_f.append({
                        "Orden ERP": d['codigo_orden'],
                        "N° Factura SRI": d.get('numero_factura', 'N/A'),
                        "Cliente": nom_cli,
                        "Fecha de Creación": str(d['created_at'])[:10],
                        "Total Cobrado": f"${float(d['total_estimado']):.2f}"
                    })
                    
                df_historial = pd.DataFrame(lista_f)
                
                # Lógica de filtrado de texto
                if txt_bus_hist:
                    df_historial = df_historial[
                        df_historial['Orden ERP'].str.contains(txt_bus_hist, case=False, na=False) |
                        df_historial['N° Factura SRI'].str.contains(txt_bus_hist, case=False, na=False) |
                        df_historial['Cliente'].str.contains(txt_bus_hist, case=False, na=False)
                    ]
                    
                if not df_historial.empty:
                    st.dataframe(df_historial, use_container_width=True, hide_index=True)
                else:
                    st.info("Ninguna factura coincide con tu búsqueda.")
            else:
                st.info("No hay facturas vinculadas en este rango de fechas.")
        except Exception as e:
            st.error(f"Error al cargar el historial de facturas: {e}")
