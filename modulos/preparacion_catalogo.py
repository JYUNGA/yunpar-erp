import streamlit as st
import pandas as pd
import google.generativeai as genai

import io
import json
import re
import urllib.request

from datetime import datetime
from pathlib import Path


try:
    from google import genai as genai_imagen
    from google.genai import types as genai_types
except Exception:
    genai_imagen = None
    genai_types = None

import pytz

from PIL import Image, ImageOps, ImageDraw, ImageFilter, ImageChops

from modulos import catalogo_db


# =========================================================
# MÓDULO: PREPARACIÓN DE CATÁLOGO
# =========================================================

# =========================================================
# CONFIGURACIÓN VISUAL DEL CATÁLOGO YUNPAR
# =========================================================

ANCHO_CATALOGO = 1080
ALTO_CATALOGO = 1350
CALIDAD_WEBP = 85

ASSETS_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
    / "assets"
)

FONDO_CATALOGO = (
    ASSETS_DIR
    / "fondo-yunpar.png"
)

# =========================================================
# CONFIGURACIÓN DE PRESENTACIONES / PERFILES
# =========================================================

PRESENTACIONES_MOCKUP = [
    "Solo prenda (sin persona)",
    "Niño",
    "Niña",
    "Adolescente masculino",
    "Adolescente femenina",
    "Hombre joven",
    "Mujer joven",
    "Hombre adulto",
    "Mujer adulta",
]

ICONOS_PRESENTACION = {
    "Solo prenda (sin persona)": "👕",
    "Niño": "👦",
    "Niña": "👧",
    "Adolescente masculino": "🧑",
    "Adolescente femenina": "👩",
    "Hombre joven": "👨",
    "Mujer joven": "👩",
    "Hombre adulto": "👨",
    "Mujer adulta": "👩",
}

MIGRACION_PRESENTACION_LEGACY = {
    "Hombre": "Hombre joven",
    "Mujer": "Mujer joven",
}

DESCRIPCIONES_PRESENTACION = {
    "Solo prenda (sin persona)": (
        "la prenda presentada sin persona, "
        "con volumen tridimensional realista, "
        "forma natural y apariencia de fotografía "
        "profesional de producto"
    ),
    "Niño": (
        "un modelo infantil masculino usando la prenda, "
        "con apariencia apropiada para su edad, "
        "proporciones naturales y pose neutral "
        "de catálogo de ropa"
    ),
    "Niña": (
        "una modelo infantil femenina usando la prenda, "
        "con apariencia apropiada para su edad, "
        "proporciones naturales y pose neutral "
        "de catálogo de ropa"
    ),
    "Adolescente masculino": (
        "un modelo adolescente masculino usando la prenda, "
        "con proporciones naturales, apariencia juvenil "
        "y pose neutral y profesional de catálogo"
    ),
    "Adolescente femenina": (
        "una modelo adolescente femenina usando la prenda, "
        "con proporciones naturales, apariencia juvenil "
        "y pose neutral y profesional de catálogo"
    ),
    "Hombre joven": (
        "un modelo masculino adulto joven usando la prenda, "
        "con proporciones naturales y pose profesional "
        "de catálogo"
    ),
    "Mujer joven": (
        "una modelo femenina adulta joven usando la prenda, "
        "con proporciones naturales y pose profesional "
        "de catálogo"
    ),
    "Hombre adulto": (
        "un modelo masculino adulto usando la prenda, "
        "con apariencia madura, proporciones naturales "
        "y pose profesional de catálogo"
    ),
    "Mujer adulta": (
        "una modelo femenina adulta usando la prenda, "
        "con apariencia madura, proporciones naturales "
        "y pose profesional de catálogo"
    ),
}


def normalizar_presentacion_legacy(valor):

    if not valor:
        return "Solo prenda (sin persona)"

    valor = str(valor).strip()

    return MIGRACION_PRESENTACION_LEGACY.get(
        valor,
        valor,
    )


def formato_presentacion(opcion):

    return (
        f"{ICONOS_PRESENTACION.get(opcion, '👤')} "
        f"{opcion}"
    )


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

    presentacion = normalizar_presentacion_legacy(
        presentacion
    )

    descripcion_presentacion = (
        DESCRIPCIONES_PRESENTACION
    )

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
19. Si la presentación incluye una persona, conserva el mismo perfil de edad y género visual en las cuatro vistas.
20. Cuando se utilicen modelos infantiles o adolescentes, usa únicamente poses neutrales y apropiadas para un catálogo de ropa.
21. No cambies el perfil seleccionado entre frente, espalda y laterales.

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
# PREPARACIÓN VISUAL FINAL YUNPAR
# =========================================================

def aplicar_marca_yunpar(
    imagen,
):

    if not FONDO_CATALOGO.exists():
        return imagen

    try:

        # =====================================================
        # FONDO YUNPAR DETRÁS DE LA PRENDA
        # =====================================================
        # La imagen de fondo se usa como escenario del catálogo.
        # NO se superpone sobre la camiseta ni sobre la persona.

        fondo_yunpar = Image.open(
            FONDO_CATALOGO
        ).convert(
            "RGB"
        )

        fondo_yunpar = ImageOps.fit(
            fondo_yunpar,
            (
                ANCHO_CATALOGO,
                ALTO_CATALOGO,
            ),
            method=Image.Resampling.LANCZOS,
        )

        imagen_rgb = imagen.convert(
            "RGB"
        )

        # Detectamos únicamente el fondo conectado con los bordes.
        # Así los detalles blancos internos de la camiseta se conservan.
        deteccion = imagen_rgb.copy()
        ancho, alto = deteccion.size

        color_marca = (1, 2, 3)

        puntos_borde = [
            (0, 0),
            (ancho - 1, 0),
            (0, alto - 1),
            (ancho - 1, alto - 1),
            (ancho // 2, 0),
            (ancho // 2, alto - 1),
            (0, alto // 2),
            (ancho - 1, alto // 2),
        ]

        for punto in puntos_borde:
            try:
                ImageDraw.floodfill(
                    deteccion,
                    punto,
                    color_marca,
                    thresh=42,
                )
            except Exception:
                pass

        # Construimos la máscara con operaciones internas de Pillow.
        # Esto evita recorrer 1.458.000 píxeles con Python por cada imagen
        # y mantiene el Paso 4 fluido incluso al procesar las cuatro vistas.
        imagen_marca = Image.new(
            "RGB",
            (ancho, alto),
            color_marca,
        )

        diferencia_marca = ImageChops.difference(
            deteccion,
            imagen_marca,
        ).convert(
            "L"
        )

        mascara = diferencia_marca.point(
            lambda p: 255 if p > 0 else 0
        )

        mascara = mascara.filter(
            ImageFilter.GaussianBlur(
                radius=1.2
            )
        )

        resultado = Image.composite(
            imagen_rgb,
            fondo_yunpar,
            mascara,
        )

        return resultado.convert(
            "RGB"
        )

    except Exception as e:

        raise RuntimeError(
            "No se pudo aplicar "
            f"el fondo YUNPAR: {e}"
        )


def preparar_mockup_final_yunpar(
    archivo,
    nombre_salida,
):

    if archivo is None:
        return None

    try:

        bytes_originales = archivo.getvalue()

        imagen = Image.open(
            io.BytesIO(
                bytes_originales
            )
        )

        imagen = ImageOps.exif_transpose(
            imagen
        )

        if (
            imagen.mode in (
                "RGBA",
                "LA",
            )
            or "transparency"
            in imagen.info
        ):

            imagen_rgba = imagen.convert(
                "RGBA"
            )

            fondo_blanco = Image.new(
                "RGBA",
                imagen_rgba.size,
                (
                    255,
                    255,
                    255,
                    255,
                ),
            )

            fondo_blanco.alpha_composite(
                imagen_rgba
            )

            imagen = fondo_blanco.convert(
                "RGB"
            )

        else:

            imagen = imagen.convert(
                "RGB"
            )

        escala = min(
            ANCHO_CATALOGO
            / imagen.width,
            ALTO_CATALOGO
            / imagen.height,
        )

        nuevo_ancho = max(
            1,
            int(
                imagen.width
                * escala
            ),
        )

        nuevo_alto = max(
            1,
            int(
                imagen.height
                * escala
            ),
        )

        imagen = imagen.resize(
            (
                nuevo_ancho,
                nuevo_alto,
            ),
            Image.Resampling.LANCZOS,
        )

        lienzo = Image.new(
            "RGB",
            (
                ANCHO_CATALOGO,
                ALTO_CATALOGO,
            ),
            (
                245,
                245,
                245,
            ),
        )

        posicion_x = (
            ANCHO_CATALOGO
            - nuevo_ancho
        ) // 2

        posicion_y = (
            ALTO_CATALOGO
            - nuevo_alto
        ) // 2

        lienzo.paste(
            imagen,
            (
                posicion_x,
                posicion_y,
            ),
        )

        lienzo = aplicar_marca_yunpar(
            lienzo
        )

        salida = io.BytesIO()

        lienzo.save(
            salida,
            format="WEBP",
            quality=CALIDAD_WEBP,
            method=6,
        )

        salida.seek(0)
        salida.name = nombre_salida

        return salida

    except Exception as e:

        raise RuntimeError(
            "No se pudo preparar "
            f"la imagen final YUNPAR: {e}"
        )


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

    inicio = texto.find("{")
    fin = texto.rfind("}")

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
# ANALIZAR MOCKUPS CON GEMINI
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
    tipo_producto_catalogo,
    categoria_catalogo,
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
            "PREPARACION"
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

         "categoria": (
            categoria_catalogo
        ),

        "descripcion_publica": (
            clasificacion.get(
                "descripcion",
                "",
            )
        ),

        "tipo_producto": (
            tipo_producto_catalogo
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
            "Clasificación con Gemini."
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

    


# =========================================================
# APOYO PARA GENERACIÓN AUTOMÁTICA DE MOCKUPS
# =========================================================

MODELO_IMAGEN_CATALOGO = "gemini-nano-banana-2.1"


def descargar_imagen_desde_url(url):

    if not url:

        raise RuntimeError(
            "La orden no tiene un arte disponible."
        )

    try:

        solicitud = urllib.request.Request(
            str(url),
            headers={
                "User-Agent": "Mozilla/5.0"
            },
        )

        with urllib.request.urlopen(
            solicitud,
            timeout=30,
        ) as respuesta:

            datos = respuesta.read()

        imagen = Image.open(
            io.BytesIO(
                datos
            )
        )

        return imagen.convert(
            "RGB"
        )

    except Exception as e:

        raise RuntimeError(
            f"No se pudo descargar el arte original: {e}"
        )


# =========================================================
# CORRECCIÓN IMPORTANTE:
# GOOGLE GENAI IMAGE -> PILLOW
# =========================================================

def imagen_a_archivo_virtual(
    imagen,
    nombre,
):

    if imagen is None:

        raise RuntimeError(
            "Gemini no devolvió una imagen válida."
        )

    if not isinstance(
        imagen,
        Image.Image,
    ):

        image_bytes = getattr(
            imagen,
            "image_bytes",
            None,
        )

        if image_bytes is None:

            raise RuntimeError(
                "Gemini devolvió una imagen, "
                "pero no fue posible leer sus bytes."
            )

        try:

            imagen = Image.open(
                io.BytesIO(
                    image_bytes
                )
            )

        except Exception as e:

            raise RuntimeError(
                "No se pudo convertir la imagen "
                f"generada por Gemini a Pillow: {e}"
            )

    memoria = io.BytesIO()

    imagen = ImageOps.exif_transpose(
        imagen
    ).convert(
        "RGB"
    )

    imagen.save(
        memoria,
        format="PNG",
        optimize=True,
    )

    memoria.seek(0)
    memoria.name = nombre

    return memoria


def generar_mockup_automatico(
    arte_url,
    presentacion,
    vista,
    referencia_frente=None,
):

    if (
        genai_imagen is None
        or genai_types is None
    ):

        raise RuntimeError(
            "No está disponible la librería google-genai. "
            "Ejecuta la instalación que ya utilizamos para "
            "la prueba de generación automática."
        )

    try:

        api_key = st.secrets[
            "gemini"
        ][
            "api_key"
        ]

    except Exception:

        raise RuntimeError(
            "No se encontró la API key de Gemini "
            "en secrets.toml."
        )

    arte_original = (
        descargar_imagen_desde_url(
            arte_url
        )
    )

    prompt = generar_prompt_mockup(
        presentacion,
        vista,
    )

    if (
        vista != "Frente"
        and referencia_frente is not None
    ):

        referencia = archivo_a_imagen(
            referencia_frente
        )

        prompt += """

REFERENCIA VISUAL ADICIONAL:
La segunda imagen adjunta es el mockup FRONTAL ya aprobado de esta misma prenda.
Úsala para conservar exactamente el mismo tipo de camiseta, cuello, mangas,
proporciones, volumen, iluminación, fondo y estilo fotográfico.
Cambia únicamente el ángulo para producir la vista solicitada.
No copies el frente cuando se solicita espalda o lateral.
"""

        contenidos = [
            prompt,
            arte_original,
            referencia,
        ]

    else:

        contenidos = [
            prompt,
            arte_original,
        ]

    cliente = genai_imagen.Client(
        api_key=api_key
    )

    respuesta = cliente.models.generate_content(
        model=MODELO_IMAGEN_CATALOGO,
        contents=contenidos,
        config=genai_types.GenerateContentConfig(
            response_modalities=[
                "IMAGE"
            ],
            image_config=genai_types.ImageConfig(
                aspect_ratio="4:5",
                image_size="1K",
            ),
        ),
    )

    imagen_generada = None

    for parte in (
        getattr(
            respuesta,
            "parts",
            None,
        )
        or []
    ):

        if getattr(
            parte,
            "thought",
            False,
        ):

            continue

        try:

            imagen_parte = (
                parte.as_image()
            )

        except Exception:

            imagen_parte = None

        if imagen_parte is not None:

            imagen_generada = (
                imagen_parte
            )

    if imagen_generada is None:

        raise RuntimeError(
            "Gemini respondió, pero no devolvió "
            "una imagen utilizable."
        )

    nombres = {
        "Frente": "frente_ia.png",
        "Espalda": "espalda_ia.png",
        "Lateral derecho": "derecha_ia.png",
        "Lateral izquierdo": "izquierda_ia.png",
    }

    return imagen_a_archivo_virtual(
        imagen_generada,
        nombres.get(
            vista,
            "mockup_ia.png",
        ),
    )


def limpiar_memoria_mockups_orden(
    orden_id,
):

    claves = [
        f"preparacion_ia_resultado_{orden_id}_frente",
        f"preparacion_ia_resultado_{orden_id}_espalda",
        f"preparacion_ia_resultado_{orden_id}_lateral_derecho",
        f"preparacion_ia_resultado_{orden_id}_lateral_izquierdo",
        f"preparacion_ia_aprobado_{orden_id}_frente",
        f"preparacion_ia_aprobado_{orden_id}_espalda",
        f"preparacion_ia_aprobado_{orden_id}_lateral_derecho",
        f"preparacion_ia_aprobado_{orden_id}_lateral_izquierdo",
        f"preparacion_frente_{orden_id}",
        f"preparacion_espalda_{orden_id}",
        f"preparacion_derecha_{orden_id}",
        f"preparacion_izquierda_{orden_id}",
        f"preparacion_confirmacion_{orden_id}",
        f"preparacion_clasificacion_{orden_id}",
        f"preparacion_clasificacion_confirmada_{orden_id}",
        f"preparacion_confirmar_clasificacion_{orden_id}",
        f"preparacion_titulo_publico_{orden_id}",
        f"preparacion_observacion_final_{orden_id}",
        f"preparacion_confirmacion_final_{orden_id}",
        f"preparacion_paquete_catalogo_{orden_id}",
    ]

    for clave in claves:

        st.session_state.pop(
            clave,
            None,
        )

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

    st.session_state.pop(
        "preparacion_catalogo_mockups_finales",
        None,
    )


def mostrar_generador_ia_vista(
    orden_id,
    arte_url,
    presentacion,
    vista,
    slug,
    referencia_frente=None,
    habilitado=True,
):

    clave_resultado = (
        f"preparacion_ia_resultado_"
        f"{orden_id}_{slug}"
    )

    clave_aprobado = (
        f"preparacion_ia_aprobado_"
        f"{orden_id}_{slug}"
    )

    resultado = st.session_state.get(
        clave_resultado
    )

    aprobado = bool(
        st.session_state.get(
            clave_aprobado,
            False,
        )
    )

    st.markdown(
        f"#### {vista}"
    )

    if not habilitado:

        st.info(
            "Primero aprueba la vista frontal. "
            "Después esta vista utilizará ese frente "
            "como referencia para mantener consistencia."
        )

        return None, False

    etiqueta_boton = (
        f"🔄 Regenerar {vista.lower()}"
        if resultado is not None
        else f"🤖 Generar {vista.lower()} con Gemini"
    )

    if st.button(
        etiqueta_boton,
        type="primary",
        width="stretch",
        key=(
            f"preparacion_generar_ia_"
            f"{orden_id}_{slug}"
        ),
    ):

        try:

            with st.spinner(
                f"Gemini está generando "
                f"{vista.lower()}..."
            ):

                nuevo_resultado = (
                    generar_mockup_automatico(
                        arte_url=arte_url,
                        presentacion=presentacion,
                        vista=vista,
                        referencia_frente=(
                            referencia_frente
                            if vista != "Frente"
                            else None
                        ),
                    )
                )

            st.session_state[
                clave_resultado
            ] = nuevo_resultado

            st.session_state[
                clave_aprobado
            ] = False

            st.rerun()

        except Exception as e:

            st.error(
                f"❌ No se pudo generar "
                f"{vista.lower()}: {e}"
            )

    resultado = st.session_state.get(
        clave_resultado
    )

    aprobado = bool(
        st.session_state.get(
            clave_aprobado,
            False,
        )
    )

    if resultado is None:

        st.caption(
            "Todavía no se ha generado esta vista."
        )

        return None, False

    st.image(
        resultado,
        caption=f"Resultado Gemini - {vista}",
        width=420,
    )

    if aprobado:

        st.success(
            f"✅ {vista} aprobado."
        )

    col_aprobar, col_descartar = (
        st.columns(2)
    )

    with col_aprobar:

        if st.button(
            f"✅ Aprobar {vista.lower()}",
            disabled=aprobado,
            width="stretch",
            key=(
                f"preparacion_aprobar_ia_"
                f"{orden_id}_{slug}"
            ),
        ):

            st.session_state[
                clave_aprobado
            ] = True

            st.rerun()

    with col_descartar:

        if st.button(
            f"🗑️ Descartar {vista.lower()}",
            width="stretch",
            key=(
                f"preparacion_descartar_ia_"
                f"{orden_id}_{slug}"
            ),
        ):

            st.session_state.pop(
                clave_resultado,
                None,
            )

            st.session_state[
                clave_aprobado
            ] = False

            st.rerun()

    return resultado, aprobado


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

    st.markdown(
        "### 🎨 Método de generación"
    )

    metodo = st.radio(
        "¿Cómo se generarán los mockups?",
        [
            "🤖 Gemini",
            "🎨 Canva IA / Manual",
        ],
        horizontal=True,
        key=f"preparacion_metodo_{orden_id}",
    )

    st.caption(
        "Generación: Gemini / Canva IA / Manual · "
        "Clasificación: Gemini"
    )

    clave_metodo_anterior = (
        f"preparacion_metodo_anterior_{orden_id}"
    )

    metodo_anterior = (
        st.session_state.get(
            clave_metodo_anterior
        )
    )

    if (
        metodo_anterior is not None
        and metodo_anterior != metodo
    ):

        limpiar_memoria_mockups_orden(
            orden_id
        )

        st.info(
            "🔄 Cambiaste el método de generación. "
            "Se limpiaron los resultados temporales "
            "de esta orden para evitar mezclar procesos."
        )

    st.session_state[
        clave_metodo_anterior
    ] = metodo

    if metodo == "🤖 Gemini":

        st.info(
            "🤖 Gemini generará las vistas UNA POR UNA. "
            "El operador debe revisar y aprobar cada imagen. "
            "Regenerar reemplaza la imagen anterior para "
            "no acumular archivos innecesarios en memoria."
        )

    else:

        st.info(
            "🎨 Método manual. Puedes usar Canva IA u otra "
            "herramienta externa, siguiendo el prompt oficial, "
            "y después cargar las cuatro vistas aquí."
        )

    st.markdown(
        "### 👕 Presentación del mockup"
    )

    clave_presentacion = (
        f"preparacion_presentacion_v2_{orden_id}"
    )

    valor_presentacion_actual = (
        st.session_state.get(
            clave_presentacion
        )
    )

    valor_presentacion_normalizado = (
        normalizar_presentacion_legacy(
            valor_presentacion_actual
        )
    )

    if (
        valor_presentacion_actual
        and valor_presentacion_actual
        != valor_presentacion_normalizado
    ):

        st.session_state[
            clave_presentacion
        ] = valor_presentacion_normalizado

    presentacion = st.selectbox(
        "Selecciona cómo se presentará este diseño",
        PRESENTACIONES_MOCKUP,
        format_func=formato_presentacion,
        key=clave_presentacion,
    )

    clave_presentacion_anterior = (
        f"preparacion_presentacion_anterior_{orden_id}"
    )

    presentacion_anterior = (
        st.session_state.get(
            clave_presentacion_anterior
        )
    )

    if (
        presentacion_anterior is not None
        and presentacion_anterior != presentacion
    ):

        limpiar_memoria_mockups_orden(
            orden_id
        )

        st.info(
            "🔄 Cambiaste el perfil de presentación. "
            "Se limpiaron los mockups, la clasificación "
            "y el paquete temporal de esta orden para "
            "evitar mezclar perfiles diferentes."
        )

    st.session_state[
        clave_presentacion_anterior
    ] = presentacion

    st.caption(
        "Esta opción se aplicará a las cuatro vistas "
        "para mantener consistencia. El perfil seleccionado "
        "solo cambia quién presenta la prenda; el diseño, "
        "los colores, los textos y los logotipos deben "
        "mantenerse."
    )

    st.success(
        "✅ Perfil seleccionado: "
        f"{formato_presentacion(presentacion)}"
    )

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

    st.markdown(
        "### 🧠 Prompt oficial YUNPAR"
    )

    if metodo == "🤖 Gemini":

        st.caption(
            "Gemini utiliza automáticamente "
            "este mismo estándar visual. "
            "Puedes revisarlo aquí."
        )

    else:

        st.caption(
            "Genera las imágenes UNA POR UNA. "
            "Nunca pidas las cuatro vistas "
            "en una misma generación."
        )

    vista_prompt = st.selectbox(
        "Vista que deseas revisar en el prompt",
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

    with st.expander(
        "📋 Ver prompt utilizado",
        expanded=(
            metodo == "🎨 Canva IA / Manual"
        ),
    ):

        st.code(
            prompt_actual,
            language="text",
        )

    st.info(
        "💡 Para mantener consistencia, la vista frontal "
        "aprobada se utilizará como referencia visual "
        "para espalda y laterales en el modo automático."
    )

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

    st.divider()

    frente = None
    espalda = None
    lateral_derecho = None
    lateral_izquierdo = None

    aprobados_ia = {
        "frente": False,
        "espalda": False,
        "lateral_derecho": False,
        "lateral_izquierdo": False,
    }

    if metodo == "🤖 Gemini":

        st.markdown(
            "### 🤖 Generar mockups con Gemini"
        )

        st.caption(
            "Genera, revisa y aprueba cada vista. "
            "Solo se mantiene una generación "
            "por vista en memoria."
        )

        frente, aprobados_ia["frente"] = (
            mostrar_generador_ia_vista(
                orden_id=orden_id,
                arte_url=arte_url,
                presentacion=presentacion,
                vista="Frente",
                slug="frente",
                habilitado=True,
            )
        )

        st.divider()

        espalda, aprobados_ia["espalda"] = (
            mostrar_generador_ia_vista(
                orden_id=orden_id,
                arte_url=arte_url,
                presentacion=presentacion,
                vista="Espalda",
                slug="espalda",
                referencia_frente=frente,
                habilitado=(
                    aprobados_ia[
                        "frente"
                    ]
                ),
            )
        )

        st.divider()

        lateral_derecho, aprobados_ia[
            "lateral_derecho"
        ] = (
            mostrar_generador_ia_vista(
                orden_id=orden_id,
                arte_url=arte_url,
                presentacion=presentacion,
                vista="Lateral derecho",
                slug="lateral_derecho",
                referencia_frente=frente,
                habilitado=(
                    aprobados_ia[
                        "frente"
                    ]
                ),
            )
        )

        st.divider()

        lateral_izquierdo, aprobados_ia[
            "lateral_izquierdo"
        ] = (
            mostrar_generador_ia_vista(
                orden_id=orden_id,
                arte_url=arte_url,
                presentacion=presentacion,
                vista="Lateral izquierdo",
                slug="lateral_izquierdo",
                referencia_frente=frente,
                habilitado=(
                    aprobados_ia[
                        "frente"
                    ]
                ),
            )
        )

    else:

        st.markdown(
            "### 📤 Cargar mockups generados"
        )

        st.caption(
            "Carga cada imagen en su posición correspondiente."
        )

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

    st.divider()

    st.markdown(
        "### 📊 Estado de los mockups"
    )

    mockups = [
        {
            "Vista": "Frente",
            "Archivo": frente,
            "Aprobado": (
                aprobados_ia["frente"]
                if metodo == "🤖 Gemini"
                else frente is not None
            ),
        },
        {
            "Vista": "Espalda",
            "Archivo": espalda,
            "Aprobado": (
                aprobados_ia["espalda"]
                if metodo == "🤖 Gemini"
                else espalda is not None
            ),
        },
        {
            "Vista": "Lateral derecho",
            "Archivo": lateral_derecho,
            "Aprobado": (
                aprobados_ia[
                    "lateral_derecho"
                ]
                if metodo == "🤖 Gemini"
                else lateral_derecho is not None
            ),
        },
        {
            "Vista": "Lateral izquierdo",
            "Archivo": lateral_izquierdo,
            "Aprobado": (
                aprobados_ia[
                    "lateral_izquierdo"
                ]
                if metodo == "🤖 Gemini"
                else lateral_izquierdo is not None
            ),
        },
    ]

    registros_estado = []
    cantidad_listos = 0

    for mockup in mockups:

        archivo = mockup[
            "Archivo"
        ]

        aprobado = mockup[
            "Aprobado"
        ]

        if (
            archivo is not None
            and aprobado
        ):

            cantidad_listos += 1

        if archivo is None:

            estado = "⏳ Pendiente"

        elif aprobado:

            estado = "✅ Aprobado"

        else:

            estado = "🔎 Por revisar"

        registros_estado.append(
            {
                "Vista": mockup[
                    "Vista"
                ],
                "Estado": estado,
                "Archivo": (
                    getattr(
                        archivo,
                        "name",
                        "imagen_generada.png",
                    )
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
        cantidad_listos
        / 4
    )

    st.progress(
        progreso
    )

    st.caption(
        f"{cantidad_listos} de 4 mockups listos."
    )

    todas_listas = (
        cantidad_listos == 4
    )

    confirmado = False

    if todas_listas:

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
                "✅ Mockups confirmados para este arte."
            )

        else:

            st.warning(
                "⚠️ Revisa las cuatro imágenes "
                "y confirma su relación "
                "con el arte original."
            )

    else:

        if metodo == "🤖 Gemini":

            st.info(
                "Genera y aprueba las cuatro vistas "
                "para completar el Paso 2."
            )

        else:

            st.info(
                "Carga las cuatro vistas "
                "para completar el Paso 2."
            )

    paso2_completo = (
        todas_listas
        and confirmado
    )

    datos_mockups = {
        "orden_id": orden_id,
        "codigo": codigo,
        "presentacion": presentacion,
        "metodo": metodo,
        "frente": frente,
        "espalda": espalda,
        "lateral_derecho": lateral_derecho,
        "lateral_izquierdo": lateral_izquierdo,
    }

    if paso2_completo:

        st.session_state[
            "preparacion_catalogo_mockups"
        ] = datos_mockups

        st.success(
            "✅ PASO 2 COMPLETADO. "
            "Las cuatro vistas están listas "
            "y confirmadas."
        )

        st.info(
            "ℹ️ Los archivos permanecen únicamente "
            "en esta sesión de Streamlit. "
            "Todavía no se han enviado a Supabase."
        )

    return (
        paso2_completo,
        datos_mockups,
    )


# =========================================================
# PASO 3
# CLASIFICACIÓN GEMINI
# =========================================================

def mostrar_paso_3(
    orden_actual,
    datos_mockups,
):

    st.divider()

    st.markdown(
        "## 3️⃣ Clasificación automática con Gemini"
    )

    st.caption(
        "Gemini analizará las cuatro vistas del producto "
        "y propondrá información útil para el catálogo."
    )

    st.info(
        "🤖 Gemini solamente propone la clasificación. "
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

    if st.button(
        "🤖 Analizar mockups con Gemini",
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
                f"la clasificación con Gemini: {e}"
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

    st.markdown(
        "### 🧠 Resultado propuesto por Gemini"
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

            "orden_id": orden_id,

            "codigo": codigo,

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

    if not FONDO_CATALOGO.exists():

        st.error(
            "❌ No se encontró assets/fondo-yunpar.png. "
            "No se puede preparar la versión final "
            "de las imágenes para el catálogo."
        )

        return False

    try:

        datos_mockups_finales = (
            datos_mockups.copy()
        )

        datos_mockups_finales[
            "frente"
        ] = preparar_mockup_final_yunpar(
            datos_mockups.get(
                "frente"
            ),
            "01_frente_yunpar.webp",
        )

        datos_mockups_finales[
            "espalda"
        ] = preparar_mockup_final_yunpar(
            datos_mockups.get(
                "espalda"
            ),
            "02_espalda_yunpar.webp",
        )

        datos_mockups_finales[
            "lateral_derecho"
        ] = preparar_mockup_final_yunpar(
            datos_mockups.get(
                "lateral_derecho"
            ),
            "03_derecha_yunpar.webp",
        )

        datos_mockups_finales[
            "lateral_izquierdo"
        ] = preparar_mockup_final_yunpar(
            datos_mockups.get(
                "lateral_izquierdo"
            ),
            "04_izquierda_yunpar.webp",
        )

        if not all(
            [
                datos_mockups_finales.get(
                    "frente"
                ),
                datos_mockups_finales.get(
                    "espalda"
                ),
                datos_mockups_finales.get(
                    "lateral_derecho"
                ),
                datos_mockups_finales.get(
                    "lateral_izquierdo"
                ),
            ]
        ):

            raise RuntimeError(
                "No se pudieron preparar "
                "las cuatro imágenes finales."
            )

        st.session_state[
            "preparacion_catalogo_mockups_finales"
        ] = {
            "orden_id": orden_id,
            "imagenes": datos_mockups_finales,
        }

    except Exception as e:

        st.error(
            "❌ No se pudieron preparar las imágenes "
            f"con la identidad visual YUNPAR: {e}"
        )

        return False

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

    tipo_producto_catalogo = st.selectbox(
        "Tipo de producto del catálogo",
        options=[
            "Uniforme / conjunto deportivo",
            "Camiseta",
            "Pantaloneta",
            "Gorra",
            "Bandera",
            "Polín",
            "Campaña / colección",
            "Producto promocional",
        ],
        key=f"preparacion_tipo_producto_catalogo_{orden_id}",
    )

    categoria_catalogo = st.selectbox(
    "Categoría del catálogo",
    options=[
        "Deportivo",
        "Corporativo",
        "Escolar",
        "Promocional",
        "Campaña",
        "Eventos",
        "Otro",
    ],
    key=f"preparacion_categoria_catalogo_{orden_id}",
)
    
    observacion_operador = st.text_area(
        "Observación interna del operador",
        placeholder=(
            "Opcional. Ej: Mockups revisados, "
            "clasificación corregida a Fútbol."
        ),
        key=f"preparacion_observacion_final_{orden_id}",
    )

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
            "Clasificación Gemini",
            "Confirmada",
        )

        st.caption(
            "Revisada por el operador"
        )

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

    st.markdown(
        "### 🎨 Preparación visual YUNPAR"
    )

    st.success(
        "✅ Fondo y marca YUNPAR aplicados "
        "a las cuatro imágenes."
    )

    st.caption(
        "1080 × 1350 px · WEBP · "
        "Calidad 85 · Marca YUNPAR"
    )

    st.markdown(
        "### 🖼️ Imágenes que se enviarán"
    )

    col_img1, col_img2, col_img3, col_img4 = (
        st.columns(4)
    )

    with col_img1:

        if datos_mockups_finales.get(
            "frente"
        ):

            st.image(
                datos_mockups_finales[
                    "frente"
                ],
                caption="⭐ Frente",
                width="stretch",
            )

    with col_img2:

        if datos_mockups_finales.get(
            "espalda"
        ):

            st.image(
                datos_mockups_finales[
                    "espalda"
                ],
                caption="Espalda",
                width="stretch",
            )

    with col_img3:

        if datos_mockups_finales.get(
            "lateral_derecho"
        ):

            st.image(
                datos_mockups_finales[
                    "lateral_derecho"
                ],
                caption="Lateral derecho",
                width="stretch",
            )

    with col_img4:

        if datos_mockups_finales.get(
            "lateral_izquierdo"
        ):

            st.image(
                datos_mockups_finales[
                    "lateral_izquierdo"
                ],
                caption="Lateral izquierdo",
                width="stretch",
            )

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
        "📦 Enviar al Catálogo de Diseños",
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
            datos_mockups=datos_mockups_finales,
            clasificacion=clasificacion,
            texto_semantico=texto_semantico,
            titulo_publico=titulo_publico,
            tipo_producto_catalogo=tipo_producto_catalogo,
            categoria_catalogo=categoria_catalogo,
            observacion_operador=observacion_operador,
        )

        # =====================================================
        # PREPARAR IMÁGENES PARA SUPABASE
        # =====================================================

        imagenes_db = []

        configuracion_imagenes = [
            (
                1,
                "frente",
                "Frente",
                True,
            ),
            (
                2,
                "espalda",
                "Espalda",
                False,
            ),
            (
                3,
                "lateral_derecho",
                "Lateral derecho",
                False,
            ),
            (
                4,
                "lateral_izquierdo",
                "Lateral izquierdo",
                False,
            ),
        ]

        for (
            orden_imagen,
            clave_imagen,
            nombre_imagen,
            es_portada,
        ) in configuracion_imagenes:

            archivo_imagen = (
                datos_mockups_finales.get(
                    clave_imagen
                )
            )

            if archivo_imagen is None:

                st.error(
                    f"❌ Falta la imagen: "
                    f"{nombre_imagen}"
                )

                return False

            bytes_imagen = (
                archivo_imagen.getvalue()
            )

            imagenes_db.append(
                {
                    "orden": orden_imagen,
                    "nombre": nombre_imagen,
                    "es_portada": es_portada,
                    "bytes": bytes_imagen,
                    "peso_optimizado": len(
                        bytes_imagen
                    ),
                    "ancho": ANCHO_CATALOGO,
                    "alto": ALTO_CATALOGO,
                    "formato": "WEBP",
                }
            )

        # =====================================================
        # CONSTRUIR BORRADOR REAL
        # =====================================================

        borrador_db = {

            "estado": "BORRADOR",

            "modo": "REAL",

            "orden_id": orden_id,

            "codigo_orden": paquete.get(
                "codigo_orden",
                "",
            ),

            "cliente": paquete.get(
                "cliente",
                "",
            ),

            "arte_original": orden_actual.get(
                "Arte",
                "",
            ),

            "tipo_producto": paquete.get(
                "tipo_producto",
                "",
            ),

            "categoria": paquete.get(
                "categoria",
                "",
            ),

            "titulo": paquete.get(
                "titulo_publico",
                "",
            ),

            "descripcion": paquete.get(
                "descripcion_publica",
                "",
            ),

            "colores": paquete.get(
                "colores",
                [],
            ),

            "etiquetas": paquete.get(
                "etiquetas",
                [],
            ),

            "relacion_confirmada": True,

            "cantidad_imagenes": len(
                imagenes_db
            ),

            "imagenes": imagenes_db,
        }

        # =====================================================
        # GUARDAR REALMENTE EN SUPABASE
        # =====================================================

        try:

            catalogo_db.validar_borrador(
                borrador_db
            )

            resultado_guardado = (
                catalogo_db
                .guardar_borrador_real(
                    borrador_db
                )
            )

        except Exception as e:

            st.error(
                "❌ No se pudo guardar "
                f"el diseño en Supabase: {e}"
            )

            return False

        # =====================================================
        # GUARDAR RESULTADO EN LA SESIÓN
        # =====================================================

        st.session_state[
            clave_paquete
        ] = paquete

        st.session_state[
            "preparacion_catalogo_paquete_final"
        ] = paquete

        st.session_state[
            f"preparacion_borrador_db_{orden_id}"
        ] = borrador_db

        st.session_state[
            f"preparacion_resultado_db_{orden_id}"
        ] = resultado_guardado

        st.success(
            "✅ Diseño guardado correctamente "
            "en Supabase."
        )

        st.rerun()

    paquete = (
        st.session_state.get(
            clave_paquete
        )
    )

    if not paquete:

        return False

    st.success(
        "✅ PASO 4 COMPLETADO. "
        "El diseño fue enviado al "
        "Catálogo de Diseños."
    )

    

    with st.expander(
        "📋 Ver paquete preparado",
        expanded=False,
    ):

        st.json(
            paquete
        )

    paquete_json = json.dumps(
        paquete,
        ensure_ascii=False,
        indent=4,
    )

    st.download_button(
        label="⬇️ Descargar paquete preparado (.json)",
        data=paquete_json,
        file_name=(
            f"{codigo}_catalogo_preparado.json"
        ),
        mime="application/json",
        width="stretch",
        key=f"preparacion_descargar_paquete_{orden_id}",
    )

    st.caption(
        "Este archivo JSON sirve como evidencia y respaldo "
        "de la información enviada al catálogo."
    )

    return True


# =========================================================
# FUNCIÓN PRINCIPAL
# =========================================================

def render(
    supabase,
):

    st.header(
        "🤖 Preparación de Catálogo",
        divider="blue",
    )

    st.caption(
        "Prepara los artes disponibles de las órdenes "
        "antes de enviarlos al catálogo digital de YUNPAR."
    )

    

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
            "Clasificación Gemini",
        )

    with col4:

        st.metric(
            "Paso 4",
            "Enviar al catálogo",
        )

    st.divider()

    st.markdown(
        "## 1️⃣ Órdenes con arte disponible"
    )

    st.caption(
        "Aquí aparecen únicamente las órdenes "
        "que tienen un arte cargado en el sistema."
    )

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

            limpiar_memoria_mockups_orden(
                id_anterior
            )

        st.session_state[
            "preparacion_catalogo_orden_actual"
        ] = orden_seleccionada

    orden_actual = (
        st.session_state.get(
            "preparacion_catalogo_orden_actual"
        )
    )

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

    st.success(
        "✅ PASO 1 COMPLETADO. "
        "La orden tiene un arte disponible "
        "y quedó seleccionada."
    )

    (
        paso2_completo,
        datos_mockups,
    ) = mostrar_paso_2(
        orden_actual
    )

    paso3_completo = False

    if paso2_completo:

        paso3_completo = (
            mostrar_paso_3(
                orden_actual,
                datos_mockups,
            )
        )

    paso4_completo = False

    if paso3_completo:

        paso4_completo = (
            mostrar_paso_4(
                orden_actual,
                datos_mockups,
            )
        )

    mostrar_estado_proceso(
        paso1_completo=True,
        paso2_completo=paso2_completo,
        paso3_completo=paso3_completo,
        paso4_completo=paso4_completo,
    )
