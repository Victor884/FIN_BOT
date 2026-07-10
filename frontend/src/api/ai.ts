import { api } from "./client";

export interface AiCompletion {
  text: string;
  model: string;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
}

export const aiApi = {
  complete: (prompt: string, signal?: AbortSignal) =>
    api.post<AiCompletion>("/ai/completions", { prompt }, { signal }),
};
