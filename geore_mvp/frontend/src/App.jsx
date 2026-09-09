import { useState, useMemo } from "react";
import "./styles/tokens.css";
import { analyzeImages } from "./api";
import UploadPanel from "./components/UploadPanel";
import QueryBar from "./components/QueryBar";
import ImageViewer from "./components/ImageViewer";
import AnswerPanel from "./components/AnswerPanel";
import ConfidenceBadge from "./components/ConfidenceBadge";
import ExecutionTrace from "./components/ExecutionTrace";


export default function App() {
  const [image1, setImage1] = useState(null);
  const [image2, setImage2] = useState(null);
  const [hasSar, setHasSar] = useState(false);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);


  // Object URLs for preview
  const image1Url = useMemo(
    () => (image1 ? URL.createObjectURL(image1) : null),
    [image1]
  );
  const image2Url = useMemo(
    () => (image2 ? URL.createObjectURL(image2) : null),
    [image2]
  );


  const canRun = !!image1 && query.trim().length > 0;


  async function handleRun() {
    if (!canRun || loading) return;


    setLoading(true);
    setError(null);
    setResult(null);


    const fd = new FormData();
    fd.append("image1", image1);
    fd.append("query", query.trim());
    if (image2) fd.append("image2", image2);
    fd.append("has_sar", hasSar.toString());


    try {
      const data = await analyzeImages(fd);
      setResult(data);
    } catch (err) {
      setError(err.message || "Analysis request failed");
    } finally {
      setLoading(false);
    }
  }


  const image2Label = hasSar ? "Image 2 (SAR)" : "Image 2 (After)";


  return (
    <div className="app-layout">
      {/* ── Header ─────────────────────────────────────── */}
      <header className="app-header">
        <span className="app-wordmark">GEORE</span>
        <span className="app-wordmark-sub">
          Remote sensing analysis instrument
        </span>
      </header>


      {/* ── Three-pane body ────────────────────────────── */}
      <div className="app-body">
        {/* Left: Input deck */}
        <aside className="panel">
          <UploadPanel
            image1={image1}
            image2={image2}
            hasSar={hasSar}
            onImage1={setImage1}
            onImage2={setImage2}
            onSarToggle={setHasSar}
          />
          <QueryBar
            query={query}
            onQueryChange={setQuery}
            onRun={handleRun}
            disabled={!canRun}
            loading={loading}
          />
        </aside>


        {/* Center: Image viewer */}
        <main className="panel-center">
          {loading && <div className="loading-text">Analyzing…</div>}
          {!loading && (
            <ImageViewer
              image1Url={image1Url}
              image2Url={image2Url}
              image2Label={image2Label}
              bbox={result?.bbox || null}
            />
          )}
        </main>


        {/* Right: Analysis output */}
        <aside className="panel">
          {error && (
            <div style={{ color: "var(--accent-warm)", fontSize: 13, marginBottom: 12 }}>
              {error}
            </div>
          )}
          {result && (
            <>
              <ConfidenceBadge
                task={result.task}
                confidence={result.confidence}
              />
              <AnswerPanel answer={result.answer} />
              <ExecutionTrace trace={result.execution_trace} />
            </>
          )}
          {!result && !error && !loading && (
            <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
              Upload an image and run a query to see analysis results here.
            </div>
          )}
        </aside>
      </div>
    </div>
  );
    
}

