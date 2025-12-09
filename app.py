"""
Dixmont Tax Map Viewer - Standalone Application
A Flask-based interactive tax map viewer for the Town of Dixmont, Maine
"""

import os
import json
import zipfile
import xml.etree.ElementTree as ET
from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for API access from other domains

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload
DATA_DIR = os.path.join(os.path.dirname(__file__), 'static', 'data')


def parse_kml(kml_content):
    """Parse KML content and extract features"""
    # KML namespace
    ns = {
        'kml': 'http://www.opengis.net/kml/2.2',
        'gx': 'http://www.google.com/kml/ext/2.2'
    }

    features = []

    try:
        root = ET.fromstring(kml_content)

        # Find all Placemarks
        for placemark in root.findall('.//kml:Placemark', ns):
            feature = {
                'type': 'Feature',
                'properties': {},
                'geometry': None
            }

            # Get name
            name_elem = placemark.find('kml:name', ns)
            if name_elem is not None and name_elem.text:
                feature['properties']['name'] = name_elem.text

            # Get description
            desc_elem = placemark.find('kml:description', ns)
            if desc_elem is not None and desc_elem.text:
                feature['properties']['description'] = desc_elem.text

            # Get extended data
            extended_data = placemark.find('kml:ExtendedData', ns)
            if extended_data is not None:
                for data in extended_data.findall('kml:Data', ns):
                    key = data.get('name')
                    value_elem = data.find('kml:value', ns)
                    if key and value_elem is not None:
                        feature['properties'][key] = value_elem.text

                # Also check for SchemaData
                for schema_data in extended_data.findall('.//kml:SimpleData', ns):
                    key = schema_data.get('name')
                    if key and schema_data.text:
                        feature['properties'][key] = schema_data.text

            # Get geometry - Polygon
            polygon = placemark.find('.//kml:Polygon', ns)
            if polygon is not None:
                coords_elem = polygon.find('.//kml:coordinates', ns)
                if coords_elem is not None and coords_elem.text:
                    coordinates = parse_coordinates(coords_elem.text)
                    feature['geometry'] = {
                        'type': 'Polygon',
                        'coordinates': [coordinates]
                    }

            # Get geometry - Point
            point = placemark.find('.//kml:Point', ns)
            if point is not None:
                coords_elem = point.find('kml:coordinates', ns)
                if coords_elem is not None and coords_elem.text:
                    coords = coords_elem.text.strip().split(',')
                    feature['geometry'] = {
                        'type': 'Point',
                        'coordinates': [float(coords[0]), float(coords[1])]
                    }

            # Get geometry - LineString
            linestring = placemark.find('.//kml:LineString', ns)
            if linestring is not None:
                coords_elem = linestring.find('kml:coordinates', ns)
                if coords_elem is not None and coords_elem.text:
                    coordinates = parse_coordinates(coords_elem.text)
                    feature['geometry'] = {
                        'type': 'LineString',
                        'coordinates': coordinates
                    }

            # Get geometry - MultiGeometry
            multi_geom = placemark.find('.//kml:MultiGeometry', ns)
            if multi_geom is not None:
                geometries = []
                for poly in multi_geom.findall('.//kml:Polygon', ns):
                    coords_elem = poly.find('.//kml:coordinates', ns)
                    if coords_elem is not None and coords_elem.text:
                        coordinates = parse_coordinates(coords_elem.text)
                        geometries.append({
                            'type': 'Polygon',
                            'coordinates': [coordinates]
                        })
                if geometries:
                    if len(geometries) == 1:
                        feature['geometry'] = geometries[0]
                    else:
                        feature['geometry'] = {
                            'type': 'MultiPolygon',
                            'coordinates': [g['coordinates'] for g in geometries]
                        }

            if feature['geometry']:
                features.append(feature)

    except ET.ParseError as e:
        print(f"KML parse error: {e}")

    return features


def parse_coordinates(coord_string):
    """Parse KML coordinate string into array of [lon, lat] pairs"""
    coordinates = []
    for coord in coord_string.strip().split():
        parts = coord.split(',')
        if len(parts) >= 2:
            try:
                lon = float(parts[0])
                lat = float(parts[1])
                coordinates.append([lon, lat])
            except ValueError:
                continue
    return coordinates


def parse_kmz(kmz_path):
    """Extract and parse KML from a KMZ file"""
    features = []

    try:
        with zipfile.ZipFile(kmz_path, 'r') as kmz:
            # Find KML file(s) in the archive
            kml_files = [f for f in kmz.namelist() if f.endswith('.kml')]

            for kml_file in kml_files:
                kml_content = kmz.read(kml_file)
                features.extend(parse_kml(kml_content))

    except zipfile.BadZipFile:
        print(f"Invalid KMZ file: {kmz_path}")
    except Exception as e:
        print(f"Error parsing KMZ: {e}")

    return features


def load_geojson_data():
    """Load GeoJSON data from the data directory"""
    geojson_path = os.path.join(DATA_DIR, 'parcels.geojson')

    if os.path.exists(geojson_path):
        with open(geojson_path, 'r') as f:
            return json.load(f)

    # Check for KMZ files and convert
    for filename in os.listdir(DATA_DIR):
        if filename.endswith('.kmz'):
            kmz_path = os.path.join(DATA_DIR, filename)
            features = parse_kmz(kmz_path)
            if features:
                geojson = {
                    'type': 'FeatureCollection',
                    'features': features
                }
                # Cache the converted data
                with open(geojson_path, 'w') as f:
                    json.dump(geojson, f)
                return geojson

    # Return empty feature collection if no data
    return {'type': 'FeatureCollection', 'features': []}


# Routes
@app.route('/')
def index():
    """Main map viewer page"""
    return render_template('index.html')


@app.route('/api/parcels')
def get_parcels():
    """API endpoint to get parcel GeoJSON data"""
    geojson = load_geojson_data()
    return jsonify(geojson)


@app.route('/api/parcel/<parcel_id>')
def get_parcel(parcel_id):
    """API endpoint to get a specific parcel by ID"""
    geojson = load_geojson_data()

    for feature in geojson.get('features', []):
        props = feature.get('properties', {})
        # Check various ID fields
        if (props.get('MAP_LOT') == parcel_id or
            props.get('PARCEL_ID') == parcel_id or
            props.get('name') == parcel_id or
            props.get('Map_Lot') == parcel_id):
            return jsonify(feature)

    return jsonify({'error': 'Parcel not found'}), 404


@app.route('/api/search')
def search_parcels():
    """Search parcels by owner name, map/lot, or address"""
    query = request.args.get('q', '').lower()

    if not query or len(query) < 2:
        return jsonify({'results': []})

    geojson = load_geojson_data()
    results = []

    for feature in geojson.get('features', []):
        props = feature.get('properties', {})

        # Search in common fields
        searchable = ' '.join([
            str(props.get('OWNER', '')),
            str(props.get('Owner', '')),
            str(props.get('owner', '')),
            str(props.get('MAP_LOT', '')),
            str(props.get('Map_Lot', '')),
            str(props.get('name', '')),
            str(props.get('ADDRESS', '')),
            str(props.get('Address', '')),
            str(props.get('LOCATION', '')),
        ]).lower()

        if query in searchable:
            # Get centroid for map navigation
            geometry = feature.get('geometry', {})
            center = get_geometry_center(geometry)

            results.append({
                'id': props.get('MAP_LOT') or props.get('Map_Lot') or props.get('name', 'Unknown'),
                'owner': props.get('OWNER') or props.get('Owner') or props.get('owner', 'Unknown'),
                'address': props.get('ADDRESS') or props.get('Address') or props.get('LOCATION', ''),
                'acreage': props.get('ACREAGE') or props.get('Acreage') or props.get('ACRES', ''),
                'center': center
            })

            if len(results) >= 20:  # Limit results
                break

    return jsonify({'results': results})


def get_geometry_center(geometry):
    """Calculate center point of a geometry"""
    if not geometry:
        return None

    geom_type = geometry.get('type')
    coords = geometry.get('coordinates', [])

    if geom_type == 'Point':
        return coords

    elif geom_type == 'Polygon':
        # Average of outer ring coordinates
        if coords and coords[0]:
            ring = coords[0]
            lon_sum = sum(c[0] for c in ring)
            lat_sum = sum(c[1] for c in ring)
            count = len(ring)
            return [lon_sum / count, lat_sum / count]

    elif geom_type == 'MultiPolygon':
        # Average of all coordinates
        all_coords = []
        for polygon in coords:
            if polygon and polygon[0]:
                all_coords.extend(polygon[0])
        if all_coords:
            lon_sum = sum(c[0] for c in all_coords)
            lat_sum = sum(c[1] for c in all_coords)
            count = len(all_coords)
            return [lon_sum / count, lat_sum / count]

    return None


@app.route('/api/stats')
def get_stats():
    """Get statistics about loaded parcel data"""
    geojson = load_geojson_data()
    features = geojson.get('features', [])

    return jsonify({
        'total_parcels': len(features),
        'has_data': len(features) > 0,
        'sample_properties': features[0].get('properties', {}).keys() if features else []
    })


@app.route('/health')
def health():
    """Health check endpoint for Cloud Run"""
    return jsonify({'status': 'healthy'})


# Static files (for development)
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
