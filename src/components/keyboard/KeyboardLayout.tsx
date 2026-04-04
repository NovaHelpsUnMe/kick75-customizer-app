import { formatAssignmentLabel } from "../../lib/via/display";
import type { BoardKey } from "../../lib/via/types";

interface KeyboardLayoutProps {
  keys: BoardKey[];
  selectedKeyId: string;
  assignments?: Record<string, string>;
  onSelectKey: (keyId: string) => void;
}

const UNIT = 52;
const GAP = 8;

function getKeyWidth(width: number): number {
  return width * UNIT + (width - 1) * GAP;
}

export function KeyboardLayout({
  keys,
  selectedKeyId,
  assignments,
  onSelectKey,
}: KeyboardLayoutProps) {
  const maxX = Math.max(...keys.map((key) => key.x + key.width));
  const maxY = Math.max(...keys.map((key) => key.y + key.height));

  return (
    <div
      className="keyboard-surface"
      style={{
        width: `${maxX * UNIT + 40}px`,
        minHeight: `${maxY * UNIT + 40}px`,
      }}
    >
      {keys.map((key) => {
        const isSelected = key.id === selectedKeyId;
        const assignment = assignments?.[key.id];

        return (
          <button
            key={key.id}
            type="button"
            className={`keyboard-key${isSelected ? " is-selected" : ""}`}
            style={{
              left: `${key.x * UNIT + 20}px`,
              top: `${key.y * UNIT + 20}px`,
              width: `${getKeyWidth(key.width)}px`,
              height: `${key.height * UNIT}px`,
            }}
            onClick={() => onSelectKey(key.id)}
          >
            <span className="keyboard-key__label">{key.label}</span>
            <span className="keyboard-key__assignment">
              {assignment ? formatAssignmentLabel(assignment) : key.matrixPosition}
            </span>
          </button>
        );
      })}
    </div>
  );
}
