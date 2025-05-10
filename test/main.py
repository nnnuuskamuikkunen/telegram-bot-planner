import requests
import datetime
import json
# import api_key
# api_key=api_key.api['api_key']
api_key='8059208448:AAFnzPAfwvrfehwl9JvP7JacTpVE3yGK6jc'

def run():
    url = "https://api.telegram.org/bot{}/getUpdates".format(api_key)
    response = requests.get(url)
    data=response.json()
    print(data)

if __name__ == "__main__":
    run()