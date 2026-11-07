# Infraestrutura

## Ambientes

| Ambiente | Banco | Onde roda | Para |
| --- | --- | --- | --- |
| Local | PostgreSQL na máquina (instância própria criada por `app.localdev`, ou um banco existente) | API e Vite no computador | Desenvolvimento |
| Testes | Banco PostgreSQL com nome terminado em `_test`; cada execução cria e apaga um schema aleatório | `pytest` | Testes automatizados |
| CI | PostgreSQL 18 em contêiner do GitHub Actions | GitHub Actions | Verificar cada push e PR |
| Produção | Supabase (PostgreSQL 17 gerenciado) | Azure App Service | Site público |

## Caminho de uma mudança até a produção

```text
feat/<n>-… ─PR─▶ Devlop ─PR─▶ main ─CI─▶ imagem no registro do Azure ─webhook─▶ Web App reinicia ─▶ migrações ─▶ site no ar
```

1. Em toda branch, o CI (`.github/workflows/ci.yml`) roda quatro jobs:
   - **backend:** ruff e pytest;
   - **frontend:** lint, testes e build;
   - **firmware:** lógica da porta, comandos IR e equações;
   - **image:** build da imagem Docker.
2. Só um push na `main` publica a imagem `movement`, com as tags `latest` e o SHA do commit, no Azure Container Registry.
3. O deploy contínuo do Web App puxa a nova `latest` e reinicia o contêiner.
4. Ao iniciar, o contêiner roda `alembic upgrade head` (aplica as migrações pendentes no Supabase) e depois sobe o Uvicorn na porta 8000.

## Azure (hospedagem)

- **Serviço:** App Service Linux com contêiner (Web App), região West US 3, assinatura Azure for Students.
- **Plano:** F1 é gratuito, mas hiberna sem uso e limita a CPU diária. B1 consome créditos.
- **Endereço público:** <https://movement-gxdafrgwcjd9f7gx.westus3-01.azurewebsites.net>. O site fica em `/`, a API em `/api` e a documentação em `/api/docs`.
- **Imagem:** vem do Azure Container Registry (plano Basic). O GitHub tem a variável `ACR_LOGIN_SERVER` e os segredos `ACR_USERNAME` e `ACR_PASSWORD`. Nos logs do CI, o nome de usuário do registro aparece mascarado como `***`.
- **Configuração no portal:**
  - variáveis de ambiente (abaixo), incluindo `WEBSITES_PORT=8000`;
  - Continuous deployment ligado no Deployment Center;
  - Health check em `/api/health`.
- O HTTPS é fornecido pelo App Service. O ESP32 envia para `<endereço>/api/telemetry`, com o certificado raiz do domínio no `config.h`.

## Supabase (banco gerenciado)

- Projeto "Movement", PostgreSQL 17, região us-west-2 (próxima do Azure West US 3).
- As tabelas ficam no schema **`movement`**. O schema `public` fica vazio de propósito: o Supabase o expõe pela API REST com a chave anônima, e os papéis `anon` e `authenticated` não têm acesso ao `movement`.
- A conexão usa o **Session pooler** (porta 5432, aceita IPv4) com TLS verificado (`verify-full`).
  - A CA do Supabase é privada, por isso a cópia oficial fica em `backend/app/certs/supabase-root-2021.crt`.
  - Na URL, o `sslrootcert` é relativo à pasta `backend` (`backend/app/database.py`).
  - A conexão direta só tem IPv6.
  - O Transaction pooler (porta 6543) não preserva configurações de sessão.
  - Por isso nenhum dos dois é usado.
- **O pooler ignora o `search_path` da URL.** Por isso a API executa `SET SESSION search_path` em cada conexão nova, a partir de `MOVEMENT_DATABASE_SCHEMA=movement` (`backend/app/database.py`).
- O painel de segurança (Advisors) não aponta alertas.
- O Supabase é usado só como PostgreSQL. Auth, Storage e a API REST dele não fazem parte do projeto.

## Variáveis de ambiente

Todas têm o prefixo `MOVEMENT_` e são lidas por `backend/app/settings.py`. O modelo comentado está em `backend/.env.example`.

| Variável | Para |
| --- | --- |
| `MOVEMENT_DATABASE_URL` | Conexão com o PostgreSQL (segredo) |
| `MOVEMENT_DATABASE_SCHEMA` | Schema das tabelas (`movement` no Supabase) |
| `MOVEMENT_SESSION_SECRET` | Chave que assina as sessões de login (segredo) |
| `MOVEMENT_OPERATOR_USERNAME` | Login do administrador principal |
| `MOVEMENT_OPERATOR_PASSWORD_HASH` | Hash scrypt da senha desse administrador (segredo) |
| `MOVEMENT_CORS_ORIGINS` | Endereços autorizados a chamar a API pelo navegador |
| `MOVEMENT_SESSION_TTL_SECONDS` | Duração da sessão (padrão 1 h) |
| `MOVEMENT_STALE_AFTER_SECONDS` | Tempo sem leitura até a sala aparecer como desatualizada |
| `MOVEMENT_RETENTION_ENABLED`, `MOVEMENT_RETENTION_INTERVAL_SECONDS` | Consolidação e limpeza automáticas das leituras |
| `MOVEMENT_ENERGY_PER_SEND_J`, `MOVEMENT_SAMPLING_BUDGET_RATIO` | Parâmetros da otimização do envio |
| `WEBSITES_PORT` | Só no Azure: porta do contêiner (8000) |

## Onde ficam os segredos

Nenhum destes arquivos está no Git, e o `.gitignore` e o `.dockerignore` os excluem. Para pedir um valor, fale com o humano responsável.

| Local | Contém |
| --- | --- |
| `backend/.env` | Configuração do ambiente local |
| `backend/.env.supabase` | Valores de produção. Fica só no computador de quem configurou o Supabase e é a origem das variáveis do Azure (`backend/scripts/azure_settings.py`). |
| Variáveis de ambiente do Web App | Os valores de produção em uso |
| Segredos do GitHub | Credenciais do registro de imagens |
| `firmware/climacontrol/config.h` | Wi-Fi, URL da API e token do ESP32 |
| `.local/postgres-dev/` | Credenciais do banco local de desenvolvimento |

Os usuários cadastrados ficam na tabela `users` (hash scrypt). O administrador principal fica só nas variáveis de ambiente. Os tokens dos ESP32 ficam como hash SHA-256 na tabela `devices`. Segredos só devem circular por conversa privada e temporária, nunca no grupo da equipe.
