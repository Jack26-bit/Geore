
export default function QueryBar({
  query,
  onQueryChange,
  onRun,
  disabled,
  loading,
}) {
  return (
    <div className="query-area">
      <textarea
        className="query-input"
        placeholder="Ask anything about your satellite imagery..."
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !disabled) {
            e.preventDefault();
            onRun();
          }
        }}
      />

      <button
        className="send-button"
        onClick={onRun}
        disabled={disabled || loading}
        aria-label="Run analysis"
      >
        ↑
      </button>
    </div>
  );
}

