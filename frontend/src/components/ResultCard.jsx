import { useRef, useEffect, useState } from "react";

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
      </div>

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
    </div>
  );
}
