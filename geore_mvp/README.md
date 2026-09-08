# GEORE — Remote Sensing AI

Agentic vision-language assistant for satellite imagery analysis.  
Supports **Visual Q&A**, **Grounding**, **Change Detection**, and **Optical–SAR Fusion**.

## Architecture

```
┌─────────────────────────────────────────────┐
│  React frontend (Vite)                      │
│  localhost:5173                              │
│      │                                      │
│      ▼ POST /analyze                        │
│  FastAPI backend                            │
│  localhost:8000                              │
│      │                                      │
│      ├─ router.py      (classify query)     │
│      ├─ rs_toolkit.py  (NDVI, change, etc.) │
│      ├─ prompts.py     (build prompt)       │
│      └─ vlm_client.py  (Gemini / NVIDIA)    │
└─────────────────────────────────────────────┘
```

## Setup

### 1. Backend

```bash
cd geore_mvp/backend

# Create and populate .env with your API keys
cp .env.example .env
# Edit .env — add GEMINI_API_KEY (required), NVIDIA_API_KEY (optional fallback)

pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Health check: `curl http://localhost:8000/health`

### 2. Frontend (separate terminal)

```bash
cd geore_mvp/frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.

## Usage

1. Upload a satellite image (PNG, JPEG, or GeoTIFF)
2. Optionally upload a second image for change detection or fusion
3. Type a query and click **Run analysis**

| Task | Input | Example query |
|------|-------|---------------|
| Visual Q&A | 1 image + question | "What type of land use is shown?" |
| Grounding | 1 image + spatial query | "Highlight the water body" |
| Change Detection | 2 images + temporal query | "What changed between these images?" |
| Optical–SAR Fusion | 2 images (SAR checked) | "Analyze the land cover" |

## API

### `GET /health`
Returns `{"status": "ok"}`.

### `POST /analyze`
Multipart form:
- `image1` — file (required)
- `image2` — file (optional)
- `query` — string (required)
- `has_sar` — boolean (optional, default `false`)

Returns JSON with `answer`, `task`, `bbox`, `confidence`, `execution_trace`.

## Legacy Streamlit UI

The original `app.py` (Streamlit) is still present at the repo root as a fallback:

```bash
cd geore_mvp
streamlit run app.py
```
