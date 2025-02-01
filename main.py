from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import pandas as pd
import folium
import numpy as np
from pathlib import Path
from scipy.spatial import ConvexHull

app = FastAPI(title="Indonesia Post Code Map")

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
    """Remove outliers using IQR method. More aggressive for zoom_level 1"""
    if len(points) < 4:  # Need at least 4 points for IQR
        return points
        
    # Use more aggressive multiplier for zoom level 1
    iqr_multiplier = 1.5
        
    q1_lat = np.percentile(points[:, 0], 25)
    q3_lat = np.percentile(points[:, 0], 75)
    iqr_lat = q3_lat - q1_lat
    
    q1_lon = np.percentile(points[:, 1], 25)
    q3_lon = np.percentile(points[:, 1], 75)
    iqr_lon = q3_lon - q1_lon
    
    # Define bounds using the dynamic multiplier
    lat_lower = q1_lat - iqr_multiplier * iqr_lat
    lat_upper = q3_lat + iqr_multiplier * iqr_lat
    lon_lower = q1_lon - iqr_multiplier * iqr_lon
    lon_upper = q3_lon + iqr_multiplier * iqr_lon
    
    # Filter points
    mask = (
        (points[:, 0] >= lat_lower) & (points[:, 0] <= lat_upper) &
        (points[:, 1] >= lon_lower) & (points[:, 1] <= lon_upper)
    )
    return points[mask]

def get_color(feature):
    """Generate a color based on the postal code value"""
    return f'#{hash(str(feature)) & 0xFFFFFF:06x}'

def create_map(zoom_level: int = 1):
    """Create a choropleth map based on postal code zoom level"""
    # Create base map centered on Indonesia
    m = folium.Map(location=[-2.5489, 118.0149], zoom_start=5)
    
    # Group data based on zoom level
    if zoom_level < 1:
        zoom_level = 1
    elif zoom_level > 5:
        zoom_level = 5
        
    # Create postal code prefix based on zoom level
    df['prefix'] = df['code'].str[:zoom_level]
    
    # Group by prefix and calculate center points
    grouped = df.groupby('prefix').agg({
        'latitude': 'mean',
        'longitude': 'mean',
        'village': 'count'  # Count number of villages in each area
    }).reset_index()
    
    # Create polygons for each postal code area
    for _, row in grouped.iterrows():
        # Get all points in this prefix group
        points = df[df['prefix'] == row['prefix']][['latitude', 'longitude']].values
        if len(points) < 3:  # Not enough points for a polygon
            # Add a marker instead
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
            # Remove outliers before creating the hull
            filtered_points = remove_outliers(points)
            if len(filtered_points) < 3:  # Not enough points after filtering
                # Add a marker for filtered points too
                folium.CircleMarker(
                    location=[row['latitude'], row['longitude']],
                    popup=f'Postal Code Prefix: {row["prefix"]}<br>Villages: {row["village"]}',
                    color=get_color(row['prefix']),
                    fill=True,
                    fill_opacity=0.7,
                    radius=8
                ).add_to(m)
                continue
                
            # Create a convex hull around the filtered points
            hull = ConvexHull(filtered_points)
            # Get the vertices of the convex hull in order
            hull_points = filtered_points[hull.vertices]
            
            # Create a polygon using the hull points
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
            # If polygon creation fails, fall back to marker
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

@app.get("/", response_class=HTMLResponse)
async def get_map(zoom_level: int = 1):
    """Serve the map with specified zoom level"""
    try:
        m = create_map(zoom_level)
        map_html = m.get_root().render()
        
        # Insert our custom controls before the closing body tag
        control_html = """
        <div style="position: fixed; top: 20px; right: 20px; background: white; padding: 10px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.2); z-index: 1000;">
            <h3 style="margin: 0 0 10px 0;">Postal Code Zoom Level</h3>
            <input type="range" id="zoomLevel" min="1" max="5" value="{}" style="width: 200px;">
            <span id="zoomValue">{}</span>
            <button onclick="updateMap()" style="display: block; margin-top: 10px; padding: 5px 10px;">Update Map</button>
        </div>
        <script>
            const slider = document.getElementById('zoomLevel');
            const output = document.getElementById('zoomValue');
            output.innerHTML = slider.value;
            
            slider.oninput = function() {{
                output.innerHTML = this.value;
            }}
            
            function updateMap() {{
                const zoomLevel = document.getElementById('zoomLevel').value;
                window.location.href = `/?zoom_level=${{zoomLevel}}`;
            }}
        </script>
        </body>
        """.format(zoom_level, zoom_level)
        
        return map_html.replace("</body>", control_html)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 