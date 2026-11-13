-- =============================================================
-- YUNPAR - Diseño IA para Ventas/Cotizaciones
-- Ejecutar UNA SOLA VEZ en Supabase > SQL Editor.
-- No elimina ni modifica datos existentes.
-- =============================================================

CREATE TABLE IF NOT EXISTS public.disenos_ia_ventas (
    id bigserial PRIMARY KEY,
    codigo varchar(30) NOT NULL UNIQUE,
    cliente_id integer NOT NULL REFERENCES public.clientes(id) ON DELETE RESTRICT,
    cliente_nombre varchar(255),
    producto_id integer REFERENCES public.productos_catalogo(id) ON DELETE SET NULL,
    producto_codigo varchar(100),
    producto_descripcion text,
    tecnica varchar(50),
    colores text,
    instrucciones text NOT NULL,
    referencia_url text,
    referencia_link text,
    propuesta_url text,
    generacion_real boolean NOT NULL DEFAULT false,
    estado varchar(60) NOT NULL DEFAULT 'PROPUESTA PREPARADA',
    revision integer NOT NULL DEFAULT 1,
    ajuste_solicitado text,
    fecha_entrega_estimada date,
    fecha_aprobacion timestamp without time zone,
    fecha_envio_diseno timestamp without time zone,
    orden_id integer REFERENCES public.ordenes(id) ON DELETE SET NULL,
    cotizacion_id integer REFERENCES public.cotizaciones(id) ON DELETE SET NULL,
    creado_por_id bigint,
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_disenos_ia_ventas_estado
    ON public.disenos_ia_ventas(estado);

CREATE INDEX IF NOT EXISTS idx_disenos_ia_ventas_cliente
    ON public.disenos_ia_ventas(cliente_id);

CREATE INDEX IF NOT EXISTS idx_disenos_ia_ventas_created_at
    ON public.disenos_ia_ventas(created_at DESC);

COMMENT ON TABLE public.disenos_ia_ventas IS
'Propuestas visuales generadas por Ventas con IA antes de pasar al diseñador humano.';
