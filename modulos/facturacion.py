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
        
        try:
            # Traemos las órdenes que NO están marcadas como facturadas
            res_pendientes = supabase.table('ordenes').select('id, codigo_orden, created_at, total_estimado, clientes(nombre_completo, cedula_ruc), estado_facturacion').is_('estado_facturacion', False).order('created_at', desc=True).limit(50).execute()
            
            # Por si las órdenes viejas tienen el campo en "null" tras crear la columna
            res_nulas = supabase.table('ordenes').select('id, codigo_orden, created_at, total_estimado, clientes(nombre_completo, cedula_ruc), estado_facturacion').is_('estado_facturacion', 'null').order('created_at', desc=True).limit(50).execute()
            
            datos_combinados = (res_pendientes.data if res_pendientes.data else []) + (res_nulas.data if res_nulas.data else [])
            
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
                            
                            pagos = datos_orden.get('pagos', [])
                            metodo = pagos[0].get('metodo_pago', 'Efectivo') if pagos else "Efectivo"
                            st.write("Forma de Pago:")
                            st.code(metodo, language=None)
                            
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
                            
                            st.markdown("---")
                            st.markdown("#### ✅ Confirmación de Emisión")
                            st.caption("Una vez generada la factura en el sistema externo, ingresa aquí el número para limpiar esta orden de la bandeja de pendientes.")
                            
                            num_factura = st.text_input("N° de Factura (Ej: 001-001-000012345)")
                            
                            if st.button("Marcar Orden como FACTURADA", type="primary", use_container_width=True):
                                if num_factura.strip():
                                    try:
                                        supabase.table('ordenes').update({
                                            "estado_facturacion": True,
                                            "numero_factura": num_factura.strip()
                                        }).eq('id', datos_orden['id']).execute()
                                        st.success(f"¡Listo! Orden {cod_sel} vinculada a la factura {num_factura} exitosamente.")
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