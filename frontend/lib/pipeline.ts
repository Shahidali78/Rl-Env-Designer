export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const STAGE_IDS = [
  "designing",
  "coding",
  "executing",
  "training",
  "reporting",
] as const;

export type StageId = (typeof STAGE_IDS)[number];
export type StageStatus = "pending" | "in_progress" | "complete" | "error";

export const STAGE_META: Record<StageId, { label: string }> = {
  designing: { label: "Designing Environment" },
  coding: { label: "Writing Code" },
  executing: { label: "Validating & Testing" },
  training: { label: "Training Agent" },
  reporting: { label: "Generating Report" },
};

export interface PipelineEvent {
  stage: StageId | "pipeline";
  status: "in_progress" | "complete" | "error";
  message?: string;
  data?: Record<string, unknown>;
}

export interface TrainingResult {
  env_name: string;
  algorithm: "SAC" | "PPO";
  total_timesteps: number;
  mean_reward_final: number;
  std_reward_final: number;
  mean_reward_initial: number;
  improvement_pct: number;
  model_path: string;
  plot_path: string;
  csv_path: string;
  training_time_seconds: number;
}

export interface PipelineResults {
  design: Record<string, unknown> | null;
  code: string | null;
  filePath: string | null;
  trainingResult: TrainingResult | null;
  reportMd: string | null;
}

export const EXAMPLE_PROBLEMS = [
  {
    chip: "Hospital shift scheduling",
    text: "Optimize hospital shift scheduling to minimize overtime costs while ensuring every shift has full nursing coverage and no nurse works more than 5 consecutive days.",
  },
  {
    chip: "Warehouse robot navigation",
    text: "Optimize the navigation of a warehouse robot that must pick items from shelves and deliver them to packing stations, minimizing travel time while avoiding collisions and battery depletion.",
  },
  {
    chip: "Smart traffic light control",
    text: "Optimize the signal timing of a four-way intersection's traffic lights to minimize average vehicle wait time across varying rush-hour and off-peak traffic patterns.",
  },
] as const;

/** Derive the artifact directory name from a backend file path like
 *  "C:\...\training\hospital_shift_env\reward_curve.png" -> "hospital_shift_env" */
export function artifactDirFromPath(p: string): string | null {
  const parts = p.split(/[\\/]/).filter(Boolean);
  return parts.length >= 2 ? parts[parts.length - 2] : null;
}
