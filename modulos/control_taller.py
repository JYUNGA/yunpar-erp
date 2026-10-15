import streamlit as st
import pandas as pd
import datetime
import time
import io
from fpdf import FPDF


# Pesos por tipo de prenda para COSTURA (1 = prenda simple). Ajustables desde la UI.
# El cortador cuenta 1 por cada prenda; las costureras usan estos pesos.
PESOS_POR_PRENDA = {
    "CAMISETA": 1.0,
    "POLO": 1.0,
    "BVD": 0.8,
    "CHOMPA": 2.5,
    "PANTALONETA": 1.0,
    "FALDA SHORT": 1.0,
    "FALDA": 1.2,
    "PANTALÓN CALENTADOR": 1.5,
    "PRENDA/GENÉRICO": 1.0,
}

TIPOS_PRENDA = list(PESOS_POR_PRENDA.keys())


def _limpiar_texto_pdf(texto):
    """Reemplaza caracteres Unicode que FPDF (latin-1) no soporta."""
    if not texto:
        return ""
    t = str(texto)
    reemplazos = {
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u2022": "-",
    }
    for a, b in reemplazos.items():
        t = t.replace(a, b)
    return t.encode("latin-1", "ignore").decode("latin-1")


class PDFInformeTaller(FPDF):
    def __init__(self, titulo):
        super().__init__()
        self.titulo = titulo

    def header(self):
        try:
            self.image("Logo_Yunpar.png", x=10, y=8, w=50)
        except Exception:
            pass
        self.set_y(20)
        self.set_font("helvetica", "B", 16)
        self.set_text_color(0, 51, 153)
        self.cell(0, 10, _limpiar_texto_pdf(self.titulo), align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.set_draw_color(200, 200, 200)
        self.line(10, self.get_y() + 2, 200, self.get_y() + 2)
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(100, 100, 100)
        self.cell(
            0,
            10,
            f"Documento Interno de Taller  |  Página {self.page_no()}/{{nb}}",
            align="C",
        )
        self.set_text_color(0, 0, 0)


def generar_informe_taller(ordenes_seleccionadas, pesos, tipo):
    """Genera un PDF de informe de taller. tipo = 'CORTE' o 'COSTURA'."""
    es_corte = tipo == "CORTE"
    titulo = "INFORME DE CORTE" if es_corte else "INFORME DE CONFECCIÓN (COSTURA)"
    pdf = PDFInformeTaller(titulo)
    pdf.add_page()

    hoy = datetime.date.today().strftime("%d/%m/%Y")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 6, _limpiar_texto_pdf(f"Fecha: {hoy}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # --- Tabla por orden ---
    a_orden, a_cliente, a_cant = 70, 90, 30
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(a_orden, 8, "Orden", border=1)
    pdf.cell(a_cliente, 8, "Cliente", border=1)
    pdf.cell(a_cant, 8, "Prendas" if es_corte else "Puntos", border=1, align="R")
    pdf.ln(8)

    pdf.set_font("helvetica", "", 10)
    total_general = 0.0
    for o in ordenes_seleccionadas:
        desglose = o.get("desglose", {})
        if es_corte:
            valor = int(sum(desglose.values()))
        else:
            valor = sum(cant * float(pesos.get(tp, 1.0)) for tp, cant in desglose.items())
        total_general += valor
        pdf.cell(a_orden, 7, _limpiar_texto_pdf(o.get("orden", "")), border=1)
        pdf.cell(a_cliente, 7, _limpiar_texto_pdf(o.get("cliente", "")), border=1)
        pdf.cell(
            a_cant,
            7,
            str(int(valor)) if es_corte else f"{valor:,.1f}",
            border=1,
            align="R",
        )
        pdf.ln(7)

    pdf.set_font("helvetica", "B", 11)
    pdf.cell(a_orden + a_cliente, 8, "TOTAL", border=1, align="R")
    pdf.cell(
        a_cant,
        8,
        str(int(total_general)) if es_corte else f"{total_general:,.1f}",
        border=1,
        align="R",
    )
    pdf.ln(8)
    pdf.ln(5)

    # --- Resumen por tipo de prenda ---
    desglose_acum = {}
    for o in ordenes_seleccionadas:
        for tp, cant in o.get("desglose", {}).items():
            desglose_acum[tp] = desglose_acum.get(tp, 0) + cant

    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 8, "Resumen por tipo de prenda", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("helvetica", "B", 10)
    if es_corte:
        pdf.cell(120, 8, "Tipo de prenda", border=1)
        pdf.cell(70, 8, "Cantidad (cada una = 1)", border=1, align="R")
        pdf.ln(8)
    else:
        pdf.cell(80, 8, "Tipo de prenda", border=1)
        pdf.cell(40, 8, "Cantidad", border=1, align="R")
        pdf.cell(40, 8, "Peso", border=1, align="R")
        pdf.cell(30, 8, "Subtotal", border=1, align="R")
        pdf.ln(8)

    pdf.set_font("helvetica", "", 10)
    for tp, cant in sorted(desglose_acum.items(), key=lambda x: -x[1]):
        if es_corte:
            pdf.cell(120, 7, _limpiar_texto_pdf(tp), border=1)
            pdf.cell(70, 7, str(int(cant)), border=1, align="R")
        else:
            peso = float(pesos.get(tp, 1.0))
            subtotal = cant * peso
            pdf.cell(80, 7, _limpiar_texto_pdf(tp), border=1)
            pdf.cell(40, 7, str(int(cant)), border=1, align="R")
            pdf.cell(40, 7, f"{peso:.1f}", border=1, align="R")
            pdf.cell(30, 7, f"{subtotal:,.1f}", border=1, align="R")
        pdf.ln(7)

    return bytes(pdf.output())


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
        res_ordenes = supabase.table("ordenes").select(
            "id, codigo_orden, creado_por_id, clientes(nombre_completo)"
        ).order("created_at", desc=True).limit(20).execute().data
        
        datos_pendientes = []
        mapa_desglose_global = {} 
        
        if res_ordenes:
            # A. Mapeo seguro de Vendedoras (Usuarios)
            ids_vendedores = list(set([o["creado_por_id"] for o in res_ordenes if o.get("creado_por_id")]))
            mapa_vend = {}
            if ids_vendedores:
                res_v = supabase.table("usuarios").select("id, nombre_completo").in_("id", ids_vendedores).execute().data
                mapa_vend = {v["id"]: v["nombre_completo"] for v in res_v}

            # B. Extracción Profunda con BLINDAJE ANTI-NULOS
            ids_ordenes = [o["id"] for o in res_ordenes]
            if ids_ordenes:
                res_items = supabase.table("items_orden").select(
                    "orden_id, familia_producto, productos_catalogo(descripcion), especificaciones_producto(talla_superior, talla_inferior)"
                ).in_("orden_id", ids_ordenes).execute().data
                
                for it in res_items:
                    oid = it["orden_id"]
                    fam = str(it.get("familia_producto", "")).strip().upper()
                    
                    # BLINDAJE 1: Si el producto fue borrado o es nulo
                    prod_data = it.get("productos_catalogo") or {}
                    prod_desc = str(prod_data.get("descripcion", "")).strip().upper()
                    
                    if not prod_desc:
                        prod_desc = fam

                    if oid not in mapa_desglose_global:
                        mapa_desglose_global[oid] = {}

                    # BLINDAJE 2: Si no hay especificaciones registradas, forzamos una lista vacía
                    especs = it.get("especificaciones_producto") or []
                    
                    for esp in especs:
                        t_sup = str(esp.get("talla_superior") or "").strip().upper()
                        t_inf = str(esp.get("talla_inferior") or "").strip().upper()
                        
                        tiene_sup = t_sup not in ["", "-", "NONE", "N/A", "NAN", "0"]
                        tiene_inf = t_inf not in ["", "-", "NONE", "N/A", "NAN", "0"]
                        
                        # Lógica Superior
                        if tiene_sup:
                            tipo_sup = "CAMISETA" 
                            if "CHOMPA" in prod_desc: tipo_sup = "CHOMPA"
                            elif "POLO" in prod_desc: tipo_sup = "POLO"
                            elif "BVD" in prod_desc: tipo_sup = "BVD"
                            mapa_desglose_global[oid][tipo_sup] = mapa_desglose_global[oid].get(tipo_sup, 0) + 1
                            
                        # Lógica Inferior
                        if tiene_inf:
                            tipo_inf = "PANTALONETA" 
                            if "FALDA SHORT" in prod_desc: tipo_inf = "FALDA SHORT"
                            elif "FALDA" in prod_desc: tipo_inf = "FALDA"
                            elif "CALENTADOR" in prod_desc: tipo_inf = "PANTALÓN CALENTADOR"
                            mapa_desglose_global[oid][tipo_inf] = mapa_desglose_global[oid].get(tipo_inf, 0) + 1
                            
                        # Fallback Genérico
                        if not tiene_sup and not tiene_inf:
                            tipo_gen = "PRENDA/GENÉRICO"
                            mapa_desglose_global[oid][tipo_gen] = mapa_desglose_global[oid].get(tipo_gen, 0) + 1

            # C. Construcción de la Tabla Visual
            for o in res_ordenes:
                oid = o["id"]
                desglose_orden = mapa_desglose_global.get(oid, {})
                total_prendas_orden = sum(desglose_orden.values())
                
                resumen_texto = ", ".join([f"{int(c)} {t}" for t, c in desglose_orden.items()])
                if not resumen_texto:
                    resumen_texto = "Sin desglose"

                # BLINDAJE 3: Si la orden se hizo para Consumidor Final y no tiene cliente relacional
                cliente_data = o.get("clientes") or {}

                datos_pendientes.append({
                    "Seleccionar": False,
                    "ID_Oculto": oid,
                    "Orden": o["codigo_orden"],
                    "Vendedora": mapa_vend.get(o["creado_por_id"], "No registrado"),
                    "Cliente": cliente_data.get("nombre_completo", "S/N"),
                    "Volumen Total": total_prendas_orden,
                    "Detalle": resumen_texto
                })
            
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
                if not listo_para_asignar:
                    st.warning(
                        "Selecciona órdenes arriba y asigna al menos un cortador o costurera."
                    )
                else:
                    try:
                        with st.spinner("Registrando asignación en el taller..."):
                            ids_seleccionados = [
                                int(x) for x in df_seleccionado["ID_Oculto"].tolist()
                            ]
                            cortador_id = mapa_cortadores.get(cortador_sel)
                            costurera_id = mapa_costureras.get(costurera_sel)
                            usuario_actual = st.session_state.get("id_usuario")
                            ahora = datetime.datetime.now().isoformat()

                            registros = []
                            for oid in ids_seleccionados:
                                prendas = sum(
                                    memoria_desglose.get(oid, {}).values()
                                )
                                registros.append(
                                    {
                                        "orden_id": oid,
                                        "cortador_id": cortador_id,
                                        "costurera_id": costurera_id,
                                        "asignado_por": usuario_actual,
                                        "prendas": int(prendas),
                                        "created_at": ahora,
                                    }
                                )

                            # Persistencia real en la tabla de trazabilidad del taller.
                            supabase.table("asignaciones_taller").insert(
                                registros
                            ).execute()

                        st.success(
                            f"¡{len(ids_seleccionados)} órdenes ({total_absoluto:.0f} prendas) "
                            "asignadas correctamente!"
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(
                            f"Error al asignar: {e}. Asegúrate de que exista la tabla "
                            "'asignaciones_taller' (ejecuta migracion_fase1.sql)."
                        )

        # --- INFORMES DE TALLER (PDF por separado: corte y costura) ---
        st.divider()
        st.markdown("### 📄 Informes de Taller (PDF)")

        with st.expander("⚖️ Pesos de confección (para costureras)", expanded=False):
            st.caption(
                "El cortador cuenta 1 por cada prenda. Para costura, cada tipo de prenda "
                "tiene un peso según su dificultad y tiempo. Ajusta los valores según tu realidad."
            )
            pesos_edit = {}
            cols_p = st.columns(3)
            for i, tipo in enumerate(TIPOS_PRENDA):
                pesos_edit[tipo] = cols_p[i % 3].number_input(
                    tipo,
                    min_value=0.0,
                    value=PESOS_POR_PRENDA.get(tipo, 1.0),
                    step=0.1,
                    format="%.1f",
                    key=f"peso_taller_{tipo}",
                )

        if total_absoluto > 0:
            if st.button(
                "📄 Generar Informes (Corte y Costura)",
                type="primary",
                use_container_width=True,
            ):
                detalle_seleccion = []
                for _, fila in df_seleccionado.iterrows():
                    oid = int(fila["ID_Oculto"])
                    detalle_seleccion.append(
                        {
                            "orden": fila["Orden"],
                            "cliente": fila["Cliente"],
                            "desglose": memoria_desglose.get(oid, {}),
                        }
                    )

                pdf_corte = generar_informe_taller(
                    detalle_seleccion, pesos_edit, "CORTE"
                )
                pdf_costura = generar_informe_taller(
                    detalle_seleccion, pesos_edit, "COSTURA"
                )

                col_d1, col_d2 = st.columns(2)
                col_d1.download_button(
                    "⬇️ Informe de Corte (PDF)",
                    pdf_corte,
                    file_name=f"informe_corte_{datetime.date.today().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
                col_d2.download_button(
                    "⬇️ Informe de Costura (PDF)",
                    pdf_costura,
                    file_name=f"informe_costura_{datetime.date.today().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
        else:
            st.caption("Selecciona órdenes arriba para poder generar los informes.")

    else:
        st.info("No hay órdenes pendientes de confección en este momento.")
