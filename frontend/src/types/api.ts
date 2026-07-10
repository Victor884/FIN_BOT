export type UserRole = "ADMIN" | "USER";

export interface AuthenticatedUser {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  telegram_linked?: boolean;
  created_at?: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token?: string;
  token_type?: string;
  expires_in?: number;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  name: string;
  email: string;
  password: string;
}

export interface TelegramLinkPayload {
  code: string;
  email: string;
  password: string;
}

export interface PublicConfig {
  api_version: string;
  environment: string;
  registration_enabled: boolean;
  features: Record<string, boolean>;
}

export interface ApiErrorShape {
  status: number;
  message: string;
  request_id?: string;
  detail?: unknown;
}
