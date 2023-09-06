import dataclasses
import json
import pathlib

import pandas as pd
import requests
from tqdm import tqdm

API_BASE_URL = "https://api.pokemontcg.io/v2/cards"
API_KEY = "282a0e4d-b45d-4d1d-b9bf-978c82c691af"
COLLECTION_PATH = pathlib.Path(__file__).parents[1] / "2023-09-05-dex-collection.csv"
POKEAPI_CACHE_PATH = pathlib.Path(__file__).parents[1] / "pokeapi_results.json"
CARDAPI_CACHE_PATH = pathlib.Path(__file__).parents[1] / "cardapi_results.json"
DEXDATA_PATH = pathlib.Path(__file__).parents[1] / "dexdata.json"
CARDDEX_CATEGORY = "KorkDex"
POKEAPI_BASE_URL = "http://127.0.0.1:8000/api/v2/"

REGIONAL_VERSIONS = {
    "alola": 7,
    "galar": 8,
    "hisui": 8,
    "paldea": 9
}
MIN_POKEMON_NR = 1
MAX_POKEMON_NR = 1010

EXCLUDE_IF_CONTAINS = [
    "-totem-",
    "pikachu-alola-cap",
    "tauros-paldea-blaze-breed",
    "tauros-paldea-aqua-breed",
    "darmanitan-galar-zen"
]

POKEMON_IN_GEN = {
    1: (1, 151),
    2: (152, 251),
    3: (252, 386),
    4: (387, 494),
    5: (495, 649),
    6: (650, 721),
    7: (722, 809),
    8: (810, 905),
    9: (906, MAX_POKEMON_NR),
}


@dataclasses.dataclass
class PokemonBase:
    name: str
    nr: int
    gen: str
    
@dataclasses.dataclass
class CardBase:
    name: str
    nr: int
    gen: str
    card_id: str

@dataclasses.dataclass
class DexFach:
    name: str
    nr: int
    gen: str
    count: int
    tray: int
    position: int

class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)

def pokeapi_data():
    all_pokemon = []
    for pokemon_nr in range(MIN_POKEMON_NR, MAX_POKEMON_NR+1):
        print(pokemon_nr)
        gen = [g_nr for g_nr, g_range in POKEMON_IN_GEN.items() if pokemon_nr in range(g_range[0], g_range[1]+1)][0]
        response = requests.get(
            POKEAPI_BASE_URL + f"pokemon-species/{pokemon_nr}"
            )
        response_json = response.json()
        
        for variety in response_json["varieties"]:
            variety_name = variety["pokemon"]["name"].lower()
            if any(substring in variety_name for substring in EXCLUDE_IF_CONTAINS):
                continue
            if variety["is_default"]:
                all_pokemon.append(
                    PokemonBase(
                        name=variety_name,
                        nr=pokemon_nr,
                        gen=gen
                    )
                )
                continue
            for region_string, region_gen in REGIONAL_VERSIONS.items():
                if region_string in variety_name:
                    all_pokemon.append(
                        PokemonBase(
                            name=variety_name,
                            nr=pokemon_nr,
                            gen=region_gen
                        )
                    )
    with open(POKEAPI_CACHE_PATH, "w") as f:
        json.dump(all_pokemon, f, indent=4, cls=EnhancedJSONEncoder)

def read_collection():
    df_col = pd.read_csv(COLLECTION_PATH, sep=";")
    return df_col[df_col["Category"] == CARDDEX_CATEGORY]

def card_data():
    # Number of cards to process at once
    nr_cards = 50
    
    df_col = read_collection()
    df_col["set_id"] = df_col["Id"].str.split("-").apply(lambda x: x[0])
    df_col["nr"] = df_col["Id"].str.split("-").apply(lambda x: x[-1])

    with open(CARDAPI_CACHE_PATH, "r") as f:
        cardapi_results = json.load(f)
    
    # Only look at cards where I don't have the information already
    all_card_ids = [result["card_id"] for result in cardapi_results]
    df_col = df_col[~df_col["Id"].isin(all_card_ids)]

    headers = {"X-Api-Key": API_KEY}

    print(f"Processing next {nr_cards} of {df_col.shape[0]} cards.")
    for _, card_row in tqdm(df_col.iterrows()):
        params = {
            "q": f"set.id:{card_row['set_id']} number:{card_row['nr']}"
        }
        response = requests.get(
            API_BASE_URL,
            headers=headers,
            params=params
            )
        response_data = response.json()["data"]
        if len(response_data) > 1:
            raise ValueError(f"Response has too many entrie: {response}")
        response_card = response_data[0]

        if len(response_card["nationalPokedexNumbers"]) > 1:
            raise ValueError(f"More than one natdex number for card {response_card}")
        natdex_number = response_card["nationalPokedexNumbers"][0]
        for region_name, region_gen in REGIONAL_VERSIONS.items():
            if region_name in response_card["name"].lower():
                gen = region_gen
                break
        else:
            gen = [g_nr for g_nr, g_range in POKEMON_IN_GEN.items() if natdex_number in range(g_range[0], g_range[1]+1)][0]
        
        cardapi_results.append(
            CardBase(
                name=response_card["name"],
                nr=natdex_number,
                gen=gen,
                card_id=card_row['Id']
            )
        )
        nr_cards -= 1
        if nr_cards == 0:
            break
    
    with open(CARDAPI_CACHE_PATH, "w") as f:
        json.dump(cardapi_results, f, indent=4, cls=EnhancedJSONEncoder)

def dex_data():
    # Number of cards in one fach
    fach_size = 5
    # Number of fach in one tray
    tray_size = 32

    with open(POKEAPI_CACHE_PATH, "r") as f:
        pokeapi_results = json.load(f)

    with open(CARDAPI_CACHE_PATH, "r") as f:
        cardapi_results = json.load(f)

    dex_data = []
    active_tray = 0
    pos_in_tray = 0
    for pokeapi_result in tqdm(pokeapi_results):
        cards = [pokeapi_result for cardapi_result in cardapi_results if (cardapi_result["nr"] == pokeapi_result["nr"]) and (cardapi_result["gen"] == pokeapi_result["gen"])]
        nr_cards = len(cards)
        nr_fach = nr_cards // fach_size + 1
        dex_fach = DexFach(
            name=cards[0]["name"] if nr_cards > 0 else pokeapi_result["name"],
            nr=pokeapi_result["nr"],
            gen=pokeapi_result["gen"],
            count=nr_cards,
            tray=active_tray,
            position=pos_in_tray
        )
        for _ in range(nr_fach):
            dex_data.append(dex_fach)
            pos_in_tray += 1
            if pos_in_tray == 32:
                pos_in_tray = 0
                active_tray += 1

    with open(DEXDATA_PATH, "w") as f:
        json.dump(dex_data, f, indent=4, cls=EnhancedJSONEncoder)


if __name__ == "__main__":
    # pokeapi_data()
    # card_data()
    dex_data()
