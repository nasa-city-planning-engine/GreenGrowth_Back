import ee
import math
from datetime import date
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
    usando datos de ECMWF ERA5 para la fecha actual.
    """

    # Crear geometría del punto
    point = ee.Geometry.Point([lon, lat])

    # Fecha actual
    today = date.today().isoformat()
    print(f"📅 Fecha: {today}")

    # Dataset ERA5 (niveles de presión)
    dataset = ee.ImageCollection("ECMWF/ERA5/DAILY").select(
        ["u_component_of_wind", "v_component_of_wind"]
    )

    # Imagen del día
    image = dataset.filterDate(today).first()
    if image is None:
        print("⚠️ No hay datos disponibles para la fecha actual.")
        return None

    # Función para calcular velocidad del viento
    def wind_speed(u, v):
        return u.pow(2).add(v.pow(2)).sqrt()

    # Niveles de presión y alturas aproximadas
    levels = {850: "~1.5 km", 500: "~5.5 km", 300: "~9–10 km"}

    results = {}

    for level, height in levels.items():
        # Filtrar las bandas por nivel de presión
        u = image.select("u_component_of_wind").filter(
            ee.Filter.eq("pressure_level", level)
        )
        v = image.select("v_component_of_wind").filter(
            ee.Filter.eq("pressure_level", level)
        )

        # Calcular velocidad total
        speed = wind_speed(u, v).mean()

        # Reducir al punto
        value = speed.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=point, scale=10000
        ).getInfo()

        if value:
            # Extraer magnitud total
            u_val = value.get("u_component_of_wind", 0)
            v_val = value.get("v_component_of_wind", 0)
            total_speed = math.sqrt(u_val**2 + v_val**2)
            results[height] = round(total_speed, 2)
        else:
            results[height] = None

    return results


# 🔍 Ejemplo de uso:
coords = {"lat": 19.4326, "lon": -99.1332}  # Ciudad de México
wind_data = get_wind_speed(coords["lat"], coords["lon"])
print("\n🌬️ Velocidades del viento (m/s):")
print(wind_data)
