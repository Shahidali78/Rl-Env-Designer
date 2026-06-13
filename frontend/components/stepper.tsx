"use client";

import { STAGE_ICONS } from "@/components/icons";
import { STAGE_IDS, STAGE_META, type StageId, type StageStatus } from "@/lib/pipeline";
import { cn } from "@/lib/utils";

function formatSeconds(s: number): string {
  if (s < 60) return `${Math.round(s)}s`;
  return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`;
}

function StatusIndicator({ status }: { status: StageStatus }) {
  if (status === "in_progress") {
    return (
      <span
        className="size-5 animate-spin rounded-full border-2 border-sky-400 border-t-transparent"
        aria-label="in progress"
      />
    );
  }
  if (status === "complete") {
    return (
      <svg viewBox="0 0 20 20" fill="none" className="size-5 text-emerald-400" aria-label="complete">
        <circle cx="10" cy="10" r="9" className="fill-emerald-400/15" />
        <path d="M6 10.5l2.5 2.5L14 7.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (status === "error") {
    return (
      <svg viewBox="0 0 20 20" fill="none" className="size-5 text-red-400" aria-label="error">
        <circle cx="10" cy="10" r="9" className="fill-red-400/15" />
        <path d="M7 7l6 6M13 7l-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
    );
  }
  return <span className="size-5 rounded-full border-2 border-border" aria-label="pending" />;
}

export function PipelineStepper({
  statuses,
  messages,
  elapsed,
}: {
  statuses: Record<StageId, StageStatus>;
  messages: Partial<Record<StageId, string>>;
  elapsed: Partial<Record<StageId, number>>;
}) {
  return (
    <ol className="flex flex-col">
      {STAGE_IDS.map((id, i) => {
        const status = statuses[id];
        const meta = STAGE_META[id];
        const Icon = STAGE_ICONS[id];
        const isLast = i === STAGE_IDS.length - 1;
        const seconds = elapsed[id];
        return (
          <li key={id} className="relative flex gap-4 pb-1">
            {!isLast && (
              <span
                className={cn(
                  "absolute left-[19px] top-10 h-[calc(100%-2rem)] w-px",
                  status === "complete" ? "bg-emerald-400/40" : "bg-border"
                )}
              />
            )}
            <span
              className={cn(
                "flex size-10 shrink-0 items-center justify-center rounded-full border transition-colors",
                status === "in_progress" &&
                  "border-sky-400/50 bg-sky-400/10 text-sky-300 shadow-[0_0_18px_-4px] shadow-sky-400/40",
                status === "complete" && "border-emerald-400/50 bg-emerald-400/10 text-emerald-300",
                status === "error" && "border-red-400/50 bg-red-400/10 text-red-300",
                status === "pending" && "border-border bg-muted/30 text-muted-foreground opacity-70"
              )}
              aria-hidden
            >
              <Icon className="size-5" />
            </span>
            <div className="flex min-h-12 flex-1 flex-col justify-center pb-4">
              <div className="flex items-center justify-between gap-3">
                <p
                  className={cn(
                    "font-medium",
                    status === "pending" && "text-muted-foreground",
                    status === "error" && "text-red-400"
                  )}
                >
                  {meta.label}
                </p>
                <span className="flex items-center gap-2">
                  {seconds !== undefined && status !== "pending" && (
                    <span
                      className={cn(
                        "font-mono text-xs tabular-nums",
                        status === "in_progress" ? "text-sky-400" : "text-muted-foreground"
                      )}
                    >
                      {formatSeconds(seconds)}
                    </span>
                  )}
                  <StatusIndicator status={status} />
                </span>
              </div>
              {messages[id] && status !== "pending" && (
                <p
                  className={cn(
                    "mt-0.5 text-sm",
                    status === "error" ? "text-red-400/90" : "text-muted-foreground"
                  )}
                >
                  {messages[id]}
                </p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
