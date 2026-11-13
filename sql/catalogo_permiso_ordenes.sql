-- ============================================================
-- YUNPAR ERP
-- Decisión comercial: puede ir / no puede ir al catálogo
-- Ejecutar UNA sola vez en Supabase por un administrador.
-- ============================================================

ALTER TABLE public.ordenes
    ADD COLUMN IF NOT EXISTS catalogo_permitido BOOLEAN NULL,
    ADD COLUMN IF NOT EXISTS catalogo_motivo TEXT NULL,
    ADD COLUMN IF NOT EXISTS catalogo_decidido_en TIMESTAMPTZ NULL;

COMMENT ON COLUMN public.ordenes.catalogo_permitido IS
'NULL = pendiente; TRUE = puede ir al catálogo; FALSE = no puede ir al catálogo';

COMMENT ON COLUMN public.ordenes.catalogo_motivo IS
'Motivo comercial cuando catalogo_permitido = FALSE';

COMMENT ON COLUMN public.ordenes.catalogo_decidido_en IS
'Fecha y hora de la última decisión explícita sobre publicación en catálogo';

CREATE INDEX IF NOT EXISTS idx_ordenes_catalogo_permitido
    ON public.ordenes (catalogo_permitido);
