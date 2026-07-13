# Arquitetura

## Fluxo Do Telegram

1. `POST /telegram/webhook` valida o segredo do webhook.
2. `update_id` e consultado em `telegram_updates`; repeticoes nao sao processadas.
3. O usuario e localizado por `telegram_user_id`. No primeiro uso, dados legados sem proprietario sao associados ao primeiro usuario Telegram.
4. O parser deterministico interpreta a mensagem e calcula sua confianca.
5. Com IA habilitada, apenas resultados incertos usam o parser externo.
6. Baixa confianca abre uma conversa persistida por 10 minutos; o usuario responde `SIM` ou `NAO` antes da gravacao.
7. Validacao, deduplicacao financeira e persistencia executam em uma sessao SQLAlchemy.
8. A resposta usa um `httpx.AsyncClient` reutilizavel com pool e timeout explicito. `/exportar` envia um CSV no chat.

Tempos de parser, validacao, banco, IA, Telegram e total sao registrados sem armazenar o texto financeiro integral.

## Runtime

- Uma engine SQLAlchemy e uma fabrica de sessoes sao reutilizadas por URL de banco.
- O schema nao e recriado por webhook. Em producao `DATABASE_AUTO_MIGRATE=false` e `scripts/bootstrap_database.py` executa Alembic e o bootstrap administrativo de forma explicita; localmente a opcao pode ficar habilitada para SQLite descartavel.
- Sessoes sao abertas por requisicao e fechadas com commit ou rollback.
- Clientes HTTP usam connection pooling, connect timeout de 3 segundos e read timeout de 8 segundos por padrao.
- Rotinas agendadas geram recorrencias, aplicam parcelas vencidas e produzem backups CSV no Supabase Storage configurado.

## Identidade

`UserRecord` e a identidade interna. Telegram e web sao apenas meios de acesso.

- Telegram: `telegram_user_id` e `chat_id` obtidos do update validado.
- Web: senha PBKDF2, JWT HS256 de curta duracao e refresh token aleatorio armazenado somente como hash.
- Vinculo: codigo aleatorio de uso unico, armazenado como hash e expirado em 10 minutos.
- Autorizacao: endpoints `/me` derivam o usuario do token; endpoints `/admin` exigem `ADMIN`.

## Dados E Portabilidade

Valores monetarios usam `Decimal`/`Numeric`, nunca `float`. Datas de negocio usam `Date`; eventos tecnicos usam timestamps com timezone. Os modelos e consultas funcionam em SQLite e PostgreSQL.

Contas, cartoes e transacoes possuem `user_id`. Nomes de conta e cartao sao unicos apenas dentro de cada usuario.

Categorias personalizadas, conversas do Telegram e agendas recorrentes tambem pertencem ao usuario. Consultas frequentes por usuario, status e data usam indices compostos para manter o caminho pronto para PostgreSQL/Supabase.

## Observabilidade

- `request_metrics`: endpoint, metodo, status, duracao, origem e request ID.
- `telegram_updates`: idempotencia e tempos das etapas do bot.
- `application_errors`: codigo normalizado, endpoint e integracao, sem stack trace ou mensagem financeira.
- Retencao padrao: 90 dias, aplicada pela rotina agendada e configuravel por `METRICS_RETENTION_DAYS`.

## Groq

`GroqService` concentra a chamada assíncrona à API, pooling, timeout e parsing da
resposta. `POST /api/v1/ai/completions` exige JWT, valida o prompt e aplica limite
por usuário. A chave permanece apenas no backend e o log registra tamanho,
modelo, status e duração, nunca o conteúdo do prompt.

O limitador atual é local ao processo. Em deploy com múltiplas réplicas, substitua
por um contador compartilhado em Redis ou PostgreSQL.

## Contrato HTTP

Respostas `/api/v1` usam envelope com `success`, `data`, `message`, `request_id` e `timestamp`. Erros acrescentam `error.code` e detalhes de validacao sem expor internals. O header `X-Request-ID` e devolvido em todas as respostas.
