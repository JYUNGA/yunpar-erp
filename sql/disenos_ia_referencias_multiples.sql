BEGIN;

ALTER TABLE public.disenos_ia_ventas
ADD COLUMN IF NOT EXISTS referencias_imagenes
jsonb NOT NULL DEFAULT '[]'::jsonb;

COMMENT ON COLUMN public.disenos_ia_ventas.referencias_imagenes IS
'Lista de imagenes de referencia: url, nombre, zona e indicacion.';

NOTIFY pgrst, 'reload schema';

COMMIT;
