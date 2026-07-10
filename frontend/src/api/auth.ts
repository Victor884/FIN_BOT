import { api, tokenStorage } from "./client";
import type {
  AuthTokens,
  AuthenticatedUser,
  LoginPayload,
  PublicConfig,
  RegisterPayload,
  TelegramLinkPayload,
} from "@/types/api";

export const authApi = {
  async login(payload: LoginPayload) {
    const tokens = await api.post<AuthTokens>("/auth/login", payload, { auth: false });
    tokenStorage.set(tokens.access_token, tokens.refresh_token);
    return tokens;
  },
  async register(payload: RegisterPayload) {
    return api.post<AuthTokens | { message: string }>("/auth/register", payload, { auth: false });
  },
  async telegramLink(payload: TelegramLinkPayload) {
    tokenStorage.setRemember(false);
    const tokens = await api.post<AuthTokens>("/auth/telegram-link", payload, { auth: false });
    if ("access_token" in tokens) tokenStorage.set(tokens.access_token, tokens.refresh_token);
    return tokens;
  },
  me() {
    return api.get<AuthenticatedUser>("/auth/me");
  },
  publicConfig() {
    return api.get<PublicConfig>("/config/public", { auth: false });
  },
  async logout() {
    try {
      const refreshToken = tokenStorage.getRefresh();
      if (refreshToken) {
        await api.post("/auth/logout", { refresh_token: refreshToken }).catch(() => undefined);
      }
    } finally {
      tokenStorage.clear();
    }
  },
};
