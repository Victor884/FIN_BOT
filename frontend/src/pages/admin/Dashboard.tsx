import { useQuery } from "@tanstack/react-query";
import {
  Users,
  UserPlus,
  Receipt,
  AlertOctagon,
  Gauge,
  Activity,
  CircleDollarSign,
  Timer,
} from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { MetricCard } from "@/components/common/MetricCard";
import { RequestErrorAlert } from "@/components/common/RequestErrorAlert";
import { adminApi } from "@/api/admin";
import { brl } from "@/lib/format";

export default function AdminDashboard() {
  const summary = useQuery({
    queryKey: ["admin", "summary"],
    queryFn: () => adminApi.summary(),
  });
  const s = summary.data;

  return (
    <>
      <PageHeader title="Visão geral" description="Métricas administrativas do FIN_BOT." />
      {summary.error && (
        <RequestErrorAlert error={summary.error} onRetry={() => summary.refetch()} />
      )}

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Usuários"
          value={s?.users_total ?? "—"}
          icon={Users}
          loading={summary.isLoading}
        />
        <MetricCard
          label="Usuários ativos"
          value={s?.users_active_30d ?? "—"}
          icon={Activity}
          tone="success"
          loading={summary.isLoading}
        />
        <MetricCard
          label="Novos usuários"
          value={s?.new_users ?? "—"}
          icon={UserPlus}
          tone="info"
          loading={summary.isLoading}
        />
        <MetricCard
          label="Transações"
          value={s?.transactions_total ?? "—"}
          icon={Receipt}
          loading={summary.isLoading}
        />
        <MetricCard
          label="Saldo agregado"
          value={s ? brl(s.aggregate_balance) : "—"}
          icon={CircleDollarSign}
          tone="success"
          loading={summary.isLoading}
        />
        <MetricCard
          label="Mensagens processadas"
          value={s?.messages_total ?? "—"}
          icon={Receipt}
          tone="warning"
          loading={summary.isLoading}
        />
        <MetricCard
          label="Taxa de erro"
          value={s ? `${Number(s.error_rate).toFixed(1)}%` : "—"}
          icon={AlertOctagon}
          tone="danger"
          loading={summary.isLoading}
        />
        <MetricCard
          label="Latência média"
          value={s ? `${Math.round(Number(s.response_time_average_ms))} ms` : "—"}
          hint={s ? `Parser: ${Number(s.parser_success_rate).toFixed(1)}%` : undefined}
          icon={Timer}
          tone="info"
          loading={summary.isLoading}
        />
      </section>

      <p className="mt-8 text-xs text-muted-foreground">
        Gráficos detalhados (atividade, performance, erros e integrações) serão adicionados na Etapa
        2 usando <code className="mx-1 rounded bg-muted px-1">/admin/dashboard/*</code>. As rotas e
        a proteção por perfil <code className="mx-1 rounded bg-muted px-1">ADMIN</code> já estão
        ativas.
      </p>

      <div className="mt-6 flex items-center gap-2 rounded-md border border-border bg-card px-4 py-3 text-xs text-muted-foreground">
        <Gauge className="h-4 w-4" /> Latência e taxa de sucesso vêm de{" "}
        <code>/admin/dashboard/summary</code>.
      </div>
    </>
  );
}
