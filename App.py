import streamlit as st
from supabase import create_client
import time
from datetime import datetime
import pytz
import google.generativeai as genai # <-- LA LIBRERÍA OFICIAL DE GEMINI

# --- IMPORTACIÓN DE MÓDULOS ---
# Importamos el nuevo módulo de asistencia y nómina junto a los demás
from modulos import clientes, productos, insumos, cotizaciones, produccion, finanzas, reportes, disenador, impresion, usuarios, ventas, facturacion, rh, apus


# --- CONFIGURACIÓN GLOBAL ---
st.set_page_config(page_title="YUNPAR ERP", page_icon="👕", layout="wide", initial_sidebar_state="expanded")

# --- MANTENER SESIÓN ACTIVA (PING) ---
st.markdown(
    """
    <script>
        setInterval(function() {
            fetch(window.location.href, { method: 'HEAD' });
        }, 25000);
    </script>
    """,
    unsafe_allow_html=True
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
        "Inicio", "Ventas", "Cotizaciones", "Producción", "Facturación", "Reportes", 
        "Diseño", "Impresión", "Caja y Finanzas", "Asistencia y Nómina", 
        "Clientes", "Productos", "Insumos", "Usuarios", "Costos y APUs"
    ],
    "VENDEDORA": [
        "Inicio", "Ventas", "Cotizaciones", "Producción", "Facturación", "Caja y Finanzas", "Clientes", "Reportes"
    ],
    "IMPRESION": [
        "Inicio", "Impresión", "Reportes"
    ],
    "DISEÑADOR": [
        "Inicio", "Diseño"
    ]
}

# --- GESTIÓN DE SESIÓN ---
def inicializar_estado():
    if 'usuario' not in st.session_state: st.session_state['usuario'] = None
    if 'rol' not in st.session_state: st.session_state['rol'] = None
    if 'id_usuario' not in st.session_state: st.session_state['id_usuario'] = None

# --- PANTALLA DE LOGIN ---
def login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True) # Espaciado
        with st.container(border=True):
            st.title("🔐 YUNPAR ERP")
            st.markdown("Acceso al Sistema de Gestión de Producción")
            
            user = st.text_input("Usuario")
            pwd = st.text_input("Contraseña", type="password")
            
            if st.button("Iniciar Sesión", type="primary", use_container_width=True):
                if user and pwd:
                    # NOTA: Si decides usar hashes (ej. hashlib), aplica el hash a 'pwd' antes de consultar
                    res = supabase.table('usuarios').select("*").eq('usuario', user).eq('password_hash', pwd).execute()
                    
                    if res.data:
                        u = res.data[0]
                        if u['activo']:
                            st.session_state['usuario'] = u['nombre_completo']
                            st.session_state['rol'] = u['rol']
                            st.session_state['id_usuario'] = u['id']
                            st.success(f"¡Bienvenido, {u['nombre_completo']}!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("🚫 Tu usuario está desactivado. Contacta al administrador.")
                    else:
                        st.error("❌ Credenciales incorrectas.")
                else:
                    st.warning("⚠️ Ingresa usuario y contraseña.")

# --- MOTOR DE INTELIGENCIA ARTIFICIAL (GEMINI) ---
@st.cache_data(ttl=86400, show_spinner=False) 
def obtener_mensaje_diario(rol_usuario, nombre, turno):
    try:
        genai.configure(api_key=st.secrets["gemini"]["api_key"])
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # PROMPT CON HUMOR: Cambiamos el dato curioso por un chiste corto y sano.
        prompt = f"""
        Eres la IA del ERP de YUNPAR (fábrica de uniformes). 
        El usuario '{nombre}' (rol: {rol_usuario}) acaba de iniciar sesión en el turno de la {turno}.
        
        Escribe un mensaje de EXACTAMENTE DOS oraciones muy breves y directas:
        1. Una frase de motivación extrema enfocada en su rol (máximo 15 palabras).
        2. Un chiste muy corto, sano y divertido (máximo 20 palabras) para sacarle una sonrisa en el trabajo.
        
        REGLA DE ORO: NO LO SALUDES. PROHIBIDO decir "Hola", "Buenos días", "Buenas tardes" o "Buenas noches" porque el sistema ya lo saludó en el título. Ve directo a la motivación y remata con el chiste. Usa 2 emojis.
        """
        
        respuesta = model.generate_content(prompt)
        return respuesta.text
    except Exception as e:
        return f"¡A dar lo mejor en esta **{turno}**, {nombre}! 🚀"

# --- ENRUTADOR DINÁMICO DE MÓDULOS ---
def enrutador(opcion):
    if opcion == "Inicio":
        zona_horaria = pytz.timezone('America/Guayaquil')
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
        
        nombre_completo = st.session_state.get('usuario', 'Equipo')
        nombre_pila = nombre_completo.split()[0] if nombre_completo else "Equipo"
        rol_actual = st.session_state.get('rol', 'Colaborador')

        # --- TARJETA DE BIENVENIDA PREMIUM (CSS) ---
        st.markdown(f"""
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
        """, unsafe_allow_html=True)
        
        col_ia, col_info = st.columns([2.2, 1])
        
        with col_ia:
            with st.spinner(f"Sincronizando IA para la {turno_ia}..."):
                # Llamamos a la IA pasándole el turno
                mensaje_ia = obtener_mensaje_diario(rol_actual, nombre_pila, turno_ia)
            
            # --- NUEVO DISEÑO DEL MENSAJE IA (Letra gigante, cursiva y de lectura rápida) ---
            st.markdown(f"""
            <div style="background-color: #f8f9fa; border: 1px solid #e9ecef; border-radius: 10px; padding: 25px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
                <h4 style="color: #ff4b4b; margin-top: 0; margin-bottom: 15px; font-weight: 700;">
                    💡 Inspiración de la {turno_ia}
                </h4>
                <div style="font-size: 1.45rem; color: #2b3035; line-height: 1.6; font-style: italic; font-weight: 500;">
                    {mensaje_ia}
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col_info:
            st.markdown("<h4 style='color: #1a3c7a; font-weight: 700;'>📌 Enfoque de tu Rol</h4>", unsafe_allow_html=True)
            if rol_actual == "GERENTE":
                st.success("📊 **Métricas.** Revisa saldos pendientes y controla el flujo del taller.")
            elif rol_actual == "VENDEDORA":
                st.warning("🛒 **Ventas.** Liquida órdenes entregadas y genera nuevas proformas.")
            elif rol_actual == "DISEÑADOR":
                st.error("🎨 **Diseño.** Sincroniza artes finales y envía archivos al plotter.")
            elif rol_actual == "IMPRESION":
                st.info("🖨️ **Plotter.** Descarga lotes de producción y mantén las máquinas a tope.")
            else:
                st.info("Revisa tus módulos en el menú lateral.")
                
            st.divider()
            st.caption(f"📅 {hora_exacta.strftime('%d/%m/%Y')} | 🏭 YUNPAR ERP v2.5")

    elif opcion == "Ventas": ventas.render(supabase)
    elif opcion == "Cotizaciones": cotizaciones.render(supabase)
    elif opcion == "Producción": produccion.render(supabase)
    elif opcion == "Facturación": facturacion.render(supabase) # <-- Corrección de sangría y variables
    elif opcion == "Reportes": reportes.render_modulo_reportes(supabase)
    elif opcion == "Diseño": disenador.render(supabase)
    elif opcion == "Impresión": impresion.render(supabase)
    elif opcion == "Caja y Finanzas": finanzas.render(supabase)
    elif opcion == "Clientes": clientes.render(supabase)
    elif opcion == "Productos": productos.render(supabase)
    elif opcion == "Insumos": insumos.render(supabase)
    elif opcion == "Usuarios": usuarios.render(supabase)
    # Enlazamos la opción de navegación con la función render de tu archivo rh.py
    elif opcion == "Asistencia y Nómina": rh.render(supabase)
    elif opcion == "Costos y APUs": apus.render(supabase)

# --- FLUJO PRINCIPAL ---
inicializar_estado()

if not st.session_state['usuario']:
    login()
else:
    # --- 1. ESCUDO DE MEMORIA (ANTIBUG) ---
    # Si la caché del navegador corrompió el rol convirtiéndolo en diccionario, lo forzamos a texto
    if isinstance(st.session_state.get('rol'), dict):
        st.session_state['rol'] = str(st.session_state['rol'].get('rol', 'Inicio'))
    elif not isinstance(st.session_state.get('rol'), str):
        st.session_state['rol'] = str(st.session_state.get('rol', 'Inicio'))
        
    rol_seguro = st.session_state['rol'].strip()

    # --- 2. SIDEBAR DINÁMICO ---
    with st.sidebar:
        st.title("🏭 YUNPAR")
        
        # También protegemos el nombre de usuario por si acaso
        usuario_seguro = st.session_state.get('usuario', 'Desconocido')
        if isinstance(usuario_seguro, dict):
            usuario_seguro = str(usuario_seguro.get('nombre_completo', 'Desconocido'))
            
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
                del st.session_state[key] # Limpieza absoluta
            st.rerun()

    # Ejecutar el módulo seleccionado
    enrutador(opcion_seleccionada)
