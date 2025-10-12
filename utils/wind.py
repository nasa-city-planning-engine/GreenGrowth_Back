import ee
import math
from datetime import date, timedelta
from dotenv import load_dotenv
import os
load_dotenv()

# Inicializar Earth Engine (se mantiene la inicialización)
credentials = ee.ServiceAccountCredentials(
    email=None,
    key_file=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
)
ee.Initialize(credentials=credentials, project=os.getenv("GEE_PROJECT"))


def get_wind_speed(lat, lon):
    """
    Obtiene la velocidad media del viento a 10m (u10, v10) para el mes pasado (del año anterior),
    calculada en tres radios de influencia (1km, 5km, 10km) para simular la dispersión.
    Devuelve los resultados como una lista [1km_radius, 5km_radius, 10km_radius].
    """

    point = ee.Geometry.Point([lon, lat])

    # --- LÓGICA DE FECHA (SE MANTIENE, ES ROBUSTA) ---
    today = date.today()
    target_date = today - timedelta(days=365)
    start_month = target_date.replace(day=1)
    
    if start_month.month == 12:
        end_month = start_month.replace(year=start_month.year + 1, month=1)
    else:
        end_month = start_month.replace(month=start_month.month + 1)
        
    start_date = start_month.isoformat()
    end_date = end_month.isoformat()
    # ----------------------------------------------------

    # --- DEFINICIÓN DEL DATASET (ERA5_LAND/HOURLY) ---
    DATASET_ID = "ECMWF/ERA5_LAND/HOURLY"
    dataset_full = ee.ImageCollection(DATASET_ID).select(["u_component_of_wind_10m", "v_component_of_wind_10m"])
    
    # Función para calcular velocidad del viento
    def wind_speed_ee(u, v):
        return u.pow(2).add(v.pow(2)).sqrt()
    
    print(f"📅 Calculando media para el mes: {start_month.strftime('%Y-%m')}")
    print("--------------------------------------------------")

    # 1. FILTRAR y REDUCIR la COLECCIÓN a una única imagen de MEDIA MENSUAL (ROBUSTA)
    dataset_filtered = dataset_full.filterDate(start_date, end_date)
    mean_image = dataset_filtered.mean() # Esta imagen contiene la media de u10 y v10 del mes
    
    if mean_image is None:
        print(f"⚠️ No se encontraron datos para la media mensual en el rango.")
        return [0.0, 0.0, 0.0]

    # SELECCIÓN de componentes medios de la imagen única
    u_mean = mean_image.select("u_component_of_wind_10m")
    v_mean = mean_image.select("v_component_of_wind_10m")
    
    # Calcular la magnitud de la velocidad media (resulta en una ee.Image)
    speed_image = wind_speed_ee(u_mean, v_mean)

    # Definimos los radios de dispersión que el modelo espera: 1km, 5km, 10km (en metros)
    # NOTA: En reduceRegion, 'scale' define la resolución de pixel, no el radio de influencia.
    # Usaremos 'geometry' con un buffer para definir el radio de influencia, 
    # y 'scale' como la resolución de muestreo.
    
    # Definimos las escalas de análisis que corresponden a la dispersión que espera el modelo.
    # Los valores 1000, 5000, 10000 m representan la distancia alrededor del punto.
    DISPERSION_RADII = [1000, 5000, 10000] # Radios en metros (1km, 5km, 10km)

    results_list = []
    
    # 3. REDUCIR la IMAGEN DE VELOCIDAD en MÚLTIPLES RADIOS
    for radius in DISPERSION_RADII:
        # Crear un buffer (círculo) alrededor del punto
        buffered_point = point.buffer(radius) 
        
        try:
            # Reducir la región definida por el buffer
            value = speed_image.reduceRegion(
                reducer=ee.Reducer.mean(), 
                geometry=buffered_point, # Usar el buffer como geometría de reducción
                scale=1000,               # Usar una escala de muestreo fija (1km) para la precisión
                maxPixels=1e13
            ).getInfo()

            if value:
                speed_key = list(value.keys())[0]
                total_speed = round(value[speed_key], 2)
                results_list.append(total_speed)
                print(f"✅ Velocidad a {radius/1000}km de radio: {total_speed} m/s")
            else:
                results_list.append(0.0)
                print(f"❌ Valor nulo en {radius/1000}km de radio.")

        except Exception as e:
            results_list.append(0.0)
            print(f"❌ Error GEE en radio {radius/1000}km: {e}")

    # 4. DEVOLVER EL ARRAY REQUERIDO POR EL MODELO
    return results_list


# 🔍 Ejemplo de uso (la lat/lon debe ser tu punto de interés)
coords = {"lat": 19.4326, "lon": -99.1332} 
wind_data = get_wind_speed(coords["lat"], coords["lon"])

print("\n--------------------------------------------------")
print("🌬️ Array final para el Modelo:")
print(f"# -- Wind Speed --")
print(f"{wind_data[0]},           # Wind Speed 1km Radius")
print(f"{wind_data[1]},           # Wind Speed 5km Radius")
print(f"{wind_data[2]}            # Wind Speed 10km Radius")