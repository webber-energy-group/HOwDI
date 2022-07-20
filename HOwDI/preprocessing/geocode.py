import pandas as pd
import geopandas as gpd
import geopy  # necessary installation, unnecessary import


def main(file):
    """Generates a GeoJSON file from geocoded locations of hub (detailed hubs.csv)"""
    hubs = pd.read_csv(file)["hub"].tolist()
    geohubs = gpd.tools.geocode(
        [hub + " Texas" for hub in hubs], provider="arcgis"
    ).set_index(pd.Series(hubs, name="hub"))
    geohubs.to_file("hubs.geojson", driver="GeoJSON")


if __name__ == "__main__":
    main("hubs.csv")
