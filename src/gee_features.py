"""Satellite features from Google Earth Engine.

Feature design follows the two established operational approaches:

  * NASA LHASA (Landslide Hazard Assessment for Situational Awareness) v1/v2 --
    a static susceptibility layer (slope, terrain, road networks, vegetation)
    modulated by dynamic triggers (current rainfall, antecedent rainfall,
    soil moisture), fed to a gradient-boosted classifier.
  * USGS shallow-landslide modelling -- infinite-slope stability driven by
    rainfall infiltration and pore-pressure rise.

Terrain is sampled over a neighbourhood, not just the exact point. Reported
landslide coordinates usually mark where debris came to rest (a road, a house,
a valley floor) rather than where the slope actually failed, so a point sample
frequently lands on flat ground below the real source area.

Two entry points:

  get_features(...)        one point; used by the live CLI and API
  get_features_batch(...)  many points in one server-side pass

The batch path exists because the per-point path needs four round trips to
Earth Engine and takes ~45 s per point, which is ~12 hours for the training
set. Batching pushes the whole loop server-side and cuts that to minutes.
"""

import ee

_initialized = False

NEIGHBOURHOOD_M = 300  # radius for terrain statistics around a point
RAIN_WINDOWS = (1, 3, 7, 15, 30)
MISSING = -9999  # server-side sentinel; converted back to None in Python

POINT_SCALE = 100
TERRAIN_SCALE = 30  # SRTM native


def init(project):
    global _initialized
    if not _initialized:
        ee.Initialize(project=project)
        _initialized = True


def _collections():
    return {
        "terrain": ee.Terrain.products(ee.Image("USGS/SRTMGL1_003")),
        "gpm": ee.ImageCollection("NASA/GPM_L3/IMERG_V07").select("precipitation"),
        "modis": ee.ImageCollection("MODIS/061/MOD13Q1").select("NDVI"),
        "s1": (
            ee.ImageCollection("COPERNICUS/S1_GRD")
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
            .select("VV")
        ),
        "smap": ee.ImageCollection("NASA/SMAP/SPL4SMGP/008").select(
            ["sm_surface", "sm_rootzone"]
        ),
    }


def _or_missing(collection, reducer, band_names):
    """Reduces a collection to an image, substituting a sentinel when empty.

    Sentinel-1 starts in late 2014 and SMAP in April 2015, so for earlier
    dates these collections are genuinely empty. Reducing an empty collection
    yields a band-less image, and selecting a band from it raises server-side,
    which would abort the entire batch. Swapping in a constant keeps the rest
    of the features for that row intact.
    """
    reduced = collection.reduce(reducer)
    fallback = ee.Image.constant([MISSING] * len(band_names)).rename(band_names)
    return ee.Image(
        ee.Algorithms.If(collection.size().gt(0), reduced.rename(band_names), fallback)
    )


def _feature_image(date, col, geom):
    """Builds the date-dependent bands for one point/date."""
    bands = []

    for days in RAIN_WINDOWS:
        window = col["gpm"].filterDate(date.advance(-days, "day"), date)
        # IMERG is mm/hr on 30-minute snapshots, so each image contributes v*0.5.
        # Scale each image BEFORE reducing, never the reduced result: scaling
        # afterwards also scales the MISSING sentinel, turning -9999 into
        # -4999.5, which then slips past the `<= MISSING + 1` test in _clean()
        # and reaches the model as thousands of millimetres of negative rain.
        half = window.map(lambda img: img.multiply(0.5))
        rain = _or_missing(half, ee.Reducer.sum(), ["r"])
        bands.append(rain.rename(f"rain_{days}d"))

    ndvi = _or_missing(
        col["modis"].filterDate(date.advance(-40, "day"), date),
        ee.Reducer.mean(),
        ["ndvi"],
    )
    bands.append(ndvi)

    # Spatially filtered so the emptiness check reflects coverage at *this*
    # point, not anywhere on Earth in the window.
    s1_here = col["s1"].filterBounds(geom)
    recent = s1_here.filterDate(date.advance(-12, "day"), date)
    baseline = s1_here.filterDate(date.advance(-365, "day"), date.advance(-30, "day"))
    vv = ee.Image(
        ee.Algorithms.If(
            recent.size().gt(0).And(baseline.size().gt(0)),
            recent.mean().subtract(baseline.mean()).rename("vv_anomaly"),
            ee.Image.constant(MISSING).rename("vv_anomaly"),
        )
    )
    bands.append(vv)

    soil = _or_missing(
        col["smap"].filterDate(date.advance(-3, "day"), date.advance(1, "day")),
        ee.Reducer.mean(),
        ["soil_moisture_surface", "soil_moisture_subsurface"],
    )
    bands.append(soil)

    return ee.Image.cat(bands)


def _clean(value):
    if value is None:
        return None
    if isinstance(value, (int, float)) and value <= MISSING + 1:
        return None
    return value


def get_features_batch(points, project, chunk_size=30):
    """points: iterable of dicts with 'lat', 'lon', 'date' (YYYY-MM-DD), 'id'.

    Returns {id: {feature: value}}. Runs the whole per-point computation
    server-side, so cost is roughly one round trip per chunk rather than four
    per point.
    """
    init(project)
    col = _collections()
    terrain = col["terrain"]
    terrain_pt = terrain.select(["elevation", "slope", "aspect"])
    terrain_nb = terrain.select(["slope", "elevation"])

    nbhd_reducer = ee.Reducer.max().combine(
        ee.Reducer.min(), sharedInputs=True
    ).combine(ee.Reducer.mean(), sharedInputs=True)

    def per_feature(feat):
        geom = feat.geometry()
        nbhd = geom.buffer(NEIGHBOURHOOD_M)
        date = ee.Date(feat.get("d"))

        at_point = terrain_pt.addBands(_feature_image(date, col, geom)).reduceRegion(
            reducer=ee.Reducer.mean(), geometry=geom, scale=POINT_SCALE, maxPixels=1e9
        )
        around = terrain_nb.reduceRegion(
            reducer=nbhd_reducer, geometry=nbhd, scale=TERRAIN_SCALE, maxPixels=1e9
        )
        return ee.Feature(None, at_point.combine(around).set("pid", feat.get("pid")))

    points = list(points)
    out = {}
    for start in range(0, len(points), chunk_size):
        chunk = points[start : start + chunk_size]
        fc = ee.FeatureCollection(
            [
                ee.Feature(
                    ee.Geometry.Point([float(p["lon"]), float(p["lat"])]),
                    {"pid": str(p["id"]), "d": str(p["date"])},
                )
                for p in chunk
            ]
        )
        rows = fc.map(per_feature).getInfo()["features"]

        for row in rows:
            props = row["properties"]
            pid = props.get("pid")
            elev_max, elev_min = props.get("elevation_max"), props.get("elevation_min")
            feats = {
                "elevation": _clean(props.get("elevation")),
                "slope": _clean(props.get("slope")),
                "aspect": _clean(props.get("aspect")),
                "slope_max_nbhd": _clean(props.get("slope_max")),
                "slope_mean_nbhd": _clean(props.get("slope_mean")),
                "relief_nbhd": (
                    elev_max - elev_min
                    if elev_max is not None and elev_min is not None
                    else None
                ),
                "ndvi": _clean(props.get("ndvi")),
                "vv_anomaly": _clean(props.get("vv_anomaly")),
                "soil_moisture_surface": _clean(props.get("soil_moisture_surface")),
                "soil_moisture_subsurface": _clean(props.get("soil_moisture_subsurface")),
            }
            for days in RAIN_WINDOWS:
                feats[f"rain_{days}d"] = _clean(props.get(f"rain_{days}d"))
            out[pid] = feats

        yield_progress = start + len(chunk)
        print(f"  fetched {yield_progress}/{len(points)}", flush=True)

    return out


def get_features(lat, lon, date_str, project):
    """Single-point convenience wrapper, used by the CLI and the live API."""
    batch = get_features_batch(
        [{"id": "_", "lat": lat, "lon": lon, "date": date_str}], project, chunk_size=1
    )
    return batch["_"]
