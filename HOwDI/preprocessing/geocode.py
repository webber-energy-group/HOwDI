import pandas as pd
import geopandas as gpd
from geopy.geocoders import Nominatim  # necessary installation, unnecessary import


def camel_case_split(str):
    """
    Splits a camelCase string into individual words. Capitalizes the first word.

    Parameters:
    -----------
    str : str
        The camelCase string to split.

    Returns:
    --------
    str
        The input string with spaces inserted between each word.

    Example:
    --------
    >>> camel_case_split("helloWorld")
    'Hello World'

    >>> camel_case_split("texasCity")
    'Texas City'
    """
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
    """Geocodes hubs using Nominatim. Searches for "{hub}, Texas" and returns the first result,
    where {hub} is the hub name specified in the "hub" column of the hubs.csv file.

    Parameters
    ----------
    file: str
        Location of hubs.csv file. Defaults to "hubs.csv"

    Returns
    -------
    geohubs: GeoDataFrame
        GeoDataFrame of hubs with the following columns:
            hub: str
                The name of the hub as specified1
            geometry: shapely.geometry.point.Point
                The longitude (x) and latitude (y) found from geocoding the hub
            address: str
                The address of the hub as found from geocoding
            County: str
                The county of the hub as found from geocoding
    """
    # read hub names
    hubs = pd.read_csv(file)["hub"].tolist()

    # changes camelCase hub names to "Camel Case"
    # >>> texasCity -> Texas City
    # adds ", Texas" to the end of each hub name
    hubs_cc = [camel_case_split(hub) + ", Texas" for hub in hubs]

    # geocodes, takes a while
    geohubs = gpd.tools.geocode(
        hubs_cc, provider="nominatim", user_agent="HOwDI"
    ).set_index(pd.Series(hubs, name="hub"))

    # get county name from address,
    # based on if an address component (section split by comma)
    # contains the word "County"
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
