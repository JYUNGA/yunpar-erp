import base64
import gc
import io
from urllib.request import Request, urlopen

import pandas as pd
import streamlit as st

from google import genai
from PIL import Image
from supabase import create_client


# =========================================================
# PRUEBA / DEMOSTRACIÓN
# GENERADOR DE MOCKUPS YUNPAR
# DOS MÉTODOS:
# 1. IA INTEGRADA
# 2. CANVA IA / MANUAL
# =========================================================

MODELO_IMAGEN = "gemini-nano-banana-2.1"

VISTAS = [
    ("frente", "Frente"),
    ("espalda", "Espalda"),
    ("derecha", "Lateral derecho"),
    ("izquierda", "Lateral izquierdo"),
]


# =========================================================
# CONEXIÓN SUPABASE
# SOLO LECTURA
# =========================================================

@st.cache_resource
def init_connection():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]

        return create_client(url, key)

    except Exception as e:
        st.error(f"❌ Error conectando con Supabase: {e}")
        st.stop()


# =========================================================
# API KEY GEMINI
# =========================================================

def obtener_api_key():
    try:
        return st.secrets["gemini"]["api_key"]
    except Exception:
        return None


# =========================================================
# ESTADO IA
# =========================================================

def clave_imagen(vista):
    return f"demo_ia_imagen_{vista}"


def clave_aprobado(vista):
    return f"demo_ia_aprobado_{vista}"


def limpiar_vista_ia(vista):
    st.session_state.pop(clave_imagen(vista), None)
    st.session_state.pop(clave_aprobado(vista), None)
    gc.collect()


def limpiar_todos_mockups_ia():
    for vista, _ in VISTAS:
        limpiar_vista_ia(vista)

    st.session_state.pop(
        "demo_ia_orden_id_generada",
        None,
    )

    gc.collect()


# =========================================================
# CONSULTAR ÓRDENES
# =========================================================

def consultar_ordenes_con_arte(supabase):
    respuesta = (
        supabase
        .table("ordenes")
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
        .limit(200)
        .execute()
    )

    ordenes = respuesta.data or []

    ordenes_con_arte = []

    for orden in ordenes:
        arte = (
            orden.get("url_arte_final")
            or orden.get("url_diseno_final")
        )

        if arte and str(arte).strip():
            orden["arte_prueba_ia"] = arte
            ordenes_con_arte.append(orden)

    if not ordenes_con_arte:
        return pd.DataFrame()

    ids_clientes = list(
        {
            orden.get("cliente_id")
            for orden in ordenes_con_arte
            if orden.get("cliente_id")
        }
    )

    mapa_clientes = {}

    if ids_clientes:
        try:
            respuesta_clientes = (
                supabase
                .table("clientes")
                .select(
                    "id, nombre_completo"
                )
                .in_(
                    "id",
                    ids_clientes,
                )
                .execute()
            )

            for cliente in respuesta_clientes.data or []:
                mapa_clientes[
                    cliente["id"]
                ] = (
                    cliente.get("nombre_completo")
                    or "Sin nombre"
                )

        except Exception:
            pass

    registros = []

    for orden in ordenes_con_arte:
        fecha_original = orden.get("created_at")
        fecha = ""

        if fecha_original:
            try:
                fecha = (
                    pd.to_datetime(fecha_original)
                    .strftime("%d/%m/%Y %H:%M")
                )
            except Exception:
                fecha = str(fecha_original)

        registros.append(
            {
                "ID": orden.get("id"),
                "Código": orden.get(
                    "codigo_orden",
                    "",
                ),
                "Cliente": mapa_clientes.get(
                    orden.get("cliente_id"),
                    "Consumidor Final",
                ),
                "Estado": orden.get(
                    "estado",
                    "",
                ),
                "Fecha": fecha,
                "Arte": orden.get(
                    "arte_prueba_ia"
                ),
                "Observaciones": orden.get(
                    "observaciones_generales",
                    "",
                ),
            }
        )

    return pd.DataFrame(registros)


# =========================================================
# DESCARGAR ARTE
# =========================================================

def descargar_arte_url(url):
    if not url:
        raise ValueError(
            "La orden seleccionada no tiene arte."
        )

    solicitud = Request(
        str(url),
        headers={
            "User-Agent": "Mozilla/5.0 YUNPAR-ERP"
        },
    )

    with urlopen(
        solicitud,
        timeout=45,
    ) as respuesta:
        datos = respuesta.read()

        tipo_contenido = respuesta.headers.get(
            "Content-Type",
            ""
        )

    if not datos:
        raise RuntimeError(
            "El arte descargado está vacío."
        )

    try:
        imagen = Image.open(
            io.BytesIO(datos)
        )

        formato = (
            imagen.format
            or "PNG"
        ).upper()

        imagen.verify()

    except Exception as e:
        raise RuntimeError(
            f"El arte no parece ser "
            f"una imagen válida: {e}"
        )

    mime_por_formato = {
        "PNG": "image/png",
        "JPEG": "image/jpeg",
        "JPG": "image/jpeg",
        "WEBP": "image/webp",
    }

    mime_type = mime_por_formato.get(
        formato
    )

    if not mime_type:
        if tipo_contenido.startswith("image/"):
            mime_type = (
                tipo_contenido
                .split(";")[0]
                .strip()
            )
        else:
            mime_type = "image/png"

    return datos, mime_type


# =========================================================
# MIME DE IMAGEN GENERADA
# =========================================================

def detectar_mime_bytes(datos):
    try:
        imagen = Image.open(
            io.BytesIO(datos)
        )

        formato = (
            imagen.format
            or "PNG"
        ).upper()

        mapa = {
            "PNG": "image/png",
            "JPEG": "image/jpeg",
            "JPG": "image/jpeg",
            "WEBP": "image/webp",
        }

        return mapa.get(
            formato,
            "image/png",
        )

    except Exception:
        return "image/png"


# =========================================================
# CONVERTIR BYTES A BASE64
# =========================================================

def bytes_a_base64(datos):
    return (
        base64.b64encode(datos)
        .decode("utf-8")
    )


# =========================================================
# PROMPT POR VISTA
# =========================================================

def generar_prompt(vista):
    instrucciones_vista = {
        "frente": """
VISTA SOLICITADA:
FRENTE.

Reconstruye la parte frontal del uniforme.
El logotipo, escudo, texto y elementos frontales
deben proceder del frente del arte original.
""",

        "espalda": """
VISTA SOLICITADA:
ESPALDA.

Reconstruye la parte posterior de la misma camiseta.
Utiliza específicamente el diseño posterior visible
en el arte original.

Debes conservar:
- patrocinadores,
- nombres,
- números,
- colores,
- degradados,
- gráficos posteriores.

NO coloques el escudo frontal en la espalda
a menos que el arte original lo muestre.
""",

        "derecha": """
VISTA SOLICITADA:
LATERAL DERECHO.

Muestra exclusivamente el costado derecho
de la misma camiseta.

Utiliza las piezas de mangas del arte original
y continúa de forma natural el diseño del frente
hacia la espalda.

Debe ser claramente una vista lateral.
No debe parecer una vista frontal.
""",

        "izquierda": """
VISTA SOLICITADA:
LATERAL IZQUIERDO.

Muestra exclusivamente el costado izquierdo
de la misma camiseta.

Utiliza las piezas de mangas del arte original
y continúa de forma natural el diseño del frente
hacia la espalda.

Debe ser claramente una vista lateral.
No debe parecer una vista frontal.
""",
    }

    vista_especifica = (
        instrucciones_vista[vista]
    )

    return f"""
Utiliza el ARTE ORIGINAL suministrado como
FUENTE PRINCIPAL Y OBLIGATORIA del diseño.

El arte puede estar plano y despiezado e incluir:

- frente,
- espalda,
- manga derecha,
- manga izquierda,
- logotipos,
- escudos,
- textos,
- números,
- patrocinadores,
- colores,
- degradados y gráficos.

Debes reconstruir una camiseta deportiva
FÍSICA Y TERMINADA.

{vista_especifica}

PRESENTACIÓN:

- Solo una prenda.
- Sin persona.
- Sin cabeza.
- Sin brazos humanos.
- Sin piernas.
- Sin maniquí visible.
- Manga corta.
- Cuello deportivo realista.
- Forma tridimensional natural.
- Fondo blanco limpio.
- Iluminación profesional.
- Producto completamente visible.
- Imagen centrada.
- Formato vertical.
- Fotografía de producto para catálogo.

FIDELIDAD OBLIGATORIA:

1. Respeta el arte original.
2. Conserva los colores.
3. Conserva logotipos y escudos.
4. Conserva textos visibles.
5. Conserva números.
6. Conserva patrocinadores.
7. Conserva patrones y degradados.
8. No inventes nuevos gráficos.
9. No cambies el tipo de camiseta.
10. No cambies el diseño por otro.
11. No inventes colores.
12. No inventes nombres.
13. No inventes números.
14. Mantén las mangas coherentes.
15. Mantén el mismo cuello.
16. Mantén las proporciones del producto.

CONSISTENCIA ENTRE VISTAS:

Si se proporcionan imágenes de mockups
previamente aprobados, utilízalas SOLAMENTE
como referencia visual para conservar:

- misma forma de camiseta,
- mismo cuello,
- mismas mangas,
- mismo volumen,
- misma iluminación,
- mismo fondo,
- mismas proporciones.

El ARTE ORIGINAL continúa siendo la fuente
principal del diseño gráfico.

NO HACER:

- No generar collage.
- No generar cuatro vistas juntas.
- No mostrar varias prendas.
- No mostrar personas.
- No agregar objetos.
- No agregar escenarios.
- No modificar el uniforme.
- No rediseñar logotipos.
- No mostrar las piezas planas.

Genera solamente UNA imagen correspondiente
a la vista solicitada.
""".strip()


# =========================================================
# REFERENCIAS IA
# =========================================================

def obtener_referencias_aprobadas(vista):
    referencias = []

    if vista == "frente":
        return referencias

    frente = st.session_state.get(
        clave_imagen("frente")
    )

    if (
        frente
        and st.session_state.get(
            clave_aprobado("frente"),
            False,
        )
    ):
        referencias.append(frente)

    if vista in [
        "derecha",
        "izquierda",
    ]:
        espalda = st.session_state.get(
            clave_imagen("espalda")
        )

        if (
            espalda
            and st.session_state.get(
                clave_aprobado("espalda"),
                False,
            )
        ):
            referencias.append(espalda)

    return referencias


# =========================================================
# GENERAR MOCKUP IA
# =========================================================

def generar_mockup_ia(
    vista,
    arte_bytes,
    arte_mime,
):
    api_key = obtener_api_key()

    if not api_key:
        raise RuntimeError(
            "No se encontró la API key "
            "de Gemini."
        )

    cliente = genai.Client(
        api_key=api_key
    )

    contenido = [
        {
            "type": "text",
            "text": generar_prompt(vista),
        },
        {
            "type": "image",
            "data": bytes_a_base64(
                arte_bytes
            ),
            "mime_type": arte_mime,
        },
    ]

    referencias = (
        obtener_referencias_aprobadas(
            vista
        )
    )

    for referencia in referencias:
        contenido.append(
            {
                "type": "image",
                "data": bytes_a_base64(
                    referencia
                ),
                "mime_type": detectar_mime_bytes(
                    referencia
                ),
            }
        )

    interaction = (
        cliente
        .interactions
        .create(
            model=MODELO_IMAGEN,
            input=contenido,
            response_format={
                "type": "image",
                "aspect_ratio": "4:5",
            },
        )
    )

    if (
        interaction is None
        or interaction.output_image is None
        or not interaction.output_image.data
    ):
        raise RuntimeError(
            "Gemini respondió, pero no "
            "devolvió una imagen."
        )

    salida = (
        interaction.output_image.data
    )

    if isinstance(
        salida,
        str,
    ):
        salida = base64.b64decode(
            salida
        )

    return salida


# =========================================================
# VALIDAR IMAGEN
# =========================================================

def validar_imagen(datos):
    try:
        imagen = Image.open(
            io.BytesIO(datos)
        )

        imagen.verify()

        return True

    except Exception:
        return False


# =========================================================
# DEPENDENCIAS DE CADA VISTA IA
# =========================================================

def puede_generar_vista(vista):
    if vista == "frente":
        return True

    if vista == "espalda":
        return st.session_state.get(
            clave_aprobado("frente"),
            False,
        )

    if vista in [
        "derecha",
        "izquierda",
    ]:
        return (
            st.session_state.get(
                clave_aprobado("frente"),
                False,
            )
            and
            st.session_state.get(
                clave_aprobado("espalda"),
                False,
            )
        )

    return False


# =========================================================
# MOSTRAR UNA VISTA IA
# =========================================================

def mostrar_vista_ia(
    vista,
    nombre,
    arte_bytes,
    arte_mime,
):
    st.subheader(
        f"📸 {nombre}"
    )

    imagen_actual = st.session_state.get(
        clave_imagen(vista)
    )

    aprobado = st.session_state.get(
        clave_aprobado(vista),
        False,
    )

    disponible = puede_generar_vista(
        vista
    )

    if not disponible:
        if vista == "espalda":
            st.info(
                "Primero aprueba el Frente."
            )
        else:
            st.info(
                "Primero aprueba Frente "
                "y Espalda."
            )

        return

    if aprobado:
        st.success(
            f"✅ {nombre} aprobado."
        )

    texto_boton = (
        f"🔄 Regenerar {nombre}"
        if imagen_actual
        else f"🤖 Generar {nombre} con IA"
    )

    if st.button(
        texto_boton,
        key=f"generar_{vista}",
        type="primary",
        width="stretch",
    ):
        limpiar_vista_ia(vista)

        try:
            with st.spinner(
                f"Generando {nombre}..."
            ):
                nueva_imagen = (
                    generar_mockup_ia(
                        vista,
                        arte_bytes,
                        arte_mime,
                    )
                )

            if not validar_imagen(
                nueva_imagen
            ):
                raise RuntimeError(
                    "La API no devolvió una "
                    "imagen válida."
                )

            st.session_state[
                clave_imagen(vista)
            ] = nueva_imagen

            st.session_state[
                clave_aprobado(vista)
            ] = False

            gc.collect()

            st.rerun()

        except Exception as e:
            st.error(
                f"❌ No se pudo generar "
                f"{nombre}."
            )

            st.exception(e)

    imagen_actual = st.session_state.get(
        clave_imagen(vista)
    )

    if imagen_actual:
        st.image(
            imagen_actual,
            caption=nombre,
            width="stretch",
        )

        col1, col2 = st.columns(2)

        with col1:
            if st.button(
                f"✅ Aprobar {nombre}",
                key=f"aprobar_{vista}",
                width="stretch",
                disabled=aprobado,
            ):
                st.session_state[
                    clave_aprobado(vista)
                ] = True

                st.rerun()

        with col2:
            if st.button(
                f"🗑️ Descartar {nombre}",
                key=f"descartar_{vista}",
                width="stretch",
            ):
                limpiar_vista_ia(vista)

                # Si se descarta una referencia
                # principal, invalidamos las vistas
                # dependientes.
                if vista == "frente":
                    limpiar_vista_ia("espalda")
                    limpiar_vista_ia("derecha")
                    limpiar_vista_ia("izquierda")

                elif vista == "espalda":
                    limpiar_vista_ia("derecha")
                    limpiar_vista_ia("izquierda")

                st.rerun()


# =========================================================
# MODO IA
# =========================================================

def mostrar_modo_ia(
    orden_actual,
):
    st.header(
        "🤖 Generación automática con IA"
    )

    st.caption(
        "Gemini genera las vistas una por una. "
        "El operador revisa y aprueba cada resultado."
    )

    st.info(
        "🧠 Solo se conservan las cuatro imágenes "
        "actuales. Al regenerar una vista, "
        "la anterior se elimina de memoria."
    )

    try:
        with st.spinner(
            "Preparando arte original..."
        ):
            arte_bytes, arte_mime = (
                descargar_arte_url(
                    orden_actual["Arte"]
                )
            )

    except Exception as e:
        st.error(
            f"❌ No se pudo leer "
            f"el arte original: {e}"
        )

        return False

    st.subheader(
        "🎨 Arte de referencia"
    )

    st.image(
        orden_actual["Arte"],
        width="stretch",
    )

    st.divider()

    with st.expander(
        "🧠 Ver prompts utilizados",
        expanded=False,
    ):
        vista_prompt = st.selectbox(
            "Prompt de:",
            [
                "Frente",
                "Espalda",
                "Lateral derecho",
                "Lateral izquierdo",
            ],
            key="selector_prompt_demo",
        )

        mapa_vista = {
            "Frente": "frente",
            "Espalda": "espalda",
            "Lateral derecho": "derecha",
            "Lateral izquierdo": "izquierda",
        }

        st.code(
            generar_prompt(
                mapa_vista[
                    vista_prompt
                ]
            ),
            language="text",
        )

    st.divider()

    # =====================================================
    # FRENTE
    # =====================================================

    mostrar_vista_ia(
        "frente",
        "Frente",
        arte_bytes,
        arte_mime,
    )

    st.divider()

    # =====================================================
    # ESPALDA
    # =====================================================

    mostrar_vista_ia(
        "espalda",
        "Espalda",
        arte_bytes,
        arte_mime,
    )

    st.divider()

    # =====================================================
    # LATERAL DERECHO
    # =====================================================

    mostrar_vista_ia(
        "derecha",
        "Lateral derecho",
        arte_bytes,
        arte_mime,
    )

    st.divider()

    # =====================================================
    # LATERAL IZQUIERDO
    # =====================================================

    mostrar_vista_ia(
        "izquierda",
        "Lateral izquierdo",
        arte_bytes,
        arte_mime,
    )

    completos = 0

    for vista, _ in VISTAS:
        if st.session_state.get(
            clave_aprobado(vista),
            False,
        ):
            completos += 1

    st.divider()

    st.header(
        "📊 Estado de generación IA"
    )

    columnas = st.columns(4)

    for indice, (
        vista,
        nombre,
    ) in enumerate(VISTAS):

        with columnas[indice]:
            aprobado = (
                st.session_state.get(
                    clave_aprobado(vista),
                    False,
                )
            )

            st.metric(
                nombre,
                (
                    "Aprobado ✅"
                    if aprobado
                    else "Pendiente"
                ),
            )

    st.progress(
        completos / 4
    )

    st.write(
        f"**{completos} de 4 vistas aprobadas.**"
    )

    return completos == 4


# =========================================================
# MODO MANUAL
# =========================================================

def mostrar_modo_manual(
    orden_actual,
):
    st.header(
        "🎨 Canva IA / Manual"
    )

    st.caption(
        "Genera los mockups fuera del ERP "
        "y carga las cuatro vistas."
    )

    st.info(
        "Esta opción queda disponible como respaldo "
        "si una generación automática no conserva "
        "correctamente logos, textos o detalles."
    )

    st.subheader(
        "🎨 Arte original"
    )

    st.image(
        orden_actual["Arte"],
        width="stretch",
    )

    st.divider()

    archivos = {}

    for vista, nombre in VISTAS:
        st.subheader(
            f"📤 {nombre}"
        )

        archivo = st.file_uploader(
            f"Subir {nombre}",
            type=[
                "png",
                "jpg",
                "jpeg",
                "webp",
            ],
            key=(
                f"manual_"
                f"{orden_actual['ID']}_"
                f"{vista}"
            ),
        )

        archivos[vista] = archivo

        if archivo is not None:
            st.image(
                archivo,
                caption=nombre,
                width=350,
            )

            st.success(
                f"✅ {nombre} cargado."
            )

        else:
            st.info(
                f"Pendiente: {nombre}"
            )

    cantidad = sum(
        1
        for archivo in archivos.values()
        if archivo is not None
    )

    st.divider()

    st.header(
        "📊 Estado del modo manual"
    )

    st.progress(
        cantidad / 4
    )

    st.write(
        f"**{cantidad} de 4 vistas cargadas.**"
    )

    confirmado = False

    if cantidad == 4:
        confirmado = st.checkbox(
            "Confirmo que revisé las cuatro "
            "imágenes y corresponden al arte "
            f"de la orden {orden_actual['Código']}.",
            key=(
                f"manual_confirmado_"
                f"{orden_actual['ID']}"
            ),
        )

        if confirmado:
            st.success(
                "✅ Mockups manuales revisados "
                "y confirmados."
            )

    return (
        cantidad == 4
        and confirmado
    )


# =========================================================
# GALERÍA FINAL IA
# =========================================================

def mostrar_galeria_final_ia():
    st.header(
        "🖼️ Galería final"
    )

    columnas = st.columns(4)

    for indice, (
        vista,
        nombre,
    ) in enumerate(VISTAS):

        with columnas[indice]:
            imagen = st.session_state.get(
                clave_imagen(vista)
            )

            if imagen:
                st.image(
                    imagen,
                    caption=nombre,
                    width="stretch",
                )


# =========================================================
# INTERFAZ PRINCIPAL
# =========================================================

def render_prueba():
    st.set_page_config(
        page_title=(
            "Prueba IA Mockups YUNPAR"
        ),
        page_icon="🤖",
        layout="wide",
    )

    supabase = init_connection()

    st.title(
        "🤖 Preparación de Mockups YUNPAR"
    )

    st.caption(
        "Demostración de los dos métodos "
        "de preparación de imágenes para catálogo."
    )

    st.warning(
        "🧪 MODO DEMOSTRACIÓN. "
        "Lee información existente, "
        "pero NO crea registros y "
        "NO sube archivos a Supabase."
    )

    # =====================================================
    # PASO 1
    # ORDEN
    # =====================================================

    st.divider()

    st.header(
        "1️⃣ Seleccionar orden"
    )

    try:
        df = consultar_ordenes_con_arte(
            supabase
        )

    except Exception as e:
        st.error(
            f"❌ Error consultando "
            f"órdenes: {e}"
        )
        return

    if df.empty:
        st.warning(
            "No existen órdenes con arte."
        )
        return

    col1, col2 = st.columns(2)

    with col1:
        buscar_codigo = st.text_input(
            "Buscar por código",
            placeholder="Ej: ORD-7259",
        )

    with col2:
        buscar_cliente = st.text_input(
            "Buscar por cliente",
            placeholder="Ej: AGRISUM",
        )

    df_filtrado = df.copy()

    if buscar_codigo:
        df_filtrado = (
            df_filtrado[
                df_filtrado["Código"]
                .astype(str)
                .str.contains(
                    buscar_codigo,
                    case=False,
                    na=False,
                )
            ]
        )

    if buscar_cliente:
        df_filtrado = (
            df_filtrado[
                df_filtrado["Cliente"]
                .astype(str)
                .str.contains(
                    buscar_cliente,
                    case=False,
                    na=False,
                )
            ]
        )

    df_filtrado = (
        df_filtrado
        .reset_index(drop=True)
    )

    if df_filtrado.empty:
        st.warning(
            "No hay resultados."
        )
        return

    evento = st.dataframe(
        df_filtrado[
            [
                "Código",
                "Cliente",
                "Estado",
                "Fecha",
            ]
        ],
        hide_index=True,
        width="stretch",
        on_select="rerun",
        selection_mode="single-row",
        key="demo_tabla_ordenes",
    )

    if evento.selection.rows:
        indice = evento.selection.rows[0]

        nueva_orden = (
            df_filtrado
            .iloc[indice]
            .to_dict()
        )

        orden_anterior = (
            st.session_state.get(
                "demo_orden_actual"
            )
        )

        id_anterior = (
            str(
                orden_anterior.get("ID")
            )
            if orden_anterior
            else ""
        )

        nuevo_id = str(
            nueva_orden.get("ID")
        )

        if (
            id_anterior
            and id_anterior != nuevo_id
        ):
            limpiar_todos_mockups_ia()

        st.session_state[
            "demo_orden_actual"
        ] = nueva_orden

    orden_actual = (
        st.session_state.get(
            "demo_orden_actual"
        )
    )

    if not orden_actual:
        st.info(
            "👆 Selecciona una orden."
        )
        return

    st.divider()

    st.header(
        "✅ Orden seleccionada"
    )

    col_arte, col_info = st.columns(
        [2, 1]
    )

    with col_arte:
        st.image(
            orden_actual["Arte"],
            caption="Arte original",
            width="stretch",
        )

    with col_info:
        st.subheader(
            orden_actual["Código"]
        )

        st.write(
            "**Cliente**"
        )
        st.write(
            orden_actual["Cliente"]
        )

        st.write(
            "**Estado**"
        )
        st.write(
            orden_actual["Estado"]
        )

        st.write(
            "**Fecha**"
        )
        st.write(
            orden_actual["Fecha"]
        )

    # =====================================================
    # PASO 2
    # MÉTODO
    # =====================================================

    st.divider()

    st.header(
        "2️⃣ Método de generación"
    )

    metodo = st.radio(
        "¿Cómo deseas preparar los mockups?",
        [
            "🤖 IA integrada YUNPAR",
            "🎨 Canva IA / Manual",
        ],
        horizontal=True,
        key="demo_metodo",
    )

    if metodo == "🤖 IA integrada YUNPAR":
        st.success(
            "🤖 La IA utilizará directamente "
            "el arte de la orden y generará "
            "cada vista por separado."
        )

        completo = mostrar_modo_ia(
            orden_actual
        )

        if completo:
            st.divider()

            mostrar_galeria_final_ia()

    else:
        st.success(
            "🎨 El operador genera los mockups "
            "con Canva IA u otra herramienta "
            "y los carga manualmente."
        )

        completo = mostrar_modo_manual(
            orden_actual
        )

    # =====================================================
    # FINAL
    # =====================================================

    st.divider()

    st.header(
        "📦 Resultado de la preparación"
    )

    if completo:
        st.success(
            "🎉 4/4 MOCKUPS LISTOS. "
            "El diseño está preparado para "
            "continuar con clasificación IA "
            "y Catálogo de Diseños."
        )

        st.button(
            "➡️ Continuar a clasificación "
            "(DEMOSTRACIÓN)",
            disabled=True,
            width="stretch",
        )

    else:
        st.info(
            "Completa y revisa las cuatro vistas "
            "para continuar."
        )

    st.warning(
        "🔒 MODO DEMOSTRACIÓN: "
        "no se modificó Supabase, "
        "no se crearon registros "
        "y no se subieron archivos."
    )


# =========================================================
# EJECUCIÓN
# =========================================================

if __name__ == "__main__":
    render_prueba()