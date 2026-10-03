"use client";

/**
 * ConfidenceBar Component
 * ========================
 * Animated confidence score visualization.
 * Extracted from the investigation page for reuse across components.
 *
 * Colors:
 *   ≥80  — green  (strong confidence)
 *   ≥60  — blue   (moderate confidence)
 *   <60  — amber  (weak confidence)
 */

interface ConfidenceBarProps {
  /** Score from 0 to 100 */
  score: number;
  /** Show numeric label on right. Defaults to true. */
  showLabel?: boolean;
}

export function ConfidenceBar({ score, showLabel = true }: ConfidenceBarProps) {
  const color =
    score >= 80 ? "#22c55e" : score >= 60 ? "#3b82f6" : "#f59e0b";
  const label = `${score.toFixed(0)}/100`;

  return (
    <div className="flex items-center gap-3">
      <div className="confidence-bar flex-1">
        <div
          className="confidence-fill"
          style={{ width: `${Math.min(100, Math.max(0, score))}%`, background: color }}
        />
      </div>
      {showLabel && (
        <span
          className="font-mono text-sm font-bold"
          style={{ color, minWidth: "4rem", textAlign: "right" }}
        >
          {label}
        </span>
      )}
    </div>
  );
}
