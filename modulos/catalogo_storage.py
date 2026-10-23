from __future__ import annotations

import re
import unicodedata

import streamlit as st
from supabase import create_client


# =========================================================
# CONFIGURACIÓN GENERAL
# =========================================================

BUCKET_CATALOGO = "catalogo-disenos"

LIMITE_ARCHIVO_BYTES = 2 * 1024 * 1024

MIME_PERMITIDOS = [
    "image/webp",
]


# =========================================================
# SEGURO PRINCIPAL
# =========================================================
#
# False:
# No permite crear bucket, subir, modificar ni borrar.
#
# True:
# Permitirá operaciones reales solamente si existe
# la configuración [supabase_admin] en secrets.toml.
#
# NO CAMBIAR TODAVÍA.
# =========================================================

MODO_SUPABASE_REAL = False


# =========================================================
# ESTADO GENERAL
# =========================================================

def storage_real_habilitado() -> bool:
    return MODO_SUPABASE_REAL is True


# =========================================================
# CLIENTE ADMINISTRATIVO
# =========================================================

def obtener_cliente_admin():
    """
    Crea un cliente administrativo independiente
    del cliente ANON utilizado normalmente por el ERP.

    Configuración futura esperada:

    [supabase_admin]
    url = "..."
    key = "..."

    NO agregar todavía esa sección.
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
    Convierte texto a una forma segura para rutas.

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
# GENERAR NOMBRE DE ARCHIVO
# =========================================================

def generar_nombre_archivo(
    posicion: int,
) -> str:
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
# GENERAR CARPETA DEL DISEÑO
# =========================================================

def generar_carpeta_publicacion(
    diseno_id,
) -> str:
    if diseno_id is None:
        raise ValueError(
            "El diseño debe tener un ID."
        )

    identificador = limpiar_texto_ruta(
        str(
            diseno_id
        )
    )

    return (
        f"diseno-{identificador}"
    )


# =========================================================
# GENERAR RUTA DE STORAGE
# =========================================================

def generar_ruta_storage(
    diseno_id,
    posicion: int,
) -> str:
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
# VALIDAR IMAGEN
# =========================================================

def validar_imagen_bytes(
    imagen_bytes: bytes,
):
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

    peso = len(
        imagen_bytes
    )

    if peso > LIMITE_ARCHIVO_BYTES:
        raise ValueError(
            "La imagen supera el límite permitido "
            "de 2 MB."
        )


# =========================================================
# PREPARAR SUBIDA SIN SUBIR
# =========================================================

def preparar_subida(
    diseno_id,
    posicion: int,
    imagen_bytes: bytes,
) -> dict:
    """
    Prepara la información de una futura subida.

    NO modifica Supabase.
    """

    validar_imagen_bytes(
        imagen_bytes
    )

    ruta = generar_ruta_storage(
        diseno_id,
        posicion,
    )

    return {
        "bucket": (
            BUCKET_CATALOGO
        ),
        "ruta": ruta,
        "bytes": imagen_bytes,
        "peso_bytes": len(
            imagen_bytes
        ),
        "content_type": (
            "image/webp"
        ),
    }


# =========================================================
# LEER NOMBRE / ID DE UN BUCKET
# =========================================================

def obtener_identificador_bucket(
    bucket,
):
    """
    Soporta respuestas tipo dict u objeto
    según la versión del cliente Supabase.
    """

    if isinstance(
        bucket,
        dict,
    ):
        return (
            bucket.get("id")
            or bucket.get("name")
        )

    identificador = getattr(
        bucket,
        "id",
        None,
    )

    if identificador:
        return identificador

    return getattr(
        bucket,
        "name",
        None,
    )


# =========================================================
# COMPROBAR SI EL BUCKET EXISTE
# =========================================================

def bucket_catalogo_existe(
    cliente_admin=None,
) -> bool:
    """
    Consulta si ya existe catalogo-disenos.

    Requiere modo real.
    """

    if not MODO_SUPABASE_REAL:
        raise RuntimeError(
            "Operación bloqueada: "
            "MODO_SUPABASE_REAL está desactivado."
        )

    if cliente_admin is None:
        cliente_admin = (
            obtener_cliente_admin()
        )

    buckets = (
        cliente_admin
        .storage
        .list_buckets()
    )

    for bucket in (
        buckets
        or []
    ):
        identificador = (
            obtener_identificador_bucket(
                bucket
            )
        )

        if identificador == BUCKET_CATALOGO:
            return True

    return False


# =========================================================
# CREAR / CONFIGURAR BUCKET
# =========================================================

def asegurar_bucket_catalogo():
    """
    Crea o actualiza el bucket del catálogo.

    Configuración:

    - Público.
    - Solo WEBP.
    - Máximo 2 MB por archivo.

    Mientras MODO_SUPABASE_REAL sea False,
    NO realiza ninguna operación.
    """

    if not MODO_SUPABASE_REAL:
        return {
            "ok": False,
            "estado": "BLOQUEADO",
            "bucket": BUCKET_CATALOGO,
            "mensaje": (
                "Modo Supabase real desactivado. "
                "No se creó ni modificó el bucket."
            ),
        }

    cliente_admin = (
        obtener_cliente_admin()
    )

    opciones = {
        "public": True,
        "allowed_mime_types": (
            MIME_PERMITIDOS
        ),
        "file_size_limit": (
            LIMITE_ARCHIVO_BYTES
        ),
    }

    existe = bucket_catalogo_existe(
        cliente_admin
    )

    if existe:
        respuesta = (
            cliente_admin
            .storage
            .update_bucket(
                BUCKET_CATALOGO,
                options=opciones,
            )
        )

        return {
            "ok": True,
            "estado": "ACTUALIZADO",
            "bucket": BUCKET_CATALOGO,
            "respuesta": respuesta,
        }

    respuesta = (
        cliente_admin
        .storage
        .create_bucket(
            BUCKET_CATALOGO,
            options=opciones,
        )
    )

    return {
        "ok": True,
        "estado": "CREADO",
        "bucket": BUCKET_CATALOGO,
        "respuesta": respuesta,
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
    Sube una imagen WEBP real.

    BLOQUEADA mientras MODO_SUPABASE_REAL=False.
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
                "content-type": (
                    "image/webp"
                ),
                "cache-control": (
                    "3600"
                ),
                "upsert": (
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
    Obtiene la URL pública de una imagen ya subida.
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
# CONSTRUIR REGISTRO PARA BD
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
# CONSTRUIR REGISTRO SIMULADO
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
    Simula exactamente cómo quedaría el registro
    de una imagen en la base.

    NO sube nada.
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
        ruta_storage=(
            subida["ruta"]
        ),
        url_publica=None,
        peso_bytes=(
            subida["peso_bytes"]
        ),
        ancho=ancho,
        alto=alto,
    )


# =========================================================
# ESTADO DEL STORAGE
# =========================================================

def obtener_estado_storage() -> dict:
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
        "bucket_publico": True,
        "mime_permitido": (
            "image/webp"
        ),
        "limite_mb": (
            LIMITE_ARCHIVO_BYTES
            / 1024
            / 1024
        ),
    }