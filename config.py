# config.py
class OrderState:
    PENDIENTE = "PENDIENTE DISEÑO"
    EN_DISENO = "EN DISEÑO"
    LISTO_IMPRESION = "LISTO PARA IMPRESIÓN"
    EN_IMPRESION = "EN IMPRESIÓN"
    EN_SUBLIMACION = "EN SUBLIMACIÓN"
    EN_CONFECCION = "EN CONFECCIÓN"
    LISTO_ENTREGA = "LISTA PARA ENTREGA"
    ENTREGADO = "ENTREGADO"
    ANULADO = "ANULADO"


# Mapa de normalización: cualquier variante (mayúsculas/acentos) → estado canónico.
_MAPA_ESTADOS = {
    "PENDIENTE": "PENDIENTE DISEÑO",
    "PENDIENTES DISEÑO": "PENDIENTE DISEÑO",
    "PENDIENTE DISEÑO": "PENDIENTE DISEÑO",
    "PENDIENTE DISENO": "PENDIENTE DISEÑO",
    "EN DISEÑO": "EN DISEÑO",
    "EN DISENO": "EN DISEÑO",
    "DISEÑO": "EN DISEÑO",
    "DISENO": "EN DISEÑO",
    "LISTO PARA IMPRESIÓN": "LISTO PARA IMPRESIÓN",
    "LISTO PARA IMPRESION": "LISTO PARA IMPRESIÓN",
    "LISTO IMPRESIÓN": "LISTO PARA IMPRESIÓN",
    "LISTO IMPRESION": "LISTO PARA IMPRESIÓN",
    "EN IMPRESIÓN": "EN IMPRESIÓN",
    "EN IMPRESION": "EN IMPRESIÓN",
    "IMPRESIÓN": "EN IMPRESIÓN",
    "IMPRESION": "EN IMPRESIÓN",
    "EN SUBLIMACIÓN": "EN SUBLIMACIÓN",
    "EN SUBLIMACION": "EN SUBLIMACIÓN",
    "SUBLIMACIÓN": "EN SUBLIMACIÓN",
    "SUBLIMACION": "EN SUBLIMACIÓN",
    "EN CONFECCIÓN": "EN CONFECCIÓN",
    "EN CONFECCION": "EN CONFECCIÓN",
    "CONFECCIÓN": "EN CONFECCIÓN",
    "CONFECCION": "EN CONFECCIÓN",
    "COSTURA": "EN CONFECCIÓN",
    "LISTA PARA ENTREGA": "LISTA PARA ENTREGA",
    "LISTO PARA ENTREGA": "LISTA PARA ENTREGA",
    "LISTO ENTREGA": "LISTA PARA ENTREGA",
    "ENTREGADO": "ENTREGADO",
    "ENTREGADA": "ENTREGADO",
    "ANULADO": "ANULADO",
    "ANULADA": "ANULADO",
    "CANCELADO": "ANULADO",
    "CANCELADA": "ANULADO",
}


def normalizar_estado(estado):
    """Devuelve el estado canónico para cualquier variante de texto."""
    if not estado:
        return estado
    clave = str(estado).strip().upper()
    return _MAPA_ESTADOS.get(clave, clave)


def transicionar_estado(
    supabase,
    orden_id,
    estado_nuevo,
    usuario_id,
    estado_anterior=None,
    notas="",
    datos_extra=None,
):
    """
    Actualiza el estado y datos adicionales en la orden, y deja un registro de auditoría.
    """
    # Normalizamos el estado para evitar variantes (mayúsculas/acentos).
    estado_nuevo = normalizar_estado(estado_nuevo)

    # 1. Preparar carga útil (payload) de actualización
    payload_orden = {"estado": estado_nuevo}
    if datos_extra and isinstance(datos_extra, dict):
        payload_orden.update(datos_extra)

    supabase.table("ordenes").update(payload_orden).eq("id", orden_id).execute()

    # 2. Registro de trazabilidad
    payload_historial = {
        "orden_id": orden_id,
        "estado_nuevo": estado_nuevo,
        "cambiado_por": usuario_id,
        "notas": notas,
    }
    if estado_anterior:
        payload_historial["estado_anterior"] = estado_anterior

    supabase.table("historial_estados").insert(payload_historial).execute()
