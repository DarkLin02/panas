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

# Configuración de la página (Título y Favicon)
st.set_page_config(page_title="Chat Analytics - Bro Edition", page_icon="☯️", layout="wide")

###################################
# Título de la aplicación
st.title('☕ Análisis de Chat: Edición "Terroncito de Azucar" 🤜🤛')
st.markdown("### Estadísticas de nuestra amistad legendaria")
###################################

##########################################
# ### Paso 1: Definir funciones de Parsing (Robustas)
##########################################

def IniciaConFechaYHora(s):
    # Patrón flexible para distintos formatos de WhatsApp
    patron = r'^(\d{1,2}/\d{1,2}/\d{2,4},? \d{1,2}:\d{2}\s?(?:[aApP]\.?[mM]\.?)?) -'
    return bool(re.match(patron, s))

def ObtenerPartes(linea):
    # Separa FechaHora del resto
    splitLinea = linea.split(' - ', 1)
    FechaHora = splitLinea[0]
    MensajeCompleto = splitLinea[1] if len(splitLinea) > 1 else ''
    
    # Intenta separar fecha y hora
    try:
        if ',' in FechaHora:
            Fecha, Hora = FechaHora.split(', ')
        else:
            Fecha, Hora = FechaHora.split(' ', 1)
    except ValueError:
        Fecha, Hora = None, None

    # Separar Autor del Mensaje
    # Buscamos el primer ": " para separar autor de contenido
    splitMensaje = MensajeCompleto.split(': ', 1)
    if len(splitMensaje) == 2:
        Miembro = splitMensaje[0]
        Mensaje = splitMensaje[1]
    else:
        Miembro = None # Es un mensaje del sistema (ej: "Cambió el icono del grupo")
        Mensaje = MensajeCompleto

    return Fecha, Hora, Miembro, Mensaje

##################################################################################
# ### Paso 2: Carga y Procesamiento de Datos
##################################################################################

@st.cache_data
def cargar_datos_chat(ruta_archivo):
    DatosLista = []
    
    try:
        with open(ruta_archivo, encoding="utf-8") as fp: 
            fp.readline() # Saltar header de cifrado si existe
            fecha, hora, miembro = None, None, None
            
            while True:
                linea = fp.readline()
                if not linea:
                    break
                linea = linea.strip()
                
                if IniciaConFechaYHora(linea): 
                    fecha, hora, miembro, mensaje = ObtenerPartes(linea) 
                    DatosLista.append([fecha, hora, miembro, mensaje])
                else:
                    # Continuación de mensaje anterior
                    if DatosLista:
                        DatosLista[-1][-1] += " " + linea 
                        
        df = pd.DataFrame(DatosLista, columns=['Fecha', 'Hora', 'Miembro', 'Mensaje'])
        
        # Conversión de fechas (Manejo de errores si el formato varía)
        try:
            df['Fecha'] = pd.to_datetime(df['Fecha'], format="%d/%m/%Y")
        except:
            # Intento secundario para formato m/d/y si falla el primero
            df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=False)

        df = df.dropna().reset_index(drop=True)
        return df
        
    except FileNotFoundError:
        st.error("No se encontró el archivo de chat. Revisa la ruta en 'app.py'.")
        return pd.DataFrame()

# RUTA DEL ARCHIVO (Asegúrate de cambiar esto al nombre real del chat con tu amigo)
# Lo ideal sería usar st.file_uploader, pero mantenemos la estructura local.
RUTA_CHAT = 'Data/Chat de WhatsApp con Pana Ema Bade.txt' 
df = cargar_datos_chat(RUTA_CHAT)

if df.empty:
    st.stop()

# --- FILTROS DE SIDEBAR (Dinámicos) ---
st.sidebar.header("🛠️ Filtros")
min_date = df['Fecha'].min().date()
max_date = df['Fecha'].max().date()

start_date, end_date = st.sidebar.date_input(
    "Rango de Fechas", 
    [min_date, max_date],
    min_value=min_date, max_value=max_date
)

# Filtrar DF principal
df = df[(df['Fecha'].dt.date >= start_date) & (df['Fecha'].dt.date <= end_date)].copy()

##################################################################
# ### Paso 3: Estadísticas Generales
##################################################################

def obtener_emojis(mensaje):
    return [c for c in regex.findall(r'\X', mensaje) if demoji.replace(c) != c]

# Cálculos
total_mensajes = df.shape[0]
multimedia_mensajes = df[df['Mensaje'] == '<Multimedia omitido>'].shape[0]
df['Emojis'] = df['Mensaje'].apply(obtener_emojis)
total_emojis = sum(df['Emojis'].str.len())
url_patron = r'(https?://\S+)'
df['URLs'] = df.Mensaje.apply(lambda x: len(re.findall(url_patron, x)))
total_links = sum(df['URLs'])

# KPI Cards visuales
st.markdown("#### 📊 Métricas Totales")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Mensajes Totales", total_mensajes)
col2.metric("Multimedia", multimedia_mensajes)
col3.metric("Emojis", total_emojis)
col4.metric("Links Compartidos", total_links)

st.divider()

###################################
# ### Paso 4: Análisis por Miembro
###################################

st.header('🏆 ¿Quién habla más?')
col_chart, col_table = st.columns([2, 1])

# Miembros más activos
df_activos = df.groupby('Miembro')['Mensaje'].count().sort_values(ascending=False).reset_index()

with col_table:
    st.markdown("#### Ranking")
    st.dataframe(df_activos, hide_index=True)

with col_chart:
    fig_bar = px.bar(df_activos, x='Miembro', y='Mensaje', color='Mensaje', 
                     template='plotly_dark', color_continuous_scale='Teal')
    st.plotly_chart(fig_bar, use_container_width=True)

###################################
# ### Paso 5: Análisis Temporal
###################################

st.header('⏰ Nuestros Horarios')
df['Hora_DT'] = pd.to_datetime(df['Hora'], format='%H:%M', errors='coerce')
df['Hora_Solo'] = df['Hora_DT'].dt.hour

hora_counts = df.groupby('Hora_Solo').size().reset_index(name='Mensajes')

fig_line = px.line(hora_counts, x='Hora_Solo', y='Mensajes', 
                   markers=True, template='plotly_dark',
                   title='Actividad por Hora del Día (0-23h)')
fig_line.update_traces(line_color='#00CC96') # Color Cyan/Verdoso
st.plotly_chart(fig_line, use_container_width=True)

###################################
# ### Paso 6: WordCloud (Lógica Corregida)
###################################

st.header('☁️ De qué hablamos (Word Cloud)')

# Definir Stopwords en Español (Agrega modismos locales si quieres limpiar más)
mis_stopwords = set(STOPWORDS)
mis_stopwords.update([
    'de', 'la', 'que', 'el', 'en', 'y', 'a', 'los', 'se', 'del', 'las', 'un', 
    'por', 'con', 'no', 'una', 'su', 'para', 'es', 'al', 'lo', 'como', 
    'más', 'pero', 'sus', 'le', 'ya', 'o', 'fue', 'este', 'ha', 'sí', 'porque',
    'esta', 'son', 'entre', 'está', 'cuando', 'muy', 'sin', 'sobre', 'ser', 
    'tengo', 'hay', 'mis', 'me', 'multimedia', 'omitido', 'te', 'yo', 'tu'
])

# Limpieza básica
def limpiar_texto(texto):
    texto = str(texto).lower()
    # Eliminar puntuación
    texto = texto.translate(str.maketrans('', '', string.punctuation))
    return texto

texto_total = " ".join(limpiar_texto(msj) for msj in df['Mensaje'] if '<Multimedia omitido>' not in msj)

# Configuración de WordCloud
# IMPORTANTE: Asegúrate de tener 'beer_icon.png' en la carpeta Resources
try:
    mask_img = np.array(Image.open('Resources\Ying_yang.jpg'))
    wc_height, wc_width = mask_img.shape[0], mask_img.shape[1]
except:
    mask_img = None # Fallback si no hay imagen
    wc_height, wc_width = 800, 800

wordcloud = WordCloud(
    width=wc_width, height=wc_height,
    background_color='black',
    stopwords=mis_stopwords,
    mask=mask_img,
    contour_width=1,
    contour_color='cyan', # Borde neón
    colormap='viridis',   # Colores más fríos/tech
    max_words=150
).generate(texto_total)

col_wc1, col_wc2 = st.columns([3,1])
with col_wc1:
    st.image(wordcloud.to_array(), use_container_width=True)
with col_wc2:
    st.markdown("""
    **Notas:**
    - Se eliminaron palabras comunes (stopwords).
    - Se filtró 'Multimedia omitido'.
    - Si ves muchos 'jajaja', es buena señal.
    """)

st.markdown("---")
st.markdown("© 2025 — **Cain Lin** | Data Science & Bro Code")