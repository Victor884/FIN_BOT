import { LayoutDashboard, Receipt, AlertTriangle, FileBarChart, Settings } from "lucide-react";
import { DashboardShell, type NavItem } from "./DashboardShell";

const items: NavItem[] = [
  { label: "Visão geral", to: "/app", icon: LayoutDashboard, end: true },
  { label: "Transações", to: "/app/transacoes", icon: Receipt },
  { label: "Pendências", to: "/app/pendencias", icon: AlertTriangle },
  { label: "Relatórios", to: "/app/relatorios", icon: FileBarChart },
  { label: "Configurações", to: "/app/configuracoes", icon: Settings },
];

export function AppLayout() {
  return <DashboardShell brand="FIN_BOT" areaBadge="Área do usuário" items={items} />;
}
