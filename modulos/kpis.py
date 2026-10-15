"""
Módulo de KPI y Métricas — exclusivo del rol GERENTE (administrador).

Organizado en pestañas:
- Resumen: flujo de caja, balance, órdenes activas, cuentas por cobrar.
- Ventas: producto más vendido, tallas, categorías y picos/valles de ventas.
- Gastos: reporte de consumibles.
- Clientes: mejores clientes y cumpleañeros del mes.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, timedelta


def _fmt(v):
    """Formatea un monto a moneda."""
    return f"${v:,.2f}"


def _preset_range(preset: str, hoy: date, primer_dia_mes: date):
    """Devuelve (inicio, fin) según el preset elegido."""
    if preset == "Este mes":
        return primer_dia_mes, hoy
    if preset == "Mes anterior":
        ultimo_prev = primer_dia_mes - timedelta(days=1)
        return ultimo_prev.replace(day=1), ultimo_prev
    if preset == "Últimos 30 días":
        return hoy - timedelta(days=29), hoy
    if preset == "Últimos 3 meses":
        return hoy - timedelta(days=90), hoy
    if preset == "Últimos 6 meses":
        return hoy - timedelta(days=180), hoy
    if preset == "Últimos 12 meses":
        return hoy - timedelta(days=365), hoy
    if preset == "Este año":
        return date(hoy.year, 1, 1), hoy
    return primer_dia_mes, hoy


def _fetch_movimientos(supabase, tabla, campo_fecha, inicio, fin):
    """Trae movimientos (pagos o egresos) no anulados dentro del rango."""
    try:
        res = (
            supabase.table(tabla)
            .select("*")
            .gte(campo_fecha, inicio.isoformat())
            .lte(campo_fecha, fin.isoformat())
            .eq("anulado", False)
            .execute()
        )
        return res.data or []
    except Exception:
        return []


def _select(supabase, tabla, select, **filtros):
    """Consulta genérica con try/except y filtros por igualdad."""
    try:
        q = supabase.table(tabla).select(select)
        for k, v in filtros.items():
            q = q.eq(k, v)
        return q.execute().data or []
    except Exception:
        return []


def _fetch_in(supabase, tabla, select, campo, ids, chunk=300):
    """Consulta con filtro .in_ en lotes (evita URLs demasiado largas)."""
    if not ids:
        return []
    out = []
    for i in range(0, len(ids), chunk):
        lote = ids[i : i + chunk]
        try:
            res = supabase.table(tabla).select(select).in_(campo, lote).execute()
            out.extend(res.data or [])
        except Exception:
            continue
    return out


def _nombres_clientes(supabase, ids):
    """Devuelve {id: nombre_completo} para una lista de ids de cliente."""
    if not ids:
        return {}
    try:
        res = (
            supabase.table("clientes")
            .select("id, nombre_completo")
            .in_("id", [int(i) for i in ids])
            .execute()
        )
        return {c["id"]: c.get("nombre_completo", "Consumidor Final") for c in res.data}
    except Exception:
        return {}


def render(supabase):
    # --- Gate de seguridad: solo administrador ---
    if st.session_state.get("rol") != "GERENTE":
        st.error("🔒 Acceso restringido. Este módulo es exclusivo del administrador.")
        st.stop()

    st.header("📈 KPI y Métricas de Gestión", divider="blue")
    st.caption("Panel exclusivo de gerencia · datos calculados en vivo desde Supabase.")

    hoy = date.today()
    primer_dia_mes = hoy.replace(day=1)

    # --- Selección de periodo ---
    col_preset, col_desde, col_hasta = st.columns([1.6, 1, 1])
    preset = col_preset.selectbox(
        "Periodo de análisis",
        [
            "Este mes",
            "Mes anterior",
            "Últimos 30 días",
            "Últimos 3 meses",
            "Últimos 6 meses",
            "Últimos 12 meses",
            "Este año",
            "Personalizado",
        ],
        index=0,
    )
    if preset == "Personalizado":
        inicio = col_desde.date_input("Desde", value=primer_dia_mes)
        fin = col_hasta.date_input("Hasta", value=hoy)
    else:
        inicio, fin = _preset_range(preset, hoy, primer_dia_mes)
        col_desde.caption(f"Desde: {inicio.strftime('%d/%m/%Y')}")
        col_hasta.caption(f"Hasta: {fin.strftime('%d/%m/%Y')}")

    if fin < inicio:
        st.warning("⚠️ La fecha 'Hasta' es anterior a 'Desde'. Ajusta el rango.")
        st.stop()

    dias = (fin - inicio).days
    inicio_prev = inicio - timedelta(days=dias + 1)
    fin_prev = inicio - timedelta(days=1)

    # ============================================================
    # CARGA DE DATOS COMPARTIDA
    # ============================================================
    with st.spinner("Calculando indicadores..."):
        pagos = _fetch_movimientos(supabase, "pagos", "fecha_pago", inicio, fin)
        pagos_prev = _fetch_movimientos(supabase, "pagos", "fecha_pago", inicio_prev, fin_prev)
        egresos = _fetch_movimientos(supabase, "egresos", "fecha", inicio, fin)
        egresos_prev = _fetch_movimientos(supabase, "egresos", "fecha", inicio_prev, fin_prev)

        try:
            res_ordenes = (
                supabase.table("ordenes")
                .select(
                    "id, total_estimado, saldo_pendiente, estado, created_at, "
                    "cliente_id, codigo_orden"
                )
                .gte("created_at", f"{inicio.isoformat()}T00:00:00")
                .lte("created_at", f"{fin.isoformat()}T23:59:59")
                .execute()
            )
            ordenes_rango = res_ordenes.data or []
        except Exception:
            ordenes_rango = []

        try:
            res_cxc = (
                supabase.table("ordenes")
                .select("id, codigo_orden, cliente_id, saldo_pendiente, estado")
                .gte("saldo_pendiente", 0.01)
                .execute()
            )
            ordenes_cxc = res_cxc.data or []
        except Exception:
            ordenes_cxc = []

    def _suma(rows, campo):
        return sum(float(r.get(campo) or 0) for r in rows)

    ingresos = _suma(pagos, "monto")
    ingresos_prev = _suma(pagos_prev, "monto")
    gastos = _suma(egresos, "monto")
    gastos_prev = _suma(egresos_prev, "monto")
    balance = ingresos - gastos

    ventas_facturadas = sum(
        float(o.get("total_estimado") or 0)
        for o in ordenes_rango
        if str(o.get("estado") or "").upper() != "ANULADO"
    )
    saldo_cxc = _suma(ordenes_cxc, "saldo_pendiente")

    estados_finales = {"ENTREGADO", "ANULADO", "ENTREGADA", "FINALIZADO"}
    ordenes_activas = sum(
        1
        for o in ordenes_rango
        if str(o.get("estado") or "").upper() not in estados_finales
    )

    # ============================================================
    # PESTAÑAS
    # ============================================================
    tab_resumen, tab_ventas, tab_gastos, tab_clientes = st.tabs(
        ["📊 Resumen", "🛒 Ventas", "💸 Gastos", "👥 Clientes"]
    )

    # ============================================================
    # TAB: RESUMEN
    # ============================================================
    with tab_resumen:
        st.subheader("Resumen ejecutivo del periodo")
        c1, c2, c3 = st.columns(3)
        c1.metric(
            "💵 Ingresos (cobrado)",
            _fmt(ingresos),
            delta=f"{_fmt(ingresos - ingresos_prev)} vs anterior",
        )
        c2.metric(
            "💸 Gastos (egresos)",
            _fmt(gastos),
            delta=f"{_fmt(gastos - gastos_prev)} vs anterior",
            delta_color="inverse",
        )
        c3.metric(
            "⚖️ Balance",
            _fmt(balance),
            delta=_fmt(balance),
            delta_color="normal" if balance >= 0 else "inverse",
        )

        c4, c5, c6 = st.columns(3)
        c4.metric("🛒 Ventas facturadas", _fmt(ventas_facturadas))
        c5.metric("🧾 Saldo por cobrar (CxC)", _fmt(saldo_cxc))
        c6.metric("🏭 Órdenes activas", f"{ordenes_activas}")

        st.divider()

        df_ing = pd.DataFrame(pagos)
        df_egr = pd.DataFrame(egresos)

        if not df_ing.empty:
            df_ing["dia"] = pd.to_datetime(df_ing["fecha_pago"], errors="coerce")
            serie_ing = df_ing.groupby(df_ing["dia"].dt.date)["monto"].sum()
        else:
            serie_ing = pd.Series(dtype="float")

        if not df_egr.empty:
            df_egr["dia"] = pd.to_datetime(df_egr["fecha"], errors="coerce")
            serie_egr = df_egr.groupby(df_egr["dia"].dt.date)["monto"].sum()
        else:
            serie_egr = pd.Series(dtype="float")

        df_flujo = pd.DataFrame({"Ingresos": serie_ing, "Gastos": serie_egr}).fillna(0)
        if not df_flujo.empty:
            fig_flujo = px.line(
                df_flujo,
                markers=True,
                title="Flujo diario: ingresos vs gastos",
                labels={"value": "Monto ($)", "index": "Fecha", "variable": "Tipo"},
            )
            fig_flujo.update_layout(legend_title_text="")
            st.plotly_chart(fig_flujo, use_container_width=True)

        if df_ing.empty:
            st.info("No hay ingresos en este periodo.")
        else:
            montos_metodo = df_ing.groupby(
                df_ing["metodo_pago"].fillna("Sin método")
            )["monto"].sum()
            fig_metodo = px.pie(
                values=montos_metodo.values,
                names=montos_metodo.index,
                title="Ingresos por método de pago",
                hole=0.4,
            )
            st.plotly_chart(fig_metodo, use_container_width=True)

        if df_egr.empty:
            st.info("No hay gastos en este periodo.")
        else:
            cat = (
                df_egr.groupby(df_egr["categoria"].fillna("Sin categoría"))["monto"]
                .sum()
                .sort_values(ascending=False)
            )
            fig_cat = px.bar(
                x=cat.values,
                y=cat.index,
                orientation="h",
                title="Gastos por categoría",
                labels={"x": "Monto ($)", "y": "Categoría"},
            )
            st.plotly_chart(fig_cat, use_container_width=True)

        if ordenes_rango:
            df_ord = pd.DataFrame(ordenes_rango)
            estados = df_ord["estado"].fillna("SIN ESTADO").value_counts()
            fig_est = px.bar(
                x=estados.values,
                y=estados.index,
                orientation="h",
                title="Órdenes por estado (flujo de producción)",
                labels={"x": "Órdenes", "y": "Estado"},
            )
            st.plotly_chart(fig_est, use_container_width=True)

        st.divider()
        st.subheader("Top deudores (cuentas por cobrar)")
        if ordenes_cxc:
            df_cxc = pd.DataFrame(ordenes_cxc)
            df_cxc["saldo_pendiente"] = pd.to_numeric(
                df_cxc["saldo_pendiente"], errors="coerce"
            ).fillna(0)
            df_cxc["cliente_id_num"] = pd.to_numeric(
                df_cxc["cliente_id"], errors="coerce"
            )
            ids = [int(c) for c in df_cxc["cliente_id_num"].dropna().unique()]
            mapa_cli = _nombres_clientes(supabase, ids)

            def _nombre_cliente(cid):
                if pd.isna(cid):
                    return "Consumidor Final"
                try:
                    return mapa_cli.get(int(cid), "Consumidor Final")
                except (ValueError, TypeError):
                    return "Consumidor Final"

            df_cxc["cliente"] = df_cxc["cliente_id_num"].map(_nombre_cliente)
            deudores = (
                df_cxc.groupby("cliente")["saldo_pendiente"]
                .sum()
                .sort_values(ascending=False)
                .head(10)
            )
            fig_deu = px.bar(
                x=deudores.values,
                y=deudores.index,
                orientation="h",
                title="Top 10 clientes con saldo pendiente",
                labels={"x": "Saldo pendiente ($)", "y": "Cliente"},
            )
            st.plotly_chart(fig_deu, use_container_width=True)
        else:
            st.success("¡No hay cuentas por cobrar pendientes!")

        st.caption("💡 Los montos de CxC son un acumulado histórico.")

    # ============================================================
    # TAB: VENTAS
    # ============================================================
    with tab_ventas:
        st.subheader("Análisis de ventas")
        st.caption("Productos, tallas y categorías se calculan sobre las ventas del periodo seleccionado.")

        # Filtramos por el periodo: órdenes del rango → ítems → tallas
        ordenes_ids = [int(o["id"]) for o in ordenes_rango]
        items = _fetch_in(
            supabase,
            "items_orden",
            "id, orden_id, producto_id, cantidad_total, familia_producto, precio_aplicado",
            "orden_id",
            ordenes_ids,
        )
        productos = _select(
            supabase, "productos_catalogo", "id, codigo_referencia, descripcion, linea_categoria"
        )
        items_ids = [int(it["id"]) for it in items]
        tallas_data = _fetch_in(
            supabase,
            "especificaciones_producto",
            "item_orden_id, talla_superior, talla_inferior, talla_polines",
            "item_orden_id",
            items_ids,
        )

        # Total de unidades vendidas en el periodo
        if items:
            df_unidades = pd.DataFrame(items)
            total_unidades = (
                pd.to_numeric(df_unidades["cantidad_total"], errors="coerce")
                .fillna(0)
                .sum()
            )
            c_u1, c_u2 = st.columns(2)
            c_u1.metric("📦 Total unidades vendidas", f"{total_unidades:,.0f}")
            c_u2.metric("🏷️ Productos distintos", f"{df_unidades['producto_id'].nunique()}")
        else:
            st.metric("📦 Total unidades vendidas", "0")

        # Picos y valles por fecha (periodo seleccionado)
        if ordenes_rango:
            df_ventas = pd.DataFrame(ordenes_rango)
            df_ventas["created_at"] = pd.to_datetime(df_ventas["created_at"], errors="coerce")
            df_ventas["total_estimado"] = pd.to_numeric(
                df_ventas["total_estimado"], errors="coerce"
            ).fillna(0)
            ventas_dia = (
                df_ventas.groupby(df_ventas["created_at"].dt.date)["total_estimado"].sum()
            )
            if not ventas_dia.empty:
                st.markdown("#### 📈 Picos y valles de ventas")
                fig_picos = px.line(
                    x=ventas_dia.index,
                    y=ventas_dia.values,
                    markers=True,
                    title="Ventas por día",
                    labels={"x": "Fecha", "y": "Ventas ($)"},
                )
                st.plotly_chart(fig_picos, use_container_width=True)

                pico = ventas_dia.idxmax()
                valle = ventas_dia.idxmin()
                c_p, c_v = st.columns(2)
                c_p.metric("🔺 Día pico", f"{pico.strftime('%d/%m/%Y')} (${ventas_dia.max():,.2f})")
                c_v.metric("🔻 Día valle", f"{valle.strftime('%d/%m/%Y')} (${ventas_dia.min():,.2f})")

        # Producto más vendido
        if items and productos:
            df_items = pd.DataFrame(items)
            df_items["cantidad_total"] = pd.to_numeric(
                df_items["cantidad_total"], errors="coerce"
            ).fillna(0)
            df_prod = pd.DataFrame(productos)
            df_items = df_items.merge(
                df_prod[["id", "descripcion"]],
                left_on="producto_id",
                right_on="id",
                how="left",
            )
            df_items["descripcion"] = df_items["descripcion"].fillna(
                df_items["familia_producto"].fillna("Sin producto")
            )
            df_items["precio_aplicado"] = pd.to_numeric(
                df_items["precio_aplicado"], errors="coerce"
            ).fillna(0)
            df_items["ingreso"] = (
                df_items["cantidad_total"] * df_items["precio_aplicado"]
            )
            top_productos = (
                df_items.groupby("descripcion")["cantidad_total"].sum()
                .sort_values(ascending=False)
                .head(10)
            )
            if not top_productos.empty:
                st.markdown("#### 🏆 Productos más vendidos")
                fig_prod = px.bar(
                    x=top_productos.values,
                    y=top_productos.index,
                    orientation="h",
                    title="Top 10 productos por cantidad",
                    labels={"x": "Cantidad", "y": "Producto"},
                )
                st.plotly_chart(fig_prod, use_container_width=True)

                # Lista (tabla) completa de productos vendidos
                tabla_productos = (
                    df_items.groupby("descripcion")
                    .agg(cantidad=("cantidad_total", "sum"), ingreso=("ingreso", "sum"))
                    .sort_values("cantidad", ascending=False)
                    .reset_index()
                )
                st.dataframe(
                    tabla_productos.rename(
                        columns={
                            "descripcion": "Producto",
                            "cantidad": "Cantidad",
                            "ingreso": "Ingreso ($)",
                        }
                    ),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Ingreso ($)": st.column_config.NumberColumn(
                            "Ingreso ($)", format="$ %.2f"
                        )
                    },
                )

            # Categoría más vendida
            if "linea_categoria" in df_prod.columns:
                df_cat_ventas = df_items.merge(
                    df_prod[["id", "linea_categoria"]],
                    left_on="producto_id",
                    right_on="id",
                    how="left",
                )
                top_categorias = (
                    df_cat_ventas.groupby(df_cat_ventas["linea_categoria"].fillna("Sin categoría"))[
                        "cantidad_total"
                    ]
                    .sum()
                    .sort_values(ascending=False)
                    .head(10)
                )
                if not top_categorias.empty:
                    st.markdown("#### 🗂️ Categorías más vendidas")
                    fig_cat_ventas = px.pie(
                        values=top_categorias.values,
                        names=top_categorias.index,
                        title="Ventas por categoría",
                        hole=0.4,
                    )
                    st.plotly_chart(fig_cat_ventas, use_container_width=True)
        else:
            st.info("No hay datos de productos para analizar.")

        # Tallas más vendidas
        if tallas_data:
            df_tallas = pd.DataFrame(tallas_data)
            tallas = []
            for col in ["talla_superior", "talla_inferior", "talla_polines"]:
                if col in df_tallas.columns:
                    tallas.extend(df_tallas[col].dropna().astype(str).str.strip().str.upper().tolist())
            invalidas = {"", "-", "NONE", "N/A", "NAN", "0", "NULL"}
            tallas_limpias = [t for t in tallas if t not in invalidas]
            if tallas_limpias:
                serie_tallas = pd.Series(tallas_limpias).value_counts().head(15)
                st.markdown("#### 📏 Tallas más vendidas")
                fig_tallas = px.bar(
                    x=serie_tallas.values,
                    y=serie_tallas.index,
                    orientation="h",
                    title="Top tallas por frecuencia",
                    labels={"x": "Unidades", "y": "Talla"},
                )
                st.plotly_chart(fig_tallas, use_container_width=True)
            else:
                st.info("No hay tallas registradas.")
        else:
            st.info("No hay tallas registradas.")

    # ============================================================
    # TAB: GASTOS (CONSUMIBLES)
    # ============================================================
    with tab_gastos:
        st.subheader("Reporte de gastos por consumibles")
        st.caption("Egresos identificados como consumibles (origen INSUMOS o categoría con 'INSUM').")

        df_egr_all = pd.DataFrame(egresos)
        if not df_egr_all.empty:
            df_egr_all["monto"] = pd.to_numeric(df_egr_all["monto"], errors="coerce").fillna(0)
            cat_txt = df_egr_all["categoria"].fillna("").astype(str).str.upper()
            orig_txt = (
                df_egr_all["origen_modulo"].fillna("").astype(str).str.upper()
                if "origen_modulo" in df_egr_all.columns
                else pd.Series("", index=df_egr_all.index)
            )
            mascara_consumibles = orig_txt.eq("INSUMOS") | cat_txt.str.contains("INSUM", na=False)
            df_consumibles = df_egr_all[mascara_consumibles].copy()

            if df_consumibles.empty:
                st.info("No hay gastos de consumibles en este periodo.")
            else:
                total_consumibles = df_consumibles["monto"].sum()
                c_g1, c_g2 = st.columns(2)
                c_g1.metric("🧵 Total consumibles", _fmt(total_consumibles))
                c_g2.metric("🧾 Registros", f"{len(df_consumibles)}")

                # Top por descripción/categoría
                top_consumibles = (
                    df_consumibles.groupby(
                        df_consumibles["categoria"].fillna("Sin categoría")
                    )["monto"].sum()
                    .sort_values(ascending=False)
                    .head(10)
                )
                fig_consumibles = px.bar(
                    x=top_consumibles.values,
                    y=top_consumibles.index,
                    orientation="h",
                    title="Top gastos de consumibles por categoría",
                    labels={"x": "Monto ($)", "y": "Categoría"},
                )
                st.plotly_chart(fig_consumibles, use_container_width=True)

                # Tendencia por fecha
                df_consumibles["dia"] = pd.to_datetime(
                    df_consumibles["fecha"], errors="coerce"
                )
                tendencia = (
                    df_consumibles.groupby(df_consumibles["dia"].dt.date)["monto"].sum()
                )
                if not tendencia.empty:
                    fig_tend = px.line(
                        x=tendencia.index,
                        y=tendencia.values,
                        markers=True,
                        title="Tendencia de gastos de consumibles",
                        labels={"x": "Fecha", "y": "Monto ($)"},
                    )
                    st.plotly_chart(fig_tend, use_container_width=True)

                # Detalle
                with st.expander("Ver detalle de consumibles"):
                    detalle = df_consumibles[
                        ["fecha", "categoria", "descripcion", "monto", "metodo_pago"]
                    ].sort_values("fecha", ascending=False)
                    st.dataframe(
                        detalle,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "monto": st.column_config.NumberColumn("Monto", format="$ %.2f")
                        },
                    )
        else:
            st.info("No hay gastos en este periodo.")

    # ============================================================
    # TAB: CLIENTES
    # ============================================================
    with tab_clientes:
        st.subheader("Mejores clientes y cumpleaños")
        st.caption("Los mejores clientes se calculan sobre el periodo seleccionado.")

        # Reutilizamos las órdenes del periodo (ya filtradas por fecha)
        ordenes_cli = [
            o for o in ordenes_rango
            if str(o.get("estado") or "").upper() != "ANULADO"
        ]

        df_ordenes_cli = pd.DataFrame(ordenes_cli) if ordenes_cli else pd.DataFrame()
        if not df_ordenes_cli.empty:
            df_ordenes_cli = df_ordenes_cli[
                df_ordenes_cli["estado"].astype(str).str.upper() != "ANULADO"
            ]
            df_ordenes_cli["total_estimado"] = pd.to_numeric(
                df_ordenes_cli["total_estimado"], errors="coerce"
            ).fillna(0)
            df_ordenes_cli["cliente_id_num"] = pd.to_numeric(
                df_ordenes_cli["cliente_id"], errors="coerce"
            )

            # Mejores clientes
            ids_cli = [int(c) for c in df_ordenes_cli["cliente_id_num"].dropna().unique()]
            mapa_cli = _nombres_clientes(supabase, ids_cli)
            df_ordenes_cli["cliente"] = df_ordenes_cli["cliente_id_num"].map(
                lambda x: mapa_cli.get(int(x), "Consumidor Final")
                if not pd.isna(x)
                else "Consumidor Final"
            )
            top_clientes = (
                df_ordenes_cli.groupby("cliente")["total_estimado"]
                .sum()
                .sort_values(ascending=False)
                .head(10)
            )
            if not top_clientes.empty:
                st.markdown("#### 🥇 Mejores clientes (por monto comprado)")
                fig_clientes = px.bar(
                    x=top_clientes.values,
                    y=top_clientes.index,
                    orientation="h",
                    title="Top 10 clientes",
                    labels={"x": "Compras ($)", "y": "Cliente"},
                )
                st.plotly_chart(fig_clientes, use_container_width=True)

            # Cumpleañeros del mes
            st.markdown("#### 🎂 Cumpleañeros del mes")
            try:
                res_clientes = (
                    supabase.table("clientes")
                    .select("id, nombre_completo, telefono, fecha_nacimiento")
                    .execute()
                )
                clientes_data = res_clientes.data or []
            except Exception:
                clientes_data = []

            df_cli = pd.DataFrame(clientes_data) if clientes_data else pd.DataFrame()
            if not df_cli.empty:
                df_cli["fecha_nacimiento"] = pd.to_datetime(
                    df_cli["fecha_nacimiento"], errors="coerce"
                )
                mes_actual = hoy.month
                df_cumple = df_cli[df_cli["fecha_nacimiento"].dt.month == mes_actual].copy()
                df_cumple["dia"] = df_cumple["fecha_nacimiento"].dt.day
                df_cumple = df_cumple.sort_values("dia")

                if df_cumple.empty:
                    st.info("No hay clientes que cumplan años este mes.")
                else:
                    # Total comprado por cliente (acumulado)
                    compras_cli = (
                        df_ordenes_cli.groupby("cliente_id_num")["total_estimado"].sum()
                        if not df_ordenes_cli.empty
                        else pd.Series(dtype="float")
                    )
                    df_cumple["total_comprado"] = df_cumple["id"].map(
                        lambda x: float(compras_cli.get(int(x), 0)) if not pd.isna(x) else 0.0
                    )
                    df_cumple_show = df_cumple[
                        ["nombre_completo", "dia", "telefono", "total_comprado"]
                    ].rename(
                        columns={
                            "nombre_completo": "Cliente",
                            "dia": "Día",
                            "telefono": "Teléfono",
                            "total_comprado": "Compras ($)",
                        }
                    )
                    st.dataframe(
                        df_cumple_show,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Compras ($)": st.column_config.NumberColumn(
                                "Compras ($)", format="$ %.2f"
                            )
                        },
                    )
            else:
                st.info("No hay clientes registrados.")
        else:
            st.info("No hay órdenes para calcular clientes.")
