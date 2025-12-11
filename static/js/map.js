/**
 * Dixmont Tax Map Viewer
 * Interactive map using Leaflet.js
 */

class TaxMapViewer {
    constructor() {
        // Dixmont, Maine center coordinates
        this.defaultCenter = [44.6769, -69.1614];
        this.defaultZoom = 13;

        // Map instance
        this.map = null;

        // Layers
        this.baseLayers = {};
        this.parcelsLayer = null;
        this.highlightLayer = null;
        this.selectedFeature = null;

        // Data
        this.parcelData = null;

        // Initialize
        this.init();
    }

    init() {
        this.createMap();
        this.createBaseLayers();
        this.setupEventListeners();
        this.loadParcelData();
    }

    createMap() {
        // Create map instance
        this.map = L.map('map', {
            center: this.defaultCenter,
            zoom: this.defaultZoom,
            zoomControl: true,
            attributionControl: true
        });

        // Add attribution
        this.map.attributionControl.addAttribution(
            'Parcel Data &copy; Town of Dixmont'
        );
    }

    createBaseLayers() {
        // OpenStreetMap (Street)
        this.baseLayers.streets = L.tileLayer(
            'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
            {
                maxZoom: 19,
                attribution: '&copy; <a href="https://openstreetmap.org">OpenStreetMap</a> contributors'
            }
        );

        // ESRI Satellite
        this.baseLayers.satellite = L.tileLayer(
            'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            {
                maxZoom: 19,
                attribution: '&copy; <a href="https://www.esri.com">Esri</a>'
            }
        );

        // USGS Topographic
        this.baseLayers.topo = L.tileLayer(
            'https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}',
            {
                maxZoom: 16,
                attribution: '&copy; <a href="https://usgs.gov">USGS</a>'
            }
        );

        // Add default layer
        this.baseLayers.streets.addTo(this.map);

        // Create highlight layer for selected/search results
        this.highlightLayer = L.layerGroup().addTo(this.map);
    }

    setupEventListeners() {
        // Sidebar toggle
        const sidebarToggle = document.getElementById('sidebar-toggle');
        const sidebar = document.getElementById('sidebar');
        sidebarToggle.addEventListener('click', () => {
            sidebar.classList.toggle('collapsed');
            // Invalidate map size after sidebar animation
            setTimeout(() => this.map.invalidateSize(), 300);
        });

        // Base layer radio buttons
        document.querySelectorAll('input[name="basemap"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                this.changeBaseLayer(e.target.value);
            });
        });

        // Search
        const searchInput = document.getElementById('search-input');
        const searchBtn = document.getElementById('search-btn');

        searchBtn.addEventListener('click', () => this.performSearch());
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.performSearch();
        });

        // Debounced live search
        let searchTimeout;
        searchInput.addEventListener('input', () => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                if (searchInput.value.length >= 2) {
                    this.performSearch();
                } else {
                    this.clearSearchResults();
                }
            }, 300);
        });

        // Zoom to town button
        document.getElementById('zoom-to-town').addEventListener('click', () => {
            this.zoomToTown();
        });

        // Fullscreen toggle
        document.getElementById('fullscreen-toggle').addEventListener('click', () => {
            this.toggleFullscreen();
        });
    }

    changeBaseLayer(layerName) {
        // Remove all base layers
        Object.values(this.baseLayers).forEach(layer => {
            if (this.map.hasLayer(layer)) {
                this.map.removeLayer(layer);
            }
        });

        // Add selected layer
        if (this.baseLayers[layerName]) {
            this.baseLayers[layerName].addTo(this.map);
        }
    }

    async loadParcelData() {
        const loadingOverlay = document.getElementById('loading-overlay');
        const dataStatus = document.getElementById('data-status');

        try {
            const response = await fetch('/api/parcels');
            const data = await response.json();

            this.parcelData = data;

            if (data.features && data.features.length > 0) {
                this.renderParcels(data);
                this.updateDataStatus('loaded', `${data.features.length} parcels loaded`);

                // Fit map to parcels
                if (this.parcelsLayer) {
                    const bounds = this.parcelsLayer.getBounds();
                    if (bounds.isValid()) {
                        this.map.fitBounds(bounds, { padding: [50, 50] });
                    }
                }
            } else {
                this.updateDataStatus('loaded', 'No parcel data available');
                this.showSampleData();
            }
        } catch (error) {
            console.error('Error loading parcels:', error);
            this.updateDataStatus('error', 'Error loading parcel data');
            this.showSampleData();
        } finally {
            loadingOverlay.classList.add('hidden');
        }
    }

    showSampleData() {
        // Show a message with sample/demo data info
        const parcelDetails = document.getElementById('parcel-details');
        parcelDetails.innerHTML = `
            <div style="text-align: center; padding: 1rem;">
                <p style="color: #666; margin-bottom: 1rem;">
                    <strong>No parcel data loaded</strong>
                </p>
                <p style="font-size: 0.85rem; color: #999;">
                    To display tax map data, upload a KMZ or KML file to the
                    <code>static/data/</code> directory, or upload a pre-converted
                    <code>parcels.geojson</code> file.
                </p>
            </div>
        `;

        // Add a sample polygon to show the map works
        const sampleBounds = [
            [44.65, -69.20],
            [44.65, -69.12],
            [44.70, -69.12],
            [44.70, -69.20]
        ];

        L.rectangle(sampleBounds, {
            color: '#1a5f7a',
            weight: 2,
            fillColor: '#1a5f7a',
            fillOpacity: 0.1,
            dashArray: '5, 5'
        }).addTo(this.map)
          .bindPopup('<strong>Dixmont Town Boundary (Approximate)</strong><br>Upload parcel data to see tax map.');
    }

    renderParcels(geojson) {
        // Remove existing layer
        if (this.parcelsLayer) {
            this.map.removeLayer(this.parcelsLayer);
        }

        // Default style
        const defaultStyle = {
            color: '#3388ff',
            weight: 2,
            fillColor: '#3388ff',
            fillOpacity: 0.1
        };

        // Hover style
        const hoverStyle = {
            color: '#ff8c00',
            weight: 3,
            fillColor: '#ff8c00',
            fillOpacity: 0.3
        };

        // Selected style
        const selectedStyle = {
            color: '#ff8c00',
            weight: 3,
            fillColor: '#ff8c00',
            fillOpacity: 0.5
        };

        // Create GeoJSON layer
        this.parcelsLayer = L.geoJSON(geojson, {
            style: defaultStyle,
            onEachFeature: (feature, layer) => {
                // Hover effects
                layer.on('mouseover', () => {
                    if (layer !== this.selectedFeature) {
                        layer.setStyle(hoverStyle);
                    }
                });

                layer.on('mouseout', () => {
                    if (layer !== this.selectedFeature) {
                        layer.setStyle(defaultStyle);
                    }
                });

                // Click to select
                layer.on('click', () => {
                    this.selectParcel(feature, layer);
                });

                // Bind popup
                const popupContent = this.createPopupContent(feature.properties);
                layer.bindPopup(popupContent);
            }
        }).addTo(this.map);
    }

    createPopupContent(properties) {
        const id = properties.MapLot || properties.name || 'N/A';
        const owner = properties.Owner || 'Unknown';

        // Build address from street number and name
        let address = '';
        if (properties.Street) {
            const stNum = properties.StNumber && properties.StNumber !== '0' ? properties.StNumber + ' ' : '';
            address = stNum + properties.Street;
        }

        const acreage = properties.Acres || '';
        const landValue = properties.LandValue || '';
        const buildingValue = properties.BldgValue || '';
        const totalValue = properties.TotalValue || '';

        let html = `<div class="popup-title">Parcel ${id}</div>`;
        html += `<div class="popup-row"><span class="popup-label">Owner:</span><span class="popup-value">${owner}</span></div>`;

        if (address) {
            html += `<div class="popup-row"><span class="popup-label">Address:</span><span class="popup-value">${address}</span></div>`;
        }
        if (acreage) {
            html += `<div class="popup-row"><span class="popup-label">Acres:</span><span class="popup-value">${parseFloat(acreage).toFixed(2)}</span></div>`;
        }
        if (landValue) {
            html += `<div class="popup-row"><span class="popup-label">Land:</span><span class="popup-value">$${parseInt(landValue).toLocaleString()}</span></div>`;
        }
        if (buildingValue && buildingValue !== '0') {
            html += `<div class="popup-row"><span class="popup-label">Building:</span><span class="popup-value">$${parseInt(buildingValue).toLocaleString()}</span></div>`;
        }
        if (totalValue) {
            html += `<div class="popup-row"><span class="popup-label">Total:</span><span class="popup-value">$${parseInt(totalValue).toLocaleString()}</span></div>`;
        }

        return html;
    }

    selectParcel(feature, layer) {
        // Reset previous selection
        if (this.selectedFeature) {
            this.selectedFeature.setStyle({
                color: '#3388ff',
                weight: 2,
                fillColor: '#3388ff',
                fillOpacity: 0.1
            });
        }

        // Set new selection
        this.selectedFeature = layer;
        layer.setStyle({
            color: '#ff8c00',
            weight: 3,
            fillColor: '#ff8c00',
            fillOpacity: 0.5
        });

        // Update sidebar
        this.showParcelDetails(feature.properties);
    }

    showParcelDetails(properties) {
        const detailsContainer = document.getElementById('parcel-details');

        // Build address from street number and name
        let address = '';
        if (properties.Street) {
            const stNum = properties.StNumber && properties.StNumber !== '0' ? properties.StNumber + ' ' : '';
            address = stNum + properties.Street;
        }

        // Map property names to display labels
        const displayFields = [
            { key: ['MapLot', 'name'], label: 'Map/Lot' },
            { key: ['Owner'], label: 'Owner' },
            { key: ['Account'], label: 'Account #' },
            { key: ['_address'], label: 'Address', value: address },
            { key: ['Acres'], label: 'Acreage', format: 'acres' },
            { key: ['LandValue'], label: 'Land Value', format: 'currency' },
            { key: ['BldgValue'], label: 'Building Value', format: 'currency', skipZero: true },
            { key: ['TotalValue'], label: 'Total Value', format: 'currency' },
            { key: ['NetAssess'], label: 'Net Assessment', format: 'currency' },
            { key: ['YearBuilt'], label: 'Year Built', skipZero: true },
        ];

        let html = '';

        for (const field of displayFields) {
            // Use provided value or find from properties
            let value = field.value !== undefined ? field.value : null;

            if (value === null || value === undefined) {
                // Find first matching key
                for (const key of field.key) {
                    if (properties[key] !== undefined && properties[key] !== null && properties[key] !== '') {
                        value = properties[key];
                        break;
                    }
                }
            }

            // Skip if no value or if skipZero and value is 0
            if (value === null || value === undefined || value === '') continue;
            if (field.skipZero && (value === '0' || value === 0)) continue;

            // Format value
            if (field.format === 'currency') {
                value = '$' + parseInt(value).toLocaleString();
            } else if (field.format === 'acres') {
                value = parseFloat(value).toFixed(2) + ' acres';
            }

            html += `
                <div class="parcel-detail-row">
                    <span class="parcel-detail-label">${field.label}:</span>
                    <span class="parcel-detail-value">${value}</span>
                </div>
            `;
        }

        // If no standard fields found, show all properties
        if (html === '') {
            for (const [key, value] of Object.entries(properties)) {
                if (value !== null && value !== undefined && value !== '') {
                    html += `
                        <div class="parcel-detail-row">
                            <span class="parcel-detail-label">${key}:</span>
                            <span class="parcel-detail-value">${value}</span>
                        </div>
                    `;
                }
            }
        }

        if (html === '') {
            html = '<p class="placeholder-text">No property details available</p>';
        }

        detailsContainer.innerHTML = html;
    }

    async performSearch() {
        const query = document.getElementById('search-input').value.trim();
        const resultsContainer = document.getElementById('search-results');

        if (query.length < 2) {
            this.clearSearchResults();
            return;
        }

        try {
            const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
            const data = await response.json();

            if (data.results && data.results.length > 0) {
                this.displaySearchResults(data.results);
            } else {
                resultsContainer.innerHTML = '<p class="no-results">No parcels found</p>';
            }
        } catch (error) {
            console.error('Search error:', error);
            resultsContainer.innerHTML = '<p class="no-results">Search error occurred</p>';
        }
    }

    displaySearchResults(results) {
        const resultsContainer = document.getElementById('search-results');

        let html = '';
        for (const result of results) {
            html += `
                <div class="search-result-item" data-center="${result.center ? JSON.stringify(result.center) : ''}" data-id="${result.id}">
                    <div class="result-id">${result.id}</div>
                    <div class="result-owner">${result.owner}</div>
                    ${result.address ? `<div class="result-address">${result.address}</div>` : ''}
                </div>
            `;
        }

        resultsContainer.innerHTML = html;

        // Add click handlers
        resultsContainer.querySelectorAll('.search-result-item').forEach(item => {
            item.addEventListener('click', () => {
                const centerData = item.dataset.center;
                const id = item.dataset.id;

                if (centerData) {
                    const center = JSON.parse(centerData);
                    this.map.setView([center[1], center[0]], 17);
                }

                // Highlight the parcel
                this.highlightParcelById(id);
            });
        });
    }

    highlightParcelById(parcelId) {
        if (!this.parcelData || !this.parcelData.features) return;

        // Clear existing highlights
        this.highlightLayer.clearLayers();

        // Find the parcel
        const feature = this.parcelData.features.find(f => {
            const props = f.properties;
            return (props.MAP_LOT === parcelId ||
                    props.Map_Lot === parcelId ||
                    props.PARCEL_ID === parcelId ||
                    props.name === parcelId);
        });

        if (feature && feature.geometry) {
            const highlightStyle = {
                color: '#ffd700',
                weight: 4,
                fillColor: '#ffd700',
                fillOpacity: 0.4
            };

            const highlightLayer = L.geoJSON(feature, {
                style: highlightStyle
            }).addTo(this.highlightLayer);

            // Show details
            this.showParcelDetails(feature.properties);

            // Open popup
            highlightLayer.bindPopup(this.createPopupContent(feature.properties)).openPopup();
        }
    }

    clearSearchResults() {
        document.getElementById('search-results').innerHTML = '';
        this.highlightLayer.clearLayers();
    }

    updateDataStatus(status, message) {
        const statusContainer = document.getElementById('data-status');
        const indicator = statusContainer.querySelector('.status-indicator');
        const text = statusContainer.querySelector('.status-text');

        indicator.className = 'status-indicator ' + status;
        text.textContent = message;
    }

    zoomToTown() {
        if (this.parcelsLayer) {
            const bounds = this.parcelsLayer.getBounds();
            if (bounds.isValid()) {
                this.map.fitBounds(bounds, { padding: [50, 50] });
                return;
            }
        }
        // Default to Dixmont center
        this.map.setView(this.defaultCenter, this.defaultZoom);
    }

    toggleFullscreen() {
        const mapContainer = document.querySelector('.map-container');

        if (!document.fullscreenElement) {
            mapContainer.requestFullscreen().then(() => {
                setTimeout(() => this.map.invalidateSize(), 100);
            }).catch(err => {
                console.error('Fullscreen error:', err);
            });
        } else {
            document.exitFullscreen().then(() => {
                setTimeout(() => this.map.invalidateSize(), 100);
            });
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.taxMapViewer = new TaxMapViewer();
});
