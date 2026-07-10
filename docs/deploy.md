# Deploy E Integracao Com Lovable

## Variaveis Obrigatorias

Backend:

```env
APP_ENV=production
DATABASE_URL=postgresql+psycopg://usuario:senha@host:5432/finbot
JWT_SECRET=valor-aleatorio-com-pelo-menos-32-caracteres
CORS_ALLOWED_ORIGINS=https://seu-projeto.lovable.app
TELEGRAM_BOT_TOKEN=definido-como-secret
TELEGRAM_WEBHOOK_SECRET=definido-como-secret
```

Opcionais:

```env
GOOGLE_SHEETS_SPREADSHEET_ID=
GOOGLE_SERVICE_ACCOUNT_FILE=
AI_ENABLED=false
OPENAI_API_KEY=
ADMIN_EMAIL=
ADMIN_PASSWORD=
AUTH_ALLOW_REGISTRATION=false
```

Nunca coloque credenciais em Git, `render.yaml`, codigo TypeScript ou logs.

## Banco

Localmente, use `sqlite:///./data/finbot.sqlite3`. Em um host gratuito com filesystem efemero, SQLite perde alteracoes quando a instancia reinicia ou e recriada. Para demonstracao remota, configure PostgreSQL externo em `DATABASE_URL`.

O PostgreSQL gratuito do Render expira depois de 30 dias. Ele serve para testes temporarios, nao para armazenamento permanente. Para uso real, escolha um PostgreSQL persistente e mantenha backups.

Migracoes:

```powershell
python -m alembic upgrade head
python -m alembic current
```

A aplicacao tambem aplica migracoes pendentes na inicializacao.

## Render

1. Conecte o repositorio GitHub ao Render.
2. Crie o servico pelo `render.yaml`.
3. Preencha `DATABASE_URL`, `CORS_ALLOWED_ORIGINS` e `PUBLIC_API_URL`.
4. Adicione Telegram, Google e OpenAI como secrets quando usados.
5. Aguarde `GET /health/ready` retornar `database=available`.
6. Copie a URL fixa `https://NOME.onrender.com`.
7. Configure o webhook:

```powershell
python scripts/set_telegram_webhook.py --url https://NOME.onrender.com
```

8. Confirme no Telegram com `/ajuda` e uma movimentacao simples.

O Render fornece subdominio HTTPS fixo para cada web service. Instancias gratuitas podem suspender por inatividade, causando uma primeira resposta mais lenta apos o periodo ocioso.

## Lovable

No ambiente do Lovable:

```env
VITE_FINBOT_API_URL=https://NOME.onrender.com
```

No cliente HTTP central:

- remova a barra final da base URL;
- use prefixo `/api/v1`;
- envie `Authorization: Bearer <token>`;
- use timeout e `AbortController`;
- em `401`, tente uma unica renovacao e repita a requisicao;
- em `403`, esconda areas administrativas;
- mostre `request_id` em erros para suporte;
- nao mantenha URL da API dentro de componentes;
- nao envie `user_id` ou `telegram_user_id` nos endpoints `/me`.

Fluxo inicial recomendado:

1. Usuario envia `/vincular` no Telegram.
2. Lovable coleta codigo, e-mail e senha.
3. Chama `POST /api/v1/auth/telegram-link`.
4. Mantem access token apenas durante a sessao e protege o refresh token contra acesso desnecessario.
5. Consulta `GET /api/v1/auth/me` para papel e identidade.
6. Direciona `ADMIN` para `/api/v1/admin/dashboard/*` e `USER` para `/api/v1/me/*`.

## Desenvolvimento Com Tunel Temporario

Com Uvicorn ativo em outra janela:

```powershell
python scripts/dev_tunnel.py
```

O script inicia LocalTunnel, captura a URL e atualiza o webhook automaticamente sem imprimir o token. Esta opcao e apenas para desenvolvimento; o Lovable deve apontar para a URL fixa do deploy.

## Docker

```powershell
docker build -t finbot .
docker run --env-file .env -p 8000:8000 finbot
```

## Validacao

```powershell
python -m pytest
python -m ruff check .
python -m compileall src tests scripts
```
