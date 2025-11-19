import ee
import json
from typing import Dict, Any, Tuple, Optional, Union, List
import os
from dotenv import load_dotenv
import datetime
load_dotenv()

project_id = os.getenv("GEE_PROJECT")
key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")


print("="*30)
print(f"DEBUG: GEE_PROJECT leído: {project_id}")
print(f"DEBUG: GEE_CREDS_PATH leído: {key_path}")
print("="*30)

if not project_id:
    raise ValueError("Variable 'GEE_PROJECT' is not defined, please check your env variables")
if not key_path:
    raise ValueError("Variable 'GOOGLE_APPLICATION_CREDENTIALS' is not defined, please check your env variables")

try:
    credentials = ee.ServiceAccountCredentials(None, key_file=key_path)

    ee.Initialize(
        credentials=credentials,
        project=project_id,
        opt_url='https://earthengine-highvolume.googleapis.com'
    )
    
    print("GEE LIVE")

except Exception as e:
    print(f"Failed to connect to GEE: {e}")

    raise e

_GA_CFG = {
    "date_month": ("2025-05-01", "2025-05-31"),
    "date_year": ("2023-01-01", "2023-12-31"),
    "vis": {
        "temp": {
            "min": -25,
            "max": 50,
            "palette": [
                "#000080",
                "#0000FF",
                "#00FFFF",
                "#00FF00",
                "#ADFF2F",
                "#FFFF00",
                "#FFA500",
                "#FF4500",
                "#FF0000",
                "#8B0000",
                "#FFFFFF",
            ],
        },
        "ndvi": {
            "min": 0,
            "max": 0.7,
            "palette": ["#ff0000", "#ffff00", "#00ff00", "#004d00"],
        },
        "aq": {
            "min": 0,
            "max": 100,
            "palette": ["#2DC937", "#E7B416", "#E77D11", "#CC3232", "#6B1A6B"],
        },
    },
    "norm_user": {
        # existentes (residencial)
        "densidad": {"buildings_per_km2": {"min": 0.0, "max": 1000.0}},
        "trafico": {"veh_day": {"min": 0.0, "max": 20000.0}},
        "albedo": {
            "albedo_0_1": {"min": 0.0, "max": 1.0},
            "cool_roof_pct": {"min": 0.0, "max": 100.0},
        },
        # nuevos (area verde)
        "arboles": {"trees_per_ha": {"min": 0.0, "max": 400.0}},
        "pasto": {"pct": {"min": 0.0, "max": 100.0}},
        "copa": {"pct": {"min": 0.0, "max": 100.0}},
    },
    "aq_sources": {
        "COPERNICUS/S5P/NRTI/L3_NO2": ("NO2_column_number_density", (0.0, 2e-4)),
        "COPERNICUS/S5P/NRTI/L3_SO2": ("SO2_column_number_density", (0.0, 1e-4)),
        "COPERNICUS/S5P/NRTI/L3_O3": ("O3_column_number_density", (0.0, 3e-4)),
        "COPERNICUS/S5P/NRTI/L3_CO": ("CO_column_number_density", (0.0, 3e-2)),
        "COPERNICUS/S5P/NRTI/L3_AER_AI": ("absorbing_aerosol_index", (-1.0, 2.0)),
    },
    "presets": {
        "green_area": "NDVI_p90",
        "residential": "NDVI_p50",
        "industrial": "NDVI_p10",
    },
}




# --- FUNCIÓN HELPER PARA ENMASCARAR NUBES ---
# Esta función es necesaria para limpiar las imágenes de Sentinel-2
def mask_s2_scl(image):
    """Enmascara nubes, sombras y nieve en una imagen Sentinel-2 SR usando la banda SCL."""
    scl = image.select("SCL")

    # Clases a conservar: 4 (vegetación), 5 (suelo desnudo), 6 (agua)
    valid_pixels = scl.eq(4).Or(scl.eq(5)).Or(scl.eq(6))

    # La colección S2_SR_HARMONIZED requiere una división por 10000 para obtener la reflectancia
    return image.updateMask(valid_pixels).divide(10000)


class GeoAnalytics:
    _CFG = _GA_CFG

    def __init__(
        self,
        latitude: float,
        longitude: float,
        buffer: int = 50000,
        temp_industry=0,
        aq_industry=0,
    ):

        self.latitude, self.longitude, self.buffer = latitude, longitude, buffer
        self.region = ee.Geometry.Point(self.longitude, self.latitude).buffer(
            self.buffer
        )

        self.avg_surface_temp = None
        self.avg_NVDI = None
        self.avg_air_quality = None


        self.temp_image: ee.Image = None
        self.ndvi: ee.Image = None
        self.ndbi: ee.Image = None
        self.aq_index: ee.Image = None
        self.sim_temp: ee.Image = None
        self.sim_ndvi: ee.Image = None
        self.sim_aq: ee.Image = None
        self.reg_coefs: Optional[Dict[str, List[ee.Number]]] = None
        self.metrics: Optional[Dict[str, Dict[str, ee.Number]]] = None
        self.attr_norm: Dict[str, Any] = self._CFG["norm_user"]
        self.temp_industry = temp_industry
        self.aq_industry = aq_industry

        self._initialize_vis_params()
        self._calculate_base_layers()

    # --- Métodos de utilidad estáticos y privados ---

    def _initialize_vis_params(self):
        """
        Sets the visualization parameters for map tiles (temperature, NDVI, air quality).
        """
        self.temp_vis_params = self._CFG["vis"]["temp"]
        self.ndvi_vis_params = self._CFG["vis"]["ndvi"]
        self.aq_vis_params = self._CFG["vis"]["aq"]
        print("🎨 Visualization parameters initialized.")

    @staticmethod
    def _normalize(img: ee.Image, vmin: float, vmax: float, to: int = 100) -> ee.Image:
        """Normalize one image from [0, to]."""
        return (
            img.subtract(vmin)
            .divide(ee.Number(vmax).subtract(vmin))
            .multiply(to)
            .clamp(0, to)
        )

    @staticmethod
    def _mean(img: ee.Image, scale: int, geom: ee.Geometry) -> ee.Dictionary:
        """Calculates the mean of one geometry image object"""
        return img.reduceRegion(
            ee.Reducer.mean(), geom, scale, maxPixels=1e13, bestEffort=True, tileScale=4
        )

    @staticmethod
    def _geojson_to_ee_geom(geojson_area: Dict[str, Any]) -> ee.Geometry:
        """Converts a GeoJSON dictionary into Earth Engine geometry object."""
        return ee.Geometry(geojson_area)

    def _unit_range(self, var: str, unit: str) -> Tuple[ee.Number, ee.Number]:
        """Gets the minimum and maximun from one variable."""
        cfg = self.attr_norm.get(var, {}).get(unit)
        if cfg is None:
            raise ValueError(f"Unity not suported for {var}: {unit}")
        return ee.Number(cfg["min"]), ee.Number(cfg["max"])

    def _norm_value(
        self, x: Union[float, int, ee.Number], vmin: ee.Number, vmax: ee.Number
    ) -> ee.Number:
        """Normalize an scalar [0, 1]."""
        x = ee.Number(x)
        return x.subtract(vmin).divide(ee.Number(vmax).subtract(vmin)).clamp(0, 1)

    def _month(self, date_str: str) -> ee.Number:
        """Extract the month from an object"""
        return ee.Date(date_str).get("month")

    def _ndvi_percentiles_for_month(self, month_int: ee.Number) -> ee.Image:
        s2 = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(self.region)
            .filter(ee.Filter.calendarRange(month_int, month_int, "month"))
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 80))
            .map(mask_s2_scl)  
        )
        ndvi_ic = s2.map(lambda i: i.normalizedDifference(["B8", "B4"]).rename("NDVI"))
        return ndvi_ic.reduce(ee.Reducer.percentile([10, 50, 90])).rename(
            ["NDVI_p10", "NDVI_p50", "NDVI_p90"]
        )

    def get_tile_url(self, image, vis_params):
        """
        Generates a tile URL for a given Earth Engine image and visualization parameters.
        """
        map_id = image.clip(self.region).getMapId(vis_params)
        return map_id["tile_fetcher"].url_format

    def _get_normalized_gas(
        self,
        coll_id: str,
        band: str,
        vmin: float,
        vmax: float,
        date_range: Tuple[str, str],
    ) -> ee.Image:
        """
        Get and normalize a gas image from Sentinel-5P using OFFL. Eliminates QA filter and uses anual mean for consistency. 
        """

        def apply_qa(img: ee.Image) -> ee.Image:
            return img.select(band)

        collection = (
            ee.ImageCollection(coll_id)
            .filterBounds(self.region)
            .filterDate(*date_range)
            .map(apply_qa)  
            .mean()
        )

        normalized = self._normalize(collection, vmin, vmax, to=100)
        return normalized.rename("v")

    def _calculate_base_layers(self):
        """
        Calculates all base data layers from Earth Engine.
        This is run once on initialization to ensure API endpoints are responsive.
        Layers: Temperature, NDVI (vegetation), Air Quality (composite index).
        """
   
        #Todays date will always be yesterday-

        end_date = ee.Date(datetime.datetime.now()).advance(-7, 'day')

        #Monthly date will consider the median from the last month.

        start_date_monthly = end_date.advance(-1, 'month')
        date_range_monthly = (start_date_monthly, end_date)

        #Annual date will consider from last year to today.

        #! Not using year for a more agile development, in production change all none heat layers to yearly, in the current version the info is from only the last month. 
        start_date_annual = end_date.advance(-1, 'year')
        date_range_annual = (start_date_annual, end_date)  

        #Heat layer
        self.base_temp = (
            ee.ImageCollection("MODIS/061/MOD11A1")
            .filterBounds(self.region)
            .filterDate(*date_range_monthly)
            .median()
            .select("LST_Day_1km")
            .multiply(0.02)
            .subtract(273.15)
        )


        #NDVI layer
        s2_composite = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(self.region)
            .filterDate(*date_range_annual)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 80))
            .map(mask_s2_scl)  
            .median()
        )
        self.base_ndvi = s2_composite.normalizedDifference(["B8", "B4"]).rename("NDVI")
        self.ndbi = s2_composite.normalizedDifference(["B11", "B8"]).rename("NDBI")

    

        #Air quality layer
        aq_components = [
            self._get_normalized_gas(
                "COPERNICUS/S5P/OFFL/L3_NO2",
                "tropospheric_NO2_column_number_density",
                0.0,
                0.0002,
                date_range_monthly,
            ),
            self._get_normalized_gas(
                "COPERNICUS/S5P/OFFL/L3_SO2",
                "SO2_column_number_density",
                0.0,
                0.0005,
                date_range_monthly,
            ),
            self._get_normalized_gas(
                "COPERNICUS/S5P/OFFL/L3_O3",
                "O3_column_number_density",
                0.1,
                0.15,
                date_range_monthly,
            ),
            self._get_normalized_gas(
                "COPERNICUS/S5P/OFFL/L3_CO",
                "CO_column_number_density",
                0.0,
                0.05,
                date_range_monthly,
            ),
            self._get_normalized_gas(
                "COPERNICUS/S5P/OFFL/L3_AER_AI",
                "absorbing_aerosol_index",
                -1.0,
                2.0,
                date_range_annual,
            ),
        ]
        self.base_aq = (
            ee.ImageCollection(aq_components).mean().rename("AQ_Composite_0_100")
        )


        self.temp_image = self.base_temp
        self.ndvi = self.base_ndvi
        self.aq_index = self.base_aq
        print("🌍 Base layers calculated successfully.")

    def get_initial_kpis(self, layer_name):      
        if layer_name == 'heat': 
            try: 
                temp = self._mean(self.temp_image, 1000, self.region)
                temp_res = temp.getInfo()
                temp_kpi = temp_res.get("LST_Day_1km") if temp_res else None
                self.avg_surface_temp = temp_kpi

                return {
                    "avg_surface_temp": temp_kpi
                }
            except Exception as error: 
                print(f"Error while calculating the kpi's: {error}")
                return None 
                
                
        elif layer_name == 'NDVI': 
            try: 
                ndvi = self._mean(self.ndvi, 20, self.region)
                ndvi_res = ndvi.getInfo()
                nvdi_kpi = ndvi_res.get("NDVI") if ndvi_res else None
                self.avg_NVDI = nvdi_kpi
                
                return {
                    "avg_NVDI": nvdi_kpi
                }
            except Exception as error: 
                print(f"Error while calculating the kpi's: {error}")
                return None
                

        elif layer_name == 'AQ': 
            try: 
                air_q = self._mean(self.aq_index, 5000, self.region)
                air_q_res = air_q.getInfo()
                air_q_kpi = air_q_res.get("AQ_Composite_0_100") if air_q_res else None
                self.avg_air_quality = air_q_kpi
                
                return {
                    "avg_air_quality": air_q_kpi
                }
                

            except Exception as error: 
                print(f"Error while calculating the kpi's: {error}")
            

        

    def _fit_linear_models_simple(
        self, sample_scale: int = 10, n: int = 4000, seed: int = 13
    ) -> Dict[str, Dict[str, ee.Number]]:
        """Ajusta un modelo de regresión lineal simple (NDVI vs LST y NDVI vs AQ)."""
        samples = (
            self.temp_image.addBands(self.ndvi)
            .addBands(self.aq_index)
            .sample(
                region=self.region,
                scale=sample_scale,
                numPixels=n,
                geometries=False,
                seed=seed,
            )
        )
        count = samples.size().getInfo()
        print(f"   Scale: {sample_scale}m", flush=True)
        print(f"   Samples found in polygon: {count}", flush=True)

        def _fit(x: str, y: str) -> Dict[str, ee.Number]:
            fit = samples.reduceColumns(ee.Reducer.linearFit(), selectors=[x, y])
            res = fit.getInfo()
            print(f"   Fit {y} vs {x}: {res}", flush=True)
            return {"a": ee.Number(fit.get("scale")), "b": ee.Number(fit.get("offset"))}

        return {
            "LST": _fit("NDVI", "LST_Day_1km"),
            "AQ": _fit("NDVI", "AQ_Composite_0_100"),
        }

    def _linreg_metrics(
        self,
        features: ee.FeatureCollection,
        y_true_key: str = "y_true",
        y_pred_key: str = "y_pred",
    ) -> ee.List:
        """Calculates R^2 y RMSE from the FeatureCollection"""
        fc = features.filter(ee.Filter.notNull([y_true_key, y_pred_key]))
        y = ee.List(fc.aggregate_array(y_true_key))
        yhat = ee.List(fc.aggregate_array(y_pred_key))
        n = y.length().min(yhat.length())

        def _metrics(y: ee.List, yhat: ee.List, n: ee.Number) -> ee.List:
            mean_y = ee.Number(y.reduce(ee.Reducer.mean()))
            ss_tot = ee.Number(
                y.map(lambda v: ee.Number(v).subtract(mean_y).pow(2)).reduce(
                    ee.Reducer.sum()
                )
            )
            ss_res = ee.Number(
                y.zip(yhat)
                .map(
                    lambda p: ee.Number(ee.List(p).get(0))
                    .subtract(ee.Number(ee.List(p).get(1)))
                    .pow(2)
                )
                .reduce(ee.Reducer.sum())
            )
            r2 = ee.Number(1).subtract(ss_res.divide(ss_tot))
            rmse = ss_res.divide(ee.Number(n)).sqrt()
            return ee.List([r2, rmse])

        return ee.Algorithms.If(
            n.eq(0),
            ee.List([ee.Number(0), ee.Number(float("nan"))]),
            _metrics(y.slice(0, n), yhat.slice(0, n), n),
        )

    def calibrate_precision(
        self,
        train_frac: float = 0.7,
        sample_scale: int = 250,
        n_samples: int = 8000,
        seed: int = 42,
    ):
        """
        Adjust multiple linear reg models (LST ~ C + NDVI + NDBI; AQ ~ C + NDVI)
        and the score metrics (R^2, RMSE).
        """
        if self.ndbi is None:
            print("NDBI no calculated, using simple model for calibration.", flush=True)
            return

        X = (
            self.ndvi.rename("NDVI")
            .addBands(self.ndbi.rename("NDBI"))
            .addBands(ee.Image.constant(1).rename("C"))
        )
        feats = (
            X.addBands(self.temp_image.rename("LST"))
            .addBands(self.aq_index.rename("AQ"))
            .sample(
                region=self.region,
                scale=sample_scale,
                numPixels=n_samples,
                geometries=False,
                seed=seed,
            )
            .randomColumn("r", seed)
        )

        tr, te = feats.filter(ee.Filter.lt("r", train_frac)), feats.filter(
            ee.Filter.gte("r", train_frac)
        )

        #LST regression
        lst_reg = tr.reduceColumns(
            ee.Reducer.linearRegression(3, 1), selectors=["C", "NDVI", "NDBI", "LST"]
        )
        B = ee.Array(lst_reg.get("coefficients"))
        b0, b1, b2 = B.get([0, 0]), B.get([1, 0]), B.get([2, 0])
        yhat_LST = te.map(
            lambda f: f.set("y_true", f.get("LST")).set(
                "y_pred",
                ee.Number(b0)
                .add(ee.Number(f.get("NDVI")).multiply(b1))
                .add(ee.Number(f.get("NDBI")).multiply(b2)),
            )
        )
        mL = ee.List(self._linreg_metrics(yhat_LST))
        r2_LST, rmse_LST = ee.Number(mL.get(0)), ee.Number(mL.get(1))

        #Air quality regression
        aq_reg = tr.reduceColumns(
            ee.Reducer.linearRegression(2, 1), selectors=["C", "NDVI", "AQ"]
        )
        A = ee.Array(aq_reg.get("coefficients"))
        a0, a1 = A.get([0, 0]), A.get([1, 0])
        yhat_AQ = te.map(
            lambda f: f.set("y_true", f.get("AQ")).set(
                "y_pred", ee.Number(a0).add(ee.Number(f.get("NDVI")).multiply(a1))
            )
        )
        mA = ee.List(self._linreg_metrics(yhat_AQ))
        r2_AQ, rmse_AQ = ee.Number(mA.get(0)), ee.Number(mA.get(1))

        # Storing results
        self.reg_coefs = {"LST": [b0, b1, b2], "AQ": [a0, a1]}
        self.metrics = {
            "LST": {"r2": r2_LST, "rmse": rmse_LST},
            "AQ": {"r2": r2_AQ, "rmse": rmse_AQ},
        }
        print(
            f"Modelo LST: R^2={r2_LST.getInfo():.3f}, RMSE={rmse_LST.getInfo():.2f}°C"
        )
        print(f"Modelo AQ: R^2={r2_AQ.getInfo():.3f}, RMSE={rmse_AQ.getInfo():.2f}")


    def _attr_modifiers_real(
        self, densidad: Dict[str, Any], trafico: Dict[str, Any], albedo: Dict[str, Any]
    ) -> Tuple[ee.Number, ee.Number, ee.Number]:
        """Calculates moddifiers of NDVI, LST, y AQ based on real data"""
        dmin, dmax = self._unit_range("densidad", densidad["unit"])
        tmin, tmax = self._unit_range("trafico", trafico["unit"])
        amin, amax = self._unit_range("albedo", albedo["unit"])

        a_val = (
            ee.Number(albedo["value"]).divide(100.0).clamp(0, 1)
            if albedo["unit"] == "cool_roof_pct"
            else ee.Number(albedo["value"])
        )

        d = self._norm_value(densidad["value"], dmin, dmax)
        t = self._norm_value(trafico["value"], tmin, tmax)
        a = self._norm_value(a_val, amin, amax)

        ndvi_adj = ee.Number(0).subtract(d.multiply(0.12))
        lst_extra = d.multiply(3.0).add(t.multiply(1.5)).subtract(a.multiply(5.0))
        aq_extra = t.multiply(25.0).subtract(a.multiply(5.0))
        return ndvi_adj, lst_extra, aq_extra

    def _attr_modifiers_green(
        self,
        arboles: Dict[str, Any],
        pasto: Dict[str, Any],
        agua_bool: bool,
        copa: Dict[str, Any],
    ) -> Tuple[ee.Number, ee.Number, ee.Number]:
        """Calculates modifiers of NDVI, LST, y AQ based on attributes from the green area proposal. """
        amin, amax = self._unit_range("arboles", arboles["unit"])
        pmin, pmax = self._unit_range("pasto", pasto["unit"])
        cmin, cmax = self._unit_range("copa", copa["unit"])

        a_n = self._norm_value(arboles["value"], amin, amax)
        p_n = self._norm_value(pasto["value"], pmin, pmax)
        c_n = self._norm_value(copa["value"], cmin, cmax)

        ndvi_adj = a_n.multiply(0.10).add(p_n.multiply(0.06)).add(c_n.multiply(0.18))
        lst_extra = a_n.multiply(-2.0).add(p_n.multiply(-1.0)).add(c_n.multiply(-2.5))
        aq_extra = a_n.multiply(-10.0).add(p_n.multiply(-4.0)).add(c_n.multiply(-8.0))

        if agua_bool:
            ndvi_adj = ndvi_adj.add(0.03)
            lst_extra = lst_extra.add(-1.5)
            aq_extra = aq_extra.add(-3.0)

        ndvi_adj = ee.Number(ndvi_adj).clamp(-0.20, 0.30)
        lst_extra = ee.Number(lst_extra).clamp(-6.0, 6.0)
        aq_extra = ee.Number(aq_extra).clamp(-25.0, 25.0)
        return ndvi_adj, lst_extra, aq_extra

    def _apply_simulation(
        self,
        ee_geometry: ee.Geometry,
        ndvi_target: ee.Image,
        lst_extra: ee.Number,
        aq_extra: ee.Number,
    ):
        
        #Default values (to prevent breaking the system if one fails)
        def_lst_slope = ee.Number(-10)
        def_lst_offset = ee.Number(35)
        def_aq_slope = ee.Number(-20)
        def_aq_offset = ee.Number(50)

        used_model = "DEFAULT"

        mask = ee.Image(0).paint(ee_geometry, 1)
        ndvi_new = self.ndvi.where(mask, ndvi_target)

        #Use the models for LST and AQ
        if self.reg_coefs is not None and self.ndbi is not None:
            b0, b1, b2 = self.reg_coefs["LST"]
            a0, a1 = self.reg_coefs["AQ"]
            # LST: LST ~ C + NDVI + NDBI
            lst_reg = (
                ee.Image.constant(b0)
                .add(ndvi_new.multiply(b1))
                .add(self.ndbi.multiply(b2))
            )
            # AQ: AQ ~ C + NDVI
            aq_reg = ee.Image.constant(a0).add(ndvi_new.multiply(a1))
            used_model = "COMPLEX"
        else:
            try: 
                # Simple model (LST ~ NDVI, AQ ~ NDVI)
                s = self._fit_linear_models_simple(sample_scale=250)

                slope_lst = ee.Algorithms.If(s["LST"]["a"], s["LST"]["a"], slope_lst)
                offset_lst = ee.Algorithms.If(s["LST"]["b"], s["LST"]["b"], offset_lst)
                slope_aq = ee.Algorithms.If(s["AQ"]["a"], s["AQ"]["a"], slope_aq)
                offset_aq = ee.Algorithms.If(s["AQ"]["b"], s["AQ"]["b"], offset_aq)

                used_model = "SIMPLE CONFIRMED"
            except Exception as e: 
                print(f"⚠️ Simple model crashed (using defaults): {e}")
                used_model = "DEFAULT (Rescue)"

            lst_reg = ndvi_new.multiply(def_lst_slope).add(def_lst_offset)
            aq_reg = ndvi_new.multiply(def_aq_slope).add(def_aq_offset)
        
        print(f"🛡️ Simulation Strategy Used: {used_model}")
        self.sim_ndvi = ndvi_new

        self.sim_temp = (
            lst_reg
            .where(mask, lst_reg.add(lst_extra))
            .unmask(lst_extra.add(25)) # Si todo es null, pon 25°C + extra
            .rename("LST_Day_1km")
        )

        self.sim_aq = (
            aq_reg
            .where(mask, aq_reg.add(aq_extra))
            .unmask(aq_extra.add(30)) # Si todo es null, pon 30 + extra
            .clamp(0, 100)
            .rename("AQ_Composite_0_100")
        )

    def predict_residential_with_real_attributes(
        self,
        geojson_area: Dict[str, Any],
        densidad: Dict[str, Any],
        trafico: Dict[str, Any],
        albedo: Dict[str, Any],
        date_range_monthly: Tuple[str, str] = ("2025-05-01", "2025-05-31"),
    ):
        """Predicts impact on residencial zone"""
        ee_geom = self._geojson_to_ee_geom(geojson_area)
        month = self._month(date_range_monthly[0])
        ndvi_p = self._ndvi_percentiles_for_month(month)

        # Target NDVI: Percentil 50 ('residential')
        ndvi_adj_base = ndvi_p.select("NDVI_p50").rename("NDVI_target").clamp(0, 1)

        ndvi_adj, lst_extra, aq_extra = self._attr_modifiers_real(
            densidad, trafico, albedo
        )
        ndvi_target = ndvi_adj_base.add(ndvi_adj).clamp(0, 1)

        self._apply_simulation(ee_geom, ndvi_target, lst_extra, aq_extra)
        print("Prediction of residential zone with real values.")

    def predict_green_area_with_attributes(
        self,
        geojson_area: Dict[str, Any],
        arboles: Dict[str, Any],
        pasto: Dict[str, Any],
        agua: bool,
        copa: Dict[str, Any],
        date_range_monthly: Tuple[str, str] = ("2025-05-01", "2025-05-31"),
    ):
        """Predicts impact on green areas"""
        ee_geom = self._geojson_to_ee_geom(geojson_area)
        month = self._month(date_range_monthly[0])
        ndvi_p = self._ndvi_percentiles_for_month(month)

        # Target NDVI: Percentil 90 ('green_area')
        ndvi_adj_base = ndvi_p.select("NDVI_p90").rename("NDVI_target").clamp(0, 1)

        ndvi_adj, lst_extra, aq_extra = self._attr_modifiers_green(
            arboles, pasto, agua, copa
        )
        ndvi_target = ndvi_adj_base.add(ndvi_adj).clamp(0, 1)

        self._apply_simulation(ee_geom, ndvi_target, lst_extra, aq_extra)
        print("Green Area prediction calculated.")

    def _predict_changes_historic_percentiles(
        self,
        geojson_area: Dict[str, Any],
        preset: str,
        date_range_monthly: Tuple[str, str] = ("2025-05-01", "2025-05-31"),
    ):
        ee_geom = self._geojson_to_ee_geom(geojson_area)
        tgt = self._CFG["presets"].get(preset)
        if not tgt:
            print(f"Preset '{preset}' invalid.")
            return

        month = self._month(date_range_monthly[0])
        ndvi_p = self._ndvi_percentiles_for_month(month)

        ndvi_target_image = ndvi_p.select(tgt).clamp(0, 1).rename("NDVI_target")

        lst_extra = ee.Number(0)
        aq_extra = ee.Number(0)

        if preset == "industrial":
            lst_extra = ee.Number(self.temp_industry)
            aq_extra = ee.Number(self.aq_industry)
            print(
                f"Preset 'industrial' apply: ΔTemp={self.temp_industry}, ΔAQ={self.aq_industry}"
            )

        self._apply_simulation(ee_geom, ndvi_target_image, lst_extra, aq_extra)


    def impact_report(
        self,
        geojson_area: Dict[str, Any],
        preset: Union[str, Tuple[str, Dict[str, Any]]],
        buffer_m: Optional[int] = None,
        calibrate: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Calculates and reports the impact of the  simulation (baseline vs. post-simulación)
        in a geojson geometry
        """
        ee_geom = self._geojson_to_ee_geom(geojson_area)

        if calibrate:
            try:
                self.calibrate_precision()
            except Exception as e:
                print(f"Fine tunning fail, using simple model: {e}")

        area = ee_geom.buffer(buffer_m) if buffer_m else ee_geom
        if buffer_m:
            print(
                f"Extended analyze {buffer_m/1000:.1f} km arround painted area."
            )

        # --- 1. Calcular Baseline ---
        base_stats = {
            "temp_c_mean": self._mean(self.temp_image, 100, area),
            "ndvi_mean": self._mean(self.ndvi, 20, area),
            "aq_mean": self._mean(self.aq_index, 100, area),
        }
        print(f"   Temp Raw: {base_stats['temp_c_mean'].getInfo()}", flush=True)
        print(f"   NDVI Raw: {base_stats['ndvi_mean'].getInfo()}", flush=True)
        print(f"   AQ Raw:   {base_stats['aq_mean'].getInfo()}", flush=True)

        # Prediction time
        if (
            isinstance(preset, tuple)
            and len(preset) == 2
            and preset[0] == "residential_real"
        ):
            attrs = preset[1] or {}
            self.predict_residential_with_real_attributes(
                geojson_area=geojson_area,
                densidad=attrs["densidad"],
                trafico=attrs["trafico"],
                albedo=attrs["albedo"],
            )
        elif (
            isinstance(preset, tuple) and len(preset) == 2 and preset[0] == "green_real"
        ):
            attrs = preset[1] or {}
            self.predict_green_area_with_attributes(
                geojson_area=geojson_area,
                arboles=attrs["arboles"],
                pasto=attrs["pasto"],
                agua=attrs.get("agua", False),
                copa=attrs["copa"],
            )
        else:
            self._predict_changes_historic_percentiles(geojson_area, preset)

        # --- 3. Calculate post simulation ---
        if self.sim_temp is None or self.sim_ndvi is None or self.sim_aq is None:
            print("Error: Simulation didn't generate valid values")
            return None

        post_stats = {
            "temp_c_mean": self._mean(self.sim_temp, 1000, area),
            "ndvi_mean": self._mean(self.sim_ndvi, 20, area),
            "aq_mean": self._mean(self.sim_aq, 5000, area),
        }

        # --- 4. Getting results and reporting them back ---
        def _safe_fetch(m: ee.Dictionary, key: str) -> Optional[float]:
            try:
                val = m.getInfo()
                return val.get(key) if val else None
            except Exception:
                return None

        base_temp = _safe_fetch(base_stats["temp_c_mean"], "LST_Day_1km")
        base_ndvi = _safe_fetch(base_stats["ndvi_mean"], "NDVI")
        base_aq = _safe_fetch(base_stats["aq_mean"], "AQ_Composite_0_100")
        post_temp = _safe_fetch(post_stats["temp_c_mean"], "LST_Day_1km")
        post_ndvi = _safe_fetch(post_stats["ndvi_mean"], "NDVI")
        post_aq = _safe_fetch(post_stats["aq_mean"], "AQ_Composite_0_100")

        delta_temp = (
            post_temp - base_temp
            if (base_temp is not None and post_temp is not None)
            else None
        )
        delta_ndvi = (
            post_ndvi - base_ndvi
            if (base_ndvi is not None and post_ndvi is not None)
            else None
        )
        delta_aq = (
            post_aq - base_aq if (base_aq is not None and post_aq is not None) else None
        )

        report = {
            "preset": preset if isinstance(preset, str) else preset[0],
            "baseline": {
                "temp_c_mean": base_temp,
                "ndvi_mean": base_ndvi,
                "aq_mean_0_100": base_aq,
            },
            "post": {
                "temp_c_mean": post_temp,
                "ndvi_mean": post_ndvi,
                "aq_mean_0_100": post_aq,
            },
            "delta": {
                "temp_c_mean": delta_temp,
                "ndvi_mean": delta_ndvi,
                "aq_mean_0_100": delta_aq,
            },
        }

        if all(
            v is not None
            for v in [base_temp, post_temp, base_ndvi, post_ndvi, base_aq, post_aq]
        ):
            print("=== Reporte de Impacto ===")
            print(f"Preset: {report['preset']}")
            print(f"Temp (°C): {base_temp:.2f} -> {post_temp:.2f} | Δ={delta_temp:.2f}")
            print(f"NDVI:      {base_ndvi:.3f} -> {post_ndvi:.3f} | Δ={delta_ndvi:.3f}")
            print(f"AQ (0–100):{base_aq:.1f}  -> {post_aq:.1f}  | Δ={delta_aq:.1f}")

        print(f"   Base Temp: {base_temp}", flush=True)
        print(f"   Post Temp: {post_temp}", flush=True)
        print(f"   Base AQ:   {base_aq}", flush=True)
        print(f"   Post AQ:   {post_aq}", flush=True)
        return report
