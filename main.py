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
                popup=f'Awalan Kode Pos: {row["prefix"]}<br>Desa/Kelurahan: {row["village"]}',
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
                    popup=f'Awalan Kode Pos: {row["prefix"]}<br>Desa/Kelurahan: {row["village"]}',
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
                popup=f'Awalan Kode Pos: {row["prefix"]}<br>Desa/Kelurahan: {row["village"]}',
                color=get_color(row['prefix']),
                fill=True,
                fill_opacity=0.4,
                weight=2
            ).add_to(m)
        except Exception as e:
            print(f"Error creating polygon for prefix {row['prefix']}: {e}")
            folium.CircleMarker(
                location=[row['latitude'], row['longitude']],
                popup=f'Awalan Kode Pos: {row["prefix"]}<br>Desa/Kelurahan: {row["village"]}',
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

@app.get("/", response_class=HTMLResponse)
async def get_map(zoom_level: int = 1):
    """Serve the cached map with specified zoom level"""
    try:
        zoom_level = max(1, min(5, zoom_level))
        map_html = map_cache[str(zoom_level)]  # Convert to string since JSON keys are strings
        
        # Update popup text to Indonesian
        map_html = map_html.replace('Postal Code Prefix:', 'Awalan Kode Pos:')
        map_html = map_html.replace('Villages:', 'Desa/Kelurahan:')
        
        # Create a complete HTML document that includes both map and controls
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Peta Kode Pos Indonesia</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="margin: 0; padding: 0;">
            {map_html}
            <div style="position: fixed; top: 80px; left: 20px; background: white; padding: 30px; 
                 border-radius: 12px; box-shadow: 0 4px 8px rgba(0,0,0,0.2); z-index: 1000; min-width: 600px;">
                <h2 style="margin: 0 0 25px 0; text-align: center; color: #2c3e50; font-size: 24px;">Detail Tingkat Kode Pos</h2>
                <div style="display: flex; align-items: start; justify-content: space-between; margin-bottom: 30px;">
                    <div style="flex: 1; padding-right: 30px;">
                        <input type="range" id="zoomLevel" min="1" max="5" value="{zoom_level}" 
                               style="writing-mode: bt-lr; -webkit-appearance: slider-vertical; width: 40px; height: 300px; transform: rotate(180deg);" 
                               autocomplete="off" data-form-type="other" data-lpignore="true">
                        <div id="zoomValue" style="margin-top: 15px; text-align: center; font-size: 1.5em; font-weight: bold; color: #2c3e50;">Tingkat {zoom_level}</div>
                    </div>
                    <div id="zoomDescription" style="flex: 2; font-size: 1.2em; color: #666; display: flex; flex-direction: column; justify-content: space-between; height: 300px; padding: 15px 0;">
                        <div class="level-item" data-level="1" style="padding: 10px; border-radius: 8px; background: #f8f9fa; cursor: pointer; transition: background 0.2s;"><strong>Tingkat 1:</strong> Wilayah kepulauan</div>
                        <div class="level-item" data-level="2" style="padding: 10px; border-radius: 8px; background: #f8f9fa; cursor: pointer; transition: background 0.2s;"><strong>Tingkat 2:</strong> Area provinsi</div>
                        <div class="level-item" data-level="3" style="padding: 10px; border-radius: 8px; background: #f8f9fa; cursor: pointer; transition: background 0.2s;"><strong>Tingkat 3:</strong> Zona kota/kabupaten</div>
                        <div class="level-item" data-level="4" style="padding: 10px; border-radius: 8px; background: #f8f9fa; cursor: pointer; transition: background 0.2s;"><strong>Tingkat 4:</strong> Area kecamatan</div>
                        <div class="level-item" data-level="5" style="padding: 10px; border-radius: 8px; background: #f8f9fa; cursor: pointer; transition: background 0.2s;"><strong>Tingkat 5:</strong> Tingkat desa/kelurahan</div>
                    </div>
                </div>

                <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 20px 0;">

                <div>
                    <h3 style="margin: 0 0 15px 0; color: #2c3e50;">Tentang Kode Pos Indonesia</h3>
                    <p style="margin: 0 0 15px 0; color: #666; line-height: 1.6;">
                        Kode pos di Indonesia terdiri dari lima angka:
                    </p>
                    <ul style="color: #666; padding-left: 20px; margin-bottom: 15px;">
                        <li>Angka pertama merupakan kode wilayah tempat kantor pos berlokasi</li>
                        <li>Angka kedua dan ketiga merupakan kode kabupaten atau kota</li>
                        <li>Angka keempat merupakan kode kecamatan</li>
                        <li>Angka kelima merupakan kode desa atau kelurahan</li>
                    </ul>
                    <p style="margin: 0 0 15px 0; color: #666; line-height: 1.6;">
                        <strong>Pengecualian untuk Jakarta:</strong>
                    </p>
                    <ul style="color: #666; padding-left: 20px; margin-bottom: 15px;">
                        <li>Angka ketiga merupakan kode kecamatan</li>
                        <li>Angka keempat merupakan kode kelurahan</li>
                        <li>Angka kelima adalah "0"</li>
                    </ul>
                    <p style="margin: 0; color: #666; font-size: 0.9em;">
                        Sumber: <a href="https://id.wikipedia.org/wiki/Daftar_kode_pos_di_Indonesia" target="_blank" style="color: #3498db;">Wikipedia - Daftar kode pos di Indonesia</a>
                    </p>
                </div>
            </div>

            <script>
                const slider = document.getElementById('zoomLevel');
                const output = document.getElementById('zoomValue');
                const levelItems = document.querySelectorAll('.level-item');
                
                // Function to update the UI and trigger navigation
                function updateLevel(level) {{
                    slider.value = level;
                    output.innerHTML = `Tingkat ${{level}}`;
                    window.location.href = `/?zoom_level=${{level}}`;
                }}
                
                // Add hover effect to level items
                levelItems.forEach(item => {{
                    item.addEventListener('mouseover', () => {{
                        item.style.background = '#e9ecef';
                    }});
                    item.addEventListener('mouseout', () => {{
                        item.style.background = '#f8f9fa';
                    }});
                    // Add click handler
                    item.addEventListener('click', () => {{
                        const level = item.getAttribute('data-level');
                        updateLevel(level);
                    }});
                }});
                
                // Update display when slider changes
                slider.oninput = function() {{
                    output.innerHTML = `Level ${{this.value}}`;
                }}
                
                let debounceTimer;
                slider.addEventListener('input', function() {{
                    clearTimeout(debounceTimer);
                    debounceTimer = setTimeout(() => {{
                        updateLevel(this.value);
                    }}, 10);
                }});
            </script>
        </body>
        </html>
        """
        
        return full_html
    except Exception as e:
        print(f"Error: {str(e)}")  # Add debug print
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 