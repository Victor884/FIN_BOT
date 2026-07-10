import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { useState } from "react";
import { Eye, EyeOff, Loader2, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import { AuthShell } from "@/components/common/AuthShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { registerSchema, type RegisterForm } from "@/schemas/auth";
import { authApi } from "@/api/auth";
import { ApiError } from "@/api/client";

export default function Cadastro() {
  const navigate = useNavigate();
  const [showPassword, setShowPassword] = useState(false);

  const config = useQuery({
    queryKey: ["public-config"],
    queryFn: () => authApi.publicConfig(),
    retry: 1,
  });

  const registrationEnabled = config.data?.registration_enabled ?? true;
  const disabled = !config.isLoading && !registrationEnabled;

  const form = useForm<RegisterForm>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      name: "",
      email: "",
      password: "",
      confirmPassword: "",
      accept: false as unknown as true,
    },
  });

  const onSubmit = async (values: RegisterForm) => {
    try {
      await authApi.register({ name: values.name, email: values.email, password: values.password });
      toast.success("Conta criada com sucesso! Faça login para continuar.");
      navigate("/login", { replace: true });
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Não foi possível criar a conta.";
      toast.error(message);
    }
  };

  return (
    <AuthShell
      title="Criar conta"
      subtitle="Cadastre-se para começar a usar o FIN_BOT."
      footer={
        <div className="text-muted-foreground">
          Já possui conta?{" "}
          <Link to="/login" className="font-medium text-primary hover:underline">
            Entrar
          </Link>
          {" · "}
          <Link to="/vincular-telegram" className="font-medium text-primary hover:underline">
            Vincular Telegram
          </Link>
        </div>
      }
    >
      {disabled && (
        <Alert variant="default" className="border-warning/40 bg-warning/10">
          <AlertTriangle className="h-4 w-4 text-warning" />
          <AlertTitle>Cadastros temporariamente indisponíveis</AlertTitle>
          <AlertDescription>
            No momento, novos cadastros pelo painel estão desativados. Você ainda pode vincular uma
            conta existente criada pelo bot no Telegram.
          </AlertDescription>
        </Alert>
      )}

      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <fieldset disabled={disabled} className="space-y-4 disabled:opacity-60">
          <div className="space-y-2">
            <Label htmlFor="name">Nome</Label>
            <Input
              id="name"
              autoComplete="name"
              placeholder="Seu nome"
              {...form.register("name")}
            />
            {form.formState.errors.name && (
              <p className="text-xs text-destructive">{form.formState.errors.name.message}</p>
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
          <div className="flex items-start gap-2">
            <Checkbox
              id="accept"
              checked={form.watch("accept") as unknown as boolean}
              onCheckedChange={(v) =>
                form.setValue("accept", Boolean(v) as unknown as true, { shouldValidate: true })
              }
            />
            <Label htmlFor="accept" className="text-sm font-normal leading-snug">
              Li e aceito os termos de uso e a política de privacidade.
            </Label>
          </div>
          {form.formState.errors.accept && (
            <p className="text-xs text-destructive">{form.formState.errors.accept.message}</p>
          )}
          <Button
            type="submit"
            className="w-full"
            disabled={form.formState.isSubmitting || disabled}
          >
            {form.formState.isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Criar conta
          </Button>
        </fieldset>
      </form>
    </AuthShell>
  );
}
