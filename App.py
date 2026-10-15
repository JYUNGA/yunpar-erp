import streamlit as st
from supabase import create_client
import time
import random
from datetime import datetime
import pytz
import google.generativeai as genai  # <-- LA LIBRERÍA OFICIAL DE GEMINI

# --- IMPORTACIÓN DE MÓDULOS ---
# Importamos el nuevo módulo de asistencia y nómina junto a los demás
from modulos import (
    clientes,
    productos,
    insumos,
    cotizaciones,
    produccion,
    finanzas,
    reportes,
    disenador,
    impresion,
    usuarios,
    ventas,
    facturacion,
    rh,
    apus,
    polines,
    control_taller,
    kpis,
    auth,
)

# --- CONFIGURACIÓN GLOBAL ---
st.set_page_config(
    page_title="YUNPAR ERP",
    page_icon="👕",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- MANTENER SESIÓN ACTIVA (PING) ---
st.markdown(
    """
    <script>
        setInterval(function() {
            fetch(window.location.href, { method: 'HEAD' });
        }, 25000);
    </script>
    """,
    unsafe_allow_html=True,
)


# --- AJUSTES RESPONSIVE / MÓVIL (global, aporte de Andrés) ---
# Aplica a toda la app: apila columnas, agranda botones y evita que las tablas
# rompan el ancho en pantallas de celular (≤768px).
st.markdown(
    """
    <style>
    @media (max-width: 1023px) {
        div[data-testid="stHorizontalBlock"] {
            flex-direction: column !important;
            gap: 0.75rem !important;
        }
        div[data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
        }
        div.stButton > button,
        div[data-testid="stFormSubmitButton"] > button {
            width: 100% !important;
            min-height: 2.8rem !important;
        }
        h1 { font-size: 2rem !important; }
        h2 { font-size: 1.45rem !important; }
        h3 { font-size: 1.2rem !important; }
        div[data-testid="stDataFrame"],
        div[data-testid="stDataEditor"] {
            max-width: 100% !important;
            overflow-x: auto !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --- CONEXIÓN BASE DE DATOS ---
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Error de configuración: {e}")
        st.stop()


supabase = init_connection()

# --- DICCIONARIO DE ROLES Y PERMISOS (RBAC) ---
# Se añade "Asistencia y Nómina" como acceso EXCLUSIVO para el rol GERENTE
PERMISOS = {
    "GERENTE": [
        "Inicio",
        "KPI y Métricas",
        "Ventas",
        "Cotizaciones",
        "Producción",
        "Control de Taller",
        "Facturación",
        "Reportes",
        "Diseño",
        "Impresión",
        "Caja y Finanzas",
        "Asistencia y Nómina",
        "Clientes",
        "Productos",
        "Insumos",
        "Usuarios",
        "Costos y APUs",
        "Polines",
    ],
    "VENDEDORA": [
        "Inicio",
        "Ventas",
        "Cotizaciones",
        "Producción",
        "Control de Taller",
        "Facturación",
        "Caja y Finanzas",
        "Clientes",
        "Reportes",
        "Polines",
    ],
    "IMPRESION": ["Inicio", "Impresión", "Reportes"],
    "DISEÑADOR": ["Inicio", "Diseño"],
}


# --- GESTIÓN DE SESIÓN ---
def inicializar_estado():
    if "usuario" not in st.session_state:
        st.session_state["usuario"] = None
    if "rol" not in st.session_state:
        st.session_state["rol"] = None
    if "id_usuario" not in st.session_state:
        st.session_state["id_usuario"] = None


# --- PANTALLA DE LOGIN ---
def login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)  # Espaciado
        with st.container(border=True):
            st.title("🔐 YUNPAR ERP")
            st.markdown("Acceso al Sistema de Gestión de Producción")

            user = st.text_input("Usuario")
            pwd = st.text_input("Contraseña", type="password")

            if st.button("Iniciar Sesión", type="primary", use_container_width=True):
                if user and pwd:
                    # Buscamos solo por usuario; la verificación de clave usa hash seguro.
                    res = (
                        supabase.table("usuarios")
                        .select("*")
                        .eq("usuario", user)
                        .execute()
                    )

                    u = res.data[0] if res.data else None

                    if not u or not auth.verify_password(pwd, u.get("password_hash")):
                        st.error("❌ Credenciales incorrectas.")
                    elif not u["activo"]:
                        st.error(
                            "🚫 Tu usuario está desactivado. Contacta al administrador."
                        )
                    else:
                        # Migración perezosa: si la clave aún está en texto plano, la re-hasheamos.
                        if not auth.is_hashed(u.get("password_hash")):
                            try:
                                supabase.table("usuarios").update(
                                    {"password_hash": auth.hash_password(pwd)}
                                ).eq("id", u["id"]).execute()
                            except Exception:
                                pass

                        st.session_state["usuario"] = u["nombre_completo"]
                        st.session_state["rol"] = u["rol"]
                        st.session_state["id_usuario"] = u["id"]
                        st.success(f"¡Bienvenido, {u['nombre_completo']}!")
                        time.sleep(1)
                        st.rerun()
                else:
                    st.warning("⚠️ Ingresa usuario y contraseña.")


# --- MOTOR DE INTELIGENCIA ARTIFICIAL (GEMINI) ---
# Sin caché de 24h: se genera una vez por sesión (session_state), así el
# mensaje es distinto en cada ingreso y no se repite entre usuarios.
def obtener_mensaje_diario(rol_usuario, nombre, turno):
    clave = f"mensaje_ia_{rol_usuario}_{nombre}_{turno}"
    if clave in st.session_state:
        return st.session_state[clave]

    try:
        genai.configure(api_key=st.secrets["gemini"]["api_key"])
        model = genai.GenerativeModel("gemini-2.5-flash")

        angulos = [
            "superar una meta de producción",
            "atender con buena actitud al cliente",
            "mantener el orden y la calidad",
            "trabajo en equipo",
            "cuidar los detalles",
            "cerrar el día sin pendientes",
        ]
        angulo = random.choice(angulos)

        prompt = f"""
        Eres la IA del ERP de YUNPAR (fábrica de uniformes).
        El usuario '{nombre}' (rol: {rol_usuario}) acaba de iniciar sesión en el turno de la {turno}.

        Escribe un mensaje de EXACTAMENTE DOS oraciones muy breves y directas:
        1. Una frase de motivación extrema enfocada en su rol, inspirada en este tema: "{angulo}" (máximo 15 palabras).
        2. Un chiste o dato curioso MUY corto, sano y divertido, relacionado con fábricas, uniformes, telas o el trabajo (máximo 20 palabras).

        REGLAS:
        - NO saludes. PROHIBIDO decir "Hola", "Buenos días", "Buenas tardes" o "Buenas noches" (el sistema ya saludó).
        - Varía el contenido: evita chistes típicos y no repitas la misma idea de siempre.
        - Adapta el tono al rol: GERENTE = visión de negocio y resultados; VENDEDORA = ventas y clientes; DISEÑADOR = creatividad y arte; IMPRESION = ritmo y calidad del plotter.
        - Usa exactamente 2 emojis.
        """

        respuesta = model.generate_content(prompt)
        texto = respuesta.text.strip()
    except Exception:
        texto = f"¡A dar lo mejor en esta **{turno}**, {nombre}! 🚀"

    st.session_state[clave] = texto
    return texto


# --- ENRUTADOR DINÁMICO DE MÓDULOS ---
def enrutador(opcion):
    if opcion == "Inicio":
        zona_horaria = pytz.timezone("America/Guayaquil")
        hora_exacta = datetime.now(zona_horaria)

        # Unificamos el saludo y el turno de la IA para que coincidan perfectamente
        if hora_exacta.hour < 12:
            saludo = "🌅 Buenos días"
            turno_ia = "Mañana"
        elif hora_exacta.hour < 19:
            saludo = "☀️ Buenas tardes"
            turno_ia = "Tarde"
        else:
            saludo = "🌙 Buenas noches"
            turno_ia = "Noche"

        nombre_completo = st.session_state.get("usuario", "Equipo")
        nombre_pila = nombre_completo.split()[0] if nombre_completo else "Equipo"
        rol_actual = st.session_state.get("rol", "Colaborador")

        # --- TARJETA DE BIENVENIDA PREMIUM (CSS) ---
        st.markdown(
            f"""
        <div style="background: linear-gradient(135deg, #0b2046 0%, #1a3c7a 100%); 
                    padding: 35px 30px; 
                    border-radius: 12px; 
                    color: white; 
                    box-shadow: 0 8px 20px rgba(0,0,0,0.15); 
                    margin-bottom: 30px;
                    border-left: 8px solid #ff4b4b;">
            <h1 style="color: white; margin-bottom: 5px; font-size: 2.5rem; font-weight: 800;">{saludo}, {nombre_pila}!</h1>
            <p style="font-size: 1.1rem; opacity: 0.85; margin-top: 0; font-weight: 300;">Panel General YUNPAR • Rol Asignado: <strong>{rol_actual}</strong></p>
        </div>
        """,
            unsafe_allow_html=True,
        )

        col_ia, col_info = st.columns([2.2, 1])

        with col_ia:
            with st.spinner(f"Sincronizando IA para la {turno_ia}..."):
                # Llamamos a la IA pasándole el turno
                mensaje_ia = obtener_mensaje_diario(rol_actual, nombre_pila, turno_ia)

            # --- NUEVO DISEÑO DEL MENSAJE IA (Letra gigante, cursiva y de lectura rápida) ---
            st.markdown(
                f"""
            <div style="background-color: #f8f9fa; border: 1px solid #e9ecef; border-radius: 10px; padding: 25px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
                <h4 style="color: #ff4b4b; margin-top: 0; margin-bottom: 15px; font-weight: 700;">
                    💡 Inspiración de la {turno_ia}
                </h4>
                <div style="font-size: 1.45rem; color: #2b3035; line-height: 1.6; font-style: italic; font-weight: 500;">
                    {mensaje_ia}
                </div>
            </div>
            """,
                unsafe_allow_html=True,
            )

        with col_info:
            st.markdown(
                "<h4 style='color: #1a3c7a; font-weight: 700;'>📌 Enfoque de tu Rol</h4>",
                unsafe_allow_html=True,
            )
            if rol_actual == "GERENTE":
                st.success(
                    "📊 **Métricas.** Revisa saldos pendientes y controla el flujo del taller."
                )
            elif rol_actual == "VENDEDORA":
                st.warning(
                    "🛒 **Ventas.** Liquida órdenes entregadas y genera nuevas proformas."
                )
            elif rol_actual == "DISEÑADOR":
                st.error(
                    "🎨 **Diseño.** Sincroniza artes finales y envía archivos al plotter."
                )
            elif rol_actual == "IMPRESION":
                st.info(
                    "🖨️ **Plotter.** Descarga lotes de producción y mantén las máquinas a tope."
                )
            else:
                st.info("Revisa tus módulos en el menú lateral.")

            st.divider()
            st.caption(f"📅 {hora_exacta.strftime('%d/%m/%Y')} | 🏭 YUNPAR ERP v2.5")

    elif opcion == "KPI y Métricas":
        kpis.render(supabase)
    elif opcion == "Ventas":
        ventas.render(supabase)
    elif opcion == "Cotizaciones":
        cotizaciones.render(supabase)
    elif opcion == "Producción":
        produccion.render(supabase)
    elif opcion == "Facturación":
        facturacion.render(supabase)  # <-- Corrección de sangría y variables
    elif opcion == "Reportes":
        reportes.render_modulo_reportes(supabase)
    elif opcion == "Diseño":
        disenador.render(supabase)
    elif opcion == "Impresión":
        impresion.render(supabase)
    elif opcion == "Caja y Finanzas":
        finanzas.render(supabase)
    elif opcion == "Clientes":
        clientes.render(supabase)
    elif opcion == "Productos":
        productos.render(supabase)
    elif opcion == "Insumos":
        insumos.render(supabase)
    elif opcion == "Usuarios":
        usuarios.render(supabase)
    # Enlazamos la opción de navegación con la función render de tu archivo rh.py
    elif opcion == "Asistencia y Nómina":
        rh.render(supabase)
    elif opcion == "Costos y APUs":
        apus.render(supabase)
    elif opcion == "Polines":
        polines.render(supabase)
    elif opcion == "Control de Taller":
        control_taller.render(supabase)


# --- FLUJO PRINCIPAL ---
inicializar_estado()

if not st.session_state["usuario"]:
    login()
else:
    # --- 1. ESCUDO DE MEMORIA (ANTIBUG) ---
    # Si la caché del navegador corrompió el rol convirtiéndolo en diccionario, lo forzamos a texto
    if isinstance(st.session_state.get("rol"), dict):
        st.session_state["rol"] = str(st.session_state["rol"].get("rol", "Inicio"))
    elif not isinstance(st.session_state.get("rol"), str):
        st.session_state["rol"] = str(st.session_state.get("rol", "Inicio"))

    rol_seguro = st.session_state["rol"].strip()

    # --- 2. SIDEBAR DINÁMICO ---
    with st.sidebar:
        st.title("🏭 YUNPAR")

        # También protegemos el nombre de usuario por si acaso
        usuario_seguro = st.session_state.get("usuario", "Desconocido")
        if isinstance(usuario_seguro, dict):
            usuario_seguro = str(usuario_seguro.get("nombre_completo", "Desconocido"))

        st.write(f"👤 **{usuario_seguro}**")
        st.caption(f"Rol: {rol_seguro}")
        st.divider()

        # Obtener los módulos permitidos de forma 100% segura
        modulos_permitidos = PERMISOS.get(rol_seguro, ["Inicio"])

        # Generar los botones de navegación
        opcion_seleccionada = st.radio("Navegación", modulos_permitidos)

        st.divider()
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]  # Limpieza absoluta
            st.rerun()

    # Ejecutar el módulo seleccionado
    enrutador(opcion_seleccionada)
