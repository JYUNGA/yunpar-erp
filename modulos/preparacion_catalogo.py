import streamlit as st
import pandas as pd
import google.generativeai as genai

import io
import json
import re

from datetime import datetime

import pytz

from PIL import Image


# =========================================================
# MÓDULO: PREPARACIÓN DE CATÁLOGO
# =========================================================


# =========================================================
# UTILIDADES
# =========================================================

def convertir_lista_texto(valor):

    if isinstance(valor, list):

        return [
            str(item).strip()
            for item in valor
            if str(item).strip()
        ]

    if not valor:

        return []

    return [
        item.strip()
        for item in str(valor).split(",")
        if item.strip()
    ]


def convertir_lista_a_texto(valor):

    if not valor:

        return ""

    if isinstance(valor, str):

        return valor

    return ", ".join(
        str(item).strip()
        for item in valor
        if str(item).strip()
    )


# =========================================================
# PROMPT ESTANDARIZADO PARA MOCKUPS
# =========================================================

def generar_prompt_mockup(
    presentacion,
    vista,
):

    descripcion_presentacion = {

        "Solo prenda (sin persona)": (
            "la prenda presentada sin persona, "
            "con volumen tridimensional realista, "
            "forma natural y apariencia de fotografía "
            "profesional de producto"
        ),

        "Hombre": (
            "un modelo masculino usando la prenda, "
            "con proporciones naturales y pose profesional "
            "de catálogo"
        ),

        "Mujer": (
            "una modelo femenina usando la prenda, "
            "con proporciones naturales y pose profesional "
            "de catálogo"
        ),

        "Niño": (
            "un modelo infantil usando la prenda, "
            "con pose profesional de catálogo "
            "y proporciones naturales"
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
            "Solo prenda (sin persona)"
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
No crear una prenda diferente.

Genera solamente:
{vista}.
"""

    return prompt.strip()


# =========================================================
# CONVERTIR ARCHIVO A IMAGEN
# =========================================================

def archivo_a_imagen(
    archivo,
):

    if archivo is None:

        return None

    try:

        datos = archivo.getvalue()

        imagen = Image.open(
            io.BytesIO(
                datos
            )
        )

        return imagen.convert(
            "RGB"
        )

    except Exception:

        return None


# =========================================================
# LIMPIAR JSON DE GEMINI
# =========================================================

def extraer_json_respuesta(
    texto,
):

    if not texto:

        raise ValueError(
            "La IA no devolvió información."
        )

    texto = texto.strip()

    texto = re.sub(
        r"^```json\s*",
        "",
        texto,
        flags=re.IGNORECASE,
    )

    texto = re.sub(
        r"^```\s*",
        "",
        texto,
    )

    texto = re.sub(
        r"\s*```$",
        "",
        texto,
    )

    inicio = texto.find(
        "{"
    )

    fin = texto.rfind(
        "}"
    )

    if (
        inicio == -1
        or fin == -1
    ):

        raise ValueError(
            "No se encontró un objeto JSON "
            "en la respuesta de la IA."
        )

    texto_json = texto[
        inicio:fin + 1
    ]

    return json.loads(
        texto_json
    )


# =========================================================
# NORMALIZAR CLASIFICACIÓN
# =========================================================

def normalizar_clasificacion(
    datos,
    presentacion,
):

    colores = datos.get(
        "colores_principales",
        [],
    )

    etiquetas = datos.get(
        "etiquetas",
        [],
    )

    if isinstance(
        colores,
        str,
    ):

        colores = convertir_lista_texto(
            colores
        )

    if isinstance(
        etiquetas,
        str,
    ):

        etiquetas = convertir_lista_texto(
            etiquetas
        )

    return {

        "tipo_producto": str(
            datos.get(
                "tipo_producto",
                "",
            )
            or ""
        ).strip(),

        "deporte": str(
            datos.get(
                "deporte",
                "",
            )
            or ""
        ).strip(),

        "tipo_prenda": str(
            datos.get(
                "tipo_prenda",
                "",
            )
            or ""
        ).strip(),

        "presentacion": (
            presentacion
        ),

        "colores_principales": (
            colores
        ),

        "patron": str(
            datos.get(
                "patron",
                "",
            )
            or ""
        ).strip(),

        "estilo": str(
            datos.get(
                "estilo",
                "",
            )
            or ""
        ).strip(),

        "descripcion": str(
            datos.get(
                "descripcion",
                "",
            )
            or ""
        ).strip(),

        "etiquetas": (
            etiquetas
        ),
    }


# =========================================================
# ANALIZAR MOCKUPS CON IA
# =========================================================

def analizar_mockups_con_ia(
    mockups,
    orden_actual,
    presentacion,
):

    try:

        api_key = st.secrets[
            "gemini"
        ][
            "api_key"
        ]

    except Exception:

        raise RuntimeError(
            "No se encontró la configuración "
            "de Gemini en secrets.toml."
        )

    genai.configure(
        api_key=api_key
    )

    model = genai.GenerativeModel(
        "gemini-2.5-flash"
    )

    imagenes = []

    for archivo in mockups:

        imagen = archivo_a_imagen(
            archivo
        )

        if imagen is not None:

            imagenes.append(
                imagen
            )

    if not imagenes:

        raise RuntimeError(
            "No se encontraron imágenes válidas "
            "para analizar."
        )

    codigo = orden_actual.get(
        "Código",
        "",
    )

    prompt = f"""
Eres un sistema de clasificación visual para el catálogo de YUNPAR, empresa de uniformes y prendas personalizadas.

ORDEN:
{codigo}

PRESENTACIÓN SELECCIONADA POR EL OPERADOR:
{presentacion}

Analiza en conjunto las imágenes proporcionadas del MISMO diseño.

Tu tarea NO es identificar personas.
NO debes inferir identidad, etnia ni otras características personales de modelos.

Debes analizar únicamente la PRENDA, el diseño gráfico y su uso comercial.

Devuelve EXCLUSIVAMENTE un objeto JSON válido.

Usa exactamente esta estructura:

{{
    "tipo_producto": "",
    "deporte": "",
    "tipo_prenda": "",
    "colores_principales": [],
    "patron": "",
    "estilo": "",
    "descripcion": "",
    "etiquetas": []
}}

REGLAS:

tipo_producto:
Describe de forma general el producto.

Ejemplos:
"Uniforme deportivo"
"Camiseta deportiva"
"Conjunto deportivo"
"Uniforme escolar"
"Prenda corporativa"

deporte:
Indica el deporte si visualmente resulta razonable.

Ejemplos:
"Fútbol"
"Baloncesto"
"Voleibol"
"Ciclismo"

Si no puede determinarse:
"General"

tipo_prenda:

Ejemplos:
"Camiseta"
"Jersey"
"Polo"
"Conjunto"
"Camiseta y pantaloneta"

colores_principales:

Devuelve solamente los colores visualmente predominantes.
Máximo 5.

patron:

Ejemplos:
"Rayas"
"Geométrico"
"Degradado"
"Pinceladas"
"Abstracto"
"Liso"
"Gráfico deportivo"

estilo:

Ejemplos:
"Deportivo moderno"
"Minimalista"
"Competitivo"
"Corporativo"
"Escolar"

descripcion:

Escribe una descripción comercial objetiva
de 1 a 2 oraciones.

No inventes información que no pueda observarse.

etiquetas:

Devuelve entre 5 y 12 palabras
o frases cortas útiles para búsquedas.

Incluye deporte, colores, estilo,
tipo de prenda y características visuales.

IMPORTANTE:

No incluyas texto fuera del JSON.
No uses Markdown.
No agregues explicaciones.
No inventes marcas.
No identifiques personas.
"""

    contenido = [
        prompt
    ]

    contenido.extend(
        imagenes
    )

    respuesta = model.generate_content(
        contenido
    )

    texto = (
        respuesta.text
        if respuesta
        else ""
    )

    datos = extraer_json_respuesta(
        texto
    )

    return normalizar_clasificacion(
        datos,
        presentacion,
    )


# =========================================================
# GENERAR TEXTO SEMÁNTICO
# =========================================================

def generar_texto_semantico(
    clasificacion,
):

    colores = convertir_lista_a_texto(
        clasificacion.get(
            "colores_principales",
            [],
        )
    )

    etiquetas = convertir_lista_a_texto(
        clasificacion.get(
            "etiquetas",
            [],
        )
    )

    partes = [

        clasificacion.get(
            "tipo_producto",
            "",
        ),

        clasificacion.get(
            "tipo_prenda",
            "",
        ),

        clasificacion.get(
            "deporte",
            "",
        ),

        (
            f"Presentación: "
            f"{clasificacion.get('presentacion', '')}"
        ),

        (
            f"Colores principales: "
            f"{colores}"
            if colores
            else ""
        ),

        (
            f"Patrón: "
            f"{clasificacion.get('patron', '')}"
        ),

        (
            f"Estilo: "
            f"{clasificacion.get('estilo', '')}"
        ),

        clasificacion.get(
            "descripcion",
            "",
        ),

        (
            f"Etiquetas: "
            f"{etiquetas}"
            if etiquetas
            else ""
        ),
    ]

    partes = [
        str(parte).strip()
        for parte in partes
        if str(parte).strip()
    ]

    return ". ".join(
        partes
    )


# =========================================================
# CONSTRUIR PAQUETE PARA CATÁLOGO
# =========================================================

def construir_paquete_catalogo(
    orden_actual,
    datos_mockups,
    clasificacion,
    texto_semantico,
    titulo_publico,
    observacion_operador,
):

    zona_horaria = pytz.timezone(
        "America/Guayaquil"
    )

    fecha_preparacion = datetime.now(
        zona_horaria
    ).strftime(
        "%d/%m/%Y %H:%M:%S"
    )

    mockups = [

        {
            "orden": 1,
            "vista": "Frente",
            "portada": True,
            "archivo": (
                datos_mockups[
                    "frente"
                ].name
                if datos_mockups.get(
                    "frente"
                )
                else ""
            ),
        },

        {
            "orden": 2,
            "vista": "Espalda",
            "portada": False,
            "archivo": (
                datos_mockups[
                    "espalda"
                ].name
                if datos_mockups.get(
                    "espalda"
                )
                else ""
            ),
        },

        {
            "orden": 3,
            "vista": "Lateral derecho",
            "portada": False,
            "archivo": (
                datos_mockups[
                    "lateral_derecho"
                ].name
                if datos_mockups.get(
                    "lateral_derecho"
                )
                else ""
            ),
        },

        {
            "orden": 4,
            "vista": "Lateral izquierdo",
            "portada": False,
            "archivo": (
                datos_mockups[
                    "lateral_izquierdo"
                ].name
                if datos_mockups.get(
                    "lateral_izquierdo"
                )
                else ""
            ),
        },
    ]

    paquete = {

        "estado": (
            "LISTO_PARA_CATALOGO"
        ),

        "modo": (
            "PRUEBA"
        ),

        "codigo_orden": (
            orden_actual.get(
                "Código",
                "",
            )
        ),

        "orden_id": (
            orden_actual.get(
                "ID"
            )
        ),

        "cliente": (
            orden_actual.get(
                "Cliente",
                "",
            )
        ),

        "titulo_publico": (
            titulo_publico.strip()
        ),

        "descripcion_publica": (
            clasificacion.get(
                "descripcion",
                "",
            )
        ),

        "tipo_producto": (
            clasificacion.get(
                "tipo_producto",
                "",
            )
        ),

        "tipo_prenda": (
            clasificacion.get(
                "tipo_prenda",
                "",
            )
        ),

        "deporte": (
            clasificacion.get(
                "deporte",
                "",
            )
        ),

        "presentacion": (
            clasificacion.get(
                "presentacion",
                "",
            )
        ),

        "colores": (
            clasificacion.get(
                "colores_principales",
                [],
            )
        ),

        "patron": (
            clasificacion.get(
                "patron",
                "",
            )
        ),

        "estilo": (
            clasificacion.get(
                "estilo",
                "",
            )
        ),

        "etiquetas": (
            clasificacion.get(
                "etiquetas",
                [],
            )
        ),

        "texto_semantico": (
            texto_semantico
        ),

        "embedding": None,

        "embedding_estado": (
            "PENDIENTE"
        ),

        "mockups": (
            mockups
        ),

        "cantidad_mockups": (
            len(
                mockups
            )
        ),

        "metodo_generacion": (
            datos_mockups.get(
                "metodo",
                "",
            )
        ),

        "observacion_operador": (
            observacion_operador.strip()
        ),

        "fecha_preparacion": (
            fecha_preparacion
        ),
    }

    return paquete


# =========================================================
# ESTADO GENERAL
# =========================================================

def mostrar_estado_proceso(
    paso1_completo=False,
    paso2_completo=False,
    paso3_completo=False,
    paso4_completo=False,
):

    st.divider()

    st.markdown(
        "## 📊 Estado del proceso"
    )

    col1, col2, col3, col4 = (
        st.columns(4)
    )

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

    with col3:

        st.metric(
            "Paso 3",
            (
                "Completado"
                if paso3_completo
                else (
                    "Disponible"
                    if paso2_completo
                    else "Pendiente"
                )
            ),
        )

        st.caption(
            "Clasificación con IA."
        )

    with col4:

        st.metric(
            "Paso 4",
            (
                "Completado"
                if paso4_completo
                else (
                    "Disponible"
                    if paso3_completo
                    else "Pendiente"
                )
            ),
        )

        st.caption(
            "Enviar al catálogo."
        )

    if paso4_completo:

        st.success(
            "✅ Preparación final completada. "
            "El diseño quedó listo para el "
            "Catálogo de Diseños."
        )

    elif paso3_completo:

        st.success(
            "✅ La clasificación fue confirmada. "
            "El diseño está listo para continuar "
            "al Paso 4."
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

    codigo = orden_actual.get(
        "Código",
        "",
    )

    orden_id = orden_actual.get(
        "ID"
    )

    arte_url = orden_actual.get(
        "Arte"
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
    # MÉTODO
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
        key=f"preparacion_metodo_{orden_id}",
    )

    if metodo == "Canva IA - Manual":

        st.info(
            "✅ Método actual recomendado. "
            "El operador visualiza o descarga el arte, "
            "utiliza el prompt oficial y genera "
            "cada vista por separado en Canva IA."
        )

    else:

        st.info(
            "Puedes utilizar otra herramienta de IA, "
            "pero debes mantener las reglas visuales "
            "establecidas por YUNPAR."
        )

    # =====================================================
    # PRESENTACIÓN
    # =====================================================

    st.markdown(
        "### 👕 Presentación del mockup"
    )

    presentacion = st.selectbox(
        "Selecciona cómo se presentará este diseño",
        [
            "Solo prenda (sin persona)",
            "Hombre",
            "Mujer",
            "Niño",
        ],
        key=f"preparacion_presentacion_v2_{orden_id}",
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
    # PROMPT
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
        key=f"preparacion_vista_prompt_{orden_id}",
    )

    prompt_actual = generar_prompt_mockup(
        presentacion,
        vista_prompt,
    )

    st.code(
        prompt_actual,
        language="text",
    )

    st.info(
        "💡 Para obtener consistencia, usa primero "
        "el arte original como referencia. "
        "Después utiliza el primer mockup aprobado "
        "como referencia visual para las siguientes vistas."
    )

    # =====================================================
    # REGLAS
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
        key=f"preparacion_frente_{orden_id}",
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
        key=f"preparacion_espalda_{orden_id}",
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
        key=f"preparacion_derecha_{orden_id}",
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
        key=f"preparacion_izquierda_{orden_id}",
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
    # ESTADO
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

        archivo = mockup[
            "Archivo"
        ]

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
            key=f"preparacion_confirmacion_{orden_id}",
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

    paso2_completo = (
        todas_cargadas
        and confirmado
    )

    if paso2_completo:

        datos_mockups = {

            "orden_id": (
                orden_id
            ),

            "codigo": (
                codigo
            ),

            "presentacion": (
                presentacion
            ),

            "metodo": (
                metodo
            ),

            "frente": (
                frente
            ),

            "espalda": (
                espalda
            ),

            "lateral_derecho": (
                lateral_derecho
            ),

            "lateral_izquierdo": (
                lateral_izquierdo
            ),
        }

        st.session_state[
            "preparacion_catalogo_mockups"
        ] = datos_mockups

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

    return (
        paso2_completo,
        {

            "presentacion": (
                presentacion
            ),

            "metodo": (
                metodo
            ),

            "frente": (
                frente
            ),

            "espalda": (
                espalda
            ),

            "lateral_derecho": (
                lateral_derecho
            ),

            "lateral_izquierdo": (
                lateral_izquierdo
            ),
        },
    )


# =========================================================
# PASO 3
# CLASIFICACIÓN IA
# =========================================================

def mostrar_paso_3(
    orden_actual,
    datos_mockups,
):

    st.divider()

    st.markdown(
        "## 3️⃣ Clasificación automática con IA"
    )

    st.caption(
        "La IA analizará las cuatro vistas del producto "
        "y propondrá información útil para el catálogo."
    )

    st.info(
        "🤖 La IA solamente propone la clasificación. "
        "El operador debe revisarla y confirmarla "
        "antes de continuar."
    )

    orden_id = orden_actual.get(
        "ID"
    )

    codigo = orden_actual.get(
        "Código",
        "",
    )

    presentacion = datos_mockups.get(
        "presentacion",
        "",
    )

    mockups = [

        datos_mockups.get(
            "frente"
        ),

        datos_mockups.get(
            "espalda"
        ),

        datos_mockups.get(
            "lateral_derecho"
        ),

        datos_mockups.get(
            "lateral_izquierdo"
        ),
    ]

    clave_clasificacion = (
        f"preparacion_clasificacion_{orden_id}"
    )

    clave_confirmada = (
        f"preparacion_clasificacion_confirmada_{orden_id}"
    )

    # =====================================================
    # ANALIZAR
    # =====================================================

    if st.button(
        "🤖 Analizar mockups con IA",
        type="primary",
        width="stretch",
        key=f"preparacion_analizar_ia_{orden_id}",
    ):

        try:

            with st.spinner(
                "Analizando las cuatro vistas..."
            ):

                clasificacion = (
                    analizar_mockups_con_ia(
                        mockups,
                        orden_actual,
                        presentacion,
                    )
                )

            st.session_state[
                clave_clasificacion
            ] = clasificacion

            st.session_state[
                clave_confirmada
            ] = False

            st.success(
                "✅ Análisis terminado. "
                "Revisa los resultados antes de confirmar."
            )

            st.rerun()

        except Exception as e:

            st.error(
                f"❌ No se pudo realizar "
                f"la clasificación con IA: {e}"
            )

    clasificacion = (
        st.session_state.get(
            clave_clasificacion
        )
    )

    if not clasificacion:

        st.warning(
            "Todavía no se ha realizado "
            "la clasificación automática."
        )

        return False

    # =====================================================
    # RESULTADOS
    # =====================================================

    st.markdown(
        "### 🧠 Resultado propuesto por la IA"
    )

    colores_iniciales = (
        convertir_lista_a_texto(
            clasificacion.get(
                "colores_principales",
                [],
            )
        )
    )

    etiquetas_iniciales = (
        convertir_lista_a_texto(
            clasificacion.get(
                "etiquetas",
                [],
            )
        )
    )

    with st.form(
        key=f"form_clasificacion_{orden_id}"
    ):

        col1, col2 = (
            st.columns(2)
        )

        with col1:

            tipo_producto = st.text_input(
                "Tipo de producto",
                value=clasificacion.get(
                    "tipo_producto",
                    "",
                ),
            )

            deporte = st.text_input(
                "Deporte / uso",
                value=clasificacion.get(
                    "deporte",
                    "",
                ),
            )

            tipo_prenda = st.text_input(
                "Tipo de prenda",
                value=clasificacion.get(
                    "tipo_prenda",
                    "",
                ),
            )

            presentacion_editada = (
                st.text_input(
                    "Presentación",
                    value=clasificacion.get(
                        "presentacion",
                        presentacion,
                    ),
                    disabled=True,
                )
            )

        with col2:

            colores_texto = st.text_input(
                "Colores principales",
                value=colores_iniciales,
            )

            patron = st.text_input(
                "Patrón visual",
                value=clasificacion.get(
                    "patron",
                    "",
                ),
            )

            estilo = st.text_input(
                "Estilo",
                value=clasificacion.get(
                    "estilo",
                    "",
                ),
            )

        descripcion = st.text_area(
            "Descripción pública propuesta",
            value=clasificacion.get(
                "descripcion",
                "",
            ),
            height=110,
        )

        etiquetas_texto = st.text_area(
            "Etiquetas para búsqueda",
            value=etiquetas_iniciales,
            height=90,
        )

        guardar_revision = (
            st.form_submit_button(
                "💾 Guardar revisión del operador",
                width="stretch",
            )
        )

    if guardar_revision:

        clasificacion_editada = {

            "tipo_producto": (
                tipo_producto.strip()
            ),

            "deporte": (
                deporte.strip()
            ),

            "tipo_prenda": (
                tipo_prenda.strip()
            ),

            "presentacion": (
                presentacion_editada
            ),

            "colores_principales": (
                convertir_lista_texto(
                    colores_texto
                )
            ),

            "patron": (
                patron.strip()
            ),

            "estilo": (
                estilo.strip()
            ),

            "descripcion": (
                descripcion.strip()
            ),

            "etiquetas": (
                convertir_lista_texto(
                    etiquetas_texto
                )
            ),
        }

        st.session_state[
            clave_clasificacion
        ] = clasificacion_editada

        st.session_state[
            clave_confirmada
        ] = False

        st.success(
            "✅ Revisión guardada temporalmente."
        )

        st.rerun()

    clasificacion = (
        st.session_state.get(
            clave_clasificacion,
            clasificacion,
        )
    )

    # =====================================================
    # RESUMEN
    # =====================================================

    st.markdown(
        "### 📋 Clasificación actual"
    )

    resumen = pd.DataFrame(
        [

            {
                "Campo": "Tipo de producto",
                "Valor": clasificacion.get(
                    "tipo_producto",
                    "",
                ),
            },

            {
                "Campo": "Deporte / uso",
                "Valor": clasificacion.get(
                    "deporte",
                    "",
                ),
            },

            {
                "Campo": "Tipo de prenda",
                "Valor": clasificacion.get(
                    "tipo_prenda",
                    "",
                ),
            },

            {
                "Campo": "Presentación",
                "Valor": clasificacion.get(
                    "presentacion",
                    "",
                ),
            },

            {
                "Campo": "Colores",
                "Valor": convertir_lista_a_texto(
                    clasificacion.get(
                        "colores_principales",
                        [],
                    )
                ),
            },

            {
                "Campo": "Patrón",
                "Valor": clasificacion.get(
                    "patron",
                    "",
                ),
            },

            {
                "Campo": "Estilo",
                "Valor": clasificacion.get(
                    "estilo",
                    "",
                ),
            },

            {
                "Campo": "Etiquetas",
                "Valor": convertir_lista_a_texto(
                    clasificacion.get(
                        "etiquetas",
                        [],
                    )
                ),
            },
        ]
    )

    st.dataframe(
        resumen,
        hide_index=True,
        width="stretch",
    )

    st.markdown(
        "**Descripción**"
    )

    st.write(
        clasificacion.get(
            "descripcion",
            "",
        )
        or "Sin descripción"
    )

    # =====================================================
    # TEXTO SEMÁNTICO
    # =====================================================

    texto_semantico = (
        generar_texto_semantico(
            clasificacion
        )
    )

    st.markdown(
        "### 🔎 Vista previa para búsqueda inteligente"
    )

    st.caption(
        "Este texto se utilizará más adelante "
        "para generar el embedding vectorial."
    )

    st.code(
        texto_semantico,
        language="text",
    )

    # =====================================================
    # CONFIRMAR
    # =====================================================

    st.divider()

    confirmar = st.checkbox(
        (
            "Confirmo que revisé la clasificación "
            f"del diseño {codigo} y que "
            "la información es correcta."
        ),
        key=f"preparacion_confirmar_clasificacion_{orden_id}",
    )

    if st.button(
        "✅ Confirmar clasificación",
        disabled=not confirmar,
        width="stretch",
        key=f"preparacion_boton_confirmar_{orden_id}",
    ):

        st.session_state[
            clave_confirmada
        ] = True

        st.session_state[
            "preparacion_catalogo_clasificacion"
        ] = {

            "orden_id": (
                orden_id
            ),

            "codigo": (
                codigo
            ),

            "clasificacion": (
                clasificacion
            ),

            "texto_semantico": (
                texto_semantico
            ),
        }

        st.success(
            "✅ PASO 3 COMPLETADO. "
            "La clasificación quedó confirmada "
            "temporalmente."
        )

        st.rerun()

    paso3_completo = bool(
        st.session_state.get(
            clave_confirmada,
            False,
        )
    )

    if paso3_completo:

        st.success(
            "✅ PASO 3 COMPLETADO. "
            "Clasificación revisada y confirmada."
        )

        st.info(
            "🔒 Todavía no se guardó esta "
            "clasificación en Supabase."
        )

    return paso3_completo


# =========================================================
# PASO 4
# ENVIAR AL CATÁLOGO
# =========================================================

def mostrar_paso_4(
    orden_actual,
    datos_mockups,
):

    st.divider()

    st.markdown(
        "## 4️⃣ Enviar al Catálogo de Diseños"
    )

    st.caption(
        "Revisa el paquete final antes de enviarlo "
        "al módulo de administración del catálogo."
    )

    st.warning(
        "🧪 MODO PRUEBA ACTIVO. "
        "El paquete se preparará únicamente en memoria. "
        "Todavía NO se escribirá en Supabase."
    )

    orden_id = orden_actual.get(
        "ID"
    )

    codigo = orden_actual.get(
        "Código",
        "",
    )

    datos_clasificacion = (
        st.session_state.get(
            "preparacion_catalogo_clasificacion"
        )
    )

    if (
        not datos_clasificacion
        or str(
            datos_clasificacion.get(
                "orden_id"
            )
        )
        != str(
            orden_id
        )
    ):

        st.error(
            "❌ No se encontró una clasificación "
            "confirmada para esta orden."
        )

        return False

    clasificacion = (
        datos_clasificacion.get(
            "clasificacion",
            {},
        )
    )

    texto_semantico = (
        datos_clasificacion.get(
            "texto_semantico",
            "",
        )
    )

    # =====================================================
    # TÍTULO
    # =====================================================

    tipo_producto = (
        clasificacion.get(
            "tipo_producto",
            "Diseño",
        )
    )

    titulo_sugerido = (
        f"{tipo_producto} - {codigo}"
    )

    st.markdown(
        "### 📝 Información final"
    )

    titulo_publico = st.text_input(
        "Título público del diseño",
        value=titulo_sugerido,
        key=f"preparacion_titulo_publico_{orden_id}",
    )

    observacion_operador = st.text_area(
        "Observación interna del operador",
        placeholder=(
            "Opcional. Ej: Mockups revisados, "
            "clasificación corregida a Fútbol."
        ),
        key=f"preparacion_observacion_final_{orden_id}",
    )

    # =====================================================
    # RESUMEN
    # =====================================================

    st.markdown(
        "### 📦 Resumen del paquete"
    )

    col1, col2, col3 = (
        st.columns(3)
    )

    with col1:

        st.metric(
            "Orden",
            codigo,
        )

        st.caption(
            orden_actual.get(
                "Cliente",
                "",
            )
        )

    with col2:

        st.metric(
            "Mockups",
            "4 / 4",
        )

        st.caption(
            "Frente + espalda + laterales"
        )

    with col3:

        st.metric(
            "Clasificación IA",
            "Confirmada",
        )

        st.caption(
            "Revisada por el operador"
        )

    # =====================================================
    # DATOS CLASIFICADOS
    # =====================================================

    resumen_final = pd.DataFrame(
        [

            {
                "Dato": "Tipo de producto",
                "Valor": clasificacion.get(
                    "tipo_producto",
                    "",
                ),
            },

            {
                "Dato": "Deporte / uso",
                "Valor": clasificacion.get(
                    "deporte",
                    "",
                ),
            },

            {
                "Dato": "Tipo de prenda",
                "Valor": clasificacion.get(
                    "tipo_prenda",
                    "",
                ),
            },

            {
                "Dato": "Presentación",
                "Valor": clasificacion.get(
                    "presentacion",
                    "",
                ),
            },

            {
                "Dato": "Colores",
                "Valor": convertir_lista_a_texto(
                    clasificacion.get(
                        "colores_principales",
                        [],
                    )
                ),
            },

            {
                "Dato": "Patrón",
                "Valor": clasificacion.get(
                    "patron",
                    "",
                ),
            },

            {
                "Dato": "Estilo",
                "Valor": clasificacion.get(
                    "estilo",
                    "",
                ),
            },
        ]
    )

    st.dataframe(
        resumen_final,
        hide_index=True,
        width="stretch",
    )

    # =====================================================
    # MOCKUPS
    # =====================================================

    st.markdown(
        "### 🖼️ Imágenes que se enviarán"
    )

    col_img1, col_img2, col_img3, col_img4 = (
        st.columns(4)
    )

    with col_img1:

        if datos_mockups.get(
            "frente"
        ):

            st.image(
                datos_mockups[
                    "frente"
                ],
                caption="⭐ Frente",
                width="stretch",
            )

    with col_img2:

        if datos_mockups.get(
            "espalda"
        ):

            st.image(
                datos_mockups[
                    "espalda"
                ],
                caption="Espalda",
                width="stretch",
            )

    with col_img3:

        if datos_mockups.get(
            "lateral_derecho"
        ):

            st.image(
                datos_mockups[
                    "lateral_derecho"
                ],
                caption="Lateral derecho",
                width="stretch",
            )

    with col_img4:

        if datos_mockups.get(
            "lateral_izquierdo"
        ):

            st.image(
                datos_mockups[
                    "lateral_izquierdo"
                ],
                caption="Lateral izquierdo",
                width="stretch",
            )

    # =====================================================
    # BÚSQUEDA INTELIGENTE
    # =====================================================

    st.markdown(
        "### 🔎 Preparación para búsqueda inteligente"
    )

    st.success(
        "✅ Texto semántico preparado."
    )

    st.code(
        texto_semantico,
        language="text",
    )

    st.info(
        "🧠 Embedding vectorial: PENDIENTE. "
        "Lo conectaremos posteriormente con pgvector "
        "en Supabase."
    )

    # =====================================================
    # VALIDACIÓN FINAL
    # =====================================================

    st.divider()

    confirmacion_final = st.checkbox(
        (
            "Confirmo que revisé el paquete final "
            f"de la orden {codigo} y está listo "
            "para el Catálogo de Diseños."
        ),
        key=f"preparacion_confirmacion_final_{orden_id}",
    )

    clave_paquete = (
        f"preparacion_paquete_catalogo_{orden_id}"
    )

    if st.button(
        "📦 Enviar al Catálogo de Diseños (MODO PRUEBA)",
        type="primary",
        disabled=(
            not confirmacion_final
            or not titulo_publico.strip()
        ),
        width="stretch",
        key=f"preparacion_enviar_catalogo_{orden_id}",
    ):

        paquete = construir_paquete_catalogo(
            orden_actual=orden_actual,
            datos_mockups=datos_mockups,
            clasificacion=clasificacion,
            texto_semantico=texto_semantico,
            titulo_publico=titulo_publico,
            observacion_operador=observacion_operador,
        )

        st.session_state[
            clave_paquete
        ] = paquete

        st.session_state[
            "preparacion_catalogo_paquete_final"
        ] = paquete

        st.success(
            "✅ Paquete preparado correctamente."
        )

        st.rerun()

    paquete = (
        st.session_state.get(
            clave_paquete
        )
    )

    if not paquete:

        return False

    # =====================================================
    # PASO 4 COMPLETO
    # =====================================================

    st.success(
        "✅ PASO 4 COMPLETADO EN MODO PRUEBA. "
        "El paquete quedó preparado para "
        "Catálogo de Diseños."
    )

    st.info(
        "🔒 No se creó ningún registro ni archivo "
        "nuevo en Supabase."
    )

    # =====================================================
    # DETALLE DEL PAQUETE
    # =====================================================

    with st.expander(
        "📋 Ver paquete preparado",
        expanded=False,
    ):

        st.json(
            paquete
        )

    # =====================================================
    # DESCARGAR EVIDENCIA JSON
    # =====================================================

    paquete_json = json.dumps(
        paquete,
        ensure_ascii=False,
        indent=4,
    )

    st.download_button(
        label="⬇️ Descargar paquete de prueba (.json)",
        data=paquete_json,
        file_name=(
            f"{codigo}_catalogo_prueba.json"
        ),
        mime="application/json",
        width="stretch",
        key=f"preparacion_descargar_paquete_{orden_id}",
    )

    st.caption(
        "Este archivo es únicamente una evidencia "
        "del paquete preparado. "
        "No reemplaza el futuro registro en Supabase."
    )

    return True


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
        "Actualmente trabaja con consultas, "
        "archivos temporales y clasificación IA. "
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
    # ÓRDENES
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

        buscar_codigo = st.text_input(
            "Buscar por código de orden",
            placeholder="Ej: ORD-7259",
            key="preparacion_buscar_codigo",
        )

    with col_bus2:

        buscar_cliente = st.text_input(
            "Buscar por cliente",
            placeholder="Ej: AGRISUM",
            key="preparacion_buscar_cliente",
        )

    # =====================================================
    # CONSULTAR ÓRDENES
    # =====================================================

    try:

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
    # SOLO CON ARTE
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
    # DATAFRAME
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

                "Fecha": (
                    fecha
                ),

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
    # FILTROS
    # =====================================================

    if buscar_codigo:

        df = df[
            df["Código"]
            .astype(str)
            .str.contains(
                buscar_codigo,
                case=False,
                na=False,
            )
        ]

    if buscar_cliente:

        df = df[
            df["Cliente"]
            .astype(str)
            .str.contains(
                buscar_cliente,
                case=False,
                na=False,
            )
        ]

    df = df.reset_index(
        drop=True
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

    evento = st.dataframe(
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
        key="preparacion_tabla_ordenes",
    )

    # =====================================================
    # SELECCIÓN
    # =====================================================

    if evento.selection.rows:

        indice = (
            evento.selection.rows[
                0
            ]
        )

        orden_seleccionada = (
            df.iloc[
                indice
            ].to_dict()
        )

        id_nueva = str(
            orden_seleccionada.get(
                "ID"
            )
        )

        orden_anterior = (
            st.session_state.get(
                "preparacion_catalogo_orden_actual"
            )
        )

        id_anterior = (
            str(
                orden_anterior.get(
                    "ID"
                )
            )
            if orden_anterior
            else ""
        )

        if (
            id_anterior
            and id_anterior != id_nueva
        ):

            st.session_state.pop(
                "preparacion_catalogo_mockups",
                None,
            )

            st.session_state.pop(
                "preparacion_catalogo_clasificacion",
                None,
            )

            st.session_state.pop(
                "preparacion_catalogo_paquete_final",
                None,
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

        mostrar_estado_proceso(
            paso1_completo=False,
            paso2_completo=False,
            paso3_completo=False,
            paso4_completo=False,
        )

        return

    # =====================================================
    # VALIDAR FILTRO
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

        mostrar_estado_proceso(
            paso1_completo=False,
            paso2_completo=False,
            paso3_completo=False,
            paso4_completo=False,
        )

        return

    # =====================================================
    # ARTE
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
    # PASO 1
    # =====================================================

    st.success(
        "✅ PASO 1 COMPLETADO. "
        "La orden tiene un arte disponible "
        "y quedó seleccionada."
    )

    # =====================================================
    # PASO 2
    # =====================================================

    (
        paso2_completo,
        datos_mockups,
    ) = mostrar_paso_2(
        orden_actual
    )

    # =====================================================
    # PASO 3
    # =====================================================

    paso3_completo = False

    if paso2_completo:

        paso3_completo = (
            mostrar_paso_3(
                orden_actual,
                datos_mockups,
            )
        )

    # =====================================================
    # PASO 4
    # =====================================================

    paso4_completo = False

    if paso3_completo:

        paso4_completo = (
            mostrar_paso_4(
                orden_actual,
                datos_mockups,
            )
        )

    # =====================================================
    # ESTADO GENERAL
    # =====================================================

    mostrar_estado_proceso(
        paso1_completo=True,
        paso2_completo=paso2_completo,
        paso3_completo=paso3_completo,
        paso4_completo=paso4_completo,
    )