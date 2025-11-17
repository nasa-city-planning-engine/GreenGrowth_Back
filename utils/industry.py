#The following code was commented, but this ilustrates how industry_model.pkl was generated

"""
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, KFold, RandomizedSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.pipeline import Pipeline
from dotenv import load_dotenv
import os
import ee
load_dotenv()


pd.set_option("display.max_columns", None)
pd.set_option("display.width", 1000)

data = "data/ghgp_data_2023.xlsx"

try:
    data_sheets = pd.ExcelFile(data).sheet_names
    print("Data_sheets found:", data_sheets)
except Exception as e:
    print(f"Error reading data: {e}")

try:
    sheet = data_sheets[0] if data_sheets else None

    df_ghg = pd.read_excel(data, sheet_name=sheet, header=3)
    print(df_ghg.info())

except Exception as e:
    print(f"\nError al cargar la hoja: {e}")


df_ghg.columns = df_ghg.columns.str.strip()
data_selected = [
    "Latitude",
    "Longitude",
    "Industry Type (subparts)",
    "Industry Type (sectors)",
    "Stationary Combustion",
    "Total reported direct emissions",
    "Methane (CH4) emissions",
    "CO2 emissions (non-biogenic)",
    "Nitrous Oxide (N2O) emissions",
]
df = df_ghg[data_selected]
df = df.dropna()

features = []
for index, row in df.iterrows():
    geometry = ee.Geometry.Point(row["Longitude"], row["Latitude"])
    properties = row.to_dict()
    feature = ee.Feature(geometry, properties)
    features.append(feature)

facility_collection = ee.FeatureCollection(features)

print(f"FeatureCollection created with {facility_collection.size().getInfo()}")

data = {
    "Industry Type (subparts)": [
        "C",
        "C,D",
        "C,I",
        "C",
        "HH",
        "C,HH",
        "C",
        "C",
        "HH",
        "C",
        "C,D",
        "C",
        "C,D",
        "C",
        "C",
        "HH",
        "C,D",
        "C,D",
        "C",
    ]
}


industry_subpart_decoder = {
    # Direct Emitters
    "C": "Stationary Combustion",
    "D": "Electricity Generation",
    "E": "Adipic Acid Production",
    "F": "Aluminum Production",
    "G": "Ammonia Manufacturing",
    "H": "Cement Production",
    "I": "Electronics Manufacture",
    "K": "Ferroalloy Production",
    "L": "Fluorinated GHG Production",
    "N": "Glass Production",
    "O": "HCFC-22 Production and HFC-23 Destruction",
    "P": "Hydrogen Production",
    "Q": "Iron and Steel Production",
    "R": "Lead Production",
    "S": "Lime Production",
    "T": "Magnesium Production",
    "U": "Miscellaneous Use of Carbonates",
    "V": "Nitric Acid Production",
    "X": "Petrochemical Production",
    "Y": "Petroleum Refining",
    "Z": "Phosphoric Acid Production",
    "AA": "Pulp and Paper Manufacturing",
    "BB": "Silicon Carbide Production",
    "CC": "Soda Ash Manufacturing",
    "DD": "SF6 from Electrical Equipment",
    "EE": "Titanium Dioxide Production",
    "FF": "Underground Coal Mines",
    "GG": "Zinc Production",
    "HH": "Municipal Landfills",
    "II": "Industrial Wastewater Treatment",
    "TT": "Industrial Waste Landfills",
    # Oil & Gas (W-Subparts)
    "W-OFFSH": "Offshore Production",
    "W-ONSH": "Onshore Production",
    "W-GB": "Gathering and Boosting",
    "W-PROC": "Natural Gas Processing",
    "W-NGTC": "Natural Gas Transmission/Compression",
    "W-TRANS": "Transmission Pipelines",
    "W-UNSTG": "Underground Natural Gas Storage",
    "W-LNGSTG": "Liquified Natural Gas Storage",
    "W-LNGIE": "Liquified Natural Gas Import/Export Equipment",
    "W-LDC": "Natural Gas Local Distribution Company",
    # Suppliers
    "LL": "Suppliers of Coal Based Liquids Fuels",
    "MM": "Suppliers of Petroleum Products",
    "MM-REF": "Petroleum Refinery (Producer)",
    "MM-IMP": "Petroleum Product Importer",
    "MM-EXP": "Petroleum Product Exporter",
    "NN": "Natural Gas and Natural Gas Liquid Supply",
    "NN-FRAC": "Natural Gas Liquids Fractionator",
    "NN-LDC": "Natural Gas Local Distribution Company (supply)",
    "OO": "Non-CO2 Industrial Gas Supply",
    "PP": "Carbon Dioxide (CO2) Supply",
    "QQ": "Import and Export of Equipment Containing Fluorinated GHGs",
    # CO2 Injection
    "RR": "Geologic Sequestration of Carbon Dioxide",
    "UU": "Injection of Carbon Dioxide",
    # Other
    "SS": "Electric Transmission and Distribution Equipment",
}

""""""
heat_potential_index = {
    "H": "High Heat",
    "Q": "High Heat",
    "Y": "High Heat",
    "D": "High Heat",
    "C": "High Heat",
    "F": "High Heat",
    "S": "High Heat",
    "AA": "High Heat",
    "EE": "High Heat",
    "T": "High Heat",
    "K": "High Heat",
    "N": "High Heat",
    "BB": "High Heat",
    "X": "Mid Heat",
    "G": "Mid Heat",
    "P": "Mid Heat",
    "V": "Mid Heat",
    "E": "Mid Heat",
    "Z": "Mid Heat",
    "O": "Mid Heat",
    "II": "Mid Heat",
    "HH": "Mid Heat",
    "I": "Low Heat",
    "GG": "Low Heat",
    "U": "Low Heat",
}


def get_heat_flags(subparts):
    codes = subparts.split(",")
    heats = {
        heat_potential_index.get(code) for code in codes if code in heat_potential_index
    }

    return {
        "High Heat": "High Heat" in heats,
        "Mid Heat": "Mid Heat" in heats,
        "Low Heat": "Low Heat" in heats,
    }


heat_flags = df["Industry Type (subparts)"].apply(get_heat_flags)
heat_flags_df = pd.DataFrame(list(heat_flags))

df = pd.concat([df, heat_flags_df], axis=1)

industry_subpart_decoder = {
    # Direct Emitters
    "C": "Stationary Combustion",
    "D": "Electricity Generation",
    "E": "Adipic Acid Production",
    "F": "Aluminum Production",
    "G": "Ammonia Manufacturing",
    "H": "Cement Production",
    "I": "Electronics Manufacture",
    "K": "Ferroalloy Production",
    "L": "Fluorinated GHG Production",
    "N": "Glass Production",
    "O": "HCFC-22 Production and HFC-23 Destruction",
    "P": "Hydrogen Production",
    "Q": "Iron and Steel Production",
    "R": "Lead Production",
    "S": "Lime Production",
    "T": "Magnesium Production",
    "U": "Miscellaneous Use of Carbonates",
    "V": "Nitric Acid Production",
    "X": "Petrochemical Production",
    "Y": "Petroleum Refining",
    "Z": "Phosphoric Acid Production",
    "AA": "Pulp and Paper Manufacturing",
    "BB": "Silicon Carbide Production",
    "CC": "Soda Ash Manufacturing",
    "DD": "SF6 from Electrical Equipment",
    "EE": "Titanium Dioxide Production",
    "FF": "Underground Coal Mines",
    "GG": "Zinc Production",
    "HH": "Municipal Landfills",
    "II": "Industrial Wastewater Treatment",
    "TT": "Industrial Waste Landfills",
    # Oil & Gas (W-Subparts)
    "W-OFFSH": "Offshore Production",
    "W-ONSH": "Onshore Production",
    "W-GB": "Gathering and Boosting",
    "W-PROC": "Natural Gas Processing",
    "W-NGTC": "Natural Gas Transmission/Compression",
    "W-TRANS": "Transmission Pipelines",
    "W-UNSTG": "Underground Natural Gas Storage",
    "W-LNGSTG": "Liquified Natural Gas Storage",
    "W-LNGIE": "Liquified Natural Gas Import/Export Equipment",
    "W-LDC": "Natural Gas Local Distribution Company",
    # Suppliers
    "LL": "Suppliers of Coal Based Liquids Fuels",
    "MM": "Suppliers of Petroleum Products",
    "MM-REF": "Petroleum Refinery (Producer)",
    "MM-IMP": "Petroleum Product Importer",
    "MM-EXP": "Petroleum Product Exporter",
    "NN": "Natural Gas and Natural Gas Liquid Supply",
    "NN-FRAC": "Natural Gas Liquids Fractionator",
    "NN-LDC": "Natural Gas Local Distribution Company (supply)",
    "OO": "Non-CO2 Industrial Gas Supply",
    "PP": "Carbon Dioxide (CO2) Supply",
    "QQ": "Import and Export of Equipment Containing Fluorinated GHGs",
    # CO2 Injection
    "RR": "Geologic Sequestration of Carbon Dioxide",
    "UU": "Injection of Carbon Dioxide",
    # Other
    "SS": "Electric Transmission and Distribution Equipment",
}


one_hot_encoded = df["Industry Type (subparts)"].str.get_dummies(sep=",")
one_hot_encoded.columns = one_hot_encoded.columns.map(industry_subpart_decoder)
df = pd.concat([df, one_hot_encoded], axis=1)

data_2 = "data/ghg_data_with_lst.csv"

try:
    df_2 = pd.read_csv(data_2)
    print(df_2.info())
except Exception as e:
    print(f"\nError al cargar el CSV: {e}")

data_wind = "data/export_facility_wind_data.csv"

try:
    df_3 = pd.read_csv(data_wind)
    print(df_3.info())
except Exception as e:
    print(f"\nError al cargar el CSV: {e}")

df.reset_index(drop=True, inplace=True)
df_2.reset_index(drop=True, inplace=True)
df_3.reset_index(drop=True, inplace=True)
df_ = pd.concat([df, df_2], axis=1)
df_complete = pd.concat([df_, df_3], axis=1)
df_complete.reset_index(drop=True, inplace=True)
df_complete = df_complete.loc[:, ~df_complete.columns.duplicated()].copy()

gwp_ch4 = 25
gwp_n2o = 298

df_complete["Pollution_Index_CO2e"] = (
    df_complete["CO2 emissions (non-biogenic)"] * 1
    + df_complete["Methane (CH4) emissions"] * gwp_ch4
    + df_complete["Nitrous Oxide (N2O) emissions"] * gwp_n2o
)
df_complete["Heat difference in 5km"] = (
    (
        df_complete["LST_2020_1km"]
        + df_complete["LST_2021_1km"]
        + df_complete["LST_2022_1km"]
        + df_complete["LST_2023_1km"]
        + df_complete["LST_2024_1km"]
    )
    / 5
) - (
    (
        df_complete["LST_2020_5km"]
        + df_complete["LST_2021_5km"]
        + df_complete["LST_2022_5km"]
        + df_complete["LST_2023_5km"]
        + df_complete["LST_2024_5km"]
    )
    / 5
)
df_complete["Heat difference in 10km"] = (
    (
        df_complete["LST_2020_1km"]
        + df_complete["LST_2021_1km"]
        + df_complete["LST_2022_1km"]
        + df_complete["LST_2023_1km"]
        + df_complete["LST_2024_1km"]
    )
    / 5
) - (
    (
        df_complete["LST_2020_10km"]
        + df_complete["LST_2021_10km"]
        + df_complete["LST_2022_10km"]
        + df_complete["LST_2023_10km"]
        + df_complete["LST_2024_10km"]
    )
    / 5
)
df_complete["Heat average in 1k"] = (
    df_complete["LST_2020_1km"]
    + df_complete["LST_2021_1km"]
    + df_complete["LST_2022_1km"]
    + df_complete["LST_2023_1km"]
    + df_complete["LST_2024_1km"]
) / 5

df_complete["u Component of wind 1km"] = df_complete[
    [
        "u_component_of_wind_10m_2020_1km",
        "u_component_of_wind_10m_2021_1km",
        "u_component_of_wind_10m_2022_1km",
        "u_component_of_wind_10m_2023_1km",
        "u_component_of_wind_10m_2024_1km",
    ]
].mean(axis=1)

df_complete["u Component of wind 5km"] = df_complete[
    [
        "u_component_of_wind_10m_2020_5km",
        "u_component_of_wind_10m_2021_5km",
        "u_component_of_wind_10m_2022_5km",
        "u_component_of_wind_10m_2023_5km",
        "u_component_of_wind_10m_2024_5km",
    ]
].mean(axis=1)

df_complete["u Component of wind 10km"] = df_complete[
    [
        "u_component_of_wind_10m_2020_10km",
        "u_component_of_wind_10m_2021_10km",
        "u_component_of_wind_10m_2022_10km",
        "u_component_of_wind_10m_2023_10km",
        "u_component_of_wind_10m_2024_10km",
    ]
].mean(axis=1)


# --- V component ---
df_complete["v Component of wind 1km"] = df_complete[
    [
        "v_component_of_wind_10m_2020_1km",
        "v_component_of_wind_10m_2021_1km",
        "v_component_of_wind_10m_2022_1km",
        "v_component_of_wind_10m_2023_1km",
        "v_component_of_wind_10m_2024_1km",
    ]
].mean(axis=1)

df_complete["v Component of wind 5km"] = df_complete[
    [
        "v_component_of_wind_10m_2020_5km",
        "v_component_of_wind_10m_2021_5km",
        "v_component_of_wind_10m_2022_5km",
        "v_component_of_wind_10m_2023_5km",
        "v_component_of_wind_10m_2024_5km",
    ]
].mean(axis=1)

df_complete["v Component of wind 10km"] = df_complete[
    [
        "v_component_of_wind_10m_2020_10km",
        "v_component_of_wind_10m_2021_10km",
        "v_component_of_wind_10m_2022_10km",
        "v_component_of_wind_10m_2023_10km",
        "v_component_of_wind_10m_2024_10km",
    ]
].mean(axis=1)
# Wind speed (magnitude) for each altitude
df_complete["Wind Speed 1km"] = np.sqrt(
    df_complete["u Component of wind 1km"] ** 2
    + df_complete["v Component of wind 1km"] ** 2
)

df_complete["Wind Speed 5km"] = np.sqrt(
    df_complete["u Component of wind 5km"] ** 2
    + df_complete["v Component of wind 5km"] ** 2
)

df_complete["Wind Speed 10km"] = np.sqrt(
    df_complete["u Component of wind 10km"] ** 2
    + df_complete["v Component of wind 10km"] ** 2
)

df_complete = df_complete.dropna()
x = df_complete[
    [
        "Latitude",
        "Longitude",
        "Total reported direct emissions",
        "Stationary Combustion",
        "Electricity Generation",
        "Adipic Acid Production",
        "Aluminum Production",
        "Ammonia Manufacturing",
        "Cement Production",
        "Electronics Manufacture",
        "Ferroalloy Production",
        "Fluorinated GHG Production",
        "Glass Production",
        "HCFC-22 Production and HFC-23 Destruction",
        "Hydrogen Production",
        "Iron and Steel Production",
        "Lead Production",
        "Lime Production",
        "Magnesium Production",
        "Miscellaneous Use of Carbonates",
        "Nitric Acid Production",
        "Petrochemical Production",
        "Petroleum Refining",
        "Phosphoric Acid Production",
        "Pulp and Paper Manufacturing",
        "Silicon Carbide Production",
        "Soda Ash Manufacturing",
        "SF6 from Electrical Equipment",
        "Titanium Dioxide Production",
        "Underground Coal Mines",
        "Zinc Production",
        "Municipal Landfills",
        "Industrial Wastewater Treatment",
        "Industrial Waste Landfills",
        "Offshore Production",
        "Natural Gas Processing",
        "Natural Gas Transmission/Compression",
        "Underground Natural Gas Storage",
        "Liquified Natural Gas Storage",
        "Liquified Natural Gas Import/Export Equipment",
        "Petroleum Refinery (Producer)",
        "Petroleum Product Importer",
        "Petroleum Product Exporter",
        "Natural Gas Liquids Fractionator",
        "Natural Gas Local Distribution Company (supply)",
        "Non-CO2 Industrial Gas Supply",
        "Carbon Dioxide (CO2) Supply",
        "Import and Export of Equipment Containing Fluorinated GHGs",
        # CO2 Injection
        "Injection of Carbon Dioxide",
        # Other
        "Electric Transmission and Distribution Equipment",
        "Wind Speed 1km",
        "Wind Speed 5km",
        "Wind Speed 10km",
    ]
].values

y = df_complete["Heat average in 1k"].values


x_train, x_test, y_train, y_test = train_test_split(
    x, y, test_size=0.2, random_state=42
)
pipeline = Pipeline(
    [
        ("scaler", StandardScaler()),
        ("model", GradientBoostingRegressor(random_state=42)),
    ]
)

param_distributions = {
     "model__n_estimators": [100, 200, 300, 500],
     "model__learning_rate": [0.01, 0.05, 0.1, 0.2],
     "model__max_depth": [3, 5, 7],
     "model__subsample": [0.7, 0.8, 0.9, 1.0],
 }


cv_strategy = KFold(n_splits=5, shuffle=True, random_state=42)

# Set up RandomizedSearchCV
# This test different combinations of the parameters using cross-validation.
random_search = RandomizedSearchCV(
    estimator=pipeline,
    param_distributions=param_distributions,
    n_iter=50,  # Number of parameter settings that are sampled.
    cv=cv_strategy,
    scoring="r2",  # The metric to evaluate the models on.
    n_jobs=-1,  # Use all available CPU cores.
    random_state=42,
    verbose=1,  # Prints updates so you can see the progress.
)


print("Starting hyperparameter tuning...")
random_search.fit(x_train, y_train)

print("\n--- Tuning Complete ---")
print(f"Best R² score found during search: {random_search.best_score_:.4f}")
print("Best parameters found:")
print(random_search.best_params_)

best_model = random_search.best_estimator_
final_score = best_model.score(x_test, y_test)
print(f"\nFinal R² score on the unseen test set: {final_score:.4f}")
"""
