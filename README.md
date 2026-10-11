# Geospatial File Measurement API

[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111%2B-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%2B-D71F00.svg)](https://www.sqlalchemy.org/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED.svg?logo=docker)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A production-grade REST API backend built with **FastAPI**, **GeoPandas**, **PyProj**, and **PostgreSQL** that ingests vector geospatial files (**OGC KML 2.2** and **ESRI Shapefile ZIP archives**), extracts individual vector features, reprojects coordinates from geographic CRS to optimal local projected metric coordinate systems, calculates planar geometric measurements (Polygon area in $\text{m}^2$, LineString length in $\text{m}$, Point passthrough), and persists results with pagination and filtering.

Engineered for the **AEREO Software Development Intern** technical assessment.

---

## Table of Contents

1. [Architectural Overview](#architectural-overview)
2. [Key Capabilities & Innovations](#key-capabilities--innovations)
3. [Geospatial & CRS Reprojection Strategy](#geospatial--crs-reprojection-strategy)
4. [Data Storage & Relational Design](#data-storage--relational-design)
5. [Project Layout](#project-layout)
6. [Prerequisites & System Dependencies](#prerequisites--system-dependencies)
7. [Local Development Setup](#local-development-setup)
8. [Docker & Containerized Deployment](#docker--containerized-deployment)
9. [API Reference & Endpoint Guide](#api-reference--endpoint-guide)
10. [Error Handling & Security Hardening](#error-handling--security-hardening)
11. [Testing & Quality Assurance](#testing--quality-assurance)
12. [Architectural Decisions & Trade-offs](#architectural-decisions--trade-offs)
13. [Scalability Roadmap](#scalability-roadmap)

---

## Architectural Overview

The application follows **Clean Architecture** principles and the **Repository Pattern** to ensure separation of concerns, testability, and enterprise maintainability:

```
[ Client Request: Multipart File Upload ]
                   │
                   ▼
       [ FastAPI Route Handlers ]
     (Upload / Metadata / Measurements)
                   │
         Validate & Sandbox
                   │
                   ▼
     [ File Processing Service ]
                   │
     ┌─────────────┴─────────────┐
     ▼                           ▼
[ Vector Ingestion ]    [ CRS Reprojection Service ]
(KML & Shapefile ZIP)   (Centroid → UTM/UPS Selection)
     │                           │
     └─────────────┬─────────────┘
                   ▼
        [ Measurement Engine ]
     (Polygon Area m² / Line Length m)
                   │
                   ▼
       [ Repository Layer ]
   (File & Feature Persistence)
                   │
                   ▼
   [ PostgreSQL / SQLite Relational DB ]
```

- **API Layer (`app/api`):** Exposes typed OpenAPI-documented endpoints with Pydantic v2 schemas.
- **Service Layer (`app/services`):** Encapsulates core domain logic: vector parsing, CRS resolution, and measurement calculation.
- **Repository Layer (`app/repositories`):** Abstract data-access interface decoupling business logic from ORM queries.
- **Storage Layer (`app/db`):** SQLAlchemy 2.0 models with Alembic schema migrations.
- **Utilities (`app/utils`):** High-security file validation, Zip Slip prevention, and temporary directory sandboxing.

---

## Key Capabilities & Innovations

- **Multi-Format Vector Support:** Parses standard OGC KML (`.kml`) and multi-file ESRI Shapefile archives (`.zip` with `.shp`, `.shx`, `.dbf`, `.prj`).
- **Dynamic Projected CRS Reprojection:** Solves the core GIS pitfall where distance/area measured in geographic degrees ($\text{deg}^2$) produces invalid numbers. Features are reprojected to the optimal local metric UTM or UPS projection.
- **Per-Feature Fault Tolerance:** Ingests heterogeneous datasets without pipeline crashes. Unsupported geometries (e.g., `GeometryCollection`) or invalid self-intersecting geometries are isolated, and the job transitions to `PARTIAL` rather than failing entirely.
- **Sanitized JSON Properties:** Complex GIS attribute tables containing NumPy types, NaN, or non-serializable objects are sanitized to native JSON primitives.
- **Zero Heavyweight C-Extension DB Dependency:** Eliminates complex PostGIS binary installations on client systems while delivering full spatial metric measurement capabilities through GeoPandas/PyProj.
- **Enterprise Security Hardening:** Zip Slip protection, UUID filesystem isolation, security response headers (`nosniff`, `DENY`), and 25 MB file size caps.

---

## Geospatial & CRS Reprojection Strategy

### The Core Problem: Why Geographic CRS Cannot Be Measured Directly
Coordinates in standard GPS/KML are expressed in **EPSG:4326 (WGS 84)** using latitude and longitude in decimal degrees. 
1. **Latitude/Longitude are angles, not distances:** One degree of longitude spans approximately $111\,\text{km}$ at the Equator, but shrinks to $0\,\text{km}$ at the poles:
   $$\Delta x = 111.320 \times \cos(\text{latitude})\,\text{km}$$
2. Calculating Euclidean distance or Shoelace polygon area directly on degree coordinates yields numbers in square degrees ($\text{deg}^2$), which are physically meaningless for land surveys or drone flights.

### The Solution: Dynamic Local Projected CRS Derivation
Our `CRSService` ([app/services/crs_service.py](file:///d:/AEREO%20Geospatial%20API/app/services/crs_service.py)) inspects the source dataset and calculates the centroid coordinates $(\text{lon}_{\text{c}}, \text{lat}_{\text{c}})$:

1. **Polar Regions (UPS):**
   - If $\text{lat}_{\text{c}} > 84^\circ\text{N}$, reproject to **Universal Polar Stereographic (UPS) North** (`EPSG:32661`).
   - If $\text{lat}_{\text{c}} < -80^\circ\text{S}$, reproject to **Universal Polar Stereographic (UPS) South** (`EPSG:32761`).
2. **Global UTM Zone Determination:**
   - Longitude is normalized to $[-180, 180]$.
   - The standard 6-degree UTM zone is calculated via:
     $$\text{zone} = \lfloor(\text{lon}_{\text{c}} + 180) / 6\rfloor + 1$$
   - Hemisphere assignment:
     - **Northern Hemisphere ($\text{lat} \ge 0$):** $\text{EPSG} = 32600 + \text{zone}$ (e.g., Bangalore at $77.59^\circ\text{E}, 12.97^\circ\text{N} \to \text{EPSG:32643}$).
     - **Southern Hemisphere ($\text{lat} < 0$):** $\text{EPSG} = 32700 + \text{zone}$.
3. **Planar Transformation:**
   Geometries are reprojected using PyProj coordinate transformation pipelines into conformal metric Cartesian coordinates $(x, y)$ in meters.
4. **Measurement Computation:**
   - **Polygon / MultiPolygon:** Area computed in square meters ($\text{m}^2$) via Shapely planar 2D Cartesian integration, accounting for exterior rings and interior holes (donut polygons).
   - **LineString / MultiLineString:** Length computed in meters ($\text{m}$).
   - **Point / MultiPoint:** Passed through with `null` measurement as per specification.

---

## Data Storage & Relational Design

The database schema utilizes standard relational tables with `sa.JSON` for GeoJSON geometry persistence, ensuring 100% compatibility across **PostgreSQL 16** (production) and **SQLite in-memory** (test suite).

```
 ┌─────────────────────────────────────────┐
 │                  files                  │
 ├─────────────────────────────────────────┤
 │ id: UUID (PK)                           │
 │ original_filename: VARCHAR(255)         │
 │ stored_filename: VARCHAR(255) (UNIQUE)  │
 │ file_type: VARCHAR(32)                  │
 │ file_size_bytes: BIGINT                 │
 │ status: VARCHAR(32)                     │
 │ crs: VARCHAR(64)                        │
 │ total_features: INTEGER                 │
 │ successful_measurements: INTEGER        │
 │ failed_measurements: INTEGER            │
 │ unsupported_features: INTEGER           │
 │ error_message: TEXT                     │
 │ created_at: TIMESTAMPTZ                 │
 │ updated_at: TIMESTAMPTZ                 │
 └────────────────────┬────────────────────┘
                      │ 1
                      │
                      │ has many (CASCADE DELETE)
                      │
                      ▼ *
 ┌─────────────────────────────────────────┐
 │                features                 │
 ├─────────────────────────────────────────┤
 │ id: UUID (PK)                           │
 │ file_id: UUID (FK -> files.id)          │
 │ feature_index: INTEGER                  │
 │ geometry_type: VARCHAR(64)              │
 │ geometry_geojson: JSON                  │
 │ properties: JSON                        │
 │ measurement_type: VARCHAR(32)           │
 │ measurement_value: DOUBLE PRECISION     │
 │ measurement_unit: VARCHAR(16)           │
 │ status: VARCHAR(32)                     │
 │ error_message: TEXT                     │
 │ created_at: TIMESTAMPTZ                 │
 ├─────────────────────────────────────────┤
 │ UNIQUE (file_id, feature_index)         │
 └─────────────────────────────────────────┘
```

---

## Project Layout

```
.
├── alembic/                      # Database migration scripts
│   ├── env.py
│   └── versions/
│       └── 0001_initial_schema.py
├── app/
│   ├── api/
│   │   └── routes/
│   │       ├── files.py          # File upload, metadata, and measurement endpoints
│   │       └── health.py         # Service health check endpoint
│   ├── core/
│   │   ├── config.py             # Pydantic Settings configuration
│   │   ├── exceptions.py         # Custom application exception hierarchy
│   │   └── logging.py            # Structured logging configuration
│   ├── db/
│   │   ├── database.py           # SQLAlchemy database session & engine
│   │   └── models.py             # Relational ORM models (FileModel, FeatureModel)
│   ├── repositories/
│   │   └── file_repository.py    # Encapsulated database operations
│   ├── schemas/
│   │   ├── feature.py            # Feature extraction schemas
│   │   ├── file.py               # File metadata response schemas
│   │   └── measurement.py        # Measurement response & pagination schemas
│   ├── services/
│   │   ├── crs_service.py        # CRS detection & UTM reprojection engine
│   │   ├── file_service.py       # Orchestration pipeline
│   │   ├── geospatial_service.py # Vector parsing (KML & Shapefile)
│   │   └── measurement_service.py# Planar metric measurement engine
│   ├── utils/
│   │   ├── archive_utils.py      # Zip Slip defense & shapefile component validator
│   │   └── file_validation.py    # File size, extension, and safe UUID naming
│   └── main.py                   # FastAPI application factory & security middleware
├── tests/
│   ├── fixtures/
│   │   └── synthetic_geometries.py # Generator for synthetic KML and Shapefile fixtures
│   ├── integration/
│   │   ├── test_api_files.py
│   │   ├── test_api_measurements.py
│   │   ├── test_end_to_end_flow.py # End-to-end client journeys
│   │   └── test_pipeline_persistence.py
│   └── unit/
│       ├── test_archive_utils.py
│       ├── test_crs_service.py
│       ├── test_feature_extraction.py
│       ├── test_file_validation.py
│       ├── test_measurement_service.py
│       └── test_security_hardening.py
├── uploads/                      # Isolated internal file upload repository
├── .dockerignore
├── .env.example
├── Dockerfile                    # Production multi-stage container build
├── docker-compose.yml            # Full-stack composition (API + PostgreSQL)
├── docker-entrypoint.sh          # Auto-migration & server launch script
├── pytest.ini                    # Pytest test suite configuration
├── requirements.txt              # Production Python dependencies
└── requirements-dev.txt          # Testing & development dependencies
```

---

## Prerequisites & System Dependencies

- **Python:** 3.11+
- **PostgreSQL:** 15+ (or run via Docker)
- **GDAL & GEOS Libraries:** Required by GeoPandas / Pyogrio
  - **Debian / Ubuntu:** `sudo apt-get install -y gdal-bin libgdal-dev libgeos-dev libproj-dev`
  - **macOS:** `brew install gdal geos proj`
  - **Windows:** Wheel binaries installed automatically through Pyogrio and Shapely

---

## Local Development Setup

### 1. Clone & Setup Virtual Environment
```bash
git clone https://github.com/Immanuelj15/Geospatial-File-Measurement-API.git
cd Geospatial-File-Measurement-API

python -m venv .venv
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Linux / macOS:
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 3. Environment Configuration
Create a local `.env` configuration from the provided template:
```bash
cp .env.example .env
```
Ensure your `.env` contains valid connection credentials:
```env
PROJECT_NAME="Geospatial File Measurement API"
ENVIRONMENT="development"
DEBUG=true
DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5432/geospatial_db"
UPLOAD_DIR="uploads"
MAX_UPLOAD_SIZE_BYTES=26214400
LOG_LEVEL="INFO"
```

### 4. Database Schema Migration
Run Alembic migrations to construct the database schema:
```bash
alembic upgrade head
```

### 5. Launch the Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
The server will be accessible at `http://localhost:8000`.

---

## Docker & Containerized Deployment

Run the complete multi-container production stack (PostgreSQL + FastAPI + Automatic Migrations) with a single command:

```bash
docker compose up --build -d
```

### Verification & Logs:
```bash
# Verify container health
docker compose ps

# View application logs
docker compose logs -f api

# Tear down stack
docker compose down -v
```

---

## API Reference & Endpoint Guide

Interactive Swagger documentation is available at **`http://localhost:8000/docs`** and ReDoc at **`http://localhost:8000/redoc`**.

### 1. Service Health Check
```http
GET /health
```
**Response (200 OK):**
```json
{
  "status": "healthy",
  "project": "Geospatial File Measurement API",
  "environment": "production"
}
```

---

### 2. Upload & Ingest Geospatial File
```http
POST /api/files/
Content-Type: multipart/form-data
```
Accepts `.kml` vector files or `.zip` archives containing an ESRI Shapefile (`.shp`, `.shx`, `.dbf`).

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/files/" \
     -H "accept: application/json" \
     -F "file=@survey.kml;type=application/vnd.google-earth.kml+xml"
```

**Response (201 Created):**
```json
{
  "id": "e305e9ea-1c25-4c07-ba71-1250262145b2",
  "filename": "survey.kml",
  "file_type": "kml",
  "file_size_bytes": 1420,
  "status": "COMPLETED",
  "crs": "EPSG:32643",
  "feature_count": 3,
  "successful_measurements": 3,
  "failed_measurements": 0,
  "unsupported_features": 0,
  "error_message": null,
  "created_at": "2026-10-11T22:30:00.000000Z",
  "updated_at": "2026-10-11T22:30:01.000000Z"
}
```

---

### 3. Retrieve File Metadata & Status
```http
GET /api/files/{id}/
```

**cURL Example:**
```bash
curl -X GET "http://localhost:8000/api/files/e305e9ea-1c25-4c07-ba71-1250262145b2/" \
     -H "accept: application/json"
```

**Response (200 OK):**
```json
{
  "id": "e305e9ea-1c25-4c07-ba71-1250262145b2",
  "filename": "survey.kml",
  "file_type": "kml",
  "file_size_bytes": 1420,
  "status": "COMPLETED",
  "crs": "EPSG:32643",
  "feature_count": 3,
  "successful_measurements": 3,
  "failed_measurements": 0,
  "unsupported_features": 0,
  "error_message": null,
  "created_at": "2026-10-11T22:30:00.000000Z",
  "updated_at": "2026-10-11T22:30:01.000000Z"
}
```

---

### 4. Retrieve Paginated Feature Measurements
```http
GET /api/files/{id}/measurements/?offset=0&limit=100&status=SUCCESS
```

| Query Parameter | Type | Default | Description |
|---|---|---|---|
| `offset` | integer | `0` | Number of items to skip ($\ge 0$). |
| `limit` | integer | `100` | Max records to return ($1 \le \text{limit} \le 500$). |
| `status` | string | `null` | Filter by status (`SUCCESS`, `FAILED`, `UNSUPPORTED`). |

**cURL Example:**
```bash
curl -X GET "http://localhost:8000/api/files/e305e9ea-1c25-4c07-ba71-1250262145b2/measurements/?limit=2" \
     -H "accept: application/json"
```

**Response (200 OK):**
```json
{
  "file_id": "e305e9ea-1c25-4c07-ba71-1250262145b2",
  "total": 3,
  "offset": 0,
  "limit": 2,
  "items": [
    {
      "id": "b1fa6770-36b0-4592-80ff-4f4044be2587",
      "feature_id": 0,
      "geometry_type": "Polygon",
      "measurement_type": "area",
      "measurement_value": 308945.12,
      "unit": "m2",
      "status": "SUCCESS",
      "error": null,
      "properties": {
        "name": "Field Parcel Alpha",
        "crop_type": "Wheat"
      },
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [
            [77.5900, 12.9700],
            [77.5950, 12.9700],
            [77.5950, 12.9750],
            [77.5900, 12.9750],
            [77.5900, 12.9700]
          ]
        ]
      }
    },
    {
      "id": "c2ea8881-47c1-4603-91ee-5f5155cf3698",
      "feature_id": 1,
      "geometry_type": "LineString",
      "measurement_type": "length",
      "measurement_value": 782.45,
      "unit": "m",
      "status": "SUCCESS",
      "error": null,
      "properties": {
        "name": "Access Road 1"
      },
      "geometry": {
        "type": "LineString",
        "coordinates": [
          [77.5946, 12.9716],
          [77.5956, 12.9726],
          [77.5966, 12.9736]
        ]
      }
    }
  ]
}
```

---

## Error Handling & Security Hardening

### Standardized Error Envelope
All error responses adhere to a unified JSON structure:
```json
{
  "error": "ErrorType",
  "message": "Human-readable description.",
  "details": {}
}
```

### Security Defenses
- **Zip Slip Defense:** Every archive member's path is normalized and verified to prevent relative directory escapes (`../`).
- **Filesystem Isolation:** Uploaded files are immediately renamed to UUIDs (`{uuid}.kml`, `{uuid}.zip`), neutralizing path injection attacks.
- **Strict Size Limits:** Rejects payloads over 25 MB and 0-byte uploads with HTTP 400.
- **Security Response Headers:** Emits `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block`, and `Referrer-Policy: strict-origin-when-cross-origin`.
- **Automatic Sandboxing & Cleanup:** Shapefiles are extracted into isolated temporary directories that are guaranteed to be cleaned up via Python context managers.

---

## Testing & Quality Assurance

The test suite covers unit logic, coordinate edge cases, archive nesting, adversarial attacks, and end-to-end client workflows with **87 passing automated tests**.

```bash
# Run complete test suite
pytest -v

# Run with coverage report
pytest --cov=app --cov-report=term-missing

# Run code style & formatting checks
ruff check .
```

### Test Suite Structure:
- `tests/unit/test_crs_service.py`: Centroid calculation, UTM zones, polar UPS thresholds, antimeridian date-line wrap.
- `tests/unit/test_measurement_service.py`: Polygon area ($\text{m}^2$), donut polygon interior rings, LineString length ($\text{m}$), 3D Z-coordinates, invalid geometry resilience.
- `tests/unit/test_archive_utils.py`: Recursive nested archives, Zip Slip detection, shapefile companion validation.
- `tests/unit/test_security_hardening.py`: HTTP security headers, 400/404/422/405 error envelopes, temp directory leaks.
- `tests/integration/test_end_to_end_flow.py`: Complete user journeys for KML, Shapefiles, partial datasets, and corrupt files.

---

## Architectural Decisions & Trade-offs

| Decision | Selected Approach | Rationale | Alternatives Evaluated |
|---|---|---|---|
| **Projection Engine** | Application Layer via GeoPandas & PyProj | Enables instant in-memory testing on SQLite, eliminates heavy binary C-extensions on PostgreSQL, and executes high-performance vectorized operations. | PostGIS extension `ST_Transform` & `ST_Area` |
| **Pipeline Architecture** | In-Process Synchronous with Status Tracking | Predictable lifecycle for immediate interview verification and zero extra infrastructure requirements. | Asynchronous Celery + Redis workers |
| **Vector Driver** | Pyogrio (GDAL-based) | High-speed C-level vector parsing, 5-10x faster than pure Python Fiona, natively bundled with modern GeoPandas. | Pure Python XML parsing / PyShp |
| **Geometry Persistence** | Standard JSON / GeoJSON | Fully cross-compatible between PostgreSQL and SQLite; frontends consume standard GeoJSON directly without backend conversion. | WKB / WKT binary storage |

---

## Scalability Roadmap

For high-scale enterprise deployments handling gigabyte-scale datasets:
1. **Background Job Queue:** Delegate `FileProcessingService` execution to **Celery** or **Temporal** workers backed by Redis/RabbitMQ.
2. **Cloud Object Storage:** Decouple filesystem storage by integrating AWS S3 / Google Cloud Storage with presigned upload URLs.
3. **Raster & 3D Surface Analysis:** Extend measurement engine to ingest GeoTIFF DEMs (Digital Elevation Models) for slope-adjusted true 3D surface area calculations.
4. **Webhooks & Event Stream:** Notify external consumer applications upon job completion via Webhooks or Kafka event streams.
