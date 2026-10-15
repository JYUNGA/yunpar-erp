# Revisión ERP YUNPAR — Usabilidad, Experiencia de Usuario y Módulo de Gastos/Ingresos

> Documento de diagnóstico y propuesta de mejoras. Generado a partir de la revisión del código
> (`App.py`, `config.py`, los 16 módulos de `modulos/`, `requirements.txt` y `Sql_Supabase.txt`).
> Foco solicitado: **usar el sistema desde el celular** y **registro de gastos e ingresos**.

---

## 1. Resumen ejecutivo

YUNPAR es un ERP funcional y con alcance de negocio real (ventas, cotizaciones, producción,
diseño, impresión, facturación, finanzas, nómina, APUs, polines). Está bien orientado al flujo
de una fábrica de uniformes. Sin embargo, **fue pensado para escritorio**, y el pedido de "usarlo
desde el celular" choca con tres decisiones de diseño que se repiten en todos los módulos:

1. **Navegación por tablas interactivas** (`st.dataframe` con `selection_mode="single-row"` /
   `multi-row`): obliga a hacer clic preciso en una fila para actuar. En un celular es muy
   difícil de tocar y no es accesible.
2. **Formularios largos con 3–4 columnas**: en pantalla angosta se apilan mal y no hay un flujo
   "de un pulgar" para capturar datos en el piso de la fábrica.
3. **Falta de feedback y confirmación**: decenas de `except:` silenciosos hacen que el usuario
   no sepa si algo falló o se guardó.

En el tema concreto de **gastos e ingresos**, hay dos huecos funcionales importantes:

- **Gastos**: el formulario de egresos captura lo mínimo (fecha, categoría, descripción, monto,
  medio de pago). No guarda **proveedor**, **número de comprobante/factura**, **foto del recibo**
  ni **quién lo registró**. No se puede editar después, solo "anular" (y solo el Gerente, por un
  flujo incómodo).
- **Ingresos**: el único ingreso posible es un **abono/pago ligado a una orden**. No existe un
  registro de "otros ingresos" (venta en efectivo sin orden, devoluciones a favor, reembolsos,
  intereses, etc.). La tabla `movimientos_caja` existe en la base pero **no se usa en el código**.

---

## 2. Arquitectura actual

| Pieza | Detalle |
|---|---|
| Frontend | Streamlit (una sola app `App.py` que enruta por `st.radio` en el sidebar) |
| Backend/BD | Supabase (Postgres), acceso directo con `create_client` y la key `anon` |
| Autenticación | Login propio contra tabla `usuarios` (contraseña en **texto plano**) |
| Roles | `GERENTE`, `VENDEDORA`, `IMPRESION`, `DISEÑADOR` con diccionario `PERMISOS` en `App.py` |
| IA | Gemini (`gemini-2.5-flash`) solo para el mensaje de bienvenida del Inicio |
| Config | `.streamlit/secrets.toml` (no está en git; `.streamlit/` está en `.gitignore`) |
| Dependencias | `requirements.txt` **sin versiones fijadas** y con `openpyxl` duplicado |

Flujo principal (`App.py`): `login()` → `inicializar_estado()` → sidebar con `st.radio` →
`enrutador(opcion)` llama al `render(supabase)` de cada módulo.

**Inventario de módulos** (16): clientes, productos, insumos, cotizaciones, producción,
finanzas, reportes, diseño, impresión, usuarios, ventas, facturación, RH, APUs, polines y
control de taller.

---

## 3. Inventario de funciones por módulo

> Resumen de lo que hace cada módulo (a nivel de flujo de negocio).

| Módulo | Funciones principales |
|---|---|
| **ventas.py** | Venta directa con carrito (productos + metros de impresión), modalidad de pago (100% / abono / crédito), alta de cliente al vuelo, historial/auditoría de ventas `VD-*`. |
| **cotizaciones.py** | CRUD de cotizaciones y detalles, códigos auto, estados (borrador/…), PDF, alta de cliente al vuelo. |
| **produccion.py** | El más grande: gestión de órdenes de producción, estados del flujo, ítems, especificaciones (tallas, polines, nombres/dorsales), abonos, fichas de costos, borrado de órdenes. |
| **control_taller.py** | Asignación de cortador/costurera y control de avance del taller. |
| **finanzas.py** | Flujo de caja (solo Gerente), cuentas por cobrar + registro de abonos, registro de egresos, libro diario + anulación de egresos. |
| **facturacion.py** | Emisión de facturas sobre órdenes, selección de pendientes, edición de pagos, PDF. |
| **reportes.py** | Generación de PDF: comprobante de cliente, hoja de producción, etiquetas (individual y lote); trazabilidad de pagos y productos. |
| **disenador.py** | Asignación de órdenes a diseño, arte final, registro manual de archivos de impresión, edición de especificaciones. |
| **impresion.py** | Cola de impresión/plotter, estados de impresión, reimpresiones, métricas. |
| **clientes.py** | CRUD de clientes, tipos de cliente, búsqueda, importar/exportar Excel. |
| **productos.py** | CRUD de catálogo de productos, precios (unitario/docena/mayorista), flags sublimado/ticket/DTF/bordado, importar/exportar. |
| **insumos.py** | CRUD de insumos, categorías, unidades, costos, importar Excel. |
| **usuarios.py** | CRUD de usuarios, roles, alta, reseteo de contraseña, borrado. |
| **rh.py** | Empleados, asistencia biométrica (horas/extra/descuento), nómina, liquidaciones, generación de egresos `NOMINA` hacia Finanzas. |
| **apus.py** | APUs (análisis de precio unitario): receta de insumos por producto, imágenes. |
| **polines.py** | Consolidación de polines (uniformes deportivos) por talla/color/jugador. |

---

## 4. Hallazgos críticos (seguridad y datos) — atender primero

Estos no son de "UX" pero sí de confianza del usuario y de integridad contable, y deben ir antes
o junto con las mejoras de interfaz.

1. **Contraseñas en texto plano.** La columna se llama `password_hash` pero guarda la contraseña
   tal cual. `App.py:128-134` compara `eq("password_hash", pwd)`; `usuarios.py:71` y `:102` la
   escriben sin hash. → Usar hash (p. ej. `hashlib.pbkdf2_hmac` o `bcrypt`) y un campo `password_hash`
   real + `salt`.

2. **La key `anon` de Supabase viaja al navegador y no se ven políticas RLS en el volcado SQL.**
   El `Sql_Supabase.txt` dice "schema for context only". Es crítico confirmar que **todas** las
   tablas tengan RLS habilitado, porque hoy el front valida permisos por rol (`PERMISOS` en
   `App.py`) pero cualquiera con la key podría saltarse esa validación. → Revisar RLS y reforzar
   por roles reales de Postgres.

3. **Borrados físicos destructivos.** `usuarios.py:117` hace `delete()` de un usuario y
   `produccion.py:352` hace `delete()` de una orden. Esto rompe historial y trazabilidad. → Cambiar
   a borrado lógico (`activo=false` / estado "ANULADO"), como ya se hace bien en `egresos`.

4. **Sin transacciones.** Ventas (`ventas.py:902-1017`) inserta orden → ítems → archivos → pago en
   llamadas separadas; nómina (`rh.py:837-872`) inserta liquidación → egreso por empleado en un
   bucle. Si algo falla a la mitad, quedan datos inconsistentes (orden sin ítems, nómina a medias).
   → Mover a una **función RPC en Supabase** que haga todo en una transacción, o al menos validar
   y compensar.

5. **Dependencias sin versionar** (`requirements.txt`) y `openpyxl` repetido (líneas 13 y 15). →
   Fijar versiones (`==`) para reproducibilidad.

6. **`except:` / `except Exception: pass` generalizados.** Conté ~133 ocurrencias de manejo de
   error silencioso en los módulos (p. ej. `reportes.py`, `cotizaciones.py`, `produccion.py`).
   El usuario queda sin saber qué pasó. → Mínimo: `st.error(...)` con el detalle, y log.

7. **Dos acciones "falsas" que engañan al usuario (bugs funcionales, prioridad máxima).**
   - `control_taller.py:202-216`: el botón "Confirmar Asignación" muestra éxito con
     `time.sleep` + `st.success`, pero **no inserta nada en la base**. El usuario cree que envió
     el lote a costura y en realidad no se guardó.
   - `impresion.py:474`: "Completar Impresión" valida el estado **local** del editor, no la BD,
     por lo que puede finalizar con archivos que siguen "Pendiente" en la base.
   Son los peores problemas de confianza: el sistema confirma algo que no ocurrió.

8. **Race condition en generación de códigos.** `generar_codigo_vd` (`ventas.py:256-271`),
   `generar_siguiente_codigo_cot` (`cotizaciones.py:97-109`, que además lee TODA la tabla),
   `productos.py:18-36` e `insumos.py:29-41` calculan el "siguiente" número en la app. Dos usuarios
   simultáneos pueden generar el mismo código y violar el `UNIQUE`. → Usar secuencias/`identity`
   en Postgres o un contador atómico.

9. **Dinero en `float` + IVA hardcodeado al 15%.** El IVA se deriva por división
   (`total / 1.15`) en `ventas.py:188-189` y `cotizaciones.py:892-893, 546-548`. Con montos
   fraccionarios (metros de impresión) los centavos se desalinean. → Usar `Decimal`/`numeric` y
   parametrizar el % de IVA.

10. **Doble liquidación de nómina.** `rh.py:820-876` no valida unicidad `(empleado_id, mes_anio)`
    ni pide confirmación; volver a clicar "Liquidar" duplica sueldos y egresos. → `unique` +
    `upsert` + confirmación.

11. **PIN/secretos visibles.** PIN hardcodeado `"1234"` en `produccion.py:1006` y PIN de gerencia
    en `secrets.toml`. Mover secretos a variables de entorno y no dejar PINs en el código.

---

## 5. Problemas de usabilidad generales (escritorio y móvil)

1. **Todo pasa por tablas con clic en la fila.** Hay **54** usos de `st.dataframe`/`st.data_editor`,
   y los flujos clave usan `selection_mode` (`finanzas.py:226,650`, `clientes.py:75`, `productos.py:94`,
   `insumos.py:88`, `cotizaciones.py:421`, `facturacion.py:114`, `impresion.py:143`,
   `produccion.py:254-264`, `ventas.py:1086`, `reportes.py:1947-1970`). En escritorio funciona, en
   móvil es el patrón que más fricción genera.

2. **Formularios densos.** Hay **188** usos de `st.columns`/`st.form`/inputs; muchos con 4 columnas
   (`apus.py:69`, `productos.py:69,141,218`, `cotizaciones.py:439`, `disenador.py:634`, etc.). En el
   celular se aprietan o se desordenan.

3. **Falta de confirmación para acciones destructivas.** Anular egresos, borrar clientes/usuarios,
   cambiar estados: varios se ejecutan con un solo clic sin diálogo de confirmación.

4. **Sin paginación ni carga perezosa.** Muchos `select("*")` y `.limit(100)` cargan todo; a medida
   que crezca la base, el celular tardará y gastará datos.

5. **Muchas consultas por render.** Hay **182** llamadas `.execute()`; varios en bucles (p. ej.
   `usuarios.py:40-45` actualiza fila por fila; `ventas.py:956-1011` inserta ítem por ítem).
   Esto se nota más en móvil (latencia).

6. **Consistencia visual/idioma.** Mezcla de `st.header`, `st.subheader`, `st.title` sin un patrón;
   montos a veces `$ 1,234.56`, a veces `$1,234.56`; bancos repetidos a mano en cada módulo
   (lista `["JEP","Pichincha","Pacifico","Austro"]` duplicada). → Centralizar catálogos y formatos.

---

## 6. Problemas específicos en móvil

- **Layout `wide` fijo** (`App.py:33`) y sidebar oculto tras el botón hamburguesa: no hay barra de
  navegación inferior ni accesos directos, por lo que cambiar de módulo en el celular es lento.
- **Dataframes con selección de fila** son casi intocables con el dedo (fila pequeña, requiere
  precisión); tampoco hay alternativa de "tocar botón" para la acción más común.
- **Formularios de captura** (gasto, abono, cliente, producto) no están optimizados para una mano:
  sin botones de "monto rápido", sin `keyboard` numérico sugerido, sin orden de campos pensado para
  el pulgar.
- **`st.form` con `clear_on_submit`** obliga a un botón "Guardar" adicional y puede ser lento de
  re-render en móvil; la alternativa es guardar directo con `on_click` + feedback.
- **No hay PWA/instalación** ni modo offline: para un taller o un vendedor en la calle, sería ideal
  capturar gasto/ingreso aunque no haya conexión y sincronizar luego.
- **El "ping" de sesión** (`App.py:38-47`) hace `HEAD` cada 25 s; con la pantalla bloqueada el móvil
  corta la red y puede perder la sesión.

---

## 7. Enfoque prioritario: Registro de Gastos e Ingresos

### 7.1 Gastos (egresos) — hoy

El formulario (`finanzas.py:410-477`) pide: fecha, categoría, descripción, monto, medio de pago,
banco (opcional). La anulación está en "Libro Diario" (`finanzas.py:644-740`), solo para Gerente,
eligiendo la fila en una tabla.

**Lo que falta (por orden de impacto para un negocio):**

1. **Proveedor / a quién se pagó.** No existe el campo. Sin esto, no se puede responder
   "¿cuánto le pagué a X este mes?".
2. **Nº de factura/comprobante y foto del recibo.** Imposible auditar o respaldar el gasto.
3. **Quién registró el gasto.** La tabla `egresos` no tiene `registrado_por_id` (sí lo tiene
   `pagos`). Hoy no se sabe qué empleado cargó el egreso.
4. **Editar un gasto** (corregir monto/descripción) en lugar de solo anular y volver a cargar.
5. **Categoría libre vs. catálogo.** `egresos.categoria` es texto libre y `categorias_egreso` no
   tiene FK. Dos usuarios pueden escribir "Nómina" y "Nomina" como categorías distintas.
6. **Gastos recurrentes/plantillas** (arriendo, sueldos fijos, luz) para capturarlos en 2 toques.
7. **Exportar** el listado de egresos a Excel/PDF desde Finanzas.
8. **Detección de duplicados** más fuerte que "últimos 10 registros" (mismo monto + misma descripción
   + mismo día → aviso).

### 7.2 Ingresos — hoy

Solo existen **abonos/pagos ligados a una orden** (`pagos`), cargados desde Ventas (abono inicial,
`ventas.py:1000-1011`) o desde Cuentas por Cobrar (`finanzas.py:312-400`).

**Lo que falta:**

1. **"Otros ingresos"** (no ligados a orden): venta en efectivo menor, devoluciones a favor,
   reembolsos de proveedores, intereses. La tabla `movimientos_caja` (tipo + categoría + monto)
   ya existe en el SQL (`Sql_Supabase.txt:192-202`) pero **no se usa en el código**. → Reactivarla
   como caja general o unificarla con `egresos` en una sola tabla de "movimientos".
2. **Registro rápido de ingreso** en celular: botón grande "➕ Ingreso" con monto, categoría, medio
   de pago y foto opcional.
3. **Conciliación por medio de pago** (cuánto entró por efectivo vs transferencia vs tarjeta por día),
   hoy solo se ve el total.
4. **Cuadre de caja real** (efectivo físico vs. registrado) para detectar faltantes/sobrantes.

### 7.3 Esquema de datos sugerido para gastos/ingresos

Una propuesta mínima y de bajo riesgo (migraciones aditivas):

- **`egresos`**: agregar `proveedor text`, `numero_comprobante text`, `registrado_por_id bigint`,
  `url_comprobante text`, `editado boolean`, `motivo_edicion text`. Añadir FK `categoria`
  → `categorias_egreso(nombre)` o, mejor, `categoria_id`.
- **`pagos`**: ya tiene `registrado_por_id`; solo falta **rellenarlo** en `finanzas.py:324-338` y
  `ventas.py:1001-1011` con `st.session_state["id_usuario"]`.
- **Reactivar `movimientos_caja`** (o crear `ingresos_extra`) con: `id`, `tipo` (INGRESO/EGRESO),
  `categoria`, `monto`, `fecha`, `metodo_pago`, `banco`, `descripcion`, `numero_comprobante`,
  `registrado_por_id`, `anulado`, `created_at`. Que Finanzas sea el único dueño de esta caja general.

---

## 8. Plan de mejoras priorizado

### P0 — Críticos (seguridad e integridad, base para todo lo demás)
1. **Corregir los dos botones "falsos"** (`control_taller.py:202-216` y `impresion.py:474`):
   que la acción realmente persista en BD y que la validación se haga contra la BD.
2. Hash de contraseñas + sal (`usuarios` + `App.py` login); no exponer `password_hash` en selects.
3. Verificar/activar RLS en Supabase para todas las tablas (y `polines.py` sin gate de rol).
4. Eliminar borrados físicos (`usuarios.py:117`, `produccion.py:352`, `clientes.py:211-215`,
   `ventas.py:1198`, `cotizaciones.py:564`, `facturacion.py` delete+insert de pagos) → borrado lógico.
5. Transacciones vía RPC para venta, abono y nómina; `unique`+`upsert` en `rh_liquidaciones`
   para impedir doble liquidación.
6. Códigos con secuencia/contador atómico (ventas, cotizaciones, productos, insumos) y
   retirar el PIN `"1234"` del código.

### P1 — Móvil y registro de gastos/ingresos (lo que pediste)
5. **Registro de egreso rediseñado** para celular:
   - Un solo formulario vertical, campos grandes, teclado numérico para monto.
   - Botones de montos rápidos ($1, $2, $5, $10, $20, $50, $100).
   - Campo **proveedor**, **Nº comprobante** y **foto del recibo** (subir a Storage de Supabase).
   - Autocompletar categoría (selector con búsqueda), guardar "última categoría usada".
   - Feedback claro al guardar + opción "registrar otro".
6. **Registro de "otro ingreso"** con el mismo patrón (reactivar `movimientos_caja`).
7. **Reemplazar la selección por fila por botones de acción** en los flujos más usados en móvil:
   - Cuentas por Cobrar: tarjetas/listas con botón "💰 Cobrar" en vez de clic en tabla.
   - Libro Diario: botón "🚫 Anular" por registro.
8. **Barra de navegación adaptada a móvil**: mantener sidebar en escritorio, pero en móvil usar
   `st.navigation`/pestañas grandes o un menú inferior con accesos rápidos (Inicio, Cobrar, Gasto,
   Ventas).
9. **Cuadre de caja por medio de pago** (efectivo vs transferencia vs tarjeta) y **detector de
   duplicados** de egresos.

### P2 — Consistencia y rendimiento
10. Centralizar catálogos (bancos, categorías de egreso, estados) en un único módulo/constantes.
11. Paginar listados y reducir consultas N+1 (batches, `.in_()`, RPC).
12. Reemplazar `except: pass` por manejo visible (`st.error`) + log.
13. Fijar versiones en `requirements.txt` (quitar `openpyxl` duplicado).
14. Unificar formato de moneda/fechas con `st.column_config` en todas las tablas.
15. Evaluar PWA/offline para captura de gastos/ingresos en calle (fase 2).

---

## 9. Roadmap sugerido

| Fase | Alcance | Resultado esperado |
|---|---|---|
| 1 (1–2 días) | P0 completo (hash, RLS, borrado lógico, RPC de venta/abono/nómina) | Sistema seguro y consistente |
| 2 (3–5 días) | P1: rediseño de Gasto + Otro ingreso + botones de acción en Finanzas + navegación móvil | Celular usable para cobrar y registrar gastos/ingresos |
| 3 (1 semana) | P2: catálogos centralizados, paginación, feedback de errores, versiones | Menos errores, más rápido, mantenible |

---

## 10. Nota sobre el alcance de esta revisión

Se revisaron a fondo los archivos centrales (`App.py`, `config.py`, `Sql_Supabase.txt`,
`finanzas.py`, `usuarios.py`, y secciones clave de `ventas.py`, `rh.py` y `reportes.py`), y se
cuantificaron patrones transversales en los 16 módulos (tablas interactivas, formularios,
manejo de errores, consultas). Si quieres, en el siguiente paso puedo entregar el desglose
línea por línea de los 3 módulos más grandes (`produccion.py`, `disenador.py`, `reportes.py`) o
empezar a implementar la **Fase 1** y el **rediseño del módulo de Gastos/Ingresos**.
