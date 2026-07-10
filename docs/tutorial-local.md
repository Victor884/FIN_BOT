# Tutorial: executar o FIN_BOT localmente

Este guia inicia backend e frontend em duas janelas do PowerShell. Os comandos
partem da pasta:

```text
C:\Users\joao.vieira\Documents\FIN
```

## 1. Pré-requisitos

Verifique as ferramentas:

```powershell
python --version
node --version
npm.cmd --version
git --version
```

Use Python 3.11 ou superior e uma versão atual do Node. No Windows, prefira
`npm.cmd`: ele funciona mesmo quando a política do PowerShell bloqueia
`npm.ps1`.

## 2. Configurar o backend

Na raiz do projeto:

```powershell
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Abra `.env` e configure no mínimo:

```env
APP_ENV=local
DATABASE_URL=sqlite:///./data/finbot.sqlite3
JWT_SECRET=gere-um-valor-local-com-mais-de-32-caracteres
CORS_ALLOWED_ORIGINS=http://localhost:8080,http://127.0.0.1:8080
```

Para gerar um segredo JWT local:

```powershell
$jwt = [guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")
$jwt
```

Cole o resultado somente em `JWT_SECRET` no `.env`.

### Groq opcional

Adicione apenas no `.env` do backend:

```env
GROQ_API_KEY=sua-chave-local
GROQ_MODEL=llama-3.1-8b-instant
GROQ_TIMEOUT_SECONDS=8
GROQ_MAX_PROMPT_CHARS=4000
GROQ_MAX_OUTPUT_TOKENS=300
GROQ_REQUESTS_PER_MINUTE=10
```

Nunca adicione `GROQ_API_KEY` ao frontend ou ao Git.

### Telegram e Google Sheets opcionais

Para testar essas integrações, preencha também:

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_SECRET=
GOOGLE_SHEETS_SPREADSHEET_ID=
GOOGLE_SERVICE_ACCOUNT_FILE=./credentials/google-service-account.json
```

## 3. Preparar o banco

Execute as migrações:

```powershell
python -m alembic upgrade head
```

Opcionalmente, crie os usuários locais de teste:

```powershell
python scripts/create_users.py
```

O script gera senhas aleatórias e as exibe uma única vez para os usuários que
forem criados. Anote-as no momento da execução e não use esses usuários em
produção.

## 4. Iniciar o backend

Na primeira janela do PowerShell:

```powershell
cd C:\Users\joao.vieira\Documents\FIN
python -m uvicorn finbot.api.app:app --reload --host 127.0.0.1 --port 8000
```

Confirme em outra janela:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health/ready
```

Resultado esperado:

```json
{"status":"healthy","database":"available","version":"0.2.0"}
```

Links úteis:

- API: `http://127.0.0.1:8000`
- Swagger: `http://127.0.0.1:8000/docs`
- OpenAPI: `http://127.0.0.1:8000/openapi.json`

Se a porta `8000` estiver ocupada, use `--port 8001` e altere o frontend para
`VITE_FINBOT_API_URL=http://127.0.0.1:8001`.

## 5. Configurar o frontend

Na segunda janela:

```powershell
cd C:\Users\joao.vieira\Documents\FIN\frontend
Copy-Item .env.example .env
npm.cmd install
```

O arquivo `frontend/.env` deve conter:

```env
VITE_FINBOT_API_URL=http://127.0.0.1:8000
```

Essa é a única variável necessária no frontend. Tokens do Telegram, Google,
OpenAI e Groq nunca devem aparecer nesse arquivo.

## 6. Iniciar o frontend

Ainda na pasta `frontend`:

```powershell
npm.cmd run dev
```

Abra:

```text
http://127.0.0.1:8080
```

O Vite usa a porta `8080` com `strictPort`, portanto avisa se ela já estiver
ocupada em vez de trocar silenciosamente.

## 7. Testar o fluxo completo

1. Abra `http://127.0.0.1:8080/login`.
2. Entre com um usuário criado pelo script ou vinculado pelo Telegram.
3. Confirme o indicador `API online`.
4. O perfil `USER` deve abrir `/app`.
5. O perfil `ADMIN` deve abrir `/admin`.
6. Um `USER` não deve conseguir consultar endpoints `/api/v1/admin/*`.
7. Dados vazios devem aparecer como zero ou lista vazia, sem quebrar a página.

Para vincular um usuário real do Telegram:

1. Envie `/vincular` ao bot.
2. Abra `/vincular-telegram` no frontend.
3. Informe código, e-mail e senha.
4. O código expira em 10 minutos e só pode ser usado uma vez.

## 8. Testar a Groq

Com `GROQ_API_KEY` configurada e o backend reiniciado:

1. Abra `http://127.0.0.1:8000/docs`.
2. Execute `POST /api/v1/auth/login`.
3. Copie apenas o `access_token` retornado em `data`.
4. Clique em `Authorize` e informe `Bearer ACCESS_TOKEN`.
5. Execute `POST /api/v1/ai/completions` com:

```json
{"prompt":"Resuma estas informações de forma objetiva"}
```

Respostas comuns:

- `200`: integração funcionando;
- `401`: token ausente ou expirado;
- `422`: prompt vazio ou acima do limite;
- `429`: limite local ou da Groq atingido;
- `503`: chave ausente, timeout ou Groq indisponível.

## 9. Rodar as validações

Backend, na raiz:

```powershell
python -m pytest
python -m ruff check .
python -m compileall src tests scripts
```

Frontend:

```powershell
cd frontend
npm.cmd run lint
npm.cmd run build
```

## 10. Problemas frequentes

### `npm.ps1 não pode ser carregado`

Use `npm.cmd` em todos os comandos.

### `Disallowed CORS origin`

Confirme que a origem exata do frontend está em `CORS_ALLOWED_ORIGINS` e
reinicie o backend após alterar `.env`.

### Frontend tenta acessar LocalTunnel antigo

Altere `frontend/.env` para a URL local e reinicie o Vite.

### `VITE_FINBOT_API_URL não configurada`

Crie `frontend/.env` e reinicie `npm.cmd run dev`. Variáveis `VITE_*` são lidas
na inicialização/build.

### Groq continua desativada após adicionar a chave

Reinicie o Uvicorn. A configuração é carregada quando a aplicação inicia.

### Porta ocupada

```powershell
netstat -ano | Select-String ':8000|:8080'
```

Encerre o processo antigo no terminal em que foi iniciado ou escolha outra
porta e atualize `VITE_FINBOT_API_URL`.
