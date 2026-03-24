// Tooltip — renders a ⓘ icon that shows help text on hover.
// Usage: <label className="label">Game Mode <Tooltip text="Select existing mode." /></label>

interface Props {
  text: string;
}

export default function Tooltip({ text }: Props) {
  return (
    <span className="group relative inline-flex items-center ml-1 align-middle">
      <span className="flex items-center justify-center w-4 h-4 rounded-full bg-[var(--border)] text-[var(--muted)] text-[10px] font-bold cursor-help select-none leading-none">
        ?
      </span>
      {/* Tooltip popup */}
      <span
        role="tooltip"
        className="
          pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50
          w-56 rounded bg-[#1e1e1e] border border-[var(--border)]
          px-2.5 py-1.5 text-xs text-[var(--text)] leading-relaxed shadow-lg
          opacity-0 group-hover:opacity-100
          transition-opacity duration-150
        "
      >
        {text}
        {/* Arrow */}
        <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-[var(--border)]" />
      </span>
    </span>
  );
}
