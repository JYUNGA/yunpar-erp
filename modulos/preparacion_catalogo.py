import streamlit as st
import pandas as pd


# =========================================================
# MÓDULO: PREPARACIÓN DE CATÁLOGO
# =========================================================


# =========================================================
# PROMPT ESTANDARIZADO YUNPAR
# =========================================================

def generar_prompt_mockup(
    presentacion,
    vista,
):
    """
    Genera el prompt oficial que utilizará el operador
    para crear los mockups de manera estandarizada.
    """

    descripcion_presentacion = {
        "Hombre": (
            "un modelo masculino de cuerpo completo o torso visible, "
            "proporciones naturales y pose profesional de catálogo"
        ),
        "Mujer": (
            "una modelo femenina de cuerpo completo o torso visible, "
            "proporciones naturales y pose profesional de catálogo"
        ),
        "Niño": (
            "un modelo infantil de apariencia natural, "
            "pose profesional de catálogo y proporciones realistas"
        ),
        "Prenda aislada": (
            "la prenda presentada sin persona, "
            "con volumen tridimensional realista y forma natural"
        ),
    }

    descripcion_vista = {
        "Frente": (
            "vista frontal completamente centrada"
        ),
        "Espalda": (
            "vista posterior completamente centrada"
        ),
        "Lateral derecho": (
            "vista lateral derecha, mostrando claramente "
            "el costado derecho de la prenda"
        ),
        "Lateral izquierdo": (
            "vista lateral izquierda, mostrando claramente "
            "el costado izquierdo de la prenda"
        ),
    }

    persona = descripcion_presentacion.get(
        presentacion,
        descripcion_presentacion[
            "Prenda aislada"
        ],
    )

    angulo = descripcion_vista.get(
        vista,
        descripcion_vista[
            "Frente"
        ],
    )

    prompt = f"""
Genera UN SOLO mockup profesional de catálogo utilizando EXACTAMENTE el arte de referencia proporcionado.

PRESENTACIÓN:
{persona}.

VISTA OBLIGATORIA:
{angulo}.

REGLAS VISUALES YUNPAR:

1. Respeta fielmente el diseño del arte original.
2. No cambies logotipos, escudos, números, patrocinadores ni textos.
3. No cambies los colores del diseño.
4. No inventes patrones ni elementos gráficos nuevos.
5. Mantén la distribución gráfica original de la prenda.
6. Mantén proporciones realistas.
7. Utiliza iluminación limpia y profesional de fotografía de producto.
8. Mantén el producto centrado.
9. Utiliza fondo limpio y uniforme.
10. Mantén el mismo estilo visual que los demás mockups de esta colección.
11. No agregues objetos decorativos.
12. No agregues otras prendas.
13. No generes collages.
14. No muestres varias vistas en una sola imagen.
15. Genera únicamente UNA imagen correspondiente a la vista solicitada.
16. La imagen debe servir para un catálogo comercial de uniformes.
17. El resultado debe verse realista, limpio y profesional.
18. El diseño gráfico debe continuar naturalmente por mangas y laterales cuando corresponda.

IMPORTANTE:

El arte suministrado es la fuente principal.
No rediseñes el uniforme.
No reinterpretar colores o logotipos.
No crear una camiseta diferente.

Genera solamente:
{vista}.
"""

    return prompt.strip()


# =========================================================
# MOSTRAR SIGUIENTES PASOS
# =========================================================

def mostrar_pasos_pendientes(
    paso1_completo=False,
    paso2_completo=False,
):

    st.divider()

    st.markdown(
        "## 📊 Estado del proceso"
    )

    col1, col2, col3, col4 = (
        st.columns(4)
    )

    # -----------------------------------------------------
    # PASO 1
    # -----------------------------------------------------

    with col1:

        st.metric(
            "Paso 1",
            (
                "Completado"
                if paso1_completo
                else "Pendiente"
            ),
        )

        st.caption(
            "Seleccionar arte."
        )

    # -----------------------------------------------------
    # PASO 2
    # -----------------------------------------------------

    with col2:

        st.metric(
            "Paso 2",
            (
                "Completado"
                if paso2_completo
                else (
                    "Disponible"
                    if paso1_completo
                    else "Pendiente"
                )
            ),
        )

        st.caption(
            "Generar y cargar mockups."
        )

    # -----------------------------------------------------
    # PASO 3
    # -----------------------------------------------------

    with col3:

        st.metric(
            "Paso 3",
            (
                "Disponible"
                if paso2_completo
                else "Pendiente"
            ),
        )

        st.caption(
            "Clasificación con IA."
        )

    # -----------------------------------------------------
    # PASO 4
    # -----------------------------------------------------

    with col4:

        st.metric(
            "Paso 4",
            "Pendiente",
        )

        st.caption(
            "Enviar al catálogo."
        )

    if paso2_completo:

        st.success(
            "✅ Los mockups están completos. "
            "El trabajo está listo para continuar "
            "con la clasificación automática."
        )

        st.button(
            "🤖 Continuar con clasificación IA",
            disabled=True,
            width="stretch",
            key="preparacion_continuar_ia",
        )

        st.caption(
            "Este botón se habilitará "
            "cuando implementemos el Paso 3."
        )

    st.warning(
        "🔒 El módulo continúa en modo de preparación. "
        "No se ha escrito ni modificado ningún dato "
        "en Supabase."
    )


# =========================================================
# PASO 2
# GENERACIÓN Y CARGA DE MOCKUPS
# =========================================================

def mostrar_paso_2(
    orden_actual,
):

    st.divider()

    st.markdown(
        "## 2️⃣ Generación y carga de mockups"
    )

    st.caption(
        "Utiliza el arte seleccionado para generar "
        "las vistas estandarizadas del producto."
    )

    # =====================================================
    # INFORMACIÓN BÁSICA
    # =====================================================

    codigo = (
        orden_actual.get(
            "Código",
            "",
        )
    )

    arte_url = (
        orden_actual.get(
            "Arte"
        )
    )

    col_info1, col_info2 = (
        st.columns(2)
    )

    with col_info1:

        st.write(
            f"**Orden seleccionada:** {codigo}"
        )

    with col_info2:

        st.write(
            f"**Cliente:** "
            f"{orden_actual.get('Cliente', '')}"
        )

    # =====================================================
    # MÉTODO DE GENERACIÓN
    # =====================================================

    st.markdown(
        "### 🎨 Método de generación"
    )

    metodo = st.radio(
        "¿Cómo se generarán los mockups?",
        [
            "Canva IA - Manual",
            "Otra herramienta IA - Manual",
        ],
        horizontal=True,
        key=(
            f"preparacion_metodo_"
            f"{orden_actual.get('ID')}"
        ),
    )

    if metodo == "Canva IA - Manual":

        st.info(
            "✅ Método actual recomendado. "
            "El operador descarga o visualiza el arte, "
            "utiliza el prompt oficial y genera "
            "cada vista por separado en Canva IA."
        )

    else:

        st.info(
            "Puedes utilizar otra herramienta de IA, "
            "pero debes mantener exactamente "
            "el prompt y las reglas visuales YUNPAR."
        )

    # =====================================================
    # PRESENTACIÓN DEL PRODUCTO
    # =====================================================

    st.markdown(
        "### 👕 Presentación del mockup"
    )

    presentacion = st.selectbox(
        "Selecciona cómo se presentará este diseño",
        [
            "Prenda aislada",
            "Hombre",
            "Mujer",
            "Niño",
        ],
        key=(
            f"preparacion_presentacion_"
            f"{orden_actual.get('ID')}"
        ),
    )

    st.caption(
        "Esta opción se aplicará a las cuatro vistas "
        "para mantener consistencia."
    )

    # =====================================================
    # ARTE ORIGINAL
    # =====================================================

    with st.expander(
        "🎨 Ver arte original",
        expanded=False,
    ):

        if arte_url:

            try:

                st.image(
                    arte_url,
                    width="stretch",
                )

            except Exception:

                st.warning(
                    "No se pudo mostrar "
                    "la vista previa del arte."
                )

                st.write(
                    arte_url
                )

        else:

            st.warning(
                "No existe una URL de arte "
                "para esta orden."
            )

    # =====================================================
    # PROMPT OFICIAL
    # =====================================================

    st.markdown(
        "### 🧠 Prompt oficial YUNPAR"
    )

    st.caption(
        "Genera las imágenes UNA POR UNA. "
        "Nunca pidas las cuatro vistas "
        "en una misma generación."
    )

    vista_prompt = st.selectbox(
        "Vista que deseas generar",
        [
            "Frente",
            "Espalda",
            "Lateral derecho",
            "Lateral izquierdo",
        ],
        key=(
            f"preparacion_vista_prompt_"
            f"{orden_actual.get('ID')}"
        ),
    )

    prompt_actual = (
        generar_prompt_mockup(
            presentacion,
            vista_prompt,
        )
    )

    st.code(
        prompt_actual,
        language="text",
    )

    st.info(
        "💡 Para obtener consistencia, "
        "usa primero el arte original como referencia. "
        "Después utiliza el primer mockup aprobado "
        "como referencia visual para las siguientes vistas."
    )

    # =====================================================
    # REGLAS DE ESTANDARIZACIÓN
    # =====================================================

    with st.expander(
        "📐 Reglas de estandarización YUNPAR",
        expanded=False,
    ):

        st.write(
            """
**Todas las imágenes deben mantener:**

- El mismo tipo de prenda.
- El mismo cuello.
- El mismo largo de mangas.
- Los mismos colores.
- Los mismos logotipos.
- La misma iluminación.
- El mismo fondo.
- Proporciones similares.
- El producto centrado.
- Un único producto por imagen.
- Sin collage.
- Sin elementos decorativos adicionales.
"""
        )

    # =====================================================
    # CARGA DE MOCKUPS
    # =====================================================

    st.divider()

    st.markdown(
        "### 📤 Cargar mockups generados"
    )

    st.caption(
        "Carga cada imagen en su posición correspondiente."
    )

    # =====================================================
    # FRENTE
    # =====================================================

    st.markdown(
        "#### 1. Frente ⭐"
    )

    frente = st.file_uploader(
        "Subir vista frontal",
        type=[
            "png",
            "jpg",
            "jpeg",
            "webp",
        ],
        key=(
            f"preparacion_frente_"
            f"{orden_actual.get('ID')}"
        ),
    )

    if frente is not None:

        st.image(
            frente,
            caption="Frente",
            width=350,
        )

        st.success(
            "✅ Frente cargado."
        )

    # =====================================================
    # ESPALDA
    # =====================================================

    st.markdown(
        "#### 2. Espalda"
    )

    espalda = st.file_uploader(
        "Subir vista posterior",
        type=[
            "png",
            "jpg",
            "jpeg",
            "webp",
        ],
        key=(
            f"preparacion_espalda_"
            f"{orden_actual.get('ID')}"
        ),
    )

    if espalda is not None:

        st.image(
            espalda,
            caption="Espalda",
            width=350,
        )

        st.success(
            "✅ Espalda cargada."
        )

    # =====================================================
    # LATERAL DERECHO
    # =====================================================

    st.markdown(
        "#### 3. Lateral derecho"
    )

    lateral_derecho = st.file_uploader(
        "Subir lateral derecho",
        type=[
            "png",
            "jpg",
            "jpeg",
            "webp",
        ],
        key=(
            f"preparacion_derecha_"
            f"{orden_actual.get('ID')}"
        ),
    )

    if lateral_derecho is not None:

        st.image(
            lateral_derecho,
            caption="Lateral derecho",
            width=350,
        )

        st.success(
            "✅ Lateral derecho cargado."
        )

    # =====================================================
    # LATERAL IZQUIERDO
    # =====================================================

    st.markdown(
        "#### 4. Lateral izquierdo"
    )

    lateral_izquierdo = st.file_uploader(
        "Subir lateral izquierdo",
        type=[
            "png",
            "jpg",
            "jpeg",
            "webp",
        ],
        key=(
            f"preparacion_izquierda_"
            f"{orden_actual.get('ID')}"
        ),
    )

    if lateral_izquierdo is not None:

        st.image(
            lateral_izquierdo,
            caption="Lateral izquierdo",
            width=350,
        )

        st.success(
            "✅ Lateral izquierdo cargado."
        )

    # =====================================================
    # ESTADO DE MOCKUPS
    # =====================================================

    st.divider()

    st.markdown(
        "### 📊 Estado de los mockups"
    )

    mockups = [
        {
            "Vista": "Frente",
            "Archivo": frente,
        },
        {
            "Vista": "Espalda",
            "Archivo": espalda,
        },
        {
            "Vista": "Lateral derecho",
            "Archivo": lateral_derecho,
        },
        {
            "Vista": "Lateral izquierdo",
            "Archivo": lateral_izquierdo,
        },
    ]

    registros_estado = []

    cantidad_cargados = 0

    for mockup in mockups:

        archivo = (
            mockup[
                "Archivo"
            ]
        )

        cargado = (
            archivo is not None
        )

        if cargado:

            cantidad_cargados += 1

        registros_estado.append(
            {
                "Vista": (
                    mockup[
                        "Vista"
                    ]
                ),
                "Estado": (
                    "✅ Cargado"
                    if cargado
                    else "⏳ Pendiente"
                ),
                "Archivo": (
                    archivo.name
                    if archivo is not None
                    else ""
                ),
            }
        )

    st.dataframe(
        pd.DataFrame(
            registros_estado
        ),
        hide_index=True,
        width="stretch",
    )

    # =====================================================
    # PROGRESO
    # =====================================================

    progreso = (
        cantidad_cargados
        / 4
    )

    st.progress(
        progreso
    )

    st.caption(
        f"{cantidad_cargados} de 4 "
        f"mockups cargados."
    )

    # =====================================================
    # VALIDACIÓN DE RELACIÓN
    # =====================================================

    todas_cargadas = (
        cantidad_cargados == 4
    )

    confirmado = False

    if todas_cargadas:

        confirmado = st.checkbox(
            (
                "Confirmo que las cuatro imágenes "
                f"corresponden al arte de la orden "
                f"{codigo}."
            ),
            key=(
                f"preparacion_confirmacion_"
                f"{orden_actual.get('ID')}"
            ),
        )

        if confirmado:

            st.success(
                "✅ Mockups confirmados "
                "para este arte."
            )

        else:

            st.warning(
                "⚠️ Revisa las cuatro imágenes "
                "y confirma su relación con "
                "el arte original."
            )

    else:

        st.info(
            "Carga las cuatro vistas para "
            "completar el Paso 2."
        )

    # =====================================================
    # GUARDAR TEMPORALMENTE EN SESIÓN
    # =====================================================

    paso2_completo = (
        todas_cargadas
        and confirmado
    )

    if paso2_completo:

        st.session_state[
            "preparacion_catalogo_mockups"
        ] = {
            "orden_id": (
                orden_actual.get(
                    "ID"
                )
            ),
            "codigo": codigo,
            "presentacion": presentacion,
            "metodo": metodo,
            "frente": frente,
            "espalda": espalda,
            "lateral_derecho": (
                lateral_derecho
            ),
            "lateral_izquierdo": (
                lateral_izquierdo
            ),
        }

        st.success(
            "✅ PASO 2 COMPLETADO. "
            "Las cuatro vistas están cargadas "
            "y confirmadas."
        )

        st.info(
            "ℹ️ Los archivos permanecen únicamente "
            "en esta sesión de Streamlit. "
            "Todavía no se han enviado a Supabase."
        )

    return paso2_completo


# =========================================================
# FUNCIÓN PRINCIPAL
# =========================================================

def render(
    supabase,
):

    # =====================================================
    # CABECERA
    # =====================================================

    st.header(
        "🤖 Preparación de Catálogo",
        divider="blue",
    )

    st.caption(
        "Prepara los artes disponibles de las órdenes "
        "antes de enviarlos al catálogo digital de YUNPAR."
    )

    st.info(
        "🔒 Módulo en construcción. "
        "Por ahora trabaja únicamente con consultas "
        "y datos temporales de sesión. "
        "No modifica información en Supabase."
    )

    # =====================================================
    # FLUJO GENERAL
    # =====================================================

    st.markdown(
        "## 📌 Flujo de trabajo"
    )

    col1, col2, col3, col4 = (
        st.columns(4)
    )

    with col1:

        st.metric(
            "Paso 1",
            "Seleccionar arte",
        )

    with col2:

        st.metric(
            "Paso 2",
            "Crear mockups",
        )

    with col3:

        st.metric(
            "Paso 3",
            "Clasificación IA",
        )

    with col4:

        st.metric(
            "Paso 4",
            "Enviar al catálogo",
        )

    st.divider()

    # =====================================================
    # PASO 1
    # ÓRDENES CON ARTE
    # =====================================================

    st.markdown(
        "## 1️⃣ Órdenes con arte disponible"
    )

    st.caption(
        "Aquí aparecen únicamente las órdenes "
        "que tienen un arte cargado en el sistema."
    )

    # =====================================================
    # BUSCADORES
    # =====================================================

    col_bus1, col_bus2 = (
        st.columns(2)
    )

    with col_bus1:

        buscar_codigo = (
            st.text_input(
                "Buscar por código de orden",
                placeholder=(
                    "Ej: ORD-7259"
                ),
                key=(
                    "preparacion_buscar_codigo"
                ),
            )
        )

    with col_bus2:

        buscar_cliente = (
            st.text_input(
                "Buscar por cliente",
                placeholder=(
                    "Ej: AGRISUM"
                ),
                key=(
                    "preparacion_buscar_cliente"
                ),
            )
        )

    # =====================================================
    # CONSULTAR ÓRDENES
    # =====================================================

    try:

        respuesta = (
            supabase
            .table(
                "ordenes"
            )
            .select(
                "id, "
                "codigo_orden, "
                "estado, "
                "cliente_id, "
                "created_at, "
                "url_arte_final, "
                "url_diseno_final, "
                "observaciones_generales"
            )
            .order(
                "created_at",
                desc=True,
            )
            .limit(
                200
            )
            .execute()
        )

        ordenes = (
            respuesta.data
            or []
        )

    except Exception as e:

        st.error(
            f"❌ No se pudieron consultar "
            f"las órdenes: {e}"
        )

        return

    # =====================================================
    # SOLO ÓRDENES CON ARTE
    # =====================================================

    ordenes_con_arte = []

    for orden in ordenes:

        arte = (
            orden.get(
                "url_arte_final"
            )
            or orden.get(
                "url_diseno_final"
            )
        )

        if (
            arte
            and str(
                arte
            ).strip()
        ):

            orden[
                "arte_preparacion"
            ] = arte

            ordenes_con_arte.append(
                orden
            )

    if not ordenes_con_arte:

        st.warning(
            "⚠️ Actualmente no existen "
            "órdenes con arte disponible."
        )

        return

    # =====================================================
    # CLIENTES
    # =====================================================

    ids_clientes = list(
        {
            orden.get(
                "cliente_id"
            )
            for orden
            in ordenes_con_arte
            if orden.get(
                "cliente_id"
            )
        }
    )

    mapa_clientes = {}

    if ids_clientes:

        try:

            respuesta_clientes = (
                supabase
                .table(
                    "clientes"
                )
                .select(
                    "id, nombre_completo"
                )
                .in_(
                    "id",
                    ids_clientes,
                )
                .execute()
            )

            for cliente in (
                respuesta_clientes.data
                or []
            ):

                mapa_clientes[
                    cliente[
                        "id"
                    ]
                ] = (
                    cliente.get(
                        "nombre_completo"
                    )
                    or "Sin nombre"
                )

        except Exception:

            mapa_clientes = {}

    # =====================================================
    # CREAR DATAFRAME
    # =====================================================

    registros = []

    for orden in ordenes_con_arte:

        fecha_original = (
            orden.get(
                "created_at"
            )
        )

        fecha = ""

        if fecha_original:

            try:

                fecha = (
                    pd.to_datetime(
                        fecha_original
                    )
                    .strftime(
                        "%d/%m/%Y %H:%M"
                    )
                )

            except Exception:

                fecha = str(
                    fecha_original
                )

        registros.append(
            {
                "ID": (
                    orden.get(
                        "id"
                    )
                ),
                "Código": (
                    orden.get(
                        "codigo_orden",
                        "",
                    )
                ),
                "Cliente": (
                    mapa_clientes.get(
                        orden.get(
                            "cliente_id"
                        ),
                        "Consumidor Final",
                    )
                ),
                "Estado": (
                    orden.get(
                        "estado",
                        "",
                    )
                ),
                "Fecha": fecha,
                "Arte": (
                    orden.get(
                        "arte_preparacion"
                    )
                ),
                "Observaciones": (
                    orden.get(
                        "observaciones_generales",
                        "",
                    )
                ),
            }
        )

    df = pd.DataFrame(
        registros
    )

    # =====================================================
    # FILTRO CÓDIGO
    # =====================================================

    if buscar_codigo:

        df = df[
            df[
                "Código"
            ]
            .astype(str)
            .str.contains(
                buscar_codigo,
                case=False,
                na=False,
            )
        ]

    # =====================================================
    # FILTRO CLIENTE
    # =====================================================

    if buscar_cliente:

        df = df[
            df[
                "Cliente"
            ]
            .astype(str)
            .str.contains(
                buscar_cliente,
                case=False,
                na=False,
            )
        ]

    df = (
        df.reset_index(
            drop=True
        )
    )

    # =====================================================
    # MÉTRICAS
    # =====================================================

    col_res1, col_res2 = (
        st.columns(2)
    )

    with col_res1:

        st.metric(
            "Artes disponibles",
            len(
                ordenes_con_arte
            ),
        )

    with col_res2:

        st.metric(
            "Resultados mostrados",
            len(
                df
            ),
        )

    if df.empty:

        st.warning(
            "🔎 No se encontraron órdenes "
            "que coincidan con la búsqueda."
        )

        return

    # =====================================================
    # BANDEJA
    # =====================================================

    st.markdown(
        "### 📥 Bandeja de trabajos disponibles"
    )

    st.caption(
        "Selecciona una fila para comenzar "
        "la preparación de ese arte."
    )

    evento = (
        st.dataframe(
            df[
                [
                    "Código",
                    "Cliente",
                    "Estado",
                    "Fecha",
                ]
            ],
            width="stretch",
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key=(
                "preparacion_tabla_ordenes"
            ),
        )
    )

    # =====================================================
    # SELECCIÓN
    # =====================================================

    if evento.selection.rows:

        indice = (
            evento
            .selection
            .rows[
                0
            ]
        )

        orden_seleccionada = (
            df.iloc[
                indice
            ]
            .to_dict()
        )

        st.session_state[
            "preparacion_catalogo_orden_actual"
        ] = orden_seleccionada

    orden_actual = (
        st.session_state.get(
            "preparacion_catalogo_orden_actual"
        )
    )

    # =====================================================
    # SIN SELECCIÓN
    # =====================================================

    if not orden_actual:

        st.info(
            "👆 Selecciona una orden "
            "de la bandeja para continuar."
        )

        mostrar_pasos_pendientes(
            paso1_completo=False,
            paso2_completo=False,
        )

        return

    # =====================================================
    # VALIDAR RESULTADO ACTUAL
    # =====================================================

    ids_actuales = (
        df[
            "ID"
        ]
        .astype(str)
        .tolist()
    )

    id_seleccionado = str(
        orden_actual.get(
            "ID"
        )
    )

    if (
        buscar_codigo
        or buscar_cliente
    ) and (
        id_seleccionado
        not in ids_actuales
    ):

        st.info(
            "👆 Selecciona una orden "
            "de los resultados actuales."
        )

        mostrar_pasos_pendientes(
            paso1_completo=False,
            paso2_completo=False,
        )

        return

    # =====================================================
    # ARTE SELECCIONADO
    # =====================================================

    st.divider()

    st.markdown(
        "## ✅ Orden seleccionada"
    )

    col_arte, col_info = (
        st.columns(
            [
                2,
                1,
            ]
        )
    )

    # =====================================================
    # ARTE
    # =====================================================

    with col_arte:

        arte_url = (
            orden_actual.get(
                "Arte"
            )
        )

        st.markdown(
            "### 🎨 Arte cargado"
        )

        if arte_url:

            try:

                st.image(
                    arte_url,
                    width="stretch",
                )

            except Exception:

                st.warning(
                    "⚠️ El arte existe, "
                    "pero no se pudo mostrar "
                    "la vista previa."
                )

                st.write(
                    arte_url
                )

        else:

            st.warning(
                "No se encontró "
                "la URL del arte."
            )

    # =====================================================
    # INFORMACIÓN
    # =====================================================

    with col_info:

        codigo = (
            orden_actual.get(
                "Código",
                "",
            )
        )

        st.markdown(
            f"### {codigo}"
        )

        st.write(
            "**Cliente**"
        )

        st.write(
            orden_actual.get(
                "Cliente",
                "",
            )
        )

        st.write(
            "**Estado de la orden**"
        )

        st.write(
            orden_actual.get(
                "Estado",
                "",
            )
        )

        st.write(
            "**Fecha**"
        )

        st.write(
            orden_actual.get(
                "Fecha",
                "",
            )
        )

        observaciones = (
            orden_actual.get(
                "Observaciones"
            )
        )

        if observaciones:

            st.markdown(
                "**Observaciones**"
            )

            st.info(
                observaciones
            )

    # =====================================================
    # PASO 1 COMPLETADO
    # =====================================================

    st.success(
        "✅ PASO 1 COMPLETADO. "
        "La orden tiene un arte disponible "
        "y quedó seleccionada."
    )

    # =====================================================
    # PASO 2
    # =====================================================

    paso2_completo = (
        mostrar_paso_2(
            orden_actual
        )
    )

    # =====================================================
    # ESTADO GENERAL
    # =====================================================

    mostrar_pasos_pendientes(
        paso1_completo=True,
        paso2_completo=(
            paso2_completo
        ),
    )