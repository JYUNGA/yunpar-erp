import streamlit as st
import pandas as pd
from datetime import datetime
import pytz

# Zona horaria local (ajustada a Ecuador por contexto de uso general)
LOCAL_TZ = pytz.timezone('America/Guayaquil')

def obtener_fecha_actual():
    return datetime.now(LOCAL_TZ).date()

def generar_codigo_vd(supabase):
    """Obtiene el último código VD- y genera el siguiente en la secuencia."""
    try:
        # Ordenar alfabéticamente de forma descendente funciona si mantenemos el padding (ej. VD-0001, VD-0002)
        res = supabase.table('ordenes') \
            .select('codigo_orden') \
            .ilike('codigo_orden', 'VD-%') \
            .order('codigo_orden', desc=True) \
            .limit(1) \
            .execute()
            
        if res.data:
            ultimo_codigo = res.data[0]['codigo_orden']
            # Extraer el número después de "VD-"
            numero = int(ultimo_codigo.split('-')[1])
            nuevo_numero = numero + 1
            return f"VD-{nuevo_numero:04d}"
        else:
            return "VD-0001"
    except Exception as e:
        st.error(f"Error al generar la secuencia: {e}")
        return None

def cargar_catalogo(supabase):
    try:
        res = supabase.table('productos_catalogo').select('*').execute()
        return res.data
    except Exception:
        return []

def render(supabase):
    # 1. CONTROL DE ACCESO ESTRICTO
    if 'rol' not in st.session_state or st.session_state['rol'] not in ["GERENTE", "VENDEDORA"]:
        st.error("🔒 Acceso denegado. Tu rol actual no tiene permisos para acceder al módulo de Ventas Directas.")
        st.stop()

    st.title("🛍️ Módulo de Ventas y Mostrador")
    st.markdown("Gestión de ventas directas e ingreso de órdenes de impresión.")

    # Cargar datos base
    catalogo = cargar_catalogo(supabase)
    if not catalogo:
        st.warning("El catálogo de productos está vacío o hubo un error al conectarse a la base de datos.")
        st.stop()
        
    # Crear diccionario para facilitar la búsqueda del ID del producto desde el nombre en la tabla
    dict_productos = {f"{p['codigo_referencia']} - {p['descripcion']}": p for p in catalogo}
    opciones_productos = list(dict_productos.keys())

    # 2. ESTRUCTURA DE LA INTERFAZ (PESTAÑAS)
    tab1, tab2 = st.tabs(["🛒 Nueva Venta Rápida", "🧾 Historial de Ventas del Día"])

    with tab1:
        st.subheader("Registrar Nueva Venta")
        
        # El st.form encapsula la transacción de la UI para no recargar la app en cada cambio
        with st.form("form_nueva_venta", clear_on_submit=True):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                cliente_id = st.text_input("ID del Cliente (Cédula/RUC o Código interno)")
                tipo_venta = st.radio("Tipo de Flujo de Venta", 
                                      options=["Venta Directa (Entrega Inmediata)", "Venta de Impresión (Pasa a Cola)"],
                                      horizontal=True)
            
            with col2:
                fecha_entrega = st.date_input("Fecha de Entrega Estimada", value="today")

            st.markdown("---")
            st.write("**Detalle de Productos**")
            
            # DataFrame inicial vacío para el data_editor
            df_carrito_base = pd.DataFrame(columns=["Producto", "Cantidad", "Precio Unitario ($)"])
            
            # Usamos st.data_editor para permitir agregar múltiples filas dinámicamente dentro del form
            df_carrito = st.data_editor(
                df_carrito_base,
                column_config={
                    "Producto": st.column_config.SelectboxColumn("Seleccionar Producto", options=opciones_productos, required=True),
                    "Cantidad": st.column_config.NumberColumn("Cantidad", min_value=1, step=1, default=1, required=True),
                    "Precio Unitario ($)": st.column_config.NumberColumn("Precio Unitario", min_value=0.0, format="%.2f", required=True)
                },
                num_rows="dynamic",
                use_container_width=True,
                key="editor_carrito"
            )

            st.markdown("---")
            st.write("**Finanzas y Cobro**")
            col_f1, col_f2, col_f3 = st.columns(3)
            
            with col_f1:
                tipo_pago = st.selectbox("Modalidad de Pago", ["Contado (100%)", "Abono Inicial (Parcial)"])
                abono_ingresado = st.number_input("Monto Recibido ($)", min_value=0.0, format="%.2f")
            
            with col_f2:
                metodo_pago = st.selectbox("Método de Pago", ["Efectivo", "Transferencia", "Tarjeta de Crédito/Débito"])
            
            with col_f3:
                banco_destino = st.text_input("Banco Destino / Ref.", help="Dejar en blanco si es Efectivo")

            submit_venta = st.form_submit_button("✅ Procesar Venta", use_container_width=True)

            if submit_venta:
                # Validaciones de la UI
                if not cliente_id:
                    st.error("Por favor ingresa el ID del Cliente.")
                    st.stop()
                if df_carrito.empty or df_carrito["Producto"].isnull().all():
                    st.error("Debes agregar al menos un producto al detalle.")
                    st.stop()

                # Cálculos de totales
                total_estimado = 0.0
                detalles_a_insertar = []
                
                for index, row in df_carrito.dropna(subset=["Producto"]).iterrows():
                    prod_info = dict_productos[row["Producto"]]
                    cantidad = row["Cantidad"]
                    precio = row["Precio Unitario ($)"]
                    subtotal = cantidad * precio
                    total_estimado += subtotal
                    
                    detalles_a_insertar.append({
                        "producto_id": prod_info["id"],
                        "precio_aplicado": precio,
                        "cantidad": cantidad
                    })

                # Ajustar abono si es de contado
                abono_final = total_estimado if tipo_pago == "Contado (100%)" else abono_ingresado
                saldo_pendiente = total_estimado - abono_final
                
                if abono_final > total_estimado:
                    st.error("El abono no puede ser mayor al total de la venta.")
                    st.stop()

                # Definir estado según regla de negocio
                estado_orden = "Entregado" if "Directa" in tipo_venta else "Pendiente Impresión"
                
                # Generar Secuencia
                nuevo_codigo_vd = generar_codigo_vd(supabase)
                if not nuevo_codigo_vd:
                    st.stop()

                # =========================================================
                # INICIO DE INSERCIÓN EN SUPABASE (Con control de errores)
                # =========================================================
                orden_creada_id = None
                
                try:
                    with st.spinner("Registrando venta en el sistema..."):
                        # 1. Insertar Orden
                        data_orden = {
                            "codigo_orden": nuevo_codigo_vd,
                            "cliente_id": cliente_id,
                            "total_estimado": total_estimado,
                            "abono_inicial": abono_final,
                            "saldo_pendiente": saldo_pendiente,
                            "estado": estado_orden,
                            "fecha_entrega": fecha_entrega.isoformat()
                        }
                        
                        res_orden = supabase.table('ordenes').insert(data_orden).execute()
                        orden_creada = res_orden.data[0]
                        orden_creada_id = orden_creada['id']

                        # 2. Insertar Detalles
                        for detalle in detalles_a_insertar:
                            detalle["orden_id"] = orden_creada_id
                        
                        supabase.table('detalles_orden').insert(detalles_a_insertar).execute()

                        # 3. Insertar Pago (Solo si el abono es mayor a 0)
                        if abono_final > 0:
                            data_pago = {
                                "orden_id": orden_creada_id,
                                "cliente_id": cliente_id,
                                "monto": abono_final,
                                "metodo_pago": metodo_pago,
                                "banco_destino": banco_destino if banco_destino else None,
                                "fecha_pago": datetime.now(LOCAL_TZ).isoformat()
                            }
                            supabase.table('pagos').insert(data_pago).execute()

                    st.success(f"🎉 Venta registrada con éxito. Código de Orden: **{nuevo_codigo_vd}**")
                    st.balloons()

                except Exception as e:
                    # Rollback manual en caso de fallo crítico en detalles o pagos
                    if orden_creada_id:
                        supabase.table('ordenes').delete().eq('id', orden_creada_id).execute()
                    
                    st.error(f"❌ Ocurrió un error crítico durante la venta y se ha cancelado la operación. Detalles del error: {e}")

    # =========================================================
    # TAB 2: HISTORIAL DEL DÍA
    # =========================================================
    with tab2:
        st.subheader(f"Ventas Directas del Día ({obtener_fecha_actual().strftime('%d/%m/%Y')})")
        
        try:
            # Traer órdenes cuyo código empiece con VD-
            # Nota: Supabase postgrest filtra fechas en formato ISO
            hoy_str = obtener_fecha_actual().isoformat()
            
            # Dependiendo de cómo guardes la fecha de creación en tu BD (ej. created_at),
            # adaptaremos la consulta. Asumiré que existe un 'created_at'. Si no, puedes omitir
            # el filtro de fecha de la DB y filtrar con Pandas, o buscar por fecha_entrega.
            res_historial = supabase.table('ordenes') \
                .select('codigo_orden, cliente_id, total_estimado, abono_inicial, saldo_pendiente, estado, fecha_entrega') \
                .ilike('codigo_orden', 'VD-%') \
                .execute()
            
            df_historial = pd.DataFrame(res_historial.data)
            
            if not df_historial.empty:
                # Formatear columnas de moneda para visualización
                cols_moneda = ['total_estimado', 'abono_inicial', 'saldo_pendiente']
                for col in cols_moneda:
                    df_historial[col] = df_historial[col].apply(lambda x: f"${x:,.2f}")
                
                st.dataframe(df_historial, use_container_width=True, hide_index=True)
            else:
                st.info("No hay ventas directas registradas en el sistema para mostrar.")
                
        except Exception as e:
            st.error(f"Error al cargar el historial: {e}")
