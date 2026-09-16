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
