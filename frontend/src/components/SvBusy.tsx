/** Animated Scenario Visualizer mark while /v1/project is in flight. */

export function SvBusy({ compact }: { compact?: boolean }) {
  return (
    <div
      className={`x-svbusy${compact ? ' compact' : ''}`}
      role="status"
      aria-live="polite"
      aria-label="Calculating projection"
    >
      <span className="x-svbusy-mark" aria-hidden>
        <svg viewBox="0 0 32 32">
          <rect width="32" height="32" rx="8" fill="#f97316" />
          <path
            className="x-svbusy-path"
            d="M6 22 L12 12 L17 18 L22 8 L26 22"
            fill="none"
            stroke="#fff"
            strokeWidth="1.8"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        </svg>
      </span>
      {compact ? null : <span className="x-svbusy-label">Calculating…</span>}
    </div>
  );
}
