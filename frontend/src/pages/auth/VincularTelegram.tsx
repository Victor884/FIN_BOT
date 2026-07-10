import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate } from "react-router-dom";
import { useState } from "react";
import { Eye, EyeOff, Loader2, MessageCircle } from "lucide-react";
import { toast } from "sonner";
import { AuthShell } from "@/components/common/AuthShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { telegramLinkSchema, type TelegramLinkForm } from "@/schemas/auth";
import { authApi } from "@/api/auth";
import { ApiError } from "@/api/client";
import { useAuth } from "@/contexts/AuthContext";

export default function VincularTelegram() {
  const navigate = useNavigate();
  const { refresh } = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const form = useForm<TelegramLinkForm>({
    resolver: zodResolver(telegramLinkSchema),
    defaultValues: { code: "", email: "", password: "", confirmPassword: "" },
  });

  const onSubmit = async (values: TelegramLinkForm) => {
    try {
      await authApi.telegramLink({
        code: values.code.trim(),
        email: values.email,
        password: values.password,
      });
      await refresh();
      toast.success("Conta vinculada com sucesso!");
      navigate("/app", { replace: true });
    } catch (err) {
      const status = err instanceof ApiError ? err.status : 0;
      const message = err instanceof ApiError ? err.message : "Falha ao vincular. Tente novamente.";
      const friendly =
        status === 404
          ? "Código inválido."
          : status === 410
            ? "Código expirado. Gere um novo pelo bot."
            : status === 409
              ? "Este código já foi utilizado ou o e-mail já está cadastrado."
              : message;
      toast.error(friendly);
    }
  };

  return (
    <AuthShell
      title="Vincular conta do Telegram"
      subtitle="Conecte a conta criada pelo bot ao painel."
      footer={
        <div className="text-muted-foreground">
          Já vinculou?{" "}
          <Link to="/login" className="font-medium text-primary hover:underline">
            Entrar
          </Link>
        </div>
      }
    >
      <div className="rounded-lg border border-border bg-muted/40 p-4 text-sm">
        <div className="flex items-center gap-2 font-medium">
          <MessageCircle className="h-4 w-4 text-primary" /> Como obter o código
        </div>
        <ol className="mt-2 list-decimal space-y-1 pl-5 text-muted-foreground">
          <li>Abra o bot FIN_BOT no Telegram.</li>
          <li>
            Envie o comando <code className="rounded bg-background px-1">/vincular</code>.
          </li>
          <li>Copie o código temporário que o bot enviar.</li>
          <li>Informe abaixo junto com o e-mail e senha desejados.</li>
        </ol>
      </div>

      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <div className="space-y-2">
          <Label htmlFor="code">Código de vinculação</Label>
          <Input
            id="code"
            placeholder="ex.: 9F3K-72A"
            autoCapitalize="characters"
            {...form.register("code")}
          />
          {form.formState.errors.code && (
            <p className="text-xs text-destructive">{form.formState.errors.code.message}</p>
          )}
        </div>
        <div className="space-y-2">
          <Label htmlFor="email">E-mail</Label>
          <Input id="email" type="email" autoComplete="email" {...form.register("email")} />
          {form.formState.errors.email && (
            <p className="text-xs text-destructive">{form.formState.errors.email.message}</p>
          )}
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Senha</Label>
          <div className="relative">
            <Input
              id="password"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
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
        <div className="space-y-2">
          <Label htmlFor="confirmPassword">Confirmar senha</Label>
          <Input
            id="confirmPassword"
            type={showPassword ? "text" : "password"}
            autoComplete="new-password"
            {...form.register("confirmPassword")}
          />
          {form.formState.errors.confirmPassword && (
            <p className="text-xs text-destructive">
              {form.formState.errors.confirmPassword.message}
            </p>
          )}
        </div>
        <Button type="submit" className="w-full" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Vincular conta
        </Button>
      </form>
    </AuthShell>
  );
}
