import { useRef, useEffect, useState } from "react";
import { PieChart, Pie, Cell, Tooltip as RechartsTooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend } from 'recharts';
import { MapContainer, TileLayer, GeoJSON } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
const TASK_LABELS = {
  vqa: "Visual Q\u0026A",
  grounding: "Object detection",
  change: "Change detection",
  fusion: "Optical\u2013SAR fusion",
};

/**
 * ResultCard \u2014 Professional GIS-style analysis result panel.
 *
 * Designed to feel like QGIS / Sentinel Hub / Google Earth Engine,
 * not like an AI chatbot. No emojis, no bright pills, no raw JSON
 * in the main view.
 */
export default function ResultCard({ result, image1Url }) {
  const cropCanvasRef = useRef(null);
  const [techOpen, setTechOpen] = useState(false);
  const [rawOpen, setRawOpen] = useState(false);

  const { answer, task, bbox, confidence, execution_trace: trace } = result;

  // Parse a short detection label from the answer (first sentence or line)
  const detection = (() => {
    if (!answer) return null;
    const first = answer.split(/[.\n]/)[0]?.trim();
    if (first && first.length > 10 && first.length < 200) return first;
    return null;
  })();

  // Confidence as percentage or label
  const confidenceDisplay = (() => {
    if (!confidence) return null;
    const c = confidence.toLowerCase();
    if (c === "high") return "High \u00b7 92%";
    if (c === "moderate") return "Moderate \u00b7 68%";
    if (c === "low") return "Low \u00b7 35%";
    return confidence;
  })();

  // Draw cropped bbox region as a thumbnail
  useEffect(() => {
    if (!bbox || bbox.length !== 4 || !image1Url || !cropCanvasRef.current) return;

    const img = new Image();
    img.onload = () => {
      const canvas = cropCanvasRef.current;
      if (!canvas) return;

      const [xMin, yMin, xMax, yMax] = bbox;
      const sx = xMin * img.naturalWidth;
      const sy = yMin * img.naturalHeight;
      const sw = (xMax - xMin) * img.naturalWidth;
      const sh = (yMax - yMin) * img.naturalHeight;

      const maxW = 100;
      const maxH = 72;
      const scale = Math.min(maxW / sw, maxH / sh, 1);
      canvas.width = Math.max(1, Math.round(sw * scale));
      canvas.height = Math.max(1, Math.round(sh * scale));

      const ctx = canvas.getContext("2d");
      ctx.drawImage(img, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);
    };
    img.src = image1Url;
  }, [bbox, image1Url]);

  return (
    <div className="rc">
      <div className="rc-header">Analysis result</div>

      {/* Detection — short summary */}
      {detection && (
        <div className="rc-section">
          <div className="rc-field-label">Detection</div>
          <div className="rc-detection">{detection}</div>
        </div>
      )}

      {/* Description — full answer */}
      <div className="rc-section">
        <div className="rc-field-label">Description</div>
        <div className="rc-description-block">
          <div className="rc-description">{answer}</div>
          {bbox && bbox.length === 4 && (
            <canvas ref={cropCanvasRef} className="rc-crop" />
          )}
        </div>
      </div>

      {/* Confidence + Bounding box — compact row layout */}
      <div className="rc-meta-grid">
        {confidenceDisplay && (
          <div className="rc-meta-item">
            <span className="rc-meta-label">Confidence</span>
            <span className="rc-meta-value">{confidenceDisplay}</span>
          </div>
        )}
        {bbox && bbox.length === 4 && (
          <div className="rc-meta-item">
            <span className="rc-meta-label">Bounding box</span>
            <span className="rc-meta-value rc-mono">
              {bbox[0].toFixed(3)}, {bbox[1].toFixed(3)} &rarr; {bbox[2].toFixed(3)}, {bbox[3].toFixed(3)}
            </span>
          </div>
        )}
        <div className="rc-meta-item">
          <span className="rc-meta-label">Task</span>
          <span className="rc-meta-value">{TASK_LABELS[task] || task}</span>
        </div>
        {result.source && (
          <div className="rc-meta-item">
            <span className="rc-meta-label">Source</span>
            <span className="rc-meta-value">{result.source === 'gee_live_fetch' ? 'GEE Live Fetch' : 'User Upload'}</span>
          </div>
        )}
        {result.fetched_coordinates && (
          <div className="rc-meta-item">
            <span className="rc-meta-label">Coordinates</span>
            <span className="rc-meta-value rc-mono">
              {result.fetched_coordinates.lat.toFixed(4)}, {result.fetched_coordinates.lon.toFixed(4)}
            </span>
          </div>
        )}
        {result.fetch_date && (
          <div className="rc-meta-item">
            <span className="rc-meta-label">Image Date</span>
            <span className="rc-meta-value">{result.fetch_date}</span>
          </div>
        )}
      </div>

      {/* Feature 2: Explainability Analytics */}
      {(result.heatmap_overlay_base64 || result.vegetation_breakdown || result.forest_cover_trend || result.flooded_area_pct !== undefined) && (
        <div className="rc-section" style={{ marginTop: 16 }}>
          <div className="rc-field-label">Visual Analytics Evidence</div>
          
          {/* Generic Heatmap */}
          {result.heatmap_overlay_base64 && (
            <div style={{ marginBottom: 12 }}>
              <span className="rc-meta-label">Heatmap Overlay</span>
              <img src={`data:image/png;base64,${result.heatmap_overlay_base64}`} alt="Heatmap overlay" style={{ width: '100%', maxWidth: '300px', display: 'block', marginTop: 8 }} />
            </div>
          )}
          
          {/* Forest Mask Overlay */}
          {result.forest_highlight_overlay_base64 && (
            <div style={{ marginBottom: 12 }}>
              <span className="rc-meta-label">Forest Cover Mask</span>
              <img src={`data:image/png;base64,${result.forest_highlight_overlay_base64}`} alt="Forest mask" style={{ width: '100%', maxWidth: '300px', display: 'block', marginTop: 8 }} />
            </div>
          )}

          {/* Agriculture Pie Chart */}
          {result.vegetation_breakdown && (
            <div style={{ marginBottom: 12 }}>
              <span className="rc-meta-label">Vegetation Types</span>
              <PieChart width={300} height={200}>
                <Pie data={result.vegetation_breakdown} cx="50%" cy="50%" outerRadius={60} fill="#8884d8" dataKey="value" nameKey="name" label>
                  {result.vegetation_breakdown.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={['#e0e0e0', '#d4e157', '#66bb6a', '#2e7d32'][index % 4]} />
                  ))}
                </Pie>
                <RechartsTooltip formatter={(value) => `${value.toFixed(1)}%`} />
                <Legend />
              </PieChart>
            </div>
          )}

          {/* Forest Cover Trend */}
          {result.forest_cover_trend && (
            <div style={{ marginBottom: 12 }}>
              <span className="rc-meta-label">Forest Cover Change</span>
              <BarChart width={300} height={200} data={result.forest_cover_trend}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis domain={[0, 100]} />
                <RechartsTooltip formatter={(value) => `${value.toFixed(1)}%`} />
                <Bar dataKey="value" fill="#4caf50" name="Forest Cover %" />
              </BarChart>
            </div>
          )}

          {/* Flood Map */}
          {result.flooded_area_pct !== undefined && (
            <div style={{ marginBottom: 12 }}>
              <span className="rc-meta-label">Flooded Area: {result.flooded_area_pct.toFixed(2)}%</span>
              {result.flood_geojson && result.fetched_coordinates && (
                <div style={{ height: '300px', width: '100%', marginTop: 8, borderRadius: 4, overflow: 'hidden' }}>
                  <MapContainer center={[result.fetched_coordinates.lat, result.fetched_coordinates.lon]} zoom={13} style={{ height: '100%', width: '100%' }}>
                    <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                    <GeoJSON data={result.flood_geojson} pathOptions={{ fillColor: 'blue', fillOpacity: 0.5, color: 'blue', weight: 1 }} />
                  </MapContainer>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Technical details — collapsed by default */}
      <div className="rc-divider" />

      <button
        className="rc-tech-toggle"
        onClick={() => setTechOpen(!techOpen)}
        aria-expanded={techOpen}
      >
        <span>Technical details</span>
        <span className={`rc-chevron ${techOpen ? "rc-chevron-open" : ""}`}>&#x203A;</span>
      </button>

      {techOpen && (
        <div className="rc-tech-body">
          {trace && (
            <div className="rc-tech-grid">
              <span className="rc-tech-label">Model</span>
              <span className="rc-tech-value">{trace.provider || trace.model_used || "\u2014"}</span>

              {trace.response_time_seconds != null && (
                <>
                  <span className="rc-tech-label">Processing time</span>
                  <span className="rc-tech-value">{trace.response_time_seconds} s</span>
                </>
              )}

              {trace.tool_called && (
                <>
                  <span className="rc-tech-label">Toolkit</span>
                  <span className="rc-tech-value">{trace.tool_called}</span>
                </>
              )}
            </div>
          )}

          {/* Raw output — second-level collapse */}
          <button
            className="rc-raw-toggle"
            onClick={() => setRawOpen(!rawOpen)}
            aria-expanded={rawOpen}
          >
            {rawOpen ? "Hide raw output" : "View raw output"}
          </button>

          {rawOpen && (
            <pre className="rc-raw">{JSON.stringify(result, null, 2)}</pre>
          )}
        </div>
      )}
      
      {result.session_id && (
        <div style={{ marginTop: 24, textAlign: 'right' }}>
          <a 
            href={`http://localhost:8000/generate_report/${result.session_id}`} 
            download 
            className="rc-download-btn"
            style={{ 
              display: 'inline-block', 
              padding: '10px 16px', 
              backgroundColor: '#1A237E', 
              color: 'white', 
              textDecoration: 'none', 
              borderRadius: '4px',
              fontWeight: '500'
            }}
          >
            Download Report (PDF)
          </a>
        </div>
      )}
    </div>
  );
}
