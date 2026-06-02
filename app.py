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
    with open('model_bicing_arbre(2).pkl', 'rb') as f:
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

#Temps Actual
ara = pd.Timestamp.now(tz='Europe/Madrid')
# Comprovem si la capsa està buida. Si ho està, posem un 0 per defecte
if not minuts_futur:
    minuts_futur = 0

# Ara ja podem fer la suma tranquil·lament perquè segur que hi ha un número
moment_futur = ara + datetime.timedelta(minutes=int(minuts_futur))
# Convertim a les variables que l'arbre entén
hora_decimal = moment_futur.hour + (moment_futur.minute / 60.0)
dia_setmana = moment_futur.weekday() # 0=Dilluns

st.info(f"Predicció per a: **{moment_futur.strftime('%H:%M')}** ({moment_futur.strftime('%A')})")

def obtenir_clima(latitud, longitud):
    # Demanem a l'API la temperatura i la pluja actuals
    url = f"https://api.open-meteo.com/v1/forecast?latitude={latitud}&longitude={longitud}&current=temperature_2m,rain"
    
    try:
        resposta = requests.get(url)
        dades_clima = resposta.json()
        
        temp = dades_clima['current']['temperature_2m']
        pluja_mm = dades_clima['current']['rain']
        
        # Si cauen més de 0mm, considerem que plou (1), si no (0)
        pluja_activa = 1 if pluja_mm > 0 else 0
        
        return temp, pluja_activa
    except:
        # Pla B: Si l'API cau o no hi ha internet, posem un valor estàndard per no trencar la web
        return 18.0, 0
temp_actual, pluja_actual = obtenir_clima(lat, lon)
estat_pluja = "Plovent" if pluja_actual == 1 else "Sense pluja"
st.write(f"**Clima actual a la zona:** {temp_actual}°C i {estat_pluja}")

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
input_dades = pd.DataFrame([[hora_decimal, dia_setmana, lat, lon, temp_actual, pluja_actual, status_actual]], 
                           columns=['hora_decimal', 'dia_setmana', 'latitude', 'longitude', 'temperature_2m', 'pluja_activa', 'status'])

if st.button("Consultar Disponibilitat Real"):
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
