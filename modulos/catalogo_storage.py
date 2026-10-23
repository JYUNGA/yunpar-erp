from __future__ import annotations

import re
import unicodedata


# =========================================================
# CONFIGURACIÓN
# =========================================================

BUCKET_CATALOGO = "catalogo-disenos"


# =========================================================
# LIMPIEZA DE TEXTO
# =========================================================

def limpiar_texto_ruta(texto: str) -> str:
    """
    Convierte un texto en algo seguro para usar
    dentro de una ruta de Storage.

    Ejemplo:
    'Uniforme Pasaje Armado' -> 'uniforme-pasaje-armado'
    """

    if not texto:
        return "sin-nombre"

    texto = str(texto).strip().lower()

    texto = unicodedata.normalize(
        "NFKD",
        texto,
    )

    texto = "".join(
        caracter
        for caracter in texto
        if not unicodedata.combining(caracter)
    )

    texto = re.sub(
        r"[^a-z0-9]+",
        "-",
        texto,
    )

    texto = texto.strip("-")

    return texto or "sin-nombre"


# =========================================================
# GENERAR NOMBRE DE ARCHIVO
# =========================================================

def generar_nombre_archivo(
    posicion: int,
) -> str:
    """
    Genera nombres internos estables.

    Ejemplo:
    1 -> 01.webp
    2 -> 02.webp
    10 -> 10.webp
    """

    return f"{int(posicion):02d}.webp"


# =========================================================
# GENERAR CARPETA DE PUBLICACIÓN
# =========================================================

def generar_carpeta_publicacion(
    diseno_id,
) -> str:
    """
    Genera la carpeta principal de un diseño.

    Ejemplo:
    diseno_id = 25

    Resultado:
    diseno-25
    """

    return f"diseno-{diseno_id}"


# =========================================================
# GENERAR RUTA COMPLETA
# =========================================================

def generar_ruta_storage(
    diseno_id,
    posicion: int,
) -> str:
    """
    Genera la ruta del archivo dentro del bucket.

    Ejemplo:
    diseno-25/01.webp
    """

    carpeta = generar_carpeta_publicacion(
        diseno_id
    )

    archivo = generar_nombre_archivo(
        posicion
    )

    return f"{carpeta}/{archivo}"


# =========================================================
# SUBIR IMAGEN
# =========================================================

def subir_imagen_catalogo(
    supabase,
    diseno_id,
    posicion: int,
    imagen_bytes: bytes,
    sobrescribir: bool = False,
):
    """
    Sube una imagen WEBP al bucket del catálogo.

    IMPORTANTE:
    Esta función todavía no debe ejecutarse
    hasta crear/autorizarnos el bucket y sus políticas.
    """

    if not imagen_bytes:
        raise ValueError(
            "No se recibieron bytes de imagen."
        )

    ruta = generar_ruta_storage(
        diseno_id,
        posicion,
    )

    respuesta = (
        supabase.storage
        .from_(BUCKET_CATALOGO)
        .upload(
            path=ruta,
            file=imagen_bytes,
            file_options={
                "content-type": "image/webp",
                "cache-control": "3600",
                "upsert": (
                    "true"
                    if sobrescribir
                    else "false"
                ),
            },
        )
    )

    return {
        "ruta": ruta,
        "respuesta": respuesta,
    }


# =========================================================
# OBTENER URL PÚBLICA
# =========================================================

def obtener_url_publica(
    supabase,
    ruta: str,
):
    """
    Devuelve la URL pública de una imagen.

    Solo funcionará si el bucket es público.
    """

    if not ruta:
        return None

    return (
        supabase.storage
        .from_(BUCKET_CATALOGO)
        .get_public_url(
            ruta
        )
    )


# =========================================================
# ELIMINAR IMAGEN
# =========================================================

def eliminar_imagen_catalogo(
    supabase,
    ruta: str,
):
    """
    Elimina una imagen del bucket.
    """

    if not ruta:
        return None

    return (
        supabase.storage
        .from_(BUCKET_CATALOGO)
        .remove(
            [ruta]
        )
    )


# =========================================================
# ELIMINAR VARIAS IMÁGENES
# =========================================================

def eliminar_imagenes_catalogo(
    supabase,
    rutas: list[str],
):
    """
    Elimina varias imágenes del bucket.
    """

    rutas_validas = [
        ruta
        for ruta in rutas
        if ruta
    ]

    if not rutas_validas:
        return None

    return (
        supabase.storage
        .from_(BUCKET_CATALOGO)
        .remove(
            rutas_validas
        )
    )


# =========================================================
# PREPARAR DATOS PARA BD
# =========================================================

def construir_registro_imagen(
    diseno_id,
    nombre_visible: str,
    posicion: int,
    ruta_storage: str,
    url_publica: str | None,
    peso_bytes: int | None = None,
    ancho: int | None = None,
    alto: int | None = None,
):
    """
    Construye el registro que posteriormente
    guardaremos en catalogo_imagenes.
    """

    return {
        "diseno_id": diseno_id,
        "nombre": nombre_visible,
        "storage_path": ruta_storage,
        "url_publica": url_publica,
        "orden": posicion,
        "es_portada": posicion == 1,
        "ancho": ancho,
        "alto": alto,
        "formato": "WEBP",
        "peso_bytes": peso_bytes,
    }