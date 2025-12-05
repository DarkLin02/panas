import pandas as pd
import re
import regex
import demoji
import numpy as np
from collections import Counter
import plotly.express as px
from PIL import Image
from wordcloud import WordCloud, STOPWORDS
import streamlit as st
import string
import requests
from io import StringIO, BytesIO
import os  # <--- Importante para manejar rutas del sistema operativo

# Configuración de la página
st.set_page_config(page_title="Chat Analytics - Bro Edition", page_icon="☯️", layout="wide")

st.title('☕ Análisis de Chat para mi terroncito de azucar 🍫')
st.markdown("### Estadísticas de nuestra amistad legendaria")

##########################################
# 1. Funciones de Parsing y Carga
##########################################

def IniciaConFechaYHora(s):
    patron = r'^(\d{1,2}/\d{1,2}/\d{2,4},? \d{1,2}:\d{2}\s?(?:[aApP]\.?[mM]\.?)?) -'
    return bool(re.match(patron, s))

def ObtenerPartes(linea):
    splitLinea = linea.split(' - ', 1)
    FechaHora = splitLinea[0]
    MensajeCompleto = splitLinea[1] if len(splitLinea) > 1 else ''
    
    try:
        if ',' in FechaHora:
            Fecha, Hora = FechaHora.split(', ')
        else:
            Fecha, Hora = FechaHora.split(' ', 1)
    except ValueError:
        Fecha, Hora = None, None

    splitMensaje = MensajeCompleto.split(': ', 1)
    if len(splitMensaje) == 2:
        Miembro = splitMensaje[0]
        Mensaje = splitMensaje[1]
    else:
        Miembro = None
        Mensaje = MensajeCompleto

    return Fecha, Hora, Miembro, Mensaje

@st.cache_data(show_spinner=False)
def procesar_datos(file_content):
    DatosLista = []
    buffer = StringIO(file_content)
    
    fecha, hora, miembro = None, None, None
    
    while True:
        linea = buffer.readline()
        if not linea:
            break
        linea = linea.strip()
        
        if IniciaConFechaYHora(linea): 
            fecha, hora, miembro, mensaje = ObtenerPartes(linea) 
            DatosLista.append([fecha, hora, miembro, mensaje])
        else:
            if DatosLista:
                DatosLista[-1][-1] += " " + linea 
                    
    df = pd.DataFrame(DatosLista, columns=['Fecha', 'Hora', 'Miembro', 'Mensaje'])
    
    # Normalización de Fechas
    try:
        df['Fecha'] = pd.to_datetime(df['Fecha'], format="%d/%m/%Y")
    except:
        df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=False)

    df = df.dropna().reset_index(drop=True)
    
    # Columnas auxiliares para análisis temporal
    df['Hora_DT'] = pd.to_datetime(df['Hora'], format='%H:%M', errors='coerce')
    df['Hora_Solo'] = df['Hora_DT'].dt.hour
    df['Dia_Semana'] = df['Fecha'].dt.day_name()
    # Traducción de días para visualización
    dias_es = {'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles', 
               'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'}
    df['Dia_Semana_ES'] = df['Dia_Semana'].map(dias_es)
    df['Mes_Año'] = df['Fecha'].dt.to_period('M').astype(str)
    
    return df

def cargar_chat():
    content = None
    # 1. Intentar cargar desde Secrets
    if 'chat_url' in st.secrets:
        try:
            with st.spinner('Descargando historial cifrado desde la nube...'):
                response = requests.get(st.secrets['chat_url'])
                response.raise_for_status()
                content = response.content.decode('utf-8')
                st.success("✅ Datos cargados desde la nube privada.")
        except Exception:
            pass # Fallo silencioso, pasamos a carga manual
    
    # 2. Carga Manual
    if content is None:
        st.info("⚠️ Sube tu archivo `_chat.txt` exportado de WhatsApp.")
        uploaded_file = st.file_uploader("Subir historial", type="txt")
        if uploaded_file is not None:
            content = uploaded_file.getvalue().decode("utf-8")
            
    return content

@st.cache_data(show_spinner=False)
def cargar_imagen_mask():
    """Intenta cargar la máscara y procesarla para WordCloud"""
    mask = None
    
    # A. Intentar cargar desde Secrets
    if 'mask_url' in st.secrets:
        try:
            response = requests.get(st.secrets['mask_url'])
            response.raise_for_status()
            image = Image.open(BytesIO(response.content))
            if image.mode == 'RGBA':
                # Crear fondo blanco para transparencias
                background = Image.new("RGB", image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[3]) 
                image = background
            mask = np.array(image)
        except Exception:
            pass 

    # B. Intentar cargar local
    if mask is None:
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            img_path = os.path.join(base_dir, 'Resources', 'heart.jpg')
            
            # Debug explícito si no existe
            if not os.path.exists(img_path):
                st.warning(f"⚠️ No se encuentra la imagen en: {img_path}")
                return None

            image = Image.open(img_path)
            
            # Procesar transparencia (RGBA -> RGB con fondo blanco)
            # WordCloud necesita fondo blanco (255) para ignorar esa zona
            if image.mode == 'RGBA':
                background = Image.new("RGB", image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[3])
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
                
            mask = np.array(image)
            
        except Exception as e:
            st.warning(f"⚠️ Error cargando máscara visual: {e}")
            mask = None
            
    return mask

# --- EJECUCIÓN ---
raw_text = cargar_chat()
if raw_text is None:
    st.stop()

df = procesar_datos(raw_text)

# --- SIDEBAR ---
st.sidebar.header("🛠️ Filtros")
fechas = df['Fecha'].dt.date.unique()
start_date, end_date = st.sidebar.date_input("Rango", [min(fechas), max(fechas)])
df = df[(df['Fecha'].dt.date >= start_date) & (df['Fecha'].dt.date <= end_date)]

##########################################
# 2. KPIs y Métricas Generales
##########################################

def get_stats(df):
    total_msgs = df.shape[0]
    multimedia = df[df['Mensaje'] == '<Multimedia omitido>'].shape[0]
    links = df.Mensaje.apply(lambda x: len(re.findall(r'(https?://\S+)', x))).sum()
    
    # Emojis
    all_emojis = []
    for m in df['Mensaje']:
        all_emojis.extend([c for c in regex.findall(r'\X', m) if demoji.replace(c) != c])
    
    return total_msgs, multimedia, links, all_emojis

msgs, media, links, emoji_list = get_stats(df)

st.markdown("#### 📊 Métricas Totales")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Mensajes", msgs)
c2.metric("Multimedia", media)
c3.metric("Emojis", len(emoji_list))
c4.metric("Links", links)
st.divider()

##########################################
# 3. Análisis de Usuarios y Emojis (NUEVO)
##########################################

col_users, col_emojis = st.columns([1, 1])

with col_users:
    st.subheader("🏆 ¿Quién habla más?")
    user_count = df['Miembro'].value_counts().reset_index()
    user_count.columns = ['Miembro', 'Mensajes']
    fig_bar = px.bar(user_count, x='Miembro', y='Mensajes', color='Miembro', 
                     text='Mensajes', template='plotly_dark')
    st.plotly_chart(fig_bar, width="stretch")

with col_emojis:
    st.subheader("😎 Top 10 Emojis")
    if emoji_list:
        emoji_counts = Counter(emoji_list).most_common(10)
        df_emojis = pd.DataFrame(emoji_counts, columns=['Emoji', 'Cantidad'])
        fig_pie = px.pie(df_emojis, values='Cantidad', names='Emoji', 
                         template='plotly_dark', hole=0.4)
        st.plotly_chart(fig_pie, width="stretch")
    else:
        st.write("No se encontraron emojis.")

##########################################
# 4. Análisis Temporal (NUEVO: Timeline y Heatmap)
##########################################

st.divider()
st.header("⏳ Cronología de la Amistad")

# Serie de Tiempo (Mensajes por día)
msg_per_day = df.groupby('Fecha').size().reset_index(name='Mensajes')
fig_time = px.line(msg_per_day, x='Fecha', y='Mensajes', title='Actividad Diaria',
                   template='plotly_dark', render_mode='svg')
fig_time.update_traces(line_color='#00CC96')
st.plotly_chart(fig_time, width="stretch")

# Heatmap (Día vs Hora) - CRUCIAL PARA "NOCTURNIDAD"
st.subheader("🔥 Heatmap: ¿Cuándo estamos activos?")
heatmap_data = df.groupby(['Dia_Semana_ES', 'Hora_Solo']).size().reset_index(name='Mensajes')

# Definir orden explícito para Plotly
dias_orden = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

fig_heat = px.density_heatmap(heatmap_data, x='Hora_Solo', y='Dia_Semana_ES', z='Mensajes',
                              nbinsx=24, color_continuous_scale='Viridis', template='plotly_dark',
                              title="Intensidad por Día y Hora",
                              category_orders={"Dia_Semana_ES": dias_orden}) # FORZAR ORDEN AQUÍ

fig_heat.update_layout(xaxis_title="Hora del día (0-23)", yaxis_title="Día")
st.plotly_chart(fig_heat, width="stretch")

##########################################
# 5. WordCloud
##########################################
st.divider()
st.header('☁️ De qué hablamos')

stopwords_es = set(STOPWORDS)
stopwords_es.update(['de', 'la', 'que', 'el', 'en', 'y', 'a', 'los', 'se', 'del', 'las', 'un', 
                     'por', 'con', 'no', 'una', 'su', 'para', 'es', 'al', 'lo', 'como', 
                     'más', 'pero', 'sus', 'le', 'ya', 'o', 'fue', 'este', 'ha', 'sí', 
                     'multimedia', 'omitido', 'http', 'https', 'www', 'com', 'jajaja', 'jaja'])

def limpiar(txt):
    return str(txt).lower().translate(str.maketrans('', '', string.punctuation))

text_all = " ".join(limpiar(m) for m in df['Mensaje'] if '<Multimedia' not in m)

# Usar la función de carga robusta
mask = cargar_imagen_mask()

if text_all:
    # Ajuste de fondo a 'black' para mejor contraste con tu tema oscuro
    wc = WordCloud(width=800, height=800, 
                   background_color='black', 
                   stopwords=stopwords_es,
                   mask=mask, 
                   colormap='cool', 
                   contour_width=1, 
                   contour_color='white').generate(text_all)
    st.image(wc.to_array(), width="stretch")
else:
    st.write("No hay suficiente texto para generar la nube.")

st.markdown("---")
st.caption("© 2025 — Cain Lin | Data Science & Bro Code")