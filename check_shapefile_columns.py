import geopandas as gpd

SHAPEFILE_PATH = r"C:\Users\New\Downloads\Seismic_Zones\Seismic_Zones.shp"  # match your actual path

gdf = gpd.read_file(SHAPEFILE_PATH)

print("=== seismic_zo column ===")
print(gdf["seismic_zo"].value_counts(dropna=False))

print("\n=== intensity_ column ===")
print(gdf["intensity_"].value_counts(dropna=False))
