import pandas as pd
import geopandas as gpd
from geopy.geocoders import Nominatim  # necessary installation, unnecessary import


def camel_case_split(str):
    # adapted from https://www.geeksforgeeks.org/python-split-camelcase-string-to-individual-strings/
    words = [[str[0]]]

    for c in str[1:]:
        if words[-1][-1].islower() and c.isupper():
            words.append(list(c))
        else:
            words[-1].append(c)

    words = ["".join(word) for word in words]
    words[0] = words[0].capitalize()
    return " ".join(words)


def geocode_hubs(file="hubs.csv"):
    """Generates a GeoJSON file from geocoded locations of hub (detailed hubs.csv)"""

    hubs = pd.read_csv(file)["hub"].tolist()
    hubs_cc = [camel_case_split(hub) + ", Texas" for hub in hubs]

    geohubs = gpd.tools.geocode(
        hubs_cc, provider="nominatim", user_agent="HOwDI"
    ).set_index(pd.Series(hubs, name="hub"))

    geohubs["County"] = [
        word.lstrip()
        for words in geohubs["address"].str.split(",")
        for word in words
        if ("County") in word
    ]

    return geohubs


def main():
    geohubs = geocode_hubs()
    geohubs.to_file("hubs.geojson", driver="GeoJSON")


if __name__ == "__main__":
    main()
