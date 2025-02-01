# Indonesia Post Code Map

An interactive web application that visualizes Indonesia's postal code regions using FastAPI and Folium. The map allows you to explore postal code regions at different zoom levels, where each level corresponds to the number of digits in the postal code prefix.

## Features

- Interactive map centered on Indonesia
- Dynamic visualization of postal code regions
- Zoom levels based on postal code prefixes (1-5 digits)
- Color-coded regions for easy distinction
- Popup information showing postal code prefix and number of villages

## Usage

1. Start the server:
  ```bash
  uvicorn main:app --reload --host 0.0.0.0 --port 8000
  ```

2. Open your browser and visit `http://localhost:8000`

3. To change the zoom level, use the query parameter:
  ```
  http://localhost:8000/?zoom_level=2
  ```
  - Zoom level 1: Groups by first digit (e.g., 2xxxx)
  - Zoom level 2: Groups by first two digits (e.g., 23xxx)
  - Zoom level 3: Groups by first three digits (e.g., 237xx)
  - And so on up to level 5

## API Documentation

The API has one main endpoint:

- `GET /`: Returns the HTML map
  - Query Parameters:
    - `zoom_level` (optional, default=1): Integer between 1-5 representing the postal code grouping level

## Data Source

- https://github.com/sooluh/kodepos

## Disclaimer

This data is provided "as is" without any guarantee whatsoever. 
Feel free to fork, tinker, add, remove, change, or do whatever you want to it. 
