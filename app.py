import streamlit as st
import pickle
import pandas as pd
import datetime
import requests

#Text a la pagina + Titol
st.set_page_config(page_title="Bicing Predictor BCN", page_icon="👍")

st.title("Predicció de Bicing Barcelona")
st.write("Aquesta xarxa prediu quantes bicis hi haurà quan arribis a la teva estació.")

#Carregar el model
@st.cache_resource
def carregar_model():
    with open('model_bicing_bosc.pkl', 'rb') as f:
        return pickle.load(f)

model = carregar_model()

# Graella per als minuts d'antelació
minuts_futur = st.text_input("Minuts per arribar:")

@st.cache_data
def carregar_estacions():
    return pd.read_csv('estacions_bicing.csv')

df_estacions = carregar_estacions()
# Combinem l'id real i el nom del carrer
st.subheader("Selecció d'Estació")
df_estacions['opcio_visual'] = "Estació " + df_estacions['id'].astype(str) + " - " + df_estacions['streetName']

llista_opcions = sorted(df_estacions['opcio_visual'].unique())

# El desplegable ara té index=None perquè surti BUIT per defecte
estacio_seleccionada = st.selectbox(
    "Busca per carrer o número d'estació:",
    llista_opcions,
    index=None,
    placeholder="Escriu per buscar...",
)

# ATENCIÓ: Si no ha triat res encara, mostrem un avís i ATUREM l'execució de la web
if not estacio_seleccionada:
    st.info("Busca i selecciona una estació de Bicing per començar.")
    st.stop()

# Si ja ha triat una estació, el codi continua i busquem les coordenades
fila_estacio = df_estacions[df_estacions['opcio_visual'] == estacio_seleccionada].iloc[0]
lat = fila_estacio['latitude']
lon = fila_estacio['longitude']

# Comprovem si la capsa està buida. Si ho està, posem un 0 per defecte
if not minuts_futur:
    minuts_futur = 0

# 1. Calculem l'hora ACTUAL a Barcelona (el teu codi original era perfecte)
ara = pd.Timestamp.now(tz='Europe/Madrid')

# 2. Calculem el moment FUTUR sumant-hi els minuts
moment_futur = ara + pd.Timedelta(minutes=int(minuts_futur))

# 3. ⚠️ AQUÍ ESTÀ LA CLAU: Actualitzem les variables per a la IA amb el temps FUTUR
hora_decimal = moment_futur.hour + (moment_futur.minute / 60.0)
dia_setmana = moment_futur.weekday() # 0=Dilluns

# A partir d'aquí, ja pots deixar l'st.info que tenies a la línia 69:
# st.info(f"Predicció per a: **{moment_futur.strftime('%H:%M')}**...")



st.info(f"Predicció per a: **{moment_futur.strftime('%H:%M')}** ({moment_futur.strftime('%A')})")

import requests

def obtenir_clima_futur(lat, lon, hora_seleccionada):
    # Demanem la previsió horària (hourly), no el temps actual
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,precipitation"
    
    resposta = requests.get(url).json()
    
    # Open-Meteo ens torna una llista amb les pròximes hores.
    # Si volem el temps d'una hora concreta d'avui (ex: les 23h), busquem el seu índex:
    index_hora = int(hora_seleccionada)
    
    temp_actual = resposta['hourly']['temperature_2m'][index_hora]
    pluja_raw = resposta['hourly']['precipitation'][index_hora]
    
    # Convertim la pluja a binari (0 o 1) per al teu model
    pluja_activa = 1 if pluja_raw > 0 else 0
    
    return temp_actual, pluja_activa

# Cridem a la nova funció passant-li la latitud, longitud i l'hora de l'slider
temp_actual, pluja_actual = obtenir_clima_futur(lat, lon, hora_decimal)

# (Opcional) Mostrem a la web el clima detectat per a aquella hora
st.write(f"**Clima previst per a aquesta hora:** {temp_actual}°C i {'amb pluja' if pluja_actual == 1 else 'sense pluja'}")

#Saber si esta tancada o oberta
def obtenir_estat_estacio(id_estacio):
    url = "https://api.bsmsa.eu/ext/api/bsm/gbfs/v2/en/station_status"
    resposta = requests.get(url)
    
    # Comprovem que la petició ha anat bé
    if resposta.status_code == 200:
        dades = resposta.json()
        estacions = dades['data']['stations']
        
        # Busquem la nostra estació a la llista
        for estacio in estacions:
            if int(estacio['station_id']) == int(id_estacio):
                estat_text = estacio['status'] # Aquí dirà 'IN_SERVICE' o 'CLOSED'
                
                # Ho convertim a números per la nostra IA (1 = Obert, 0 = Tancat)
                if estat_text == 'IN_SERVICE':
                    return 1
                else:
                    return 0
                    
    # Si alguna cosa falla amb l'internet, assumim que està oberta (1) per no trencar l'app
    return 1
id_seleccionat = df_estacions[df_estacions['opcio_visual'] == estacio_seleccionada]['id'].values[0]
status_actual = obtenir_estat_estacio(id_seleccionat)
# --- 4. PREDICCIÓ ---
# Nota: L'ordre ha de ser EXACTAMENT el mateix que vas usar al X_train de Kaggle
# Suposem l'ordre: hora_decimal, dia_setmana, lat, lon
# Forcem el DataFrame a tenir l'ordre exacte de Kaggle abans de predir
input_dades = pd.DataFrame([[hora_decimal, dia_setmana, lat, lon, temp_actual, pluja_actual, status_actual]], 
                           columns=['hora_decimal', 'dia_setmana', 'latitude', 'longitude', 'temperature_2m', 'pluja_activa', 'status_num'])
ordre_correcte = ['hora_decimal', 'dia_setmana', 'latitude', 'longitude', 'temperature_2m', 'pluja_activa', 'status_num']
input_dades = input_dades[ordre_correcte]

# Ara sí, fem la predicció de forma segura
prediccio = model.predict(input_dades)[0]

if st.button("Consultar Disponibilita"):
    prediccio = model.predict(input_dades)[0]
    
    st.metric(label="Bicicletes disponibles estimades", value=f"{round(prediccio, 1)}")
    
    if prediccio < 1:
        st.error("L'estació probablement no en tindra cap")
    elif prediccio < 3:
        st.warning("Quedaran molt poques bicis")
    elif prediccio < 6:
        st.success("Hi haurà bicis suficients")
    else:
        st.success("Hi haurà moltes bicis")
# Això ens ensenyarà la taula a la web per "espiar" què rep la IA
st.write(input_dades)

# El teu codi de predicció de sota:
prediccio = model.predict(input_dades)[0]
