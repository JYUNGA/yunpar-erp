import streamlit as st
import pandas as pd
from datetime import datetime
import time
import uuid
import os

# --- FUNCIONES DE SUBIDA DE IMÁGENES (Adaptadas de produccion.py) ---
def subir_img_apu(supabase, archivo_streamlit):
    try:
        file_bytes = archivo_streamlit.getvalue()
        _, extension = os.path.splitext(archivo_streamlit.name)
        extension = extension.lower()
        if not extension: extension = ".jpg"
        
        content_type = "image/jpeg"
        if extension == ".png": content_type = "image/png"
            
        nombre = f"apuntes_apus/{int(time.time())}_{uuid.uuid4()}{extension}"
        
        supabase.storage.from_("ordenes_produccion").upload(
            path=nombre, file=file_bytes, file_options={"content-type": content_type}
        )
        return supabase.storage.from_("ordenes_produccion").get_public_url(nombre)
    except Exception as e: 
        st.error(f"Error subida imagen: {e}")
        return None

def borrar_img_apu(supabase, url_archivo):
    if not url_archivo: return
    try:
        ruta_relativa = url_archivo.split("/ordenes_produccion/")[-1]
        supabase.storage.from_("ordenes_produccion").remove([ruta_relativa])
    except Exception as e:
        print(f"No se pudo borrar imagen antigua: {e}")

# --- MÓDULO PRINCIPAL ---
def render(supabase):
    # 1. SEGURIDAD ESTRICTA
    rol_actual = st.session_state.get('rol', '').upper()
    if rol_actual != "GERENTE":
        st.error("🚫 Acceso Denegado. Solo el Gerente puede gestionar APUs y Costos.")
        st.stop()

    st.title("⚙️ Fichas de Costos (APUs)")
    st.markdown("Gestiona la receta (materiales) y los apuntes de rendimiento de cada producto.")

    # 2. SELECTOR DE PRODUCTO
    productos = supabase.table('productos_catalogo').select("id, codigo_referencia, descripcion, precio_unitario, precio_docena, precio_mayorista").eq('activo', True).execute().data
    if not productos:
        st.warning("No hay productos activos en el catálogo.")
        return

    mapa_prod = {f"{p['codigo_referencia']} | {p['descripcion']}": p for p in productos}
    sel_prod = st.selectbox("🔍 Selecciona un Producto para ver/editar su APU", list(mapa_prod.keys()))
    
    if not sel_prod: return
    prod_obj = mapa_prod[sel_prod]
    pid = prod_obj['id']

    st.divider()

    # 3. MÉTRICAS DE RENTABILIDAD
    res_receta = supabase.table('fichas_costos').select("*, insumos(id, nombre, costo_unitario, unidad_medida)").eq('producto_id', pid).execute()
    receta = res_receta.data
    
    costo_total_materiales = sum(float(r['cantidad_por_unidad']) * float(r['insumos']['costo_unitario']) for r in receta)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Precio Unitario", f"${prod_obj['precio_unitario']:.2f}")
    m2.metric("Precio Docena", f"${prod_obj['precio_docena']:.2f}")
    m3.metric("Costo Materiales APU", f"${costo_total_materiales:.2f}")
    
    margen = prod_obj['precio_unitario'] - costo_total_materiales if prod_obj['precio_unitario'] > 0 else 0
    pct_margen = (margen / prod_obj['precio_unitario'] * 100) if prod_obj['precio_unitario'] > 0 else 0
    
    if pct_margen >= 50:
        m4.metric("Margen Unitario", f"${margen:.2f} ({pct_margen:.1f}%)")
    elif pct_margen >= 30:
        m4.metric("Margen Unitario", f"${margen:.2f} ({pct_margen:.1f}%)")
    else:
        m4.metric("Margen Unitario", f"${margen:.2f} ({pct_margen:.1f}%)")

    tab_receta, tab_apuntes = st.tabs(["🧵 Receta / Materiales", "📸 Apuntes y Rendimientos"])

    # =========================================================================
    # TAB 1: RECETA DE MATERIALES
    # =========================================================================
    with tab_receta:
        st.markdown("#### Agregar Insumo a la Receta")
        insumos = supabase.table('insumos').select("id, nombre, unidad_medida, costo_unitario").eq('activo', True).execute().data
        mapa_ins = {f"{i['nombre']} (${i['costo_unitario']:.2f}/{i['unidad_medida']})": i for i in insumos}

        c1, c2, c3 = st.columns([3, 1, 1])
        sel_ins = c1.selectbox("Seleccionar Insumo", list(mapa_ins.keys()), key=f"sel_ins_{pid}")
        cant_ins = c2.number_input("Cant x Unidad", min_value=0.001, format="%.3f", key=f"cant_ins_{pid}")
        
        if c3.button("➕ Agregar", use_container_width=True):
            if sel_ins and cant_ins > 0:
                obj_ins = mapa_ins[sel_ins]
                try:
                    supabase.table('fichas_costos').insert({
                        "producto_id": pid, "insumo_id": obj_ins['id'], "cantidad_por_unidad": cant_ins
                    }).execute()
                    st.success("Insumo agregado al APU")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                        st.warning("Este insumo ya está en la receta. Elimínalo primero si quieres cambiar la cantidad.")
                    else:
                        st.error(f"Error: {e}")

        st.markdown("#### Receta Actual")
        if receta:
            df_receta = pd.DataFrame([{
                "ID": r['id'],
                "Insumo": r['insumos']['nombre'],
                "Unidad": r['insumos']['unidad_medida'],
                "Cant.": r['cantidad_por_unidad'],
                "Costo Unit.": r['insumos']['costo_unitario'],
                "Costo Total": float(r['cantidad_por_unidad']) * float(r['insumos']['costo_unitario'])
            } for r in receta])

            st.dataframe(df_receta[['Insumo', 'Unidad', 'Cant.', 'Costo Unit.', 'Costo Total']], use_container_width=True, hide_index=True)
            
            # Botón para eliminar
            with st.expander("🗑️ Eliminar Insumo de la Receta"):
                id_borrar = st.number_input("Ingresa el ID del insumo a eliminar", min_value=1, step=1, key=f"del_ins_{pid}")
                if st.button("Borrar Insumo", type="secondary"):
                    supabase.table('fichas_costos').delete().eq('id', id_borrar).execute()
                    st.success("Eliminado"); time.sleep(0.5); st.rerun()
        else:
            st.info("Este producto no tiene insumos asignados todavía.")

    # =========================================================================
    # TAB 2: APUNTES E IMÁGENES (N CANTIDAD)
    # =========================================================================
    with tab_apuntes:
        st.markdown("##### 📸 Subir Apuntes Manuales (Rendimientos, Cortes, etc.)")
        st.caption("Puedes subir múltiples imágenes. Quedarán guardadas como ayuda memoria para este producto.")
        
        archivos = st.file_uploader("Seleccionar imágenes", type=["jpg", "png", "jpeg"], accept_multiple_files=True, key=f"up_apu_{pid}")
        
        if archivos:
            if st.button(f"💾 Subir {len(archivos)} imagen(es)", type="primary"):
                with st.spinner("Subiendo..."):
                    for arch in archivos:
                        url = subir_img_apu(supabase, arch)
                        if url:
                            supabase.table('apu_imagenes').insert({"producto_id": pid, "url_imagen": url}).execute()
                    st.success("Imágenes guardadas correctamente")
                    time.sleep(0.5)
                    st.rerun()

        st.divider()
        st.markdown("##### 📂 Galería de Apuntes Guardados")
        imagenes_db = supabase.table('apu_imagenes').select("*").eq('producto_id', pid).order('created_at', desc=True).execute().data
        
        if imagenes_db:
            # Mostrar en columnas de 3
            cols = st.columns(3)
            for i, img in enumerate(imagenes_db):
                with cols[i % 3]:
                    st.image(img['url_imagen'], use_container_width=True)
                    if st.button("🗑️ Quitar", key=f"del_img_apu_{img['id']}"):
                        borrar_img_apu(supabase, img['url_imagen'])
                        supabase.table('apu_imagenes').delete().eq('id', img['id']).execute()
                        st.rerun()
        else:
            st.info("Aún no hay apuntes adjuntos para este producto.")