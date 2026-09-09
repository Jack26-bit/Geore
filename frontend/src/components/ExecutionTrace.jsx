/**
 * ExecutionTrace — numbered terminal-style step list.
 * Shows the agentic pipeline: task → tool → model → response.
 */
export default function ExecutionTrace({ trace }) {
  if (!trace) return null;

  const steps = [
    { label: "Task classified", value: trace.task },
    {
      label: "Tool called",
      value: trace.tool_called || "none (direct VLM query)",
    },
    {
      label: "Tool output",
      value: trace.tool_output
        ? JSON.stringify(trace.tool_output, null, 0)
        : "\u2014",
    },
    { label: "Model used", value: trace.provider || trace.model_used },
    {
      label: "Response time",
      value: trace.response_time_seconds != null
        ? `${trace.response_time_seconds}s`
        : "\u2014",
    },
  ];

  return (
    <div>
      <div className="divider" />
      <p className="section-label">Execution trace</p>
      <ol className="trace-list">
        {steps.map((step, i) => (
          <li key={i}>
            <span className="trace-step-num">{i + 1}.</span>
            <span className="trace-step-label">{step.label}</span>
            <span className="trace-step-value">{step.value}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
