from __future__ import annotations

from modulos import catalogo_storage


# =========================================================
# CONFIGURACIÓN GENERAL
# =========================================================
#
# False:
# Ninguna función de escritura puede modificar la BD real.
#
# True:
# Se permitirá guardar, publicar, ocultar y eliminar
# únicamente utilizando el cliente administrativo.
#
# NO CAMBIAR TODAVÍA.
# =========================================================

MODO_DB_REAL = False


# =========================================================
# ESTADO GENERAL
# =========================================================

def db_real_habilitada() -> bool:
    """
    Indica si las operaciones reales de la base
    están habilitadas.
    """

    return (
        MODO_DB_REAL is True
        and catalogo_storage.storage_real_habilitado()
    )


def obtener_estado_db() -> dict:
    """
    Devuelve el estado actual de la conexión
    administrativa del catálogo.
    """

    return {
        "modo_real": MODO_DB_REAL,
        "storage_real": (
            catalogo_storage
            .storage_real_habilitado()
        ),
        "puede_escribir": (
            db_real_habilitada()
        ),
        "estado": (
            "REAL"
            if db_real_habilitada()
            else "PRUEBA"
        ),
    }


# =========================================================
# SEGURIDAD
# =========================================================

def verificar_modo_real():
    """
    Bloquea cualquier operación de escritura
    mientras el modo real esté desactivado.
    """

    if not MODO_DB_REAL:
        raise RuntimeError(
            "Operación bloqueada: "
            "MODO_DB_REAL está desactivado."
        )

    if not (
        catalogo_storage
        .storage_real_habilitado()
    ):
        raise RuntimeError(
            "Operación bloqueada: "
            "Supabase Storage real está desactivado."
        )


# =========================================================
# CLIENTE ADMINISTRATIVO
# =========================================================

def obtener_cliente_admin():
    """
    Reutiliza el mismo cliente administrativo
    definido para Storage.

    Nunca utiliza el cliente ANON normal del ERP.
    """

    verificar_modo_real()

    return (
        catalogo_storage
        .obtener_cliente_admin()
    )


# =========================================================
# BUSCAR TIPO DE PRODUCTO
# =========================================================

def obtener_tipo_producto_id(
    cliente_admin,
    nombre: str,
):
    """
    Busca el ID real del tipo de producto.
    """

    if not nombre:
        raise ValueError(
            "El tipo de producto es obligatorio."
        )

    respuesta = (
        cliente_admin
        .table(
            "catalogo_tipos_producto"
        )
        .select(
            "id, nombre"
        )
        .eq(
            "nombre",
            nombre,
        )
        .limit(
            1
        )
        .execute()
    )

    datos = (
        respuesta.data
        or []
    )

    if not datos:
        raise ValueError(
            f"No existe el tipo de producto "
            f"'{nombre}' en Supabase."
        )

    return datos[0]["id"]


# =========================================================
# BUSCAR CATEGORÍA
# =========================================================

def obtener_categoria_id(
    cliente_admin,
    nombre: str,
):
    """
    Busca el ID real de la categoría.
    """

    if not nombre:
        raise ValueError(
            "La categoría es obligatoria."
        )

    respuesta = (
        cliente_admin
        .table(
            "catalogo_categorias"
        )
        .select(
            "id, nombre"
        )
        .eq(
            "nombre",
            nombre,
        )
        .limit(
            1
        )
        .execute()
    )

    datos = (
        respuesta.data
        or []
    )

    if not datos:
        raise ValueError(
            f"No existe la categoría "
            f"'{nombre}' en Supabase."
        )

    return datos[0]["id"]


# =========================================================
# CONSTRUIR REGISTRO DEL DISEÑO
# =========================================================

def construir_registro_diseno(
    borrador: dict,
    tipo_producto_id,
    categoria_id,
) -> dict:
    """
    Convierte el borrador de Streamlit
    al formato de catalogo_disenos.
    """

    return {
        "codigo_orden_origen": (
            borrador.get(
                "codigo_orden"
            )
        ),
        "cliente_origen": (
            borrador.get(
                "cliente"
            )
        ),
        "arte_original_url": (
            borrador.get(
                "arte_original"
            )
        ),
        "tipo_producto_id": (
            tipo_producto_id
        ),
        "categoria_id": (
            categoria_id
        ),
        "titulo": (
            borrador.get(
                "titulo",
                "",
            ).strip()
        ),
        "descripcion": (
            borrador.get(
                "descripcion",
                "",
            ).strip()
        ),
        "colores": (
            borrador.get(
                "colores",
                [],
            )
        ),
        "etiquetas": (
            borrador.get(
                "etiquetas",
                [],
            )
        ),
        "estado": (
            "BORRADOR"
        ),
    }


# =========================================================
# VALIDAR BORRADOR
# =========================================================

def validar_borrador(
    borrador: dict,
):
    """
    Comprueba que el borrador tenga la
    información mínima necesaria.
    """

    if not borrador:
        raise ValueError(
            "No existe un borrador para guardar."
        )

    if not borrador.get(
        "titulo"
    ):
        raise ValueError(
            "El título es obligatorio."
        )

    if not borrador.get(
        "descripcion"
    ):
        raise ValueError(
            "La descripción es obligatoria."
        )

    if not borrador.get(
        "tipo_producto"
    ):
        raise ValueError(
            "El tipo de producto es obligatorio."
        )

    if not borrador.get(
        "categoria"
    ):
        raise ValueError(
            "La categoría es obligatoria."
        )

    if not borrador.get(
        "relacion_confirmada"
    ):
        raise ValueError(
            "Debe confirmarse la relación "
            "con el arte original."
        )

    imagenes = (
        borrador.get(
            "imagenes",
            []
        )
    )

    if not imagenes:
        raise ValueError(
            "Debe existir al menos una imagen."
        )

    portadas = [
        imagen
        for imagen in imagenes
        if imagen.get(
            "es_portada"
        )
    ]

    if len(
        portadas
    ) != 1:
        raise ValueError(
            "Debe existir exactamente "
            "una imagen de portada."
        )


# =========================================================
# SIMULACIÓN DEL REGISTRO
# =========================================================

def preparar_guardado_simulado(
    borrador: dict,
) -> dict:
    """
    Simula la estructura que posteriormente
    se guardará en la BD.

    NO escribe nada.
    """

    validar_borrador(
        borrador
    )

    imagenes = []

    codigo = (
        borrador.get(
            "codigo_orden"
        )
        or "sin-orden"
    )

    for imagen in borrador.get(
        "imagenes",
        [],
    ):
        registro = (
            catalogo_storage
            .construir_registro_prueba(
                diseno_id=codigo,
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
                        1080,
                    )
                ),
                alto=(
                    imagen.get(
                        "alto",
                        1350,
                    )
                ),
            )
        )

        imagenes.append(
            registro
        )

    return {
        "estado": "PRUEBA",
        "diseno": {
            "codigo_orden_origen": (
                borrador.get(
                    "codigo_orden"
                )
            ),
            "cliente_origen": (
                borrador.get(
                    "cliente"
                )
            ),
            "arte_original_url": (
                borrador.get(
                    "arte_original"
                )
            ),
            "tipo_producto": (
                borrador.get(
                    "tipo_producto"
                )
            ),
            "categoria": (
                borrador.get(
                    "categoria"
                )
            ),
            "titulo": (
                borrador.get(
                    "titulo"
                )
            ),
            "descripcion": (
                borrador.get(
                    "descripcion"
                )
            ),
            "colores": (
                borrador.get(
                    "colores",
                    [],
                )
            ),
            "etiquetas": (
                borrador.get(
                    "etiquetas",
                    [],
                )
            ),
            "estado": "BORRADOR",
        },
        "imagenes": imagenes,
    }


# =========================================================
# INSERTAR DISEÑO REAL
# =========================================================

def insertar_diseno_real(
    cliente_admin,
    registro: dict,
):
    """
    Inserta una publicación en catalogo_disenos.
    """

    respuesta = (
        cliente_admin
        .table(
            "catalogo_disenos"
        )
        .insert(
            registro
        )
        .execute()
    )

    datos = (
        respuesta.data
        or []
    )

    if not datos:
        raise RuntimeError(
            "Supabase no devolvió el diseño creado."
        )

    diseno = datos[0]

    if not diseno.get(
        "id"
    ):
        raise RuntimeError(
            "El diseño creado no tiene ID."
        )

    return diseno


# =========================================================
# INSERTAR IMAGEN REAL
# =========================================================

def insertar_imagen_real(
    cliente_admin,
    registro: dict,
):
    """
    Inserta un registro en catalogo_imagenes.
    """

    respuesta = (
        cliente_admin
        .table(
            "catalogo_imagenes"
        )
        .insert(
            registro
        )
        .execute()
    )

    datos = (
        respuesta.data
        or []
    )

    if not datos:
        raise RuntimeError(
            "Supabase no devolvió "
            "la imagen creada."
        )

    return datos[0]


# =========================================================
# ELIMINAR DISEÑO REAL
# =========================================================

def eliminar_diseno_real(
    cliente_admin,
    diseno_id,
):
    """
    Elimina un diseño.

    catalogo_imagenes se elimina automáticamente
    mediante ON DELETE CASCADE.
    """

    return (
        cliente_admin
        .table(
            "catalogo_disenos"
        )
        .delete()
        .eq(
            "id",
            diseno_id,
        )
        .execute()
    )


# =========================================================
# GUARDAR BORRADOR REAL
# =========================================================

def guardar_borrador_real(
    borrador: dict,
) -> dict:
    """
    Flujo completo de guardado real:

    1. Valida el borrador.
    2. Verifica modo seguro.
    3. Busca tipo y categoría.
    4. Inserta catalogo_disenos.
    5. Obtiene ID real.
    6. Sube imágenes a Storage.
    7. Inserta catalogo_imagenes.
    8. Si algo falla, intenta revertir.

    Esta función permanece BLOQUEADA
    mientras MODO_DB_REAL=False.
    """

    verificar_modo_real()

    validar_borrador(
        borrador
    )

    cliente_admin = (
        obtener_cliente_admin()
    )

    diseno_id = None

    rutas_subidas = []

    imagenes_creadas = []

    try:
        # =================================================
        # ASEGURAR BUCKET
        # =================================================

        estado_bucket = (
            catalogo_storage
            .asegurar_bucket_catalogo()
        )

        if not estado_bucket.get(
            "ok"
        ):
            raise RuntimeError(
                estado_bucket.get(
                    "mensaje",
                    "No se pudo preparar el bucket.",
                )
            )

        # =================================================
        # OBTENER TIPO
        # =================================================

        tipo_producto_id = (
            obtener_tipo_producto_id(
                cliente_admin,
                borrador.get(
                    "tipo_producto"
                ),
            )
        )

        # =================================================
        # OBTENER CATEGORÍA
        # =================================================

        categoria_id = (
            obtener_categoria_id(
                cliente_admin,
                borrador.get(
                    "categoria"
                ),
            )
        )

        # =================================================
        # CREAR DISEÑO
        # =================================================

        registro_diseno = (
            construir_registro_diseno(
                borrador=borrador,
                tipo_producto_id=(
                    tipo_producto_id
                ),
                categoria_id=(
                    categoria_id
                ),
            )
        )

        diseno_creado = (
            insertar_diseno_real(
                cliente_admin,
                registro_diseno,
            )
        )

        diseno_id = (
            diseno_creado[
                "id"
            ]
        )

        # =================================================
        # SUBIR IMÁGENES
        # =================================================

        for imagen in borrador.get(
            "imagenes",
            [],
        ):
            posicion = (
                imagen.get(
                    "orden",
                    1,
                )
            )

            subida = (
                catalogo_storage
                .subir_imagen_catalogo(
                    diseno_id=diseno_id,
                    posicion=posicion,
                    imagen_bytes=(
                        imagen.get(
                            "bytes"
                        )
                    ),
                    sobrescribir=False,
                )
            )

            ruta = subida[
                "ruta"
            ]

            rutas_subidas.append(
                ruta
            )

            url_publica = (
                catalogo_storage
                .obtener_url_publica(
                    ruta
                )
            )

            registro_imagen = (
                catalogo_storage
                .construir_registro_imagen(
                    diseno_id=(
                        diseno_id
                    ),
                    nombre_visible=(
                        imagen.get(
                            "nombre",
                            "Imagen",
                        )
                    ),
                    posicion=(
                        posicion
                    ),
                    ruta_storage=(
                        ruta
                    ),
                    url_publica=(
                        url_publica
                    ),
                    peso_bytes=(
                        imagen.get(
                            "peso_optimizado"
                        )
                    ),
                    ancho=(
                        imagen.get(
                            "ancho"
                        )
                    ),
                    alto=(
                        imagen.get(
                            "alto"
                        )
                    ),
                )
            )

            imagen_creada = (
                insertar_imagen_real(
                    cliente_admin,
                    registro_imagen,
                )
            )

            imagenes_creadas.append(
                imagen_creada
            )

        return {
            "ok": True,
            "estado": "BORRADOR",
            "diseno_id": (
                diseno_id
            ),
            "diseno": (
                diseno_creado
            ),
            "imagenes": (
                imagenes_creadas
            ),
            "rutas": (
                rutas_subidas
            ),
        }

    except Exception as e:
        # =================================================
        # REVERSIÓN DE STORAGE
        # =================================================

        if rutas_subidas:
            try:
                catalogo_storage.eliminar_imagenes_catalogo(
                    rutas_subidas
                )
            except Exception:
                pass

        # =================================================
        # REVERSIÓN DE BD
        # =================================================

        if diseno_id is not None:
            try:
                eliminar_diseno_real(
                    cliente_admin,
                    diseno_id,
                )
            except Exception:
                pass

        raise RuntimeError(
            f"No se pudo guardar el borrador real: {e}"
        ) from e


# =========================================================
# CAMBIAR ESTADO
# =========================================================

def cambiar_estado_diseno(
    diseno_id,
    nuevo_estado: str,
):
    """
    Cambia el estado de una publicación.

    Estados permitidos:
    BORRADOR
    PUBLICADO
    OCULTO
    """

    verificar_modo_real()

    estados_validos = [
        "BORRADOR",
        "PUBLICADO",
        "OCULTO",
    ]

    if nuevo_estado not in estados_validos:
        raise ValueError(
            "Estado de catálogo no válido."
        )

    cliente_admin = (
        obtener_cliente_admin()
    )

    respuesta = (
        cliente_admin
        .table(
            "catalogo_disenos"
        )
        .update(
            {
                "estado": nuevo_estado
            }
        )
        .eq(
            "id",
            diseno_id,
        )
        .execute()
    )

    datos = (
        respuesta.data
        or []
    )

    if not datos:
        raise RuntimeError(
            "No se pudo actualizar "
            "el estado de la publicación."
        )

    return datos[0]


# =========================================================
# PUBLICAR
# =========================================================

def publicar_diseno_real(
    diseno_id,
):
    return cambiar_estado_diseno(
        diseno_id,
        "PUBLICADO",
    )


# =========================================================
# OCULTAR
# =========================================================

def ocultar_diseno_real(
    diseno_id,
):
    return cambiar_estado_diseno(
        diseno_id,
        "OCULTO",
    )


# =========================================================
# VOLVER A BORRADOR
# =========================================================

def volver_borrador_real(
    diseno_id,
):
    return cambiar_estado_diseno(
        diseno_id,
        "BORRADOR",
    )