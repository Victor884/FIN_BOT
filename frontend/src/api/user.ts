import { api } from "./client";

export type Money = number | string;

export interface DashboardSummary {
  start_date: string;
  end_date: string;
  income: Money;
  expenses: Money;
  balance: Money;
  transaction_count: number;
  daily_expense_average: Money;
  largest_expense: Money;
  top_expense_category: string | null;
  pending_expenses: Money;
  previous_period_balance: Money;
  balance_change_percent: Money | null;
}

export interface CashFlowPoint {
  label: string;
  income: Money;
  expenses: Money;
  balance: Money;
  count: number;
}

export interface CategoryPoint {
  category: string;
  amount: Money;
  count: number;
}

export type TransactionType = "income" | "expense" | "transfer" | "adjustment";
export type TransactionStatus = "paid" | "pending" | "received";

export interface Transaction {
  id: string;
  type: TransactionType;
  amount: Money;
  transaction_date: string;
  description: string;
  category: string | null;
  account_from: string | null;
  account_to: string | null;
  payment_method: string | null;
  status: TransactionStatus;
  source: string;
  sheets_synced: boolean;
  needs_confirmation: boolean;
  is_recurring: boolean;
  created_at: string;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface TransactionFilters {
  q?: string;
  from?: string;
  to?: string;
  type?: TransactionType | "all";
  category?: string;
  status?: TransactionStatus | "all";
  page?: number;
  page_size?: number;
  sort?: string;
}

const periodQuery = (params?: { from?: string; to?: string }) => ({
  start_date: params?.from,
  end_date: params?.to,
});

export const userApi = {
  summary: (params?: { from?: string; to?: string }) =>
    api.get<DashboardSummary>("/me/dashboard/summary", { query: periodQuery(params) }),
  cashFlow: (params?: { from?: string; to?: string }) =>
    api.get<CashFlowPoint[]>("/me/dashboard/cash-flow", { query: periodQuery(params) }),
  categories: (params?: { from?: string; to?: string }) =>
    api.get<CategoryPoint[]>("/me/dashboard/categories", { query: periodQuery(params) }),
  transactions: (filters?: TransactionFilters) =>
    api.get<Paginated<Transaction>>("/me/transactions", {
      query: {
        search: filters?.q,
        start_date: filters?.from,
        end_date: filters?.to,
        type: filters?.type === "all" ? undefined : filters?.type,
        category: filters?.category,
        status: filters?.status === "all" ? undefined : filters?.status,
        page: filters?.page,
        page_size: filters?.page_size,
        sort: filters?.sort,
      },
    }),
  transaction: (id: string) => api.get<Transaction>(`/me/transactions/${id}`),
  pending: (page = 1, pageSize = 25) =>
    api.get<Paginated<Transaction>>("/me/pending-transactions", {
      query: { page, page_size: pageSize },
    }),
  export: (params: { from?: string; to?: string }) =>
    api.get<Blob>("/me/export", {
      query: periodQuery(params),
      raw: true,
    }),
};
