import {
  LayoutDashboard,
  Users,
  Receipt,
  Tags,
  Activity,
  Gauge,
  AlertOctagon,
  Plug,
  Settings,
} from "lucide-react";
import { DashboardShell, type NavItem } from "./DashboardShell";

const items: NavItem[] = [
  { label: "Visão geral", to: "/admin", icon: LayoutDashboard, end: true },
  { label: "Usuários", to: "/admin/usuarios", icon: Users },
  { label: "Transações", to: "/admin/transacoes", icon: Receipt },
  { label: "Categorias", to: "/admin/categorias", icon: Tags },
  { label: "Atividade", to: "/admin/atividade", icon: Activity },
  { label: "Performance", to: "/admin/performance", icon: Gauge },
  { label: "Erros", to: "/admin/erros", icon: AlertOctagon },
  { label: "Integrações", to: "/admin/integracoes", icon: Plug },
  { label: "Configurações", to: "/admin/configuracoes", icon: Settings },
];

export function AdminLayout() {
  return <DashboardShell brand="FIN_BOT" areaBadge="Administração" items={items} />;
}
