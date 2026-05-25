import Image from "next/image";

type Props = {
  className?: string;
  size?: number;
};

export function GridarMark({ className = "h-5 w-5", size = 32 }: Props) {
  return (
    <Image
      src="/brand/gridar-mark-256.png"
      alt="Gridar"
      width={size}
      height={size}
      className={className}
      priority
    />
  );
}

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
