GEE_PROJECT = "project-77313e00-dc69-4c84-9cd"

FEATURE_COLUMNS = [
    # Static susceptibility (LHASA-style)
    "elevation",
    "slope",
    "aspect",
    "slope_max_nbhd",
    "slope_mean_nbhd",
    "relief_nbhd",
    "dist_to_road_m",
    "ndvi",
    # Dynamic trigger
    "rain_1d",
    "rain_3d",
    "rain_7d",
    "rain_15d",
    "rain_30d",
    "soil_moisture_surface",
    "soil_moisture_subsurface",
    "vv_anomaly",
    # Physics-based (USGS infinite-slope)
    "factor_of_safety",
]

POSITIVES_CSV = "data/raw/combined_ner_landslides.csv"
TRAINING_CSV = "data/processed/training_data.csv"
MODEL_PATH = "data/processed/model.pkl"

# Negative (non-landslide) samples generated per real landslide event
NEGATIVES_PER_POSITIVE = 2

# Radius in degrees around EACH real event within which its negative
# (non-landslide) samples are drawn (~0.15 deg =~ 16 km). Keeping negatives
# close to real events (rather than anywhere in NER) keeps the classification
# task meaningful: "risky day/spot vs safe day/spot in landslide-prone
# terrain", not just "hills vs flat valley".
NEGATIVE_RADIUS_DEG = 0.15

# Days to exclude around each known event date when picking negative dates,
# so we don't accidentally label a real high-risk day as "safe"
EXCLUDE_WINDOW_DAYS = 5
