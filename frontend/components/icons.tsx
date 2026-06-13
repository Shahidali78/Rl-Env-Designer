import type { ComponentType, SVGProps } from "react";

import type { StageId } from "@/lib/pipeline";

type IconProps = SVGProps<SVGSVGElement>;

function Svg({ children, ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      {...props}
    >
      {children}
    </svg>
  );
}

/** Designer — a small graph of connected nodes (state/action/reward). */
export function DesignIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="6" cy="6" r="2.4" />
      <circle cx="18" cy="8" r="2.4" />
      <circle cx="10" cy="18" r="2.4" />
      <path d="M8.3 6.6l7.3 1M7 8.2l2.3 7.5M16.5 9.9l-5 6.3" />
    </Svg>
  );
}

/** Coder — angle brackets. */
export function CodeIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M8.5 7L4 12l4.5 5" />
      <path d="M15.5 7L20 12l-4.5 5" />
      <path d="M13.2 5.5l-2.4 13" />
    </Svg>
  );
}

/** Executor — shield with a check. */
export function ValidateIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M12 3l7 2.8v5.1c0 4.3-2.9 7.4-7 9.1-4.1-1.7-7-4.8-7-9.1V5.8L12 3z" />
      <path d="M9 12l2.2 2.2L15.5 9.7" />
    </Svg>
  );
}

/** Trainer — rising reward curve with an end arrow. */
export function TrainIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M3 17l5.5-5.5 3.5 3.5L20 7" />
      <path d="M14.5 7H20v5.5" />
    </Svg>
  );
}

/** Reporter — document with bar chart. */
export function ReportIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M6 3h8.5L19 7.5V20a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z" />
      <path d="M14.5 3v4.5H19" />
      <path d="M9 17v-3M12 17v-5.5M15 17v-2" />
    </Svg>
  );
}

/** Four-point spark, used on the generate button. */
export function SparkIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path
        d="M12 4l1.7 4.8L18.5 10.5l-4.8 1.7L12 17l-1.7-4.8L5.5 10.5l4.8-1.7L12 4z"
        fill="currentColor"
        stroke="none"
      />
    </Svg>
  );
}

/** Brand mark — the agent-environment loop with the agent at the center. */
export function LogoMark(props: IconProps) {
  return (
    <Svg strokeWidth={2} {...props}>
      <path d="M19.5 12a7.5 7.5 0 1 1-2.6-5.7" />
      <path d="M19.7 3.6l-.4 3.9-3.9-.4" />
      <circle cx="12" cy="12" r="2.4" fill="currentColor" stroke="none" />
    </Svg>
  );
}

export const STAGE_ICONS: Record<StageId, ComponentType<IconProps>> = {
  designing: DesignIcon,
  coding: CodeIcon,
  executing: ValidateIcon,
  training: TrainIcon,
  reporting: ReportIcon,
};

/** Per-agent accent colors used on the marketing cards. */
export const STAGE_ACCENTS: Record<StageId, { text: string; chip: string }> = {
  designing: { text: "text-violet-400", chip: "border-violet-400/30 bg-violet-400/10" },
  coding: { text: "text-sky-400", chip: "border-sky-400/30 bg-sky-400/10" },
  executing: { text: "text-amber-400", chip: "border-amber-400/30 bg-amber-400/10" },
  training: { text: "text-emerald-400", chip: "border-emerald-400/30 bg-emerald-400/10" },
  reporting: { text: "text-pink-400", chip: "border-pink-400/30 bg-pink-400/10" },
};
