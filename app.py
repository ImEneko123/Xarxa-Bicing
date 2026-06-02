import streamlit as st
import pickle
import pandas as pd
import datetime

#Text a la pagina + Titol
st.set_page_config(page_title="Bicing Predictor BCN", page_icon="👍")

st.title("Predicció de Bicing Barcelona")
st.write("Aquesta xarxa prediu quantes bicis hi haurà quan arribis a la teva estació.")

#Carregar el model
@st.cache_resource
def carregar_model():
    with open('model_bicing_arbre.pkl', 'rb') as f:
        return pickle.load(f)

model = carregar_model()

#Elements interactius
st.sidebar.header("Configurar els parametres")

# Slider per als minuts d'antelació
minuts_futur = st.text_input("Minuts per arribar:")

st.subheader("Selecció d'Estació")
# Combinem l'id real i el nom del carrer
df_estacions['opcio_visual'] = "Estació " + df_estacions['id'].astype(str) + " - " + df_estacions['name']

llista_opcions = sorted(df_estacions['opcio_visual'].unique())

estacio_seleccionada = st.selectbox(
    "Busca per carrer o número d'estació:",
    llista_opcions,
    index=0,
    placeholder="Escriu per buscar...",
)

fila_estacio = df_estacions[df_estacions['opcio_visual'] == estacio_seleccionada].iloc[0]
lat = fila_estacio['latitude']
lon = fila_estacio['longitude']

#Logica del temps
ara = datetime.datetime.now()
moment_futur = ara + datetime.timedelta(minutes=minuts_futur)

# Convertim a les variables que l'arbre entén
hora_decimal = moment_futur.hour + (moment_futur.minute / 60.0)
dia_setmana = moment_futur.weekday() # 0=Dilluns

st.info(f"Predicció per a: **{moment_futur.strftime('%H:%M')}** ({moment_futur.strftime('%A')})")

# --- 4. PREDICCIÓ ---
# Nota: L'ordre ha de ser EXACTAMENT el mateix que vas usar al X_train de Kaggle
# Suposem l'ordre: hora_decimal, dia_setmana, lat, lon
input_dades = pd.DataFrame([[hora_decimal, dia_setmana, lat, lon]], 
                           columns=['hora_decimal', 'dia_setmana', 'latitude', 'longitude'])

if st.button("Consultar disponibilitat"):
    prediccio = model.predict(input_dades)[0]
    
    # Resultat visual
    st.metric(label="Bicicletes estimades", value=f"{round(prediccio, 1)} 🚲")
    
    if prediccio < 1:
        st.error("⚠️ Sembla que l'estació estarà buida!")
    elif prediccio < 3:
        st.warning("🧐 Quedaran poques bicis, afanya't!")
    else:
        st.success("✅ Hi haurà bicis de sobra!")
