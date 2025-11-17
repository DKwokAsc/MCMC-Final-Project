import os
import geopandas as gpd

# Optional: let GDAL try to restore or create a missing .shx index
os.environ["SHAPE_RESTORE_SHX"] = "YES"

def main():
    # Folder where THIS script lives: .../MCMC-FINAL-PROJECT/scripts
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Shapefile is in: scripts/data/wi_gen_20_st_prec.shp
    shapefile_path = os.path.join(script_dir, "data", "wi_gen_20_st_prec.shp")

    # Output GeoJSON in the same scripts/data folder
    output_json = os.path.join(script_dir, "data", "wi_gen_20_st_prec.json")

    print(f"Script directory:   {script_dir}")
    print(f"Reading shapefile:  {shapefile_path}")

    if not os.path.exists(shapefile_path):
        print("❌ ERROR: Shapefile not found. Contents of scripts/data:")
        data_dir = os.path.join(script_dir, "data")
        if os.path.isdir(data_dir):
            for name in os.listdir(data_dir):
                print("  ", name)
        else:
            print("  (scripts/data directory does not exist)")
        return

    # Read shapefile
    gdf = gpd.read_file(shapefile_path)

    # Optional: reproject to WGS84 if needed
    try:
        if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
            print("Reprojecting to WGS84 (EPSG:4326)...")
            gdf = gdf.to_crs(epsg=4326)
    except Exception as e:
        print(f"Warning: could not inspect/reproject CRS ({e}). Using original CRS.")

    print(f"Writing GeoJSON to: {output_json}")
    gdf.to_file(output_json, driver="GeoJSON")

    print("✅ Conversion complete!")

if __name__ == "__main__":
    main()
