import streamlit as st
import pandas as pd
import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from jinja2 import Environment, FileSystemLoader

# Configuración de rutas
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.models import init_db, Lead
from src.mailer import send_email

# Cargar variables de entorno
load_dotenv(PROJECT_ROOT / ".env")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/leads.db")
TEMPLATE_PATH = PROJECT_ROOT / "templates" / "email_comercial.html"

# Configuración de la página
st.set_page_config(page_title="AI Client Scrapper - Panel de Control", layout="wide", page_icon="🚀")

# Estilos personalizados
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #2c3e50; color: white; }
    .stButton>button:hover { background-color: #34495e; color: white; border: 1px solid #2c3e50; }
    .success-text { color: #27ae60; font-weight: bold; }
    .priority-tag { background-color: #e74c3c; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.8em; }
    </style>
    """, unsafe_allow_state_dict=True)

# Inicializar sesión de base de datos
@st.cache_resource
def get_session():
    return init_db(DATABASE_URL)

session = get_session()

# --- Funciones de Negocio ---
def run_script(script_name, args=None):
    """Ejecuta un script de la carpeta src."""
    script_path = PROJECT_ROOT / "src" / script_name
    env = os.environ.copy()
    if args:
        env.update(args)
    
    process = subprocess.Popen(
        [sys.executable, str(script_path)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    return process

def get_leads_df():
    """Obtiene los leads de la base de datos como DataFrame."""
    query = "SELECT * FROM leads ORDER BY fecha_scraping DESC"
    engine = create_engine(DATABASE_URL)
    return pd.read_sql(query, engine)

# --- Sidebar ---
st.sidebar.title("⚙️ Configuración")
keyword = st.sidebar.text_input("Palabra clave de búsqueda", value="instalaciones solares")
max_pages = st.sidebar.slider("Páginas por fuente", 1, 10, 2)
st.sidebar.divider()

if st.sidebar.button("🔍 Lanzar Scraper (Solo Búsqueda)"):
    st.sidebar.info("Iniciando búsqueda... Revisa la consola o los logs.")
    # Ejecutar scraper y enriquecimiento secuencialmente (simulado para la UI)
    with st.spinner('Buscando empresas y subvenciones...'):
        # 1. Scraper
        subprocess.run([sys.executable, str(PROJECT_ROOT / "src" / "scraper.py")], 
                      env={**os.environ, "SEARCH_KEYWORD": keyword, "MAX_PAGES": str(max_pages)})
        # 2. Enriquecimiento
        subprocess.run([sys.executable, str(PROJECT_ROOT / "src" / "enrich_leads.py")])
    st.sidebar.success("Búsqueda y enriquecimiento completados.")
    st.rerun()

# --- Dashboard Principal ---
st.title("🚀 AI Client Scrapper")
st.subheader("Gestión Inteligente de Leads y Subvenciones")

df = get_leads_df()

# Métricas
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Leads", len(df))
with col2:
    st.metric("Con Subvenciones", len(df[df['total_subvenciones'] > 0]))
with col3:
    st.metric("Prioritarios", len(df[df['es_prioritario'] == True]))
with col4:
    st.metric("Contactados", len(df[df['contactado'] == True]))

st.divider()

# --- Gestión de Leads ---
tab1, tab2 = st.tabs(["📋 Listado de Leads", "📧 Editor de Plantilla"])

with tab1:
    st.write("### Empresas Identificadas")
    
    # Filtros rápidos
    f_col1, f_col2 = st.columns(2)
    with f_col1:
        search_term = st.text_input("Filtrar por nombre o NIF")
    with f_col2:
        only_priority = st.checkbox("Mostrar solo prioritarios")

    filtered_df = df.copy()
    if search_term:
        filtered_df = filtered_df[filtered_df['nombre'].str.contains(search_term, case=False) | 
                                 filtered_df['nif'].str.contains(search_term, case=False, na=False)]
    if only_priority:
        filtered_df = filtered_df[filtered_df['es_prioritario'] == True]

    # Mostrar Tabla
    st.dataframe(
        filtered_df[[
            'id', 'nombre', 'nif', 'total_subvenciones', 'num_concesiones', 
            'email', 'web', 'es_prioritario', 'contactado'
        ]],
        use_container_width=True,
        hide_index=True
    )

    # Acción Individual
    st.write("---")
    st.write("### Acciones sobre Lead")
    lead_id = st.selectbox("Selecciona un Lead para contactar", filtered_df['id'].tolist() if not filtered_df.empty else [])
    
    if lead_id:
        selected_lead = session.query(Lead).filter(Lead.id == lead_id).first()
        l_col1, l_col2 = st.columns([2, 1])
        
        with l_col1:
            st.write(f"**Empresa:** {selected_lead.nombre}")
            st.write(f"**Email:** {selected_lead.email if selected_lead.email else '⚠️ No disponible'}")
            st.write(f"**Subvenciones:** {selected_lead.total_subvenciones:,.2f}€")
        
        with l_col2:
            if not selected_lead.email:
                st.warning("No se puede enviar email (falta dirección)")
            elif selected_lead.contactado:
                st.success("✅ Ya contactado")
                if st.button("Re-enviar Email"):
                    # Lógica de envío individual
                    st.info("Re-enviando...")
            else:
                if st.button("🚀 Enviar Propuesta Ahora"):
                    # Renderizar plantilla
                    env = Environment(loader=FileSystemLoader(str(PROJECT_ROOT / "templates")))
                    template = env.get_template("email_comercial.html")
                    html_content = template.render(
                        nombre_empresa=selected_lead.nombre,
                        total_subvenciones=f"{selected_lead.total_subvenciones:,.2f}"
                    )
                    
                    if send_email(selected_lead.email, f"Propuesta para {selected_lead.nombre}", html_content):
                        selected_lead.contactado = True
                        session.commit()
                        st.success(f"Email enviado a {selected_lead.email}")
                        st.rerun()
                    else:
                        st.error("Error al enviar el email. Revisa la configuración SMTP.")

with tab2:
    st.write("### Personalizar Plantilla de Email")
    if TEMPLATE_PATH.exists():
        with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            current_template = f.read()
        
        new_template = st.text_area("Código HTML de la plantilla", value=current_template, height=400)
        
        if st.button("💾 Guardar Cambios en Plantilla"):
            with open(TEMPLATE_PATH, 'w', encoding='utf-8') as f:
                f.write(new_template)
            st.success("Plantilla actualizada correctamente.")
            
        st.write("#### Previsualización (Empresa Ejemplo)")
        env = Environment(loader=FileSystemLoader(str(PROJECT_ROOT / "templates")))
        try:
            prev_template = env.from_string(new_template)
            preview_html = prev_template.render(nombre_empresa="EMPRESA DE PRUEBA S.L.", total_subvenciones="150,000.00")
            st.components.v1.html(preview_html, height=500, scrolling=True)
        except Exception as e:
            st.error(f"Error en la plantilla: {e}")
    else:
        st.error("No se encontró el archivo de plantilla.")
