import pandas as pd
import geopandas as gpd
import geopy  # necessary installation, unnecessary import


def geocode_hubs(file="hubs.csv"):
    """Generates a GeoJSON file from geocoded locations of hub (detailed hubs.csv)"""
    hubs = pd.read_csv(file)["hub"].tolist()
    geohubs = gpd.tools.geocode(
        [hub + " Texas" for hub in hubs], provider="arcgis"
    ).set_index(pd.Series(hubs, name="hub"))

    return geohubs

def main():
    geohubs = geocode_hubs()
    geohubs.to_file("hubs.geojson", driver="GeoJSON")

if __name__ == "__main__":
    main()
