import ee
import math
from datetime import date, timedelta # Importar timedelta
from dotenv import load_dotenv
import os
load_dotenv()
# Inicializar Earth Engine
credentials = ee.ServiceAccountCredentials(
    email=None,
    key_file=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
)
ee.Initialize(credentials=credentials, project=os.getenv("GEE_PROJECT"))


def get_wind_speed(lat, lon):
    """
    Obtiene la velocidad del viento (en m/s) a ~1.5 km, ~5.5 km y ~9-10 km
    usando datos de ECMWF ERA5 para la fecha disponible más reciente.
    """

    point = ee.Geometry.Point([lon, lat])

    # --- CORRECCIÓN DE FECHA ---
    # Usar el rango de fechas de ayer a hoy para capturar el último día completo.
    today = date.today()
    yesterday = today - timedelta(days=1)
    
    # El filtro de fecha buscará la colección entre el inicio de ayer y el final de hoy
    # Usaremos un rango de 2 días completos para aumentar las posibilidades de éxito.
    start_date = (today - timedelta(days=2)).isoformat()
    end_date = today.isoformat()
    print(f"📅 Buscando datos entre: {start_date} y {end_date}")
    # ---------------------------

    DATASET_ID = "ECMWF/ERA5/HOURLY"
    
    dataset_full = ee.ImageCollection(DATASET_ID).select(
        ["u_component_of_wind", "v_component_of_wind"]
    )
    
    def wind_speed_ee(u, v):
        return u.pow(2).add(v.pow(2)).sqrt()

    levels = {850: "~1.5 km", 500: "~5.5 km", 300: "~9–10 km"}
    results = {}

    for level, height in levels.items():
        
        # 1. FILTRAR la colección por RANGO DE FECHAS y NIVEL DE PRESIÓN
        dataset_filtered = dataset_full.filter(
            ee.Filter.And(
                ee.Filter.eq("pressure_level", level),
                ee.Filter.date(start_date, end_date) # Usar el rango de 2 días
            )
        )

        # 2. OBTENER la imagen más reciente (o la primera si el orden no importa)
        # Esto asegura que si hay datos en el rango, obtenemos algo.
        image = dataset_filtered.sort('system:time_start', False).first()
        
        if image is None:
            print(f"⚠️ No hay datos disponibles para el nivel {level}hPa en el rango.")
            results[height] = None
            continue # Saltar al siguiente nivel si no hay imagen

        # 3. SELECCIÓN y CÁLCULO
        try:
            # Las bandas se seleccionan de la imagen única
            u = image.select("u_component_of_wind")
            v = image.select("v_component_of_wind")
            
            # Calcular velocidad total
            speed = wind_speed_ee(u, v)

            # Reducir al punto
            value = speed.reduceRegion(
                reducer=ee.Reducer.mean(), 
                geometry=point, 
                scale=10000 
            ).getInfo()

            if value:
                speed_key = list(value.keys())[0]
                total_speed = value[speed_key]
                results[height] = round(total_speed, 2)
            else:
                results[height] = None

        except Exception as e:
             # Este bloque atrapa si, por alguna razón, la banda no existe en la imagen filtrada.
             print(f"❌ Error al procesar nivel {level}hPa: {e}")
             results[height] = None


    return results


# 🔍 Ejemplo de uso:
coords = {"lat": 19.4326, "lon": -99.1332}  # Ciudad de México
wind_data = get_wind_speed(coords["lat"], coords["lon"])
print("\n🌬️ Velocidades del viento (m/s):")
print(wind_data)