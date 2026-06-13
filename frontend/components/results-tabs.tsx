"use client";

import Image from "next/image";
import ReactMarkdown from "react-markdown";
import hljs from "highlight.js/lib/core";
import python from "highlight.js/lib/languages/python";
import "highlight.js/styles/github-dark.css";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { API_URL, artifactDirFromPath, type PipelineResults } from "@/lib/pipeline";

hljs.registerLanguage("python", python);

function downloadText(filename: string, content: string) {
  const url = URL.createObjectURL(new Blob([content], { type: "text/plain" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border bg-muted/30 px-4 py-3">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 font-mono text-lg font-semibold">{value}</p>
    </div>
  );
}

export function ResultsTabs({
  results,
  plotUrl,
}: {
  results: PipelineResults;
  plotUrl: string | null;
}) {
  const { code, design, trainingResult, reportMd } = results;
  const highlighted = code ? hljs.highlight(code, { language: "python" }).value : "";
  const artifactDir = trainingResult ? artifactDirFromPath(trainingResult.plot_path) : null;
  const codeFilename = results.filePath?.split(/[\\/]/).pop() ?? "environment.py";

  return (
    <div className="flex flex-col gap-4">
      {/* Summary strip */}
      {trainingResult && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-muted/20 px-4 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono font-semibold">{trainingResult.env_name}</span>
            <Badge variant="secondary">{trainingResult.algorithm}</Badge>
            <Badge
              className={
                trainingResult.improvement_pct >= 0
                  ? "border-emerald-400/40 bg-emerald-400/10 text-emerald-300"
                  : "border-red-400/40 bg-red-400/10 text-red-300"
              }
              variant="outline"
            >
              {trainingResult.improvement_pct >= 0 ? "▲" : "▼"}{" "}
              {Math.abs(trainingResult.improvement_pct).toFixed(1)}% vs baseline
            </Badge>
          </div>
          <div className="flex flex-wrap gap-2">
            {code && (
              <Button variant="outline" size="sm" onClick={() => downloadText(codeFilename, code)}>
                ↓ Code
              </Button>
            )}
            {reportMd && (
              <Button variant="outline" size="sm" onClick={() => downloadText("report.md", reportMd)}>
                ↓ Report
              </Button>
            )}
            {artifactDir && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  const a = document.createElement("a");
                  a.href = `${API_URL}/artifacts/${artifactDir}/model.zip`;
                  a.download = "model.zip";
                  a.click();
                }}
              >
                ↓ Model
              </Button>
            )}
          </div>
        </div>
      )}

      <Tabs defaultValue="report" className="w-full">
      <TabsList className="grid w-full grid-cols-2 sm:grid-cols-4">
        <TabsTrigger value="report">Report</TabsTrigger>
        <TabsTrigger value="code">Environment Code</TabsTrigger>
        <TabsTrigger value="curve">Reward Curve</TabsTrigger>
        <TabsTrigger value="design">Design JSON</TabsTrigger>
      </TabsList>

      <TabsContent value="report" className="mt-4">
        <article className="prose prose-invert prose-neutral max-w-none prose-headings:scroll-mt-8 prose-table:text-sm">
          {reportMd ? <ReactMarkdown>{reportMd}</ReactMarkdown> : <p>No report available.</p>}
        </article>
      </TabsContent>

      <TabsContent value="code" className="mt-4">
        <div className="overflow-hidden rounded-lg border">
          <div className="flex items-center justify-between border-b bg-muted/40 px-4 py-2">
            <span className="font-mono text-xs text-muted-foreground">{codeFilename}</span>
            <Badge variant="secondary">Python</Badge>
          </div>
          <pre className="max-h-[32rem] overflow-auto bg-[#0d1117] p-4 text-sm leading-relaxed">
            <code
              className="hljs language-python"
              dangerouslySetInnerHTML={{ __html: highlighted }}
            />
          </pre>
        </div>
      </TabsContent>

      <TabsContent value="curve" className="mt-4 space-y-4">
        {trainingResult && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Metric label="Algorithm" value={trainingResult.algorithm} />
            <Metric
              label="Timesteps"
              value={trainingResult.total_timesteps.toLocaleString()}
            />
            <Metric
              label="Final reward"
              value={trainingResult.mean_reward_final.toFixed(2)}
            />
            <Metric
              label="Improvement"
              value={`${trainingResult.improvement_pct >= 0 ? "+" : ""}${trainingResult.improvement_pct.toFixed(1)}%`}
            />
          </div>
        )}
        {plotUrl ? (
          <Image
            src={plotUrl}
            alt="Training reward curve"
            width={960}
            height={540}
            unoptimized
            className="h-auto w-full rounded-lg border bg-white"
          />
        ) : (
          <p className="text-sm text-muted-foreground">
            Reward curve image not available.
          </p>
        )}
      </TabsContent>

      <TabsContent value="design" className="mt-4">
        <pre className="max-h-[32rem] overflow-auto rounded-lg border bg-muted/30 p-4 font-mono text-sm leading-relaxed">
          {design ? JSON.stringify(design, null, 2) : "No design available."}
        </pre>
      </TabsContent>
      </Tabs>
    </div>
  );
}
