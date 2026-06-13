"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { HowItWorks } from "@/components/how-it-works";
import { LogoMark, SparkIcon, STAGE_ICONS } from "@/components/icons";
import { ResultsTabs } from "@/components/results-tabs";
import { PipelineStepper } from "@/components/stepper";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import {
  API_URL,
  EXAMPLE_PROBLEMS,
  STAGE_IDS,
  artifactDirFromPath,
  type PipelineEvent,
  type PipelineResults,
  type StageId,
  type StageStatus,
  type TrainingResult,
} from "@/lib/pipeline";

const PENDING_ALL = Object.fromEntries(
  STAGE_IDS.map((id) => [id, "pending"])
) as Record<StageId, StageStatus>;

const EMPTY_RESULTS: PipelineResults = {
  design: null,
  code: null,
  filePath: null,
  trainingResult: null,
  reportMd: null,
};

const TRAINING_PRESETS = [
  { label: "Fast", steps: 10_000, hint: "~5 min" },
  { label: "Balanced", steps: 25_000, hint: "~10–15 min" },
  { label: "Thorough", steps: 50_000, hint: "~30 min" },
] as const;

export default function Home() {
  const [problem, setProblem] = useState("");
  const [nTimesteps, setNTimesteps] = useState<number>(TRAINING_PRESETS[0].steps);
  const [running, setRunning] = useState(false);
  const [started, setStarted] = useState(false);
  const [done, setDone] = useState(false);
  const [pipelineError, setPipelineError] = useState<string | null>(null);
  const [statuses, setStatuses] = useState(PENDING_ALL);
  const [messages, setMessages] = useState<Partial<Record<StageId, string>>>({});
  const [elapsed, setElapsed] = useState<Partial<Record<StageId, number>>>({});
  const [results, setResults] = useState<PipelineResults>(EMPTY_RESULTS);
  const [plotUrl, setPlotUrl] = useState<string | null>(null);
  const [apiUp, setApiUp] = useState<boolean | null>(null);

  const plotUrlRef = useRef<string | null>(null);
  const statusesRef = useRef(statuses);
  statusesRef.current = statuses;
  const stageStartRef = useRef<Partial<Record<StageId, number>>>({});

  // Live backend status dot in the header.
  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const res = await fetch(`${API_URL}/health`, { cache: "no-store" });
        if (!cancelled) setApiUp(res.ok);
      } catch {
        if (!cancelled) setApiUp(false);
      }
    };
    check();
    const t = setInterval(check, 15_000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

  // Tick the active stage's timer once a second while the pipeline runs.
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => {
      const active = STAGE_IDS.find((id) => statusesRef.current[id] === "in_progress");
      if (!active) return;
      const start = stageStartRef.current[active];
      if (!start) return;
      setElapsed((prev) => ({ ...prev, [active]: (Date.now() - start) / 1000 }));
    }, 1000);
    return () => clearInterval(t);
  }, [running]);

  const reset = useCallback(() => {
    setStarted(false);
    setDone(false);
    setPipelineError(null);
    setStatuses(PENDING_ALL);
    setMessages({});
    setElapsed({});
    setResults(EMPTY_RESULTS);
    stageStartRef.current = {};
    if (plotUrlRef.current) URL.revokeObjectURL(plotUrlRef.current);
    plotUrlRef.current = null;
    setPlotUrl(null);
  }, []);

  const fetchPlot = useCallback(async (tr: TrainingResult) => {
    const dir = artifactDirFromPath(tr.plot_path);
    if (!dir) return;
    try {
      const res = await fetch(`${API_URL}/artifacts/${dir}/reward_curve.png`);
      if (!res.ok) return;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      plotUrlRef.current = url;
      setPlotUrl(url);
    } catch {
      // image is optional — the metrics still render
    }
  }, []);

  const handleEvent = useCallback(
    (ev: PipelineEvent) => {
      if (ev.stage === "pipeline") {
        if (ev.status === "complete") setDone(true);
        if (ev.status === "error") setPipelineError(ev.message ?? "Pipeline failed.");
        return;
      }
      const stage = ev.stage;
      if (ev.status === "in_progress") {
        stageStartRef.current[stage] = Date.now();
      } else {
        const start = stageStartRef.current[stage];
        if (start) {
          setElapsed((prev) => ({ ...prev, [stage]: (Date.now() - start) / 1000 }));
        }
      }
      setStatuses((prev) => ({ ...prev, [stage]: ev.status }));
      if (ev.message) setMessages((prev) => ({ ...prev, [stage]: ev.message }));
      if (ev.status === "error") {
        setPipelineError(ev.message ?? `The ${stage} stage failed.`);
        return;
      }
      if (ev.status !== "complete" || !ev.data) return;

      const data = ev.data;
      if (stage === "designing") {
        setResults((prev) => ({ ...prev, design: data }));
      } else if (stage === "coding") {
        setResults((prev) => ({
          ...prev,
          code: data.code as string,
          filePath: data.file_path as string,
        }));
      } else if (stage === "training") {
        const tr = data as unknown as TrainingResult;
        setResults((prev) => ({ ...prev, trainingResult: tr }));
        void fetchPlot(tr);
      } else if (stage === "reporting") {
        setResults((prev) => ({ ...prev, reportMd: data.report_md as string }));
      }
    },
    [fetchPlot]
  );

  const runPipeline = useCallback(async () => {
    if (!problem.trim() || running) return;
    reset();
    setStarted(true);
    setRunning(true);
    try {
      const res = await fetch(`${API_URL}/run-pipeline`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ problem_description: problem, n_timesteps: nTimesteps }),
      });
      if (!res.ok || !res.body) {
        throw new Error(`Backend returned ${res.status} ${res.statusText}`);
      }

      // Consume the NDJSON stream line by line.
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { done: streamDone, value } = await reader.read();
        if (streamDone) break;
        buffer += decoder.decode(value, { stream: true });
        let newline;
        while ((newline = buffer.indexOf("\n")) >= 0) {
          const line = buffer.slice(0, newline).trim();
          buffer = buffer.slice(newline + 1);
          if (line) handleEvent(JSON.parse(line) as PipelineEvent);
        }
      }
    } catch (err) {
      setPipelineError(
        err instanceof Error
          ? `${err.message} — is the backend running at ${API_URL}?`
          : "Unexpected error while contacting the backend."
      );
    } finally {
      setRunning(false);
    }
  }, [problem, running, nTimesteps, reset, handleEvent]);

  return (
    <div className="app-bg flex flex-1 flex-col">
      {/* Sticky top bar */}
      <header className="sticky top-0 z-20 border-b bg-background/70 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <span className="flex size-9 items-center justify-center rounded-lg bg-gradient-to-br from-sky-500 to-violet-500 text-white shadow-lg shadow-violet-500/20">
              <LogoMark className="size-5" />
            </span>
            <div className="leading-tight">
              <p className="font-semibold tracking-tight">RL Environment Designer</p>
              <p className="text-xs text-muted-foreground">5-agent AI pipeline</p>
            </div>
          </div>
          <div
            className={cn(
              "flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium",
              apiUp === true && "border-emerald-400/40 bg-emerald-400/10 text-emerald-300",
              apiUp === false && "border-red-400/40 bg-red-400/10 text-red-300",
              apiUp === null && "border-border text-muted-foreground"
            )}
          >
            <span
              className={cn(
                "size-2 rounded-full",
                apiUp === true && "animate-pulse bg-emerald-400",
                apiUp === false && "bg-red-400",
                apiUp === null && "bg-muted-foreground"
              )}
            />
            {apiUp === true ? "API connected" : apiUp === false ? "API offline" : "Checking..."}
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="mx-auto w-full max-w-6xl px-4 pb-2 pt-12 text-center">
        <h1 className="bg-gradient-to-r from-sky-400 via-violet-400 to-emerald-400 bg-clip-text text-4xl font-bold tracking-tight text-transparent sm:text-5xl">
          RL Environment Designer
        </h1>
        <p className="mx-auto mt-3 max-w-2xl text-balance text-muted-foreground">
          Describe any optimization problem → AI builds and trains a custom RL
          environment
        </p>
      </section>

      {/* Main split */}
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
          {/* LEFT — input */}
          <Card className="border-border/70 bg-card/70 shadow-xl shadow-black/20 backdrop-blur-sm">
            <CardHeader>
              <CardTitle>Your problem</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-5">
              <Textarea
                value={problem}
                onChange={(e) => setProblem(e.target.value)}
                placeholder="Describe your optimization problem... e.g. Optimize hospital shift scheduling to minimize overtime while ensuring full coverage"
                className="min-h-44 resize-y text-base"
                disabled={running}
              />

              <div>
                <p className="mb-2 text-sm font-medium text-muted-foreground">
                  Training budget
                </p>
                <div className="grid grid-cols-3 gap-2">
                  {TRAINING_PRESETS.map((preset) => (
                    <button
                      key={preset.label}
                      type="button"
                      disabled={running}
                      onClick={() => setNTimesteps(preset.steps)}
                      className={cn(
                        "rounded-lg border px-2 py-2 text-center transition-colors disabled:opacity-50",
                        nTimesteps === preset.steps
                          ? "border-sky-400/60 bg-sky-400/10"
                          : "border-border bg-muted/30 hover:border-sky-400/30"
                      )}
                    >
                      <span className="block text-sm font-medium">{preset.label}</span>
                      <span className="block font-mono text-xs text-muted-foreground">
                        {preset.steps.toLocaleString()} steps
                      </span>
                      <span className="block text-xs text-muted-foreground">{preset.hint}</span>
                    </button>
                  ))}
                </div>
              </div>

              <Button
                size="lg"
                onClick={runPipeline}
                disabled={running || !problem.trim()}
                className="w-full bg-gradient-to-r from-sky-500 to-violet-500 text-white shadow-lg shadow-violet-500/20 hover:from-sky-400 hover:to-violet-400"
              >
                {running ? (
                  <>
                    <span className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                    Running pipeline...
                  </>
                ) : (
                  <>
                    <SparkIcon className="size-4" />
                    Generate Environment
                  </>
                )}
              </Button>

              <div>
                <p className="mb-2 text-sm font-medium text-muted-foreground">
                  Try an example
                </p>
                <div className="flex flex-wrap gap-2">
                  {EXAMPLE_PROBLEMS.map((example) => (
                    <button
                      key={example.chip}
                      type="button"
                      disabled={running}
                      onClick={() => setProblem(example.text)}
                      className="rounded-full border bg-muted/40 px-3 py-1.5 text-sm text-foreground/90 transition-colors hover:border-sky-400/50 hover:bg-sky-400/10 disabled:opacity-50"
                    >
                      {example.chip}
                    </button>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* RIGHT — output */}
          <div className="flex flex-col gap-6">
            {!started ? (
              <Card className="border-dashed bg-card/40">
                <CardContent className="flex min-h-72 flex-col items-center justify-center gap-5 text-center">
                  <span className="flex size-16 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-500/20 to-violet-500/20 text-sky-300">
                    <LogoMark className="size-9" />
                  </span>
                  <p className="max-w-sm text-muted-foreground">
                    Describe a problem on the left and the five-agent pipeline
                    will design, code, validate, train, and report — live.
                  </p>
                  <div className="flex flex-wrap items-center justify-center gap-2 text-xs text-muted-foreground/80">
                    {STAGE_IDS.map((id, i) => {
                      const Icon = STAGE_ICONS[id];
                      return (
                        <span key={id} className="flex items-center gap-2">
                          {i > 0 && <span className="text-muted-foreground/40">→</span>}
                          <span className="flex items-center gap-1 rounded-full border bg-muted/30 px-2 py-1">
                            <Icon className="size-3.5" />
                            {["Design", "Code", "Validate", "Train", "Report"][i]}
                          </span>
                        </span>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            ) : (
              <Card className="border-border/70 bg-card/70 shadow-xl shadow-black/20 backdrop-blur-sm">
                <CardHeader className="flex-row items-center justify-between space-y-0">
                  <CardTitle>Pipeline progress</CardTitle>
                  {(done || pipelineError) && (
                    <Button variant="outline" size="sm" onClick={reset}>
                      ↺ Start Over
                    </Button>
                  )}
                </CardHeader>
                <CardContent>
                  <PipelineStepper statuses={statuses} messages={messages} elapsed={elapsed} />
                  {pipelineError && (
                    <div
                      role="alert"
                      className="mt-2 rounded-lg border border-red-400/40 bg-red-400/10 p-4 text-sm text-red-300"
                    >
                      <p className="font-semibold">Pipeline failed</p>
                      <p className="mt-1 break-words">{pipelineError}</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {done && (
              <Card className="border-border/70 bg-card/70 shadow-xl shadow-black/20 backdrop-blur-sm">
                <CardHeader>
                  <CardTitle>Results</CardTitle>
                </CardHeader>
                <CardContent>
                  <ResultsTabs results={results} plotUrl={plotUrl} />
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </main>

      <HowItWorks />

      <footer className="border-t bg-card/30">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-4 py-5 text-xs text-muted-foreground">
          <span>RL Environment Auto-Designer — an agentic AI pipeline</span>
          <span className="font-mono">FastAPI · Gymnasium · Stable Baselines3 · Next.js</span>
        </div>
      </footer>
    </div>
  );
}
