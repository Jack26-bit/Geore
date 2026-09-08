const TASK_LABELS = {
  vqa: "Visual Q&A",
  grounding: "Grounding",
  change: "Change Detection",
  fusion: "Optical\u2013SAR Fusion",
};

export default function ConfidenceBadge({ task, confidence }) {
  if (!task) return null;
  return (
    <div className="badge-row">
      <span className="badge badge-task">
        {TASK_LABELS[task] || task}
      </span>
      <span className={`badge badge-confidence-${confidence}`}>
        {confidence}
      </span>
    </div>
  );
}
