import requests
import json

try:
    r = requests.get('https://api.binance.com/api/v3/ticker/24hr')
    data = r.json()
    # Filter for USDT pairs, excluding leveraged tokens
    pairs = [i for i in data if i['symbol'].endswith('USDT') and all(x not in i['symbol'] for x in ['UP', 'DOWN', 'BEAR', 'BULL'])]
    # Sort by quote volume descending
    pairs.sort(key=lambda x: float(x['quoteVolume']), reverse=True)
    top_100 = [p['symbol'] for p in pairs[:100]]
    with open('top_100_pairs.txt', 'w', encoding='utf-8') as f:
        f.write(', '.join([f'"{p}"' for p in top_100]))
    print("Success: top_100_pairs.txt created.")
except Exception as e:
    print(f"Error: {e}")
