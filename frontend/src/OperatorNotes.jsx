import InfoTooltip from "./InfoTooltip";

export default function OperatorNotes({ value, onChange }) {
  return (
    <div className="field">
      <label>
        Notes for the AI (optional)
        <InfoTooltip text={'Use this to correct anything the AI is likely to get wrong on its own — a name it mishears, a term it should translate a specific way, etc. Example: "The manager\'s name around 1:41 is \'Jithin\', not \'Jiten\' — please use \'Jithin\' everywhere." These notes are applied on your next attempt at this video.'} />
      </label>
      <textarea
        className="operator-notes"
        rows={5}
        placeholder={'e.g. "The character around 1:41 is named \'Jithin\', not \'Jiten\' — please use \'Jithin\'."'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
