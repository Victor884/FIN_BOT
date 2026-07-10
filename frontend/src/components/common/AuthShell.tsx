import type { ReactNode } from "react";
import { Sprout } from "lucide-react";

interface Props {
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
}

export function AuthShell({ title, subtitle, children, footer }: Props) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto grid min-h-screen max-w-6xl grid-cols-1 lg:grid-cols-2">
        <aside className="relative hidden overflow-hidden bg-gradient-to-br from-primary/20 via-primary/5 to-background p-10 lg:flex lg:flex-col lg:justify-between">
          <div className="flex items-center gap-2 text-lg font-semibold">
            <Sprout className="h-6 w-6 text-primary" />
            FIN_BOT
          </div>
          <div>
            <h2 className="text-3xl font-semibold tracking-tight">
              Sua gestão financeira, direto do Telegram.
            </h2>
            <p className="mt-3 max-w-md text-sm text-muted-foreground">
              Registre lançamentos por mensagem, acompanhe categorias em tempo real e monitore o
              funcionamento do bot em um painel único.
            </p>
          </div>
          <div className="text-xs text-muted-foreground">
            © {new Date().getFullYear()} FIN_BOT · Painel de gestão
          </div>
        </aside>
        <main className="flex items-center justify-center p-6 sm:p-10">
          <div className="w-full max-w-md space-y-6">
            <div className="flex items-center gap-2 text-lg font-semibold lg:hidden">
              <Sprout className="h-5 w-5 text-primary" />
              FIN_BOT
            </div>
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
              {subtitle && <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>}
            </div>
            {children}
            {footer && <div className="border-t border-border pt-4 text-sm">{footer}</div>}
          </div>
        </main>
      </div>
    </div>
  );
}
