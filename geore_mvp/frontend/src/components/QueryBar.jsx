export default function QueryBar({
  query,
  onQueryChange,
  onRun,
  disabled,
  loading,
}) {
  return (
    <div className="query-bar">
      <label>Query</label>

      <textarea
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        placeholder="What do you see in this image?"
      />

      <button
        type="button"
        onClick={onRun}
        disabled={disabled || loading}
      >
        {loading ? "Analyzing..." : "Run analysis"}
      </button>
    </div>
  );
}