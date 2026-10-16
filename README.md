# GEORE — Remote Sensing AI

[![CI Pipeline](https://github.com/chinmaymusale123/Geore/actions/workflows/ci.yml/badge.svg)](https://github.com/chinmaymusale123/Geore/actions/workflows/ci.yml)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-20232A?style=flat&logo=react&logoColor=61DAFB)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-646CFF?style=flat&logo=vite&logoColor=white)](https://vitejs.dev/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An agentic vision-language assistant for satellite and remote-sensing imagery analysis.  
Provides automated query routing, deterministic spectral calculations (NDVI, NDWI, change masking), Google Earth Engine satellite data fetching, and multi-modal AI reasoning (Gemini Flash with NVIDIA fallback).

---

## Key Capabilities

- **Visual Q&A (VQA):** High-level semantic questions regarding topography, land use, infrastructure, and environmental patterns.
- **Object Grounding:** Pinpoint and visualize bounding boxes around spatial features (e.g. water bodies, airstrips, deforestation patches).
- **Change Detection:** Bi-temporal pixel differencing and connected-component analysis to highlight environmental transformations over time.
- **Optical–SAR Fusion:** Complementary multi-sensor analysis fusing optical imagery with SAR (Synthetic Aperture Radar) backscatter to penetrate clouds and distinguish built-up surfaces.
- **Automated Monitoring & Alerts:** Background monitoring pipeline integrating Google Earth Engine data fetching with risk scoring and alerting.

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  React Frontend (Vite + Tailwind / Tokens)                   │
│  http://localhost:5173                                       │
│      │                                                       │
│      ▼ HTTP Multipart (POST /analyze)                        │
│  FastAPI Backend (localhost:8000)                            │
│      │                                                       │
│      ├─ router.py        (Rule-based zero-latency classifier)│
│      ├─ rs_toolkit.py    (NDVI, NDWI, Change Mask, Fusion)   │
│      ├─ data_fetcher.py  (Google Earth Engine / Fallback)    │
│      ├─ risk_engine.py   (Environmental Risk Assessment)     │
│      ├─ alert_engine.py  (Event Notification Dispatcher)     │
│      ├─ prompts.py       (Dynamic Task Prompt Construction)  │
│      └─ vlm_client.py    (Gemini 2.0 Flash / NVIDIA Fallback)│
└──────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
Geore/
├── .github/
│   └── workflows/
│       └── ci.yml               # Automated CI test pipeline
├── backend/
│   ├── tests/                   # Backend unit tests
│   │   ├── test_router.py
│   │   └── test_rs_toolkit.py
│   ├── alert_engine.py          # Alert notification logic
│   ├── data_fetcher.py          # Earth Engine satellite data ingestion
│   ├── database.py              # SQLite persistence for monitoring events
│   ├── main.py                  # FastAPI application entrypoint
│   ├── monitor.py               # Autonomous monitoring pipeline
│   ├── prompts.py               # System & VLM prompt templates
│   ├── region_config.py         # Geo-coordinates and AOI configurations
│   ├── requirements.txt         # Python dependencies
│   ├── risk_engine.py           # Anomaly and risk score calculations
│   ├── router.py                # Deterministic query routing
│   ├── rs_toolkit.py            # NumPy / OpenCV remote sensing tools
│   └── vlm_client.py            # Hosted Gemini & NVIDIA model client
├── frontend/
│   ├── src/                     # React application source code
│   ├── package.json
│   └── vite.config.js
└── README.md
```

---

## Quickstart

### 1. Backend Setup

```bash
cd backend

# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Open .env and insert your GEMINI_API_KEY (and optional NVIDIA_API_KEY)

# Launch API server
uvicorn main:app --reload --port 8000
```

Health check: `curl http://localhost:8000/health`

### 2. Frontend Setup

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

Navigate to `http://localhost:5173` in your browser.

---

## Running Tests

GEORE includes a dedicated unit test suite for the deterministic remote-sensing toolkit and query classifier:

```bash
# Run all backend unit tests
python -m unittest discover -s backend/tests -p "test_*.py" -v
```

Tests run automatically on every push via the GitHub Actions CI pipeline.

---

## API Reference

### `GET /health`
Returns server status:
```json
{"status": "ok"}
```

### `POST /analyze`
Multipart form data request:
- `image1` (file, required): Primary satellite image (PNG/JPEG/TIFF).
- `image2` (file, optional): Secondary image for change detection or SAR.
- `query` (text, required): Analysis prompt or question.
- `has_sar` (bool, optional): Set to `true` if second image is SAR.

Returns:
```json
{
  "task": "change",
  "answer": "Significant vegetation loss detected in the northwest sector...",
  "bbox": null,
  "confidence": "high",
  "execution_trace": [...]
}
```

---

## License

Distributed under the MIT License.
