import { useState } from "react";

const CHOICES = [
  {
    value: "drift",
    label: "Let it drift",
    description: "Video speeds up/slows down as much as it safely can; this segment ends up a bit longer or shorter than the original, but audio quality stays perfect.",
  },
  {
    value: "residual_audio",
    label: "Video + a little audio stretch",
    description: "Video is clamped to a safe speed, and a small audio stretch closes the rest of the gap. A middle ground.",
  },
  {
    value: "fallback_audio",
    label: "Stretch audio instead",
    description: "Just for this segment: video stays untouched, audio is time-stretched to fit exactly like normal mode.",
  },
];

export default function ReviewPanel({ flaggedSegments, onSubmit }) {
  const [choices, setChoices] = useState({});
  const allChosen = flaggedSegments.every((seg) => choices[seg.index]);

  return (
    <section className="panel review-needed-panel">
      <h2>A few segments need your call</h2>
      <p className="hint">
        These segments would need to speed up or slow down the video too much to look natural. Pick how to handle
        each one, then continue.
      </p>

      {flaggedSegments.map((seg) => (
        <div key={seg.index} className="flagged-segment">
          <div className="flagged-segment-text">
            <p className="flagged-english">{seg.english}</p>
            <p className="flagged-translated">{seg.translated}</p>
            <p className="flagged-meta">
              Would need to run {seg.direction} by {seg.factor}x to match the voiceover naturally.
            </p>
          </div>
          <div className="flagged-choices">
            {CHOICES.map((choice) => (
              <label key={choice.value} className="flagged-choice">
                <input
                  type="radio"
                  name={`resolve-${seg.index}`}
                  checked={choices[seg.index] === choice.value}
                  onChange={() => setChoices((c) => ({ ...c, [seg.index]: choice.value }))}
                />
                <span>
                  <strong>{choice.label}</strong> &mdash; {choice.description}
                </span>
              </label>
            ))}
          </div>
        </div>
      ))}

      <button className="generate-btn" disabled={!allChosen} onClick={() => onSubmit(choices)}>
        Continue with these choices
      </button>
    </section>
  );
}
