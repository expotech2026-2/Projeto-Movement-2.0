# Estado atual

Atualizado em **06/11/2026**. Atualize este arquivo e a data ao terminar uma tarefa que mude o que está aqui.

## Pronto

- As etapas 1 a 7 estão implementadas e mescladas na `Devlop` e na `main`, que têm os mesmos arquivos.
- Verificações passando: testes de backend e de frontend, build, lint, lógica da porta e build da imagem. O CI da `main` está verde.
- A imagem de produção (`movement:latest`) está publicada no registro do Azure.
- O Supabase está configurado: schema `movement` protegido da API pública, catálogo do Inmetro carregado e nenhum alerta de segurança.

## Bloqueado

- **O Web App do Azure está parado e sem variáveis de ambiente.** Depende de quem tem acesso ao portal:
  1. aplicar as variáveis;
  2. dar Start (com plano B1 se o F1 estourar a cota);
  3. ligar o Continuous deployment;
  4. configurar o Health check em `/api/health`.
- No primeiro início, o contêiner leva o banco da migração `0003` para a `0005_alerts`.
- Depois de ligado, falta testar o site público:
  - `/api/health` e `/api/ready`;
  - o site em `/` e a documentação em `/api/docs`;
  - uma rota protegida sem login, que deve responder 401.

## Partes manuais pendentes 👤

- **#5:** medir no Wokwi a duração real do envio, que alimenta a energia por envio da Pesquisa Operacional.
- **#7:** montar os circuitos no Logisim Evolution e anexar os prints (`docs/eletronica-digital.md`, seção 11).
- Montar o circuito físico e testar as barreiras reais. O firmware nunca foi gravado num ESP32 de verdade.
- Confirmar com os professores que o Supabase vale como banco gerenciado e o Wokwi como simulação do circuito.

## Problemas conhecidos

- **TLS no configurador:** `app.configure_existing` força `sslmode=verify-full` em conexões remotas, e a verificação do certificado falha no pooler do Supabase porque a CA dele não está no repositório de certificados do sistema.
  - O `backend/.env.supabase` em uso tem `sslmode=require`, funciona e mantém a conexão criptografada.
  - Não o regenere com o configurador sem informar `sslrootcert` com a CA do Supabase.
  - Correção proposta: incluir o certificado da CA do Supabase no repositório e na imagem.
- **Issues com texto antigo:** a #3 foi fechada com os critérios desmarcados. As issues #4 a #7 e #11 descrevem estados anteriores (a #6 cita a migração 0004; a #7, o desenho antigo com sensores PIR). Vale o código.
- **Branches antigas:** `feat/5-calculos-fisica`, `feat/6-arquitetura-padroes`, `feat/7-circuito-logisim`, `Test` e `3-etapa-3-deploy-no-azure-com-cicd` já estão inteiras na `main` e podem ser apagadas.
- **Cópia no OneDrive:** a pasta do projeto no OneDrive não funciona com git e está desatualizada. Trabalhe num clone fora do OneDrive.
