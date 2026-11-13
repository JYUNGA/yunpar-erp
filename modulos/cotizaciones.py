import streamlit as st
import pandas as pd
import datetime
import time
import urllib.parse
import os
import qrcode
import tempfile
import uuid
import mimetypes
import requests
from fpdf import FPDF
from num2words import num2words
from config import OrderState, transicionar_estado



def _inyectar_estilos_responsive():
    """Ajustes visuales para escritorio y, sobre todo, celular."""
    st.markdown(
        """
        <style>
        html { scroll-behavior: smooth; }

        [data-testid="stAppViewContainer"] {
            overflow-x: hidden;
        }

        [data-testid="stMainBlockContainer"] {
            max-width: 1320px;
            padding-top: 1.6rem;
            padding-bottom: 4rem;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: .25rem;
            overflow-x: auto !important;
            overflow-y: hidden !important;
            flex-wrap: nowrap !important;
            scrollbar-width: none;
            -ms-overflow-style: none;
            padding-bottom: .15rem;
        }

        .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar {
            display: none;
        }

        .stTabs [data-baseweb="tab"] {
            flex: 0 0 auto !important;
            white-space: nowrap !important;
            min-width: max-content !important;
            padding-left: .65rem !important;
            padding-right: .65rem !important;
        }

        .stButton > button,
        .stDownloadButton > button,
        [data-testid="stLinkButton"] a {
            border-radius: 11px !important;
            min-height: 42px;
        }

        [data-testid="stImage"] img {
            border-radius: 14px;
            object-fit: contain;
        }

        [data-testid="stAlert"] {
            border-radius: 14px;
        }

        @media (max-width: 700px) {
            [data-testid="stMainBlockContainer"] {
                max-width: 100% !important;
                padding: .75rem .7rem 4.5rem !important;
            }

            h1 {
                font-size: 1.65rem !important;
                line-height: 1.12 !important;
                margin-bottom: .6rem !important;
            }

            h2 {
                font-size: 1.35rem !important;
                line-height: 1.15 !important;
            }

            h3 {
                font-size: 1.18rem !important;
                line-height: 1.2 !important;
            }

            h4 {
                font-size: 1.04rem !important;
                line-height: 1.2 !important;
            }

            p, label, .stCaption {
                line-height: 1.4 !important;
            }

            [data-testid="stHorizontalBlock"] {
                flex-direction: column !important;
                gap: .55rem !important;
            }

            [data-testid="column"] {
                width: 100% !important;
                flex: 1 1 100% !important;
                min-width: 0 !important;
            }

            .stButton > button,
            .stDownloadButton > button,
            [data-testid="stLinkButton"] a {
                width: 100% !important;
                min-height: 46px !important;
                font-size: .90rem !important;
            }

            .stTabs [data-baseweb="tab-list"] {
                width: 100% !important;
                gap: .12rem !important;
                scroll-snap-type: x proximity;
            }

            .stTabs [data-baseweb="tab"] {
                scroll-snap-align: start;
                font-size: .82rem !important;
                padding: .45rem .48rem !important;
            }

            [data-baseweb="select"],
            [data-baseweb="input"],
            textarea,
            input {
                max-width: 100% !important;
            }

            [data-testid="stDataFrame"],
            [data-testid="stDataEditor"] {
                max-width: 100% !important;
                overflow-x: auto !important;
                border-radius: 12px;
            }

            [data-testid="stImage"] {
                width: 100% !important;
            }

            [data-testid="stImage"] img {
                max-width: 100% !important;
                height: auto !important;
                max-height: 520px !important;
                object-fit: contain !important;
            }

            [data-testid="stVerticalBlock"] {
                gap: .72rem !important;
            }

            hr {
                margin: 1rem 0 !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _dia_rerun_local():
    """Rerun solo del fragmento cuando sea posible para no mandar el scroll arriba."""
    try:
        st.rerun(scope="fragment")
    except Exception:
        st.rerun()


# --- CLASE PDF CON PLANTILLA VISUAL ---
class PDFCotizacion(FPDF):
    def __init__(self, datos_cabecera=None, ruta_fondo=None):
        super().__init__()
        self.datos_cabecera = datos_cabecera
        self.ruta_fondo = ruta_fondo

    def header(self):
        # 1. FONDO (Carga directa, sin procesamientos lentos)
        if self.ruta_fondo and os.path.exists(self.ruta_fondo):
            self.image(self.ruta_fondo, x=0, y=0, w=210, h=297)

        # 2. LLENADO DE DATOS
        if self.datos_cabecera:
            self.set_font("Arial", "B", 10)
            self.set_text_color(60, 60, 60)

            # N° Cotización
            self.set_xy(68, 78)
            self.cell(40, 5, self.datos_cabecera.get("codigo", ""), 0, 0, "L")

            # Cliente
            self.set_xy(80, 86)
            self.cell(
                90,
                5,
                limpiar_texto_pdf(self.datos_cabecera.get("cliente_nombre", "")),
                0,
                0,
                "L",
            )

            # Fecha
            self.set_xy(78, 92)
            self.cell(40, 5, self.datos_cabecera.get("fecha", ""), 0, 0, "L")

            # Contacto/Teléfono
            self.set_xy(161, 85)
            self.cell(50, 5, self.datos_cabecera.get("telefono", ""), 0, 0, "L")

            # Cliente Tipo
            self.set_xy(160, 93)
            self.set_font("Arial", "", 9)
            tipo = self.datos_cabecera.get("tipo", "")
            self.cell(38, 5, limpiar_texto_pdf(tipo[:18]), 0, 0, "C")

        # 3. MÁRGENES DE TABLA
        self.set_y(105)
        self.set_left_margin(52)
        self.set_right_margin(10)

    def footer(self):
        self.set_y(-10)
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", "", 7)
        self.cell(0, 10, f"Pag {self.page_no()}", 0, 0, "R")


# --- FUNCIONES AUXILIARES ---
def limpiar_texto_pdf(texto):
    if not texto:
        return ""
    reemplazos = {
        "│": "|",
        "–": "-",
        "“": '"',
        "”": '"',
        "’": "'",
        "‘": "'",
        "Ñ": "N",
        "ñ": "n",
        "°": " degrees",
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
    }
    t = str(texto)
    for k, v in reemplazos.items():
        t = t.replace(k, v)
    return t.encode("latin-1", "replace").decode("latin-1")


def generar_siguiente_codigo_cot(supabase):
    try:
        resp = supabase.table("cotizaciones").select("codigo_cotizacion").execute()
        codigos = [d["codigo_cotizacion"] for d in resp.data]
        max_num = 0
        for c in codigos:
            if c.startswith("COT-") and c[4:].isdigit():
                num = int(c[4:])
                if num > max_num:
                    max_num = num
        return f"COT-{str(max_num + 1).zfill(4)}"
    except:
        return "COT-0001"


def generar_pdf_final(cabecera, items, observaciones, vigencia_fecha, total_letras):
    ruta_fondo = "PROFORMA.png"
    pdf = PDFCotizacion(datos_cabecera=cabecera, ruta_fondo=ruta_fondo)
    pdf.add_page()

    pdf.set_fill_color(245, 166, 35)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 9)

    w_cod, w_desc, w_cant, w_unit, w_tot = 18, 65, 15, 18, 20

    pdf.cell(w_cod, 8, "Codigo", 1, 0, "C", True)
    pdf.cell(w_desc, 8, "Descripcion", 1, 0, "C", True)
    pdf.cell(w_cant, 8, "Cant", 1, 0, "C", True)
    pdf.cell(w_unit, 8, "P.Unit", 1, 0, "C", True)
    pdf.cell(w_tot, 8, "Total", 1, 1, "C", True)
    pdf.ln(8)

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "", 9)

    qr_data_string = f"COT: {cabecera['codigo']}\nCLIENTE: {cabecera['cliente_nombre']}\nTOTAL: ${cabecera['total']:.2f}\n"

    for item in items:
        x_start, y_start = pdf.get_x(), pdf.get_y()
        desc = limpiar_texto_pdf(item["descripcion"])
        pdf.set_xy(x_start + w_cod, y_start)
        pdf.multi_cell(w_desc, 6, desc, 0, "L")
        row_height = max(8, pdf.get_y() - y_start)

        pdf.set_xy(x_start, y_start)
        pdf.cell(w_cod, row_height, limpiar_texto_pdf(str(item["codigo"])), 0, 0, "C")

        cx, cy = pdf.get_x(), pdf.get_y()
        pdf.multi_cell(w_desc, 6, desc, 0, "L")
        pdf.set_xy(cx + w_desc, cy)

        c_txt = (
            f"{int(item['cantidad'])}"
            if item["cantidad"] % 1 == 0
            else f"{item['cantidad']:.2f}"
        )
        pdf.cell(w_cant, row_height, c_txt, 0, 0, "C")
        pdf.cell(w_unit, row_height, f"${float(item['precio']):.2f}", 0, 0, "R")
        pdf.cell(w_tot, row_height, f"${float(item['subtotal']):.2f}", 0, 1, "R")

        pdf.set_draw_color(220, 220, 220)
        pdf.line(
            52, pdf.get_y(), 52 + w_cod + w_desc + w_cant + w_unit + w_tot, pdf.get_y()
        )
        pdf.set_draw_color(0, 0, 0)
        qr_data_string += f"- {item['codigo']} ({c_txt})\n"

    pdf.ln(5)
    y = pdf.get_y()
    if y > 230:
        pdf.add_page()
        y = pdf.get_y()

    pdf.set_xy(52, y)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(10, 5, "SON:", 0, 0)
    pdf.set_font("Arial", "I", 8)
    pdf.multi_cell(110, 5, limpiar_texto_pdf(total_letras), 0)

    x_totales = 140
    pdf.set_xy(x_totales, y)
    pdf.set_font("Arial", "", 10)
    pdf.cell(20, 5, "Subtotal:", 0, 0, "R")
    pdf.cell(25, 5, f"${float(cabecera['subtotal']):.2f}", 0, 1, "R")
    pdf.set_x(x_totales)
    pdf.cell(20, 5, "IVA (15%):", 0, 0, "R")
    pdf.cell(25, 5, f"${float(cabecera['iva']):.2f}", 0, 1, "R")
    pdf.set_x(x_totales)
    pdf.set_font("Arial", "B", 12)
    pdf.set_text_color(18, 38, 122)
    pdf.cell(20, 8, "TOTAL:", 0, 0, "R")
    pdf.cell(25, 8, f"${float(cabecera['total']):.2f}", 0, 1, "R")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)

    if observaciones:
        pdf.set_x(52)
        pdf.set_font("Arial", "B", 9)
        pdf.cell(0, 6, "OBSERVACIONES / CONDICIONES:", 0, 1)
        pdf.set_x(52)
        pdf.set_font("Arial", "", 8)
        pdf.multi_cell(140, 5, limpiar_texto_pdf(observaciones), 1)
        pdf.ln(3)

    pdf.set_x(52)
    pdf.set_font("Arial", "I", 9)
    pdf.set_text_color(200, 0, 0)
    pdf.cell(0, 6, f"Oferta valida hasta: {vigencia_fecha}", 0, 1)
    pdf.set_text_color(0, 0, 0)

    qr = qrcode.QRCode(version=1, box_size=5, border=1)
    try:
        qr.add_data(qr_data_string.encode("utf-8").decode("latin-1"))
    except:
        qr.add_data("Datos Cotizacion")
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white")
    temp_qr_path = tempfile.mktemp(suffix=".png")
    img_qr.save(temp_qr_path)
    pdf.image(temp_qr_path, x=52, y=pdf.get_y() + 2, w=25)

    pdf.set_xy(75, pdf.get_y() + 7)
    pdf.set_font("Arial", "", 7)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(65, 4, "Escanea para verificar\ndetalles originales.", 0, "L")
    pdf.set_text_color(0, 0, 0)

    pos_firma = 258
    if pdf.get_y() > 240:
        pdf.add_page()
    pdf.set_y(pos_firma)
    pdf.set_font("Arial", "", 8)
    pdf.set_xy(55, pos_firma)
    pdf.cell(50, 0, "_______________________", 0, 1, "C")
    pdf.set_xy(55, pos_firma)
    pdf.cell(50, 5, "Dpto. Ventas", 0, 0, "C")
    pdf.set_xy(120, pos_firma)
    pdf.cell(50, 0, "_______________________", 0, 1, "C")
    pdf.set_xy(120, pos_firma)
    pdf.cell(50, 5, "Cliente Conforme", 0, 1, "C")
    pdf.set_xy(120, pos_firma + 4)
    pdf.set_font("Arial", "B", 7)
    pdf.cell(50, 5, limpiar_texto_pdf(cabecera["cliente_nombre"][:30]), 0, 1, "C")

    # CORRECCIÓN: fpdf moderno ya devuelve un bytearray.
    # Solo lo casteamos a bytes para compatibilidad estricta con st.download_button
    return bytes(pdf.output())



# --- DISEÑO CON IA (PRODUCCIÓN / SUPABASE) ---
_DIA_TABLE = "disenos_ia_ventas"
_DIA_BUCKET = "ordenes_produccion"


def _dia_now_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _dia_api_key_gemini():
    try:
        return st.secrets["gemini"]["api_key"]
    except Exception:
        return None


def _dia_tabla_disponible(supabase):
    try:
        supabase.table(_DIA_TABLE).select("id").limit(1).execute()
        return True, None
    except Exception as e:
        return False, str(e)


def _dia_codigo_siguiente(supabase):
    try:
        res = (
            supabase.table(_DIA_TABLE)
            .select("codigo")
            .order("id", desc=True)
            .limit(1)
            .execute()
        )
        if res.data:
            ultimo = str(res.data[0].get("codigo") or "")
            if ultimo.startswith("DIA-") and ultimo[4:].isdigit():
                return f"DIA-{int(ultimo[4:]) + 1:04d}"
    except Exception:
        pass
    return f"DIA-{int(time.time()) % 100000:05d}"


def _dia_codigo_orden(supabase):
    try:
        res = (
            supabase.table("ordenes")
            .select("codigo_orden")
            .ilike("codigo_orden", "ORD-%")
            .order("codigo_orden", desc=True)
            .limit(1)
            .execute()
        )
        if res.data:
            ultimo = str(res.data[0].get("codigo_orden") or "")
            if ultimo.startswith("ORD-") and ultimo[4:].isdigit():
                return f"ORD-{int(ultimo[4:]) + 1:04d}"
    except Exception:
        pass
    return f"ORD-{int(time.time())}"


def _dia_extension_mime(mime):
    mime = (mime or "image/png").lower()
    if "webp" in mime:
        return ".webp"
    if "jpeg" in mime or "jpg" in mime:
        return ".jpg"
    return ".png"


def _dia_subir_bytes(supabase, contenido, mime, carpeta, nombre_base):
    if not contenido:
        return None
    ext = _dia_extension_mime(mime)
    ruta = f"{carpeta}/{nombre_base}_{uuid.uuid4().hex[:10]}{ext}"
    supabase.storage.from_(_DIA_BUCKET).upload(
        path=ruta,
        file=bytes(contenido),
        file_options={"content-type": mime or "image/png"},
    )
    return supabase.storage.from_(_DIA_BUCKET).get_public_url(ruta)


def _dia_descargar_imagen(url):
    if not url or not str(url).lower().startswith(("http://", "https://")):
        return None, None
    try:
        resp = requests.get(str(url), timeout=12)
        resp.raise_for_status()
        mime = (resp.headers.get("content-type") or "").split(";")[0].strip()
        if mime and not mime.startswith("image/"):
            return None, None
        return bytes(resp.content), mime or "image/png"
    except Exception:
        return None, None


def _dia_generar_imagen_gemini(registro):
    """Genera la propuesta comercial con Gemini. El arte técnico sigue a cargo del diseñador."""
    import base64
    import io

    try:
        from google import genai
        from PIL import Image
    except Exception as e:
        raise RuntimeError(
            "Faltan dependencias para Gemini/Pillow. Instale 'google-genai' y 'Pillow'. "
            f"Detalle: {e}"
        )

    api_key = _dia_api_key_gemini()
    if not api_key:
        raise RuntimeError("No se encontró [gemini][api_key] en .streamlit/secrets.toml.")

    producto = registro.get("producto") or registro.get("producto_descripcion") or "Prenda por definir"
    tecnica = registro.get("tecnica") or "Por definir"
    colores = registro.get("colores") or "No especificados"
    brief = registro.get("instrucciones") or ""
    ajuste = registro.get("ajuste_solicitado") or ""

    prompt = f"""
Crea UNA propuesta visual profesional para presentar a un cliente de una empresa de confección.

OBJETIVO:
Generar un mockup de una prenda terminada que sirva como PROPUESTA COMERCIAL para aprobación del cliente.
No es un arte técnico definitivo para impresión; el diseñador humano hará luego la preparación de producción.

PRENDA / REFERENCIA DE PRODUCTO:
{producto}

TÉCNICA PREVISTA:
{tecnica}

COLORES SOLICITADOS:
{colores}

BRIEF DEL CLIENTE:
{brief}

AJUSTE DE LA REVISIÓN ACTUAL:
{ajuste if ajuste else 'Sin ajustes adicionales.'}

REGLAS IMPORTANTES:
- Usa la imagen de referencia del cliente como guía principal cuando esté disponible.
- Conserva los elementos esenciales solicitados por el cliente.
- No inventes texto legible, nombres, marcas o escudos nuevos que no estén en la referencia o en el brief.
- Muestra solamente una prenda terminada, sin persona y sin maniquí visible.
- Vista frontal clara y comercial.
- Fondo blanco limpio.
- Iluminación de estudio.
- Producto centrado y completamente visible.
- Estética profesional de catálogo.
- No hagas collage.
- No muestres varias opciones en una misma imagen.
- Mantén coherencia de colores, logotipo/escudo y composición con la referencia.

Genera solamente la imagen de la propuesta visual.
""".strip()

    contenido = [{"type": "text", "text": prompt}]

    ref_bytes = registro.get("referencia_bytes")
    ref_mime = registro.get("referencia_tipo") or "image/png"
    if not ref_bytes:
        ref_bytes, ref_mime_desc = _dia_descargar_imagen(
            registro.get("referencia_url") or registro.get("referencia_link")
        )
        if ref_mime_desc:
            ref_mime = ref_mime_desc

    if ref_bytes:
        contenido.append(
            {
                "type": "image",
                "data": base64.b64encode(ref_bytes).decode("utf-8"),
                "mime_type": ref_mime,
            }
        )

    cliente = genai.Client(api_key=api_key)
    interaction = cliente.interactions.create(
        model="gemini-nano-banana-2.1",
        input=contenido,
        response_format={"type": "image", "aspect_ratio": "4:5"},
    )

    if interaction is None or interaction.output_image is None:
        raise RuntimeError("Gemini respondió sin devolver una imagen.")

    salida = interaction.output_image.data
    if not salida:
        raise RuntimeError("Gemini devolvió una imagen vacía.")
    if isinstance(salida, str):
        salida = base64.b64decode(salida)
    salida = bytes(salida)

    try:
        img = Image.open(io.BytesIO(salida))
        formato = (img.format or "PNG").upper()
        img.verify()
    except Exception as e:
        raise RuntimeError(f"La respuesta de Gemini no parece una imagen válida: {e}")

    mime = {
        "PNG": "image/png",
        "JPEG": "image/jpeg",
        "JPG": "image/jpeg",
        "WEBP": "image/webp",
    }.get(formato, "image/png")
    return salida, mime


def _dia_cargar_registros(supabase):
    try:
        return (
            supabase.table(_DIA_TABLE)
            .select("*")
            .order("created_at", desc=True)
            .limit(100)
            .execute()
            .data
            or []
        )
    except Exception:
        return []


def _dia_buscar_registro_db(supabase, codigo):
    try:
        res = (
            supabase.table(_DIA_TABLE)
            .select("*")
            .eq("codigo", codigo)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception:
        return None


def _dia_actualizar(supabase, registro_id, datos):
    payload = dict(datos)
    payload["updated_at"] = _dia_now_iso()
    return supabase.table(_DIA_TABLE).update(payload).eq("id", int(registro_id)).execute()


def _dia_limpiar_formulario():
    for key in [
        "dia_cliente",
        "dia_producto",
        "dia_tecnica",
        "dia_colores",
        "dia_ref_link",
        "dia_instrucciones",
        "dia_ref_img",
        "dia_fecha_entrega",
    ]:
        st.session_state.pop(key, None)
    st.session_state.pop("_diseno_ia_actual", None)


def _dia_crear_orden_para_disenador(supabase, registro, productos):
    if registro.get("orden_id"):
        return int(registro["orden_id"]), None

    codigo_orden = _dia_codigo_orden(supabase)
    prod_obj = next(
        (p for p in productos if p.get("id") == registro.get("producto_id")),
        None,
    )
    precio = float((prod_obj or {}).get("precio_unitario") or 0)

    observaciones = [
        f"DISEÑO IA: {registro.get('codigo')}",
        f"Técnica: {registro.get('tecnica') or 'Por definir'}",
        f"Colores: {registro.get('colores') or 'No especificados'}",
        f"Brief: {registro.get('instrucciones') or ''}",
    ]
    if registro.get("ajuste_solicitado"):
        observaciones.append(f"Último ajuste: {registro.get('ajuste_solicitado')}")
    if registro.get("referencia_link"):
        observaciones.append(f"Enlace externo: {registro.get('referencia_link')}")

    fecha_entrega = registro.get("fecha_entrega_estimada") or (
        datetime.date.today() + datetime.timedelta(days=7)
    ).isoformat()

    data_orden = {
        "codigo_orden": codigo_orden,
        "cliente_id": registro.get("cliente_id"),
        "fecha_entrega": str(fecha_entrega),
        "creado_por_id": st.session_state.get("id_usuario"),
        "estado": "PENDIENTE DISEÑO",
        "total_estimado": precio,
        "observaciones_generales": " | ".join(observaciones),
        "url_boceto_vendedora": registro.get("propuesta_url"),
        "alerta_cambios": False,
    }
    res = supabase.table("ordenes").insert(data_orden).execute()
    if not res.data:
        raise RuntimeError("Supabase no devolvió la orden creada.")
    orden_id = int(res.data[0]["id"])

    # Trazabilidad igual que el resto del ERP.
    try:
        transicionar_estado(
            supabase,
            orden_id,
            OrderState.PENDIENTE,
            st.session_state.get("id_usuario"),
            notas=f"Creación desde Diseño IA {registro.get('codigo')}",
        )
    except Exception:
        # La orden ya está creada; un fallo de historial no debe bloquear el flujo comercial.
        pass

    if prod_obj:
        supabase.table("items_orden").insert(
            {
                "orden_id": orden_id,
                "producto_id": prod_obj.get("id"),
                "familia_producto": prod_obj.get("tipo_prenda") or prod_obj.get("descripcion"),
                "descripcion_item": prod_obj.get("descripcion"),
                "cantidad_total": 1,
                "precio_aplicado": precio,
            }
        ).execute()

    return orden_id, codigo_orden


@st.fragment
def _render_diseno_ia(supabase):
    """Diseño IA integrado con Supabase y el módulo Diseño."""
    st.subheader("🎨 Diseño con IA")
    st.caption(
        "Referencia del cliente → propuesta IA → ajustes → aprobación → diseñador → cotización."
    )

    tabla_ok, error_tabla = _dia_tabla_disponible(supabase)
    if not tabla_ok:
        st.info(
            "✅ Módulo Diseño IA listo para integración. "
            "La persistencia definitiva será activada por el ingeniero ejecutando "
            "sql/disenos_ia_ventas.sql en Supabase. "
            "Después de esa activación, este flujo se habilitará automáticamente."
        )
        with st.expander("🔧 Información para integración"):
            st.markdown(
                "**Pendiente del ingeniero:** ejecutar una sola vez "
                "`sql/disenos_ia_ventas.sql` en Supabase y recargar YUNPAR."
            )
            if error_tabla:
                st.caption("Detalle técnico detectado:")
                st.code(error_tabla)
        return

    try:
        clientes = supabase.table("clientes").select("*").execute().data or []
    except Exception as e:
        st.error(f"No se pudieron cargar los clientes: {e}")
        return
    mapa_clientes = {
        f"{c.get('nombre_completo', 'SIN NOMBRE')} | {c.get('cedula_ruc', '')}": c
        for c in clientes
    }

    try:
        productos = (
            supabase.table("productos_catalogo")
            .select("*")
            .eq("activo", True)
            .execute()
            .data
            or []
        )
    except Exception as e:
        st.error(f"No se pudieron cargar los productos: {e}")
        return
    mapa_productos = {
        f"{p.get('codigo_referencia', '')} | {p.get('descripcion', '')}": p
        for p in productos
    }

    cab1, cab2 = st.columns([5, 1])
    cab1.markdown("#### 1️⃣ Datos del cliente y referencia")
    if cab2.button("🆕 Nueva", use_container_width=True, key="dia_nueva_propuesta"):
        _dia_limpiar_formulario()
        _dia_rerun_local()

    c1, c2 = st.columns(2)
    with c1:
        sel_cliente = st.selectbox(
            "Cliente *", [""] + list(mapa_clientes.keys()), key="dia_cliente"
        )
        sel_producto = st.selectbox(
            "Prenda / producto de referencia",
            ["Sin definir"] + list(mapa_productos.keys()),
            key="dia_producto",
        )
        tecnica = st.selectbox(
            "Técnica prevista",
            ["Por definir", "Sublimado", "DTF", "Bordado", "Mixto"],
            key="dia_tecnica",
        )
        colores = st.text_input(
            "Colores solicitados",
            placeholder="Ej: azul marino, dorado y blanco",
            key="dia_colores",
        )
        fecha_entrega = st.date_input(
            "Fecha estimada de entrega",
            value=datetime.date.today() + datetime.timedelta(days=7),
            key="dia_fecha_entrega",
        )

    with c2:
        ref_img = st.file_uploader(
            "📷 Imagen enviada por el cliente",
            type=["png", "jpg", "jpeg", "webp"],
            key="dia_ref_img",
        )
        ref_link = st.text_input(
            "🔗 Enlace de referencia (opcional)",
            placeholder="https://...",
            key="dia_ref_link",
        )
        if ref_img is not None:
            st.image(ref_img, caption="Referencia cargada", use_container_width=True)

    instrucciones = st.text_area(
        "✍️ ¿Qué desea el cliente? *",
        placeholder=(
            "Ej: conservar el escudo, usar azul oscuro, agregar líneas doradas "
            "y dejar espacio para número y apellido."
        ),
        height=120,
        key="dia_instrucciones",
    )

    st.markdown("#### 2️⃣ Preparar propuesta")
    api_ok = bool(_dia_api_key_gemini())
    if api_ok:
        st.caption("✅ Gemini listo para generar la propuesta visual.")
    else:
        st.error("Gemini no está configurado. Agregue [gemini][api_key] en secrets.toml.")

    if st.button(
        "✨ PREPARAR PROPUESTA CON IA",
        type="primary",
        use_container_width=True,
        key="dia_generar",
        disabled=not api_ok,
    ):
        errores = []
        if not sel_cliente:
            errores.append("selecciona un cliente")
        if ref_img is None and not ref_link.strip():
            errores.append("sube una imagen o agrega un enlace de referencia")
        if not instrucciones.strip():
            errores.append("escribe las indicaciones del cliente")

        if errores:
            st.error("Antes de continuar: " + "; ".join(errores) + ".")
        else:
            cliente = mapa_clientes[sel_cliente]
            prod = mapa_productos.get(sel_producto) if sel_producto != "Sin definir" else None
            codigo = _dia_codigo_siguiente(supabase)
            registro_local = {
                "codigo": codigo,
                "cliente_id": cliente.get("id"),
                "cliente": cliente.get("nombre_completo", ""),
                "producto_id": prod.get("id") if prod else None,
                "producto": (
                    f"{prod.get('codigo_referencia', '')} | {prod.get('descripcion', '')}"
                    if prod else "Sin definir"
                ),
                "tecnica": tecnica,
                "colores": colores.strip(),
                "instrucciones": instrucciones.strip(),
                "referencia_link": ref_link.strip(),
                "referencia_bytes": ref_img.getvalue() if ref_img is not None else None,
                "referencia_tipo": ref_img.type if ref_img is not None else None,
                "ajuste_solicitado": "",
            }

            try:
                with st.spinner("Gemini está preparando la propuesta visual..."):
                    propuesta_bytes, propuesta_mime = _dia_generar_imagen_gemini(registro_local)

                referencia_url = None
                if ref_img is not None:
                    referencia_url = _dia_subir_bytes(
                        supabase,
                        ref_img.getvalue(),
                        ref_img.type or "image/png",
                        f"disenos-ia/{codigo}",
                        "referencia",
                    )

                propuesta_url = _dia_subir_bytes(
                    supabase,
                    propuesta_bytes,
                    propuesta_mime,
                    f"disenos-ia/{codigo}",
                    "propuesta_r1",
                )

                payload = {
                    "codigo": codigo,
                    "cliente_id": cliente.get("id"),
                    "cliente_nombre": cliente.get("nombre_completo", ""),
                    "producto_id": prod.get("id") if prod else None,
                    "producto_codigo": prod.get("codigo_referencia") if prod else None,
                    "producto_descripcion": prod.get("descripcion") if prod else "Sin definir",
                    "tecnica": tecnica,
                    "colores": colores.strip(),
                    "instrucciones": instrucciones.strip(),
                    "referencia_url": referencia_url,
                    "referencia_link": ref_link.strip() or None,
                    "propuesta_url": propuesta_url,
                    "generacion_real": True,
                    "estado": "PROPUESTA PREPARADA",
                    "revision": 1,
                    "ajuste_solicitado": "",
                    "fecha_entrega_estimada": str(fecha_entrega),
                    "creado_por_id": st.session_state.get("id_usuario"),
                    "updated_at": _dia_now_iso(),
                }
                ins = supabase.table(_DIA_TABLE).insert(payload).execute()
                if not ins.data:
                    raise RuntimeError("No se pudo registrar la propuesta en Supabase.")

                st.session_state["_diseno_ia_actual"] = codigo
                st.success(f"{codigo} creado y guardado correctamente.")
                _dia_rerun_local()
            except Exception as e:
                st.error(f"No se pudo preparar la propuesta: {e}")

    registros = _dia_cargar_registros(supabase)
    if not registros:
        st.caption("Aún no hay propuestas registradas.")
        return

    st.markdown("#### 3️⃣ Revisión con el cliente")
    codigos = [r.get("codigo") for r in registros if r.get("codigo")]
    actual = st.session_state.get("_diseno_ia_actual")
    idx_actual = codigos.index(actual) if actual in codigos else 0
    codigo_sel = st.selectbox(
        "Propuesta activa", codigos, index=idx_actual, key="dia_propuesta_activa"
    )
    st.session_state["_diseno_ia_actual"] = codigo_sel
    registro = _dia_buscar_registro_db(supabase, codigo_sel)
    if not registro:
        st.warning("No se pudo cargar la propuesta seleccionada.")
        return

    estado_actual = registro.get("estado") or "PROPUESTA PREPARADA"
    estado_icono = {
        "PROPUESTA PREPARADA": "🟡",
        "AJUSTES SOLICITADOS": "🟠",
        "PROPUESTA REGENERADA": "🟣",
        "APROBADO POR CLIENTE": "🟢",
        "ENVIADO A DISEÑADOR": "🔵",
    }.get(estado_actual, "⚪")
    st.markdown(f"### {estado_icono} {registro.get('codigo')} — {estado_actual}")

    vista1, vista2 = st.columns(2)
    with vista1:
        st.markdown("**Referencia original**")
        ref_visual = registro.get("referencia_url") or registro.get("referencia_link")
        if ref_visual:
            try:
                st.image(ref_visual, caption="Referencia del cliente", use_container_width=True)
            except Exception:
                st.markdown(f"[Abrir referencia]({ref_visual})")
        else:
            st.caption("Sin referencia visual guardada.")

    with vista2:
        st.markdown("**Propuesta IA**")
        if registro.get("propuesta_url"):
            st.image(
                registro.get("propuesta_url"),
                caption=f"{registro.get('codigo')} · Revisión {registro.get('revision', 1)}",
                use_container_width=True,
            )
            st.caption("✨ Imagen generada con Gemini")
        else:
            st.warning("No hay propuesta visual almacenada.")

        producto_txt = " | ".join(
            [x for x in [registro.get("producto_codigo"), registro.get("producto_descripcion")] if x]
        ) or "Sin definir"
        st.write(f"**Cliente:** {registro.get('cliente_nombre', '')}")
        st.write(f"**Producto:** {producto_txt}")
        st.write(f"**Técnica:** {registro.get('tecnica') or 'Por definir'}")
        st.write(f"**Colores:** {registro.get('colores') or 'No especificados'}")
        st.write(f"**Revisión:** {registro.get('revision', 1)}")
        st.write("**Brief:**")
        st.write(registro.get("instrucciones") or "")

    ajuste_key = f"dia_ajuste_{registro.get('codigo')}"
    if ajuste_key not in st.session_state:
        st.session_state[ajuste_key] = registro.get("ajuste_solicitado") or ""
    ajuste = st.text_area(
        "📝 Ajustes solicitados por el cliente",
        placeholder="Ej: reducir el dorado y mover el escudo.",
        key=ajuste_key,
    )

    siguientes = {
        "PROPUESTA PREPARADA": "Si el cliente pide cambios, guarda el ajuste; si está conforme, aprueba.",
        "AJUSTES SOLICITADOS": "Regenera con IA antes de aprobar.",
        "PROPUESTA REGENERADA": "Revisa la nueva imagen con el cliente.",
        "APROBADO POR CLIENTE": "Envía la propuesta al diseñador.",
        "ENVIADO A DISEÑADOR": "Ya está en la bandeja de Diseño. Puedes crear la cotización.",
    }
    st.caption("➡️ " + siguientes.get(estado_actual, "Continúa con el flujo."))

    b1, b2, b3, b4 = st.columns(4)
    bloquear = estado_actual in ["APROBADO POR CLIENTE", "ENVIADO A DISEÑADOR"]

    if b1.button(
        "💾 Guardar ajuste",
        use_container_width=True,
        key=f"dia_ajustar_{registro.get('codigo')}",
        disabled=bloquear,
    ):
        ajuste_limpio = str(ajuste or "").strip()
        if not ajuste_limpio:
            st.warning("Escribe primero el ajuste solicitado por el cliente.")
        else:
            _dia_actualizar(
                supabase,
                registro["id"],
                {
                    "ajuste_solicitado": ajuste_limpio,
                    "estado": "AJUSTES SOLICITADOS",
                },
            )
            st.success("Ajuste guardado. Ahora regenera la propuesta.")
            _dia_rerun_local()

    puede_regenerar = estado_actual == "AJUSTES SOLICITADOS" and api_ok
    if b2.button(
        "✨ Regenerar con IA",
        use_container_width=True,
        key=f"dia_regenerar_{registro.get('codigo')}",
        disabled=not puede_regenerar,
    ):
        try:
            registro_gen = dict(registro)
            with st.spinner("Generando nueva revisión..."):
                imagen, mime = _dia_generar_imagen_gemini(registro_gen)
            nueva_revision = int(registro.get("revision") or 1) + 1
            propuesta_url = _dia_subir_bytes(
                supabase,
                imagen,
                mime,
                f"disenos-ia/{registro.get('codigo')}",
                f"propuesta_r{nueva_revision}",
            )
            _dia_actualizar(
                supabase,
                registro["id"],
                {
                    "propuesta_url": propuesta_url,
                    "generacion_real": True,
                    "revision": nueva_revision,
                    "estado": "PROPUESTA REGENERADA",
                },
            )
            st.success(f"Revisión {nueva_revision} generada y guardada.")
            _dia_rerun_local()
        except Exception as e:
            st.error(f"No se pudo regenerar la propuesta: {e}")

    puede_aprobar = estado_actual in ["PROPUESTA PREPARADA", "PROPUESTA REGENERADA"] and bool(registro.get("propuesta_url"))
    if b3.button(
        "✅ Cliente aprueba",
        use_container_width=True,
        key=f"dia_aprobar_{registro.get('codigo')}",
        disabled=not puede_aprobar,
    ):
        _dia_actualizar(
            supabase,
            registro["id"],
            {
                "estado": "APROBADO POR CLIENTE",
                "fecha_aprobacion": _dia_now_iso(),
            },
        )
        st.success("Propuesta aprobada por el cliente.")
        _dia_rerun_local()

    if b4.button(
        "📤 Enviar al diseñador",
        use_container_width=True,
        key=f"dia_enviar_{registro.get('codigo')}",
        disabled=estado_actual != "APROBADO POR CLIENTE",
    ):
        try:
            orden_id, codigo_orden = _dia_crear_orden_para_disenador(
                supabase, registro, productos
            )
            _dia_actualizar(
                supabase,
                registro["id"],
                {
                    "estado": "ENVIADO A DISEÑADOR",
                    "orden_id": orden_id,
                    "fecha_envio_diseno": _dia_now_iso(),
                },
            )
            st.success(
                f"Enviado a Diseño correctamente. Orden {codigo_orden or orden_id} creada en Supabase."
            )
            _dia_rerun_local()
        except Exception as e:
            st.error(f"No se pudo enviar al diseñador: {e}")

    st.markdown("#### 4️⃣ Continuar a cotización")
    puede_cotizar = estado_actual == "ENVIADO A DISEÑADOR"
    if st.button(
        "🧾 CREAR COTIZACIÓN CON ESTE DISEÑO",
        use_container_width=True,
        key=f"dia_cotizar_{registro.get('codigo')}",
        disabled=not puede_cotizar,
    ):
        st.session_state["cliente_id_edicion"] = registro.get("cliente_id")
        st.session_state["modo_edicion_cot"] = False
        st.session_state["cot_items"] = []
        st.session_state["_dia_enlace_cotizacion_id"] = registro.get("id")

        prod_obj = next(
            (p for p in productos if p.get("id") == registro.get("producto_id")),
            None,
        )
        if prod_obj:
            precio = float(prod_obj.get("precio_unitario") or 0)
            st.session_state["cot_items"] = [
                {
                    "id": prod_obj.get("id"),
                    "codigo": prod_obj.get("codigo_referencia", ""),
                    "descripcion": prod_obj.get("descripcion", ""),
                    "cantidad": 1.0,
                    "precio": precio,
                    "subtotal": precio,
                    "obj_raw": prod_obj,
                }
            ]

        partes_obs = [
            f"Diseño IA {registro.get('codigo')}",
            f"Orden Diseño: {registro.get('orden_id') or 'pendiente'}",
            f"Producto: {registro.get('producto_codigo') or ''} | {registro.get('producto_descripcion') or ''}",
            f"Técnica: {registro.get('tecnica') or 'Por definir'}",
            f"Colores: {registro.get('colores') or 'No especificados'}",
            f"Brief: {registro.get('instrucciones') or ''}",
        ]
        if registro.get("ajuste_solicitado"):
            partes_obs.append(f"Último ajuste: {registro.get('ajuste_solicitado')}")
        st.session_state["cot_obs_temp"] = " | ".join(partes_obs)
        st.session_state["vista_cot"] = "EDITOR"
        st.rerun()

    st.divider()
    st.markdown("#### Historial de diseños")
    st.caption("Propuestas guardadas en Supabase.")
    registros_hist = registros
    for i in range(0, len(registros_hist), 3):
        fila = registros_hist[i:i + 3]
        cols = st.columns(len(fila))
        for col, r in zip(cols, fila):
            with col:
                with st.container(border=True):
                    icon = {
                        "PROPUESTA PREPARADA": "🟡",
                        "AJUSTES SOLICITADOS": "🟠",
                        "PROPUESTA REGENERADA": "🟣",
                        "APROBADO POR CLIENTE": "🟢",
                        "ENVIADO A DISEÑADOR": "🔵",
                    }.get(r.get("estado"), "⚪")
                    st.markdown(f"**{icon} {r.get('codigo', '')}**")
                    st.caption(r.get("cliente_nombre") or "Sin cliente")
                    st.write(
                        " | ".join(
                            [x for x in [r.get("producto_codigo"), r.get("producto_descripcion")] if x]
                        ) or "Sin producto"
                    )
                    st.markdown(f"**Estado:** {r.get('estado', '')}")
                    extras = [f"Revisión {r.get('revision', 1)}"]
                    if r.get("orden_id"):
                        extras.append(f"Orden #{r.get('orden_id')}")
                    if r.get("cotizacion_id"):
                        extras.append(f"Cotización #{r.get('cotizacion_id')}")
                    st.caption(" · ".join(extras))


# --- RENDER PRINCIPAL ---
def render(supabase):
    _inyectar_estilos_responsive()

    if "vista_cot" not in st.session_state:
        st.session_state["vista_cot"] = "LISTA"
    if "cot_items" not in st.session_state:
        st.session_state["cot_items"] = []

    if st.session_state["vista_cot"] == "LISTA":
        st.title("📑 Catálogo y Cotizaciones")

        # --- NUEVA ARQUITECTURA MÓVIL: Separación de intenciones ---
        tab_rapida, tab_formal, tab_diseno = st.tabs(
            ["🔎 Precios", "📋 Cotizaciones", "🎨 Diseño IA"]
        )

        # 1. MÓDULO DE CONSULTA ÁGIL (Pensado 100% para celular)
        with tab_rapida:
            st.markdown("🔍 **Búsqueda Ágil de Precios**")

            # Traemos los datos incluyendo los campos de categorización (Una sola consulta rápida)
            prods_raw = (
                supabase.table("productos_catalogo")
                .select(
                    "codigo_referencia, descripcion, tipo_prenda, linea_categoria, grupo_edad, precio_unitario, precio_docena, precio_mayorista"
                )
                .eq("activo", True)
                .execute()
                .data
            )

            if prods_raw:
                df_cat = pd.DataFrame(prods_raw)

                # Buscador principal (Siempre visible)
                txt_rapido = st.text_input(
                    "Palabra clave o código:",
                    placeholder="Ej: Camiseta, 001, Polo...",
                    label_visibility="collapsed",
                )

                # Filtros ocultos en un acordeón (Ahorra espacio en celular)
                with st.expander(
                    "⚙️ Filtros avanzados (Prenda, Categoría, Edad)", expanded=False
                ):
                    f_col1, f_col2, f_col3 = st.columns(3)

                    lista_tp = ["Todos"] + sorted(
                        [
                            str(x)
                            for x in df_cat["tipo_prenda"].dropna().unique()
                            if str(x).strip()
                        ]
                    )
                    lista_cat = ["Todos"] + sorted(
                        [
                            str(x)
                            for x in df_cat["linea_categoria"].dropna().unique()
                            if str(x).strip()
                        ]
                    )
                    lista_edad = ["Todos"] + sorted(
                        [
                            str(x)
                            for x in df_cat["grupo_edad"].dropna().unique()
                            if str(x).strip()
                        ]
                    )

                    filtro_tp = f_col1.selectbox("Prenda", lista_tp)
                    filtro_cat = f_col2.selectbox("Categoría", lista_cat)
                    filtro_edad = f_col3.selectbox("Edad", lista_edad)

                # Proceso de filtrado secuencial
                df_f = df_cat.copy()

                if txt_rapido:
                    df_f = df_f[
                        df_f["descripcion"].str.contains(
                            txt_rapido, case=False, na=False
                        )
                        | df_f["codigo_referencia"].str.contains(
                            txt_rapido, case=False, na=False
                        )
                    ]
                if filtro_tp != "Todos":
                    df_f = df_f[df_f["tipo_prenda"] == filtro_tp]
                if filtro_cat != "Todos":
                    df_f = df_f[df_f["linea_categoria"] == filtro_cat]
                if filtro_edad != "Todos":
                    df_f = df_f[df_f["grupo_edad"] == filtro_edad]

                # Renderizado de Tarjetas: Solo mostramos resultados si el usuario interactuó con algo
                if (
                    txt_rapido
                    or filtro_tp != "Todos"
                    or filtro_cat != "Todos"
                    or filtro_edad != "Todos"
                ):
                    if not df_f.empty:
                        # Limitamos a 15 para no colapsar la memoria del celular si hay muchos
                        st.caption(
                            f"Se encontraron {len(df_f)} resultados (Mostrando primeros 15):"
                        )

                        for _, row in df_f.head(15).iterrows():
                            with st.container(border=True):
                                st.markdown(
                                    f"**[{row['codigo_referencia']}]** {row['descripcion']}"
                                )
                                c1, c2, c3 = st.columns(3)
                                # Usamos format exacto para evitar números con muchos decimales
                                c1.metric(
                                    "Unitario", f"${float(row['precio_unitario']):.2f}"
                                )
                                c2.metric(
                                    "Docena", f"${float(row['precio_docena']):.2f}"
                                )
                                c3.metric(
                                    "Mayor", f"${float(row['precio_mayorista']):.2f}"
                                )
                    else:
                        st.info("No hay productos con esta combinación de filtros.")
            else:
                st.warning("No hay productos activos en el catálogo.")

        # 2. MÓDULO TRADICIONAL DE COTIZACIONES
        with tab_formal:
            c_tit, c_btn = st.columns([3, 2])
            c_tit.subheader("Historial")
            if c_btn.button(
                "➕ NUEVA COTIZACIÓN", type="primary", use_container_width=True
            ):
                st.session_state["vista_cot"] = "EDITOR"
                st.session_state["modo_edicion_cot"] = False
                st.session_state["cot_items"] = []
                st.session_state["cot_obs_temp"] = ""
                st.session_state["cliente_id_edicion"] = None
                st.rerun()

            with st.container(border=True):
                col_fil1, col_fil2, col_fil3 = st.columns(3)
                h_f_txt = col_fil1.text_input("🔍 Buscar Cliente / Código")
                h_f_ini = col_fil2.date_input(
                    "Desde", value=datetime.date.today() - datetime.timedelta(days=30)
                )
                h_f_fin = col_fil3.date_input("Hasta", value=datetime.date.today())

            query = (
                supabase.table("cotizaciones").select("*").order("created_at", desc=True)
            )
            query = query.gte("created_at", str(h_f_ini)).lte(
                "created_at", str(h_f_fin) + " 23:59:59"
            )
            resp_cots = query.execute()
            df_cots = pd.DataFrame(resp_cots.data)

            if not df_cots.empty:
                ids_cli = df_cots["cliente_id"].unique().tolist()
                if ids_cli:
                    resp_clis = (
                        supabase.table("clientes")
                        .select("id, nombre_completo")
                        .in_("id", ids_cli)
                        .execute()
                    )
                    mapa_cli = {c["id"]: c["nombre_completo"] for c in resp_clis.data}
                    df_cots["Cliente"] = df_cots["cliente_id"].map(mapa_cli)

                if h_f_txt:
                    df_cots = df_cots[
                        df_cots["codigo_cotizacion"].str.contains(h_f_txt, case=False)
                        | df_cots["Cliente"].str.contains(h_f_txt, case=False, na=False)
                    ]

                opciones_cot = {}
                for idx, row in df_cots.iterrows():
                    etiqueta = (
                        f"{row['codigo_cotizacion']} · {row.get('Cliente', 'Sin cliente')} · "
                        f"${float(row.get('total', 0) or 0):.2f} · {row.get('estado', '')}"
                    )
                    opciones_cot[etiqueta] = idx

                etiqueta_sel = st.selectbox(
                    "Selecciona una cotización",
                    list(opciones_cot.keys()),
                    key="cot_hist_selector",
                )
                idx = opciones_cot[etiqueta_sel]
                row_sel = df_cots.loc[idx]

                with st.container(border=True):
                    c_res1, c_res2 = st.columns([2, 1])
                    c_res1.markdown(
                        f"#### ⚙️ {row_sel['codigo_cotizacion']}\n"
                        f"**{row_sel.get('Cliente', 'Sin cliente')}**"
                    )
                    c_res2.metric("Total", f"${float(row_sel.get('total', 0) or 0):.2f}")
                    st.caption(
                        f"📅 {row_sel.get('fecha_emision', '')} · "
                        f"Estado: {row_sel.get('estado', '')}"
                    )
                    b1, b2, b3, b4 = st.columns(4)

                    if b1.button("✏️ EDITAR", use_container_width=True):
                        detalles = (
                            supabase.table("detalles_cotizacion")
                            .select("*")
                            .eq("cotizacion_id", int(row_sel["id"]))
                            .execute()
                            .data
                        )
                        items_load = []
                        for d in detalles:
                            try:
                                prod = (
                                    supabase.table("productos_catalogo")
                                    .select("*")
                                    .eq("id", d["producto_id"])
                                    .single()
                                    .execute()
                                    .data
                                )
                                items_load.append(
                                    {
                                        "id": d["producto_id"],
                                        "codigo": prod["codigo_referencia"],
                                        "descripcion": d["descripcion_snapshot"],
                                        "cantidad": float(d["cantidad"]),
                                        "precio": float(d["precio_unitario"]),
                                        "subtotal": float(d["subtotal"]),
                                        "obj_raw": prod,
                                    }
                                )
                            except:
                                pass
                        st.session_state["cot_items"] = items_load
                        st.session_state["modo_edicion_cot"] = True
                        st.session_state["id_cot_edicion"] = int(row_sel["id"])
                        st.session_state["cliente_id_edicion"] = int(
                            row_sel["cliente_id"]
                        )
                        st.session_state["codigo_edicion"] = row_sel[
                            "codigo_cotizacion"
                        ]
                        st.session_state["cot_obs_temp"] = row_sel["observaciones"]
                        st.session_state["vista_cot"] = "EDITOR"
                        st.rerun()

                    if b2.button("📄 PDF", use_container_width=True):
                        detalles = (
                            supabase.table("detalles_cotizacion")
                            .select("*")
                            .eq("cotizacion_id", int(row_sel["id"]))
                            .execute()
                            .data
                        )
                        items_pdf = []
                        for d in detalles:
                            prod = (
                                supabase.table("productos_catalogo")
                                .select("codigo_referencia")
                                .eq("id", d["producto_id"])
                                .single()
                                .execute()
                                .data
                            )
                            items_pdf.append(
                                {
                                    "codigo": prod["codigo_referencia"],
                                    "descripcion": d["descripcion_snapshot"],
                                    "cantidad": d["cantidad"],
                                    "precio": d["precio_unitario"],
                                    "subtotal": d["subtotal"],
                                }
                            )

                        cli_data = (
                            supabase.table("clientes")
                            .select("*")
                            .eq("id", int(row_sel["cliente_id"]))
                            .single()
                            .execute()
                            .data
                        )
                        tl = num2words(row_sel["total"], lang="es").upper() + " DÓLARES"

                        try:
                            f_em = datetime.datetime.strptime(
                                row_sel["fecha_emision"], "%Y-%m-%d"
                            ).date()
                            days_val = (
                                row_sel["validez_dias"]
                                if row_sel["validez_dias"]
                                else 30
                            )
                            str_val = str(f_em + datetime.timedelta(days=days_val))
                        except:
                            str_val = str(
                                datetime.date.today() + datetime.timedelta(days=30)
                            )

                        pdf_bytes = generar_pdf_final(
                            cabecera={
                                "cliente_nombre": cli_data["nombre_completo"],
                                "cliente_ruc": cli_data["cedula_ruc"],
                                "telefono": cli_data["telefono"],
                                "fecha": str(row_sel["fecha_emision"]),
                                "codigo": row_sel["codigo_cotizacion"],
                                "subtotal": float(row_sel["total"]) / 1.15,
                                "iva": float(row_sel["total"])
                                - (float(row_sel["total"]) / 1.15),
                                "total": row_sel["total"],
                                "tipo": cli_data.get("tipo_institucion", ""),
                            },
                            items=items_pdf,
                            observaciones=row_sel["observaciones"],
                            vigencia_fecha=str_val,
                            total_letras=tl,
                        )
                        st.download_button(
                            "⬇️ Bajar",
                            pdf_bytes,
                            f"{row_sel['codigo_cotizacion']}.pdf",
                            "application/pdf",
                        )

                    confirmar_borrar = b3.checkbox(
                        "¿Seguro?", key=f"confirm_cot_{row_sel['id']}"
                    )
                    if b3.button(
                        "🗑️ Borrar",
                        use_container_width=True,
                        disabled=not confirmar_borrar,
                    ):
                        # Borrado lógico: marcamos como ANULADO en vez de eliminar.
                        supabase.table("cotizaciones").update(
                            {"estado": "ANULADO"}
                        ).eq("id", int(row_sel["id"])).execute()
                        st.toast("Cotización anulada")
                        time.sleep(1)
                        st.rerun()

                    tel_cl = ""
                    try:
                        tel_cl = (
                            supabase.table("clientes")
                            .select("telefono")
                            .eq("id", int(row_sel["cliente_id"]))
                            .single()
                            .execute()
                            .data["telefono"]
                        )
                    except:
                        pass
                    if tel_cl:
                        tc = "".join(filter(str.isdigit, str(tel_cl)))
                        if len(tc) > 0 and not tc.startswith("593"):
                            tc = "593" + tc
                        lnk = f"https://wa.me/{tc}?text=Cotizacion%20{row_sel['codigo_cotizacion']}%20Total:{row_sel['total']}"
                        b4.link_button("📲 WA", lnk, use_container_width=True)
                    else:
                        b4.button("No Telf", disabled=True)
            else:
                st.info("Sin registros.")

        # 3. DISEÑO CON IA (INTEGRADO)
        with tab_diseno:
            _render_diseno_ia(supabase)

    elif st.session_state["vista_cot"] == "EDITOR":
        c_b, c_h = st.columns([1, 6])
        if c_b.button("🔙 Volver", use_container_width=True):
            st.session_state["vista_cot"] = "LISTA"
            st.rerun()

        c_h.header(
            f"✏️ Editando: {st.session_state.get('codigo_edicion', 'Nueva Cotización')}"
        )
        st.divider()

        # 1. CLIENTE
        c_cli, c_dat = st.columns([2, 1])
        with c_cli:
            try:
                cli_db = supabase.table("clientes").select("*").execute().data
                opciones_cli = {
                    f"{c['nombre_completo']} | {c['cedula_ruc']}": c for c in cli_db
                }
                claves_cli = list(opciones_cli.keys())
            except:
                opciones_cli = {}
                claves_cli = []

            idx_sel = 0
            if st.session_state.get("cliente_id_edicion"):
                curr = st.session_state["cliente_id_edicion"]
                for i, v in enumerate(opciones_cli.values()):
                    if v["id"] == curr:
                        idx_sel = i + 1
                        break

            sel = st.selectbox("Cliente", [""] + claves_cli, index=idx_sel)
            sel_id = opciones_cli[sel]["id"] if sel else None

            with st.popover("➕ Crear Cliente Nuevo"):
                with st.form("new_c"):
                    nc1, nc2 = st.columns(2)
                    ruc, nom = nc1.text_input("RUC/CI *"), nc2.text_input("Nombre *")
                    nc3, nc4 = st.columns(2)
                    tel, mail = nc3.text_input("Telf"), nc4.text_input("Email")
                    ciu = st.text_input("Ciudad")
                    try:
                        res_tip = (
                            supabase.table("catalogo_tipos_cliente")
                            .select("nombre")
                            .eq("activo", True)
                            .order("nombre")
                            .execute()
                        )
                        opc_tipo = (
                            [t["nombre"] for t in res_tip.data]
                            if res_tip.data
                            else ["Cliente Final"]
                        )
                    except:
                        opc_tipo = ["Cliente Final"]

                    nc_tipo = st.selectbox("Tipo", opc_tipo)
                    nc_gen = st.selectbox("Género", ["Masculino", "Femenino", "Otro"])
                    if st.form_submit_button("Guardar"):
                        if ruc and nom:
                            try:
                                res = (
                                    supabase.table("clientes")
                                    .insert(
                                        {
                                            "cedula_ruc": ruc,
                                            "nombre_completo": nom.upper(),
                                            "telefono": tel,
                                            "email": mail,
                                            "ciudad": ciu,
                                            "tipo_institucion": nc_tipo,
                                            "genero": nc_gen,
                                        }
                                    )
                                    .execute()
                                )
                                st.session_state["cliente_id_edicion"] = res.data[0][
                                    "id"
                                ]
                                st.success("Creado!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")

        with c_dat:
            f_em = st.date_input("Fecha", value=datetime.date.today())

        # 2. PRODUCTOS (Buscador mejorado según imagen)
        st.markdown("---")
        with st.container(border=True):
            st.markdown("🔍 **Filtros de Búsqueda (Catálogo)**")
            prods = (
                supabase.table("productos_catalogo")
                .select("*")
                .eq("activo", True)
                .execute()
                .data
            )
            df_p = pd.DataFrame(prods)

            if not df_p.empty:
                # Fila 1: Selectores
                f1, f2, f3 = st.columns(3)
                tp = f1.selectbox(
                    "Prenda", ["Todos"] + sorted(df_p["tipo_prenda"].unique().tolist())
                )
                cat = f2.selectbox(
                    "Categoría",
                    ["Todos"] + sorted(df_p["linea_categoria"].unique().tolist()),
                )
                edad = f3.selectbox(
                    "Edad", ["Todos"] + sorted(df_p["grupo_edad"].unique().tolist())
                )

                # Fila 2: Checkboxes de Características
                st.markdown("**Características de Producción:**")
                c1, c2, c3, c_search = st.columns([1, 1, 1, 2.5])
                solo_sub = c1.checkbox("Solo Sublimado")
                solo_dtf = c2.checkbox("Solo DTF")
                solo_bor = c3.checkbox("Solo Bordado")
                txt_busq = c_search.text_input(
                    "Buscar texto...", placeholder="Cód o Nombre"
                )

                # Aplicar Filtros
                df_f = df_p
                if tp != "Todos":
                    df_f = df_f[df_f["tipo_prenda"] == tp]
                if cat != "Todos":
                    df_f = df_f[df_f["linea_categoria"] == cat]
                if edad != "Todos":
                    df_f = df_f[df_f["grupo_edad"] == edad]
                if solo_sub:
                    df_f = df_f[df_f["requiere_sublimado"] == True]
                if solo_dtf:
                    df_f = df_f[df_f["requiere_dtf"] == True]
                if solo_bor:
                    df_f = df_f[df_f["requiere_bordado"] == True]
                if txt_busq:
                    df_f = df_f[
                        df_f["descripcion"].str.contains(txt_busq, case=False)
                        | df_f["codigo_referencia"].str.contains(txt_busq, case=False)
                    ]

                st.markdown("Seleccione el producto de la lista filtrada")
                map_p = {
                    f"{r['codigo_referencia']} | {r['descripcion']}": r
                    for r in df_f.to_dict("records")
                }

                if map_p:
                    k_sel = st.selectbox(
                        "Resultado", list(map_p.keys()), label_visibility="collapsed"
                    )
                    obj = map_p[k_sel]

                    # Área de inserción de cantidad y precio
                    st.markdown("<br>", unsafe_allow_html=True)
                    col_k, col_t, col_pr, col_bt = st.columns([1, 1.5, 1, 1])

                    cant = col_k.number_input("Cant", 1.0, step=1.0)
                    tarifa = col_t.selectbox(
                        "Tarifa", ["Auto", "Unit", "Docena", "Mayorista"]
                    )

                    # Lógica de Precios
                    p_base = obj["precio_unitario"]
                    req_pin = False
                    if tarifa == "Auto":
                        if cant >= 25:
                            p_base = obj["precio_mayorista"]
                        elif cant >= 12:
                            p_base = obj["precio_docena"]
                    elif tarifa == "Docena":
                        p_base = obj["precio_docena"]
                        if cant < 12:
                            req_pin = True
                    elif tarifa == "Mayorista":
                        p_base = obj["precio_mayorista"]
                        if cant < 25:
                            req_pin = True

                    final_p = col_pr.number_input("Precio", value=float(p_base))

                    add_ready = True
                    if req_pin:
                        pin = st.text_input(
                            "🔑 Autorización Requerida", type="password"
                        )
                        pin_ok = False
                        try:
                            pin_ok = bool(pin) and pin == st.secrets["admin"]["pin_gerencia"]
                        except Exception:
                            pin_ok = False
                        if not pin_ok:
                            st.warning(
                                "Requiere PIN para aplicar tarifa de volumen con pocas unidades"
                            )
                            add_ready = False

                    if col_bt.button(
                        "➕ AGREGAR", type="primary", use_container_width=True
                    ):
                        if add_ready:
                            st.session_state["cot_items"].append(
                                {
                                    "id": obj["id"],
                                    "codigo": obj["codigo_referencia"],
                                    "descripcion": obj["descripcion"],
                                    "cantidad": cant,
                                    "precio": final_p,
                                    "subtotal": cant * final_p,
                                    "obj_raw": obj,
                                }
                            )
                            st.rerun()

        # 3. DETALLE DE LA COTIZACIÓN (Edición de cantidad y eliminación habilitada)
        if st.session_state["cot_items"]:
            st.markdown("### Detalle de Items")
            st.info(
                "💡 Edita la cantidad directamente en la tabla. Para eliminar un ítem usa el botón de abajo."
            )

            # Preparar datos
            df_original = pd.DataFrame(st.session_state["cot_items"])

            # Editor con eliminación dinámica habilitada
            edited_df = st.data_editor(
                df_original[
                    ["codigo", "descripcion", "cantidad", "precio", "subtotal"]
                ],
                column_config={
                    "codigo": st.column_config.TextColumn("Código", disabled=True),
                    "descripcion": st.column_config.TextColumn(
                        "Descripción", disabled=True
                    ),
                    "cantidad": st.column_config.NumberColumn(
                        "Cant.", min_value=1.0, step=1.0, format="%d"
                    ),
                    "precio": st.column_config.NumberColumn(
                        "P. Unit", format="$ %.2f", disabled=True
                    ),
                    "subtotal": st.column_config.NumberColumn(
                        "Total", format="$ %.2f", disabled=True
                    ),
                },
                num_rows="dynamic",  # ESTA LÍNEA PERMITE ELIMINAR FILAS
                use_container_width=True,
                key="grid_cot_edit",
                hide_index=True,
            )

            # Lógica de Sincronización: Detecta si se borró una fila o se cambió un valor
            if not edited_df.equals(
                df_original[["codigo", "descripcion", "cantidad", "precio", "subtotal"]]
            ):
                new_items = []
                # Reconstruimos la lista basándonos en lo que quedó en el editor
                for index, row in edited_df.iterrows():
                    # Buscamos el objeto original por índice para no perder IDs ni obj_raw
                    if index < len(st.session_state["cot_items"]):
                        orig = st.session_state["cot_items"][index]
                        nueva_cant = float(row["cantidad"])

                        new_items.append(
                            {
                                "id": orig["id"],
                                "codigo": orig["codigo"],
                                "descripcion": orig["descripcion"],
                                "cantidad": nueva_cant,
                                "precio": orig["precio"],
                                "subtotal": nueva_cant * orig["precio"],
                                "obj_raw": orig.get("obj_raw"),
                            }
                        )

                st.session_state["cot_items"] = new_items
                st.rerun()

            # Eliminación táctil (sin depender de la tecla Delete, ideal para móvil)
            st.divider()
            st.markdown("#### 🗑️ Eliminar ítem")
            opciones_del = [
                f"{i + 1}. {it['codigo']} | {it['descripcion']} (x{it['cantidad']})"
                for i, it in enumerate(st.session_state["cot_items"])
            ]
            sel_del = st.selectbox(
                "Selecciona el ítem a eliminar:",
                opciones_del,
                key="cot_del_sel",
            )
            if st.button(
                "🗑️ Eliminar ítem seleccionado",
                type="secondary",
                use_container_width=True,
            ):
                idx_del = opciones_del.index(sel_del)
                st.session_state["cot_items"].pop(idx_del)
                st.toast("Ítem eliminado", icon="🗑️")
                st.rerun()

            # --- El resto de tu lógica de totales y guardado se mantiene igual ---
            tot = sum([x["subtotal"] for x in st.session_state["cot_items"]])
            st.markdown(f"### Total Cotizado: :green[${tot:.2f}]")

            obs = st.text_area(
                "Observaciones de la Cotización",
                value=st.session_state.get("cot_obs_temp", ""),
            )

            if st.button(
                "💾 GUARDAR COTIZACIÓN", type="primary", use_container_width=True
            ):
                if sel_id:
                    try:
                        cod = st.session_state.get(
                            "codigo_edicion"
                        ) or generar_siguiente_codigo_cot(supabase)
                        data_head = {
                            "codigo_cotizacion": cod,
                            "cliente_id": sel_id,
                            "subtotal": tot / 1.15,
                            "iva": tot - (tot / 1.15),
                            "total": tot,
                            "observaciones": obs,
                            "fecha_emision": str(f_em),
                            "estado": "BORRADOR",
                            "creado_por_id": st.session_state.get("id_usuario", 1),
                        }

                        if st.session_state.get("modo_edicion_cot"):
                            supabase.table("cotizaciones").update(data_head).eq(
                                "id", st.session_state["id_cot_edicion"]
                            ).execute()
                            cot_id = st.session_state["id_cot_edicion"]
                            supabase.table("detalles_cotizacion").delete().eq(
                                "cotizacion_id", cot_id
                            ).execute()
                        else:
                            res = (
                                supabase.table("cotizaciones")
                                .insert(data_head)
                                .execute()
                            )
                            cot_id = res.data[0]["id"]

                        detalles = []
                        for i in st.session_state["cot_items"]:
                            detalles.append(
                                {
                                    "cotizacion_id": cot_id,
                                    "producto_id": i["id"],
                                    "cantidad": i["cantidad"],
                                    "precio_unitario": i["precio"],
                                    "subtotal": i["subtotal"],
                                    "descripcion_snapshot": i["descripcion"],
                                }
                            )
                        supabase.table("detalles_cotizacion").insert(detalles).execute()

                        # Si la cotización nació desde Diseño IA, dejamos la relación persistida.
                        diseno_enlace_id = st.session_state.get("_dia_enlace_cotizacion_id")
                        if diseno_enlace_id:
                            try:
                                _dia_actualizar(
                                    supabase,
                                    diseno_enlace_id,
                                    {"cotizacion_id": cot_id},
                                )
                                st.session_state.pop("_dia_enlace_cotizacion_id", None)
                            except Exception as e_link:
                                st.warning(
                                    f"La cotización se guardó, pero no se pudo enlazar con Diseño IA: {e_link}"
                                )

                        st.success(f"Cotización {cod} guardada con éxito")
                        st.session_state["vista_cot"] = "LISTA"
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")
                else:
                    st.error("Debe seleccionar un cliente antes de guardar.")
