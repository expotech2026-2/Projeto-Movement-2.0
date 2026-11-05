# API Movement

FastAPI, SQLAlchemy, Alembic e PostgreSQL. Veja o [guia principal](../README.md) para instalação, conexão ao banco Movement existente, inicialização e política de retenção.

## Rotas

| Método | Caminho | Autorização | Função |
| --- | --- | --- | --- |
| GET | `/health` | Pública | Processo ativo |
| GET | `/ready` | Pública | Banco acessível e migrações aplicadas |
| POST | `/auth/login` | Usuário e senha | Obter sessão e dados do usuário |
| GET | `/auth/me` | Sessão | Usuário e perfil atuais |
| GET | `/units` | Sessão | Unidades com quantidade de salas |
| POST / PUT / DELETE | `/units[/{unit_id}]` | Administrador | Cadastrar / editar / excluir unidade vazia |
| GET | `/rooms?unit_id=` | Sessão | Listar salas, opcionalmente de uma unidade |
| POST / PUT / DELETE | `/rooms[/{room_id}]` | Administrador | Cadastrar / editar ou mover / excluir sala vazia |
| GET | `/rooms/{room_id}/appliances` | Sessão | Listar aparelhos |
| POST / PUT / DELETE | `/rooms/{room_id}/appliances[/{id}]` | Administrador | Cadastrar / editar / excluir aparelho |
| GET | `/rooms/{room_id}/devices` | Sessão | Listar dispositivo |
| POST | `/rooms/{room_id}/devices` | Administrador | Provisionar dispositivo |
| GET | `/rooms/{room_id}/latest` | Sessão | Última leitura e obsolescência |
| GET | `/rooms/{room_id}/history` | Sessão | Leituras dos últimos 30 dias |
| GET | `/rooms/{room_id}/monthly` | Sessão | Uma média por sala/mês |
| GET | `/catalog`, `/catalog/brands`, `/catalog/models` | Sessão | Catálogo Inmetro: fonte, marcas e modelos filtrados por `brand`, `kind` e `q` |
| GET | `/reports/pdf?unit_id=&room_id=` | Sessão | Relatório PDF de todas as unidades, de uma unidade ou de uma sala |
| GET | `/rooms/{room_id}/sampling-plan?budget_ratio=` | Sessão | Plano de leitura otimizado: intervalo por hora, energia, economia e erro esperado |
| GET / POST / PUT / DELETE | `/users[/{user_id}]` | Administrador | Gerenciar administradores e professores |
| POST | `/telemetry` | Token do dispositivo | Publicar medição |
| GET | `/devices/me/sampling-interval` | Token do dispositivo | Intervalo de envio da hora atual para o ESP32 |

Consulte os schemas e exemplos atualizados em `/docs` ou `/openapi.json`. `history` aceita `limit` de 1 a 2.000 e `since` em ISO 8601 com fuso. Limite padrão: 500.

## Organização do fluxo

`main.py` cuida do login, telemetria e consultas detalhadas. `auth.py` e `dependencies.py` resolvem a sessão e o perfil (Administrador ou Professor); `users.py` gerencia os usuários. `management.py` contém o cadastro de unidades, salas, aparelhos e dispositivos. `catalog.py` serve o catálogo Inmetro e `reports.py` gera o relatório PDF com `reportlab`. `models.py` define as tabelas, e `repository.py` persiste leituras com idempotência. `retention.py` consolida e elimina dados vencidos na mesma transação. `optimization.py` modela e resolve o plano de leitura (programação linear inteira com `scipy.optimize.milp`), e `sampling.py` o expõe ao painel e ao ESP32.

O token identifica o dispositivo e sua sala; a API não aceita `room_id` no corpo da telemetria. A chave única `(device_id, message_id)` impede duplicação. Reenvio idêntico retorna 200; conteúdo diferente retorna 409. Novas leituras retornam 201. Datas fora da janela permitida e valores inválidos retornam 422.

A tabela `monthly_summaries` guarda acumuladores e médias calculadas pelo PostgreSQL. O endpoint mensal combina os acumuladores com as leituras detalhadas, sem contar a mesma amostra duas vezes. O bloqueio consultivo PostgreSQL protege execuções simultâneas da retenção.

Use `python -m app.configure_existing` na raiz do projeto para conectar ao banco existente, sem colocar a senha no histórico de comandos. Use `python -m app.cli retain` na pasta `backend` para executar a retenção manualmente. O executável Python deve ser o do ambiente virtual.

O schema gerenciado em um banco existente é `movement`. A instância local isolada utiliza o schema `public`; os testes usam um schema aleatório separado. Nunca aponte `MOVEMENT_TEST_DATABASE_URL` para o banco real.
