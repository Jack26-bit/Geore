export default function AnswerPanel({ answer }) {
  if (!answer) return null;
  return (
    <div>
      <p className="section-label">Analysis result</p>
      <div className="answer-text">{answer}</div>
    </div>
  );
}
