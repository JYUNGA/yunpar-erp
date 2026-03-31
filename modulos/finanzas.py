import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date

def render(supabase):
    # ==========================================
    # 🔐 SISTEMA DE ROLES (RBAC)
    # ==========================================
    rol_actual = st.session_state.get('rol', 'VENDEDORA').upper() 

    st.title("💸 Finanzas y Control de Caja")
    st.markdown("Gestión de ingresos (Abonos/Pagos), egresos operativos y cuentas por cobrar.")

    # ==========================================
    # 🏗️ CONSTRUCCIÓN DINÁMICA DE PESTAÑAS
    # ==========================================
    if rol_actual == "GERENTE":
        nombres_tabs = ["📊 Flujo de Caja", "⏳ Cuentas por Cobrar", "📤 Registrar Gasto", "📖 Libro Diario"]
    else:
        nombres_tabs = ["⏳ Cuentas por Cobrar", "📤 Registrar Gasto"]

    tabs_creados = st.tabs(nombres_tabs)
    mis_tabs = dict(zip(nombres_tabs, tabs_creados))

    hoy = date.today()
    primer_dia_mes = hoy.replace(day=1)
    
    # ==========================================
    # TAB 1: FLUJO DE CAJA (Solo Gerente)
    # ==========================================
    if "📊 Flujo de Caja" in mis_tabs:
        with mis_tabs["📊 Flujo de Caja"]:
            st.subheader("Resumen de Flujo de Caja")
            col_f1, col_f2 = st.columns(2)
            f_inicio = col_f1.date_input("🗓️ Desde", value=primer_dia_mes)
            f_fin = col_f2.date_input("🗓️ Hasta", value=hoy)
            
            res_pagos = supabase.table("pagos").select("monto").gte("fecha_pago", f_inicio.isoformat()).lte("fecha_pago", f_fin.isoformat()).execute()
            ingresos_rango = sum([float(p["monto"]) for p in res_pagos.data]) if res_pagos.data else 0.0
            
            res_egresos = supabase.table("egresos").select("monto").gte("fecha", f_inicio.isoformat()).lte("fecha", f_fin.isoformat()).execute()
            egresos_rango = sum([float(e["monto"]) for e in res_egresos.data]) if res_egresos.data else 0.0
            
            balance = ingresos_rango - egresos_rango

            col1, col2, col3 = st.columns(3)
            col1.metric("🟢 Ingresos del Periodo", f"${ingresos_rango:,.2f}")
            col2.metric("🔴 Egresos del Periodo", f"${egresos_rango:,.2f}")
            col3.metric("⚖️ Balance", f"${balance:,.2f}", delta=f"${balance:,.2f}", delta_color="normal" if balance >= 0 else "inverse")

            st.divider()
            df_grafico = pd.DataFrame({"Categoría": ["Ingresos", "Egresos"], "Monto": [ingresos_rango, egresos_rango]})
            
            if ingresos_rango > 0 or egresos_rango > 0:
                fig = px.bar(
                    df_grafico, x="Categoría", y="Monto", color="Categoría",
                    color_discrete_map={"Ingresos": "#2ecc71", "Egresos": "#e74c3c"}, text_auto='.2f',
                    title=f"Comparativa: {f_inicio.strftime('%d/%m/%Y')} al {f_fin.strftime('%d/%m/%Y')}"
                )
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hay movimientos registrados en este rango de fechas.")

    # ==========================================
    # TAB 2: CUENTAS POR COBRAR (Gerente y Vendedora)
    # ==========================================
    if "⏳ Cuentas por Cobrar" in mis_tabs:
        with mis_tabs["⏳ Cuentas por Cobrar"]:
            st.subheader("Órdenes con Saldo Pendiente")
            
            res_cxc = supabase.table("ordenes").select("id, codigo_orden, cliente_id, created_at, total_estimado, abono_inicial, saldo_pendiente, estado").gt("saldo_pendiente", 0).execute()
            
            if res_cxc.data:
                df_cxc = pd.DataFrame(res_cxc.data)
                
                cliente_ids = df_cxc['cliente_id'].dropna().unique().tolist()
                mapa_clientes = {}
                if cliente_ids:
                    res_cli = supabase.table('clientes').select('id, nombre_completo').in_('id', cliente_ids).execute()
                    mapa_clientes = {c['id']: c.get('nombre_completo', 'Consumidor Final') for c in res_cli.data}
                
                df_cxc['Cliente'] = df_cxc['cliente_id'].map(lambda x: mapa_clientes.get(x, 'Consumidor Final'))
                
                with st.expander("🔍 Buscador Avanzado (Filtros)", expanded=False):
                    col_b1, col_b2, col_b3 = st.columns([2, 2, 2])
                    busqueda_cod = col_b1.text_input("Código de Orden", placeholder="Ej: 6429", key="bus_cod_cxc")
                    busqueda_cli = col_b2.text_input("Nombre del Cliente", placeholder="Ej: Wilmer", key="bus_cli_cxc")
                    busqueda_fechas = col_b3.date_input("Rango de Fechas (Creación)", value=[], format="DD/MM/YYYY", key="bus_fec_cxc")
                
                df_filtrado = df_cxc.copy()
                if busqueda_cod: df_filtrado = df_filtrado[df_filtrado['codigo_orden'].str.contains(busqueda_cod, case=False, na=False)]
                if busqueda_cli: df_filtrado = df_filtrado[df_filtrado['Cliente'].str.contains(busqueda_cli, case=False, na=False)]
                if len(busqueda_fechas) == 2:
                    inicio = pd.to_datetime(busqueda_fechas[0])
                    fin = pd.to_datetime(busqueda_fechas[1]).replace(hour=23, minute=59, second=59)
                    fechas_creacion = pd.to_datetime(df_filtrado['created_at'])
                    df_filtrado = df_filtrado[(fechas_creacion >= inicio) & (fechas_creacion <= fin)]
                
                st.markdown("👇 **Haz clic en la fila de la orden en la tabla para registrar su pago:**")
                
                evento_tabla = st.dataframe(
                    df_filtrado[["id", "codigo_orden", "Cliente", "total_estimado", "abono_inicial", "saldo_pendiente", "estado"]], 
                    use_container_width=True, 
                    hide_index=True,
                    selection_mode="single-row",
                    on_select="rerun",
                    column_config={
                        "id": None, 
                        "total_estimado": st.column_config.NumberColumn("Total", format="$ %.2f"),
                        "abono_inicial": st.column_config.NumberColumn("Abono", format="$ %.2f"),
                        "saldo_pendiente": st.column_config.NumberColumn("Saldo", format="$ %.2f")
                    }
                )
                
                filas_seleccionadas = evento_tabla.selection.rows
                
                if len(filas_seleccionadas) == 0:
                    st.info("👆 Selecciona una orden en la tabla para habilitar las opciones de pago.")
                else:
                    indice_fila = filas_seleccionadas[0]
                    fila_datos = df_filtrado.iloc[indice_fila]
                    orden_seleccionada_id = int(fila_datos["id"])
                    saldo_actual = float(fila_datos["saldo_pendiente"])
                    
                    st.divider()
                    st.markdown(f"### 💰 Liquidar Orden: **{fila_datos['codigo_orden']}** ({fila_datos['Cliente']})")

                    with st.form(key="form_pago", clear_on_submit=True):
                        col_monto, col_metodo, col_banco = st.columns(3)
                        monto_a_pagar = col_monto.number_input("Monto a Pagar ($)", min_value=0.01, max_value=saldo_actual, value=saldo_actual)
                        metodo_pago = col_metodo.selectbox("Método de Pago", ["Efectivo", "Transferencia", "Tarjeta", "Otro"])
                        banco_destino = col_banco.selectbox("Banco Destino", ["Seleccionar...", "JEP", "Pichincha", "Pacifico", "Austro"])
                        
                        submit_pago = st.form_submit_button("💾 Confirmar Pago", type="primary", use_container_width=True)
                        
                        if submit_pago:
                            if metodo_pago == "Transferencia" and banco_destino == "Seleccionar...":
                                st.error("⚠️ Debes seleccionar a qué banco ingresó la transferencia.")
                            else:
                                try:
                                    data_pago = {
                                        "orden_id": orden_seleccionada_id,
                                        "cliente_id": int(fila_datos["cliente_id"]),
                                        "monto": monto_a_pagar,
                                        "metodo_pago": metodo_pago,
                                        "fecha_pago": hoy.isoformat()
                                    }
                                    if banco_destino != "Seleccionar...":
                                        data_pago["banco_destino"] = banco_destino

                                    supabase.table("pagos").insert(data_pago).execute()
                                    
                                    nuevo_saldo = saldo_actual - monto_a_pagar
                                    update_data = {"saldo_pendiente": nuevo_saldo}
                                    
                                    estado_actual = fila_datos.get("estado", "")
                                    if nuevo_saldo <= 0: 
                                        if estado_actual not in ["Listo para Impresión", "En Impresión", "En Diseño", "En Sublimación", "En Confección"]:
                                            update_data["estado"] = "Lista para Entrega"

                                    supabase.table("ordenes").update(update_data).eq("id", orden_seleccionada_id).execute()
                                    
                                    st.success(f"✅ Pago registrado con éxito. Nuevo saldo: ${nuevo_saldo:.2f}")
                                    st.rerun() 
                                except Exception as e:
                                    st.error(f"Error al registrar el pago: {e}")
            else:
                st.success("¡Excelente! Todas las órdenes están pagadas.")

    # ==========================================
    # TAB 3: REGISTRAR GASTO (Gerente y Vendedora)
    # ==========================================
    if "📤 Registrar Gasto" in mis_tabs:
        with mis_tabs["📤 Registrar Gasto"]:
            c_gasto, c_cat = st.columns([2, 1])
            
            with c_gasto:
                st.subheader("Registrar Nuevo Egreso Operativo")
                
                res_categorias = supabase.table("categorias_egreso").select("nombre").execute()
                lista_categorias = [c["nombre"] for c in res_categorias.data] if res_categorias.data else ["Otros"]

                with st.form("form_egreso", clear_on_submit=True):
                    col1, col2 = st.columns(2)
                    fecha_gasto = col1.date_input("Fecha del Gasto", value=hoy)
                    categoria_gasto = col2.selectbox("Categoría", lista_categorias)
                    
                    descripcion_gasto = st.text_input("Descripción breve (Ej. Compra de hilos)")
                    
                    col3, col4, col5 = st.columns(3)
                    monto_gasto = col3.number_input("Monto ($)", min_value=0.01, step=1.00, format="%.2f")
                    metodo_gasto = col4.selectbox("Medio de Pago", ["Efectivo", "Transferencia", "Tarjeta"])
                    banco_origen = col5.selectbox("Banco Origen", ["Seleccionar...", "JEP", "Pichincha", "Pacifico", "Austro"])
                    
                    submit_gasto = st.form_submit_button("📤 Guardar Egreso", type="primary", use_container_width=True)
                    
                    if submit_gasto:
                        if not descripcion_gasto.strip():
                            st.warning("⚠️ Por favor, ingresa una descripción.")
                        elif metodo_gasto == "Transferencia" and banco_origen == "Seleccionar...":
                            st.error("⚠️ Debes seleccionar de qué banco salió el dinero.")
                        else:
                            try:
                                data_egreso = {
                                    "fecha": fecha_gasto.isoformat(),
                                    "categoria": categoria_gasto,
                                    "descripcion": descripcion_gasto,
                                    "monto": monto_gasto,
                                    "metodo_pago": metodo_gasto
                                }
                                if banco_origen != "Seleccionar...":
                                    data_egreso["banco"] = banco_origen

                                supabase.table("egresos").insert(data_egreso).execute()
                                st.toast("✅ Gasto registrado exitosamente.", icon="📉")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al registrar: {e}")
                                
            with c_cat:
                st.subheader("Gestión")
                with st.expander("➕ Crear Nueva Categoría"):
                    nueva_cat = st.text_input("Nombre de categoría")
                    if st.button("Guardar Categoría", use_container_width=True):
                        if nueva_cat:
                            try:
                                supabase.table("categorias_egreso").insert({"nombre": nueva_cat.strip()}).execute()
                                st.toast("Categoría añadida", icon="✅")
                                st.rerun()
                            except:
                                st.error("Error al crear. Quizá ya existe.")
                
                st.divider()
                st.markdown("##### 🕒 Últimos 10 Registros")
                st.caption("Revisa aquí para evitar registrar el mismo gasto dos veces.")
                
                try:
                    res_ultimos = supabase.table("egresos").select("fecha, descripcion, monto").order("created_at", desc=True).limit(10).execute()
                    
                    if res_ultimos.data:
                        df_ultimos = pd.DataFrame(res_ultimos.data)
                        st.dataframe(
                            df_ultimos,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "fecha": "Fecha",
                                "descripcion": "Descripción",
                                "monto": st.column_config.NumberColumn("Monto", format="$ %.2f")
                            }
                        )
                    else:
                        st.info("No hay egresos recientes.")
                except Exception as e:
                    st.caption("Error al cargar el historial.")

    # ==========================================
    # TAB 4: LIBRO DIARIO (Solo Gerente)
    # ==========================================
    if "📖 Libro Diario" in mis_tabs:
        with mis_tabs["📖 Libro Diario"]:
            st.subheader("Libro Diario y Cuadre de Caja")
            
            fecha_input = st.date_input(
                "🗓️ Selecciona fecha única o un rango de fechas:", 
                value=(hoy, hoy), 
                key="fecha_diario_filtro"
            )
            
            if isinstance(fecha_input, tuple):
                if len(fecha_input) == 2:
                    f_ini_diario, f_fin_diario = fecha_input
                elif len(fecha_input) == 1:
                    f_ini_diario = f_fin_diario = fecha_input[0]
                else:
                    f_ini_diario = f_fin_diario = hoy
            else:
                f_ini_diario = f_fin_diario = fecha_input

            col_ing_diario, col_egr_diario = st.columns(2)
            
            res_pagos_dia = supabase.table("pagos").select("id, orden_id, monto, metodo_pago, banco_destino").gte("fecha_pago", f_ini_diario.isoformat()).lte("fecha_pago", f_fin_diario.isoformat()).execute()
            res_egresos_dia = supabase.table("egresos").select("id, categoria, descripcion, monto, metodo_pago, banco").gte("fecha", f_ini_diario.isoformat()).lte("fecha", f_fin_diario.isoformat()).execute()
            
            with col_ing_diario:
                st.markdown("#### 🟢 Ingresos")
                if res_pagos_dia.data:
                    df_ingresos_dia = pd.DataFrame(res_pagos_dia.data)
                    
                    ordenes_ids = df_ingresos_dia['orden_id'].tolist()
                    if ordenes_ids:
                        res_ords = supabase.table("ordenes").select("id, codigo_orden").in_("id", ordenes_ids).execute()
                        if res_ords.data:
                            mapa_ords = {o['id']: o['codigo_orden'] for o in res_ords.data}
                            df_ingresos_dia['Orden'] = df_ingresos_dia['orden_id'].map(mapa_ords)
                    
                    df_ingresos_dia['Medio'] = df_ingresos_dia.apply(
                        lambda x: f"{x['metodo_pago']} ({x['banco_destino']})" if pd.notna(x.get('banco_destino')) and x.get('banco_destino') else x['metodo_pago'], axis=1
                    )
                    
                    df_mostrar_ing = df_ingresos_dia[['Orden', 'monto', 'Medio']] if 'Orden' in df_ingresos_dia.columns else df_ingresos_dia[['monto', 'Medio']]
                    st.dataframe(df_mostrar_ing, use_container_width=True, hide_index=True)
                    
                    total_ing_dia = df_ingresos_dia['monto'].astype(float).sum()
                    st.success(f"**Total Ingresos: ${total_ing_dia:,.2f}**")
                else:
                    st.info("No hay ingresos en este periodo.")
                    total_ing_dia = 0.0

            with col_egr_diario:
                st.markdown("#### 🔴 Egresos")
                if res_egresos_dia.data:
                    df_egresos_dia = pd.DataFrame(res_egresos_dia.data)
                    
                    df_egresos_dia['Medio'] = df_egresos_dia.apply(
                        lambda x: f"{x['metodo_pago']} ({x['banco']})" if pd.notna(x.get('banco')) and x.get('banco') else x['metodo_pago'], axis=1
                    )
                    
                    # --- LÓGICA DE BORRADO SEGURO (SOLUCIONA EL CLIC FANTASMA) ---
                    if rol_actual == "GERENTE":
                        st.caption("👇 Haz clic en un egreso para anularlo.")
                        evento_tabla_egresos = st.dataframe(
                            df_egresos_dia[['id', 'categoria', 'descripcion', 'monto', 'Medio']], 
                            use_container_width=True, 
                            hide_index=True,
                            selection_mode="single-row",
                            on_select="rerun",
                            column_config={
                                "id": None, 
                                "monto": st.column_config.NumberColumn("monto", format="$ %.2f")
                            }
                        )
                        
                        # 1. Cuando haces clic en la tabla, guardamos la intención de borrar en memoria.
                        if len(evento_tabla_egresos.selection.rows) > 0:
                            indice_egr = evento_tabla_egresos.selection.rows[0]
                            fila_egreso = df_egresos_dia.iloc[indice_egr]
                            st.session_state['id_egreso_eliminar'] = str(fila_egreso['id'])
                            st.session_state['desc_egreso_eliminar'] = f"{fila_egreso['descripcion']} (${fila_egreso['monto']:.2f})"
                        else:
                            # Si deseleccionas la tabla, limpiamos la memoria
                            st.session_state.pop('id_egreso_eliminar', None)
                            
                        # 2. Si la memoria tiene un ID, mostramos el botón (Así no desaparece al recargar)
                        if 'id_egreso_eliminar' in st.session_state:
                            st.markdown("---")
                            st.markdown("##### 🗑️ Anular Egreso Seleccionado")
                            st.info(f"Vas a eliminar: **{st.session_state['desc_egreso_eliminar']}**")
                            
                            if st.button("🚨 Confirmar y Eliminar", type="primary", use_container_width=True):
                                try:
                                    # Ejecutamos el SQL usando la variable de la memoria
                                    supabase.table("egresos").delete().eq("id", st.session_state['id_egreso_eliminar']).execute()
                                    # Borramos la memoria para limpiar la pantalla
                                    st.session_state.pop('id_egreso_eliminar', None) 
                                    st.success("✅ Gasto eliminado permanentemente de la base de datos.")
                                    st.rerun() # Refrescamos para ver el saldo corregido
                                except Exception as e:
                                    st.error(f"Error al eliminar en la BD: {e}")
                                    
                    else:
                        # Si no es gerente, solo ve la tabla estática
                        st.dataframe(df_egresos_dia[['categoria', 'descripcion', 'monto', 'Medio']], use_container_width=True, hide_index=True)

                    total_egr_dia = df_egresos_dia['monto'].astype(float).sum()
                    st.error(f"**Total Egresos: ${total_egr_dia:,.2f}**")
                else:
                    st.info("No hay egresos en este periodo.")
                    total_egr_dia = 0.0
                    
            st.divider()
            cierre_caja = total_ing_dia - total_egr_dia
            st.metric("Cierre de Caja del Periodo", f"${cierre_caja:,.2f}", delta=f"${cierre_caja:,.2f}", delta_color="normal" if cierre_caja >= 0 else "inverse")
