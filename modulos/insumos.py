import streamlit as st
import pandas as pd
import datetime
import time
from io import BytesIO

def render(supabase):
    st.title("🧵 Gestión de Insumos")
    tab1, tab2, tab3 = st.tabs(["🔍 Buscador y Edición", "➕ Nuevo Manual", "📂 Importar / Exportar"])

    # --- CATEGORÍAS Y UNIDADES DINÁMICAS DESDE LA BD ---
    try:
        # Traemos ambos campos en un solo consulta para optimizar
        res_datos = supabase.table('insumos').select("categoria, unidad_medida").execute()
        cats_db = sorted(list(set([d['categoria'] for d in res_datos.data if d['categoria']])))
        unds_db = sorted(list(set([d['unidad_medida'] for d in res_datos.data if d['unidad_medida']])))
    except:
        cats_db, unds_db = [], []

    CATEGORIAS_BASE = ["TELA", "HILO", "PAPEL", "TINTA", "OTROS", "SERVICIOS"]
    CATEGORIAS = sorted(list(set(cats_db + CATEGORIAS_BASE)))
    OPCION_NUEVA_CAT = "➕ Nueva Categoría..."

    UNIDADES_BASE = ["METRO", "KG", "ROLLO", "UNIDAD", "LITRO", "CARRETE"]
    UNIDADES = sorted(list(set(unds_db + UNIDADES_BASE)))
    OPCION_NUEVA_UND = "➕ Nueva Unidad..."

    # --- FUNCIONES AUXILIARES ---
    def generar_cod_insumo():
        try:
            res = supabase.table('insumos').select("codigo_insumo").execute()
            nums = []
            for d in res.data:
                s = d['codigo_insumo']
                if s.startswith("M") and s[1:].isdigit():
                    nums.append(int(s[1:]))
            if nums:
                return f"M{max(nums) + 1}"
            return "M1"
        except:
            return "M1"

    # ==============================================================================
    # TAB 1: LISTADO AVANZADO Y EDICIÓN
    # ==============================================================================
    with tab1:
        st.subheader("Inventario de Materiales")
        
        # 1. Cargar Datos
        ver_todos = st.checkbox("Ver eliminados/inactivos", key="ins_chk_ver")
        q = supabase.table('insumos').select("*").order('codigo_insumo')
        if not ver_todos:
            q = q.eq('activo', True)
        res = q.execute()
        df_ins = pd.DataFrame(res.data)
        
        if not df_ins.empty:
            # 2. Filtros
            with st.expander("🔍 Filtros de Búsqueda", expanded=True):
                c1, c2, c3 = st.columns(3)
                
                # Filtro Categoría
                cats = ["Todas"] + sorted(list(df_ins['categoria'].unique()))
                f_cat = c1.selectbox("Filtrar por Categoría", cats)
                
                # Filtro Unidad
                units = ["Todas"] + sorted(list(df_ins['unidad_medida'].unique()))
                f_und = c2.selectbox("Filtrar por Unidad", units)
                
                # Buscador Texto
                busq = c3.text_input("Buscar por Nombre o Código...")

            # 3. Aplicar Filtros
            df_show = df_ins.copy()
            if f_cat != "Todas":
                df_show = df_show[df_show['categoria'] == f_cat]
            if f_und != "Todas":
                df_show = df_show[df_show['unidad_medida'] == f_und]
            if busq: 
                df_show = df_show[
                    df_show['nombre'].str.contains(busq, case=False, na=False) | 
                    df_show['codigo_insumo'].str.contains(busq, case=False, na=False)
                ]
            
            st.caption(f"Resultados: {len(df_show)} insumos.")

            # 4. Tabla Interactiva
            evt = st.dataframe(
                df_show[['codigo_insumo', 'categoria', 'nombre', 'unidad_medida', 'costo_unitario', 'activo']], 
                use_container_width=True, 
                selection_mode="single-row", 
                on_select="rerun", 
                hide_index=True
            )
            
            # 5. ZONA DE EDICIÓN Y BORRADO
            if evt.selection.rows:
                idx = evt.selection.rows[0]
                item = df_show.iloc[idx]
                
                st.divider()
                st.markdown(f"### ✏️ Editando: :orange[{item['nombre']}]")
                
                with st.form("edit_insumo_form"):
                    c_e1, c_e2, c_e3 = st.columns(3)
                    
                    opciones_cat_edit = CATEGORIAS + [OPCION_NUEVA_CAT]
                    idx_cat = opciones_cat_edit.index(item['categoria']) if item['categoria'] in opciones_cat_edit else 0
                    new_cat_sel = c_e1.selectbox("Categoría", opciones_cat_edit, index=idx_cat)
                    new_cat_extra = st.text_input("Nombre nueva categoría", key="edit_nueva_cat") if new_cat_sel == OPCION_NUEVA_CAT else ""
                    new_cat = new_cat_extra.strip().upper() if new_cat_sel == OPCION_NUEVA_CAT else new_cat_sel
                    
                    new_nom = c_e2.text_input("Descripción", value=item['nombre'])
                    
                    opciones_und_edit = UNIDADES + [OPCION_NUEVA_UND]
                    idx_und = opciones_und_edit.index(item['unidad_medida']) if item['unidad_medida'] in opciones_und_edit else 0
                    new_und_sel = c_e3.selectbox("Unidad", opciones_und_edit, index=idx_und)
                    new_und_extra = st.text_input("Nombre nueva unidad", key="edit_nueva_und") if new_und_sel == OPCION_NUEVA_UND else ""
                    new_und = new_und_extra.strip().upper() if new_und_sel == OPCION_NUEVA_UND else new_und_sel
                    
                    c_e4, c_e5 = st.columns(2)
                    new_cost = c_e4.number_input("Costo Unitario ($)", value=float(item['costo_unitario']), format="%.4f")
                    new_act = c_e5.checkbox("Activo / Visible", value=item['activo'])
                    
                    # Botones de Acción
                    col_save, col_del = st.columns([1, 1])
                    
                    guardar = col_save.form_submit_button("💾 Actualizar Datos")
                    borrar = col_del.form_submit_button("🗑️ ELIMINAR INSUMO")
                    
                    if guardar:
                        supabase.table('insumos').update({
                            "categoria": new_cat, "nombre": new_nom.upper(),
                            "unidad_medida": new_und, "costo_unitario": new_cost, "activo": new_act
                        }).eq('id', int(item['id'])).execute()
                        st.success("✅ Insumo actualizado correctamente.")
                        time.sleep(1); st.rerun()
                        
                    if borrar:
                        # Borrado Lógico
                        supabase.table('insumos').update({'activo': False}).eq('id', int(item['id'])).execute()
                        st.warning(f"Insumo {item['codigo_insumo']} desactivado/eliminado.")
                        time.sleep(1); st.rerun()

        else:
            st.info("No hay insumos registrados. Ve a la pestaña 'Importar Excel' o crea uno nuevo.")

    # ==============================================================================
    # TAB 2: NUEVO MANUAL (CÓDIGO AUTOMÁTICO)
    # ==============================================================================
    with tab2:
        st.subheader("Registrar Nuevo Material")
        auto_cod = generar_cod_insumo()
        
        with st.form("new_insumo"):
            c1, c2 = st.columns([1, 3])
            n_cod = c1.text_input("Código (Automático)", value=auto_cod, disabled=True)
            n_nom = c2.text_input("Descripción del Material *")
            
            c3, c4, c5 = st.columns(3)
            opciones_cat_new = CATEGORIAS + [OPCION_NUEVA_CAT]
            n_cat_sel = c3.selectbox("Categoría", opciones_cat_new)
            n_cat_extra = c3.text_input("Nueva categoría", key="new_nueva_cat") if n_cat_sel == OPCION_NUEVA_CAT else ""
            n_cat = n_cat_extra.strip().upper() if n_cat_sel == OPCION_NUEVA_CAT else n_cat_sel
            opciones_und_new = UNIDADES + [OPCION_NUEVA_UND]
            n_und_sel = c4.selectbox("Unidad", opciones_und_new)
            n_und_extra = c4.text_input("Nueva unidad", key="new_nueva_und") if n_und_sel == OPCION_NUEVA_UND else ""
            n_und = n_und_extra.strip().upper() if n_und_sel == OPCION_NUEVA_UND else n_und_sel
            n_cos = c5.number_input("Costo Unitario ($)", min_value=0.0, format="%.4f")
            
            if st.form_submit_button("Guardar Material"):
                if n_nom and n_cat and n_und:
                    try:
                        supabase.table('insumos').insert({
                            "codigo_insumo": auto_cod, "categoria": n_cat, "nombre": n_nom.upper(),
                            "unidad_medida": n_und, "costo_unitario": n_cos, "activo": True
                        }).execute()
                        st.success(f"Material {n_nom} creado con código {auto_cod}"); time.sleep(1.5); st.rerun()
                    except Exception as e: st.error(f"Error: {e}")
                else: st.warning("Falta la descripción, categoría o unidad.")

    # ==============================================================================
    # TAB 3: IMPORTAR / EXPORTAR
    # ==============================================================================
    with tab3:
        col_imp, col_exp = st.columns(2)
        
        # 1. EXPORTAR
        with col_exp:
            st.subheader("📤 Respaldo")
            st.write("Descarga tu inventario actual.")
            if st.button("Generar Excel Insumos"):
                try:
                    res_back = supabase.table('insumos').select("*").execute()
                    df_back = pd.DataFrame(res_back.data)
                    if not df_back.empty:
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            df_back.to_excel(writer, index=False, sheet_name='Insumos')
                        st.download_button(label="💾 Descargar .xlsx", data=output.getvalue(), file_name=f"Insumos_{datetime.date.today()}.xlsx")
                    else: st.warning("No hay datos para exportar.")
                except Exception as e: st.error(f"Error exportando: {e}")

        # 2. IMPORTAR
        with col_imp:
            st.subheader("📥 Carga Masiva")
            st.markdown("Excel debe tener columnas: **ID, TIPO, DESCRIPCION, UNIDAD, COSTO**")
            archivo = st.file_uploader("Sube tu archivo Excel/CSV", type=['xlsx', 'csv'])
            
            if archivo and st.button("🚀 Procesar Carga"):
                with st.spinner("Leyendo archivo..."):
                    try:
                        if archivo.name.endswith('xlsx'): df = pd.read_excel(archivo)
                        else: df = pd.read_csv(archivo)
                        
                        df.columns = df.columns.str.strip().str.upper()
                        
                        progress_bar = st.progress(0)
                        total_rows = len(df)
                        success_count = 0
                        
                        for i, row in df.iterrows():
                            try:
                                item = {
                                    "codigo_insumo": str(row.get('ID')).strip(),
                                    "categoria": str(row.get('TIPO', 'GENERAL')).strip().upper(),
                                    "nombre": str(row.get('DESCRIPCION', '')).strip().upper(),
                                    "unidad_medida": str(row.get('UNIDAD', 'UNIDAD')).strip().upper(),
                                    "costo_unitario": float(row.get('COSTO', 0)),
                                    "activo": True
                                }
                                supabase.table('insumos').upsert(item, on_conflict="codigo_insumo").execute()
                                success_count += 1
                            except: pass
                            progress_bar.progress((i + 1) / total_rows)
                        
                        st.success(f"✅ ¡Proceso Terminado! Se cargaron/actualizaron {success_count} insumos.")
                        time.sleep(3); st.rerun()
                        
                    except Exception as e: st.error(f"Error crítico en el archivo: {e}")