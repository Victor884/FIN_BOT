# Arquitetura

## Fluxo Do Telegram

1. `POST /telegram/webhook` valida o segredo do webhook.
2. `update_id` e consultado em `telegram_updates`; repeticoes nao sao processadas.
3. O usuario e localizado por `telegram_user_id`. No primeiro uso, dados legados sem proprietario sao associados ao primeiro usuario Telegram.
4. O parser deterministico interpreta a mensagem e calcula sua confianca.
5. Com IA habilitada, apenas resultados incertos usam o parser externo.
6. Validacao, deduplicacao financeira e persistencia executam em uma sessao SQLAlchemy.
7. A resposta usa um `httpx.AsyncClient` reutilizavel com pool e timeout explicito.
8. A sincronizacao com Google Sheets ocorre em background e atualiza `sheets_synced`.

Tempos de parser, validacao, banco, IA, Telegram e total sao registrados sem armazenar o texto financeiro integral.

## Runtime

- Uma engine SQLAlchemy e uma fabrica de sessoes sao reutilizadas por URL de banco.
- O schema nao e recriado por webhook; Alembic roda na inicializacao e tambem pode ser executado manualmente.
- Sessoes sao abertas por requisicao e fechadas com commit ou rollback.
- Clientes HTTP usam connection pooling, connect timeout de 3 segundos e read timeout de 8 segundos por padrao.
- Sheets permanece fora do caminho critico.

## Identidade

`UserRecord` e a identidade interna. Telegram e web sao apenas meios de acesso.

- Telegram: `telegram_user_id` e `chat_id` obtidos do update validado.
- Web: senha PBKDF2, JWT HS256 de curta duracao e refresh token aleatorio armazenado somente como hash.
- Vinculo: codigo aleatorio de uso unico, armazenado como hash e expirado em 10 minutos.
- Autorizacao: endpoints `/me` derivam o usuario do token; endpoints `/admin` exigem `ADMIN`.

## Dados E Portabilidade

Valores monetarios usam `Decimal`/`Numeric`, nunca `float`. Datas de negocio usam `Date`; eventos tecnicos usam timestamps com timezone. Os modelos e consultas funcionam em SQLite e PostgreSQL.

Contas, cartoes e transacoes possuem `user_id`. Nomes de conta e cartao sao unicos apenas dentro de cada usuario.

## Observabilidade

- `request_metrics`: endpoint, metodo, status, duracao, origem e request ID.
- `telegram_updates`: idempotencia e tempos das etapas do bot.
- `application_errors`: codigo normalizado, endpoint e integracao, sem stack trace ou mensagem financeira.
- Retencao padrao: 90 dias, aplicada na inicializacao e configuravel por `METRICS_RETENTION_DAYS`.

## Contrato HTTP

Respostas `/api/v1` usam envelope com `success`, `data`, `message`, `request_id` e `timestamp`. Erros acrescentam `error.code` e detalhes de validacao sem expor internals. O header `X-Request-ID` e devolvido em todas as respostas.
