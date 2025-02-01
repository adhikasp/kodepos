from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
import pandas as pd
import folium
import numpy as np
from scipy.spatial import ConvexHull
from typing import Dict

app = FastAPI(title="Indonesia Post Code Map")

# Cache to store pre-calculated map data for each zoom level
map_cache: Dict[int, str] = {}

# Load the data once when starting the server
try:
    df = pd.read_csv('kodepos.csv')
    # Convert postal codes to strings to preserve leading zeros
    df['code'] = df['code'].astype(str).str.zfill(5)
    
    # Filter points to only include those within reasonable bounds for Indonesia
    # Approximate bounds: Latitude: -11 to 6, Longitude: 95 to 141
    df = df[
        (df['latitude'] >= -11) & (df['latitude'] <= 6) &
        (df['longitude'] >= 95) & (df['longitude'] <= 141)
    ]
except Exception as e:
    print(f"Error loading data: {e}")
    raise

def remove_outliers(points):
    """Remove outliers using IQR method."""
    if len(points) < 4:  # Need at least 4 points for IQR
        return points
        
    iqr_multiplier = 1.5
        
    q1_lat = np.percentile(points[:, 0], 25)
    q3_lat = np.percentile(points[:, 0], 75)
    iqr_lat = q3_lat - q1_lat
    
    q1_lon = np.percentile(points[:, 1], 25)
    q3_lon = np.percentile(points[:, 1], 75)
    iqr_lon = q3_lon - q1_lon
    
    lat_lower = q1_lat - iqr_multiplier * iqr_lat
    lat_upper = q3_lat + iqr_multiplier * iqr_lat
    lon_lower = q1_lon - iqr_multiplier * iqr_lon
    lon_upper = q3_lon + iqr_multiplier * iqr_lon
    
    mask = (
        (points[:, 0] >= lat_lower) & (points[:, 0] <= lat_upper) &
        (points[:, 1] >= lon_lower) & (points[:, 1] <= lon_upper)
    )
    return points[mask]

def get_color(feature):
    """Generate a color based on the postal code value"""
    return f'#{hash(str(feature)) & 0xFFFFFF:06x}'

def calculate_map_features(zoom_level: int) -> folium.Map:
    """Calculate map features for a specific zoom level"""
    # Create base map centered on Indonesia
    m = folium.Map(location=[-2.5489, 118.0149], zoom_start=5)
    
    # Ensure zoom level is within bounds
    zoom_level = max(1, min(5, zoom_level))
        
    # Create postal code prefix based on zoom level
    df['prefix'] = df['code'].str[:zoom_level]
    
    # Group by prefix and calculate center points
    grouped = df.groupby('prefix').agg({
        'latitude': 'mean',
        'longitude': 'mean',
        'village': 'count'
    }).reset_index()
    
    # Create polygons for each postal code area
    for _, row in grouped.iterrows():
        points = df[df['prefix'] == row['prefix']][['latitude', 'longitude']].values
        if len(points) < 3:
            folium.CircleMarker(
                location=[row['latitude'], row['longitude']],
                popup=f'Postal Code Prefix: {row["prefix"]}<br>Villages: {row["village"]}',
                color=get_color(row['prefix']),
                fill=True,
                fill_opacity=0.7,
                radius=8
            ).add_to(m)
            continue
            
        try:
            filtered_points = remove_outliers(points)
            if len(filtered_points) < 3:
                folium.CircleMarker(
                    location=[row['latitude'], row['longitude']],
                    popup=f'Postal Code Prefix: {row["prefix"]}<br>Villages: {row["village"]}',
                    color=get_color(row['prefix']),
                    fill=True,
                    fill_opacity=0.7,
                    radius=8
                ).add_to(m)
                continue
                
            hull = ConvexHull(filtered_points)
            hull_points = filtered_points[hull.vertices]
            
            folium.Polygon(
                locations=hull_points,
                popup=f'Postal Code Prefix: {row["prefix"]}<br>Villages: {row["village"]}',
                color=get_color(row['prefix']),
                fill=True,
                fill_opacity=0.4,
                weight=2
            ).add_to(m)
        except Exception as e:
            print(f"Error creating polygon for prefix {row['prefix']}: {e}")
            folium.CircleMarker(
                location=[row['latitude'], row['longitude']],
                popup=f'Postal Code Prefix: {row["prefix"]}<br>Villages: {row["village"]}',
                color=get_color(row['prefix']),
                fill=True,
                fill_opacity=0.7,
                radius=8
            ).add_to(m)
            continue
    
    return m

def initialize_cache():
    """Initialize the cache with pre-calculated map data for all zoom levels"""
    import os
    import json
    
    cache_file = "map_cache.json"
    
    if os.path.exists(cache_file):
        print("Loading map cache from file...")
        with open(cache_file, 'r', encoding='utf-8') as f:
            global map_cache
            map_cache = json.load(f)
        print("Map cache loaded successfully!")
        return
        
    print("Initializing map cache...")
    for zoom_level in range(1, 6):
        print(f"Calculating map data for zoom level {zoom_level}...")
        m = calculate_map_features(zoom_level)
        map_cache[zoom_level] = m.get_root().render()
    
    print("Saving map cache to file...")
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(map_cache, f)
    print("Map cache initialization complete!")\

initialize_cache()

@app.get("/map-data")
async def get_map_data(zoom_level: int = 1):
    """Return cached map HTML for AJAX updates"""
    try:
        zoom_level = max(1, min(5, zoom_level))
        return JSONResponse(content={"map_html": map_cache[zoom_level]})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", response_class=HTMLResponse)
async def get_map(zoom_level: int = 1):
    """Serve the cached map with specified zoom level"""
    try:
        zoom_level = max(1, min(5, zoom_level))
        map_html = map_cache[zoom_level]
        
        # Insert our custom controls before the closing body tag
        control_html = """
        <div style="position: fixed; top: 20px; right: 20px; background: white; padding: 10px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.2); z-index: 1000;">
            <h3 style="margin: 0 0 10px 0;">Postal Code Zoom Level</h3>
            <input type="range" id="zoomLevel" min="1" max="5" value="{}" style="width: 200px;" autocomplete="off" data-form-type="other" data-lpignore="true">
            <span id="zoomValue">{}</span>
        </div>
        <div id="map-container"></div>
        <script>
            const slider = document.getElementById('zoomLevel');
            const output = document.getElementById('zoomValue');
            output.innerHTML = slider.value;
            
            slider.oninput = function() {{
                output.innerHTML = this.value;
            }}
            
            let debounceTimer;
            slider.addEventListener('input', function() {{
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => {{
                    window.location.href = `/?zoom_level=${{this.value}}`;
                }}, 10);
            }});
        </script>
        </body>
        """.format(zoom_level, zoom_level)
        
        return map_html.replace("</body>", control_html)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 