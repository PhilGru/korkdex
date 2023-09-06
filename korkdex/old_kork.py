import collections
import json
import pathlib
import time
import unicodedata

import pandas as pd
import requests
from tqdm import tqdm

COLLECTION_PATH = pathlib.Path(__file__).parents[1] / "dex-collection.csv"
PKMN_INFO_PATH = pathlib.Path(__file__).parents[1] / "pkmn-info.json"
POKEAPI_PATH = "https://pokeapi.co/api/v2/pokemon-species/"


kork_sets = {
    "sv1": "Scarlet & Violet"
}

old_sets = []
new_sets = ["sv1"]

pkmn_in_gen = {
    1: (1, 151),
    2: (152, 251),
    3: (252, 386),
    4: (387, 494), 
    5: (495, 649),
    6: (650, 721),
    7: (722, 809),
    8: (810, 905),
    9: (906, 2000),
}

def load_pkmn_info():
    with open(PKMN_INFO_PATH, "r") as f:
        result = json.load(f)
    return result

def save_pkmn_info(pkmn_info):
    with open(PKMN_INFO_PATH, "w") as f:
        json.dump(pkmn_info, f, indent=4)

def read_collection():
    df_col = pd.read_csv(COLLECTION_PATH, sep=";")
    df_kork = df_col[df_col["Category"] == "KorkDex"]
    df_kork["name_ascii"] = df_kork["Name"].apply(lambda x: unicodedata.normalize("NFD", x).encode("ascii", "ignore").decode("utf-8").lower())
    df_kork_old = df_kork[df_kork["Set"].isin([kork_sets[set_id] for set_id in old_sets])]
    df_kork_new = df_kork[df_kork["Set"].isin([kork_sets[set_id] for set_id in new_sets])]

    pkmn_info = load_pkmn_info()
    pkmn_nat_ids = {}
    for _, row in tqdm(df_kork_new.iterrows()):
        pkmn_name = row["name_ascii"]
        if (pkmn_single_info := pkmn_info.get(pkmn_name)) is None:
            # Load pokemon info from api
            pokeapi_request_url = f"{POKEAPI_PATH}{pkmn_name}"
            print(f"Request: {pokeapi_request_url}")
            pokeapi_res = requests.get(pokeapi_request_url)
            if pokeapi_res.status_code != 200:
                raise ValueError(f"PokeApi request {pokeapi_request_url} failed.")
            pokeapi_content = json.loads(pokeapi_res.content)
            national_id = pokeapi_content["id"]
            pkmn_info[pkmn_name] = {"national_id": national_id}
            save_pkmn_info(pkmn_info)
            time.sleep(1)
        else:
            national_id = pkmn_single_info["national_id"]
        pkmn_nat_ids[pkmn_name] = national_id
    series_nat_ids = pd.Series(pkmn_nat_ids)
    series_nat_ids.name = "nat_id"
    # Order by Nat IDs
    df_kork_new_nat = pd.merge(df_kork_new, series_nat_ids, left_on="name_ascii", right_index=True, how="left")
    df_kork_new_nat = df_kork_new_nat.sort_values(by="nat_id")
    pkmn_ordered = df_kork_new_nat.groupby("nat_id").count()["Set"]
    counts_for_gen = collections.defaultdict(dict)
    for gen, (first_id, last_id) in pkmn_in_gen.items():
        pkmn_ordered_gen = pkmn_ordered.loc[first_id:last_id+1]
        counts_for_gen[gen] = dict(collections.Counter(pkmn_ordered_gen))
    return counts_for_gen

if __name__ == "__main__":
    counts_for_gen = read_collection()
    for gen, counts in counts_for_gen.items():
        for nr, count in counts.items():
            print(gen, f"{count}x{nr}")
    print()