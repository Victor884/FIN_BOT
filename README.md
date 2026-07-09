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

## Status Atual

- Estrutura inicial do projeto criada.
- Webhook FastAPI para Telegram criado em `/telegram/webhook`.
- Parser por regras criado para despesas, receitas e transferencias simples.
- Validacao de movimentacoes financeiras criada.
- Persistencia inicial com SQLAlchemy e SQLite criada.
- Testes automatizados cobrindo estrutura, webhook, parser, validacao e repositorio.

## Proximos Passos

O projeto deve continuar em modulos pequenos, sempre com testes, revisao de credenciais, commit e push antes de avancar.

1. Criar o servico de lancamento financeiro.
   - Orquestrar parser, validacao e repositorio.
   - Retornar resultado estruturado para sucesso, erro e pendencias de confirmacao.
   - Commit sugerido: `feat: adiciona serviço de lançamento financeiro`.

2. Conectar o webhook do Telegram ao servico.
   - Ler mensagens recebidas.
   - Registrar movimentacoes validas.
   - Retornar respostas amigaveis para o usuario.
   - Commit sugerido: `feat: conecta telegram ao serviço financeiro`.

3. Adicionar prevencao de duplicidade.
   - Criar hash da mensagem e dados principais.
   - Evitar registros repetidos em janela curta de tempo.
   - Commit sugerido: `feat: evita lançamentos duplicados`.

4. Criar consultas financeiras.
   - Resumo do mes.
   - Gastos por categoria.
   - Saldo mensal.
   - Despesas pendentes.
   - Resumo semanal.
   - Commit sugerido: `feat: adiciona consultas financeiras`.

5. Criar integracao com Google Sheets.
   - Cliente autenticado por Service Account.
   - Append de lancamentos.
   - Sincronizacao manual inicial.
   - Commit sugerido: `feat: adiciona integração com google sheets`.

6. Criar estrutura das abas da planilha.
   - `Lancamentos`
   - `Categorias`
   - `Contas`
   - `Resumo_Mensal`
   - `Categorias_Mes`
   - `Pendentes`
   - `Dashboard`
   - Commit sugerido: `feat: cria modelo de planilha financeira`.

7. Adicionar dashboards e indicadores.
   - Receitas, despesas e saldo mensal.
   - Gastos por categoria.
   - Maiores despesas.
   - Fixos vs variaveis.
   - Economia ou deficit.
   - Commit sugerido: `feat: adiciona indicadores financeiros`.

8. Adicionar IA opcional.
   - Usar modelo barato apenas quando o parser por regras tiver baixa confianca.
   - Retornar JSON estruturado.
   - Manter `AI_ENABLED=false` como padrao.
   - Commit sugerido: `feat: adiciona parser com IA opcional`.

9. Melhorar logs e tratamento de erros.
   - Padronizar logs por modulo.
   - Capturar erros do Telegram, banco e Google Sheets.
   - Evitar exposicao de dados sensiveis nos logs.
   - Commit sugerido: `feat: melhora logs e tratamento de erros`.

10. Preparar deploy.
    - Adicionar comando de start.
    - Documentar variaveis de ambiente.
    - Configurar webhook publico.
    - Commit sugerido: `docs: adiciona guia de deploy`.

11. Adicionar CI.
    - Rodar `pytest`, `ruff` e `compileall` no GitHub Actions.
    - Commit sugerido: `ci: adiciona validações automatizadas`.

## Desenvolvimento

1. Copie `.env.example` para `.env`.
2. Preencha os tokens apenas no `.env`.
3. Instale as dependencias quando o modulo exigir.
4. Rode as verificacoes antes de cada commit.

```bash
python -m compileall src tests
python -m pytest
python -m ruff check .
```

## Deploy E Credenciais

O guia completo de credenciais, configuracao local, webhook do Telegram, Google Sheets e deploy esta em `docs/deploy.md`.

## CI

O GitHub Actions roda automaticamente em push para `main` e em pull requests:

- `python -m pytest`
- `python -m ruff check .`
- `python -m compileall src tests`

## Politica De Seguranca

- Nunca commitar `.env`, tokens, chaves ou credenciais.
- Manter `.env.example` atualizado sem valores sensiveis.
- Validar o diff antes de cada commit.
