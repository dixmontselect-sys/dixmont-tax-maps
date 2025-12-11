# Future Tax Map Features - Dixmont, Maine

## Overview
This document outlines planned improvements and feature enhancements for the Dixmont Tax Map application. The goal is to create a comprehensive, automated, and user-friendly property information system.

---

## Current State (Implemented)

### Interactive Map Viewer
- Leaflet-based interactive map with parcel boundaries
- Search by owner name, Map/Lot, or address
- Click-to-view parcel details (owner, acreage, assessed values)
- Multiple base map options (Street, Satellite, Topographic)
- Remote KMZ data loading from Maine GeoLibrary
- Legal disclaimer modal

### PDF Tax Maps (New)
- Three-tab interface: Interactive Map, PDF Tax Maps, Commitment Books
- All 12 tax map sheets available for viewing/download
- Index map for reference
- In-browser PDF viewer modal

### Commitment Books (New)
- Real Estate Tax Commitment (Alphabetical)
- Real Estate Tax Commitment (By Map/Lot)
- Personal Property Tax Commitment
- Tree Growth Program listings

---

## Phase 1: Quick Wins (Low Effort, High Impact)

### 1.1 Direct PDF Linking from Assessor
**Status:** Ready to implement

Instead of hosting PDF copies locally, link directly to the assessor's hosted PDFs on maineassessment.com. This:
- Reduces storage requirements
- Ensures users always see the latest documents
- Eliminates manual update process

**Implementation:**
```javascript
// Replace local PDF paths with assessor URLs
const assessorBaseUrl = 'https://www.maineassessment.com/dixmont';
// Fetch PDF list from assessor page or maintain a mapping
```

### 1.2 Last Updated Indicator
Display when tax data was last updated, helping users understand data freshness.

### 1.3 Print Functionality
Add dedicated print button for parcel details with formatted output suitable for official records.

---

## Phase 2: Automation & Synchronization

### 2.1 Automated PDF Update Checker
**Priority:** High

Create a scheduled job that:
1. Checks the assessor's website for updated PDFs
2. Compares file hashes or modification dates
3. Alerts administrators when updates are available
4. Optionally auto-syncs to Cloud Storage backup

**Architecture:**
```
┌─────────────────────┐
│  Cloud Scheduler    │──────▶ Trigger weekly
└─────────────────────┘
           │
           ▼
┌─────────────────────┐
│  Cloud Function     │──────▶ Check assessor site
│  (PDF Checker)      │
└─────────────────────┘
           │
           ▼
┌─────────────────────┐
│  Cloud Storage      │──────▶ Backup PDFs
│  (PDF Archive)      │
└─────────────────────┘
           │
           ▼
┌─────────────────────┐
│  Notification       │──────▶ Email/Slack alert
│  (Optional)         │
└─────────────────────┘
```

**Python Implementation Sketch:**
```python
import requests
from google.cloud import storage
import hashlib

def check_for_updates(request):
    assessor_pdfs = [
        'https://www.maineassessment.com/dixmont/commitment.pdf',
        # ... other PDF URLs
    ]

    storage_client = storage.Client()
    bucket = storage_client.bucket('dixmont-tax-pdfs')

    updates_found = []
    for pdf_url in assessor_pdfs:
        # Fetch current PDF
        response = requests.get(pdf_url)
        current_hash = hashlib.md5(response.content).hexdigest()

        # Compare with stored hash
        blob = bucket.blob(f'hashes/{pdf_name}.md5')
        if blob.exists():
            stored_hash = blob.download_as_string().decode()
            if current_hash != stored_hash:
                updates_found.append(pdf_name)
                # Backup new version
                bucket.blob(f'pdfs/{pdf_name}').upload_from_string(response.content)
                blob.upload_from_string(current_hash)

    return {'updates': updates_found}
```

### 2.2 Cloud Storage Backup System
**Priority:** High

Maintain versioned backups of all PDFs in Google Cloud Storage:
- Automatic backup when updates detected
- Version history for rollback capability
- Fallback serving if assessor site is unavailable

**Bucket Structure:**
```
gs://dixmont-tax-pdfs/
├── current/
│   ├── index.pdf
│   ├── map_1.pdf
│   └── ...
├── archive/
│   └── 2024-12-01/
│       ├── index.pdf
│       └── ...
└── hashes/
    ├── index.pdf.md5
    └── ...
```

---

## Phase 3: Data Integration & Intelligence

### 3.1 Commitment Book ↔ Tax Map Integration
**Priority:** Medium-High

Allow users to click a property in the commitment book PDF and jump to that parcel on the interactive map.

**Approach 1: Text Extraction (Recommended)**
1. Extract text from commitment book PDFs using Python (PyPDF2/pdfplumber)
2. Parse owner names, Map/Lot numbers, addresses
3. Store in searchable database
4. Create links between commitment entries and map parcels

**Approach 2: PDF Annotation**
1. Pre-process PDFs to add hyperlinks
2. Links open interactive map centered on parcel

**Database Schema:**
```sql
CREATE TABLE commitment_entries (
    id SERIAL PRIMARY KEY,
    owner_name VARCHAR(255),
    map_lot VARCHAR(50),
    address VARCHAR(255),
    land_value DECIMAL(12,2),
    building_value DECIMAL(12,2),
    total_value DECIMAL(12,2),
    tax_amount DECIMAL(10,2),
    geojson_feature_id VARCHAR(50)  -- Link to parcel geometry
);
```

### 3.2 Unified Search
Search across ALL data sources:
- Interactive map parcels
- Commitment book entries
- Tree growth listings
- Personal property records

**Implementation:**
```javascript
async function unifiedSearch(query) {
    const [mapResults, commitmentResults, treeGrowthResults] = await Promise.all([
        searchMapParcels(query),
        searchCommitmentBook(query),
        searchTreeGrowth(query)
    ]);

    return {
        parcels: mapResults,
        commitments: commitmentResults,
        treeGrowth: treeGrowthResults
    };
}
```

### 3.3 Property History View
Display assessment history over time for any parcel:
- Value changes year over year
- Ownership changes
- Tax rate history

---

## Phase 4: Advanced Features

### 4.1 AI-Powered Data Extraction
Use AI (Claude API or similar) to:
- Extract structured data from unstructured PDFs
- Auto-categorize property types
- Identify data inconsistencies
- Generate property summaries

**Use Case Example:**
```
User clicks on parcel → AI summarizes:
"This 25-acre residential property owned by John Smith has been
in the Tree Growth program since 2018. Land value increased 12%
since last assessment. Current tax: $2,450/year."
```

### 4.2 Parcel Comparison Tool
Allow users to compare multiple parcels:
- Side-by-side value comparisons
- Acreage comparison
- Tax burden comparison
- Neighborhood analysis

### 4.3 Export & Reports
Generate downloadable reports:
- Individual parcel reports (PDF)
- Area summaries
- Custom filtered lists
- CSV/Excel exports for analysis

### 4.4 Public Notification System
Allow residents to subscribe to:
- Updates affecting their property
- Town-wide assessment changes
- Meeting notifications related to property taxes

---

## Phase 5: Administrative Tools

### 5.1 Admin Dashboard
Web interface for town administrators to:
- Trigger manual data refreshes
- View sync status/history
- Manage PDF sources
- Review data quality reports

### 5.2 Wagtail CMS Integration
Enable content editors to:
- Update tax map page content without code changes
- Manage displayed documents
- Configure data sources
- View usage analytics

### 5.3 Data Quality Monitoring
Automated checks for:
- Missing parcel data
- Inconsistencies between map and commitment book
- Broken PDF links
- Stale data alerts

---

## Technical Recommendations

### Architecture
```
┌────────────────────────────────────────────────────────────────┐
│                         Cloud Run                               │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │  Tax Map App     │  │  Wagtail CMS     │                    │
│  │  (Flask)         │  │  (Django)        │                    │
│  └────────┬─────────┘  └────────┬─────────┘                    │
└───────────┼─────────────────────┼──────────────────────────────┘
            │                     │
            ▼                     ▼
┌───────────────────────┐  ┌────────────────────┐
│  Cloud Storage        │  │  Neon PostgreSQL   │
│  - PDF Archive        │  │  - Wagtail DB      │
│  - GeoJSON Cache      │  │  - Commitment Data │
└───────────────────────┘  └────────────────────┘
            │
            ▼
┌───────────────────────┐
│  External Sources     │
│  - Maine GeoLibrary   │
│  - maineassessment.com│
└───────────────────────┘
```

### Technology Stack
- **Frontend:** Vanilla JS + Leaflet (keep lightweight)
- **Backend:** Flask (current) or migrate to FastAPI
- **Database:** Neon PostgreSQL (shared with Wagtail)
- **Storage:** Google Cloud Storage
- **Scheduling:** Cloud Scheduler + Cloud Functions
- **PDF Processing:** PyPDF2, pdfplumber, or pdf.js

### Performance Targets
- Initial page load: < 2 seconds
- Interactive map ready: < 3 seconds
- Search results: < 500ms
- PDF viewer load: < 1 second

---

## Implementation Priority Matrix

| Feature | Effort | Impact | Priority |
|---------|--------|--------|----------|
| Direct PDF linking | Low | High | P1 |
| Cloud Storage backup | Medium | High | P1 |
| Auto update checker | Medium | High | P1 |
| Unified search | Medium | High | P2 |
| Commitment integration | High | High | P2 |
| AI data extraction | High | Medium | P3 |
| Admin dashboard | Medium | Medium | P3 |
| Property comparison | Medium | Low | P4 |
| Notification system | High | Low | P4 |

---

## Next Steps

1. **Immediate:** Deploy current tabbed interface with local PDFs
2. **Week 1:** Set up Cloud Storage bucket for PDF backup
3. **Week 2:** Implement automated update checker
4. **Week 3:** Extract commitment book data to database
5. **Week 4:** Add unified search functionality

---

## Questions to Resolve

1. Does the assessor (Maine Assessment) provide an API or structured data feed?
2. How often does the assessor update their data? (Annually? Quarterly?)
3. Is there interest in resident notification features?
4. What administrative access do town staff need?
5. Budget for Cloud Storage and Cloud Functions?

---

*Document created: December 2024*
*Last updated: December 2024*
