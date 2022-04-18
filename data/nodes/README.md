## nodes.csv

File describes nodes

- build_smr
    - Binary 
- build_electrolyzer
    - Binary
- transportationFuel_tonnesperday
- industrialFuel_tonnesperday
- existing_tonnesperday
- major
    - Binary
    - True: Node can make large connections
- minor
    - Binary
    - True: Node can make small connections

## existing_arcs.csv

Describes predefined arcs that are appended to output

## geocode.py

Generates `nodes.geojson`, which is a GeoJSON containing the locations of each node