from __future__ import annotations

import re
import unicodedata

import streamlit as st
from supabase import create_client


# =========================================================
# CONFIGURACIÓN GENERAL
# =========================================================

BUCKET_CATALOGO = "catalogo-disenos"

# =========================================================
# SEGURO PRINCIPAL
# =========================================================
#
# FALSE:
# No permite subir, borrar ni modificar archivos reales.
#
# TRUE:
# Permitirá operaciones reales SOLO si existe una
# configuración administrativa válida en secrets.toml.
#
# POR AHORA NO CAMBIAR.
# =========================================================

MODO_SUPABASE_REAL = False


# =========================================================
# ESTADO DEL STORAGE
# =========================================================

def storage_real_habilitado() -> bool:
    """
    Indica si las operaciones reales de Storage
    están habilitadas.

    Por ahora siempre será False mientras
    MODO_SUPABASE_REAL permanezca desactivado.
    """

    return MODO_SUPABASE_REAL is True


# =========================================================
# CLIENTE ADMINISTRATIVO
# =========================================================

def obtener_cliente_admin():
    """
    Obtiene un cliente administrativo independiente
    del cliente ANON que utiliza actualmente el ERP.

    IMPORTANTE:
    Esta función solamente se utilizará cuando
    MODO_SUPABASE_REAL sea True.

    La configuración futura será:

    [supabase_admin]
    url = "..."
    key = "..."

    NO crear esa configuración todavía.
    """

    if not MODO_SUPABASE_REAL:
        raise RuntimeError(
            "El modo Supabase real está desactivado."
        )

    try:
        config_admin = st.secrets[
            "supabase_admin"
        ]

        url = config_admin[
            "url"
        ]

        key = config_admin[
            "key"
        ]

    except Exception as e:
        raise RuntimeError(
            "No existe una configuración "
            "administrativa válida para Supabase."
        ) from e

    if not url or not key:
        raise RuntimeError(
            "La configuración administrativa "
            "de Supabase está incompleta."
        )

    return create_client(
        url,
        key,
    )


# =========================================================
# LIMPIAR TEXTO PARA RUTAS
# =========================================================

def limpiar_texto_ruta(
    texto: str,
) -> str:
    """
    Convierte texto normal en un texto seguro
    para utilizar dentro de rutas.

    Ejemplo:

    'Uniforme Pasaje Armado'
    ->
    'uniforme-pasaje-armado'
    """

    if not texto:
        return "sin-nombre"

    texto = str(
        texto
    ).strip().lower()

    texto = unicodedata.normalize(
        "NFKD",
        texto,
    )

    texto = "".join(
        caracter
        for caracter in texto
        if not unicodedata.combining(
            caracter
        )
    )

    texto = re.sub(
        r"[^a-z0-9]+",
        "-",
        texto,
    )

    texto = texto.strip(
        "-"
    )

    return texto or "sin-nombre"


# =========================================================
# GENERAR NOMBRE DEL ARCHIVO
# =========================================================

def generar_nombre_archivo(
    posicion: int,
) -> str:
    """
    Genera nombres internos estables.

    Ejemplos:

    1  -> 01.webp
    2  -> 02.webp
    10 -> 10.webp
    """

    posicion = int(
        posicion
    )

    if posicion < 1:
        raise ValueError(
            "La posición debe ser mayor o igual a 1."
        )

    return (
        f"{posicion:02d}.webp"
    )


# =========================================================
# GENERAR CARPETA DE PUBLICACIÓN
# =========================================================

def generar_carpeta_publicacion(
    diseno_id,
) -> str:
    """
    Genera la carpeta interna del diseño.

    Ejemplo:

    diseno_id = 25

    Resultado:
    diseno-25
    """

    if diseno_id is None:
        raise ValueError(
            "El diseño debe tener un ID."
        )

    return (
        f"diseno-{diseno_id}"
    )


# =========================================================
# GENERAR RUTA STORAGE
# =========================================================

def generar_ruta_storage(
    diseno_id,
    posicion: int,
) -> str:
    """
    Genera la ruta completa dentro del bucket.

    Ejemplo:

    diseno-25/01.webp
    """

    carpeta = (
        generar_carpeta_publicacion(
            diseno_id
        )
    )

    archivo = (
        generar_nombre_archivo(
            posicion
        )
    )

    return (
        f"{carpeta}/{archivo}"
    )


# =========================================================
# VALIDAR BYTES DE IMAGEN
# =========================================================

def validar_imagen_bytes(
    imagen_bytes: bytes,
):
    """
    Comprueba que exista contenido antes
    de intentar una futura subida.
    """

    if not imagen_bytes:
        raise ValueError(
            "No se recibieron bytes de imagen."
        )

    if not isinstance(
        imagen_bytes,
        bytes,
    ):
        raise TypeError(
            "La imagen debe estar en formato bytes."
        )


# =========================================================
# PREPARAR SUBIDA
# =========================================================

def preparar_subida(
    diseno_id,
    posicion: int,
    imagen_bytes: bytes,
) -> dict:
    """
    Prepara la información que posteriormente
    se utilizará para subir una imagen.

    ESTA FUNCIÓN NO SUBE NADA.

    Es segura para utilizar durante las pruebas.
    """

    validar_imagen_bytes(
        imagen_bytes
    )

    ruta = generar_ruta_storage(
        diseno_id,
        posicion,
    )

    return {
        "bucket": BUCKET_CATALOGO,
        "ruta": ruta,
        "bytes": imagen_bytes,
        "peso_bytes": len(
            imagen_bytes
        ),
        "content_type": "image/webp",
    }


# =========================================================
# SUBIR IMAGEN REAL
# =========================================================

def subir_imagen_catalogo(
    diseno_id,
    posicion: int,
    imagen_bytes: bytes,
    sobrescribir: bool = False,
):
    """
    Sube realmente una imagen optimizada
    al Storage del catálogo.

    Mientras MODO_SUPABASE_REAL sea False,
    esta función se bloqueará automáticamente.
    """

    if not MODO_SUPABASE_REAL:
        raise RuntimeError(
            "Operación bloqueada: "
            "MODO_SUPABASE_REAL está desactivado."
        )

    validar_imagen_bytes(
        imagen_bytes
    )

    cliente_admin = (
        obtener_cliente_admin()
    )

    ruta = generar_ruta_storage(
        diseno_id,
        posicion,
    )

    respuesta = (
        cliente_admin
        .storage
        .from_(
            BUCKET_CATALOGO
        )
        .upload(
            path=ruta,
            file=imagen_bytes,
            file_options={
                "content-type":
                    "image/webp",

                "cache-control":
                    "3600",

                "upsert":
                    (
                        "true"
                        if sobrescribir
                        else "false"
                    ),
            },
        )
    )

    return {
        "bucket": (
            BUCKET_CATALOGO
        ),
        "ruta": ruta,
        "respuesta": respuesta,
    }


# =========================================================
# OBTENER URL PÚBLICA
# =========================================================

def obtener_url_publica(
    ruta: str,
):
    """
    Obtiene la URL pública de una imagen.

    Solamente podrá utilizarse cuando
    el modo real esté habilitado.
    """

    if not MODO_SUPABASE_REAL:
        raise RuntimeError(
            "Operación bloqueada: "
            "MODO_SUPABASE_REAL está desactivado."
        )

    if not ruta:
        raise ValueError(
            "La ruta no puede estar vacía."
        )

    cliente_admin = (
        obtener_cliente_admin()
    )

    return (
        cliente_admin
        .storage
        .from_(
            BUCKET_CATALOGO
        )
        .get_public_url(
            ruta
        )
    )


# =========================================================
# ELIMINAR UNA IMAGEN
# =========================================================

def eliminar_imagen_catalogo(
    ruta: str,
):
    """
    Elimina una imagen real del bucket.

    Está bloqueada mientras el modo real
    se encuentre desactivado.
    """

    if not MODO_SUPABASE_REAL:
        raise RuntimeError(
            "Operación bloqueada: "
            "MODO_SUPABASE_REAL está desactivado."
        )

    if not ruta:
        raise ValueError(
            "La ruta no puede estar vacía."
        )

    cliente_admin = (
        obtener_cliente_admin()
    )

    return (
        cliente_admin
        .storage
        .from_(
            BUCKET_CATALOGO
        )
        .remove(
            [
                ruta
            ]
        )
    )


# =========================================================
# ELIMINAR VARIAS IMÁGENES
# =========================================================

def eliminar_imagenes_catalogo(
    rutas: list[str],
):
    """
    Elimina varias imágenes reales.

    Está bloqueada mientras el modo real
    permanezca desactivado.
    """

    if not MODO_SUPABASE_REAL:
        raise RuntimeError(
            "Operación bloqueada: "
            "MODO_SUPABASE_REAL está desactivado."
        )

    rutas_validas = [
        ruta
        for ruta in rutas
        if ruta
    ]

    if not rutas_validas:
        return None

    cliente_admin = (
        obtener_cliente_admin()
    )

    return (
        cliente_admin
        .storage
        .from_(
            BUCKET_CATALOGO
        )
        .remove(
            rutas_validas
        )
    )


# =========================================================
# CONSTRUIR REGISTRO PARA catalogo_imagenes
# =========================================================

def construir_registro_imagen(
    diseno_id,
    nombre_visible: str,
    posicion: int,
    ruta_storage: str,
    url_publica: str | None = None,
    peso_bytes: int | None = None,
    ancho: int | None = None,
    alto: int | None = None,
) -> dict:
    """
    Construye los datos que posteriormente
    se guardarán en catalogo_imagenes.

    No escribe nada en la base.
    """

    return {
        "diseno_id": (
            diseno_id
        ),
        "nombre": (
            nombre_visible
        ),
        "storage_path": (
            ruta_storage
        ),
        "url_publica": (
            url_publica
        ),
        "orden": (
            posicion
        ),
        "es_portada": (
            posicion == 1
        ),
        "ancho": ancho,
        "alto": alto,
        "formato": "WEBP",
        "peso_bytes": (
            peso_bytes
        ),
    }


# =========================================================
# CONSTRUIR REGISTRO DE PRUEBA
# =========================================================

def construir_registro_prueba(
    diseno_id,
    nombre_visible: str,
    posicion: int,
    imagen_bytes: bytes,
    ancho: int = 1080,
    alto: int = 1350,
) -> dict:
    """
    Simula cómo quedaría una imagen preparada
    para Supabase.

    NO sube nada.
    NO modifica la base.
    """

    subida = preparar_subida(
        diseno_id=diseno_id,
        posicion=posicion,
        imagen_bytes=imagen_bytes,
    )

    return construir_registro_imagen(
        diseno_id=diseno_id,
        nombre_visible=nombre_visible,
        posicion=posicion,
        ruta_storage=subida[
            "ruta"
        ],
        url_publica=None,
        peso_bytes=subida[
            "peso_bytes"
        ],
        ancho=ancho,
        alto=alto,
    )


# =========================================================
# INFORMACIÓN DEL MODO ACTUAL
# =========================================================

def obtener_estado_storage() -> dict:
    """
    Devuelve información simple para mostrar
    en el módulo del catálogo.
    """

    return {
        "modo_real": (
            MODO_SUPABASE_REAL
        ),
        "bucket": (
            BUCKET_CATALOGO
        ),
        "estado": (
            "REAL"
            if MODO_SUPABASE_REAL
            else "PRUEBA"
        ),
        "puede_escribir": (
            MODO_SUPABASE_REAL
        ),
    }