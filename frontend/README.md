# FIN_BOT — Painel Web

Frontend em **React + Vite + TypeScript** para o bot financeiro FIN_BOT
(Telegram). Consome a API FastAPI existente via cliente HTTP centralizado
com controle de sessão JWT (access + refresh), rotas protegidas e áreas
separadas para **USER** e **ADMIN**.

## Stack

- React 19 + TypeScript + Vite 8
- React Router DOM 7
- TanStack Query 5
- React Hook Form + Zod
- Tailwind CSS 4 + shadcn/ui
- Recharts, Lucide, Sonner

## Configuração

Crie um arquivo `.env` (ou `.env.local`) baseado em `.env.example`:

```env
VITE_FINBOT_API_URL=http://127.0.0.1:8000
# ou LocalTunnel:
# VITE_FINBOT_API_URL=https://honest-worlds-smell.loca.lt
```

A URL não deve terminar com `/` — o cliente HTTP monta as rotas com prefixo
`/api/v1` automaticamente.

## Scripts

```powershell
npm.cmd install       # instalar dependências
npm.cmd run dev       # dev server em http://localhost:8080
npm.cmd run build     # build de produção
npm.cmd run preview   # servir build local
npm.cmd run lint      # ESLint
```

## Estrutura

```
src/
  api/            # cliente HTTP + auth/user/admin
  components/     # UI reutilizável (auth, common, ui shadcn)
  contexts/       # AuthContext, ThemeContext
  layouts/        # AppLayout, AdminLayout, DashboardShell
  pages/          # rotas organizadas por área
  schemas/        # validações Zod
  types/          # tipos de domínio
  lib/            # utilitários (format etc.)
```

## Autenticação

- Tokens em `sessionStorage` por padrão. Se "Lembrar de mim" estiver marcado,
  ficam em `localStorage`. A API usa access token curto e refresh token rotativo.
- 401 → tenta renovar via `POST /api/v1/auth/refresh` com
  `{ refresh_token }` uma única vez. Falhou? Sessão é limpa e usuário
  redirecionado para `/login`.
- 403 → toast + redirecionamento para `/403` (via `RoleRoute`).
- Contexto: `useAuth()` em `@/contexts/AuthContext`.

### Ajuste do endpoint de refresh

O contrato assumido em `src/api/client.ts::refreshTokens()` é:

```text
POST /api/v1/auth/refresh
body: { "refresh_token": "..." }
resp: { "success": true, "data": { "access_token": "...", "refresh_token": "..." } }
```

O cliente HTTP central remove o envelope `success/data` automaticamente.

## Groq

O frontend nunca recebe `GROQ_API_KEY`. A chamada autenticada disponível para
uma feature futura é:

```text
POST /api/v1/ai/completions
body: { "prompt": "..." }
```

O cliente está preparado em `src/api/ai.ts`. A chave, modelo, timeout e limites
são configurados exclusivamente no backend.

## Rotas

Públicas: `/login`, `/cadastro`, `/vincular-telegram`, `/403`, `/404`.
Usuário (`USER` ou `ADMIN`): `/app`, `/app/transacoes`, `/app/transacoes/:id`,
`/app/pendencias`, `/app/relatorios`, `/app/configuracoes`.
Admin (`ADMIN`): `/admin`, `/admin/usuarios`, `/admin/transacoes`,
`/admin/categorias`, `/admin/atividade`, `/admin/performance`,
`/admin/erros`, `/admin/integracoes`, `/admin/configuracoes`.

`/` redireciona conforme o perfil autenticado.

## Etapas

**Etapa 1 (atual):** stack, cliente HTTP, AuthContext, refresh token, rotas
protegidas, login, cadastro (com `GET /config/public`), vincular Telegram,
layouts (sidebar recolhível + drawer mobile + tema claro/escuro), dashboards
de USER e ADMIN consumindo `/me/dashboard/summary` e
`/admin/dashboard/summary`. Demais páginas ficam com placeholder documentado.

**Etapa 2:** tabelas de transações (com filtros sincronizados à URL,
paginação, exportação), pendências, relatórios, dashboards admin completos
(atividade, performance, erros, integrações) e ações ainda não previstas na
API ficarão desabilitadas com tooltip.

## Endpoints ainda não disponíveis

Ações abaixo não têm endpoint conhecido — a UI as expõe desabilitadas
com tooltip “Funcionalidade ainda não disponível na API”:

- editar/excluir transação;
- confirmar/descartar pendência;
- bloquear/excluir usuário;
- editar categorias;
- testar integrações.
