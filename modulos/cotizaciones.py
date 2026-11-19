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
from decimal import Decimal, ROUND_HALF_UP
from copy import deepcopy
from types import SimpleNamespace
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
_COT_IVA_OPCIONES = {
    "INCLUIDO": "Precio final ya incluye IVA",
    "AGREGADO": "Agregar IVA al precio",
}
_COT_IVA_TASA = Decimal("0.15")
_COT_CENTAVO = Decimal("0.01")


def _cot_dinero(valor):
    return Decimal(str(0 if pd.isna(valor) else valor)).quantize(
        _COT_CENTAVO, rounding=ROUND_HALF_UP
    )


def _cot_calcular_iva(items, modalidad):
    # Los precios y subtotales de los items conservan el importe ingresado.
    importe = sum((_cot_dinero(i["subtotal"]) for i in items), Decimal("0.00"))
    if modalidad == "INCLUIDO":
        total = importe
        subtotal = _cot_dinero(total / (1 + _COT_IVA_TASA))
        iva = total - subtotal
    elif modalidad == "AGREGADO":
        subtotal = importe
        iva = _cot_dinero(subtotal * _COT_IVA_TASA)
        total = subtotal + iva
    else:
        raise ValueError("Modalidad de IVA no válida.")
    return subtotal, iva, total


def _cot_modalidad_guardada(cabecera):
    # Las cotizaciones anteriores al cambio se calculaban con IVA incluido.
    valor = cabecera.get("modalidad_iva")
    # Solo lectura: respetar posibles proformas históricas sin IVA.
    if isinstance(valor, str) and (valor in _COT_IVA_OPCIONES or valor == "SIN_IVA"):
        return valor
    return "INCLUIDO"


def _cot_totales_guardados(cabecera):
    # Nunca volver a aplicar IVA a una cotización histórica.
    total = _cot_dinero(cabecera["total"])
    subtotal = cabecera.get("subtotal")
    iva = cabecera.get("iva")
    if _cot_modalidad_guardada(cabecera) == "SIN_IVA":
        # Proforma comercial sin impuesto añadido; no implica exención fiscal.
        if (pd.notna(subtotal) and _cot_dinero(subtotal) != total) or (
            pd.notna(iva) and _cot_dinero(iva) != Decimal("0.00")
        ):
            raise ValueError("Importes inconsistentes en cotización sin incluir IVA.")
        return total, Decimal("0.00"), total
    if pd.notna(subtotal) and pd.notna(iva):
        return _cot_dinero(subtotal), _cot_dinero(iva), total
    if pd.notna(subtotal):
        base = _cot_dinero(subtotal)
        return base, total - base, total
    if pd.notna(iva):
        impuesto = _cot_dinero(iva)
        return total - impuesto, impuesto, total
    base = _cot_dinero(total / (1 + _COT_IVA_TASA))
    return base, total - base, total


def _cot_iniciar_modalidad(modalidad="INCLUIDO"):
    st.session_state["cot_modalidad_iva"] = modalidad
    st.session_state.pop("cot_modalidad_iva_widget", None)


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


# --- MODO DE PRUEBA LOCAL: SOLO COTIZACIONES ---
# Activar antes de arrancar App.py: $env:YUNPAR_COT_MODO_PRUEBA="1"
# Por defecto desactivado. No cambia el cliente Supabase global.
def _cot_modo_prueba():
    return os.environ.get("YUNPAR_COT_MODO_PRUEBA", "0") == "1"


_COT_PRUEBA_TABLAS = frozenset({
    "cotizaciones", "detalles_cotizacion", "clientes",
    "productos_catalogo", "catalogo_tipos_cliente",
})
_COT_PRUEBA_EDITABLES = frozenset({
    "cotizaciones", "detalles_cotizacion", "clientes",
})


def _cot_prueba_fecha(valor):
    fecha = datetime.datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    if fecha.tzinfo is not None:
        fecha = fecha.astimezone().replace(tzinfo=None)
    return fecha


class _CotConsultaPrueba:
    """Consultas sobre una copia en memoria; nunca ejecuta escrituras remotas."""

    def __init__(self, nombre, datos):
        self.nombre = nombre
        self.datos = datos
        self.accion = "select"
        self.campos = "*"
        self.payload = None
        self.filtros = []
        self.orden = None
        self.tope = None
        self.unico = False

    def select(self, campos="*"):
        self.campos = campos
        return self

    def eq(self, campo, valor):
        self.filtros.append(lambda r: r.get(campo) == valor)
        return self

    def in_(self, campo, valores):
        self.filtros.append(lambda r: r.get(campo) in valores)
        return self

    def gte(self, campo, valor):
        self.filtros.append(lambda r: r.get(campo) is not None and (
            _cot_prueba_fecha(r[campo]) >= _cot_prueba_fecha(valor)
            if campo == "created_at" else r[campo] >= valor))
        return self

    def lte(self, campo, valor):
        self.filtros.append(lambda r: r.get(campo) is not None and (
            _cot_prueba_fecha(r[campo]) <= _cot_prueba_fecha(valor)
            if campo == "created_at" else r[campo] <= valor))
        return self

    def order(self, campo, desc=False):
        self.orden = (campo, desc)
        return self

    def limit(self, cantidad):
        self.tope = cantidad
        return self

    def single(self):
        self.unico = True
        return self

    def insert(self, payload):
        self.accion, self.payload = "insert", payload
        return self

    def update(self, payload):
        self.accion, self.payload = "update", payload
        return self

    def delete(self):
        self.accion = "delete"
        return self

    def _validar(self, fila, otras):
        if self.nombre == "cotizaciones":
            if fila.get("modalidad_iva") not in _COT_IVA_OPCIONES:
                raise ValueError("Modalidad IVA no válida")
            if any(r.get("codigo_cotizacion") == fila.get("codigo_cotizacion")
                   and r.get("id") != fila.get("id") for r in otras):
                raise ValueError("Código de cotización duplicado")
            if not any(r.get("id") == fila.get("cliente_id")
                       for r in self.datos["clientes"]):
                raise ValueError("Cliente no encontrado en la copia local")
        elif self.nombre == "detalles_cotizacion":
            if not any(r.get("id") == fila.get("cotizacion_id")
                       for r in self.datos["cotizaciones"]):
                raise ValueError("Cotización no encontrada en la copia local")
            if not any(r.get("id") == fila.get("producto_id")
                       for r in self.datos["productos_catalogo"]):
                raise ValueError("Producto no encontrado en la copia local")
        elif self.nombre == "clientes":
            if any(r.get("cedula_ruc") == fila.get("cedula_ruc")
                   and r.get("id") != fila.get("id") for r in otras):
                raise ValueError("RUC/CI duplicado en la copia local")

    def execute(self):
        filas = self.datos[self.nombre]
        def coincide(r):
            return all(f(r) for f in self.filtros)

        if self.accion == "select":
            salida = [deepcopy(r) for r in filas if coincide(r)]
            if self.orden:
                campo, desc = self.orden
                def clave(r):
                    valor = r.get(campo)
                    if campo == "created_at" and valor is not None:
                        valor = _cot_prueba_fecha(valor)
                    return valor is not None, valor
                salida.sort(key=clave, reverse=desc)
            if self.tope is not None:
                salida = salida[:self.tope]
            if self.campos != "*":
                campos = [c.strip() for c in self.campos.split(",")]
                salida = [{c: r[c] for c in campos} for r in salida]
        else:
            if self.nombre not in _COT_PRUEBA_EDITABLES:
                raise RuntimeError("Modo prueba: escritura bloqueada en " + self.nombre)
            copia = deepcopy(filas)
            salida = []
            if self.accion == "insert":
                lote = self.payload if isinstance(self.payload, list) else [self.payload]
                for original in lote:
                    fila = deepcopy(original)
                    # ID negativo: no puede confundirse con los IDs reales existentes.
                    fila["id"] = min([0] + [int(r["id"]) for r in copia]) - 1
                    if self.nombre == "cotizaciones":
                        fila.setdefault("created_at", datetime.datetime.now().isoformat(timespec="seconds"))
                        fila.setdefault("validez_dias", 30)
                    self._validar(fila, copia)
                    copia.append(fila)
                    salida.append(deepcopy(fila))
            elif self.accion == "update":
                if not self.filtros:
                    raise RuntimeError("Actualización sin filtro bloqueada")
                for fila in copia:
                    if coincide(fila):
                        fila.update(deepcopy(self.payload))
                        self._validar(fila, copia)
                        salida.append(deepcopy(fila))
            elif self.accion == "delete":
                if not self.filtros:
                    raise RuntimeError("Borrado sin filtro bloqueado")
                salida = [deepcopy(r) for r in copia if coincide(r)]
                copia = [r for r in copia if not coincide(r)]
            else:
                raise RuntimeError("Operación no implementada")
            filas[:] = copia
        if self.unico:
            if len(salida) != 1:
                raise RuntimeError("Se esperaba un registro")
            salida = salida[0]
        return SimpleNamespace(data=salida)


class _CotSupabasePrueba:
    def __init__(self, datos):
        self.datos = datos

    def table(self, nombre):
        if nombre not in _COT_PRUEBA_TABLAS:
            raise RuntimeError("Tabla no permitida en modo prueba: " + nombre)
        return _CotConsultaPrueba(nombre, self.datos)


def _cot_cargar_copia_prueba(supabase):
    # Solo SELECT al servidor real. Una copia independiente por sesión de Streamlit.
    clave = "_yunpar_cot_prueba_datos_v1"
    if clave not in st.session_state:
        datos = {}
        for nombre in sorted(_COT_PRUEBA_TABLAS):
            filas = []
            offset = 0
            # Paginar incluso si Supabase limita el número de filas por respuesta.
            while True:
                campo_orden = "nombre" if nombre == "catalogo_tipos_cliente" else "id"
                lote = (supabase.table(nombre).select("*").order(campo_orden)
                        .range(offset, offset + 499).execute().data or [])
                if not lote:
                    break
                filas.extend(deepcopy(lote))
                offset += len(lote)
            datos[nombre] = filas
        st.session_state[clave] = datos
    return _CotSupabasePrueba(st.session_state[clave])


def generar_siguiente_codigo_cot(supabase):
    prefijo = "PRUEBA-COT-" if isinstance(supabase, _CotSupabasePrueba) else "COT-"
    try:
        resp = supabase.table("cotizaciones").select("codigo_cotizacion").execute()
        codigos = [d["codigo_cotizacion"] for d in resp.data]
        max_num = 0
        for c in codigos:
            if c.startswith(prefijo) and c[len(prefijo):].isdigit():
                num = int(c[len(prefijo):])
                if num > max_num:
                    max_num = num
        return f"{prefijo}{str(max_num + 1).zfill(4)}"
    except:
        return f"{prefijo}0001"


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
    modalidad_pdf = _cot_modalidad_guardada(cabecera)
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

    pdf.ln(2)
    pdf.set_x(52)
    pdf.set_font("Arial", "I", 8)
    pdf.cell(
        0, 4,
        {
            "INCLUIDO": "Precios de los items: IVA incluido",
            "AGREGADO": "Precios de los items: sin IVA (se agrega al subtotal)",
            "SIN_IVA": "Precios cotizados sin incluir IVA.",
        }[modalidad_pdf],
        0, 1,
    )
    if cabecera.get("modo_prueba"):
        pdf.set_x(52)
        pdf.set_text_color(180, 0, 0)
        pdf.cell(0, 4, "MODO PRUEBA - NO VALIDO PARA CLIENTES", 0, 1)
        pdf.set_text_color(0, 0, 0)
    pdf.ln(1)
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
    if modalidad_pdf != "SIN_IVA" and _cot_dinero(cabecera["iva"]) != Decimal("0.00"):
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
_DIA_MAX_REFERENCIAS = 8
_DIA_MAX_BYTES = 8 * 1024 * 1024
_DIA_ZONAS = ["Referencia general", "Frente / pecho", "Pecho derecho", "Pecho izquierdo", "Centro del pecho",
              "Espalda", "Manga izquierda", "Manga derecha", "Ambas mangas", "Cuello", "Costado",
              "Logo / patrocinador", "Otro detalle"]
_DIA_FORMATOS = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
_DIA_ESTADOS_ELIMINABLES = ("PROPUESTA PREPARADA", "AJUSTES SOLICITADOS", "PROPUESTA REGENERADA")


def _dia_logo_institucional():
    """Recurso opcional local, sin depender de Internet ni modificar Storage."""
    from pathlib import Path
    raiz = Path(__file__).resolve().parent.parent
    for nombre in ("Logo_Yunpar_DIA.png", "Logo_Yunpar.png", "Logo_YUNPAR.png"):
        ruta = raiz / nombre
        if ruta.is_file():
            datos = ruta.read_bytes()
            return datos, _dia_validar_imagen(datos)
    raise FileNotFoundError("Coloca Logo_Yunpar_DIA.png en la carpeta raíz de YUNPAR, junto a App.py.")


def _dia_modo_automatico(referencias, *indicaciones, enlace=None):
    """Por seguridad no invertir logos o texto cuyo contenido no conocemos.

    Solo reflejar si se pide expresamente un espejo sin marcas visibles en los
    perfiles y no hay referencias de logos/zonas específicas ni enlace externo.
    """
    import re
    import unicodedata
    def normalizar(texto):
        return ''.join(c for c in unicodedata.normalize('NFD', str(texto or '').lower())
                       if unicodedata.category(c) != 'Mn')
    general = ' '.join(normalizar(t) for t in indicaciones)
    if enlace or not re.search(r'\b(?:simetric[oa]s?|espejo|identicos)\b', general):
        return "ind"
    if not re.search(r'\bsin (?:letras|logos|marcas|texto|numeros)\b', general):
        return "ind"
    for ref in referencias:
        if ref.get("zona") != "Referencia general":
            return "ind"
        if re.search(r'\b(?:logo|logotipo|escudo|patrocinador|texto|letras|numero|nombre)s?\b',
                     normalizar(ref.get("nombre")) + ' ' + normalizar(ref.get("indicacion"))):
            return "ind"
    # Cualquier solicitud de asimetría prevalece sobre el espejo.
    if re.search(r'\b(?:izquierd[oa]s?|derech[oa]s?|diferentes?|asimetric[oa]s?)\b', general):
        return "ind"
    # Si está expresamente descrita una prenda sin marcas, el espejo es fiel.
    return "sim"


def _dia_reflejar_lateral(datos):
    import io
    from PIL import Image, ImageOps
    with Image.open(io.BytesIO(datos)) as original:
        espejo = ImageOps.mirror(ImageOps.exif_transpose(original).convert("RGBA"))
        salida = io.BytesIO()
        espejo.save(salida, format="PNG")
        return salida.getvalue()



def _dia_modo_prueba():
    return os.environ.get("YUNPAR_DIA_MODO_PRUEBA", "0") == "1" or _cot_modo_prueba()


class _DiaConsultaPrueba(_CotConsultaPrueba):
    """Persistencia local exclusiva de Diseño IA, sin escrituras remotas."""
    def execute(self):
        if self.accion == "select":
            return super().execute()
        filas = self.datos[self.nombre]
        if self.accion == "insert":
            fila = deepcopy(self.payload)
            if any(r.get("codigo") == fila.get("codigo") for r in filas):
                raise ValueError("Código de diseño duplicado")
            fila["id"] = min([0] + [r["id"] for r in filas]) - 1
            fila.setdefault("created_at", _dia_now_iso())
            filas.append(fila)
            return SimpleNamespace(data=[deepcopy(fila)])
        if self.accion == "update" and self.filtros:
            salida = []
            for fila in filas:
                if all(f(fila) for f in self.filtros):
                    fila.update(deepcopy(self.payload))
                    salida.append(deepcopy(fila))
            return SimpleNamespace(data=salida)
        if self.accion == "delete" and self.filtros:
            borradas = [r for r in filas if all(f(r) for f in self.filtros)]
            filas[:] = [r for r in filas if not all(f(r) for f in self.filtros)]
            return SimpleNamespace(data=deepcopy(borradas))
        raise RuntimeError("Operación no permitida en prueba de Diseño IA")


class _DiaSupabasePrueba:
    def __init__(self, real):
        self.real = real
        self.datos = st.session_state.setdefault("_dia_prueba_datos", {_DIA_TABLE: []})

    def table(self, nombre):
        if nombre == _DIA_TABLE:
            return _DiaConsultaPrueba(nombre, self.datos)
        if nombre in {"clientes", "productos_catalogo"}:
            # El flujo únicamente necesita SELECT del catálogo real.
            return SimpleNamespace(select=self.real.table(nombre).select)
        raise RuntimeError("Tabla bloqueada en prueba de Diseño IA: " + nombre)


def _dia_referencias_disponibles(supabase):
    if isinstance(supabase, _DiaSupabasePrueba):
        return True
    try:
        supabase.table(_DIA_TABLE).select("referencias_imagenes").limit(1).execute()
        return True
    except Exception:
        return False


def _dia_guardadas(registro):
    refs = registro.get("referencias_imagenes")
    if isinstance(refs, list):
        validas = [r for r in refs if isinstance(r, dict) and r.get("url")]
        if validas:
            return validas
    # Compatibilidad con propuestas creadas antes de la migración.
    if registro.get("referencia_url"):
        return [{"url": registro["referencia_url"], "nombre": "Referencia original",
                 "zona": "Referencia general", "indicacion": ""}]
    return []


def _dia_origen_visual(url):
    if str(url or "").startswith("dia-prueba://"):
        archivo = st.session_state.get("_dia_prueba_archivos", {}).get(url)
        return archivo[0] if archivo else None
    return url


def _dia_validar_imagen(contenido):
    import io
    from PIL import Image
    if not contenido or len(contenido) > _DIA_MAX_BYTES:
        raise ValueError("Cada referencia debe pesar como máximo 8 MB.")
    with Image.open(io.BytesIO(contenido)) as imagen:
        mime = _DIA_FORMATOS.get(imagen.format)
        if not mime or imagen.width * imagen.height > 30_000_000:
            raise ValueError("Usa PNG, JPG o WEBP de hasta 30 megapíxeles.")
        imagen.verify()
    return mime


def _dia_imagen_para_gemini(contenido):
    # Conservamos el original en Storage; enviamos una copia optimizada a Gemini.
    import io
    from PIL import Image, ImageOps
    with Image.open(io.BytesIO(contenido)) as imagen:
        if imagen.width * imagen.height > 30_000_000:
            raise ValueError("La referencia excede 30 megapíxeles.")
        imagen = ImageOps.exif_transpose(imagen).convert("RGBA")
        imagen.thumbnail((1600, 1600))
        fondo = Image.new("RGB", imagen.size, "white")
        fondo.paste(imagen, mask=imagen.getchannel("A"))
        salida = io.BytesIO()
        fondo.save(salida, format="JPEG", quality=90)
        return salida.getvalue(), "image/jpeg"



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
    if isinstance(supabase, _DiaSupabasePrueba):
        prefijo = "DIA-PRUEBA-"
        filas = supabase.table(_DIA_TABLE).select("codigo").execute().data
        numeros = [int(r["codigo"][len(prefijo):]) for r in filas
                   if r.get("codigo", "").startswith(prefijo) and r["codigo"][len(prefijo):].isdigit()]
        siguiente = max(max(numeros, default=0), int(st.session_state.get("_dia_prueba_ultimo_codigo", 0))) + 1
        st.session_state["_dia_prueba_ultimo_codigo"] = siguiente
        return f"{prefijo}{siguiente:04d}"
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
    if isinstance(supabase, _DiaSupabasePrueba):
        url = f"dia-prueba://{carpeta}/{nombre_base}_{uuid.uuid4().hex[:10]}"
        st.session_state.setdefault("_dia_prueba_archivos", {})[url] = (bytes(contenido), mime)
        return url
    ext = _dia_extension_mime(mime)
    ruta = f"{carpeta}/{nombre_base}_{uuid.uuid4().hex[:10]}{ext}"
    supabase.storage.from_(_DIA_BUCKET).upload(
        path=ruta,
        file=bytes(contenido),
        file_options={"content-type": mime or "image/png"},
    )
    return supabase.storage.from_(_DIA_BUCKET).get_public_url(ruta)


def _dia_descargar_imagen(url):
    if str(url or "").startswith("dia-prueba://"):
        return st.session_state.get("_dia_prueba_archivos", {}).get(url, (None, None))
    if not url or not str(url).lower().startswith(("http://", "https://")):
        return None, None
    # Solo URLs públicas de imágenes; no acceder a servicios de la red interna.
    import ipaddress
    import socket
    from urllib.parse import urlsplit, urljoin
    try:
        destino = str(url)
        for _ in range(4):
            partes = urlsplit(destino)
            if partes.scheme not in {"http", "https"} or not partes.hostname or partes.username or partes.password:
                return None, None
            if partes.port not in (None, 80, 443):
                return None, None
            ips = socket.getaddrinfo(partes.hostname, partes.port or (443 if partes.scheme == "https" else 80))
            if not ips or any(not ipaddress.ip_address(i[4][0]).is_global for i in ips):
                return None, None
            with requests.get(destino, timeout=(5, 15), stream=True, allow_redirects=False) as resp:
                if resp.is_redirect:
                    destino = urljoin(destino, resp.headers["Location"])
                    continue
                resp.raise_for_status()
                mime = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
                if mime and not mime.startswith("image/") and mime != "application/octet-stream":
                    return None, None
                datos = bytearray()
                for fragmento in resp.iter_content(65536):
                    datos.extend(fragmento)
                    if len(datos) > 16 * 1024 * 1024:
                        return None, None
                return (bytes(datos), mime or "image/png") if datos else (None, None)
    except Exception:
        pass
    return None, None

def _dia_generar_imagen_gemini(registro):
    """Genera cuatro vistas individuales y las compone en una sola lámina comercial."""
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
    brief = registro.get("instrucciones") or "Seguir las referencias visuales y las indicaciones individuales; no inventar cambios."
    ajuste = registro.get("ajuste_solicitado") or ""
    referencias = registro.get("referencias_locales")
    if referencias is None:
        referencias = _dia_guardadas(registro)
    modo = _dia_modo_automatico(referencias, registro.get("instrucciones"), ajuste,
                                 enlace=registro.get("referencia_link"))
    regla_laterales = (
        "Los costados deben ser simétricos en su tela, paneles, rayas y colores. "
        "La vista izquierda se reflejará por código; no dibujes letras, logos ni números visibles en el perfil. "
        "Respeta los logos frontales y posteriores en sus propias vistas."
        if modo == "sim" else
        "Los perfiles conservarán los mismos cortes, costuras, paneles y proporciones de color a ambos lados, "
        "excepto las diferencias expresamente solicitadas. Los logos y textos deben estar orientados correctamente, nunca invertidos. "
        "Si ambos costados son iguales, conserva EXACTAMENTE la distribución de tela, rayas, ancho y altura de paneles "
        "del perfil ya generado; cambia únicamente el ángulo y las marcas que correspondan. No inviertas letras."
    )

    prompt = f"""
Crea una vista de boceto comercial de UNA MISMA prenda, para aprobación del cliente.
No es arte técnico definitivo para impresión.

PRENDA: {producto}
TÉCNICA: {tecnica}
COLORES: {colores}
INDICACIONES GENERALES: {brief}
AJUSTE DE ESTA REVISIÓN: {ajuste or 'Sin ajustes adicionales.'}

REGLAS COMUNES PARA TODAS LAS VISTAS:
- Fondo blanco, una sola prenda completa, centrada, sin recortes ni objetos extra.
- Sin modelos humanos, sin maniquí visible, sin fondos decorativos, sin rótulos ni collage.
- Conserva el mismo corte, cuello, costuras, logos, colores y proporciones de la prenda.
- {regla_laterales}
- Izquierda y derecha corresponden a quien lleva la prenda, no al observador. En FRENTE, el pecho derecho aparece a la izquierda de la imagen; el pecho izquierdo a la derecha.
- Un logo indicado para el pecho derecho (por ejemplo YUNPAR) debe quedar en el pecho derecho de quien viste la prenda. En LATERAL DERECHO conserva la parte del logo de ese pecho que resulte naturalmente visible desde ese ángulo; no lo omitas si está a la vista. No lo dupliques ni lo traslades a la manga para hacerlo visible.
- Aplica la regla equivalente al pecho izquierdo y su lateral. Un logo centrado puede verse parcialmente en ambos perfiles dependiendo de su tamaño y ubicación. En una vista posterior no dibujes un logo de pecho.
- Un logo pedido en ambas mangas debe aparecer correctamente orientado en ambas mangas, y en el perfil correspondiente. Nunca intercambies los escudos o marques solo una manga.
- Aplica cada logo y detalle SOLO en las posiciones indicadas por el cliente. Respeta su forma, texto y colores salvo cambio solicitado.
- La solicitud de ajuste más reciente prevalece sobre las indicaciones anteriores en aquello que cambia.
- Una indicación escrita explícita de una imagen prevalece sobre su etiqueta de zona si hay conflicto.
- Si se pide quitar rayas, cambiar color o logo, aplica el cambio a todas las vistas afectadas.
- Conserva todo lo anterior que no se ha pedido cambiar.
- Las imágenes siguientes se acompañan de una descripción de su uso.
- No copies flechas, recuadros ni anotaciones de referencia al tejido.
- No inventes patrocinadores, nombres, números, escudos o adornos no solicitados.
- Si se proporciona una lámina anterior con varias vistas, no la reproduzcas entera: úsala solo como referencia de diseño.
- Si se adjunta una vista nueva ya generada en esta misma revisión, úsala como guía de identidad visual.
- La vista solicitada al final del mensaje es la única que debes generar.
""".strip()

    contenido = [{"type": "text", "text": prompt}]
    if len(referencias) > _DIA_MAX_REFERENCIAS:
        raise ValueError("Máximo 8 referencias por propuesta.")

    def agregar_imagen(datos, etiqueta):
        if not datos:
            raise ValueError(f"No se pudo cargar {etiqueta}. Revisa la imagen de referencia.")
        optimizada, mime = _dia_imagen_para_gemini(datos)
        contenido.extend([
            {"type": "text", "text": etiqueta},
            {"type": "image", "data": base64.b64encode(optimizada).decode("ascii"), "mime_type": mime},
        ])

    for i, ref in enumerate(referencias, 1):
        datos = ref.get("bytes")
        if not datos:
            datos, _ = _dia_descargar_imagen(ref.get("url"))
        zona = ref.get('zona') or 'Referencia general'
        indicacion = ref.get('indicacion') or 'Seguir referencia y brief'
        orientacion = {
            'Pecho derecho': 'Derecha de quien usa la prenda (izquierda del observador en el frente). Mantener en el lateral derecho donde sea visible.',
            'Pecho izquierdo': 'Izquierda de quien usa la prenda (derecha del observador en el frente). Mantener en el lateral izquierdo donde sea visible.',
            'Centro del pecho': 'En el centro del delantero, visible parcialmente de perfil si corresponde.',
            'Ambas mangas': 'En las dos mangas, sin reflejar letras ni deformar el logo.',
        }.get(zona, '')
        agregar_imagen(datos, f"Referencia {i}: {ref.get('nombre', '')}. Zona: {zona}. "
                       f"Indicación: {indicacion}. {orientacion}")

    enlace = registro.get("referencia_link")
    if enlace:
        datos_link, _ = _dia_descargar_imagen(enlace)
        if datos_link:
            agregar_imagen(datos_link, "Referencia adicional del enlace directo del cliente.")
        elif not referencias:
            raise ValueError("El enlace no devuelve una imagen accesible. Descarga la imagen y adjúntala.")
        else:
            st.warning("El enlace externo no es una imagen accesible. Se usarán las imágenes adjuntas; "
                       "para analizar ese enlace, sube su imagen directamente.")
    if not referencias and not enlace:
        raise ValueError("Adjunta al menos una referencia.")

    if registro.get("propuesta_url"):
        anterior, _ = _dia_descargar_imagen(registro["propuesta_url"])
        if not anterior:
            raise ValueError("No se pudo recuperar la propuesta anterior para mantener su coherencia.")
        agregar_imagen(anterior, "Propuesta anterior: úsala como base del ajuste, sin perder las referencias originales.")
    cliente = genai.Client(api_key=api_key)
    vistas = []
    anclas = []
    for rotulo, instruccion_vista in _DIA_VISTAS:
        if rotulo == "LATERAL DERECHO" and modo == "sim":
            # Misma geometría y colores, sin reinterpretación de Gemini.
            vistas.append((rotulo, _dia_reflejar_lateral(vistas[-1][1])))
            continue
        entrada = list(contenido) + list(anclas) + [{
            "type": "text",
            "text": (f"VISTA EXCLUSIVA: {rotulo}. {instruccion_vista} "
                     "Devuelve exactamente UNA imagen con UNA sola prenda vista desde ese ángulo. "
                     "No dibujes otras vistas, no hagas cuadrícula, no escribas etiquetas. "
                     "Se compondrá la lámina por código después."),
        }]
        if sum(len(p.get("data", "")) for p in entrada) > 15 * 1024 * 1024:
            raise ValueError("Las referencias exceden el tamaño combinado permitido. Reduce sus dimensiones.")
        try:
            interaction = cliente.interactions.create(
                model="gemini-nano-banana-2.1",
                input=entrada,
                response_format={"type": "image", "aspect_ratio": "4:5"},
            )
            salida = interaction.output_image.data if interaction and interaction.output_image else None
            if not salida:
                raise RuntimeError("Gemini no devolvió una imagen.")
            if isinstance(salida, str):
                salida = base64.b64decode(salida, validate=True)
            salida = bytes(salida)
            with Image.open(io.BytesIO(salida)) as img:
                if img.format not in _DIA_FORMATOS or img.width * img.height > 30_000_000:
                    raise ValueError("Formato o tamaño de imagen de salida no válido.")
                img.verify()
            if any(salida == datos for _, datos in vistas):
                raise ValueError("Gemini devolvió una imagen idéntica a otra vista.")
            vistas.append((rotulo, salida))
            # Las tres vistas previas sirven de anclas para el perfil derecho independiente.
            if rotulo in {"FRENTE", "ESPALDA"} or (rotulo == "LATERAL IZQUIERDO" and modo == "ind"):
                optimizada, mime = _dia_imagen_para_gemini(salida)
                anclas.extend([
                    {"type": "text", "text": f"Vista {rotulo} NUEVA de esta misma revisión: conserva su diseño, pero no repitas su ángulo."},
                    {"type": "image", "data": base64.b64encode(optimizada).decode("ascii"), "mime_type": mime},
                ])
        except Exception as e:
            raise RuntimeError(f"No se completó la vista {rotulo}. No se guardó una lámina incompleta. Detalle: {e}") from e
    return _dia_componer_lamina(vistas)


_DIA_VISTAS = (
    ("FRENTE", "Vista frontal recta: muestra el pecho, el cuello delantero y ambas mangas de frente."),
    ("ESPALDA", "Vista posterior recta: muestra exclusivamente la espalda y el cuello posterior."),
    ("LATERAL IZQUIERDO", "Perfil ortogonal izquierdo de quien lleva la prenda, girado 90 grados; solo el costado y la manga izquierda predominan. Conserva los logos del pecho izquierdo donde sean naturalmente visibles, sin trasladarlos a la manga. No mostrar pecho ni espalda completos."),
    ("LATERAL DERECHO", "Perfil ortogonal derecho de quien lleva la prenda, girado 90 grados en sentido opuesto al lateral izquierdo; solo el costado y la manga derecha predominan. Comprueba el FRENTE nuevo para conservar el logo del pecho derecho en la superficie delantera donde naturalmente sea visible desde este perfil, sin trasladarlo a la manga. Replica los paneles y colores del lateral izquierdo salvo diferencias solicitadas. No mostrar pecho ni espalda completos."),
)


def _dia_componer_lamina(vistas):
    """Composición determinista 2 x 2: etiquetas y posiciones controladas por Python."""
    import io
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    if [rotulo for rotulo, _ in vistas] != [rotulo for rotulo, _ in _DIA_VISTAS]:
        raise ValueError("La propuesta debe contener las cuatro vistas en su orden correcto.")
    ancho, alto = 1800, 1400
    lamina = Image.new("RGB", (ancho, alto), "white")
    dibujo = ImageDraw.Draw(lamina)
    fuente = None
    for nombre in ("DejaVuSans.ttf", "arial.ttf", "Arial.ttf"):
        try:
            fuente = ImageFont.truetype(nombre, 32)
            break
        except OSError:
            continue
    if fuente is None:
        fuente = ImageFont.load_default()
    for i, (rotulo, datos) in enumerate(vistas):
        x, y = (i % 2) * 900, (i // 2) * 700
        with Image.open(io.BytesIO(datos)) as original:
            rgba = ImageOps.exif_transpose(original).convert("RGBA")
            blanca = Image.new("RGB", rgba.size, "white")
            blanca.paste(rgba, mask=rgba.getchannel("A"))
            imagen = ImageOps.contain(blanca, (850, 610), Image.Resampling.LANCZOS)
        lamina.paste(imagen, (x + (900 - imagen.width) // 2, y + 15 + (610 - imagen.height) // 2))
        caja = dibujo.textbbox((0, 0), rotulo, font=fuente)
        dibujo.text((x + (900 - (caja[2] - caja[0])) // 2 - caja[0], y + 645 - caja[1]),
                     rotulo, font=fuente, fill=(32, 32, 32))
    salida = io.BytesIO()
    lamina.save(salida, format="JPEG", quality=95, subsampling=0)
    return salida.getvalue(), "image/jpeg"


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


def _dia_limpiar_formulario(abrir=True, activo=None):
    # Nueva identidad de widgets: Streamlit no recupera valores del formulario anterior.
    for key in list(st.session_state.keys()):
        if key.startswith(("dia_form_", "dia_ajuste_", "dia_propuesta_activa", "dia_confirmar_vistas_")) or key in {
            "dia_cliente", "dia_producto", "dia_tecnica", "dia_colores", "dia_ref_link",
            "dia_instrucciones", "dia_ref_img", "dia_fecha_entrega"
        }:
            st.session_state.pop(key, None)
    st.session_state.pop("_dia_borrar_pendiente", None)
    st.session_state["_dia_epoch"] = int(st.session_state.get("_dia_epoch", 0)) + 1
    st.session_state["_dia_form_abierto"] = abrir
    st.session_state["_diseno_ia_actual"] = activo


def _dia_accion_formulario(accion):
    _dia_limpiar_formulario(abrir=accion != "cancelar")
    st.session_state.pop("_dia_mensaje", None)
    st.session_state["_dia_aviso"] = {
        "nueva": "Nuevo diseño: formulario listo para completar.",
        "limpiar": "Formulario limpio. Puedes comenzar de nuevo; el historial no se ha borrado.",
        "cancelar": "Edición cancelada. Abre un diseño del historial o presiona Nueva o Limpiar.",
    }[accion]


def _dia_seleccionar_propuesta(codigo):
    """Abre la propuesta elegida, con widgets nuevos y sin borrar registros guardados."""
    _dia_limpiar_formulario(abrir=False, activo=codigo or None)
    st.session_state.pop("_dia_mensaje", None)
    st.session_state.pop("_dia_aviso", None)


def _dia_cambiar_selector(clave):
    codigo = st.session_state.get(clave)
    _dia_seleccionar_propuesta(codigo)


def _dia_puede_eliminar(registro):
    return (registro.get("estado") in _DIA_ESTADOS_ELIMINABLES
            and registro.get("orden_id") is None and registro.get("cotizacion_id") is None
            and not registro.get("fecha_aprobacion") and not registro.get("fecha_envio_diseno"))


def _dia_borrar_propuesta(supabase, codigo, registro_id):
    """Borra solo borradores no vinculados; nunca órdenes ni cotizaciones."""
    local = isinstance(supabase, _DiaSupabasePrueba)
    if _dia_modo_prueba() != local:
        raise RuntimeError("Modo de persistencia incorrecto; no se eliminó nada.")
    registro = _dia_buscar_registro_db(supabase, codigo)
    if not registro or registro.get("id") != registro_id or not _dia_puede_eliminar(registro):
        raise ValueError("El diseño ya no existe, fue aprobado o está vinculado a otro módulo.")
    consulta = (supabase.table(_DIA_TABLE).delete().eq("id", registro_id).eq("codigo", codigo)
                .eq("estado", registro["estado"]).eq("revision", registro.get("revision")))
    if not local:
        consulta = (consulta.is_("orden_id", "null").is_("cotizacion_id", "null")
                    .is_("fecha_aprobacion", "null").is_("fecha_envio_diseno", "null"))
    else:
        for campo in ("orden_id", "cotizacion_id", "fecha_aprobacion", "fecha_envio_diseno"):
            consulta = consulta.eq(campo, None)
    respuesta = consulta.execute()
    if not respuesta.data or len(respuesta.data) != 1:
        raise RuntimeError("No se confirmó la eliminación; el diseño pudo haber cambiado.")
    if local:
        archivos = st.session_state.get("_dia_prueba_archivos", {})
        prefijo = f"dia-prueba://disenos-ia/{codigo}/"
        for url in list(archivos):
            if url.startswith(prefijo):
                archivos.pop(url, None)
        return None
    # En producción no borrar carpetas completas: podría haber archivos de otra
    # revisión o un código reutilizado. Solo los objetos registrados en esta fila.
    from urllib.parse import urlsplit, unquote
    urls = {r.get("url") for r in _dia_guardadas(registro)}
    urls.update((registro.get("referencia_url"), registro.get("propuesta_url")))
    rutas = []
    prefijo = f"disenos-ia/{codigo}/"
    marcador = f"/storage/v1/object/public/{_DIA_BUCKET}/"
    try:
        bucket = supabase.storage.from_(_DIA_BUCKET)
        for url in urls:
            if not url:
                continue
            partes = urlsplit(url)
            if marcador not in partes.path:
                continue
            ruta = unquote(partes.path.split(marcador, 1)[1])
            if not ruta.startswith(prefijo) or '/' in ruta[len(prefijo):] or not ruta[len(prefijo):]:
                continue
            if ruta[len(prefijo):] in {'.', '..'} or '\\' in ruta:
                continue
            canon = urlsplit(bucket.get_public_url(ruta))
            if (partes.scheme, partes.netloc, unquote(partes.path)) == (canon.scheme, canon.netloc, unquote(canon.path)):
                rutas.append(ruta)
        if rutas:
            bucket.remove(sorted(set(rutas)))
    except Exception:
        return "Diseño eliminado. No se pudo confirmar la limpieza de archivos en Storage."
    return None


def _dia_confirmar_borrado(supabase, codigo, registro_id):
    try:
        aviso = _dia_borrar_propuesta(supabase, codigo, registro_id)
        if st.session_state.get("_diseno_ia_actual") == codigo:
            _dia_limpiar_formulario(abrir=False)
        st.session_state.pop("_dia_borrar_pendiente", None)
        st.session_state.pop("_dia_aviso", None)
        st.session_state["_dia_mensaje"] = f"{codigo} eliminado del historial."
        if aviso:
            st.session_state["_dia_aviso"] = aviso
    except Exception as e:
        st.session_state["_dia_aviso"] = f"No se pudo eliminar {codigo}: {e}"
        st.session_state.pop("_dia_borrar_pendiente", None)


def _dia_historial(supabase, registros):
    st.divider()
    st.markdown("#### Historial de diseños")
    st.caption("Propuestas guardadas en memoria local." if _dia_modo_prueba() else "Propuestas guardadas en Supabase.")
    st.caption("Se muestran todos los estados, incluidas las propuestas aprobadas y enviadas.")
    for i in range(0, len(registros), 3):
        fila = registros[i:i + 3]
        for col, r in zip(st.columns(len(fila)), fila):
            with col:
                with st.container(border=True):
                    icon = {
                        "PROPUESTA PREPARADA": "🟡", "AJUSTES SOLICITADOS": "🟠",
                        "PROPUESTA REGENERADA": "🟣", "APROBADO POR CLIENTE": "🟢",
                        "ENVIADO A DISEÑADOR": "🔵",
                    }.get(r.get("estado"), "⚪")
                    titulo, tacho = st.columns([4, 1])
                    titulo.markdown(f"**{icon} {r.get('codigo', '')}**")
                    codigo = r.get("codigo")
                    if codigo:
                        tacho.button("🗑️", key=f"dia_hist_borrar_{r.get('id')}_{codigo}",
                                     help="Eliminar propuesta no aprobada" if _dia_puede_eliminar(r) else
                                     "Protegido: propuesta aprobada o vinculada a otro módulo",
                                     disabled=not _dia_puede_eliminar(r), use_container_width=True,
                                     on_click=lambda c=codigo: st.session_state.update({"_dia_borrar_pendiente": c}))
                    st.caption(r.get("cliente_nombre") or "Sin cliente")
                    st.write(" | ".join([x for x in [r.get("producto_codigo"), r.get("producto_descripcion")] if x]) or "Sin producto")
                    st.markdown(f"**Estado:** {r.get('estado', '')}")
                    extras = [f"Revisión {r.get('revision', 1)}"]
                    if r.get("orden_id"):
                        extras.append(f"Orden #{r.get('orden_id')}")
                    if r.get("cotizacion_id"):
                        extras.append(f"Cotización #{r.get('cotizacion_id')}")
                    st.caption(" · ".join(extras))
                    codigo = r.get("codigo")
                    if codigo:
                        seleccionado = codigo == st.session_state.get("_diseno_ia_actual")
                        st.button("Abierta" if seleccionado else "📂 Abrir diseño",
                                  key=f"dia_hist_abrir_{r.get('id')}_{codigo}",
                                  use_container_width=True, disabled=seleccionado,
                                  on_click=_dia_seleccionar_propuesta, args=(codigo,))
                        if st.session_state.get("_dia_borrar_pendiente") == codigo and _dia_puede_eliminar(r):
                            st.warning(f"¿Eliminar {codigo}? Esta acción no se puede deshacer.")
                            si, no = st.columns(2)
                            si.button("Eliminar", type="primary", use_container_width=True,
                                      key=f"dia_hist_confirmar_{r.get('id')}_{codigo}",
                                      on_click=_dia_confirmar_borrado, args=(supabase, codigo, r.get('id')))
                            no.button("Conservar", use_container_width=True,
                                      key=f"dia_hist_conservar_{r.get('id')}_{codigo}",
                                      on_click=lambda: st.session_state.pop("_dia_borrar_pendiente", None))


def _dia_crear_orden_para_disenador(supabase, registro, productos):
    if isinstance(supabase, _DiaSupabasePrueba) or _dia_modo_prueba():
        raise RuntimeError("Envío al diseñador bloqueado en modo prueba.")
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
    for ref in _dia_guardadas(registro):
        observaciones.append(f"Referencia {ref.get('nombre', '')} ({ref.get('zona', '')}): "
                             f"{ref.get('indicacion', '')} — {ref.get('url', '')}")

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

    if _dia_modo_prueba():
        st.caption("MODO PRUEBA LOCAL · Diseño IA: no escribe en Supabase ni crea órdenes. "
                   "La generación sí usa Gemini y puede consumir cuota.")
        supabase = _DiaSupabasePrueba(supabase)
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

    epoch = st.session_state.get("_dia_epoch", 0)
    pref = f"dia_form_{epoch}_"
    abierto = st.session_state.get("_dia_form_abierto", True)
    refs_ok = _dia_referencias_disponibles(supabase)
    if not refs_ok:
        st.warning("Falta habilitar referencias_imagenes en Supabase. Ejecuta la migración "
                   "sql/disenos_ia_referencias_multiples.sql antes de generar nuevas propuestas.")

    cab1, cab2, cab3, cab4 = st.columns([3, 1, 1, 1])
    cab1.markdown("#### 1️⃣ Datos del cliente y referencias")
    cab2.button("🆕 Nueva", use_container_width=True, key="dia_nueva_propuesta",
                on_click=_dia_accion_formulario, args=("nueva",))
    cab3.button("🧹 Limpiar", use_container_width=True, key="dia_limpiar",
                help="Vacía y abre el formulario, sin borrar diseños guardados.",
                on_click=_dia_accion_formulario, args=("limpiar",))
    cab4.button("✖ Cancelar", use_container_width=True, key="dia_cancelar",
                help="Cierra el formulario y la revisión activa sin borrar diseños guardados.",
                on_click=_dia_accion_formulario, args=("cancelar",))

    api_ok = bool(_dia_api_key_gemini())
    mensaje = st.session_state.pop("_dia_mensaje", None)
    if mensaje:
        st.success(mensaje)
    aviso = st.session_state.get("_dia_aviso")
    if aviso:
        st.info(aviso)

    if abierto:
        c1, c2 = st.columns(2)
        with c1:
            sel_cliente = st.selectbox("Cliente *", list(mapa_clientes.keys()), index=None,
                                       placeholder="Seleccionar cliente", key=pref + "cliente")
            sel_producto = st.selectbox("Prenda / producto de referencia", ["Sin definir"] + list(mapa_productos.keys()),
                                        key=pref + "producto")
            tecnica = st.selectbox("Técnica prevista", ["Por definir", "Sublimado", "DTF", "Bordado", "Mixto"],
                                   key=pref + "tecnica")
            colores = st.text_input("Colores solicitados", placeholder="Ej: rojo, logos blancos", key=pref + "colores")
            fecha_entrega = st.date_input("Fecha estimada de entrega (opcional)", value=None,
                                          key=pref + "fecha_entrega")
            st.caption("Si no eliges fecha, se estima una semana desde hoy.")
        with c2:
            archivos = st.file_uploader("📷 Imágenes enviadas por el cliente",
                                        type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True,
                                        key=pref + "referencias") or []
            st.caption(f"{len(archivos)} de {_DIA_MAX_REFERENCIAS} archivos subidos · 8 MB máximo por archivo. "
                       "Usa la X junto al nombre para quitar una imagen.")
            ref_link = st.text_input("🔗 Enlace de imagen directa (opcional)", placeholder="https://.../logo.png",
                                     key=pref + "enlace")
            st.caption("Si el cliente envía una página web, descarga el logo y adjúntalo como imagen.")
            usar_logo = st.checkbox("Agregar logo institucional YUNPAR", key=pref + "usar_logo",
                                    help="Solo se adjunta si marcas esta opción. Cuenta como una referencia.")

        referencias = []
        errores_refs = []
        if len(archivos) + int(usar_logo) > _DIA_MAX_REFERENCIAS:
            errores_refs.append(f"Selecciona máximo {_DIA_MAX_REFERENCIAS} imágenes, incluido el logo YUNPAR si lo agregas.")
        else:
            import hashlib
            for indice, archivo in enumerate(archivos, 1):
                try:
                    if getattr(archivo, "size", 0) > _DIA_MAX_BYTES:
                        raise ValueError("Cada referencia debe pesar como máximo 8 MB.")
                    datos = archivo.getvalue()
                    mime = _dia_validar_imagen(datos)
                    # file_id mantiene estables las indicaciones incluso si se quita otra imagen.
                    ident = getattr(archivo, "file_id", None) or hashlib.sha256(datos + archivo.name.encode()).hexdigest()
                    # En caso de archivos idénticos con el mismo identificador, evitar widgets duplicados.
                    if any(r["ident"] == ident for r in referencias):
                        continue
                    with st.container(border=True):
                        mini, info = st.columns([1, 2])
                        mini.image(datos, caption=f"{indice}. {archivo.name}", use_container_width=True)
                        zona = info.selectbox("Ubicación / uso", _DIA_ZONAS, key=pref + f"zona_{ident}",
                                              help="Derecha e izquierda desde la perspectiva de quien lleva la camiseta.")
                        indicacion = info.text_input("¿Qué hacer con esta imagen?", key=pref + f"indicacion_{ident}",
                                                    placeholder="Ej: poner este logo en blanco en la manga")
                    referencias.append({"ident": ident, "nombre": archivo.name, "zona": zona,
                                        "indicacion": indicacion.strip(), "bytes": datos, "mime": mime})
                except Exception as e:
                    errores_refs.append(f"{archivo.name}: {e}")
        if usar_logo and not errores_refs:
            try:
                datos_logo, mime_logo = _dia_logo_institucional()
                with st.container(border=True):
                    mini, info = st.columns([1, 2])
                    mini.image(datos_logo, caption="Logo institucional YUNPAR", use_container_width=True)
                    zona_logo = info.selectbox("Ubicación del logo YUNPAR", _DIA_ZONAS, index=2,
                                              key=pref + "logo_zona",
                                              help="Derecha e izquierda desde la perspectiva de quien lleva la camiseta.")
                    indicacion_logo = info.text_input("Indicaciones del logo YUNPAR", key=pref + "logo_indicacion",
                                                     placeholder="Ej: pequeño, en el pecho derecho")
                referencias.append({"ident": "yunpar_institucional", "nombre": "Logo YUNPAR.png",
                                    "zona": zona_logo, "indicacion": indicacion_logo.strip() or
                                    "Colocar el logo YUNPAR en la zona seleccionada, respetando su identidad y texto.",
                                    "bytes": datos_logo, "mime": mime_logo})
            except Exception as e:
                errores_refs.append(f"Logo institucional: {e}")
        for error in errores_refs:
            st.error(error)

        instrucciones = st.text_area("✍️ ¿Qué desea el cliente? (opcional)", height=130, key=pref + "instrucciones",
                                     placeholder="Ej: camiseta roja, quitar rayas negras y blancas, cuello redondo rojo, "
                                                 "logos blancos según las referencias adjuntas.")
        st.caption("Puedes dejar las indicaciones generales vacías. Se usarán las referencias y sus indicaciones individuales.")
        st.markdown("#### 2️⃣ Preparar propuesta")
        modo_laterales = _dia_modo_automatico(referencias, instrucciones, enlace=ref_link.strip())
        st.caption("Se generarán automáticamente cuatro vistas de la misma prenda. "
                   "Revisa ángulos, posiciones, logos y colores antes de aprobar.")
        if api_ok:
            st.caption("✅ Gemini configurado para generar la propuesta visual.")
        else:
            st.error("Gemini no está configurado. Agregue [gemini][api_key] en secrets.toml.")
        if st.button("✨ PREPARAR PROPUESTA CON IA", type="primary", use_container_width=True,
                     key="dia_generar", disabled=not api_ok or bool(errores_refs) or not refs_ok):
            errores = []
            if not sel_cliente:
                errores.append("selecciona un cliente")
            if not referencias and not ref_link.strip():
                errores.append("sube al menos una imagen o agrega un enlace directo")
            if errores:
                st.error("Antes de continuar: " + "; ".join(errores) + ".")
            else:
                cliente = mapa_clientes[sel_cliente]
                prod = mapa_productos.get(sel_producto)
                codigo = _dia_codigo_siguiente(supabase)
                registro_local = {
                    "codigo": codigo, "cliente_id": cliente.get("id"),
                    "cliente": cliente.get("nombre_completo", ""),
                    "producto_id": prod.get("id") if prod else None,
                    "producto": f"{prod.get('codigo_referencia', '')} | {prod.get('descripcion', '')}" if prod else "Sin definir",
                    "tecnica": tecnica, "colores": colores.strip(), "instrucciones": instrucciones.strip(),
                    "referencia_link": ref_link.strip() or None, "referencias_locales": referencias,
                    "ajuste_solicitado": "", "modo_laterales": modo_laterales,
                }
                try:
                    with st.spinner("Gemini está preparando las cuatro vistas de la prenda..."):
                        propuesta_bytes, propuesta_mime = _dia_generar_imagen_gemini(registro_local)
                    refs_guardadas = []
                    for indice, ref in enumerate(referencias, 1):
                        url = _dia_subir_bytes(supabase, ref["bytes"], ref["mime"], f"disenos-ia/{codigo}", f"referencia_{indice}")
                        if not url:
                            raise RuntimeError("No se pudo guardar una referencia.")
                        refs_guardadas.append({"url": url, "nombre": ref["nombre"], "zona": ref["zona"],
                                               "indicacion": ref["indicacion"]})
                    propuesta_url = _dia_subir_bytes(supabase, propuesta_bytes, propuesta_mime, f"disenos-ia/{codigo}", f"propuesta_4v_r1_{modo_laterales}")
                    if not propuesta_url:
                        raise RuntimeError("No se pudo guardar la lámina.")
                    payload = {
                        "codigo": codigo, "cliente_id": cliente.get("id"), "cliente_nombre": cliente.get("nombre_completo", ""),
                        "producto_id": prod.get("id") if prod else None,
                        "producto_codigo": prod.get("codigo_referencia") if prod else None,
                        "producto_descripcion": prod.get("descripcion") if prod else "Sin definir",
                        "tecnica": tecnica, "colores": colores.strip(), "instrucciones": instrucciones.strip(),
                        "referencia_url": refs_guardadas[0]["url"] if refs_guardadas else None,
                        "referencias_imagenes": refs_guardadas, "referencia_link": ref_link.strip() or None,
                        "propuesta_url": propuesta_url, "generacion_real": True, "estado": "PROPUESTA PREPARADA",
                        "revision": 1, "ajuste_solicitado": "",
                        "fecha_entrega_estimada": str(fecha_entrega or datetime.date.today() + datetime.timedelta(days=7)),
                        "creado_por_id": st.session_state.get("id_usuario"), "updated_at": _dia_now_iso(),
                    }
                    ins = supabase.table(_DIA_TABLE).insert(payload).execute()
                    if not ins.data:
                        raise RuntimeError("No se pudo confirmar el registro de la propuesta.")
                    _dia_limpiar_formulario(abrir=False, activo=codigo)
                    st.session_state.pop("_dia_aviso", None)
                    st.session_state["_dia_mensaje"] = f"{codigo} creado y guardado correctamente."
                    _dia_rerun_local()
                    return
                except Exception as e:
                    st.error(f"No se pudo preparar la propuesta: {e}")
    else:
        st.caption("Formulario cerrado. Presiona Nueva o Limpiar para iniciar otro diseño; el historial permanece disponible.")


    registros = _dia_cargar_registros(supabase)
    if not registros:
        st.caption("Aún no hay propuestas registradas.")
        return

    st.markdown("#### 3️⃣ Revisión con el cliente")
    codigos = [r.get("codigo") for r in registros if r.get("codigo")]
    actual = st.session_state.get("_diseno_ia_actual")
    opciones = [""] + codigos
    selector_key = f"dia_propuesta_activa_{epoch}"
    # No recalcular index con la selección del último rerun: puede cambiar la identidad
    # del widget en versiones de Streamlit y restaurar la propuesta anterior.
    if selector_key not in st.session_state or st.session_state[selector_key] not in opciones:
        st.session_state[selector_key] = actual if actual in opciones else ""
    codigo_sel = st.selectbox(
        "Propuesta activa", opciones, index=0, key=selector_key,
        format_func=lambda c: c or "Seleccionar propuesta del historial",
        on_change=_dia_cambiar_selector, args=(selector_key,)
    )
    st.caption("Puedes elegir cualquier diseño aquí o usar Abrir diseño en su tarjeta del historial, incluso si está aprobado. Abrir uno descarta el formulario no guardado.")
    st.session_state["_diseno_ia_actual"] = codigo_sel or None
    if not codigo_sel:
        _dia_historial(supabase, registros)
        return
    registro = _dia_buscar_registro_db(supabase, codigo_sel)
    if not registro:
        st.warning("No se pudo cargar la propuesta seleccionada.")
        _dia_historial(supabase, registros)
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

    st.markdown("**Referencias originales del cliente**")
    refs_hist = _dia_guardadas(registro)
    if refs_hist:
        for i in range(0, len(refs_hist), 3):
            fila = refs_hist[i:i+3]
            for col, ref in zip(st.columns(len(fila)), fila):
                with col:
                    origen = _dia_origen_visual(ref.get("url"))
                    if origen:
                        try:
                            st.image(origen, caption=ref.get("nombre") or "Referencia", use_container_width=True)
                        except Exception:
                            st.caption("No se pudo mostrar esta referencia.")
                    st.caption(ref.get("zona") or "Referencia general")
                    if ref.get("indicacion"):
                        st.write(ref["indicacion"])
    if registro.get("referencia_link"):
        st.write("Enlace original:", registro["referencia_link"])
    if not refs_hist and not registro.get("referencia_link"):
        st.caption("Sin referencia visual guardada.")

    st.markdown("**Lámina de propuesta IA**")
    if registro.get("propuesta_url"):
        st.image(_dia_origen_visual(registro["propuesta_url"]),
                 caption=f"{registro.get('codigo')} · Revisión {registro.get('revision', 1)}", use_container_width=True)
        st.caption("Revisa que los cuatro ángulos sean distintos y que los detalles coincidan antes de aprobar. "
                   "Las propuestas anteriores pueden no tener las cuatro vistas; pueden regenerarse mientras estén sin aprobar.")
    else:
        st.warning("No hay propuesta visual almacenada.")

    producto_txt = " | ".join([x for x in [registro.get("producto_codigo"), registro.get("producto_descripcion")] if x]) or "Sin definir"
    with st.expander("Datos e indicaciones del cliente", expanded=True):
        st.write(f"**Cliente:** {registro.get('cliente_nombre', '')}")
        st.write(f"**Producto:** {producto_txt}")
        st.write(f"**Técnica:** {registro.get('tecnica') or 'Por definir'}")
        st.write(f"**Colores:** {registro.get('colores') or 'No especificados'}")
        st.write(f"**Revisión:** {registro.get('revision', 1)}")
        st.write("**Brief:**")
        st.write(registro.get("instrucciones") or "Sin indicaciones generales; se utilizaron las referencias.")


    ajuste_key = f"dia_ajuste_{epoch}_{registro.get('codigo')}"
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

    puede_aprobar = estado_actual in ["PROPUESTA PREPARADA", "PROPUESTA REGENERADA"] and bool(registro.get("propuesta_url"))
    if puede_aprobar and "/propuesta_4v_r" in str(registro.get("propuesta_url") or ""):
        revisadas = st.checkbox("Verifiqué frente, espalda y ambos laterales; los cuatro ángulos y sus detalles son correctos.",
                                key=f"dia_confirmar_vistas_{epoch}_{registro.get('codigo')}_{registro.get('revision')}")
        puede_aprobar = puede_aprobar and revisadas

    puede_regenerar = estado_actual == "AJUSTES SOLICITADOS" and api_ok
    modo_regen = _dia_modo_automatico(_dia_guardadas(registro), registro.get("instrucciones"),
                                      registro.get("ajuste_solicitado"), enlace=registro.get("referencia_link"))

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

    if b2.button(
        "✨ Regenerar con IA",
        use_container_width=True,
        key=f"dia_regenerar_{registro.get('codigo')}",
        disabled=not puede_regenerar,
    ):
        try:
            registro_gen = dict(registro, modo_laterales=modo_regen)
            with st.spinner("Generando nueva revisión..."):
                imagen, mime = _dia_generar_imagen_gemini(registro_gen)
            nueva_revision = int(registro.get("revision") or 1) + 1
            propuesta_url = _dia_subir_bytes(
                supabase,
                imagen,
                mime,
                f"disenos-ia/{registro.get('codigo')}",
                f"propuesta_4v_r{nueva_revision}_{modo_regen}",
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
        disabled=estado_actual != "APROBADO POR CLIENTE" or _dia_modo_prueba(),
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

    if _dia_modo_prueba():
        st.caption("Modo prueba: enviar al diseñador y crear cotizaciones están bloqueados.")
    st.markdown("#### 4️⃣ Continuar a cotización")
    puede_cotizar = estado_actual == "ENVIADO A DISEÑADOR" and not _dia_modo_prueba()
    if st.button(
        "🧾 CREAR COTIZACIÓN CON ESTE DISEÑO",
        use_container_width=True,
        key=f"dia_cotizar_{registro.get('codigo')}",
        disabled=not puede_cotizar,
    ) and puede_cotizar:
        st.session_state["cliente_id_edicion"] = registro.get("cliente_id")
        st.session_state["modo_edicion_cot"] = False
        st.session_state["cot_items"] = []
        st.session_state.pop("codigo_edicion", None)
        st.session_state.pop("id_cot_edicion", None)
        _cot_iniciar_modalidad()
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

    _dia_historial(supabase, registros)


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
            cot_db = _cot_cargar_copia_prueba(supabase) if _cot_modo_prueba() else supabase
            if _cot_modo_prueba():
                st.caption("MODO PRUEBA LOCAL · Los cambios de Cotizaciones no se guardan en Supabase.")
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
                st.session_state.pop("codigo_edicion", None)
                st.session_state.pop("id_cot_edicion", None)
                st.session_state.pop("_dia_enlace_cotizacion_id", None)
                _cot_iniciar_modalidad()
                st.rerun()

            with st.container(border=True):
                col_fil1, col_fil2, col_fil3 = st.columns(3)
                h_f_txt = col_fil1.text_input("🔍 Buscar Cliente / Código")
                h_f_ini = col_fil2.date_input(
                    "Desde", value=datetime.date.today() - datetime.timedelta(days=30)
                )
                h_f_fin = col_fil3.date_input("Hasta", value=datetime.date.today())

            query = (
                cot_db.table("cotizaciones").select("*").order("created_at", desc=True)
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
                        cot_db.table("clientes")
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
                            cot_db.table("detalles_cotizacion")
                            .select("*")
                            .eq("cotizacion_id", int(row_sel["id"]))
                            .execute()
                            .data
                        )
                        items_load = []
                        for d in detalles:
                            try:
                                prod = (
                                    cot_db.table("productos_catalogo")
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
                        st.session_state.pop("_dia_enlace_cotizacion_id", None)
                        _cot_iniciar_modalidad(_cot_modalidad_guardada(row_sel))
                        st.session_state["vista_cot"] = "EDITOR"
                        st.rerun()

                    if b2.button("📄 PDF", use_container_width=True):
                        detalles = (
                            cot_db.table("detalles_cotizacion")
                            .select("*")
                            .eq("cotizacion_id", int(row_sel["id"]))
                            .execute()
                            .data
                        )
                        items_pdf = []
                        for d in detalles:
                            prod = (
                                cot_db.table("productos_catalogo")
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
                            cot_db.table("clientes")
                            .select("*")
                            .eq("id", int(row_sel["cliente_id"]))
                            .single()
                            .execute()
                            .data
                        )
                        subtotal_pdf, iva_pdf, total_pdf = _cot_totales_guardados(row_sel)
                        tl = num2words(float(total_pdf), lang="es").upper() + " DÓLARES"

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
                                "subtotal": float(subtotal_pdf),
                                "iva": float(iva_pdf),
                                "total": float(total_pdf),
                                "modalidad_iva": _cot_modalidad_guardada(row_sel),
                                "tipo": cli_data.get("tipo_institucion", ""),
                                "modo_prueba": _cot_modo_prueba(),
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
                        cot_db.table("cotizaciones").update(
                            {"estado": "ANULADO"}
                        ).eq("id", int(row_sel["id"])).execute()
                        st.toast("Cotización anulada")
                        time.sleep(1)
                        st.rerun()

                    tel_cl = ""
                    try:
                        tel_cl = (
                            cot_db.table("clientes")
                            .select("telefono")
                            .eq("id", int(row_sel["cliente_id"]))
                            .single()
                            .execute()
                            .data["telefono"]
                        )
                    except:
                        pass
                    if _cot_modo_prueba():
                        b4.button("📲 WA", disabled=True, help="Envío a clientes bloqueado en modo prueba")
                    elif tel_cl:
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
        cot_db = _cot_cargar_copia_prueba(supabase) if _cot_modo_prueba() else supabase
        if _cot_modo_prueba():
            st.caption("MODO PRUEBA LOCAL · Guardado simulado; Supabase no se modifica desde Cotizaciones.")
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
                cli_db = cot_db.table("clientes").select("*").execute().data
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
                            cot_db.table("catalogo_tipos_cliente")
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
                                    cot_db.table("clientes")
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
                cot_db.table("productos_catalogo")
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
                                    "subtotal": float(_cot_dinero(Decimal(str(cant)) * Decimal(str(final_p)))),
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
                                "subtotal": float(_cot_dinero(Decimal(str(nueva_cant)) * Decimal(str(orig["precio"])))),
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

            # --- TRATAMIENTO DEL IVA ---
            st.markdown("#### 🧾 Tratamiento del IVA")
            opciones_iva = list(_COT_IVA_OPCIONES)
            modalidad_actual = st.session_state.get("cot_modalidad_iva", "INCLUIDO")
            if modalidad_actual == "SIN_IVA":
                st.info(
                    "Esta cotización se guardó sin incluir IVA. "
                    "Selecciona una de las dos modalidades vigentes para actualizarla."
                )
            indice_iva = (
                opciones_iva.index(modalidad_actual)
                if modalidad_actual in opciones_iva else None
            )
            modalidad_iva = st.radio(
                "¿Cómo se manejará el IVA en esta cotización?",
                opciones_iva,
                index=indice_iva,
                format_func=lambda opcion: _COT_IVA_OPCIONES[opcion],
                key="cot_modalidad_iva_widget",
            )
            if modalidad_iva not in _COT_IVA_OPCIONES:
                st.stop()  # No guardar ni recalcular importes históricos sin elegir IVA.
            st.session_state["cot_modalidad_iva"] = modalidad_iva
            subtotal_sin_iva, iva_cotizacion, total_final = _cot_calcular_iva(
                st.session_state["cot_items"], modalidad_iva
            )
            st.caption(
                {
                    "INCLUIDO": "Los precios ingresados ya incluyen IVA.",
                    "AGREGADO": "Los precios ingresados son sin IVA. El 15% se agrega al subtotal.",
                }[modalidad_iva]
            )
            col_base, col_iva, col_total = st.columns(3)
            col_iva.metric("IVA (15%)", f"${iva_cotizacion:.2f}")
            col_base.metric("Subtotal sin IVA", f"${subtotal_sin_iva:.2f}")
            col_total.metric("Total cotizado", f"${total_final:.2f}")

            obs = st.text_area(
                "Observaciones de la Cotización",
                value=st.session_state.get("cot_obs_temp", ""),
            )

            if st.button(
                "💾 GUARDAR COTIZACIÓN", type="primary", use_container_width=True
            ):
                if sel_id:
                    try:
                        # Verificación de esquema: no escribir si falta la columna.
                        try:
                            cot_db.table("cotizaciones").select(
                                "modalidad_iva"
                            ).limit(1).execute()
                        except Exception as e:
                            raise RuntimeError(
                                "No se pudo verificar la columna modalidad_iva. "
                                "Revisa la migración de IVA en Supabase antes de guardar."
                            ) from e

                        cod = (
                            st.session_state["codigo_edicion"]
                            if st.session_state.get("modo_edicion_cot")
                            else generar_siguiente_codigo_cot(cot_db)
                        )
                        data_head = {
                            "codigo_cotizacion": cod,
                            "cliente_id": sel_id,
                            "subtotal": float(subtotal_sin_iva),
                            "iva": float(iva_cotizacion),
                            "total": float(total_final),
                            "modalidad_iva": modalidad_iva,
                            "observaciones": obs,
                            "fecha_emision": str(f_em),
                            "estado": "BORRADOR",
                            "creado_por_id": st.session_state.get("id_usuario", 1),
                        }

                        if st.session_state.get("modo_edicion_cot"):
                            cot_db.table("cotizaciones").update(data_head).eq(
                                "id", st.session_state["id_cot_edicion"]
                            ).execute()
                            cot_id = st.session_state["id_cot_edicion"]
                            cot_db.table("detalles_cotizacion").delete().eq(
                                "cotizacion_id", cot_id
                            ).execute()
                        else:
                            res = (
                                cot_db.table("cotizaciones")
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
                        cot_db.table("detalles_cotizacion").insert(detalles).execute()

                        # Si la cotización nació desde Diseño IA, dejamos la relación persistida.
                        diseno_enlace_id = st.session_state.get("_dia_enlace_cotizacion_id")
                        if diseno_enlace_id and _cot_modo_prueba():
                            # Nunca enlazar una cotización ficticia con un diseño real.
                            st.session_state.pop("_dia_enlace_cotizacion_id", None)
                        elif diseno_enlace_id:
                            try:
                                _dia_actualizar(
                                    cot_db,
                                    diseno_enlace_id,
                                    {"cotizacion_id": cot_id},
                                )
                                st.session_state.pop("_dia_enlace_cotizacion_id", None)
                            except Exception as e_link:
                                st.warning(
                                    f"La cotización se guardó, pero no se pudo enlazar con Diseño IA: {e_link}"
                                )

                        st.success(
                            f"Cotización {cod} guardada en modo prueba (solo local)"
                            if _cot_modo_prueba() else f"Cotización {cod} guardada con éxito"
                        )
                        st.session_state["vista_cot"] = "LISTA"
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")
                else:
                    st.error("Debe seleccionar un cliente antes de guardar.")
