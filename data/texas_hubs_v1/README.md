## hubs.csv

File describes hubs

- build_smr
    - Binary 
- build_electrolyzer
    - Binary
- transportationFuel_tonnesperday
- industrialFuel_tonnesperday
- existing_tonnesperday
- major
    - Binary
    - True: Hub can make large connections
- minor
    - Binary
    - True: hub can make small connections

## existing_arcs.csv

Describes predefined arcs that are appended to output

## geocode.py

Generates `hubs.geojson`, which is a GeoJSON containing the locations of each hub