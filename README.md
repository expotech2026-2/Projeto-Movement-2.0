# Movement 2.0

Gestão de salas e aparelhos de ar-condicionado, baseada no Projeto Integrador entregue. Frontend React separado da API FastAPI; PostgreSQL como banco de dados e pgAdmin 4 para administração.

## Funcionalidades

- Login com dois perfis: Administrador e Professor, com sessão assinada e expiração.
- Unidades (por exemplo, Centro e Polo Sede), cada uma com suas salas.
- Cadastro, busca, seleção, edição e exclusão de unidades e salas vazias.
- Vários aparelhos por sala: Split, Janela, Cassete, Piso-teto, Portátil e VRF/VRV.
- Catálogo do Inmetro com marcas e modelos registrados no Brasil; o modelo escolhido preenche tipo, BTU/h e inverter.
- Relatório em PDF de todas as unidades, de uma unidade ou de uma sala.
- Tema escuro com a logo do projeto e opção de tema claro.
- Cadastro autenticado de dispositivo ESP32 por sala, com token exibido uma única vez.
- Telemetria por dispositivo, sem aceitar uma sala informada pelo cliente.
- Painel com temperatura, umidade, ocupação, inventário e gráfico por período.
- Histórico mensal por sala e exportação CSV; atualização automática a cada 15 segundos.
- Migrações, autenticação, validação, CORS restrito e proteção de salas com dados vinculados.

O status do inventário indica a situação cadastral do equipamento. O estado ligado/desligado vem da telemetria do sensor da sala. Esta versão não envia comandos físicos de ligar/desligar pelo site.

## Unidades, perfis e catálogo

As salas pertencem a uma unidade: `Centro → Sala 101, Sala 102…`, `Polo Sede → Auditório…`. Uma unidade só pode ser excluída depois que suas salas forem movidas ou excluídas. Na migração de uma base existente, cada localização já informada nas salas vira uma unidade, e as salas sem localização vão para a "Unidade principal".

| Ação | Administrador | Professor |
| --- | --- | --- |
| Consultar unidades, salas, aparelhos, leituras e histórico | Sim | Sim |
| Gerar relatórios em PDF | Sim | Sim |
| Cadastrar, editar e excluir unidades, salas e aparelhos | Sim | Não |
| Cadastrar sensores ESP32 | Sim | Não |
| Gerenciar usuários | Sim | Não |

O login definido em `backend/.env` (`MOVEMENT_OPERATOR_USERNAME`) continua sendo o administrador principal. Os demais administradores e professores são cadastrados na tela Usuários, com senha de pelo menos 12 caracteres. Desativar um usuário ou trocar a senha dele encerra as sessões abertas.

O catálogo vem da tabela de eficiência energética de condicionadores de ar do Programa Brasileiro de Etiquetagem (Inmetro), atualizada em 31/12/2025: 1.507 modelos de 52 marcas, com tipo, BTU/h, tecnologia, classe e número de registro. Ele fica em `backend/app/data/inmetro_condicionadores.csv` e é carregado pela migração. Portáteis e VRF/VRV não constam dessa tabela e são preenchidos manualmente. Em quatro modelos, a capacidade publicada estava sem os milhares ou trocada com a coluna em watts e foi corrigida; esses casos têm `corrected=1` no CSV.

Para atualizar o catálogo com uma nova tabela do Inmetro, baixe o PDF de 28 colunas e, na pasta `backend`, execute:

```powershell
..\.venv\Scripts\python.exe -m pip install pdfplumber
..\.venv\Scripts\python.exe scripts\inmetro_catalog.py TABELA.pdf app\data\inmetro_condicionadores.csv
..\.venv\Scripts\python.exe -m app.cli catalog-import
```

O `pdfplumber` é usado apenas por esse conversor e não faz parte do `requirements.lock`. O relatório PDF usa o `reportlab`, incluído no `requirements.lock`.

## Organização

```text
frontend/             React, Vite, componentes, estilos e cliente HTTP
backend/app/          FastAPI, modelos, serviços e retenção
backend/migrations/   Migrações Alembic
backend/tests/        Testes com PostgreSQL separado
database/             Consultas e importação de servidores no pgAdmin
firmware/             ESP32 do projeto original com envio para FastAPI
scripts/              Inicialização e encerramento no Windows
```

Comentários do código são limitados a uma linha. Credenciais, bancos locais, configurações privadas e dependências instaladas ficam fora do Git.

## Preparar o ambiente

Requisitos: Python 3.12+, Node.js 22.12+ (testado com Node 24), PostgreSQL e pgAdmin 4. Os comandos abaixo são para PowerShell, na raiz do projeto.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e backend
npm.cmd ci --prefix frontend
```

Se usar `uv`, substitua a criação por `uv venv --python 3.12 .venv` e a instalação por `uv pip install --python .venv\Scripts\python.exe -r backend\requirements.lock`, seguida de `uv pip install --python .venv\Scripts\python.exe --no-deps -e backend`.

## Conectar ao banco Movement existente

Configuração informada: PostgreSQL em `127.0.0.1:5432`, usuário `postgres`, banco `Movement`. “Movement” no painel Servers do pgAdmin é um nome de cadastro; o endereço real deve estar na aba Connection das propriedades do servidor.

```powershell
.\.venv\Scripts\python.exe -m app.configure_existing
```

O comando solicita a senha sem exibi-la, verifica a conexão, cria o schema `movement` dentro do banco existente e aplica as migrações em uma transação. Tabelas de outros schemas são preservadas. Em caso de falha de conexão ou migração, `backend/.env` é preservado. Se já houver tabelas sem controle Alembic no schema `movement`, a configuração para sem alterá-las.

Após sucesso, o comando configura `backend/.env` e guarda a configuração anterior em um backup privado. Se houver login local já configurado, ele será mantido; caso contrário, o comando solicita a criação da senha do operador. Para outro endereço, use `--host ENDERECO`; porta, usuário e banco também podem ser informados.

No pgAdmin: `Servers > Movement > Databases > Movement > Schemas > movement > Tables`. Atualize a árvore depois da migração. As tabelas são `rooms`, `air_conditioners`, `devices`, `sensor_readings`, `monthly_summaries` e `alembic_version`.

`database/pgadmin-servers.json` permite importar os cadastros pelo menu Tools > Import/Export Servers. Não contém senhas. `database/consultas.sql` contém consultas de inventário, leituras e médias.

## Banco gerenciado no Supabase

O banco em nuvem é o projeto Supabase "Movement" (`ifirpelguapcdszegqqm`, região `us-west-2`, PostgreSQL 17). As tabelas ficam no schema `movement`. O schema `public` fica vazio porque o Supabase o expõe pela API REST com a chave anônima.

A conexão usa o Session pooler, `aws-1-us-west-2.pooler.supabase.com:5432`, que aceita IPv4. A conexão direta `db.ifirpelguapcdszegqqm.supabase.co` só tem IPv6, e o Transaction pooler (porta 6543) não preserva configurações de sessão entre transações; por isso nenhum dos dois é usado.

Para aplicar as migrações e gerar a configuração, na pasta `backend`:

```powershell
..\.venv\Scripts\python.exe -m app.configure_existing --url "postgresql://postgres.ifirpelguapcdszegqqm@aws-1-us-west-2.pooler.supabase.com:5432/postgres" --env-file .env.supabase
```

O comando solicita a senha do banco (Project Settings > Database) e, na primeira execução, cria a senha do administrador de produção. Fora desta máquina a conexão exige TLS (`sslmode=require`). O resultado fica em `backend/.env.supabase`, fora do Git, e o `backend/.env` local é preservado. Como o pooler ignora o `search_path` da URL, a API define o schema em cada conexão a partir de `MOVEMENT_DATABASE_SCHEMA=movement`.

Para executar a API local com o banco do Supabase, na pasta `backend`:

```powershell
..\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --env-file .env.supabase --host 127.0.0.1 --port 8000
```

As variáveis do arquivo informado têm prioridade sobre `backend/.env`. Em produção, os mesmos valores vão para as variáveis de ambiente do Azure (veja a próxima seção). O painel de segurança do Supabase (Advisors) não aponta alertas para esta configuração.

## Deploy no Azure

A produção roda no Azure App Service (Linux, contêiner), com a imagem publicada no Azure Container Registry. O `Dockerfile` da raiz gera um único contêiner: `app.site:create_site` serve o site em `/` e a API em `/api`, o mesmo caminho usado pelo proxy do Vite. Ao iniciar, o contêiner aplica as migrações pendentes no Supabase.

O trabalho é feito em branches `feat/<número>-<descrição>` ou `fix/<número>-<descrição>`, entra na `Devlop` por pull request para teste e só depois segue para a `main`. Em todas as branches a pipeline executa lint, testes, build do frontend e build da imagem. Somente um push na `main` publica `movement:latest` no registro, e o App Service se atualiza com essa imagem.

Configuração inicial, feita uma única vez:

1. Ative a assinatura Azure for Students em <https://azure.microsoft.com/free/students> com o e-mail da faculdade.
2. No portal, crie um **Container Registry**, plano Basic, num grupo de recursos `movement`. Prefira a região West US 2, próxima do Supabase; se a assinatura não a permitir, use uma das regiões liberadas. Em Settings > Access keys, habilite **Admin user**.
3. Cadastre no GitHub o endereço do registro e as credenciais do Admin user. Os valores dos segredos são solicitados no terminal:

```powershell
gh variable set ACR_LOGIN_SERVER --repo expotech2026-2/Projeto-Movement-2.0 --body NOME-DO-REGISTRO.azurecr.io
gh secret set ACR_USERNAME --repo expotech2026-2/Projeto-Movement-2.0
gh secret set ACR_PASSWORD --repo expotech2026-2/Projeto-Movement-2.0
```

4. Faça o merge da `Devlop` na `main`, ou execute de novo a pipeline da `main`, para publicar a primeira imagem.
5. Crie um **Web App**: Publish **Container**, sistema **Linux**, mesma região do registro, plano Free F1 se estiver disponível para contêiner, ou Basic B1. Na aba Container, escolha Azure Container Registry, o registro, a imagem `movement` e a tag `latest`.
6. Na pasta `backend`, gere as variáveis de ambiente a partir de `backend/.env.supabase`:

```powershell
..\.venv\Scripts\python.exe scripts\azure_settings.py https://NOME-DO-APP.azurewebsites.net
```

7. Copie o conteúdo de `backend/.env.azure.json` (fora do Git) para Web App > Settings > Environment variables > Advanced edit e aplique. O arquivo inclui `WEBSITES_PORT=8000` e limita o CORS ao endereço publicado.
8. Em Deployment Center, ative **Continuous deployment**, para que cada nova imagem `latest` reinicie o app. Em Monitoring > Health check, informe `/api/health`.
9. Confira `https://NOME-DO-APP.azurewebsites.net/api/ready`. A documentação interativa fica em `/api/docs`.

O registro Basic e o plano B1 consomem os créditos da assinatura de estudante; o plano F1 não tem custo, mas hiberna sem uso e limita o tempo de CPU diário. No firmware, use `https://NOME-DO-APP.azurewebsites.net/api/telemetry` em `MOVEMENT_API_URL` e o certificado raiz do domínio em `MOVEMENT_CA_CERT`.

## Desenvolvimento local separado

Para experimentar sem acessar o banco existente:

```powershell
.\.venv\Scripts\python.exe -m app.localdev setup --port 5433
```

O comando usa os binários PostgreSQL já instalados, cria uma instância própria em `.local/postgres-dev`, os bancos `Movement` e `Movement_test`, a sala inicial e um dispositivo. O banco existente na porta 5432 é preservado. Se os binários não forem encontrados, informe `--postgres-bin "C:\Program Files\PostgreSQL\18\bin"`.

As credenciais geradas ficam somente em `.local/postgres-dev/access.txt`. A configuração privada é criada em `backend/.env`. O setup não sobrescreve uma configuração que aponte para outro banco.

## Iniciar o site

```powershell
.\scripts\iniciar.ps1 -BancoLocal
```

Para o banco existente, após executar `app.configure_existing`, use `.\scripts\iniciar.ps1` sem `-BancoLocal`.

- Site: <http://127.0.0.1:5173>
- API e documentação interativa: <http://127.0.0.1:8000/docs>
- Disponibilidade do banco e migrações: <http://127.0.0.1:8000/ready>

Os processos iniciam em segundo plano; os logs ficam em `.local/logs`. Para encerrá-los, execute `.\scripts\parar.ps1`. Para parar também o banco isolado, execute `.\.venv\Scripts\python.exe -m app.localdev stop`. Os dados são preservados.

Alternativamente, execute a API em um terminal na pasta `backend` e o frontend em outro na pasta `frontend`:

```powershell
..\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
npm.cmd run dev
```

O frontend usa `/api` e o proxy do Vite durante o desenvolvimento. Em produção, o contêiner descrito em "Deploy no Azure" serve o build e a API no mesmo endereço, com HTTPS fornecido pelo App Service. `vite preview` apenas serve o build e não substitui esse proxy.

## Regras de retenção

1. Leituras detalhadas ficam disponíveis por 30 dias, contados pelo horário da medição.
2. A API consolida as leituras mais antigas ao iniciar e a cada hora. A limpeza física pode ocorrer até uma hora depois do limite; as consultas detalhadas já ocultam leituras vencidas.
3. Cada sala tem uma única linha consolidada por mês civil, no fuso `America/Sao_Paulo`.
4. A consolidação acumula somas e quantidades. As médias são colunas geradas e armazenadas pelo PostgreSQL. Novos lotes são ponderados pela quantidade de amostras; médias de lotes não são promediadas entre si.
5. A remoção das leituras e o armazenamento dos acumuladores ocorrem na mesma transação. Um bloqueio transacional evita contagem duplicada entre vários processos.
6. O endpoint mensal combina as amostras consolidadas com as ainda detalhadas para apresentar uma única média do mês, sem sobreposição. O mês é parcial enquanto ainda houver uma parte dentro da janela de 30 dias; fica concluído quando todo o mês passou desse limite.
7. O resumo é mantido por 12 meses após o encerramento do respectivo mês. Exemplo: setembro/2026 fica salvo até 01/10/2027, às 00:00 no fuso de São Paulo. O painel pode mostrar 12 meses encerrados e o mês atual parcial.
8. Sem amostras, não se cria média artificial nem registro com zero. Leituras com mais de 30 dias são recusadas na entrada da API.

As médias são por amostra: temperatura interna/externa, umidade interna/externa, ocupação e percentual de amostras com A/C ligado. Esse percentual não é consumo de energia nem representa medição individual de cada aparelho.

Para uma execução manual ou agendada pelo sistema operacional, na pasta `backend`:

```powershell
..\.venv\Scripts\python.exe -m app.cli retain
```

A retenção depende de a API ou esse comando estar em execução. Após um período desligado, a próxima execução processa o acúmulo de dados antes de descartar resumos vencidos. Configure `MOVEMENT_RETENTION_ENABLED=false` se adotar exclusivamente um agendador externo.

## Sensores e teste sem hardware

Cadastre o dispositivo em Salas e aparelhos e guarde o token exibido. Cada sala aceita um ESP32 responsável pelas medições ambientais, independentemente da quantidade de aparelhos do inventário.

```powershell
.\.venv\Scripts\python.exe backend\scripts\publish_sample.py
```

O token é solicitado sem eco. A leitura publicada por esse comando é simulada; use-o somente no ambiente de desenvolvimento. O fluxo completo é `ESP32 -> POST /telemetry -> PostgreSQL -> FastAPI -> React`.

O firmware mantém a simulação de climatização e os sensores do projeto entregue. Agora publica na API; o envio ThingSpeak/TalkBack fica desativado por padrão. Copie `firmware/climacontrol/config.h.example` para `config.h` e configure URL, token e certificado CA quando usar HTTPS. O arquivo privado é ignorado pelo Git. Nenhuma chave ThingSpeak original foi mantida na versão distribuída.

Para ESP32 físico, o endereço da API precisa ser alcançável pela rede do dispositivo. Em desenvolvimento de rede local, execute o Uvicorn com `--host 0.0.0.0` e informe o IP do computador no firmware. O Wokwi precisa de gateway/túnel para acessar uma API local. O relógio é sincronizado por NTP e cada mensagem usa UUID; reenvios mantêm o mesmo conteúdo até a confirmação. A fila do firmware contém uma mensagem em RAM e não substitui uma fila persistente em flash.

O LED IR continua sendo uma simulação herdada da entrega; não implementa o protocolo real dos diferentes fabricantes. O firmware não foi compilado nem testado em hardware nesta execução.

## Verificações

```powershell
npm.cmd run lint --prefix frontend
npm.cmd run test --prefix frontend
npm.cmd run build --prefix frontend
.\.venv\Scripts\python.exe -m ruff check backend
```

Os testes de backend exigem um banco separado com nome terminado em `_test`. O setup local gera a URL em `.local/postgres-dev/test.env`. Carregue-a sem imprimir a senha:

```powershell
$testConfig = Get-Content .local\postgres-dev\test.env -Raw
$env:MOVEMENT_TEST_DATABASE_URL = $testConfig.Trim().Substring('MOVEMENT_TEST_DATABASE_URL='.Length)
.\.venv\Scripts\python.exe -m pytest backend\tests -q
```

Os testes criam e removem apenas um schema aleatório nesse banco de testes. Cobrem autenticação, validação, idempotência, concorrência, cadastros, isolamento por sala, migrações, média ponderada, fronteiras de data, retenção de 12 meses e reversão da remoção quando a agregação falha. A integração contínua executa backend e frontend no GitHub.

A autorização atual é de um único operador para todos os ambientes. Dados de energia, comandos físicos, múltiplos operadores e permissões por sala exigem implementações adicionais.
