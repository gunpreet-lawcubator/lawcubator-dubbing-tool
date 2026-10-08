const STEP_ORDER = [
  "extracting_audio",
  "transcribing",
  "aligning",
  "translating",
  "generating_tts",
  "time_aligning",
  "retiming_video",
  "assembling",
  "mixing_bgm",
  "muxing_video",
  "done",
];

function stepLabels(languageLabel) {
  const lang = languageLabel || "the target language";
  return {
    extracting_audio: "Reading your video",
    transcribing: "Listening to the speech and writing it down",
    aligning: "Saving the transcript",
    translating: `Translating everything into ${lang}`,
    generating_tts: `Recording the ${lang} voiceover`,
    time_aligning: "Fine-tuning the voice timing",
    retiming_video: "Adjusting video timing to match the voiceover",
    assembling: "Putting the audio track together",
    mixing_bgm: "Adding the intro jingle and background music",
    muxing_video: "Rendering the final video with subtitles",
    done: "All done!",
  };
}

function StepIcon({ state }) {
  if (state === "done") return <span className="step-icon step-icon-done">&#10003;</span>;
  if (state === "error") return <span className="step-icon step-icon-error">&#33;</span>;
  if (state === "active") return <span className="step-icon step-icon-active" />;
  return <span className="step-icon step-icon-pending" />;
}

export default function ProgressSteps({ languageLabel, step, stepDetail, status, error }) {
  const labels = stepLabels(languageLabel);
  const currentStepIndex = STEP_ORDER.indexOf(step);

  return (
    <section className="panel progress-panel">
      <h2>Working on your dub&hellip;</h2>
      <ol className="steps">
        {STEP_ORDER.map((s, i) => {
          const state =
            status === "error" && i === currentStepIndex
              ? "error"
              : i < currentStepIndex
              ? "done"
              : i === currentStepIndex
              ? "active"
              : "pending";
          return (
            <li key={s} className={`step step-${state}`}>
              <StepIcon state={state} />
              <span>
                {labels[s]}
                {state === "active" && stepDetail ? ` (${stepDetail})` : ""}
              </span>
            </li>
          );
        })}
      </ol>
      {status === "error" && <pre className="error">{error}</pre>}
    </section>
  );
}
