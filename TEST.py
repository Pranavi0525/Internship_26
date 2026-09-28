import time
import requests

url = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/438d3de0e0f40597bc563c1a91c9210a/MODIS_SP/68,6,98,38/5/2000-11-01"

print("Starting request...")
start = time.time()
try:
    resp = requests.get(url, timeout=(10, 30))  # (connect_timeout, read_timeout)
    print(f"Done in {time.time()-start:.1f}s -- status {resp.status_code}")
    print(resp.text[:300])
except requests.exceptions.ConnectTimeout:
    print(f"CONNECT timed out after {time.time()-start:.1f}s -- can't reach the server at all")
except requests.exceptions.ReadTimeout:
    print(f"READ timed out after {time.time()-start:.1f}s -- connected fine, but server never replied")
except Exception as e:
    print(f"Other error after {time.time()-start:.1f}s: {type(e).__name__}: {e}")