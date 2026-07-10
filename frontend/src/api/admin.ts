import { api } from "./client";
import type { CategoryPoint, CashFlowPoint, Money } from "./user";

export interface AdminSummary {
  users_total: number;
  users_active_today: number;
  users_active_7d: number;
  users_active_30d: number;
  new_users: number;
  messages_total: number;
  transactions_total: number;
  income_count: number;
  expense_count: number;
  transfer_count: number;
  income_amount: Money;
  expense_amount: Money;
  aggregate_balance: Money;
  local_parser_messages: number;
  ai_parser_messages: number;
  ai_usage_rate: Money;
  parser_success_rate: Money;
  error_rate: Money;
  response_time_average_ms: Money;
  response_time_p50_ms: number;
  response_time_p95_ms: number;
  response_time_p99_ms: number;
  duplicates_blocked: number;
}

export interface ActivityEvent {
  update_id: string;
  user_id: string | null;
  username: string | null;
  status: string;
  parser_source: string | null;
  ai_used: boolean;
  duration_ms: number | null;
  created_at: string;
}

export interface ActivityData {
  series: { date: string; messages: number; transactions: number; active_users: number }[];
  recent: ActivityEvent[];
}

export interface PerformanceMetrics {
  endpoints: {
    endpoint: string;
    requests: number;
    average_ms: number;
    p95_ms: number;
  }[];
  recent_requests: {
    request_id: string;
    endpoint: string;
    method: string;
    status_code: number;
    duration_ms: number;
    origin: string | null;
    created_at: string;
  }[];
}

export interface ApiErrorLog {
  id: string;
  request_id: string | null;
  endpoint: string;
  code: string;
  integration: string | null;
  created_at: string;
}

export interface IntegrationStatus {
  name: string;
  status: string;
  latency_ms: number | null;
  message: string | null;
}

export interface AdminUser {
  id: string;
  name: string | null;
  username: string | null;
  role: "ADMIN" | "USER";
  status: string;
  messages: number;
  created_at: string;
  last_activity_at: string;
}

const periodQuery = (params?: { from?: string; to?: string }) => ({
  start_date: params?.from,
  end_date: params?.to,
});

export const adminApi = {
  summary: (params?: { from?: string; to?: string }) =>
    api.get<AdminSummary>("/admin/dashboard/summary", { query: periodQuery(params) }),
  activity: (params?: { from?: string; to?: string }) =>
    api.get<ActivityData>("/admin/dashboard/activity", { query: periodQuery(params) }),
  performance: (params?: { from?: string; to?: string }) =>
    api.get<PerformanceMetrics>("/admin/dashboard/performance", { query: periodQuery(params) }),
  errors: (params?: { from?: string; to?: string }) =>
    api.get<ApiErrorLog[]>("/admin/dashboard/errors", { query: periodQuery(params) }),
  integrations: () => api.get<IntegrationStatus[]>("/admin/dashboard/integrations"),
  users: (limit = 50) => api.get<AdminUser[]>("/admin/dashboard/users", { query: { limit } }),
  transactions: (params?: { from?: string; to?: string }) =>
    api.get<CashFlowPoint[]>("/admin/dashboard/transactions", { query: periodQuery(params) }),
  categories: (params?: { from?: string; to?: string }) =>
    api.get<CategoryPoint[]>("/admin/dashboard/categories", { query: periodQuery(params) }),
};
