import { STAGE_ACCENTS, STAGE_ICONS } from "@/components/icons";
import { Card, CardContent } from "@/components/ui/card";
import type { StageId } from "@/lib/pipeline";
import { cn } from "@/lib/utils";

const AGENTS: { stage: StageId; name: string; description: string }[] = [
  {
    stage: "designing",
    name: "Designer Agent",
    description:
      "Analyzes your problem and designs the RL formulation: what the agent observes, what actions it can take, how it's rewarded, and when an episode ends.",
  },
  {
    stage: "coding",
    name: "Coder Agent",
    description:
      "Turns the design into a complete, runnable Gymnasium environment in Python — spaces, dynamics, and every reward component, fully self-contained.",
  },
  {
    stage: "executing",
    name: "Code Executor",
    description:
      "Runs the generated environment in an isolated process, checks the Gymnasium contract, and automatically asks the AI to fix any bugs it finds.",
  },
  {
    stage: "training",
    name: "Trainer Agent",
    description:
      "Picks SAC or PPO based on the action space and trains a policy with Stable Baselines3, logging reward curves throughout the run.",
  },
  {
    stage: "reporting",
    name: "Reporter Agent",
    description:
      "Writes a human-readable report: the design decisions explained, training performance versus the random baseline, and how to improve further.",
  },
];

export function HowItWorks() {
  return (
    <section className="mx-auto w-full max-w-6xl px-4 pb-16">
      <h2 className="mb-2 text-center text-2xl font-semibold tracking-tight">
        How it works
      </h2>
      <p className="mb-8 text-center text-muted-foreground">
        Five specialized AI agents hand your problem from one to the next.
      </p>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {AGENTS.map((agent, i) => {
          const Icon = STAGE_ICONS[agent.stage];
          const accent = STAGE_ACCENTS[agent.stage];
          return (
            <Card
              key={agent.name}
              className="bg-card/60 transition-all hover:-translate-y-1 hover:border-sky-400/30 hover:shadow-lg hover:shadow-sky-400/5"
            >
              <CardContent className="flex flex-col gap-3 pt-2">
                <div className="flex items-center justify-between">
                  <span
                    className={cn(
                      "flex size-9 items-center justify-center rounded-lg border",
                      accent.chip,
                      accent.text
                    )}
                  >
                    <Icon className="size-5" />
                  </span>
                  <span className="font-mono text-xs text-muted-foreground">
                    step {i + 1}
                  </span>
                </div>
                <h3 className="font-semibold leading-tight">{agent.name}</h3>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {agent.description}
                </p>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </section>
  );
}
