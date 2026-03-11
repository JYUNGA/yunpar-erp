import streamlit as st
import pandas as pd
import time
from io import BytesIO

def render(supabase):
    st.title("👕 Catálogo de Productos y Precios")
    tab1, tab2, tab3 = st.tabs(["🔍 Buscador y Edición", "➕ Nuevo (Automático)", "📂 Importar / Exportar"])

    # --- FUNCIONES AUXILIARES ---
    def obtener_opciones(campo):
        try:
            data = supabase.table('productos_catalogo').select(campo).eq('activo', True).execute().data
            lista = sorted(list(set([d[campo] for d in data if d[campo]])))
            return lista + ["➕ Crear Nuevo..."]
        except: return ["➕ Crear Nuevo..."]

    def generar_siguiente_codigo():
        """Calcula el siguiente código A000X basado en el máximo existente."""
        try:
            # Traemos TODOS los códigos (incluso los inactivos/borrados para no repetir secuencia)
            resp = supabase.table('productos_catalogo').select("codigo_referencia").execute()
            codigos = [d['codigo_referencia'] for d in resp.data]
            
            max_num = 0
            for c in codigos:
                # Solo analizamos los que tienen formato A#### (ignoramos los _DEL)
                if c.startswith("A") and len(c) == 5 and c[1:].isdigit():
                    num = int(c[1:])
                    if num > max_num:
                        max_num = num
            
            # Retornamos el siguiente
            return f"A{str(max_num + 1).zfill(4)}"
        except:
            return "A0001" # Si es el primero

    # ==============================================================================
    # TAB 1: BUSCADOR CON FILTROS COMPLETOS
    # ==============================================================================
    with tab1:
        st.subheader("Gestionar Catálogo")
        
        ver_inactivos = st.checkbox("Mostrar productos eliminados/archivados")
        
        query = supabase.table('productos_catalogo').select("*").order('codigo_referencia')
        if not ver_inactivos:
            query = query.eq('activo', True)
        resp = query.execute()
        df_prod = pd.DataFrame(resp.data)
        
        if not df_prod.empty:
            # --- ZONA DE FILTROS ---
            with st.expander("Filtros de Búsqueda", expanded=True):
                c1, c2, c3 = st.columns(3)
                
                tipos_disp = ["Todos"] + sorted(list(df_prod['tipo_prenda'].dropna().unique()))
                filtro_tipo = c1.selectbox("Prenda", tipos_disp)
                
                df_t = df_prod if filtro_tipo == "Todos" else df_prod[df_prod['tipo_prenda'] == filtro_tipo]
                cats_disp = ["Todos"] + sorted(list(df_t['linea_categoria'].dropna().unique()))
                filtro_cat = c2.selectbox("Categoría", cats_disp)

                edads_disp = ["Todos"] + sorted(list(df_prod['grupo_edad'].dropna().unique()))
                filtro_edad = c3.selectbox("Edad", edads_disp)
                
                # FILTROS DE PRODUCCIÓN
                st.caption("Características de Producción:")
                cf1, cf2, cf3, cf4 = st.columns(4)
                f_sub = cf1.checkbox("Solo Sublimado")
                f_dtf = cf2.checkbox("Solo DTF")
                f_bor = cf3.checkbox("Solo Bordado")
                f_busq = cf4.text_input("Buscar texto...", placeholder="Cód o Nombre")

            # --- APLICAR LÓGICA ---
            df_final = df_prod.copy()
            if filtro_tipo != "Todos": df_final = df_final[df_final['tipo_prenda'] == filtro_tipo]
            if filtro_cat != "Todos": df_final = df_final[df_final['linea_categoria'] == filtro_cat]
            if filtro_edad != "Todos": df_final = df_final[df_final['grupo_edad'] == filtro_edad]
            
            if f_sub: df_final = df_final[df_final['requiere_sublimado'] == True]
            if f_dtf: df_final = df_final[df_final['requiere_dtf'] == True]
            if f_bor: df_final = df_final[df_final['requiere_bordado'] == True]
                
            if f_busq:
                df_final = df_final[
                    df_final['descripcion'].str.contains(f_busq, case=False, na=False) | 
                    df_final['codigo_referencia'].str.contains(f_busq, case=False, na=False)
                ]

            st.caption(f"Resultados: {len(df_final)} productos.")
            
            # --- TABLA ---
            evento = st.dataframe(
                df_final[['codigo_referencia', 'descripcion', 'precio_unitario', 'tipo_prenda', 'activo']],
                use_container_width=True,
                hide_index=True,
                selection_mode="single-row",
                on_select="rerun"
            )
            
            # --- EDICIÓN REACTIVA ---
            if evento.selection.rows:
                idx = evento.selection.rows[0]
                item = df_final.iloc[idx]
                
                st.divider()
                st.markdown(f"### ✏️ Editando: :orange[{item['codigo_referencia']}]")
                
                list_tipo = obtener_opciones('tipo_prenda')
                list_cat = obtener_opciones('linea_categoria')
                list_edad = obtener_opciones('grupo_edad')
                def get_idx(lista, val): return lista.index(val) if val in lista else 0

                c_izq, c_der = st.columns([1, 1])
                
                with c_izq:
                    # TIPO
                    sel_t = st.selectbox("Tipo", list_tipo, index=get_idx(list_tipo, item['tipo_prenda']), key="e_t")
                    val_t = st.text_input("Nuevo Tipo", key="e_t_n").upper() if sel_t == "➕ Crear Nuevo..." else sel_t
                    
                    # CATEGORIA
                    sel_c = st.selectbox("Categoría", list_cat, index=get_idx(list_cat, item['linea_categoria']), key="e_c")
                    val_c = st.text_input("Nueva Cat.", key="e_c_n").upper() if sel_c == "➕ Crear Nuevo..." else sel_c

                    # EDAD
                    sel_e = st.selectbox("Edad", list_edad, index=get_idx(list_edad, item['grupo_edad']), key="e_e")
                    val_e = st.text_input("Nueva Edad", key="e_e_n").upper() if sel_e == "➕ Crear Nuevo..." else sel_e

                    desc = st.text_input("Descripción", value=item['descripcion'], key="e_desc")

                with c_der:
                    c1, c2, c3 = st.columns(3)
                    p1 = c1.number_input("Unitario", value=float(item['precio_unitario'] or 0))
                    p2 = c2.number_input("Docena", value=float(item['precio_docena'] or 0))
                    p3 = c3.number_input("Mayorista", value=float(item['precio_mayorista'] or 0))
                    
                    b1, b2, b3, b4 = st.columns(4)
                    ck_s = b1.checkbox("Sublim", value=item['requiere_sublimado'])
                    ck_d = b2.checkbox("DTF", value=item['requiere_dtf'])
                    ck_b = b3.checkbox("Bordado", value=item['requiere_bordado'])
                    ck_t = b4.checkbox("Ticket", value=item['requiere_ticket'])

                st.markdown("---")
                btn_save, btn_del = st.columns([2, 1])
                
                if btn_save.button("💾 GUARDAR CAMBIOS", type="primary"):
                    try:
                        supabase.table('productos_catalogo').update({
                            "descripcion": desc.upper(),
                            "tipo_prenda": val_t, "linea_categoria": val_c, "grupo_edad": val_e,
                            "precio_unitario": p1, "precio_docena": p2, "precio_mayorista": p3,
                            "requiere_sublimado": ck_s, "requiere_dtf": ck_d, 
                            "requiere_bordado": ck_b, "requiere_ticket": ck_t
                        }).eq('id', int(item['id'])).execute()
                        st.success("✅ Actualizado")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")

                if item['activo']:
                    if btn_del.button("🗑️ ELIMINAR Y LIBERAR CÓDIGO"):
                        try:
                            # Renombrar para liberar código
                            nuevo_cod_archivo = f"{item['codigo_referencia']}_DEL_{int(time.time())}"
                            supabase.table('productos_catalogo').update({
                                'activo': False,
                                'codigo_referencia': nuevo_cod_archivo,
                                'descripcion': f"[ELIMINADO] {item['descripcion']}" 
                            }).eq('id', int(item['id'])).execute()
                            
                            st.success(f"Código {item['codigo_referencia']} liberado.")
                            time.sleep(2)
                            st.rerun()
                        except Exception as e: st.error(f"Error: {e}")

    # ==============================================================================
    # TAB 2: NUEVO AUTOMÁTICO
    # ==============================================================================
    with tab2:
        st.subheader("Registrar Nuevo Producto")
        
        # 1. Calculamos el siguiente código automáticamente
        siguiente_cod = generar_siguiente_codigo()
        st.info(f"💡 El sistema ha asignado el código: **{siguiente_cod}**")

        list_tipo_n = obtener_opciones('tipo_prenda')
        list_cat_n = obtener_opciones('linea_categoria')
        list_edad_n = obtener_opciones('grupo_edad')

        with st.container(border=True):
            c1, c2 = st.columns([1, 3])
            
            # CAMPO BLOQUEADO (DISABLED)
            st.text_input("Código (Automático)", value=siguiente_cod, disabled=True)
            nuevo_desc = c2.text_input("Descripción *", key="n_desc_man")
            
            c3, c4, c5 = st.columns(3)
            
            sel_tn = c3.selectbox("Tipo", list_tipo_n, key="n_st")
            val_tn = c3.text_input("Nuevo Tipo", key="n_tt").upper() if sel_tn == "➕ Crear Nuevo..." else sel_tn
            
            sel_cn = c4.selectbox("Cat", list_cat_n, key="n_sc")
            val_cn = c4.text_input("Nueva Cat", key="n_tc").upper() if sel_cn == "➕ Crear Nuevo..." else sel_cn
                
            sel_en = c5.selectbox("Edad", list_edad_n, key="n_se")
            val_en = c5.text_input("Nueva Edad", key="n_te").upper() if sel_en == "➕ Crear Nuevo..." else sel_en
            
            st.write("---")
            cp1, cp2, cp3 = st.columns(3)
            np1 = cp1.number_input("Unitario", min_value=0.0, step=0.01, key="n_p1")
            np2 = cp2.number_input("Docena", min_value=0.0, step=0.01, key="n_p2")
            np3 = cp3.number_input("Mayorista", min_value=0.0, step=0.01, key="n_p3")
            
            cb1, cb2, cb3, cb4 = st.columns(4)
            n_s = cb1.checkbox("Sublim", key="n_b1")
            n_d = cb2.checkbox("DTF", key="n_b2")
            n_b = cb3.checkbox("Bordad", key="n_b3")
            n_t = cb4.checkbox("Ticket", key="n_b4")
            
            if st.button("💾 GUARDAR PRODUCTO NUEVO", type="primary"):
                if nuevo_desc and val_tn and val_cn:
                    try:
                        datos = {
                            "codigo_referencia": siguiente_cod, # Usamos el calculado
                            "descripcion": nuevo_desc.upper(),
                            "tipo_prenda": val_tn, "linea_categoria": val_cn, "grupo_edad": val_en,
                            "precio_unitario": np1, "precio_docena": np2, "precio_mayorista": np3,
                            "requiere_sublimado": n_s, "requiere_dtf": n_d, 
                            "requiere_bordado": n_b, "requiere_ticket": n_t,
                            "activo": True
                        }
                        supabase.table('productos_catalogo').insert(datos).execute()
                        st.balloons() # Celebración
                        st.success(f"Producto {siguiente_cod} creado exitosamente.")
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error técnico: {e}")
                else: st.warning("Falta Descripción, Tipo o Categoría.")

    # ==============================================================================
    # TAB 3: IMPORTAR / EXPORTAR
    # ==============================================================================
    with tab3:
        c_imp, c_exp = st.columns(2)
        with c_imp:
            st.subheader("🚀 Carga Masiva")
            archivo = st.file_uploader("Sube Lista Precios.xlsx", type=['xlsx'])
            if archivo and st.button("Procesar Archivo", type="primary"):
                with st.spinner("Procesando y guardando datos masivamente..."):
                    try:
                        df = pd.read_excel(archivo)
                        df.columns = df.columns.str.strip().str.upper() # Mantiene tu limpieza de columnas

                        # Traductor de booleanos super robusto
                        mapeo_booleanos = {
                            "VERDADERO": True, "FALSO": False, 
                            "TRUE": True, "FALSE": False, 
                            "SI": True, "NO": False,
                            "1": True, "0": False
                        }
                        
                        def limpiar_booleano(valor):
                            val_str = str(valor).strip().upper()
                            return mapeo_booleanos.get(val_str, False)

                        batch_productos = []

                        for i, row in df.iterrows():
                            try:
                                # Lógica para tu código
                                raw_cod = row.get('COD.') if 'COD.' in df.columns else row.get('ID', '')
                                
                                # Saltar filas vacías al final del excel
                                if pd.isna(raw_cod) or str(raw_cod).strip() == "":
                                    continue 
                                    
                                cod_final = f"A{str(int(raw_cod)).zfill(4)}" if isinstance(raw_cod, (int, float)) else str(raw_cod).strip()
                                
                                item = {
                                    "codigo_referencia": cod_final,
                                    "descripcion": str(row.get('DESCRIPCION', '')).strip(),
                                    "tipo_prenda": str(row.get('PRENDA', '')).strip().upper(),
                                    "linea_categoria": str(row.get('TELA|CATEG', '')).strip().upper(),
                                    "grupo_edad": str(row.get('EDAD', '')).strip().upper(),
                                    "precio_unitario": float(pd.to_numeric(row.get('UNI'), errors='coerce') or 0),
                                    "precio_docena": float(pd.to_numeric(row.get('>12'), errors='coerce') or 0),
                                    "precio_mayorista": float(pd.to_numeric(row.get('>25'), errors='coerce') or 0),
                                    "requiere_sublimado": limpiar_booleano(row.get('SUBLIMADO')),
                                    "requiere_ticket": limpiar_booleano(row.get('TICKET')),
                                    "requiere_dtf": limpiar_booleano(row.get('DTF')),
                                    "requiere_bordado": limpiar_booleano(row.get('BORDADO')),
                                    "activo": True
                                }
                                batch_productos.append(item)
                            except Exception:
                                pass # Ignorar fila si está corrupta y continuar con la siguiente
                                
                        # Inserción masiva usando tu misma regla de UPSERT
                        if batch_productos:
                            supabase.table('productos_catalogo').upsert(batch_productos, on_conflict="codigo_referencia").execute()
                            st.success(f"✅ ¡Se procesaron {len(batch_productos)} productos correctamente!")
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.warning("⚠️ No se encontraron productos válidos en el archivo.")

                    except Exception as e: 
                        st.error(f"Error crítico al leer el archivo: {e}")

        with c_exp:
            st.subheader("📤 Respaldo")
            if st.button("Generar Excel"):
                try:
                    resp = supabase.table('productos_catalogo').select("*").execute()
                    df_back = pd.DataFrame(resp.data)
                    if not df_back.empty:
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            df_back.to_excel(writer, index=False, sheet_name='Productos')
                        st.download_button(label="Descargar .xlsx", data=output.getvalue(), file_name="Productos_Respaldo.xlsx")
                except: pass
