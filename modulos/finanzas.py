import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date

def render(supabase):
    st.title("💸 Finanzas y Control de Caja")
    st.markdown("Gestión de ingresos (Abonos/Pagos), egresos operativos y cuentas por cobrar.")

    tab_flujo, tab_cxc, tab_gastos, tab_diario = st.tabs([
        "📊 Flujo de Caja", 
        "⏳ Cuentas por Cobrar", 
        "📤 Registrar Gasto", 
        "📖 Libro Diario"
    ])

    hoy = date.today()
    primer_dia_mes = hoy.replace(day=1)
    
    # ==========================================
    # TAB 1: FLUJO DE CAJA 
    # ==========================================
    with tab_flujo:
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
    # TAB 2: CUENTAS POR COBRAR
    # ==========================================
    with tab_cxc:
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
            
            with st.expander("🔍 Buscador Avanzado (Filtros)", expanded=True):
                col_b1, col_b2, col_b3 = st.columns([2, 2, 2])
                busqueda_cod = col_b1.text_input("Código de Orden", placeholder="Ej: 001", key="bus_cod_cxc")
                busqueda_cli = col_b2.text_input("Nombre del Cliente", placeholder="Ej: Juan", key="bus_cli_cxc")
                busqueda_fechas = col_b3.date_input("Rango de Fechas (Creación)", value=[], format="DD/MM/YYYY", key="bus_fec_cxc")
            
            df_filtrado = df_cxc.copy()
            if busqueda_cod: df_filtrado = df_filtrado[df_filtrado['codigo_orden'].str.contains(busqueda_cod, case=False, na=False)]
            if busqueda_cli: df_filtrado = df_filtrado[df_filtrado['Cliente'].str.contains(busqueda_cli, case=False, na=False)]
            if len(busqueda_fechas) == 2:
                inicio = pd.to_datetime(busqueda_fechas[0])
                fin = pd.to_datetime(busqueda_fechas[1]).replace(hour=23, minute=59, second=59)
                fechas_creacion = pd.to_datetime(df_filtrado['created_at'])
                df_filtrado = df_filtrado[(fechas_creacion >= inicio) & (fechas_creacion <= fin)]
            
            st.dataframe(
                df_filtrado[["codigo_orden", "Cliente", "total_estimado", "abono_inicial", "saldo_pendiente", "estado"]], 
                use_container_width=True, hide_index=True
            )
            
            st.divider()
            st.markdown("### 💰 Registrar Abono o Pago Final")
            
            if not df_filtrado.empty:
                opciones_ordenes = {row["id"]: f"{row['codigo_orden']} - Cliente: {row['Cliente']} - Saldo: ${row['saldo_pendiente']}" for _, row in df_filtrado.iterrows()}
                orden_seleccionada_id = st.selectbox("1. Selecciona la Orden a Pagar", options=list(opciones_ordenes.keys()), format_func=lambda x: opciones_ordenes[x])
                
                orden_data = next((item for item in res_cxc.data if item["id"] == orden_seleccionada_id), None)
                saldo_actual = float(orden_data["saldo_pendiente"]) if orden_data else 0.0

                col_monto, col_metodo, col_banco = st.columns(3)
                monto_a_pagar = col_monto.number_input("2. Monto a Pagar ($)", min_value=0.01, max_value=saldo_actual, value=saldo_actual)
                metodo_pago = col_metodo.selectbox("3. Método de Pago", ["Efectivo", "Transferencia", "Tarjeta", "Otro"])
                
                banco_destino = None
                if metodo_pago == "Transferencia":
                    # Agregamos "Seleccionar..." para obligar al usuario a interactuar
                    banco_destino = col_banco.selectbox("4. Banco Destino", ["Seleccionar...", "JEP", "Pichincha", "Pacifico", "Austro"])
                
                if st.button("💾 Guardar Pago", type="primary", use_container_width=True):
                    # VALIDACIÓN ESTRICTA DEL BANCO
                    if metodo_pago == "Transferencia" and (not banco_destino or banco_destino == "Seleccionar..."):
                        st.error("⚠️ Operación cancelada: Debes seleccionar a qué banco ingresó la transferencia.")
                    else:
                        try:
                            data_pago = {
                                "orden_id": orden_seleccionada_id,
                                "cliente_id": orden_data["cliente_id"],
                                "monto": monto_a_pagar,
                                "metodo_pago": metodo_pago,
                                "fecha_pago": hoy.isoformat()
                            }
                            # Solo guardamos el banco si no es "Seleccionar..."
                            if banco_destino and banco_destino != "Seleccionar...":
                                data_pago["banco_destino"] = banco_destino

                            supabase.table("pagos").insert(data_pago).execute()
                            
                            nuevo_saldo = saldo_actual - monto_a_pagar
                            update_data = {"saldo_pendiente": nuevo_saldo}
                            if nuevo_saldo <= 0: update_data["estado"] = "Lista para Entrega"

                            supabase.table("ordenes").update(update_data).eq("id", orden_seleccionada_id).execute()
                            st.success(f"Pago registrado con éxito. Nuevo saldo: ${nuevo_saldo:.2f}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al registrar el pago: {e}")
            else:
                st.info("No hay resultados para tu búsqueda.")
        else:
            st.success("¡Excelente! Todas las órdenes están pagadas.")

    # ==========================================
    # TAB 3: REGISTRAR GASTO 
    # ==========================================
    with tab_gastos:
        c_gasto, c_cat = st.columns([2, 1])
        
        with c_gasto:
            st.subheader("Registrar Nuevo Egreso Operativo")
            
            res_categorias = supabase.table("categorias_egreso").select("nombre").execute()
            lista_categorias = [c["nombre"] for c in res_categorias.data] if res_categorias.data else ["Otros"]

            col1, col2 = st.columns(2)
            fecha_gasto = col1.date_input("Fecha del Gasto", value=hoy)
            categoria_gasto = col2.selectbox("Categoría", lista_categorias)
            
            descripcion_gasto = st.text_input("Descripción breve (Ej. Compra de hilos)")
            
            col3, col4, col5 = st.columns(3)
            monto_gasto = col3.number_input("Monto ($)", min_value=0.01, step=1.00, format="%.2f")
            metodo_gasto = col4.selectbox("Medio de Pago", ["Efectivo", "Transferencia", "Tarjeta"])
            
            banco_origen = None
            if metodo_gasto == "Transferencia":
                # Agregamos "Seleccionar..." para obligar a interactuar
                banco_origen = col5.selectbox("Banco Origen (De dónde sale)", ["Seleccionar...", "JEP", "Pichincha", "Pacifico", "Austro"])
            
            st.write("") 
            if st.button("📤 Guardar Egreso", type="primary", use_container_width=True):
                # VALIDACIÓN ESTRICTA (Descripción y Banco)
                if not descripcion_gasto.strip():
                    st.warning("⚠️ Por favor, ingresa una descripción.")
                elif metodo_gasto == "Transferencia" and (not banco_origen or banco_origen == "Seleccionar..."):
                    st.error("⚠️ Operación cancelada: Debes seleccionar de qué banco salió el dinero para la transferencia.")
                else:
                    try:
                        data_egreso = {
                            "fecha": fecha_gasto.isoformat(),
                            "categoria": categoria_gasto,
                            "descripcion": descripcion_gasto,
                            "monto": monto_gasto,
                            "metodo_pago": metodo_gasto
                        }
                        if banco_origen and banco_origen != "Seleccionar...":
                            data_egreso["banco"] = banco_origen

                        supabase.table("egresos").insert(data_egreso).execute()
                        st.success("Gasto registrado exitosamente.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al registrar: ¿Ejecutaste el comando SQL para añadir la columna 'banco'? Detalles: {e}")
                        
        with c_cat:
            st.subheader("Gestión")
            with st.expander("➕ Crear Nueva Categoría"):
                nueva_cat = st.text_input("Nombre de categoría")
                if st.button("Guardar Categoría", use_container_width=True):
                    if nueva_cat:
                        try:
                            supabase.table("categorias_egreso").insert({"nombre": nueva_cat.strip()}).execute()
                            st.success("Categoría añadida")
                            st.rerun()
                        except:
                            st.error("Error al crear. Quizá ya existe.")

    # ==========================================
    # TAB 4: LIBRO DIARIO
    # ==========================================
    with tab_diario:
        st.subheader("Libro Diario y Cuadre de Caja")
        
        fecha_diario = st.date_input("Selecciona la fecha para revisar transacciones:", value=hoy, key="fecha_diario_filtro")
        col_ing_diario, col_egr_diario = st.columns(2)
        
        res_pagos_dia = supabase.table("pagos").select("orden_id, monto, metodo_pago, banco_destino").eq("fecha_pago", fecha_diario.isoformat()).execute()
        res_egresos_dia = supabase.table("egresos").select("categoria, descripcion, monto, metodo_pago, banco").eq("fecha", fecha_diario.isoformat()).execute()
        
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
                st.info("No hay ingresos.")
                total_ing_dia = 0.0

        with col_egr_diario:
            st.markdown("#### 🔴 Egresos")
            if res_egresos_dia.data:
                df_egresos_dia = pd.DataFrame(res_egresos_dia.data)
                
                df_egresos_dia['Medio'] = df_egresos_dia.apply(
                    lambda x: f"{x['metodo_pago']} ({x['banco']})" if pd.notna(x.get('banco')) and x.get('banco') else x['metodo_pago'], axis=1
                )
                
                st.dataframe(df_egresos_dia[['categoria', 'monto', 'Medio']], use_container_width=True, hide_index=True)
                
                total_egr_dia = df_egresos_dia['monto'].astype(float).sum()
                st.error(f"**Total Egresos: ${total_egr_dia:,.2f}**")
            else:
                st.info("No hay egresos.")
                total_egr_dia = 0.0
                
        st.divider()
        cierre_caja = total_ing_dia - total_egr_dia
        st.metric("Cierre de Caja del Día", f"${cierre_caja:,.2f}")