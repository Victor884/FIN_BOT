import { useQuery } from "@tanstack/react-query";
import { ArrowDownRight, ArrowUpRight, Receipt, Wallet, AlertTriangle } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { MetricCard } from "@/components/common/MetricCard";
import { RequestErrorAlert } from "@/components/common/RequestErrorAlert";
import { userApi } from "@/api/user";
import { brl } from "@/lib/format";

export default function Dashboard() {
  const summary = useQuery({
    queryKey: ["me", "summary"],
    queryFn: () => userApi.summary(),
  });

  const s = summary.data;

  return (
    <>
      <PageHeader
        title="Visão geral"
        description="Acompanhe seu saldo, receitas e despesas processadas pelo FIN_BOT."
      />
      {summary.error && (
        <RequestErrorAlert error={summary.error} onRetry={() => summary.refetch()} />
      )}

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Saldo atual"
          value={s ? brl(s.balance) : "—"}
          icon={Wallet}
          tone={s && Number(s.balance) < 0 ? "danger" : "success"}
          loading={summary.isLoading}
        />
        <MetricCard
          label="Receitas"
          value={s ? brl(s.income) : "—"}
          icon={ArrowUpRight}
          tone="success"
          loading={summary.isLoading}
        />
        <MetricCard
          label="Despesas"
          value={s ? brl(s.expenses) : "—"}
          icon={ArrowDownRight}
          tone="danger"
          loading={summary.isLoading}
        />
        <MetricCard
          label="Transações"
          value={s ? s.transaction_count.toLocaleString("pt-BR") : "—"}
          hint={
            s && Number(s.pending_expenses) > 0 ? `${brl(s.pending_expenses)} pendentes` : undefined
          }
          icon={Receipt}
          tone="info"
          loading={summary.isLoading}
        />
      </section>

      <section className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <MetricCard
          label="Resultado do período"
          value={s ? brl(s.balance) : "—"}
          tone={s && Number(s.balance) < 0 ? "danger" : "success"}
          loading={summary.isLoading}
        />
        <MetricCard
          label="Pendências"
          value={s ? brl(s.pending_expenses) : "—"}
          icon={AlertTriangle}
          tone="warning"
          loading={summary.isLoading}
        />
        <MetricCard
          label="Maior categoria"
          value={s?.top_expense_category ?? "—"}
          loading={summary.isLoading}
        />
      </section>

      <p className="mt-8 text-xs text-muted-foreground">
        Gráficos de fluxo de caixa e categorias serão adicionados na Etapa 2 usando os endpoints
        <code className="mx-1 rounded bg-muted px-1">/me/dashboard/cash-flow</code> e
        <code className="mx-1 rounded bg-muted px-1">/me/dashboard/categories</code>.
      </p>
    </>
  );
}
