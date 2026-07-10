import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { LogOut, Menu, Moon, Sprout, Sun, X, ChevronDown, type LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/contexts/AuthContext";
import { useTheme } from "@/contexts/ThemeContext";
import { cn } from "@/lib/utils";
import { API_URL } from "@/api/client";

export interface NavItem {
  label: string;
  to: string;
  icon: LucideIcon;
  end?: boolean;
}

interface Props {
  brand: string;
  items: NavItem[];
  areaBadge?: string;
}

function NavList({ items, onNavigate }: { items: NavItem[]; onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-1">
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
              isActive && "bg-accent text-foreground font-medium",
            )
          }
        >
          <item.icon className="h-4 w-4" />
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}

function Breadcrumb({ items }: { items: NavItem[] }) {
  const location = useLocation();
  const current = items.find((i) =>
    i.end ? location.pathname === i.to : location.pathname.startsWith(i.to),
  );
  return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground">
      <Link to={items[0]?.to ?? "/"} className="hover:text-foreground">
        Início
      </Link>
      {current && current.to !== items[0]?.to && (
        <>
          <span>/</span>
          <span className="text-foreground">{current.label}</span>
        </>
      )}
    </div>
  );
}

export function DashboardShell({ brand, items, areaBadge }: Props) {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const [confirmLogout, setConfirmLogout] = useState(false);

  const initials = (user?.name || user?.email || "?")
    .split(" ")
    .map((s) => s[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className="hidden w-64 flex-col border-r border-border bg-card/50 lg:flex">
        <SidebarInner brand={brand} items={items} areaBadge={areaBadge} />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-background/95 px-4 backdrop-blur">
          <div className="flex items-center gap-3">
            <MobileNav brand={brand} items={items} areaBadge={areaBadge} />
            <Breadcrumb items={items} />
          </div>
          <div className="flex items-center gap-2">
            <ApiStatusBadge />
            <Button variant="ghost" size="icon" onClick={toggle} aria-label="Alternar tema">
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="gap-2 px-2">
                  <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/15 text-xs font-semibold text-primary">
                    {initials}
                  </span>
                  <span className="hidden text-sm md:inline">{user?.name || user?.email}</span>
                  <ChevronDown className="hidden h-4 w-4 md:inline" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel>
                  <div className="text-sm font-medium">{user?.name}</div>
                  <div className="text-xs text-muted-foreground">{user?.email}</div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={() => setConfirmLogout(true)}>
                  <LogOut className="mr-2 h-4 w-4" /> Sair
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-7xl">
            <Outlet />
          </div>
        </main>
      </div>

      <LogoutConfirm
        open={confirmLogout}
        onOpenChange={setConfirmLogout}
        onConfirm={() => {
          setConfirmLogout(false);
          void logout();
        }}
      />
    </div>
  );
}

function SidebarInner({ brand, items, areaBadge }: Props & { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-border px-5 py-4">
        <Sprout className="h-5 w-5 text-primary" />
        <div className="flex flex-col leading-tight">
          <span className="text-sm font-semibold">{brand}</span>
          {areaBadge && (
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
              {areaBadge}
            </span>
          )}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-3">
        <NavList items={items} />
      </div>
      <div className="border-t border-border p-3 text-[11px] text-muted-foreground">
        API: <span className="font-mono">{API_URL || "não configurada"}</span>
      </div>
    </div>
  );
}

function MobileNav(props: Props) {
  const [open, setOpen] = useState(false);
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Abrir menu">
          <Menu className="h-5 w-5" />
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="w-72 p-0">
        <div className="flex h-14 items-center justify-between border-b px-4">
          <span className="text-sm font-semibold">{props.brand}</span>
          <Button variant="ghost" size="icon" onClick={() => setOpen(false)} aria-label="Fechar">
            <X className="h-4 w-4" />
          </Button>
        </div>
        <div className="p-3" onClick={() => setOpen(false)}>
          <NavList items={props.items} />
        </div>
      </SheetContent>
    </Sheet>
  );
}

function ApiStatusBadge() {
  const [online, setOnline] = useState<boolean | null>(null);
  useEffect(() => {
    if (!API_URL) {
      setOnline(false);
      return;
    }
    const ctrl = new AbortController();
    fetch(`${API_URL}/api/v1/config/public`, { method: "GET", signal: ctrl.signal })
      .then((r) => setOnline(r.ok))
      .catch(() => setOnline(false));
    return () => ctrl.abort();
  }, []);
  return (
    <div className="hidden items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs md:flex">
      <span
        className={cn(
          "h-2 w-2 rounded-full",
          online === null ? "bg-muted-foreground" : online ? "bg-primary" : "bg-destructive",
        )}
      />
      API {online === null ? "verificando" : online ? "online" : "indisponível"}
    </div>
  );
}

function LogoutConfirm({
  open,
  onOpenChange,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onConfirm: () => void;
}) {
  if (!open) return null;
  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={() => onOpenChange(false)}
    >
      <div
        className="w-full max-w-sm rounded-lg border border-border bg-card p-6 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-semibold">Sair da conta?</h3>
        <p className="mt-2 text-sm text-muted-foreground">
          Você precisará informar suas credenciais novamente para entrar.
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button variant="destructive" onClick={onConfirm}>
            Sair
          </Button>
        </div>
      </div>
    </div>
  );
}

export type { Props as DashboardShellProps };
export function ChildOutlet(_: { children?: ReactNode }) {
  return null;
}
