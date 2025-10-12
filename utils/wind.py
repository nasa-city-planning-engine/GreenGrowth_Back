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
    Obtains wind speed for the industrial prediction model
    """

    point = ee.Geometry.Point([lon, lat])
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

    # --- (ERA5_LAND/HOURLY) -----------------------------
    DATASET_ID = "ECMWF/ERA5_LAND/HOURLY"
    dataset_full = ee.ImageCollection(DATASET_ID).select(["u_component_of_wind_10m", "v_component_of_wind_10m"])
    
    def wind_speed_ee(u, v):
        return u.pow(2).add(v.pow(2)).sqrt()
    
    print(f"📅 Calculating median for {start_month.strftime('%Y-%m')}")



    dataset_filtered = dataset_full.filterDate(start_date, end_date)
    mean_image = dataset_filtered.mean() 
    
    if mean_image is None:
        print(f"Data not found in the range provided.")
        return [0.0, 0.0, 0.0]

    u_mean = mean_image.select("u_component_of_wind_10m")
    v_mean = mean_image.select("v_component_of_wind_10m")
    
    speed_image = wind_speed_ee(u_mean, v_mean)

    DISPERSION_RADII = [1000, 5000, 10000] # Radius in meters (1km, 5km, 10km)

    results_list = []
    
    for radius in DISPERSION_RADII:
        buffered_point = point.buffer(radius) 
        
        try:
            value = speed_image.reduceRegion(
                reducer=ee.Reducer.mean(), 
                geometry=buffered_point, 
                scale=1000,               
                maxPixels=1e13
            ).getInfo()

            if value:
                speed_key = list(value.keys())[0]
                total_speed = round(value[speed_key], 2)
                results_list.append(total_speed)
                print(f"Wind speed in {radius/1000}km radius of: {total_speed} m/s")
            else:
                results_list.append(0.0)
                print(f"Null value in {radius/1000} km radio.")

        except Exception as e:
            results_list.append(0.0)
            print(f"Error GEE in radius {radius/1000}km: {e}")

    # 4. Returns the array
    return results_list


# Ejemplo de uso (la lat/lon debe ser tu punto de interés)
# coords = {"lat": 19.4326, "lon": -99.1332} 
# wind_data = get_wind_speed(coords["lat"], coords["lon"])

#print("\n--------------------------------------------------")
#print("🌬️ Array final para el Modelo:")
#print(f"# -- Wind Speed --")
#print(f"{wind_data[0]},           # Wind Speed 1km Radius")
#print(f"{wind_data[1]},           # Wind Speed 5km Radius")
#print(f"{wind_data[2]}            # Wind Speed 10km Radius")