import pandas as pd
import yaml

# %%
# capex and ng
capex = pd.read_excel(
    "regional_CAPEX_multipliers.xlsx",
    usecols=["County", "CAP_COST_MULT"],
    index_col="County",
)
ng = pd.read_excel(
    "regional_NG_cost_with_multipliers.xlsx",
    usecols=["County", "gas_price ($/MMBtu)"],
    index_col="County",
)

# %%
# elec_prices

elec_prices_by_month = pd.read_excel(
    "ERCOT_elec_prices_by_HUB.xlsx", sheet_name=list(range(1, 13))
)  # $/MW-hr

elec_prices_df = pd.concat(elec_prices_by_month.values())
# get rid of feb 13-20
elec_prices_df_no_feb = elec_prices_df[
    ~(
        elec_prices_df["Delivery Date"].isin(
            ["02/{:02d}/2021".format(x) for x in range(13, 21)]
        )
    )
]


prices_by_hub = (
    elec_prices_df_no_feb[["Settlement Point Name", "Settlement Point Price"]]
    .groupby("Settlement Point Name")
    .mean()
)

prices_by_hub = prices_by_hub * 1.20 / 1000

# elec_point_price_avg = float(prices_by_hub.loc["HB_HUBAVG"])

# elec_pm = prices_by_hub / elec_point_price_avg
# elec_prices = elec_pm * 0.075

with open("ERCOT_lz_county_map.yml") as f:
    ercot_lz_county_map_file = yaml.load(f, Loader=yaml.FullLoader)

lz_county_map = ercot_lz_county_map_file["Load-zone_county_map"]
lz_map = ercot_lz_county_map_file["Load-zone_name"]

final_elec_prices_by_hub = {
    v + " County": float(prices_by_hub.loc[lz_map[k]])
    for k in lz_county_map
    for v in lz_county_map[k]
}

final_elec_prices_by_hub_df = pd.DataFrame(
    pd.Series(final_elec_prices_by_hub), columns=["e_price"]
)
final_elec_prices_by_hub_df.index.name = "County"
# %%
final = pd.concat([ng, capex, final_elec_prices_by_hub_df], axis=1)
final["ng_usd_per_mmbtu"] = final["gas_price ($/MMBtu)"]  # .fillna(4.25)
final["e_usd_per_kwh"] = final["e_price"]  # .fillna(0.075)
final["capital_pm"] = final["CAP_COST_MULT"]  # .fillna(1)
final = final.drop(["gas_price ($/MMBtu)", "e_price", "CAP_COST_MULT"], axis=1)

# # add defaults as a "default" row
# defaults = {
#     "County": "default",
#     "ng_usd_per_mmbtu": 5,
#     "e_usd_per_kwh": 0.075,
#     "capital_pm": 1,
# }
# final = final.append(defaults)

final.to_csv("../texas_pm.csv")
# %%
