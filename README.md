# Movement 2.0 — Gestão de salas e climatização com ESP32

> **Projeto da ExpoTech 2026.2**, categoria INTERFACE (Engenharia da Computação). A avaliação individual é de 09 a 13/11/2026, e o projeto não muda depois dela. O panorama para IAs está em [`contexto/`](contexto/README.md), e o que está pronto ou pendente, em [`contexto/estado-atual.md`](contexto/estado-atual.md).

Gestão de **salas de aula e aparelhos de ar-condicionado** com telemetria de um **ESP32** em cada sala:
- duas barreiras infravermelhas na porta contam quem entra e sai;
- um DHT11 mede temperatura e umidade;
- o firmware decide quando resfriar.

O site mostra o painel de cada sala, o histórico, o inventário com o **catálogo do Inmetro (1.507 modelos de 52 marcas)** e relatórios em PDF. A API escolhe o intervalo de envio do ESP32 por **programação linear inteira**, para gastar menos energia. O projeto evolui o Projeto Integrador entregue anteriormente.

---

## Como abrir

### Site publicado

A produção fica em <https://movement-gxdafrgwcjd9f7gx.westus3-01.azurewebsites.net>. Entre com o administrador definido nas variáveis de ambiente ou com um usuário cadastrado.

| Caminho | Conteúdo |
| --- | --- |
| `/` | Site |
| `/api/docs` | Documentação interativa da API |
| `/api/health` | O processo está de pé |
| `/api/ready` | O banco responde e as migrações estão aplicadas |

```text
ESP32 da sala ── POST /api/telemetry + token ─┐
                                              ▼
navegador ─▶ Azure App Service (contêiner) ──┬─ /     → site React (build do Vite)
                                             └─ /api  → API FastAPI ─▶ Supabase (PostgreSQL 17, schema movement)
```

A imagem do `Dockerfile` gera um único contêiner. Nele, `app.site:create_site` serve o site e a API no mesmo endereço, com o HTTPS fornecido pelo App Service. Ao iniciar, o contêiner aplica as migrações pendentes e só então aceita conexões.

### No computador (Windows)

Requisitos: Python 3.12+, Node.js 22.12+ (testado com Node 24), PostgreSQL e pgAdmin 4. Os comandos abaixo são para PowerShell, na raiz do projeto. Trabalhe num clone fora do OneDrive, porque o git não funciona dentro dele.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e backend
npm.cmd ci --prefix frontend
```

Se usar `uv`:
1. crie o ambiente com `uv venv --python 3.12 .venv`;
2. instale com `uv pip install --python .venv\Scripts\python.exe -r backend\requirements.lock`;
3. rode `uv pip install --python .venv\Scripts\python.exe --no-deps -e backend`.

Atrás do proxy da empresa, acrescente `--system-certs`.

Para ter um banco próprio, sem tocar no banco existente:

```powershell
.\.venv\Scripts\python.exe -m app.localdev setup --port 5433
```

O comando:
- usa os binários PostgreSQL já instalados e cria uma instância própria em `.local/postgres-dev`;
- cria os bancos `Movement` e `Movement_test`, a sala inicial e um dispositivo;
- guarda as credenciais geradas só em `.local/postgres-dev/access.txt` e cria a configuração privada em `backend/.env`;
- preserva o banco existente na porta 5432 e não sobrescreve uma configuração que aponte para outro banco.

Se os binários não forem encontrados, informe `--postgres-bin "C:\Program Files\PostgreSQL\18\bin"`.

Para subir o site e a API:

```powershell
.\scripts\iniciar.ps1 -BancoLocal
```

| Endereço | Conteúdo |
| --- | --- |
| <http://127.0.0.1:5173> | Site |
| <http://127.0.0.1:8000/docs> | API e documentação interativa |
| <http://127.0.0.1:8000/ready> | Disponibilidade do banco e migrações |

- **Banco existente:** depois de executar `app.configure_existing` (veja *Banco Movement existente*), use `.\scripts\iniciar.ps1` sem `-BancoLocal`.
- **Logs:** os processos rodam em segundo plano e gravam em `.local/logs`.
- **Encerrar:** `.\scripts\parar.ps1`. Para parar também o banco isolado, `.\.venv\Scripts\python.exe -m app.localdev stop`. Os dados são preservados.

Também dá para rodar a API e o site em dois terminais, um na pasta `backend` e outro na pasta `frontend`:

```powershell
..\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
npm.cmd run dev
```

Durante o desenvolvimento, o site chama `/api` pelo proxy do Vite. O `vite preview` só serve o build e não substitui esse proxy.

### Configuração (.env)

A API lê variáveis de ambiente com o prefixo `MOVEMENT_` (`backend/app/settings.py`). O modelo comentado é o [`backend/.env.example`](backend/.env.example); copie para `backend/.env`, que fica fora do Git. Com `--env-file`, o Uvicorn carrega outro arquivo, e os valores dele têm prioridade sobre o `backend/.env`.

| Variável | Padrão | Para quê |
| --- | --- | --- |
| `MOVEMENT_DATABASE_URL` | obrigatória | Conexão com o PostgreSQL |
| `MOVEMENT_DATABASE_SCHEMA` | — | Schema das tabelas, definido em cada conexão; `movement` no Supabase |
| `MOVEMENT_SESSION_SECRET` | obrigatória | Chave que assina as sessões de login |
| `MOVEMENT_OPERATOR_USERNAME` | `admin` | Login do administrador principal |
| `MOVEMENT_OPERATOR_PASSWORD_HASH` | obrigatória | Hash scrypt da senha dele; gere com `python -m app.cli password-hash`, na pasta `backend` |
| `MOVEMENT_CORS_ORIGINS` | `["http://localhost:5173"]` | Endereços de onde o navegador pode chamar a API |
| `MOVEMENT_SESSION_TTL_SECONDS` | `3600` | Duração da sessão |
| `MOVEMENT_STALE_AFTER_SECONDS` | `90` | Sem leitura nesse tempo, a sala aparece como desatualizada |
| `MOVEMENT_RETENTION_ENABLED` | `true` | Consolidação e limpeza automáticas das leituras pela API |
| `MOVEMENT_RETENTION_INTERVAL_SECONDS` | `3600` | Intervalo entre execuções da retenção |
| `MOVEMENT_ENERGY_PER_SEND_J` | `0.32` | Energia de um envio do ESP32, em joules |
| `MOVEMENT_SAMPLING_BUDGET_RATIO` | `0.5` | Fração da energia de referência que o plano de envio pode gastar |
| `WEBSITES_PORT` | — | Só no Azure: porta do contêiner (`8000`) |

O site tem uma única variável opcional, `VITE_API_BASE_URL`, que vale `/api` por padrão (`frontend/.env.example`).

### Ambientes e CI/CD

| Ambiente | Branch | Endereço | Banco |
| --- | --- | --- | --- |
| Desenvolvimento | `feat/<n>-…` ou `fix/<n>-…` | <http://127.0.0.1:5173> | PostgreSQL local |
| Integração e teste | `Devlop` | só no CI | PostgreSQL 18 do CI |
| Produção | `main` | <https://movement-gxdafrgwcjd9f7gx.westus3-01.azurewebsites.net> | Supabase |

- **CI** ([ci.yml](.github/workflows/ci.yml)) roda em todas as branches:
  - **backend:** ruff e pytest contra um PostgreSQL 18 de verdade;
  - **frontend:** lint, testes e build;
  - **firmware:** equações lógicas, lógica da porta e comandos IR extraídos do `sketch.ino`;
  - **image:** build da imagem Docker.
- **CD:** só um push na `main` publica `movement:latest` e `movement:<sha>` no Azure Container Registry. O deploy contínuo do App Service puxa a nova `latest` e reinicia o contêiner, que migra o banco ao subir.
- **Fluxo:** cada issue tem uma branch `feat/<número>-<descrição>`, que entra na `Devlop` por PR com merge commit. Depois de testar na `Devlop`, um humano abre o PR `Devlop → main`. Ninguém dá push direto nessas duas branches.

Comandos de verificação, convenções de código e definição de pronto: [AGENTS.md](AGENTS.md).

### Banco gerenciado no Supabase

O banco em nuvem é o projeto Supabase "Movement" (`ifirpelguapcdszegqqm`, região `us-west-2`, PostgreSQL 17).
- As tabelas ficam no schema `movement`.
- O schema `public` fica vazio porque o Supabase o expõe pela API REST com a chave anônima.
- O Supabase é usado só como PostgreSQL: Auth, Storage e a API REST dele ficam de fora.

A conexão usa o **Session pooler**, `aws-1-us-west-2.pooler.supabase.com:5432`, que aceita IPv4. Os outros dois acessos não servem:
- a conexão direta, `db.ifirpelguapcdszegqqm.supabase.co`, só tem IPv6;
- o Transaction pooler, na porta 6543, não preserva configurações de sessão entre transações.

**O pooler ignora o `search_path` da URL.** Por isso a API define o schema em cada conexão a partir de `MOVEMENT_DATABASE_SCHEMA=movement`.

Para aplicar as migrações e gerar a configuração, na pasta `backend`:

```powershell
..\.venv\Scripts\python.exe -m app.configure_existing --url "postgresql://postgres.ifirpelguapcdszegqqm@aws-1-us-west-2.pooler.supabase.com:5432/postgres" --env-file .env.supabase
```

O comando:
- solicita a senha do banco (Project Settings > Database) e, na primeira execução, cria a senha do administrador;
- grava o resultado em `backend/.env.supabase`, fora do Git;
- aceita como destino apenas `.env` ou `.env.<nome>` em `backend/`, com permissões privadas também para o backup;
- ao reconfigurar um arquivo, mantém o login que já está gravado nele.

**TLS:** conexões remotas usam `sslmode=verify-full`, que verifica o certificado e o nome do servidor. A URL aceita apenas as opções `sslmode` e `sslrootcert`.
- **Supabase:** a CA dele é privada ("Supabase Root 2021 CA", válida até 2031) e não vem no repositório de certificados do sistema. Por isso o configurador usa a cópia oficial embutida em `backend/app/certs/supabase-root-2021.crt`.
- **Outros servidores:** o configurador usa os certificados do sistema.
- **Caminho relativo:** um `sslrootcert` relativo é procurado a partir da pasta `backend`. Isso funciona também em pastas com acento, que o libpq do Windows não abre por caminho absoluto.

Para executar a API local com o banco do Supabase, na pasta `backend`:

```powershell
..\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --env-file .env.supabase --host 127.0.0.1 --port 8000
```

Em produção, os mesmos valores vão para as variáveis de ambiente do Azure (veja a próxima seção). O painel de segurança do Supabase (Advisors) não aponta alertas para esta configuração.

### Deploy no Azure (configuração inicial)

A produção roda no Azure App Service (Linux, contêiner), com a imagem publicada no Azure Container Registry. A configuração abaixo é feita uma única vez:

1. Ative a assinatura Azure for Students em <https://azure.microsoft.com/free/students> com o e-mail da faculdade.
2. No portal, crie um **Container Registry**, plano Basic, num grupo de recursos `movement`. Prefira a região West US 2, próxima do Supabase; se a assinatura não a permitir, use uma das regiões liberadas. Em Settings > Access keys, habilite **Admin user**.
3. Cadastre no GitHub o endereço do registro e as credenciais do Admin user. Os valores dos segredos são solicitados no terminal:

```powershell
gh variable set ACR_LOGIN_SERVER --repo expotech2026-2/Projeto-Movement-2.0 --body NOME-DO-REGISTRO.azurecr.io
gh secret set ACR_USERNAME --repo expotech2026-2/Projeto-Movement-2.0
gh secret set ACR_PASSWORD --repo expotech2026-2/Projeto-Movement-2.0
```

4. Faça o merge da `Devlop` na `main`, ou execute de novo a pipeline da `main`, para publicar a primeira imagem.
5. Crie um **Web App**:
   - Publish **Container**, sistema **Linux**, na mesma região do registro;
   - plano Free F1, se estiver disponível para contêiner, ou Basic B1;
   - na aba Container, escolha Azure Container Registry, o registro, a imagem `movement` e a tag `latest`.
6. Na pasta `backend`, gere as variáveis de ambiente a partir de `backend/.env.supabase`:

```powershell
..\.venv\Scripts\python.exe scripts\azure_settings.py https://NOME-DO-APP.azurewebsites.net
```

   Um `.env.supabase` gerado antes da CA embutida tem `sslmode=require`: a conexão é criptografada, mas não confere o servidor. Para verificar o certificado, troque na `MOVEMENT_DATABASE_URL` o trecho `sslmode=require` por `sslmode=verify-full&sslrootcert=app%2Fcerts%2Fsupabase-root-2021.crt`.

7. Copie o conteúdo de `backend/.env.azure.json`, que fica fora do Git, para Web App > Settings > Environment variables > Advanced edit:
   - acrescente as entradas às que já existem, sem apagar as `DOCKER_REGISTRY_*`, e aplique;
   - o arquivo inclui `WEBSITES_PORT=8000` e limita o CORS ao endereço publicado.
8. Em Deployment Center, ative **Continuous deployment**, para que cada nova imagem `latest` reinicie o app. Em Monitoring > Health check, informe `/api/health`.
9. Confira `https://NOME-DO-APP.azurewebsites.net/api/ready`. A documentação interativa fica em `/api/docs`.

Custos:
- o registro Basic e o plano B1 consomem os créditos da assinatura de estudante;
- o plano F1 não tem custo, mas hiberna sem uso e limita o tempo de CPU diário.

Mande os valores do `.env.supabase` e do `.env.azure.json` só por conversa privada e temporária.

### Banco Movement existente (pgAdmin)

Para usar um PostgreSQL já instalado, com usuário `postgres` e banco `Movement` em `127.0.0.1:5432`, execute na pasta `backend`:

```powershell
..\.venv\Scripts\python.exe -m app.configure_existing
```

"Movement", no painel Servers do pgAdmin, é só o nome do cadastro; o endereço real está na aba Connection das propriedades do servidor.

O comando:
- solicita a senha sem exibi-la e verifica a conexão;
- cria o schema `movement` dentro do banco existente e aplica as migrações numa transação;
- preserva as tabelas de outros schemas;
- em caso de falha de conexão ou de migração, preserva o `backend/.env`;
- para sem alterar nada se já houver tabelas sem controle do Alembic no schema `movement`.

Depois do sucesso, ele configura o `backend/.env` e guarda a configuração anterior num backup privado. Se já houver login local configurado, ele é mantido; senão, o comando pede a criação da senha do administrador. Para outro endereço, use `--host ENDERECO`; porta, usuário e banco também podem ser informados.

No pgAdmin, as tabelas ficam em `Servers > Movement > Databases > Movement > Schemas > movement > Tables`; atualize a árvore depois da migração.
- `database/pgadmin-servers.json` importa os cadastros pelo menu Tools > Import/Export Servers e não contém senhas.
- `database/consultas.sql` traz consultas para o Query Tool, que funcionam no schema `movement` e no `public` do banco local:
  - unidades;
  - inventário por unidade;
  - dispositivos;
  - médias mensais;
  - leituras;
  - alertas;
  - usuários;
  - catálogo por marca.

  Senhas e tokens não aparecem: ficam só como hash.

| Tabela | Conteúdo |
| --- | --- |
| `units` | Unidades |
| `rooms` | Salas, cada uma numa unidade |
| `air_conditioners` | Aparelhos de cada sala |
| `ac_catalog` | Catálogo do Inmetro |
| `users` | Administradores e professores cadastrados |
| `devices` | ESP32 de cada sala (hash do token) |
| `sensor_readings` | Leituras detalhadas dos últimos 30 dias |
| `monthly_summaries` | Médias mensais por sala, por 12 meses |
| `alerts` | Alertas de conforto e umidade |
| `alembic_version` | Migração aplicada (atual: `0005_alerts`) |

---

## Login, perfis e usuários

Fora as rotas de saúde e o próprio login, a API exige sessão: sem ela, responde 401. A telemetria exige o token do dispositivo.

| Ação | Administrador | Professor |
| --- | --- | --- |
| Consultar unidades, salas, aparelhos, leituras e histórico | Sim | Sim |
| Gerar relatórios em PDF | Sim | Sim |
| Cadastrar, editar e excluir unidades, salas e aparelhos | Sim | Não |
| Cadastrar sensores ESP32 | Sim | Não |
| Gerenciar usuários | Sim | Não |

- **Administrador principal:** é o login definido em `MOVEMENT_OPERATOR_USERNAME`. A senha fica só como hash scrypt em `MOVEMENT_OPERATOR_PASSWORD_HASH`.
- **Demais usuários:** administradores e professores são cadastrados na tela Usuários, com senha de pelo menos 12 caracteres. A tabela `users` guarda só o hash scrypt.
- **Sessões:** são assinadas e expiram em 1 hora (`MOVEMENT_SESSION_TTL_SECONDS`). Desativar um usuário ou trocar a senha dele encerra as sessões abertas.
- **Dispositivos:** cada sala tem um ESP32 responsável pelas medições, seja qual for a quantidade de aparelhos.
  - O token dele é exibido uma única vez no cadastro e guardado como hash SHA-256.
  - A API deduz a sala pelo token e recusa uma sala informada pelo cliente.

---

## O que o sistema faz

### Unidades, salas e aparelhos

As salas pertencem a uma unidade: `Centro → Sala 101, Sala 102…`, `Polo Sede → Auditório…`.
- Unidades e salas podem ser cadastradas, buscadas, editadas e excluídas.
- Uma unidade só pode ser excluída depois que as salas dela forem movidas ou excluídas.
- Uma sala com leituras não pode ser excluída.

Na migração de uma base existente, cada localização já informada nas salas vira uma unidade, e as salas sem localização vão para a "Unidade principal".

Cada sala tem vários aparelhos: Split, Janela, Cassete, Piso-teto, Portátil e VRF/VRV.
- O status do inventário indica a situação cadastral do equipamento.
- O estado ligado ou desligado vem da telemetria do sensor da sala.

### Catálogo do Inmetro

O catálogo vem da tabela de eficiência energética de condicionadores de ar do Programa Brasileiro de Etiquetagem (Inmetro), atualizada em 31/12/2025.
- São 1.507 modelos de 52 marcas, com tipo, BTU/h, tecnologia, classe e número de registro.
- Ao escolher o modelo, o formulário preenche tipo, BTU/h e inverter.
- O arquivo fica em `backend/app/data/inmetro_condicionadores.csv` e é carregado pela migração.
- Portáteis e VRF/VRV não constam da tabela e são preenchidos à mão.
- Em quatro modelos, a capacidade publicada estava sem os milhares ou trocada com a coluna em watts. Eles foram corrigidos e têm `corrected=1` no CSV.

Para atualizar com uma nova tabela do Inmetro, baixe o PDF de 28 colunas e, na pasta `backend`, execute:

```powershell
..\.venv\Scripts\python.exe -m pip install pdfplumber
..\.venv\Scripts\python.exe scripts\inmetro_catalog.py TABELA.pdf app\data\inmetro_condicionadores.csv
..\.venv\Scripts\python.exe -m app.cli catalog-import
```

O `pdfplumber` é usado só por esse conversor e não faz parte do `requirements.lock`.

### Painel e telemetria

O fluxo completo é `ESP32 → POST /api/telemetry → PostgreSQL → FastAPI → React`.

**Painel da sala:**
- temperatura e umidade interna e externa, ocupação e estado do A/C;
- inventário e gráfico por período;
- tema escuro com a logo do projeto e opção de tema claro;
- atualização a cada 15 segundos;
- sem leitura há mais de 90 s, a sala aparece como desatualizada.

**Telemetria idempotente:** cada leitura traz um `message_id` (UUID) e o horário da medição. O reenvio da mesma leitura responde 200 sem duplicar dados.

**Histórico:** médias mensais por sala e exportação CSV.

O site **não envia comandos físicos** de ligar ou desligar: quem decide o resfriamento é o firmware.

### Alertas

Cada leitura nova notifica observadores (padrão Observer, em `backend/app/events.py`), que registram alertas de **conforto** e de **umidade** da sala. Eles aparecem no painel e em `GET /api/rooms/{id}/alerts`.

### Plano de envio otimizado

Para cada hora do dia, um modelo de programação linear inteira escolhe o intervalo de envio do ESP32 entre 15, 30, 60, 90, 120 e 300 s. Ele minimiza o erro esperado da medição dentro de um orçamento diário de energia.
- **Resultado no perfil padrão:** com 0,32 J por envio e orçamento de 50%, a economia é de cerca de 51%.
- **Perfil real:** vem do histórico da sala.
- **Firmware:** consulta o intervalo da hora a cada 15 min em `GET /api/devices/me/sampling-interval`.
- **Site:** mostra o plano da sala (`GET /api/rooms/{id}/sampling-plan`).

A análise de sensibilidade sai de `backend/scripts/sensibilidade.py`, que não acessa o banco. Modelo, dados e limitações estão em [docs/pesquisa-operacional.md](docs/pesquisa-operacional.md).

### Relatórios em PDF

Relatório de todas as unidades, de uma unidade ou de uma sala, gerado no servidor com o ReportLab (`GET /api/reports/pdf`). Ele traz o inventário, as condições atuais e as médias mensais. Administradores e professores podem gerá-lo.

### Retenção dos dados

1. Leituras detalhadas ficam disponíveis por 30 dias, contados pelo horário da medição.
2. A API consolida as leituras mais antigas ao iniciar e a cada hora. A limpeza física pode ocorrer até uma hora depois do limite; as consultas detalhadas já ocultam leituras vencidas.
3. Cada sala tem uma única linha consolidada por mês civil, no fuso `America/Sao_Paulo`.
4. A consolidação acumula somas e quantidades. As médias são colunas geradas e armazenadas pelo PostgreSQL. Novos lotes são ponderados pela quantidade de amostras; médias de lotes não são promediadas entre si.
5. A remoção das leituras e o armazenamento dos acumuladores ocorrem na mesma transação. Um bloqueio transacional evita contagem duplicada entre vários processos.
6. O endpoint mensal combina as amostras consolidadas com as ainda detalhadas para apresentar uma única média do mês, sem sobreposição. O mês é parcial enquanto ainda houver uma parte dentro da janela de 30 dias; fica concluído quando todo o mês passou desse limite.
7. O resumo é mantido por 12 meses após o encerramento do respectivo mês. Exemplo: setembro/2026 fica salvo até 01/10/2027, às 00:00 no fuso de São Paulo. O painel pode mostrar 12 meses encerrados e o mês atual parcial.
8. Sem amostras, não se cria média artificial nem registro com zero. Leituras com mais de 30 dias são recusadas na entrada da API.

As médias são por amostra:
- temperatura e umidade, interna e externa;
- ocupação;
- percentual de amostras com A/C ligado. Esse percentual não é consumo de energia nem medição individual de cada aparelho.

Para uma execução manual ou agendada pelo sistema operacional, na pasta `backend`:

```powershell
..\.venv\Scripts\python.exe -m app.cli retain
```

A retenção depende de a API ou esse comando estar em execução. Depois de um período desligado, a próxima execução processa o acúmulo antes de descartar resumos vencidos. Configure `MOVEMENT_RETENTION_ENABLED=false` se adotar só um agendador externo.

---

## Hardware e firmware

### Montagem real

| Componente | Qtd. | Função |
| --- | --- | --- |
| ESP32 DevKit V1 | 1 | Lê os sensores, decide o resfriamento e envia as leituras por Wi-Fi |
| Barreira infravermelha iPEC IR15 Mini | 2 | Na mesma porta: A do lado de fora, B do lado de dentro |
| DHT11 + resistor de 10 kΩ | 1 | Temperatura e umidade, com pull-up na linha de dados |
| LED infravermelho 940 nm + BC547 + resistores de 68 Ω e 1 kΩ | 1 | Pulso IR para o ar-condicionado (~51 mA a partir do pino VIN) |
| Fonte de 12 V, 0,5 A ou mais | 1 | Alimenta as barreiras (cerca de 60 mA cada) |

| GPIO | Ligação |
| --- | --- |
| 13 | Barreira A (fora), contato do relé entre o pino e o GND, `INPUT_PULLUP` |
| 26 | Barreira B (dentro), idem. O GPIO 12 é pino de partida e não pode ficar em nível alto ao ligar. |
| 27 / 14 | DHT interno / DHT externo (opcional) |
| 2 | Base do BC547 pelo resistor de 1 kΩ |

A saída das barreiras é um contato seco de relé, então os 12 V nunca chegam ao ESP32 e não é preciso conversor de nível. Cálculos e ligações: [docs/fisica.md, seção 9](docs/fisica.md#9-montagem-real).

### Contagem de pessoas

O firmware deduz o sentido pela ordem dos cortes, com uma máquina de estados:
- A, depois B, depois as duas livres = **entrada**;
- B, depois A, depois as duas livres = **saída**.

Detalhes da contagem:
- filtra a oscilação do contato do relé por 30 ms;
- as barreiras precisam ficar a **15 cm ou mais** uma da outra.

No modo automático, o resfriamento só atua com a sala ocupada, e o LED IR desliga o aparelho quando a sala esvazia. Equações, contador e circuitos do Logisim estão em [docs/eletronica-digital.md](docs/eletronica-digital.md).

### Firmware

- Cadastre o dispositivo da sala na tela Unidades e salas e guarde o token exibido.
- Copie `firmware/climacontrol/config.h.example` para `config.h` e configure:
  - URL da API: em produção, `https://NOME-DO-APP.azurewebsites.net/api/telemetry`;
  - token do dispositivo;
  - certificado raiz do domínio (`MOVEMENT_CA_CERT`).
  O arquivo é privado e o Git o ignora.
- Para o DHT11 da montagem, inclua `#define MOVEMENT_DHT_TYPE DHT11` no `config.h`. Sem essa linha vale o DHT22, que é o modelo do Wokwi.
- O relógio é sincronizado por NTP e cada mensagem usa um UUID. Os reenvios mantêm o mesmo conteúdo até a confirmação.
- A fila guarda uma mensagem em RAM e não substitui uma fila persistente em flash.
- **Modo manual:** digite no monitor serial `AUTO`, `MANUAL`, `AC_ON`, `AC_OFF`, `TEMP+`, `TEMP-` ou a temperatura alvo (de 18 a 30). Ele volta ao automático depois de 30 min. O ThingSpeak/TalkBack do projeto original foi removido.
- **Comandos IR:** um pulso por comando no LED, e a duração diz qual é: 100 ms baixa 1 °C, 300 ms sobe 1 °C, 800 ms liga e 1,5 s desliga. O monitor serial mostra cada um, por exemplo `[IR] BAIXAR (100 ms) -> aparelho ligado em 23 C`.

Na rede local, o ESP32 físico precisa alcançar a API: rode o Uvicorn com `--host 0.0.0.0` e informe o IP do computador no firmware. Para testar sem hardware, publique uma leitura simulada. O token é solicitado sem eco, e o comando é só para desenvolvimento:

```powershell
.\.venv\Scripts\python.exe backend\scripts\publish_sample.py
```

### Simulação no Wokwi

O circuito está em `firmware/climacontrol/diagram.json` e no [projeto do Wokwi](https://wokwi.com/projects/465088583677549569).
- O Wokwi não tem a barreira iPEC: dois sensores PIR fazem o papel das barreiras A e B.
- Ele usa DHT22 e um LED com resistor.
- O Wokwi precisa de gateway ou túnel para acessar uma API local; com o site publicado, use o endereço do Azure.

---

## Requisitos da ExpoTech

| Disciplina | Entrega | Documento |
| --- | --- | --- |
| Eletrônica Digital e Analógica | Máquina de estados da porta, contador, comparador e acionamento do resfriamento | [docs/eletronica-digital.md](docs/eletronica-digital.md) |
| Física para Sistemas Computacionais | Lei de Ohm, potência, níveis lógicos, RC, consumo, energia por envio e modelo térmico | [docs/fisica.md](docs/fisica.md) |
| Software Architecture & Design Patterns | C4, UML, padrões Strategy e Observer, SOLID | [docs/arquitetura.md](docs/arquitetura.md) |
| Cloud Computing | Azure App Service, Supabase, variáveis de ambiente e CI/CD | *Como abrir*, neste README |
| Pesquisa Operacional | Programação linear inteira do plano de envio | [docs/pesquisa-operacional.md](docs/pesquisa-operacional.md) |

---

## Estrutura do projeto

```text
README.md  AGENTS.md  CLAUDE.md          # guia geral; guia para IAs e colaboradores (CLAUDE.md aponta para o AGENTS.md)
Dockerfile  .dockerignore                # imagem de produção: build do React + API, site em / e API em /api
contexto/                                # panorama do projeto para IAs, sem segredos; estado-atual.md diz o que falta

backend/
    pyproject.toml  requirements.lock    # dependências e ruff
    .env.example                         # modelo comentado das variáveis MOVEMENT_*
    alembic.ini  migrations/versions/    # migrações 0001 a 0005; as aplicadas não mudam
    README.md                            # tabela completa das rotas da API
    app/
        main.py                          # create_app: rotas de saúde, login e telemetria; inclui os routers
        site.py                          # create_site: API em /api e build do React em / (usado no contêiner)
        settings.py  database.py         # configuração; conexão com search_path por sessão
        certs/                           # CA raiz do Supabase, usada no verify-full
        models.py  schemas.py            # tabelas (SQLAlchemy 2.0) e contratos da API (Pydantic)
        auth.py  security.py  users.py   # perfis, hash scrypt, sessões assinadas e cadastro de usuários
        dependencies.py  repository.py   # injeção de dependências e repositório da telemetria
        management.py                    # unidades, salas, aparelhos e dispositivos
        catalog.py  data/                # catálogo do Inmetro (CSV)
        reports.py  assets/              # relatório em PDF (ReportLab) e logo
        retention.py                     # consolidação mensal e limpeza das leituras
        optimization.py  sampling.py     # programação linear inteira e rotas do plano de envio (Strategy)
        events.py                        # Observer: alertas de conforto e umidade
        cli.py                           # password-hash, retain, catalog-import, local, create-device
        configure_existing.py            # liga a API a um PostgreSQL existente ou ao Supabase
        localdev.py                      # PostgreSQL próprio de desenvolvimento em .local/postgres-dev
    scripts/                             # fora da imagem: Azure, catálogo, leitura simulada, sensibilidade
    tests/                               # pytest contra um PostgreSQL de verdade (banco *_test)

frontend/
    src/
        App.jsx  main.jsx                # aplicação e telas principais
        components/                      # login, unidades, usuários, relatórios, gráfico, alertas, plano de envio
        services/movementApi.js          # único cliente HTTP (com testes em movementApi.test.js)
        hooks/  config/  styles/         # atualização do painel, tema, catálogo e estilos

firmware/climacontrol/
    sketch.ino                           # ESP32: porta, DHT, resfriamento, envio e plano de envio
    config.h.example                     # modelo do config.h privado (URL, token, CA, tipo do DHT)
    diagram.json  wokwi-project.txt      # circuito no Wokwi

hardware/logica/                         # verificação das equações e teste C++ da porta e dos comandos IR (CI)
docs/                                    # física, eletrônica digital, arquitetura e pesquisa operacional
database/                                # consultas SQL e importação de servidores no pgAdmin
scripts/                                 # iniciar.ps1 e parar.ps1: sobem e encerram o site e a API no Windows
.github/workflows/ci.yml                 # CI em todas as branches; publicação da imagem só na main
```

---

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

Os testes criam e removem apenas um schema aleatório nesse banco. Eles cobrem:
- autenticação, validação, idempotência e concorrência;
- cadastros e isolamento por sala;
- migrações (upgrade, downgrade e `alembic check`);
- média ponderada, fronteiras de data, retenção de 12 meses e reversão da remoção quando a agregação falha;
- otimização, alertas e arquitetura.

A lista completa, incluindo `ruff format --check`, está no [AGENTS.md](AGENTS.md#verificação-obrigatória-antes-de-cada-commit).

## Limitações

- O site não envia comandos físicos aos aparelhos.
- O LED IR manda pulsos simples (a duração diz o comando) e não implementa o protocolo real dos fabricantes.
- O CI não compila o firmware, só testa a lógica da porta e dos comandos IR; o firmware ainda não foi gravado num ESP32 real.
- Medição de energia por aparelho e permissões por sala exigem implementações adicionais.
