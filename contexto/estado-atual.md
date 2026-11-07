# Estado atual

Atualizado em **07/11/2026**. Atualize este arquivo e a data ao terminar uma tarefa que mude o que está aqui.

## Pronto

- As etapas 1 a 7 estão implementadas e mescladas na `Devlop` e na `main`.
- A conexão com o Supabase verifica o certificado (`verify-full`) com a CA oficial embutida em `backend/app/certs/`.
- Verificações passando: testes de backend e de frontend, build, lint, lógica da porta, comandos IR e build da imagem. O CI da `main` está verde.
- O firmware está pronto para a montagem real: Wi-Fi no `config.h`, temperatura interna lida do DHT, porta numa tarefa própria (não perde passagens durante o envio) e comando IR no protocolo do fabricante (IRremoteESP8266), com `IR_TESTE` para descobrir o protocolo. O aparelho desliga quando a sala esvazia no modo automático.
- A imagem de produção (`movement:latest`) está publicada no registro do Azure.
- O Supabase está configurado: schema `movement` protegido da API pública, catálogo do Inmetro carregado e nenhum alerta de segurança.

## Bloqueado

- **O Web App do Azure está parado e sem variáveis de ambiente.** Depende de quem tem acesso ao portal:
  1. aplicar as variáveis, trocando na `MOVEMENT_DATABASE_URL` o `sslmode=require` por `sslmode=verify-full&sslrootcert=app%2Fcerts%2Fsupabase-root-2021.crt`;
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
- Gravar o firmware no ESP32 e testar com o ar-condicionado da demonstração: `IR_TESTE` para achar o protocolo, `IR <nome>` para gravar, depois entrar e sair pela porta e ver o aparelho ligar e desligar. O firmware com a IRremoteESP8266 ainda não foi compilado.
- Montar o circuito físico e testar as barreiras reais. O firmware nunca foi gravado num ESP32 de verdade.
- Confirmar com os professores que o Supabase vale como banco gerenciado e o Wokwi como simulação do circuito.

## Problemas conhecidos

- **Segredos de produção na `Devlop`:** o commit `8feb992` incluiu `backend/variaveis-azure.json` com os valores reais (senha do banco, chave de sessão e hash do administrador). A equipe decidiu removê-lo depois. Até lá:
  - não mesclar a `Devlop` na `main`, porque o arquivo entraria na imagem Docker;
  - ao remover, trocar os segredos, porque eles continuam no histórico do Git.
- **Issues com texto antigo:** a #3 foi fechada com 8 dos 11 critérios pendentes. As issues #4 a #7 e #11 descrevem estados anteriores (a #6 cita a migração 0004; a #7, o desenho antigo com sensores PIR). Vale o código.
- **Branches antigas:** `feat/5-calculos-fisica`, `feat/6-arquitetura-padroes`, `feat/7-circuito-logisim`, `Test` e `3-etapa-3-deploy-no-azure-com-cicd` já estão inteiras na `main` e podem ser apagadas.
- **Cópia no OneDrive:** a pasta do projeto no OneDrive não funciona com git e está desatualizada. Trabalhe num clone fora do OneDrive.
