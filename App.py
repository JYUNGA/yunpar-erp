import streamlit as st
from supabase import create_client
import time

# --- IMPORTACIÓN DE MÓDULOS ---
from modulos import clientes, productos, insumos, cotizaciones, produccion, finanzas, reportes, disenador, impresion, usuarios

# --- CONFIGURACIÓN GLOBAL ---
st.set_page_config(page_title="YUNPAR ERP", page_icon="👕", layout="wide", initial_sidebar_state="expanded")

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
# Aquí controlamos qué ve cada usuario en el menú lateral.
PERMISOS = {
    "GERENTE": [
        "Inicio", "Cotizaciones", "Producción", "Reportes", 
        "Diseño", "Impresión", "Caja y Finanzas", 
        "Clientes", "Productos", "Insumos", "Usuarios"
    ],
    "VENDEDORA": [
        "Inicio", "Cotizaciones", "Producción", "Caja y Finanzas", "Clientes", "Reportes"
    ],
    "IMPRESION": [
        "Inicio", "Impresión"
    ],
    "DISEÑADOR": [
        "Inicio", "Diseño" # Producción habilitado para subir artes finales
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

# --- ENRUTADOR DINÁMICO DE MÓDULOS ---
def enrutador(opcion):
    if opcion == "Inicio":
        st.title("📊 Tablero Principal")
        st.info(f"Bienvenido al sistema ERP YUNPAR. Tu rol es: **{st.session_state['rol']}**")
    elif opcion == "Cotizaciones": cotizaciones.render(supabase)
    elif opcion == "Producción": produccion.render(supabase)
    elif opcion == "Reportes": reportes.render_modulo_reportes(supabase)
    elif opcion == "Diseño": disenador.render(supabase)
    elif opcion == "Impresión": impresion.render(supabase)
    elif opcion == "Caja y Finanzas": finanzas.render(supabase)
    elif opcion == "Clientes": clientes.render(supabase)
    elif opcion == "Productos": productos.render(supabase)
    elif opcion == "Insumos": insumos.render(supabase)
    elif opcion == "Usuarios": usuarios.render(supabase)

# --- FLUJO PRINCIPAL ---
inicializar_estado()

if not st.session_state['usuario']:
    login()
else:
    # --- SIDEBAR DINÁMICO ---
    with st.sidebar:
        st.title("🏭 YUNPAR")
        st.write(f"👤 **{st.session_state['usuario']}**")
        st.caption(f"Rol: {st.session_state['rol']}")
        st.divider()
        
        # Obtener los módulos permitidos para el rol actual
        rol_actual = st.session_state['rol']
        modulos_permitidos = PERMISOS.get(rol_actual, ["Inicio"])
        
        # Generar los botones de navegación de forma dinámica
        opcion_seleccionada = st.radio("Navegación", modulos_permitidos)
        
        st.divider()
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    # Ejecutar el módulo seleccionado
    enrutador(opcion_seleccionada)