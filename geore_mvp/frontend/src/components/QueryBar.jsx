export default function QueryBar({ query, onQueryChange, onRun, disabled, loading }) {
  return (
    <div>
      <div className="divider" />
      <p className="section-label">Query</p>
      <textarea
        className="query-input"
        placeholder={"e.g. What type of land use is shown?\ne.g. Highlight the water body\ne.g. What changed between these images?"}
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && e.ctrlKey && !disabled) onRun();
        }}
      />
      <button
        className="btn-run"
        onClick={onRun}
        disabled={disabled || loading}
      >
        {loading ? "Analyzing\u2026" : "Run analysis"}
      </button>
    </div>
  );
}
