# Dixmont Tax Map Viewer

Interactive tax map viewer for the Town of Dixmont, Maine. A standalone Flask application that displays parcel data on an interactive Leaflet.js map.

## Features

- Interactive map with parcel boundaries
- Search by owner name, Map/Lot number, or address
- Multiple base map options (Street, Satellite, Topographic)
- Click parcels to view property details
- Mobile-responsive design
- KMZ/KML file parsing
- GeoJSON support

## Quick Start

### Local Development

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python app.py
   ```

4. Open http://localhost:8080 in your browser

### Adding Parcel Data

Place your parcel data in the `static/data/` directory:

- **KMZ files**: Will be automatically parsed and converted to GeoJSON
- **KML files**: Will be automatically parsed and converted to GeoJSON
- **GeoJSON files**: Name the file `parcels.geojson` for automatic loading

Expected property fields (case-insensitive):
- `MAP_LOT` or `PARCEL_ID` - Parcel identifier
- `OWNER` - Property owner name
- `ADDRESS` or `LOCATION` - Property address
- `ACREAGE` or `ACRES` - Parcel size
- `LAND_VALUE` - Land assessment value
- `BLDG_VALUE` - Building assessment value
- `TOTAL_VALUE` - Total assessment value

## Deployment to Cloud Run

### Using gcloud CLI

1. Build and deploy:
   ```bash
   gcloud run deploy dixmont-tax-maps \
     --source . \
     --region us-east1 \
     --project dixmont \
     --allow-unauthenticated
   ```

### Using Docker

1. Build the image:
   ```bash
   docker build -t dixmont-tax-maps .
   ```

2. Run locally:
   ```bash
   docker run -p 8080:8080 dixmont-tax-maps
   ```

3. Push to Google Container Registry:
   ```bash
   docker tag dixmont-tax-maps gcr.io/dixmont/dixmont-tax-maps
   docker push gcr.io/dixmont/dixmont-tax-maps
   ```

4. Deploy to Cloud Run:
   ```bash
   gcloud run deploy dixmont-tax-maps \
     --image gcr.io/dixmont/dixmont-tax-maps \
     --region us-east1 \
     --project dixmont \
     --allow-unauthenticated
   ```

## API Endpoints

- `GET /` - Main map viewer page
- `GET /api/parcels` - Get all parcel data as GeoJSON
- `GET /api/parcel/<id>` - Get specific parcel by ID
- `GET /api/search?q=<query>` - Search parcels
- `GET /api/stats` - Get parcel data statistics
- `GET /health` - Health check endpoint

## Project Structure

```
dixmont-tax-maps/
├── app.py              # Flask application
├── requirements.txt    # Python dependencies
├── Dockerfile          # Container configuration
├── README.md           # This file
├── static/
│   ├── css/
│   │   └── style.css   # Application styles
│   ├── js/
│   │   └── map.js      # Leaflet map JavaScript
│   └── data/
│       └── .gitkeep    # Placeholder for data files
└── templates/
    └── index.html      # Main HTML template
```

## Configuration

Environment variables:
- `PORT` - Server port (default: 8080)
- `FLASK_DEBUG` - Enable debug mode (default: false)

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## License

Town of Dixmont, Maine - Municipal Use
