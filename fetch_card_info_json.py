import requests
import json


def card_info_json():
    response = requests.get("https://db.ygoprodeck.com/api/v7/cardinfo.php")
    response.raise_for_status()
    return response.json()


if __name__ == '__main__':
    data = card_info_json()
    with open("cardinfo.json", "w", encoding="utf-8") as f:
        json.dump(data, f)