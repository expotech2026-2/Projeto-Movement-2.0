# Guia para agentes (Claude Code, Codex) e colaboradores

Movement 2.0: gestão de salas e aparelhos de ar-condicionado com telemetria de um ESP32. Projeto da ExpoTech 2026.2, categoria INTERFACE (Engenharia da Computação). Cada tarefa é uma issue do GitHub com especificação, testes obrigatórios e critérios de aceite; siga a issue à risca e este guia para tudo que ela não disser.

**Contexto:** antes de começar, leia [`contexto/README.md`](contexto/README.md). Ele aponta o arquivo de cada área: propósito, software, hardware, infraestrutura em nuvem e estado atual. Ao terminar uma tarefa que mude o que está pronto ou pendente, atualize `contexto/estado-atual.md`.

## Mapa do repositório

```text
contexto/               Panorama do projeto para IAs, sem segredos; estado-atual.md lista o que falta
backend/app/            FastAPI: main.py (create_app, telemetria), routers create_*_router()
backend/app/models.py   Modelos SQLAlchemy 2.0 (tipados com Mapped)
backend/migrations/     Alembic; versions/000N_slug.py
backend/tests/          pytest; fixtures database_url e context em conftest.py
backend/scripts/        Utilitários de linha de comando (fora da imagem Docker)
frontend/src/           React 19 + Vite; services/movementApi.js é o único cliente HTTP
firmware/climacontrol/  ESP32 (Arduino C++); diagram.json é o circuito no Wokwi
docs/                   Documentação dos requisitos da ExpoTech
Dockerfile              Imagem de produção: site em / e API em /api (app.site:create_site)
.github/workflows/ci.yml  CI em todas as branches; publicação no Azure só na main
```

## Preparar o ambiente

### Linux (Codex, Claude Code na nuvem, CI)

```bash
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements.lock
pip install --no-deps -e backend
npm ci --prefix frontend
```

PostgreSQL só para testes. Com Docker:

```bash
docker run -d --name movement-pg -p 5432:5432 \
  -e POSTGRES_USER=movement -e POSTGRES_PASSWORD=ci-only-password -e POSTGRES_DB=Movement_test \
  postgres:18
```

Sem Docker:

```bash
sudo apt-get update && sudo apt-get install -y postgresql
sudo service postgresql start
sudo -u postgres psql -c "CREATE USER movement WITH PASSWORD 'ci-only-password' CREATEDB;"
sudo -u postgres createdb -O movement Movement_test
```

Em seguida, nos dois casos:

```bash
export MOVEMENT_TEST_DATABASE_URL=postgresql+psycopg://movement:ci-only-password@127.0.0.1:5432/Movement_test
```

### Windows (máquina da equipe)

Siga o README ("Preparar o ambiente" e "Desenvolvimento local separado"). A cópia do projeto dentro do OneDrive não funciona com git: clone o repositório numa pasta fora do OneDrive (ex.: `C:\dev\Projeto-Movement-2.0`) para trabalhar com branches. Atrás do proxy da empresa, use `uv pip install --system-certs`.

## Verificação obrigatória antes de cada commit

Na raiz do repositório, todos precisam passar:

```bash
ruff check backend
ruff format --check backend
pytest backend/tests -q
npm run lint --prefix frontend
npm test --prefix frontend
npm run build --prefix frontend
python hardware/logica/verificar_logica.py
python hardware/logica/testar_firmware.py
```

O CI roda esses comandos, exceto o `ruff format --check`, e também constrói a imagem Docker. `testar_firmware.py` precisa de um compilador C++ (`g++`, `clang++` ou `pip install ziglang`).

## Convenções

- **Idioma:** identificadores em inglês, como no código existente. Textos para o usuário, mensagens de erro (`HTTPException(..., "Mensagem em português")`), documentação e mensagens de commit em português.
- **Comentários:** no máximo uma linha, só quando o código não for autoexplicativo.
- **Python:** 3.12, ruff com `line-length = 100` e regras E, F, I. Tipos nas assinaturas.
- **Rotas novas:** num módulo próprio, com uma função `create_<nome>_router() -> APIRouter` incluída em `create_app()` (`backend/app/main.py`) por `app.include_router(...)`.
- **Autorização:** leitura com `dependencies=[Depends(require_user)]` ou `principal: CurrentUser`; escrita com `dependencies=Admin` (`Admin = [Depends(require_admin)]`); dispositivo ESP32 com `Depends(require_device)` (token Bearer, guardado como hash SHA-256).
- **Banco:** sessão por `session: Db`. Nunca escreva o nome do schema no SQL: a conexão já define o `search_path` (`MOVEMENT_DATABASE_SCHEMA`). Datas sempre com fuso (UTC no banco; `America/Sao_Paulo` para agrupar por hora ou dia).
- **Configuração:** campo novo em `Settings` (`backend/app/settings.py`, prefixo `MOVEMENT_`) e linha correspondente, comentada, em `backend/.env.example`.
- **Migrações:** nunca altere as já aplicadas (0001 a 0003). Mudança de modelo exige:
  1. o modelo em `backend/app/models.py`;
  2. `backend/migrations/versions/000N_slug.py` com `revision = "000N_slug"`, `down_revision` igual à anterior, e `upgrade()` e `downgrade()` completos;
  3. `SCHEMA_VERSION` em `main.py` igual à nova revisão;
  4. tabela nova também na consulta do `/ready` em `main.py`.
  
  A fixture de testes roda upgrade → downgrade → upgrade e, ao final, `alembic check`. Modelo e migração diferentes fazem a suíte falhar no encerramento.
- **Testes:** testes puros não usam fixture. Testes de API usam `context`, que fornece `client`, `app`, `unit`, `room`, `device`, `professor`, `operator_headers` (admin), `professor_headers` e `device_headers`. Para publicar uma leitura, veja `sample()` e `publish()` em `backend/tests/test_telemetry.py`.
- **Frontend:** componentes funcionais em `frontend/src/components/`. Chamadas HTTP só por `request(path, options)` de `services/movementApi.js`, com uma função exportada por rota e teste em `movementApi.test.js`. Gráficos com Recharts; estilos em `src/styles/movement.css`.
- **Firmware:** sem bibliotecas novas além da DHT e da IRremoteESP8266. O CI não compila o firmware inteiro, só testa a lógica da porta (`passoPorta` e `filtrarBarreira`) a escolha dos comandos IR (`proximoComandoIR` e `estadoNovoParaEnviar`) e o alvo de conforto (`calcularTempRecomendada`), extraídas do `sketch.ino` por `hardware/logica/testar_firmware.py`: mantenha as mudanças pequenas, revise a sintaxe e descreva no PR o teste manual no Wokwi. `config.h` é privado.

## Segurança

- Nunca faça commit de `.env`, `.env.*` (exceto `.env.example`), `firmware/**/config.h`, tokens ou senhas, nem os imprima em logs.
- Testes só rodam contra um banco cujo nome termina em `_test`.
- Não altere arquivos `backend/.env*` locais nem recursos de produção (Supabase, Azure).

## Fluxo de git

- `main` = produção (publica no Azure). `Devlop` = integração e teste. Nunca faça push direto nelas.
- Cada issue tem uma branch `feat/<número>-<descrição>`. Se ela já existe e não tem commits próprios, atualize-a antes de começar:

```bash
git fetch origin
git switch feat/4-pesquisa-operacional
git merge --ff-only origin/Devlop
```

- Commits pequenos, em português, no estilo `feat: ...`, `fix: ...`, `docs: ...`, `test: ...`.
- PR para a `Devlop` com `gh pr create --base Devlop`. O corpo cita `Issue #N` e mostra a saída dos comandos de verificação. Merge com *merge commit*, nunca *squash*.
- Depois de validar na `Devlop`, um humano abre o PR `Devlop → main`.

## Definição de pronto

1. Todos os comandos de verificação passam.
2. Todos os critérios de aceite da issue estão marcados.
3. A documentação citada na issue foi criada ou atualizada.
4. As partes manuais (marcadas com 👤 na issue) estão listadas no PR para um humano executar.
