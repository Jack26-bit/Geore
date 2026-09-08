
import { useMemo, useState } from "react";
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

  const image1Url = useMemo(
    () => (image1 ? URL.createObjectURL(image1) : null),
    [image1]
  );

  const image2Url = useMemo(
    () => (image2 ? URL.createObjectURL(image2) : null),
    [image2]
  );

  const canRunAnalysis = image1 && query.trim().length > 0;

  async function handleRunAnalysis() {
    if (!canRunAnalysis || loading) return;

    setLoading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();

    formData.append("image1", image1);
    formData.append("query", query.trim());

    if (image2) {
      formData.append("image2", image2);
    }

    formData.append("has_sar", String(hasSar));

    try {
      const analysisResult = await analyzeImages(formData);
      setResult(analysisResult);
    } catch (err) {
      setError(err.message || "Unable to complete the analysis.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <span className="app-wordmark">GEORE</span>
        <span className="app-subtitle">Satellite imagery explorer</span>
      </header>

      <main className="chat-page">
        {!result && !loading && (
          <section className="welcome">
            <div className="welcome-mark">G</div>

            <h1>What would you like to know?</h1>

            <p>
              Upload satellite imagery and ask a simple question about it.
            </p>
          </section>
        )}

        {(result || loading) && (
          <section className="image-section">
            <ImageViewer
              image1Url={image1Url}
              image2Url={image2Url}
              image2Label={hasSar ? "Image 2 (SAR)" : "Image 2 (After)"}
              bbox={result?.bbox || null}
            />
          </section>
        )}

        {error && <div className="error-message">{error}</div>}

        {result && (
          <section className="answer-section">
            <div className="answer-heading">
              <span>GEORE</span>
            </div>

            <ConfidenceBadge
              task={result.task}
              confidence={result.confidence}
            />

            <AnswerPanel answer={result.answer} />

            <ExecutionTrace trace={result.execution_trace} />
          </section>
        )}

        {!result && !loading && (
          <section className="composer-area">
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
              onRun={handleRunAnalysis}
              disabled={!canRunAnalysis}
              loading={loading}
            />
          </section>
        )}

        {loading && (
          <div className="thinking">
            Looking at your imagery...
          </div>
        )}
      </main>
    </div>
  );
}

