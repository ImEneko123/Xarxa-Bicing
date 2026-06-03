import streamlit as st
import pickle
import pandas as pd
import datetime
import requests
import io
@st.cache_resource
def carregar_model_des_de_dropbox():
    url = "https://www.dropbox.com/scl/fi/7q27qgr70j41byczov5q2/model_bicing_bosc.pkl?rlkey=tm9sr1sgbv5uin3uha0br4h3r&st=u489vb8v&dl=1"
    
    resposta = requests.get(url)
    
    fitxer_memoria = io.BytesIO(resposta.content)
    return pickle.load(fitxer_memoria)

# Carreguem el model
model_bicing_bosc = carregar_model_des_de_dropbox()
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

estacio_seleccionada = st.selectbox(
    "Busca per carrer o número d'estació:",
    llista_opcions,
    index=None,
    placeholder="Escriu per buscar...",
)

# Si no ha triat res encara, mostrem un avís i aturem l'execució de la web
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

# Calculem l'hora actual a Barcelona
ara = pd.Timestamp.now(tz='Europe/Madrid')

# Calculem el moment futur sumant-hi els minuts
moment_futur = ara + pd.Timedelta(minutes=int(minuts_futur))

# Actualitzem les variables per a la IA amb el temps futur
hora_decimal = moment_futur.hour + (moment_futur.minute / 60.0)
dia_setmana = moment_futur.weekday() # 0=Dilluns

st.info(f"Predicció per a: **{moment_futur.strftime('%H:%M')}** ({moment_futur.strftime('%A')})")

import requests

def obtenir_clima_futur(lat, lon, hora_seleccionada):
    
    api_key = "c9dc5c80c2fb4a5195b153641260306" 
    
    # URL de previsió per a les coordenades
    url = f"http://api.weatherapi.com/v1/forecast.json?key={api_key}&q={lat},{lon}&days=1&aqi=no&alerts=no"
    
    try:
        resposta = requests.get(url).json()
        
        index_hora = int(hora_seleccionada)
        dades_hora = resposta['forecast']['forecastday'][0]['hour'][index_hora]
        
        # Extraiem la temperatura
        temp_actual = dades_hora['temp_c']
        
        # Mirem si plou
        pluja_activa = dades_hora['will_it_rain']
        
        return temp_actual, pluja_activa

    except Exception as e:
        st.error(f"Error en connectar amb WeatherAPI: {e}")
        return 18.0, 0  
        
    index_hora = int(hora_seleccionada)
    temp_actual = resposta['hourly']['temperature_2m'][index_hora]
    pluja_raw = resposta['hourly']['precipitation'][index_hora]
    
    # Convertim la pluja a binari
    pluja_activa = 1 if pluja_raw > 0 else 0
    
    return temp_actual, pluja_activa
# Cridem a la nova funció passant-li la latitud, longitud i l'hora
temp_actual, pluja_actual = obtenir_clima_futur(lat, lon, hora_decimal)

#Ensenyem el clima
st.write(f"**Clima previst per a aquesta hora:** {temp_actual}°C i {'amb pluja' if pluja_actual == 1 else 'sense pluja'}")

#Saber si l'estació esta tancada o oberta
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
                estat_text = estacio['status']
                
                # Ho convertim a binari
                if estat_text == 'IN_SERVICE':
                    return 1
                else:
                    return 0
                    
    # Si alguna cosa falla amb la cerca assumim que està oberta
    return 1
id_seleccionat = df_estacions[df_estacions['opcio_visual'] == estacio_seleccionada]['id'].values[0]
status_actual = obtenir_estat_estacio(id_seleccionat)
# -------------------------------------------------------------Fer la predicció ---------------------------------------------------------
input_dades = pd.DataFrame([[hora_decimal, dia_setmana, lat, lon, temp_actual, pluja_actual, status_actual]], 
                           columns=['hora_decimal', 'dia_setmana', 'latitude', 'longitude', 'temperature_2m', 'pluja_activa', 'status_num'])
ordre_correcte = ['hora_decimal', 'dia_setmana', 'latitude', 'longitude', 'temperature_2m', 'pluja_activa', 'status_num']
input_dades = input_dades[ordre_correcte]

# Fem la predicció finalment
prediccio = model_bicing_bosc.predict(input_dades)[0]

if st.button("Consultar Bicis Disponibles"):
    prediccio = model_bicing_bosc.predict(input_dades)[0]
    
    st.metric(label="Bicicletes disponibles estimades", value=f"{round(prediccio, 1)}")
    
    if prediccio < 1:
        st.error("L'estació probablement no en tindra cap")
    elif prediccio < 3:
        st.warning("Quedaran molt poques bicis")
    elif prediccio < 6:
        st.success("Hi haurà bicis suficients")
    else:
        st.success("Hi haurà moltes bicis")
#Que rep l'IA
st.write(input_dades)
