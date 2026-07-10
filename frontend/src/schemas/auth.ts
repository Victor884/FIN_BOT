import { z } from "zod";

export const loginSchema = z.object({
  email: z.string().trim().min(1, "Informe o e-mail").email("E-mail inválido").max(255),
  password: z.string().min(1, "Informe a senha").max(200),
  remember: z.boolean().optional(),
});
export type LoginForm = z.infer<typeof loginSchema>;

export const registerSchema = z
  .object({
    name: z.string().trim().min(2, "Informe seu nome").max(120),
    email: z.string().trim().email("E-mail inválido").max(255),
    password: z.string().min(8, "Mínimo de 8 caracteres").max(200),
    confirmPassword: z.string().min(1, "Confirme a senha"),
    accept: z.literal(true, { errorMap: () => ({ message: "Você precisa aceitar os termos" }) }),
  })
  .refine((v) => v.password === v.confirmPassword, {
    path: ["confirmPassword"],
    message: "As senhas não coincidem",
  });
export type RegisterForm = z.infer<typeof registerSchema>;

export const telegramLinkSchema = z
  .object({
    code: z.string().trim().min(4, "Código inválido").max(64),
    email: z.string().trim().email("E-mail inválido").max(255),
    password: z.string().min(8, "Mínimo de 8 caracteres").max(200),
    confirmPassword: z.string().min(1, "Confirme a senha"),
  })
  .refine((v) => v.password === v.confirmPassword, {
    path: ["confirmPassword"],
    message: "As senhas não coincidem",
  });
export type TelegramLinkForm = z.infer<typeof telegramLinkSchema>;
