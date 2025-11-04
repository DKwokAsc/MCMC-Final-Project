#!/usr/bin/env python3
import os
import requests

# ======================================================
# USER CONFIGURATION (edit these values if needed)
# ======================================================
RDH_USERNAME = "ilyasomeed7@gmail.com"
RDH_PASSWORD = "H#13755854h"
STATE = "Wisconsin"      # You can change this to any state
OUTPUT_FORMAT = "csv"    # only csv is supported by the RDH API
RDH_LIST_URL = "https://redistrictingdatahub.org/wp-json/download/list"
# ======================================================

# Save path: ../data/wisconsin_datasets.csv relative to this script
script_dir = os.path.dirname(os.path.abspath(__file__))
output_dir = os.path.join(script_dir, "..", "data")
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, f"{STATE.lower().replace(' ', '_')}_datasets.csv")

# Prepare API parameters (same structure as your notebook)
params = {
    "username": RDH_USERNAME,
    "password": RDH_PASSWORD,
    "format": OUTPUT_FORMAT,
    "states": STATE,
}

print(f"Fetching dataset list for {STATE} from RDH...")

try:
    resp = requests.get(RDH_LIST_URL, params=params, timeout=60)
    resp.raise_for_status()
except requests.RequestException as e:
    print(f"Error fetching data: {e}")
    exit(1)

# Save output to relative path
with open(output_path, "wb") as f:
    f.write(resp.content)

print(f"Saved data for {STATE} to: {output_path}")
