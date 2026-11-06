# Software

## Visão geral

```text
ESP32 ──HTTPS + token──▶ API FastAPI ──▶ PostgreSQL (Supabase)
                              ▲
Navegador ── site React ──────┘  (mesmo endereço: site em /, API em /api)
```

O sistema é um **monólito modular**: uma única imagem Docker com a API e o build do site. A aplicação de entrada é `app.site:create_site`, que monta a API em `/api` e serve o React em `/`. Cada área da API fica num router próprio.

## Tecnologias

| Camada | Tecnologia |
| --- | --- |
| API | Python 3.12, FastAPI, Uvicorn, Pydantic Settings |
| Banco | PostgreSQL (17 no Supabase, 18 nos testes), SQLAlchemy 2.0, Alembic, psycopg 3 |
| Site | React 19, Vite, Recharts; tema escuro com opção de claro |
| Relatórios | PDF gerado com ReportLab |
| Otimização | SciPy (`milp`, solver HiGHS) |
| Segurança | Senhas com scrypt, sessões assinadas com itsdangerous, token do ESP32 guardado como hash SHA-256 |
| Firmware | Arduino C++ para ESP32 (ver [hardware.md](hardware.md)) |

## Funcionalidades

- Unidades (ex.: Centro, Polo Sede) com suas salas; cada sala com vários aparelhos (Split, Janela, Cassete, Piso-teto, Portátil, VRF/VRV).
- Catálogo do Inmetro com 1.507 modelos de 52 marcas: escolher o modelo preenche tipo, BTU/h e inverter.
- Painel da sala com temperatura, umidade, ocupação, estado do A/C, gráfico por período e alertas. Atualiza a cada 15 s.
- Histórico mensal, exportação CSV e relatório em PDF (geral, por unidade ou por sala).
- Usuários Administrador e Professor. Desativar o usuário ou trocar a senha dele encerra as sessões abertas.
- Cadastro do ESP32 por sala, com o token exibido uma única vez.
- Plano de envio otimizado: intervalo de envio do ESP32 por hora do dia.

O site **não liga nem desliga** aparelhos: o estado do A/C vem da telemetria e a decisão de resfriar é do ESP32.

## Banco de dados

As tabelas ficam no schema `movement` (nunca escreva o schema no SQL; a conexão já o define).

| Tabela | Conteúdo |
| --- | --- |
| `units` | Unidades |
| `rooms` | Salas, cada uma numa unidade |
| `air_conditioners` | Aparelhos de cada sala |
| `ac_catalog` | Catálogo do Inmetro, carregado pela migração a partir de `backend/app/data/` |
| `users` | Administradores e professores cadastrados (hash da senha e versão da sessão) |
| `devices` | ESP32 de cada sala (hash do token) |
| `sensor_readings` | Leituras detalhadas, guardadas por 30 dias |
| `monthly_summaries` | Médias mensais por sala, guardadas por 12 meses |
| `alerts` | Alertas de conforto e umidade gerados a partir das leituras |

Migrações em `backend/migrations/versions/`: de 0001 a 0005 (`0005_alerts` é a atual). As migrações já aplicadas não podem ser alteradas.

Regras importantes:
- A telemetria é **idempotente**: cada leitura tem um `message_id`, e o reenvio da mesma leitura não duplica dados.
- A API consolida as leituras com mais de 30 dias nas médias mensais ao iniciar e a cada hora.
- Leituras com mais de 30 dias são recusadas.
- Datas são gravadas em UTC e agrupadas no fuso `America/Sao_Paulo`.

## API

A documentação interativa fica em `/api/docs`. Principais grupos de rotas:

| Rotas | Para |
| --- | --- |
| `/api/health`, `/api/ready` | Saúde do processo e disponibilidade do banco e das migrações |
| `/api/auth/login`, `/api/auth/me` | Login e usuário atual |
| `/api/units`, `/api/rooms`, `/api/rooms/{id}/appliances`, `/api/rooms/{id}/devices` | Cadastros |
| `/api/catalog` | Marcas e modelos do Inmetro |
| `/api/users` | Usuários (só administrador) |
| `/api/telemetry` | Envio de leituras pelo ESP32 |
| `/api/rooms/{id}/latest`, `/history`, `/monthly`, `/alerts` | Consultas da sala |
| `/api/reports/pdf` | Relatórios |
| `/api/rooms/{id}/sampling-plan`, `/api/devices/me/sampling-interval` | Plano de envio otimizado |

## Padrões de projeto

| Padrão | Onde | Para quê |
| --- | --- | --- |
| Strategy (GoF) | `IntervalPolicy` em `backend/app/optimization.py` (intervalo fixo ou otimizado) | Trocar a regra do intervalo de envio sem mudar quem a usa |
| Observer (GoF) | `TelemetrySubject` em `backend/app/events.py` | Cada leitura nova notifica observadores que geram alertas de conforto e de umidade |
| Repository | `TelemetryRepository` em `backend/app/repository.py` | Isolar o acesso ao banco das regras |
| Inversão de dependência (SOLID) | `Depends(telemetry_repository)` em `backend/app/dependencies.py` | As rotas recebem o repositório pronto; os testes usam um repositório em memória |

Diagramas C4 e UML estão em `docs/arquitetura.md`.

## Otimização (Pesquisa Operacional)

Para cada hora do dia, o modelo escolhe um intervalo de envio entre 15, 30, 60, 90, 120 e 300 s. Ele minimiza o erro esperado da medição e respeita um orçamento diário de energia. É um problema da mochila de múltipla escolha, resolvido por programação linear inteira.

No perfil padrão, com 0,32 J por envio e orçamento de 50%, a economia é de cerca de 51%. O perfil real vem do histórico da sala. O ESP32 consulta o intervalo da hora a cada 15 min. Detalhes e análise de sensibilidade em `docs/pesquisa-operacional.md`.
