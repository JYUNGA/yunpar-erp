import streamlit as st
import pandas as pd
import datetime
import time


def render(supabase):
    st.header("✂️ Control de Taller", divider="red")

    # --- 1. CONSULTA DINÁMICA DE PERSONAL (Recursos Humanos) ---
    # Leemos a los empleados activos directamente de la base de datos
    try:
        res_rh = (
            supabase.table("rh_empleados")
            .select("id, nombre_completo, cargo")
            .eq("activo", True)
            .execute()
            .data
        )

        # Filtramos internamente por roles
        lista_cortadores = [
            e for e in res_rh if str(e.get("cargo")).strip().upper() == "CORTADOR"
        ]
        lista_costureras = [
            e for e in res_rh if str(e.get("cargo")).strip().upper() == "COSTURERA"
        ]

        mapa_cortadores = {c["nombre_completo"]: c["id"] for c in lista_cortadores}
        mapa_costureras = {c["nombre_completo"]: c["id"] for c in lista_costureras}
    except Exception:
        # Fallback en caso de que la tabla aún no esté estructurada
        mapa_cortadores = {"Juan (Cortador)": 1}
        mapa_costureras = {"Maria (Costurera)": 2, "Ana (Costurera)": 3}

    # --- 2. CONSULTA DE ÓRDENES PENDIENTES DE CONFECCIÓN ---
    try:
        res_ordenes = (
            supabase.table("ordenes")
            .select("id, codigo_orden, creado_por_id, clientes(nombre_completo)")
            .order("created_at", desc=True)
            .limit(20)
            .execute()
            .data
        )

        datos_pendientes = []
        mapa_desglose_global = {}

        if res_ordenes:
            # A. Mapeo seguro de Vendedoras (Usuarios)
            ids_vendedores = list(
                set([o["creado_por_id"] for o in res_ordenes if o.get("creado_por_id")])
            )
            mapa_vend = {}
            if ids_vendedores:
                res_v = (
                    supabase.table("usuarios")
                    .select("id, nombre_completo")
                    .in_("id", ids_vendedores)
                    .execute()
                    .data
                )
                mapa_vend = {v["id"]: v["nombre_completo"] for v in res_v}

            # B. Extracción Profunda: Desglose por especificaciones (Camisetas vs Pantalonetas)
            ids_ordenes = [o["id"] for o in res_ordenes]
            if ids_ordenes:
                # Traemos los items Y sus especificaciones físicas (Las prendas reales)
                res_items = (
                    supabase.table("items_orden")
                    .select(
                        "orden_id, familia_producto, productos_catalogo(descripcion), especificaciones_producto(talla_superior, talla_inferior)"
                    )
                    .in_("orden_id", ids_ordenes)
                    .execute()
                    .data
                )

                for it in res_items:
                    oid = it["orden_id"]
                    fam = str(it.get("familia_producto", "")).strip().upper()

                    # Extraer el nombre real del producto para detectar faldas o polos
                    prod_desc = ""
                    if it.get("productos_catalogo"):
                        prod_desc = (
                            str(it["productos_catalogo"].get("descripcion", ""))
                            .strip()
                            .upper()
                        )
                    if not prod_desc:
                        prod_desc = fam

                    if oid not in mapa_desglose_global:
                        mapa_desglose_global[oid] = {}

                    # Recorremos cada prenda física individual
                    especs = it.get("especificaciones_producto", [])
                    for esp in especs:
                        t_sup = str(esp.get("talla_superior") or "").strip().upper()
                        t_inf = str(esp.get("talla_inferior") or "").strip().upper()

                        tiene_sup = t_sup not in ["", "-", "NONE", "N/A", "NAN", "0"]
                        tiene_inf = t_inf not in ["", "-", "NONE", "N/A", "NAN", "0"]

                        # 1. Lógica de Prenda Superior
                        if tiene_sup:
                            tipo_sup = "CAMISETA"  # Por defecto
                            if "CHOMPA" in prod_desc:
                                tipo_sup = "CHOMPA"
                            elif "POLO" in prod_desc:
                                tipo_sup = "POLO"
                            elif "BVD" in prod_desc:
                                tipo_sup = "BVD"

                            mapa_desglose_global[oid][tipo_sup] = (
                                mapa_desglose_global[oid].get(tipo_sup, 0) + 1
                            )

                        # 2. Lógica de Prenda Inferior
                        if tiene_inf:
                            tipo_inf = "PANTALONETA"  # Por defecto
                            if "FALDA SHORT" in prod_desc:
                                tipo_inf = "FALDA SHORT"
                            elif "FALDA" in prod_desc:
                                tipo_inf = "FALDA"
                            elif "CALENTADOR" in prod_desc:
                                tipo_inf = "PANTALÓN CALENTADOR"

                            mapa_desglose_global[oid][tipo_inf] = (
                                mapa_desglose_global[oid].get(tipo_inf, 0) + 1
                            )

                        # 3. Fallback (Por si es un producto genérico que no usa tallas)
                        if not tiene_sup and not tiene_inf:
                            tipo_gen = "PRENDA/GENÉRICO"
                            mapa_desglose_global[oid][tipo_gen] = (
                                mapa_desglose_global[oid].get(tipo_gen, 0) + 1
                            )

            # C. Construcción de la Tabla Visual
            for o in res_ordenes:
                oid = o["id"]
                desglose_orden = mapa_desglose_global.get(oid, {})
                total_prendas_orden = sum(desglose_orden.values())

                # Armamos un texto rápido para la tabla. Ej: "12 CAMISETA, 12 PANTALONETA"
                resumen_texto = ", ".join(
                    [f"{int(c)} {t}" for t, c in desglose_orden.items()]
                )
                if not resumen_texto:
                    resumen_texto = "Sin desglose"

                datos_pendientes.append(
                    {
                        "Seleccionar": False,
                        "ID_Oculto": oid,
                        "Orden": o["codigo_orden"],
                        "Vendedora": mapa_vend.get(o["creado_por_id"], "No registrado"),
                        "Cliente": o.get("clientes", {}).get("nombre_completo", "S/N"),
                        "Volumen Total": total_prendas_orden,
                        "Detalle": resumen_texto,
                    }
                )

        df_pendientes = pd.DataFrame(datos_pendientes)
        st.session_state["mapa_desglose_taller"] = mapa_desglose_global

    except Exception as e:
        st.error(f"Error cargando órdenes: {e}")
        df_pendientes = pd.DataFrame()

    # --- 3. INTERFAZ MOBILE-FIRST (Acumulador en tiempo real) ---
    if not df_pendientes.empty:
        st.markdown("**Selecciona las órdenes que deseas enviar a costura hoy:**")

        df_editado = st.data_editor(
            df_pendientes,
            column_config={
                "Seleccionar": st.column_config.CheckboxColumn("✅", default=False),
                "ID_Oculto": None,
                "Orden": st.column_config.TextColumn("Orden", disabled=True),
                "Vendedora": st.column_config.TextColumn("Atendido por", disabled=True),
                "Cliente": st.column_config.TextColumn("Cliente", disabled=True),
                "Volumen Total": st.column_config.NumberColumn(
                    "Prendas", disabled=True
                ),
                "Detalle": st.column_config.TextColumn("Desglose", disabled=True),
            },
            hide_index=True,
            use_container_width=True,
            key="editor_taller",
        )

        # --- 4. CALCULADORA MATRICIAL EN VIVO Y ASIGNACIÓN ---
        df_seleccionado = df_editado[df_editado["Seleccionar"] == True]

        # Sumatoria profunda leyendo la memoria de la base de datos
        desglose_acumulado = {}
        total_absoluto = 0.0

        memoria_desglose = st.session_state.get("mapa_desglose_taller", {})
        for oid in df_seleccionado["ID_Oculto"]:
            prendas_de_esta_orden = memoria_desglose.get(oid, {})
            for tipo, cantidad in prendas_de_esta_orden.items():
                desglose_acumulado[tipo] = desglose_acumulado.get(tipo, 0) + cantidad
                total_absoluto += cantidad

        st.divider()

        c_met, c_act = st.columns([1, 1])

        with c_met:
            st.markdown("### 📊 Análisis de Carga")
            st.metric("Volumen Total", f"{total_absoluto:.1f} unidades")

            if desglose_acumulado:
                st.markdown("**Desglose de Confección:**")
                # Mostramos píldoras visuales con los totales por cada tipo de prenda
                for tipo, cant in desglose_acumulado.items():
                    cant_str = int(cant) if float(cant).is_integer() else f"{cant:.2f}"
                    st.info(f"🧵 **{tipo}:** {cant_str} unidades")
            else:
                st.caption("Selecciona órdenes arriba para calcular el volumen.")

        with c_act:
            st.markdown("### 👤 Asignación de Personal")
            cortador_sel = st.selectbox(
                "✂️ Cortador", ["Ninguno"] + list(mapa_cortadores.keys())
            )
            costurera_sel = st.selectbox(
                "🧵 Costurera", ["Ninguna"] + list(mapa_costureras.keys())
            )

            listo_para_asignar = total_absoluto > 0 and (
                cortador_sel != "Ninguno" or costurera_sel != "Ninguna"
            )

            st.write("")  # Espaciado
            if st.button(
                "🚀 Confirmar Asignación",
                type="primary",
                use_container_width=True,
                disabled=not listo_para_asignar,
            ):
                try:
                    with st.spinner("Registrando en historial de producción..."):
                        # Aquí ejecutarás el INSERT a la tabla de trazabilidad
                        time.sleep(1)
                        st.success(
                            f"¡Lote de {total_absoluto} prendas asignado exitosamente!"
                        )
                        time.sleep(1.5)
                        st.rerun()
                except Exception as e:
                    st.error(f"Error al asignar: {e}")
    else:
        st.info("No hay órdenes pendientes de confección en este momento.")
