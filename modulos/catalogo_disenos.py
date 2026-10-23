import io
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image, ImageOps

from modulos import catalogo_db
from modulos import catalogo_storage


# =========================================================
# CONFIGURACIÓN GENERAL DEL CATÁLOGO
# =========================================================

ANCHO_CATALOGO = 1080
ALTO_CATALOGO = 1350
CALIDAD_WEBP = 85

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
FONDO_CATALOGO = ASSETS_DIR / "fondo-yunpar.png"


# =========================================================
# TIPOS DE PRODUCTO INICIALES
# =========================================================

TIPOS_PRODUCTO_INICIALES = [
    "Uniforme / conjunto deportivo",
    "Camiseta",
    "Pantaloneta",
    "Gorra",
    "Bandera",
    "Polín",
    "Campaña / colección",
    "Producto promocional",
]


# =========================================================
# CATEGORÍAS
# =========================================================

CATEGORIAS = [
    "Deportivo",
    "Corporativo",
    "Escolar",
    "Promocional",
    "Campaña",
    "Eventos",
    "Otro",
]


# =========================================================
# TIPOS DE IMAGEN
# =========================================================

TIPOS_IMAGEN = [
    "Principal",
    "Frente",
    "Espalda",
    "Lateral derecho",
    "Lateral izquierdo",
    "Detalle",
    "Producto completo",
    "Aplicación",
    "Ambiente",
    "Campaña",
    "Otro",
]


# =========================================================
# TIPOS DE PRODUCTO DINÁMICOS
# =========================================================

def inicializar_tipos_producto():
    """
    Inicializa los tipos de producto.

    Por ahora se guardan únicamente
    durante la sesión de Streamlit.
    """

    if "catalogo_tipos_producto" not in st.session_state:
        st.session_state["catalogo_tipos_producto"] = (
            TIPOS_PRODUCTO_INICIALES.copy()
        )

    return st.session_state["catalogo_tipos_producto"]


# =========================================================
# UTILIDADES
# =========================================================

def formatear_peso(cantidad_bytes):
    if cantidad_bytes is None:
        return "0 B"

    if cantidad_bytes < 1024:
        return f"{cantidad_bytes} B"

    if cantidad_bytes < 1024 * 1024:
        return f"{cantidad_bytes / 1024:.1f} KB"

    return f"{cantidad_bytes / (1024 * 1024):.2f} MB"


def convertir_lista_texto(texto):
    """
    Convierte:
    'Rojo, blanco, negro'

    en:
    ['Rojo', 'blanco', 'negro']
    """

    if not texto:
        return []

    return [
        elemento.strip()
        for elemento in texto.split(",")
        if elemento.strip()
    ]


# =========================================================
# MARCA YUNPAR
# =========================================================

def aplicar_marca_yunpar(imagen):
    """
    Aplica el patrón YUNPAR sobre la imagen.
    """

    if not FONDO_CATALOGO.exists():
        return imagen

    try:
        marca = Image.open(
            FONDO_CATALOGO
        ).convert("RGBA")

        marca = ImageOps.fit(
            marca,
            (
                ANCHO_CATALOGO,
                ALTO_CATALOGO,
            ),
            method=Image.Resampling.LANCZOS,
        )

        gris = marca.convert("L")

        mascara = ImageOps.invert(
            gris
        )

        mascara = mascara.point(
            lambda p: min(
                75,
                int(p * 2.2),
            )
        )

        marca.putalpha(
            mascara
        )

        resultado = imagen.convert(
            "RGBA"
        )

        resultado.alpha_composite(
            marca
        )

        return resultado.convert(
            "RGB"
        )

    except Exception as e:
        st.warning(
            f"⚠️ No se pudo aplicar la marca YUNPAR: {e}"
        )

        return imagen


# =========================================================
# OPTIMIZACIÓN DE IMÁGENES
# =========================================================

def optimizar_imagen(archivo):
    """
    Convierte una imagen para el catálogo:

    - Corrige orientación.
    - Mantiene proporción.
    - Formato 4:5.
    - 1080 x 1350.
    - Marca YUNPAR.
    - WEBP.
    - Calidad 85.
    """

    if archivo is None:
        return None

    try:
        bytes_originales = archivo.getvalue()

        peso_original = len(
            bytes_originales
        )

        imagen = Image.open(
            io.BytesIO(
                bytes_originales
            )
        )

        imagen = ImageOps.exif_transpose(
            imagen
        )

        ancho_original, alto_original = (
            imagen.size
        )

        # =================================================
        # TRANSPARENCIA
        # =================================================

        if (
            imagen.mode in ("RGBA", "LA")
            or "transparency" in imagen.info
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

        # =================================================
        # ESCALAR SIN DEFORMAR
        # =================================================

        escala = min(
            ANCHO_CATALOGO / imagen.width,
            ALTO_CATALOGO / imagen.height,
        )

        nuevo_ancho = max(
            1,
            int(
                imagen.width * escala
            ),
        )

        nuevo_alto = max(
            1,
            int(
                imagen.height * escala
            ),
        )

        imagen = imagen.resize(
            (
                nuevo_ancho,
                nuevo_alto,
            ),
            Image.Resampling.LANCZOS,
        )

        # =================================================
        # LIENZO 4:5
        # =================================================

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

        # =================================================
        # MARCA YUNPAR
        # =================================================

        lienzo = aplicar_marca_yunpar(
            lienzo
        )

        # =================================================
        # WEBP
        # =================================================

        salida = io.BytesIO()

        lienzo.save(
            salida,
            format="WEBP",
            quality=CALIDAD_WEBP,
            method=6,
        )

        bytes_optimizados = salida.getvalue()

        peso_optimizado = len(
            bytes_optimizados
        )

        if peso_original > 0:
            ahorro = (
                1
                - (
                    peso_optimizado
                    / peso_original
                )
            ) * 100

        else:
            ahorro = 0

        return {
            "bytes": bytes_optimizados,
            "peso_original": peso_original,
            "peso_optimizado": peso_optimizado,
            "ahorro": ahorro,
            "ancho_original": ancho_original,
            "alto_original": alto_original,
            "ancho_final": ANCHO_CATALOGO,
            "alto_final": ALTO_CATALOGO,
            "formato": "WEBP",
        }

    except Exception as e:
        st.error(
            f"❌ No se pudo procesar la imagen: {e}"
        )

        return None


# =========================================================
# GALERÍA DINÁMICA
# =========================================================

def inicializar_galeria(orden_id):
    slots_key = (
        f"catalogo_slots_{orden_id}"
    )

    contador_key = (
        f"catalogo_contador_{orden_id}"
    )

    if slots_key not in st.session_state:
        st.session_state[
            slots_key
        ] = [0]

    if contador_key not in st.session_state:
        st.session_state[
            contador_key
        ] = 1

    return (
        slots_key,
        contador_key,
    )


def agregar_imagen_galeria(
    orden_id,
):
    slots_key, contador_key = (
        inicializar_galeria(
            orden_id
        )
    )

    nuevo_id = st.session_state[
        contador_key
    ]

    st.session_state[
        slots_key
    ].append(
        nuevo_id
    )

    st.session_state[
        contador_key
    ] += 1


def eliminar_imagen_galeria(
    orden_id,
    uid,
):
    slots_key, _ = (
        inicializar_galeria(
            orden_id
        )
    )

    slots = st.session_state[
        slots_key
    ]

    if (
        uid in slots
        and len(slots) > 1
    ):
        slots.remove(
            uid
        )

    claves = [
        f"galeria_archivo_{orden_id}_{uid}",
        f"galeria_tipo_{orden_id}_{uid}",
        f"galeria_nombre_{orden_id}_{uid}",
    ]

    for clave in claves:
        if clave in st.session_state:
            del st.session_state[
                clave
            ]


def mover_imagen_galeria(
    orden_id,
    uid,
    direccion,
):
    slots_key, _ = (
        inicializar_galeria(
            orden_id
        )
    )

    slots = st.session_state[
        slots_key
    ]

    if uid not in slots:
        return

    posicion = slots.index(
        uid
    )

    nueva_posicion = (
        posicion
        + direccion
    )

    if (
        nueva_posicion < 0
        or nueva_posicion >= len(
            slots
        )
    ):
        return

    (
        slots[posicion],
        slots[nueva_posicion],
    ) = (
        slots[nueva_posicion],
        slots[posicion],
    )


# =========================================================
# MOSTRAR IMAGEN PROCESADA
# =========================================================

def mostrar_imagen_procesada(
    archivo,
    clave_descarga,
):
    if archivo is None:
        return None

    resultado = optimizar_imagen(
        archivo
    )

    if resultado is None:
        return None

    st.image(
        resultado["bytes"],
        use_container_width=True,
    )

    col1, col2, col3 = (
        st.columns(3)
    )

    col1.metric(
        "Original",
        formatear_peso(
            resultado[
                "peso_original"
            ]
        ),
    )

    col2.metric(
        "Optimizada",
        formatear_peso(
            resultado[
                "peso_optimizado"
            ]
        ),
    )

    col3.metric(
        "Ahorro",
        f"{resultado['ahorro']:.1f}%",
    )

    st.caption(
        f"✅ {ANCHO_CATALOGO} × "
        f"{ALTO_CATALOGO} px · "
        f"WEBP · "
        f"Calidad {CALIDAD_WEBP}% · "
        f"Marca YUNPAR"
    )

    st.download_button(
        "⬇️ Descargar optimizada",
        data=resultado["bytes"],
        file_name="imagen_catalogo.webp",
        mime="image/webp",
        use_container_width=True,
        key=clave_descarga,
    )

    return resultado


# =========================================================
# PREPARAR STORAGE SIMULADO
# =========================================================

def preparar_storage_simulado(
    borrador,
):
    """
    Prepara las rutas futuras de Supabase Storage.

    NO sube archivos.
    NO modifica Supabase.
    """

    estado_storage = (
        catalogo_storage
        .obtener_estado_storage()
    )

    estado_db = (
        catalogo_db
        .obtener_estado_db()
    )

    codigo_orden = (
        borrador.get(
            "codigo_orden"
        )
        or borrador.get(
            "orden_id"
        )
        or "sin-orden"
    )

    registros = []

    for imagen in borrador.get(
        "imagenes",
        [],
    ):
        registro = (
            catalogo_storage
            .construir_registro_prueba(
                diseno_id=codigo_orden,
                nombre_visible=(
                    imagen.get(
                        "nombre",
                        "Imagen",
                    )
                ),
                posicion=(
                    imagen.get(
                        "orden",
                        1,
                    )
                ),
                imagen_bytes=(
                    imagen.get(
                        "bytes"
                    )
                ),
                ancho=(
                    imagen.get(
                        "ancho",
                        ANCHO_CATALOGO,
                    )
                ),
                alto=(
                    imagen.get(
                        "alto",
                        ALTO_CATALOGO,
                    )
                ),
            )
        )

        registros.append(
            registro
        )

    return {
        "estado_storage": estado_storage,
        "imagenes": registros,
    }


# =========================================================
# GUARDAR BORRADOR TEMPORAL
# =========================================================

def guardar_borrador_temporal(
    orden_actual,
    tipo_producto,
    categoria,
    titulo,
    descripcion,
    colores,
    etiquetas,
    confirmado,
    resultados_galeria,
):
    """
    Guarda un borrador solamente en memoria.

    NO escribe en Supabase.
    NO sube imágenes.
    """

    imagenes = []

    for item in resultados_galeria:
        resultado = item[
            "resultado"
        ]

        imagenes.append(
            {
                "uid": item["uid"],
                "orden": item["orden"],
                "nombre": item["nombre"],
                "es_portada": (
                    item["orden"] == 1
                ),
                "bytes": (
                    resultado[
                        "bytes"
                    ]
                ),
                "peso_original": (
                    resultado[
                        "peso_original"
                    ]
                ),
                "peso_optimizado": (
                    resultado[
                        "peso_optimizado"
                    ]
                ),
                "ahorro": (
                    resultado[
                        "ahorro"
                    ]
                ),
                "ancho": (
                    resultado[
                        "ancho_final"
                    ]
                ),
                "alto": (
                    resultado[
                        "alto_final"
                    ]
                ),
                "formato": (
                    resultado[
                        "formato"
                    ]
                ),
            }
        )

    borrador = {
        "estado": "BORRADOR",
        "modo": "PRUEBA",
        "orden_id": (
            orden_actual.get(
                "ID"
            )
        ),
        "codigo_orden": (
            orden_actual.get(
                "Código"
            )
        ),
        "cliente": (
            orden_actual.get(
                "Cliente"
            )
        ),
        "arte_original": (
            orden_actual.get(
                "Arte"
            )
        ),
        "tipo_producto": (
            tipo_producto
        ),
        "categoria": (
            categoria
        ),
        "titulo": (
            titulo.strip()
        ),
        "descripcion": (
            descripcion.strip()
        ),
        "colores": (
            convertir_lista_texto(
                colores
            )
        ),
        "etiquetas": (
            convertir_lista_texto(
                etiquetas
            )
        ),
        "relacion_confirmada": (
            confirmado
        ),
        "cantidad_imagenes": (
            len(
                imagenes
            )
        ),
        "imagenes": (
            imagenes
        ),
        "guardado_en": (
            datetime.now().strftime(
                "%d/%m/%Y %H:%M:%S"
            )
        ),
    }

    # =====================================================
    # PREPARACIÓN SIMULADA PARA STORAGE
    # =====================================================

    borrador[
        "preparacion_storage"
    ] = preparar_storage_simulado(
        borrador
    )

    # =====================================================
    # PREPARACIÓN SIMULADA PARA BASE DE DATOS
    # =====================================================

    borrador[
        "preparacion_db"
    ] = catalogo_db.preparar_guardado_simulado(
        borrador
    )

    clave = (
        f"catalogo_borrador_"
        f"{orden_actual.get('ID')}"
    )

    st.session_state[
        clave
    ] = borrador

    st.session_state[
        "catalogo_ultimo_borrador"
    ] = borrador

    return borrador


# =========================================================
# MOSTRAR PREPARACIÓN PARA SUPABASE
# =========================================================

def mostrar_preparacion_storage(
    borrador,
):
    preparacion = borrador.get(
        "preparacion_storage"
    )

    if not preparacion:
        return

    estado = preparacion.get(
        "estado_storage",
        {},
    )

    imagenes = preparacion.get(
        "imagenes",
        [],
    )

    st.divider()

    st.markdown(
        "## 📦 Preparación para Supabase"
    )

    st.caption(
        "Vista previa de cómo se prepararían "
        "los archivos antes de subirlos."
    )

    col1, col2, col3 = (
        st.columns(3)
    )

    col1.metric(
        "Storage",
        estado.get(
            "estado",
            "PRUEBA",
        ),
    )

    col2.metric(
        "Bucket",
        estado.get(
            "bucket",
            "catalogo-disenos",
        ),
    )

    puede_escribir = estado.get(
        "puede_escribir",
        False,
    )

    col3.metric(
        "Escritura real",
        (
            "ACTIVADA"
            if puede_escribir
            else "DESACTIVADA"
        ),
    )

    if not puede_escribir:
        st.info(
            "🔒 Escritura real desactivada. "
            "Estas rutas son únicamente una simulación."
        )
    else:
        st.warning(
            "⚠️ Escritura real habilitada."
        )

    if not imagenes:
        st.warning(
            "No existen imágenes preparadas."
        )
        return

    registros = []

    for imagen in imagenes:
        registros.append(
            {
                "Orden": (
                    imagen.get(
                        "orden"
                    )
                ),
                "Nombre": (
                    imagen.get(
                        "nombre"
                    )
                ),
                "Portada": (
                    "Sí"
                    if imagen.get(
                        "es_portada"
                    )
                    else "No"
                ),
                "Ruta futura": (
                    imagen.get(
                        "storage_path"
                    )
                ),
                "Peso": (
                    formatear_peso(
                        imagen.get(
                            "peso_bytes",
                            0,
                        )
                    )
                ),
                "Resolución": (
                    f"{imagen.get('ancho', '')} "
                    f"× "
                    f"{imagen.get('alto', '')}"
                ),
                "Formato": (
                    imagen.get(
                        "formato",
                        "WEBP",
                    )
                ),
                "Estado": (
                    "LISTA PARA SUBIR"
                ),
            }
        )

    st.dataframe(
        pd.DataFrame(
            registros
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.success(
        "✅ La estructura de archivos está preparada."
    )

    st.warning(
        "⚠️ Todavía NO se ha creado ningún archivo "
        "en Supabase Storage."
    )


# =========================================================
# MOSTRAR PREPARACIÓN DE BASE DE DATOS
# =========================================================

def mostrar_preparacion_db(
    borrador,
):
    preparacion = borrador.get(
        "preparacion_db"
    )

    if not preparacion:
        return

    estado_db = catalogo_db.obtener_estado_db()

    st.divider()

    st.markdown(
        "## 🗃️ Preparación de base de datos"
    )

    st.caption(
        "Vista previa de los registros que se guardarían "
        "en las tablas del catálogo."
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Base de datos",
        estado_db.get(
            "estado",
            "PRUEBA",
        ),
    )

    col2.metric(
        "Storage real",
        (
            "ACTIVADO"
            if estado_db.get(
                "storage_real",
                False,
            )
            else "DESACTIVADO"
        ),
    )

    puede_escribir = estado_db.get(
        "puede_escribir",
        False,
    )

    col3.metric(
        "Escritura BD",
        (
            "ACTIVADA"
            if puede_escribir
            else "BLOQUEADA"
        ),
    )

    if not puede_escribir:
        st.info(
            "🔒 La escritura real de la base de datos está bloqueada. "
            "Lo que ves aquí es únicamente una simulación."
        )
    else:
        st.warning(
            "⚠️ La escritura real de la base de datos está habilitada."
        )

    diseno = preparacion.get(
        "diseno",
        {},
    )

    st.markdown(
        "### 📝 Registro preparado para `catalogo_disenos`"
    )

    resumen_diseno = pd.DataFrame(
        [
            {
                "Orden origen": diseno.get(
                    "codigo_orden_origen",
                    "",
                ),
                "Cliente": diseno.get(
                    "cliente_origen",
                    "",
                ),
                "Tipo": diseno.get(
                    "tipo_producto",
                    "",
                ),
                "Categoría": diseno.get(
                    "categoria",
                    "",
                ),
                "Título": diseno.get(
                    "titulo",
                    "",
                ),
                "Estado": diseno.get(
                    "estado",
                    "BORRADOR",
                ),
            }
        ]
    )

    st.dataframe(
        resumen_diseno,
        use_container_width=True,
        hide_index=True,
    )

    imagenes = preparacion.get(
        "imagenes",
        [],
    )

    st.markdown(
        "### 🖼️ Registros preparados para `catalogo_imagenes`"
    )

    if imagenes:
        resumen_imagenes = []

        for imagen in imagenes:
            resumen_imagenes.append(
                {
                    "Orden": imagen.get(
                        "orden"
                    ),
                    "Nombre": imagen.get(
                        "nombre"
                    ),
                    "Portada": (
                        "Sí"
                        if imagen.get(
                            "es_portada"
                        )
                        else "No"
                    ),
                    "Ruta": imagen.get(
                        "storage_path"
                    ),
                    "Peso": formatear_peso(
                        imagen.get(
                            "peso_bytes",
                            0,
                        )
                    ),
                    "Resolución": (
                        f"{imagen.get('ancho', '')} "
                        f"× "
                        f"{imagen.get('alto', '')}"
                    ),
                    "Formato": imagen.get(
                        "formato",
                        "WEBP",
                    ),
                }
            )

        st.dataframe(
            pd.DataFrame(
                resumen_imagenes
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.warning(
            "No existen registros de imágenes preparados."
        )

    st.success(
        "✅ La estructura de base de datos está preparada."
    )

    st.warning(
        "⚠️ Todavía NO se ha insertado ningún registro "
        "en las tablas reales del catálogo."
    )


# =========================================================
# MOSTRAR BORRADOR TEMPORAL
# =========================================================

def mostrar_borrador_temporal(
    borrador,
):
    if not borrador:
        return

    st.divider()

    st.markdown(
        "## 🧪 Borrador temporal guardado"
    )

    st.success(
        "✅ El borrador está guardado solamente "
        "en esta sesión de Streamlit. "
        "No se envió a Supabase."
    )

    col1, col2, col3 = (
        st.columns(3)
    )

    col1.metric(
        "Estado",
        borrador.get(
            "estado",
            "BORRADOR",
        ),
    )

    col2.metric(
        "Imágenes",
        borrador.get(
            "cantidad_imagenes",
            0,
        ),
    )

    col3.metric(
        "Modo",
        borrador.get(
            "modo",
            "PRUEBA",
        ),
    )

    st.caption(
        f"🕒 Guardado: "
        f"{borrador.get('guardado_en', '')}"
    )

    with st.expander(
        "👀 Ver resumen del borrador",
        expanded=False,
    ):
        st.write(
            f"**Orden:** "
            f"{borrador.get('codigo_orden', '')}"
        )

        st.write(
            f"**Cliente:** "
            f"{borrador.get('cliente', '')}"
        )

        st.write(
            f"**Tipo de producto:** "
            f"{borrador.get('tipo_producto', '')}"
        )

        st.write(
            f"**Categoría:** "
            f"{borrador.get('categoria', '')}"
        )

        st.write(
            f"**Título:** "
            f"{borrador.get('titulo', '')}"
        )

        st.write(
            f"**Descripción:** "
            f"{borrador.get('descripcion', '')}"
        )

        colores = borrador.get(
            "colores",
            [],
        )

        etiquetas = borrador.get(
            "etiquetas",
            [],
        )

        st.write(
            "**Colores:** "
            + (
                ", ".join(
                    colores
                )
                if colores
                else "Sin definir"
            )
        )

        st.write(
            "**Etiquetas:** "
            + (
                ", ".join(
                    etiquetas
                )
                if etiquetas
                else "Sin definir"
            )
        )

        if borrador.get(
            "imagenes"
        ):
            st.markdown(
                "### 📸 Imágenes guardadas"
            )

            resumen_imagenes = []

            for imagen in borrador[
                "imagenes"
            ]:
                resumen_imagenes.append(
                    {
                        "Orden": (
                            imagen[
                                "orden"
                            ]
                        ),
                        "Nombre": (
                            imagen[
                                "nombre"
                            ]
                        ),
                        "Portada": (
                            "Sí"
                            if imagen[
                                "es_portada"
                            ]
                            else "No"
                        ),
                        "Peso": (
                            formatear_peso(
                                imagen[
                                    "peso_optimizado"
                                ]
                            )
                        ),
                        "Resolución": (
                            f"{imagen['ancho']} "
                            f"× "
                            f"{imagen['alto']}"
                        ),
                        "Formato": (
                            imagen[
                                "formato"
                            ]
                        ),
                    }
                )

            st.dataframe(
                pd.DataFrame(
                    resumen_imagenes
                ),
                use_container_width=True,
                hide_index=True,
            )

    # =====================================================
    # PREPARACIÓN PARA SUPABASE
    # =====================================================

    mostrar_preparacion_storage(
        borrador
    )

    # =====================================================
    # PREPARACIÓN DE BASE DE DATOS
    # =====================================================

    mostrar_preparacion_db(
        borrador
    )


# =========================================================
# FUNCIÓN PRINCIPAL
# =========================================================

def render(supabase):

    # =====================================================
    # CABECERA
    # =====================================================

    st.header(
        "🖼️ Catálogo de Diseños",
        divider="blue",
    )

    st.caption(
        "Convierte artes finales de YUNPAR "
        "en publicaciones listas para "
        "el catálogo digital."
    )

    estado_storage = (
        catalogo_storage
        .obtener_estado_storage()
    )

    estado_db = (
        catalogo_db
        .obtener_estado_db()
    )

    st.info(
        "🔒 Modo de prueba: "
        "los borradores se guardan únicamente "
        "durante la sesión actual. "
        "Todavía no se escribe ni se publica "
        "información en Supabase."
    )

    if not estado_storage.get(
        "puede_escribir",
        False,
    ):
        st.caption(
            "🔐 Supabase Storage: "
            "escritura real DESACTIVADA."
        )

    if not estado_db.get(
        "puede_escribir",
        False,
    ):
        st.caption(
            "🔐 Base de datos del catálogo: "
            "escritura real BLOQUEADA."
        )

    if FONDO_CATALOGO.exists():
        st.success(
            "✅ Marca YUNPAR disponible."
        )
    else:
        st.warning(
            "⚠️ No se encontró "
            "assets/fondo-yunpar.png."
        )

    # =====================================================
    # 1. SELECCIONAR ARTE FINAL
    # =====================================================

    st.markdown(
        "## 1️⃣ Seleccionar arte final"
    )

    st.caption(
        "Elige el trabajo de YUNPAR "
        "que deseas preparar para el catálogo."
    )

    col_bus1, col_bus2 = (
        st.columns(2)
    )

    buscar_codigo = (
        col_bus1.text_input(
            "Buscar por código",
            placeholder=(
                "Ej: ORD-7274"
            ),
        )
    )

    buscar_cliente = (
        col_bus2.text_input(
            "Buscar por cliente",
            placeholder=(
                "Ej: Esmeralda"
            ),
        )
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
            f"❌ Error consultando órdenes: {e}"
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
                "arte_catalogo"
            ] = arte

            ordenes_con_arte.append(
                orden
            )

    if not ordenes_con_arte:
        st.warning(
            "No existen órdenes "
            "con arte final."
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
            clientes = (
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
                clientes.data
                or []
            ):
                mapa_clientes[
                    cliente["id"]
                ] = (
                    cliente.get(
                        "nombre_completo"
                    )
                    or "Sin nombre"
                )

        except Exception:
            pass

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
                    orden["id"]
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
                        "arte_catalogo"
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

    st.caption(
        f"{len(df)} arte(s) disponibles."
    )

    if df.empty:
        st.warning(
            "No se encontraron resultados."
        )

        return

    # =====================================================
    # TABLA
    # =====================================================

    evento = st.dataframe(
        df[
            [
                "Código",
                "Cliente",
                "Estado",
                "Fecha",
            ]
        ],
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
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

        st.session_state[
            "catalogo_orden_actual"
        ] = (
            df.iloc[
                indice
            ].to_dict()
        )

    orden_actual = (
        st.session_state.get(
            "catalogo_orden_actual"
        )
    )

    if not orden_actual:
        st.info(
            "👆 Selecciona un arte "
            "para comenzar."
        )

        return

    orden_id = str(
        orden_actual["ID"]
    )

    # =====================================================
    # ARTE SELECCIONADO
    # =====================================================

    st.divider()

    st.markdown(
        "## ✅ Arte seleccionado"
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

        if arte_url:
            try:
                st.image(
                    arte_url,
                    use_container_width=True,
                )

            except Exception:
                st.warning(
                    "No se pudo mostrar "
                    "el arte seleccionado."
                )

    with col_info:
        st.markdown(
            f"""
### {orden_actual["Código"]}

**Cliente**

{orden_actual["Cliente"]}

**Estado**

{orden_actual["Estado"]}

**Fecha**

{orden_actual["Fecha"]}
"""
        )

        observaciones = (
            orden_actual.get(
                "Observaciones"
            )
        )

        if observaciones:
            st.info(
                observaciones
            )

    # =====================================================
    # 2. PRODUCTO
    # =====================================================

    st.divider()

    st.markdown(
        "## 2️⃣ ¿Qué vamos a publicar?"
    )

    st.caption(
        "Selecciona el tipo de producto "
        "al que pertenece este diseño."
    )

    tipos_producto = (
        inicializar_tipos_producto()
    )

    col_tipo1, col_tipo2 = (
        st.columns(2)
    )

    with col_tipo1:
        tipo_producto = st.selectbox(
            "Tipo de producto",
            tipos_producto,
            key=(
                f"tipo_producto_"
                f"{orden_id}"
            ),
        )

    with col_tipo2:
        categoria = st.selectbox(
            "Categoría",
            CATEGORIAS,
            key=(
                f"categoria_"
                f"{orden_id}"
            ),
        )

    # =====================================================
    # NUEVO TIPO DE PRODUCTO
    # =====================================================

    with st.expander(
        "➕ Agregar nuevo tipo de producto",
        expanded=False,
    ):
        st.caption(
            "Si YUNPAR comienza a trabajar "
            "con un producto nuevo, "
            "puedes agregarlo aquí."
        )

        nuevo_tipo = st.text_input(
            "Nombre del nuevo producto",
            placeholder=(
                "Escribe el nombre "
                "del producto"
            ),
            key=(
                f"nuevo_tipo_producto_"
                f"{orden_id}"
            ),
        )

        if st.button(
            "💾 Agregar producto",
            key=(
                f"guardar_tipo_producto_"
                f"{orden_id}"
            ),
            use_container_width=True,
        ):
            nuevo_tipo_limpio = (
                nuevo_tipo.strip()
            )

            if not nuevo_tipo_limpio:
                st.warning(
                    "⚠️ Escribe el nombre "
                    "del producto."
                )

            else:
                ya_existe = any(
                    producto.lower()
                    == nuevo_tipo_limpio.lower()
                    for producto
                    in st.session_state[
                        "catalogo_tipos_producto"
                    ]
                )

                if ya_existe:
                    st.warning(
                        "⚠️ Ese tipo de producto "
                        "ya existe."
                    )

                else:
                    st.session_state[
                        "catalogo_tipos_producto"
                    ].append(
                        nuevo_tipo_limpio
                    )

                    st.success(
                        f"✅ Producto "
                        f"'{nuevo_tipo_limpio}' "
                        f"agregado correctamente."
                    )

                    st.rerun()

    # =====================================================
    # 3. GALERÍA
    # =====================================================

    st.divider()

    st.markdown(
        "## 3️⃣ Imágenes para el catálogo"
    )

    st.caption(
        "Agrega las imágenes que realmente "
        "necesites para mostrar este producto. "
        "La primera imagen será la portada."
    )

    slots_key, _ = (
        inicializar_galeria(
            orden_id
        )
    )

    slots = st.session_state[
        slots_key
    ]

    resultados_galeria = []

    for posicion, uid in enumerate(
        slots
    ):
        with st.container(
            border=True
        ):
            cab1, cab2 = (
                st.columns(
                    [
                        4,
                        2,
                    ]
                )
            )

            if posicion == 0:
                cab1.markdown(
                    "### ⭐ Portada del carrusel"
                )
            else:
                cab1.markdown(
                    f"### Imagen en posición "
                    f"{posicion + 1}"
                )

            with cab2:
                b1, b2, b3 = (
                    st.columns(3)
                )

                if b1.button(
                    "⬆️",
                    key=(
                        f"subir_"
                        f"{orden_id}_"
                        f"{uid}"
                    ),
                    disabled=(
                        posicion == 0
                    ),
                ):
                    mover_imagen_galeria(
                        orden_id,
                        uid,
                        -1,
                    )

                    st.rerun()

                if b2.button(
                    "⬇️",
                    key=(
                        f"bajar_"
                        f"{orden_id}_"
                        f"{uid}"
                    ),
                    disabled=(
                        posicion
                        == len(slots) - 1
                    ),
                ):
                    mover_imagen_galeria(
                        orden_id,
                        uid,
                        1,
                    )

                    st.rerun()

                if b3.button(
                    "🗑️",
                    key=(
                        f"eliminar_"
                        f"{orden_id}_"
                        f"{uid}"
                    ),
                    disabled=(
                        len(slots) == 1
                    ),
                ):
                    eliminar_imagen_galeria(
                        orden_id,
                        uid,
                    )

                    st.rerun()

            col_img, col_config = (
                st.columns(
                    [
                        2,
                        1,
                    ]
                )
            )

            with col_config:
                if posicion == 0:
                    indice_default = 0
                else:
                    indice_default = 5

                tipo_imagen = (
                    st.selectbox(
                        "Nombre / tipo de imagen",
                        TIPOS_IMAGEN,
                        index=indice_default,
                        key=(
                            f"galeria_tipo_"
                            f"{orden_id}_"
                            f"{uid}"
                        ),
                    )
                )

                if tipo_imagen == "Otro":
                    nombre_imagen = (
                        st.text_input(
                            "Nombre personalizado",
                            placeholder=(
                                "Ej: Producto instalado"
                            ),
                            key=(
                                f"galeria_nombre_"
                                f"{orden_id}_"
                                f"{uid}"
                            ),
                        )
                    )
                else:
                    nombre_imagen = (
                        tipo_imagen
                    )

                if posicion == 0:
                    st.info(
                        "⭐ Esta imagen aparecerá "
                        "primero en el catálogo."
                    )

            with col_img:
                archivo = (
                    st.file_uploader(
                        "Subir imagen",
                        type=[
                            "png",
                            "jpg",
                            "jpeg",
                            "webp",
                        ],
                        key=(
                            f"galeria_archivo_"
                            f"{orden_id}_"
                            f"{uid}"
                        ),
                    )
                )

                resultado = (
                    mostrar_imagen_procesada(
                        archivo,
                        clave_descarga=(
                            f"descarga_"
                            f"{orden_id}_"
                            f"{uid}"
                        ),
                    )
                )

            if resultado:
                resultados_galeria.append(
                    {
                        "uid": uid,
                        "orden": (
                            posicion + 1
                        ),
                        "nombre": (
                            nombre_imagen
                            if nombre_imagen
                            else (
                                f"Imagen "
                                f"{posicion + 1}"
                            )
                        ),
                        "resultado": (
                            resultado
                        ),
                    }
                )

    # =====================================================
    # AGREGAR IMAGEN
    # =====================================================

    if st.button(
        "➕ Agregar otra imagen",
        use_container_width=True,
        key=(
            f"agregar_imagen_"
            f"{orden_id}"
        ),
    ):
        agregar_imagen_galeria(
            orden_id
        )

        st.rerun()

    # =====================================================
    # RELACIÓN
    # =====================================================

    st.divider()

    st.markdown(
        "### 🔗 Relación con el arte original"
    )

    confirmado = st.checkbox(
        (
            "Confirmo que las imágenes "
            "cargadas corresponden al arte "
            f"{orden_actual['Código']}"
        ),
        key=(
            f"confirmar_"
            f"{orden_id}"
        ),
    )

    if confirmado:
        st.success(
            "✅ Imágenes confirmadas "
            "para este arte."
        )
    else:
        st.warning(
            "⚠️ Confirma que las imágenes "
            "corresponden al arte seleccionado."
        )

    # =====================================================
    # 4. INFORMACIÓN
    # =====================================================

    st.divider()

    st.markdown(
        "## 4️⃣ Información del catálogo"
    )

    st.caption(
        "Información que utilizará "
        "la página pública."
    )

    titulo = st.text_input(
        "Título",
        placeholder=(
            "Ej: Diseño deportivo personalizado"
        ),
        key=(
            f"titulo_catalogo_"
            f"{orden_id}"
        ),
    )

    descripcion = st.text_area(
        "Descripción pública",
        placeholder=(
            "Describe brevemente "
            "el producto o diseño."
        ),
        key=(
            f"descripcion_catalogo_"
            f"{orden_id}"
        ),
    )

    col_meta1, col_meta2 = (
        st.columns(2)
    )

    colores = (
        col_meta1.text_input(
            "Colores",
            placeholder=(
                "Ej: Rojo, blanco, negro"
            ),
            key=(
                f"colores_catalogo_"
                f"{orden_id}"
            ),
        )
    )

    etiquetas = (
        col_meta2.text_input(
            "Etiquetas",
            placeholder=(
                "Ej: deportivo, sublimado, "
                "personalizado"
            ),
            key=(
                f"etiquetas_catalogo_"
                f"{orden_id}"
            ),
        )
    )

    # =====================================================
    # 5. ESTADO
    # =====================================================

    st.divider()

    st.markdown(
        "## 5️⃣ Estado de preparación"
    )

    cantidad_imagenes = len(
        resultados_galeria
    )

    datos_ok = bool(
        titulo
        and tipo_producto
        and categoria
        and descripcion
    )

    col_estado1, col_estado2, col_estado3 = (
        st.columns(3)
    )

    col_estado1.metric(
        "Imágenes",
        cantidad_imagenes,
    )

    col_estado2.metric(
        "Datos",
        (
            "OK"
            if datos_ok
            else "Pendiente"
        ),
    )

    col_estado3.metric(
        "Relación",
        (
            "Confirmada"
            if confirmado
            else "Pendiente"
        ),
    )

    # =====================================================
    # RESUMEN GALERÍA
    # =====================================================

    if resultados_galeria:
        st.markdown(
            "### 📸 Galería preparada"
        )

        resumen = []

        for item in resultados_galeria:
            resultado = item[
                "resultado"
            ]

            resumen.append(
                {
                    "Orden": (
                        item[
                            "orden"
                        ]
                    ),
                    "Nombre": (
                        item[
                            "nombre"
                        ]
                    ),
                    "Original": (
                        formatear_peso(
                            resultado[
                                "peso_original"
                            ]
                        )
                    ),
                    "Optimizada": (
                        formatear_peso(
                            resultado[
                                "peso_optimizado"
                            ]
                        )
                    ),
                    "Ahorro": (
                        f"{resultado['ahorro']:.1f}%"
                    ),
                    "Resolución": (
                        f"{ANCHO_CATALOGO} "
                        f"× "
                        f"{ALTO_CATALOGO}"
                    ),
                    "Formato": "WEBP",
                    "Marca": "YUNPAR",
                }
            )

        st.dataframe(
            pd.DataFrame(
                resumen
            ),
            use_container_width=True,
            hide_index=True,
        )

    # =====================================================
    # VALIDACIÓN
    # =====================================================

    listo = bool(
        cantidad_imagenes >= 1
        and datos_ok
        and confirmado
    )

    if listo:
        st.success(
            "✅ Esta publicación está lista. "
            "Puedes guardar el borrador de prueba."
        )
    else:
        st.warning(
            "⚠️ Aún faltan datos o imágenes "
            "para completar la publicación."
        )

    # =====================================================
    # BOTONES
    # =====================================================

    col_b1, col_b2 = (
        st.columns(2)
    )

    guardar = col_b1.button(
        "💾 Guardar borrador",
        use_container_width=True,
        key=(
            f"guardar_borrador_"
            f"{orden_id}"
        ),
    )

    col_b2.button(
        "🚀 Publicar en catálogo",
        disabled=True,
        use_container_width=True,
        type="primary",
        key=(
            f"publicar_catalogo_"
            f"{orden_id}"
        ),
    )

    # =====================================================
    # GUARDAR
    # =====================================================

    if guardar:
        if not listo:
            st.warning(
                "⚠️ Completa los datos, "
                "agrega al menos una imagen "
                "y confirma la relación con el arte."
            )

        else:
            guardar_borrador_temporal(
                orden_actual=orden_actual,
                tipo_producto=tipo_producto,
                categoria=categoria,
                titulo=titulo,
                descripcion=descripcion,
                colores=colores,
                etiquetas=etiquetas,
                confirmado=confirmado,
                resultados_galeria=(
                    resultados_galeria
                ),
            )

            st.success(
                "✅ Borrador guardado "
                "correctamente en modo de prueba."
            )

            st.info(
                "🔒 No se modificó Supabase "
                "y no se subieron archivos reales."
            )

    # =====================================================
    # MOSTRAR BORRADOR
    # =====================================================

    clave_borrador = (
        f"catalogo_borrador_"
        f"{orden_actual.get('ID')}"
    )

    borrador_actual = (
        st.session_state.get(
            clave_borrador
        )
    )

    if borrador_actual:
        mostrar_borrador_temporal(
            borrador_actual
        )

    st.caption(
        "💡 Guardar borrador funciona únicamente "
        "en memoria mientras el modo real esté desactivado. "
        "Las secciones de preparación de Storage y base de datos "
        "son simulaciones y no realizan ninguna escritura real."
    )