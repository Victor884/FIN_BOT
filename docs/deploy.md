# Deploy E Configuracao

Este guia cobre as credenciais necessarias, configuracao local, deploy e testes manuais.

## Credenciais Necessarias

### Obrigatorias

1. `TELEGRAM_BOT_TOKEN`
   - Criado no Telegram pelo BotFather.
   - Usado para configurar o webhook e, futuramente, enviar mensagens pelo bot.

2. `TELEGRAM_WEBHOOK_SECRET`
   - Texto secreto criado por voce.
   - Deve ser enviado pelo Telegram no header `X-Telegram-Bot-Api-Secret-Token`.
   - Exemplo de formato: uma frase aleatoria longa ou UUID.

3. `DATABASE_URL`
   - Banco usado pelo backend.
   - Para MVP local: `sqlite:///./data/finbot.sqlite3`.
   - Para producao: prefira PostgreSQL gerenciado.

### Necessarias Para Google Sheets

4. `GOOGLE_SHEETS_SPREADSHEET_ID`
   - ID da planilha.
   - Fica na URL do Google Sheets:
     `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit`.

5. `GOOGLE_SERVICE_ACCOUNT_FILE`
   - Caminho para o arquivo JSON da Service Account.
   - Local: exemplo `./credentials/google-service-account.json`.
   - Em deploy, prefira montar o arquivo como secret ou usar storage seguro da plataforma.

### Opcionais Para IA

6. `OPENAI_API_KEY`
   - Necessaria apenas se `AI_ENABLED=true`.
   - Nao e incluida pelo ChatGPT Plus; a API usa chave propria da plataforma OpenAI.

7. `OPENAI_MODEL`
   - Padrao: `gpt-5.4-nano`.

8. `OPENAI_BASE_URL`
   - Padrao: `https://api.openai.com/v1`.

## Criar Bot No Telegram

1. Abra o Telegram.
2. Converse com `@BotFather`.
3. Envie `/newbot`.
4. Escolha nome e username.
5. Copie o token gerado para `TELEGRAM_BOT_TOKEN`.

## Criar Planilha E Service Account

1. Crie uma planilha no Google Sheets.
2. Copie o ID da planilha para `GOOGLE_SHEETS_SPREADSHEET_ID`.
3. No Google Cloud, crie um projeto.
4. Ative a Google Sheets API.
5. Crie uma Service Account.
6. Gere uma chave JSON.
7. Compartilhe a planilha com o email da Service Account como editor.
8. Salve o caminho do JSON em `GOOGLE_SERVICE_ACCOUNT_FILE`.

## Configuracao Local

1. Copie `.env.example` para `.env`.
2. Preencha as variaveis necessarias.
3. Instale o projeto:

```bash
python -m pip install -e .[dev]
```

4. Rode as verificacoes:

```bash
python -m pytest
python -m ruff check .
python -m compileall src tests
```

5. Inicie a API:

```bash
python -m uvicorn finbot.api.app:app --reload
```

6. Teste o health check:

```bash
curl http://127.0.0.1:8000/health
```

## Teste Manual Do Webhook Local

Com a API rodando, envie:

```bash
curl -X POST http://127.0.0.1:8000/telegram/webhook \
  -H "Content-Type: application/json" \
  -H "X-Telegram-Bot-Api-Secret-Token: seu-segredo" \
  -d "{\"update_id\":1,\"message\":{\"message_id\":1,\"date\":1783526400,\"chat\":{\"id\":123,\"type\":\"private\"},\"text\":\"Gastei R$ 45 no mercado hoje\"}}"
```

## Configurar Webhook Do Telegram

Depois do deploy, use a URL publica:

```bash
curl "https://api.telegram.org/botTELEGRAM_BOT_TOKEN/setWebhook?url=https://SUA-URL/telegram/webhook&secret_token=TELEGRAM_WEBHOOK_SECRET"
```

Substitua:

- `TELEGRAM_BOT_TOKEN` pelo token do BotFather.
- `https://SUA-URL` pela URL publica do deploy.
- `TELEGRAM_WEBHOOK_SECRET` pelo segredo configurado no backend.

## Deploy No Render

1. Conecte o repositorio GitHub no Render.
2. Use o `render.yaml` ou configure manualmente:
   - Build command: `python -m pip install .`
   - Start command: `python -m uvicorn finbot.api.app:app --host 0.0.0.0 --port $PORT`
   - Health check path: `/health`
3. Configure as variaveis de ambiente.
4. Depois do deploy, configure o webhook do Telegram.

## Docker

Build:

```bash
docker build -t finbot .
```

Run:

```bash
docker run --env-file .env -p 8000:8000 finbot
```

