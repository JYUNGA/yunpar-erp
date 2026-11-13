-- ============================================================
-- YUNPAR ERP
-- PUNTO 6: EVITAR PREPARAR DOS VECES EL MISMO DISEÑO
-- LO EJECUTA EL INGENIERO EN SUPABASE - UNA SOLA VEZ
-- ============================================================

do $$
begin
    if to_regclass('public.catalogo_disenos') is null then
        raise notice 'La tabla public.catalogo_disenos todavía no existe. Ejecute primero la migración base del catálogo.';
        return;
    end if;

    alter table public.catalogo_disenos
        add column if not exists arte_original_hash text;

    comment on column public.catalogo_disenos.arte_original_hash is
        'SHA-256 del arte original. Se usa para evitar publicar/preparar dos veces el mismo diseño en órdenes diferentes.';

    create index if not exists idx_catalogo_disenos_arte_original_hash
        on public.catalogo_disenos (arte_original_hash)
        where arte_original_hash is not null;

    if not exists (
        select 1
        from public.catalogo_disenos
        where arte_original_hash is not null
          and btrim(arte_original_hash) <> ''
        group by arte_original_hash
        having count(*) > 1
    ) then
        create unique index if not exists uq_catalogo_disenos_arte_original_hash
            on public.catalogo_disenos (arte_original_hash)
            where arte_original_hash is not null
              and btrim(arte_original_hash) <> '';
    else
        raise notice 'Existen hashes duplicados previos; no se creó el índice UNIQUE. Revise esos registros antes de activarlo.';
    end if;
end
$$;
