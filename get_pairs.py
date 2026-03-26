import requests
import json

try:
    r = requests.get('https://api.binance.com/api/v3/ticker/24hr')
    data = r.json()
    pairs = [i for i in data if i['symbol'].endswith('USDT') and all(x not in i['symbol'] for x in ['UP', 'DOWN', 'BEAR', 'BULL'])]
    pairs.sort(key=lambda x: float(x['quoteVolume']), reverse=True)
    top_100 = [p['symbol'] for p in pairs[:100]]
    print(json.dumps(top_100))
except Exception as e:
    print(f"Error: {e}")
