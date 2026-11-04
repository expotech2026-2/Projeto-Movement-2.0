# API Movement

FastAPI, SQLAlchemy, Alembic e PostgreSQL. Veja o [guia principal](../README.md) para instalação, conexão ao banco Movement existente, inicialização e política de retenção.

## Rotas

| Método | Caminho | Autorização | Função |
| --- | --- | --- | --- |
| GET | `/health` | Pública | Processo ativo |
| GET | `/ready` | Pública | Banco acessível e migrações aplicadas |
| POST | `/auth/login` | Usuário e senha | Obter sessão |
| GET / POST | `/rooms` | Operador | Listar / cadastrar salas |
| PUT / DELETE | `/rooms/{room_id}` | Operador | Editar / excluir sala vazia |
| GET / POST | `/rooms/{room_id}/appliances` | Operador | Listar / cadastrar aparelhos |
| PUT / DELETE | `/rooms/{room_id}/appliances/{id}` | Operador | Editar / excluir aparelho da sala |
| GET / POST | `/rooms/{room_id}/devices` | Operador | Listar / provisionar dispositivo |
| GET | `/rooms/{room_id}/latest` | Operador | Última leitura e obsolescência |
| GET | `/rooms/{room_id}/history` | Operador | Leituras dos últimos 30 dias |
| GET | `/rooms/{room_id}/monthly` | Operador | Uma média por sala/mês |
| POST | `/telemetry` | Token do dispositivo | Publicar medição |

Consulte os schemas e exemplos atualizados em `/docs` ou `/openapi.json`. `history` aceita `limit` de 1 a 2.000 e `since` em ISO 8601 com fuso. Limite padrão: 500.

## Organização do fluxo

`main.py` cuida do login, telemetria e consultas detalhadas. `management.py` contém o cadastro de salas, aparelhos e dispositivos. `models.py` define as tabelas, e `repository.py` persiste leituras com idempotência. `retention.py` consolida e elimina dados vencidos na mesma transação.

O token identifica o dispositivo e sua sala; a API não aceita `room_id` no corpo da telemetria. A chave única `(device_id, message_id)` impede duplicação. Reenvio idêntico retorna 200; conteúdo diferente retorna 409. Novas leituras retornam 201. Datas fora da janela permitida e valores inválidos retornam 422.

A tabela `monthly_summaries` guarda acumuladores e médias calculadas pelo PostgreSQL. O endpoint mensal combina os acumuladores com as leituras detalhadas, sem contar a mesma amostra duas vezes. O bloqueio consultivo PostgreSQL protege execuções simultâneas da retenção.

Use `python -m app.configure_existing` na raiz do projeto para conectar ao banco existente, sem colocar a senha no histórico de comandos. Use `python -m app.cli retain` na pasta `backend` para executar a retenção manualmente. O executável Python deve ser o do ambiente virtual.

O schema gerenciado em um banco existente é `movement`. A instância local isolada utiliza o schema `public`; os testes usam um schema aleatório separado. Nunca aponte `MOVEMENT_TEST_DATABASE_URL` para o banco real.
