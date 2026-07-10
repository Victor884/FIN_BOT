import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useState } from "react";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { AuthShell } from "@/components/common/AuthShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { loginSchema, type LoginForm } from "@/schemas/auth";
import { useAuth } from "@/contexts/AuthContext";
import { ApiError } from "@/api/client";
import { PageSkeleton } from "@/components/common/PageSkeleton";

export default function Login() {
  const { login, isAuthenticated, isLoading, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation() as { state?: { from?: string } };
  const [showPassword, setShowPassword] = useState(false);
  const form = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "", remember: true },
  });

  if (isLoading) return <PageSkeleton />;
  if (isAuthenticated) {
    return <Navigate to={user?.role === "ADMIN" ? "/admin" : "/app"} replace />;
  }

  const onSubmit = async (values: LoginForm) => {
    try {
      const me = await login({ email: values.email, password: values.password }, values.remember);
      toast.success(`Bem-vindo, ${me.name || me.email}`);
      const target = location.state?.from ?? (me.role === "ADMIN" ? "/admin" : "/app");
      navigate(target, { replace: true });
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Falha ao autenticar. Tente novamente.";
      toast.error(message);
    }
  };

  return (
    <AuthShell
      title="Acesse sua conta"
      subtitle="Entre para gerenciar suas transações do FIN_BOT."
      footer={
        <div className="flex flex-col gap-1 text-muted-foreground">
          <span>
            Ainda não tem conta?{" "}
            <Link to="/cadastro" className="font-medium text-primary hover:underline">
              Criar conta
            </Link>
          </span>
          <span>
            Já usa o bot?{" "}
            <Link to="/vincular-telegram" className="font-medium text-primary hover:underline">
              Vincular conta do Telegram
            </Link>
          </span>
        </div>
      }
    >
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <div className="space-y-2">
          <Label htmlFor="email">E-mail</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            placeholder="voce@exemplo.com"
            {...form.register("email")}
          />
          {form.formState.errors.email && (
            <p className="text-xs text-destructive">{form.formState.errors.email.message}</p>
          )}
        </div>
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label htmlFor="password">Senha</Label>
          </div>
          <div className="relative">
            <Input
              id="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              placeholder="••••••••"
              {...form.register("password")}
            />
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              className="absolute inset-y-0 right-2 my-auto flex h-8 w-8 items-center justify-center rounded text-muted-foreground hover:text-foreground"
              aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}
            >
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
          {form.formState.errors.password && (
            <p className="text-xs text-destructive">{form.formState.errors.password.message}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Checkbox
            id="remember"
            checked={form.watch("remember")}
            onCheckedChange={(v) => form.setValue("remember", Boolean(v))}
          />
          <Label htmlFor="remember" className="text-sm font-normal">
            Lembrar de mim neste dispositivo
          </Label>
        </div>
        <Button type="submit" className="w-full" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Entrar
        </Button>
      </form>
    </AuthShell>
  );
}
