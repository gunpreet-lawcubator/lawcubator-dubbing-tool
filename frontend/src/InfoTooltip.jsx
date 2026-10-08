export default function InfoTooltip({ text }) {
  return (
    <span className="info-tooltip" tabIndex={0}>
      <span className="info-icon" aria-hidden="true">i</span>
      <span className="tooltip-bubble" role="tooltip">
        {text}
      </span>
    </span>
  );
}
