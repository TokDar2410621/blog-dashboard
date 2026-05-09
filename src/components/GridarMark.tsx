/** Gridar brand mark — geometric "G" with hidden upward arrow in negative space.
 *  Single-color SVG, takes its color from currentColor so you can tint it via
 *  Tailwind text-* utilities (e.g. text-emerald-500). */
type Props = {
  className?: string;
};

export function GridarMark({ className = "h-5 w-5" }: Props) {
  return (
    <svg
      viewBox="0 0 100 100"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="Gridar"
      role="img"
    >
      <path
        fill="currentColor"
        fillRule="evenodd"
        d="M50 4L90 27L90 73L50 96L10 73L10 27ZM50 22L26 36L26 64L50 78L74 64L74 56L56 56L56 47L74 47L74 36Z"
      />
      <polygon fill="currentColor" points="40,62 50,44 60,62" />
    </svg>
  );
}

/** Full Gridar logo lockup — brand mark + wordmark. */
export function GridarLogo({
  markClass = "h-6 w-6",
  textClass = "font-semibold tracking-tight",
}: {
  markClass?: string;
  textClass?: string;
}) {
  return (
    <span className="inline-flex items-center gap-2">
      <GridarMark className={markClass} />
      <span className={textClass}>Gridar</span>
    </span>
  );
}
