export type ModelParameters = {
  temperature: number;
  top_p: number;
  frequency_penalty: number;
  presence_penalty: number;
  max_tokens?: number;
};

export type TunableModelParameterKey =
  | "temperature"
  | "top_p"
  | "frequency_penalty"
  | "presence_penalty";

export const DEFAULT_MODEL_PARAMETERS: ModelParameters = {
  temperature: 1.0,
  top_p: 1.0,
  frequency_penalty: 0.0,
  presence_penalty: 0.0,
};

export const MESSAGE_MAX_LENGTH = 20000;
