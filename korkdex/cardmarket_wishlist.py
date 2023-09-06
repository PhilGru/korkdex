import pathlib

import pandas as pd
import requests

API_BASE_URL = "https://api.pokemontcg.io/v2/cards"
API_KEY = "282a0e4d-b45d-4d1d-b9bf-978c82c691af"
COLLECTION_PATH = pathlib.Path(__file__).parents[1] / "2023-07-21-dex-collection.csv"

def read_collection():
    df_col = pd.read_csv(COLLECTION_PATH, sep=";")
    return df_col[(df_col["Category"] == "Wishlist") | (df_col["Category"] == "Wishlist, but not for that price")]

def main():
    df_col = read_collection()
    df_col = df_col.sample(5)
    df_col["set_id"] = df_col["Id"].str.split("-").apply(lambda x: x[0])
    df_col["nr"] = df_col["Id"].str.split("-").apply(lambda x: x[-1])
    
    headers = {"X-Api-Key": API_KEY}
    for _, card_row in df_col.iterrows():
        print()
        print()
        # params = {
        #     "q": {
        #         "set.id": card_row["set_id"],
        #         "number": card_row["nr"]
        #     }
        # }
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

        print(card_row)
        print()
        attacks = response_card["attacks"]
        if len(attacks) == 0:
            print(f"{response_card['name']}")
            continue
        attacks_str = "["
        for i, attack in enumerate(attacks):
            attacks_str += attack["name"]
            if i != (len(attacks) -1):
                attacks_str += " | "
        attacks_str += "]"
        print(f"{response_card['name']} {attacks_str}")
        continue


if __name__ == "__main__":
    main()