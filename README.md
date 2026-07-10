# FIN_BOT

Assistente financeiro pessoal com Telegram, FastAPI, SQLAlchemy, Google Sheets opcional e uma API autenticada para dashboards externos como o Lovable.

## Arquitetura

```text
Telegram -> Webhook FastAPI -> Parser local -> IA opcional -> Validacao -> Banco
                                                        \-> Sheets em background

Lovable -> JWT -> API /api/v1 -> Servicos de dashboard -> Banco
```

O parser local atende mensagens previsiveis. A IA so e acionada quando o resultado local esta incompleto, ambiguo ou abaixo do limite de confianca. O Google Sheets roda depois da resposta do Telegram.

## Modulos

- `api`: rotas, dependencias, schemas, CORS e tratamento de erros.
- `core`: configuracao, seguranca, logs e retencao de metricas.
- `db`: modelos, repositorios, engine compartilhada e sessoes.
- `parser`: regras locais e fallback opcional por IA.
- `services`: casos de uso financeiros, autenticacao e dashboards.
- `telegram`: contratos e cliente HTTP da Bot API.
- `sheets`: sincronizacao e estrutura da planilha.
- `migrations`: migracoes Alembic portaveis para SQLite e PostgreSQL.

## Execucao Local

```powershell
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
python -m alembic upgrade head
python -m uvicorn finbot.api.app:app --reload
```

Verificacao:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health/ready
```

Documentacao interativa: `http://127.0.0.1:8000/docs`.

## Endpoints

Infraestrutura:

- `GET /health`
- `GET /health/live`
- `GET /health/ready`
- `GET /api/v1/config/public`

Telegram:

- `POST /telegram/webhook`

Autenticacao web:

- `POST /api/v1/auth/register` quando habilitado
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/telegram-link`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`

Dashboard do usuario autenticado:

- `GET /api/v1/me/dashboard/summary`
- `GET /api/v1/me/dashboard/cash-flow`
- `GET /api/v1/me/dashboard/categories`
- `GET /api/v1/me/transactions`
- `GET /api/v1/me/transactions/{transaction_id}`
- `GET /api/v1/me/pending-transactions`
- `GET /api/v1/me/export`

Dashboard administrativo, sempre com `role=ADMIN`:

- `GET /api/v1/admin/dashboard/summary`
- `GET /api/v1/admin/dashboard/activity`
- `GET /api/v1/admin/dashboard/users`
- `GET /api/v1/admin/dashboard/transactions`
- `GET /api/v1/admin/dashboard/categories`
- `GET /api/v1/admin/dashboard/performance`
- `GET /api/v1/admin/dashboard/errors`
- `GET /api/v1/admin/dashboard/integrations`

## Vinculo Telegram E Lovable

1. O usuario envia `/vincular` ao bot.
2. O bot gera um codigo aleatorio valido por 10 minutos e por um unico uso.
3. O Lovable envia codigo, e-mail e senha para `POST /api/v1/auth/telegram-link`.
4. A API retorna access token curto e refresh token rotativo para o mesmo usuario do Telegram.
5. O Lovable usa `Authorization: Bearer ACCESS_TOKEN`; nunca envia `telegram_user_id`.

## Lovable

Configure no projeto Lovable durante o build:

```env
VITE_FINBOT_API_URL=https://seu-servico.onrender.com
```

Centralize a URL em um unico cliente HTTP e acrescente `/api/v1` nas chamadas. Variaveis `VITE_*` sao incorporadas no build; altere a configuracao e publique novamente quando a URL mudar. A API permite apenas origens listadas em `CORS_ALLOWED_ORIGINS`.

## URL Estavel

O arquivo `render.yaml` prepara um web service com URL HTTPS fixa. Depois do deploy:

```powershell
python scripts/set_telegram_webhook.py --url https://seu-servico.onrender.com
```

LocalTunnel fica restrito ao desenvolvimento. Para iniciar o tunel e atualizar o webhook automaticamente:

```powershell
python scripts/dev_tunnel.py
```

O token nao e impresso pelo script.

## Qualidade

```powershell
python -m pytest
python -m ruff check .
python -m compileall src tests scripts
```

Detalhes de configuracao e deploy: [docs/deploy.md](docs/deploy.md). Arquitetura: [docs/architecture.md](docs/architecture.md).
