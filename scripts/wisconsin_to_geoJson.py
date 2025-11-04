#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import time
import zipfile
from pathlib import Path
from urllib.parse import quote_plus

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============ EDIT THESE ============
RDH_USERNAME = "your_rdh_username_or_email"
RDH_PASSWORD = "your_rdh_password"
STATE        = "Wisconsin"
# Optional: further narrow beyond just "2024" (e.g., to ward/precinct)
KEYWORDS_ALL = ["2024"]  # add "ward", "precinct", "general" if you want stricter filtering
# ====================================

RDH_LIST_URL = "https://redistrictingdatahub.org/wp-json/download/list"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

POLITE_DELAY = 1.0  # seconds between HTTP calls (helps avoid rate limits)


def make_session() -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=1.5,  # 0s, 1.5s, 3.0s, 4.5s, ...
        status_forcelist=(403, 408, 409, 429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    s.headers.update(HEADERS)
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://",  HTTPAdapter(max_retries=retries))
    return s


SESSION = make_session()


def repo_paths(state: str):
    """Create/return data paths relative to this script."""
    script_dir = Path(__file__).resolve().parent
    data_dir = (script_dir / ".." / "data").resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    base = state.lower().replace(" ", "_")
    files_dir = data_dir / f"{base}_files"
    files_dir.mkdir(parents=True, exist_ok=True)

    geojson_dir = data_dir / f"{base}_geojson"
    geojson_dir.mkdir(parents=True, exist_ok=True)

    catalog_csv = data_dir / f"{base}_datasets.csv"
    return data_dir, files_dir, geojson_dir, catalog_csv


def fail_if_html(content: bytes, save_path: Path, what: str):
    head = content[:200].lstrip().lower()
    if head.startswith(b"<!doctype html") or head.startswith(b"<html"):
        bad = save_path.with_suffix(".html")
        bad.write_bytes(content)
        raise SystemExit(
            f"Got HTML instead of expected {what}. Saved page to {bad.name}. "
            f"Likely blocked or bad credentials."
        )


def fetch_catalog(state: str, catalog_csv: Path):
    print(f"Fetching catalog for {state} ...")
    params = {
        "username": RDH_USERNAME,
        "password": RDH_PASSWORD,
        "format": "csv",
        "states": state,
    }
    r = SESSION.get(RDH_LIST_URL, params=params, timeout=60, allow_redirects=False)
    if 300 <= r.status_code < 400:
        raise SystemExit(
            f"Catalog request redirected ({r.status_code}). Check username/password or access."
        )
    r.raise_for_status()

    content = r.content
    fail_if_html(content, catalog_csv, "CSV catalog")
    catalog_csv.write_bytes(content)
    print(f"Saved catalog → {catalog_csv}")
    time.sleep(POLITE_DELAY)


def iter_catalog_rows(catalog_csv: Path):
    """Yield rows from the downloaded CSV."""
    with catalog_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def is_valid_zip(path: Path) -> bool:
    try:
        return zipfile.is_zipfile(path)
    except Exception:
        return False


def download_zip(url_template: str, dest_zip: Path):
    """
    Download a single ZIP using the RDH URL template.
    Credentials are URL-encoded and inserted.
    Validates that the response is a real ZIP; if not, saves HTML for inspection.
    """
    u = quote_plus(RDH_USERNAME)
    p = quote_plus(RDH_PASSWORD)
    url = (url_template or "").replace("YOURUSERNAME", u).replace("YOURPASSWORD", p)

    # Skip if already a valid ZIP
    if dest_zip.exists() and dest_zip.stat().st_size > 0 and is_valid_zip(dest_zip):
        return "exists"

    print(f"Downloading {dest_zip.name} ...")
    r = SESSION.get(url, stream=True, timeout=300, allow_redirects=True)
    r.raise_for_status()

    content = r.content
    # Check Content-Type first, then sniff
    ctype = (r.headers.get("Content-Type") or "").lower()
    if "text/html" in ctype or content[:200].lstrip().lower().startswith(b"<html"):
        bad_html = dest_zip.with_suffix(".html")
        bad_html.write_bytes(content)
        raise RuntimeError(f"Server returned HTML, not ZIP (saved {bad_html.name}).")

    dest_zip.write_bytes(content)

    if not is_valid_zip(dest_zip):
        bad_html = dest_zip.with_suffix(".html")
        bad_html.write_bytes(content)
        raise RuntimeError(f"Download was not a ZIP (saved {bad_html.name}).")

    time.sleep(POLITE_DELAY)
    return "downloaded"


def convert_zip_shapefile_to_geojson(zip_path: Path, out_geojson: Path):
    """
    Read the .shp inside the ZIP and write a GeoJSON (EPSG:4326).
    """
    import geopandas as gpd

    if not is_valid_zip(zip_path):
        raise RuntimeError("Not a valid ZIP (check the .html saved next to it).")

    with zipfile.ZipFile(zip_path) as z:
        shp_inside = next((n for n in z.namelist() if n.lower().endswith(".shp")), None)
    if not shp_inside:
        raise RuntimeError("No .shp found inside ZIP")

    # Read the shapefile directly from the ZIP
    gdf = gpd.read_file(f"zip://{zip_path}!{shp_inside}")

    # Reproject to WGS84 for web maps if needed
    try:
        if gdf.crs is None or gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)
    except Exception:
        # If CRS is missing/unreadable, continue without reprojection
        pass

    out_geojson.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(out_geojson, driver="GeoJSON")


def main():
    if not RDH_USERNAME or not RDH_PASSWORD:
        raise SystemExit("Please set RDH_USERNAME and RDH_PASSWORD at the top of the script.")

    data_dir, files_dir, geojson_dir, catalog_csv = repo_paths(STATE)

    # 1) Fetch/refresh catalog (fail-fast if blocked)
    fetch_catalog(STATE, catalog_csv)

    # 2) Iterate catalog, filter ONLY 2024 shapefiles (+ optional keywords), download & convert
    downloads = 0
    conversions = 0

    for row in iter_catalog_rows(catalog_csv):
        fmt = (row.get("Format") or "").strip().upper()
        fname = (row.get("Filename") or "").strip()
        title = (row.get("Title") or "").strip()
        url_tmpl = (row.get("URL") or "").strip()

        # Filter: must reference 2024 somewhere (title/filename/url)
        blob = f"{fname} {title} {url_tmpl}".lower()
        if "2024" not in blob:
            continue

        # Optional: require all keywords (if you added more than ["2024"])
        if KEYWORDS_ALL:
            all_ok = all(k.lower() in blob for k in KEYWORDS_ALL)
            if not all_ok:
                continue

        # Only shapefiles
        if fmt != "SHP" or not fname or not url_tmpl:
            continue

        dest_zip = files_dir / fname
        base = Path(fname).stem  # e.g., wi_2024_gen_prec
        out_geojson = geojson_dir / f"{base}.geojson"

        try:
            status = download_zip(url_tmpl, dest_zip)
            if status == "downloaded":
                print(f"Saved ZIP → {dest_zip}")
                downloads += 1
            else:
                print(f"Using existing ZIP → {dest_zip}")

            if out_geojson.exists() and out_geojson.stat().st_size > 0:
                print(f"GeoJSON already exists → {out_geojson.name}")
                continue

            print(f"Converting {fname} → {out_geojson.name}")
            convert_zip_shapefile_to_geojson(dest_zip, out_geojson)
            print(f"Wrote GeoJSON → {out_geojson}")
            conversions += 1
        except Exception as e:
            print(f"{fname}: {e}")

    print(f"Done. Downloads: {downloads}, Conversions: {conversions}")


if __name__ == "__main__":
    main()