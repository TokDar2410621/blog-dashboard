/** Gridar brand mark - geometric "G" with subtle arrow integration.
 *  Sourced from the Canva design (G1 candidate). The PNG ships with a
 *  transparent background, so it sits cleanly on any bg color. */

type Props = {
  className?: string;
  size?: number;
};

export function GridarMark({ className = "h-5 w-5", size }: Props) {
  return (
    <img
      src="/brand/gridar-mark-256.png"
      alt="Gridar"
      width={size}
      height={size}
      className={className}
      decoding="async"
    />
  );
}

/** Full Gridar logo lockup - brand mark + wordmark. */
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
