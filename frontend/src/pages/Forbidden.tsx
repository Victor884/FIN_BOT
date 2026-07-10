import { Link } from "react-router-dom";
import { ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";

export default function Forbidden() {
  const { user } = useAuth();
  const homePath = user?.role === "ADMIN" ? "/admin" : "/app";
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md rounded-2xl border border-border bg-card p-8 text-center shadow-sm">
        <ShieldAlert className="mx-auto h-10 w-10 text-warning" />
        <h1 className="mt-4 text-2xl font-semibold">Acesso negado</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Você não possui permissão para acessar esta área. Fale com um administrador se acreditar
          que isso é um erro.
        </p>
        <Button asChild className="mt-6">
          <Link to={homePath}>Voltar ao painel</Link>
        </Button>
      </div>
    </div>
  );
}
