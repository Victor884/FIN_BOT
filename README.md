# Finbot

Bot financeiro pessoal para Telegram, com backend em FastAPI, interpretacao de mensagens em linguagem natural, persistencia em banco de dados e sincronizacao com Google Sheets.

## Objetivo

Construir o projeto de forma incremental, com modulos pequenos, testes e commits objetivos.

## Stack Inicial

- Python
- FastAPI
- Telegram Bot API
- SQLite no MVP
- Google Sheets API
- OpenAI API opcional para mensagens ambiguas

## Modulos

- `api`: aplicacao FastAPI e rotas HTTP
- `telegram`: adaptador do Telegram
- `parser`: interpretacao de mensagens financeiras
- `validation`: validacao dos dados extraidos
- `db`: persistencia e repositorios
- `sheets`: sincronizacao com Google Sheets
- `core`: configuracoes, logs e erros
- `models`: modelos de dominio
- `services`: casos de uso da aplicacao

## Desenvolvimento

1. Copie `.env.example` para `.env`.
2. Preencha os tokens apenas no `.env`.
3. Instale as dependencias quando o modulo exigir.
4. Rode as verificacoes antes de cada commit.

```bash
python -m compileall src tests
python -m pytest
```

## Politica De Seguranca

- Nunca commitar `.env`, tokens, chaves ou credenciais.
- Manter `.env.example` atualizado sem valores sensiveis.
- Validar o diff antes de cada commit.

