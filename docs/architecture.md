# Arquitetura

## Fluxo Alvo

```text
Telegram
   -> Webhook FastAPI
   -> Parser de mensagens
   -> Validacao
   -> Banco de dados
   -> Sincronizacao com Google Sheets
   -> Dashboard mensal
```

## Principios

- O banco de dados sera a fonte da verdade.
- Google Sheets sera usado como camada de analise e dashboard.
- A IA sera opcional e chamada apenas quando regras locais nao forem suficientes.
- Integracoes externas ficarao isoladas atras de adaptadores.
- O projeto evoluira por commits pequenos e verificaveis.

## Modulos

| Modulo | Responsabilidade |
| --- | --- |
| `api` | Rotas HTTP, health check e webhooks |
| `telegram` | Recebimento e envio de mensagens no Telegram |
| `parser` | Extracao de tipo, valor, data, categoria e descricao |
| `validation` | Regras de consistencia antes de salvar |
| `db` | Conexao, migracoes e repositorios |
| `sheets` | Escrita e leitura no Google Sheets |
| `core` | Configuracoes, logs e excecoes |
| `models` | Entidades e objetos de valor |
| `services` | Orquestracao dos casos de uso |

