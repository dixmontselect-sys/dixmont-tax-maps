"""
Dixmont Tax Map Viewer - Standalone Application
A Flask-based interactive tax map viewer for the Town of Dixmont, Maine
"""

import os
import json
import re
import zipfile
import io
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from datetime import datetime
import requests
from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS

# Remote KMZ file URL (tax assessing company)
REMOTE_KMZ_URL = "https://4a1b1e2a-906f-4969-8e26-d6a9ca3c78df.filesusr.com/ugd/85f57f_24a82e0a5f174629ab7ed01b8f67a2f5.kmz?dn=DixmontParcels.kmz"

# Track data source
data_source_info = {
    'source': 'unknown',
    'loaded_at': None,
    'parcel_count': 0,
    'error': None
}


class KMLDescriptionParser(HTMLParser):
    """Parse HTML table from KML description to extract property data"""

    def __init__(self):
        super().__init__()
        self.data = {}
        self.current_key = None
        self.current_value = None
        self.in_td = False
        self.td_count = 0
        self.row_data = []
        self.owner_from_header = None
        self.in_header_row = False

    def handle_starttag(self, tag, attrs):
        if tag == 'td':
            self.in_td = True
            self.td_count += 1
        elif tag == 'tr':
            self.row_data = []
            self.td_count = 0
            # Check if this is a header row (bold, centered)
            attrs_dict = dict(attrs)
            style = attrs_dict.get('style', '')
            if 'font-weight:bold' in style or 'text-align:center' in style:
                self.in_header_row = True
            else:
                self.in_header_row = False

    def handle_endtag(self, tag):
        if tag == 'td':
            self.in_td = False
        elif tag == 'tr':
            # Process completed row
            if len(self.row_data) == 2:
                key, value = self.row_data
                if key and value:
                    self.data[key.strip()] = value.strip()
            elif len(self.row_data) == 1 and self.in_header_row:
                # Single cell in header row is often the owner name
                self.owner_from_header = self.row_data[0].strip()
            self.row_data = []

    def handle_data(self, data):
        if self.in_td:
            text = data.strip()
            if text:
                self.row_data.append(text)

    def get_properties(self):
        """Return extracted properties with normalized keys"""
        props = {}

        # Map various key names to standard property names
        key_mapping = {
            'Owner': 'Owner',
            'owner': 'Owner',
            'OWNER': 'Owner',
            'MapBkLot': 'MapLot',
            'TRMapBkLot': 'MapLot',
            'Map_Lot': 'MapLot',
            'MAP_LOT': 'MapLot',
            'GISAcres': 'Acres',
            'TRIOAcres': 'Acres',
            'Acres': 'Acres',
            'ACRES': 'Acres',
            'LandValue': 'LandValue',
            'Land_Value': 'LandValue',
            'LAND_VALUE': 'LandValue',
            'BldgValue': 'BldgValue',
            'Bldg_Value': 'BldgValue',
            'BLDG_VALUE': 'BldgValue',
            'TotalValue': 'TotalValue',
            'Total_Value': 'TotalValue',
            'TOTAL_VALUE': 'TotalValue',
            'Street': 'Street',
            'STREET': 'Street',
            'StNumber': 'StNumber',
            'Account': 'Account',
            'Town': 'Town',
            'County': 'County',
            'Year_Built': 'YearBuilt',
            'BldgStyle': 'BldgStyle',
            'NetAssess': 'NetAssess',
            'Exemption': 'Exemption',
        }

        for key, value in self.data.items():
            normalized_key = key_mapping.get(key, key)
            props[normalized_key] = value

        # Add owner from header if not found elsewhere
        if 'Owner' not in props and self.owner_from_header:
            props['Owner'] = self.owner_from_header

        return props


def parse_html_description(html_content):
    """Extract property data from HTML description"""
    if not html_content:
        return {}

    parser = KMLDescriptionParser()
    try:
        parser.feed(html_content)
        return parser.get_properties()
    except Exception as e:
        print(f"Error parsing HTML description: {e}")
        return {}

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

            # Get name (Map/Lot number)
            name_elem = placemark.find('kml:name', ns)
            if name_elem is not None and name_elem.text:
                feature['properties']['name'] = name_elem.text
                feature['properties']['MapLot'] = name_elem.text

            # Get description and parse HTML table for property data
            desc_elem = placemark.find('kml:description', ns)
            if desc_elem is not None and desc_elem.text:
                # Parse HTML description to extract property data
                html_props = parse_html_description(desc_elem.text)
                feature['properties'].update(html_props)

                # Keep raw description for reference (but truncated)
                # feature['properties']['description'] = desc_elem.text[:100]

            # Get extended data (fallback if no HTML description)
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

            # Use MapLot from parsed data if name was empty
            if not feature['properties'].get('name') and feature['properties'].get('MapLot'):
                feature['properties']['name'] = feature['properties']['MapLot']

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
                # Filter out large empty features (roads, ROW, unmapped areas)
                # These have no name and no owner and cover large areas
                props = feature['properties']
                name = props.get('name', '').strip()
                owner = props.get('Owner', '').strip()

                # Skip features that are clearly not parcels
                if not name and not owner:
                    # This is likely a road ROW or unmapped area - skip it
                    continue

                # Also skip features named just spaces or very generic
                if name in ['', ' ', 'UNK', 'ROW']:
                    # Skip unknown and right-of-way features
                    continue

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
    """Extract and parse KML from a KMZ file path"""
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


def parse_kmz_bytes(kmz_bytes):
    """Extract and parse KML from KMZ bytes (for remote files)"""
    features = []

    try:
        with zipfile.ZipFile(io.BytesIO(kmz_bytes), 'r') as kmz:
            # Find KML file(s) in the archive
            kml_files = [f for f in kmz.namelist() if f.endswith('.kml')]

            for kml_file in kml_files:
                kml_content = kmz.read(kml_file)
                features.extend(parse_kml(kml_content))

    except zipfile.BadZipFile:
        print("Invalid KMZ data from remote source")
    except Exception as e:
        print(f"Error parsing remote KMZ: {e}")

    return features


def fetch_remote_kmz():
    """Try to fetch KMZ from remote URL"""
    global data_source_info

    try:
        print(f"Attempting to fetch KMZ from remote URL...")
        response = requests.get(REMOTE_KMZ_URL, timeout=30)
        response.raise_for_status()

        # Check that we got a reasonable file size (KMZ should be > 10KB)
        if len(response.content) < 10000:
            raise ValueError(f"Remote file too small ({len(response.content)} bytes)")

        features = parse_kmz_bytes(response.content)

        if features:
            print(f"Successfully loaded {len(features)} features from remote KMZ")
            data_source_info['source'] = 'remote'
            data_source_info['loaded_at'] = datetime.now().isoformat()
            data_source_info['parcel_count'] = len(features)
            data_source_info['error'] = None
            return features
        else:
            raise ValueError("No features parsed from remote KMZ")

    except requests.exceptions.Timeout:
        error_msg = "Remote KMZ fetch timed out"
        print(error_msg)
        data_source_info['error'] = error_msg
    except requests.exceptions.RequestException as e:
        error_msg = f"Remote KMZ fetch failed: {str(e)}"
        print(error_msg)
        data_source_info['error'] = error_msg
    except Exception as e:
        error_msg = f"Remote KMZ processing error: {str(e)}"
        print(error_msg)
        data_source_info['error'] = error_msg

    return None


def load_geojson_data():
    """Load GeoJSON data - tries remote first, falls back to local"""
    global data_source_info

    geojson_path = os.path.join(DATA_DIR, 'parcels.geojson')

    # Check if we have a cached file and if it's recent (less than 1 hour old)
    # For now, always try remote first on app start, then use cache
    if os.path.exists(geojson_path):
        # If we already know the source, just return cached data
        if data_source_info['source'] != 'unknown':
            with open(geojson_path, 'r') as f:
                return json.load(f)

    # Try remote source first
    features = fetch_remote_kmz()

    if features:
        geojson = {
            'type': 'FeatureCollection',
            'features': features
        }
        # Cache the converted data
        try:
            with open(geojson_path, 'w') as f:
                json.dump(geojson, f)
            print(f"Cached {len(features)} features from remote source")
        except Exception as e:
            print(f"Warning: Could not cache data: {e}")
        return geojson

    # Fallback to local KMZ file
    print("Falling back to local KMZ file...")
    for filename in os.listdir(DATA_DIR):
        if filename.endswith('.kmz'):
            kmz_path = os.path.join(DATA_DIR, filename)
            features = parse_kmz(kmz_path)
            if features:
                data_source_info['source'] = 'local'
                data_source_info['loaded_at'] = datetime.now().isoformat()
                data_source_info['parcel_count'] = len(features)

                geojson = {
                    'type': 'FeatureCollection',
                    'features': features
                }
                # Cache the converted data
                try:
                    with open(geojson_path, 'w') as f:
                        json.dump(geojson, f)
                    print(f"Cached {len(features)} features from local source")
                except Exception as e:
                    print(f"Warning: Could not cache data: {e}")
                return geojson

    # Check for existing cached file as last resort
    if os.path.exists(geojson_path):
        print("Using existing cached geojson file")
        data_source_info['source'] = 'cached'
        with open(geojson_path, 'r') as f:
            data = json.load(f)
            data_source_info['parcel_count'] = len(data.get('features', []))
            return data

    # Return empty feature collection if no data
    data_source_info['source'] = 'none'
    data_source_info['error'] = 'No data source available'
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
            str(props.get('Owner', '')),
            str(props.get('MapLot', '')),
            str(props.get('name', '')),
            str(props.get('Street', '')),
            str(props.get('Account', '')),
        ]).lower()

        if query in searchable:
            # Get centroid for map navigation
            geometry = feature.get('geometry', {})
            center = get_geometry_center(geometry)

            # Build address from street number and name
            st_num = props.get('StNumber', '')
            street = props.get('Street', '')
            address = f"{st_num} {street}".strip() if st_num != '0' else street

            results.append({
                'id': props.get('MapLot') or props.get('name', 'Unknown'),
                'owner': props.get('Owner', 'Unknown'),
                'address': address,
                'acreage': props.get('Acres', ''),
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
        'sample_properties': list(features[0].get('properties', {}).keys()) if features else [],
        'data_source': data_source_info
    })


@app.route('/api/data-source')
def get_data_source():
    """Get information about the current data source"""
    return jsonify(data_source_info)


@app.route('/api/refresh')
def refresh_data():
    """Force refresh data from remote source"""
    global data_source_info

    # Reset source info to trigger fresh load
    data_source_info['source'] = 'unknown'

    # Delete cached file
    geojson_path = os.path.join(DATA_DIR, 'parcels.geojson')
    if os.path.exists(geojson_path):
        try:
            os.remove(geojson_path)
        except:
            pass

    # Reload data
    geojson = load_geojson_data()

    return jsonify({
        'success': True,
        'data_source': data_source_info,
        'parcel_count': len(geojson.get('features', []))
    })


@app.route('/health')
def health():
    """Health check endpoint for Cloud Run"""
    return jsonify({'status': 'healthy', 'data_source': data_source_info['source']})


# Static files (for development)
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
