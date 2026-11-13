# Estado atual

Atualizado em **12/11/2026**. Atualize este arquivo e a data ao terminar uma tarefa que mude o que está aqui.

## Em desenvolvimento: protocolo IR pelo cadastro

- Branch `fix/protocolo-ir-cadastro-ar`: cadastro salva protocolo e variante por aparelho,
  e `GET /devices/me/control` envia os pares distintos dos aparelhos ativos da sala do token.
- Migração `0009_appliance_ir`: preenche cadastros existentes pela marca + modelo exatos.
- Migração `0010_ir_brand_candidate`: sem modelo exato, protocolo candidato pela marca;
  só 1 dos 1.507 modelos do Inmetro tinha correspondência exata.
- Firmware 2.5.2: com a lista do site vazia, usa o protocolo gravado por `IR <nome>`.
- Auditoria somente leitura encontrou 3 Samsung AR24BVFAAWKNAZ em produção e 1 em teste.
  `SAMSUNG_AC` está registrado como candidato por família, sem confirmação nesse modelo.
- Firmware 2.5.1 aplica a configuração mesmo sem mudar a versão do comando do professor;
  transmite cada par protocolo/variante distinto. Todos recebem o mesmo estado da sala.
- Banco remoto expandido em 12/11/2026: 3 aparelhos de produção e 1 de teste com
  SAMSUNG_AC, variante 1, origem family_candidate. Campos novos e revisão IR da sala
  criados; alembic_version preservada em 0008 para manter a API publicada saudável.
  /api/health e /api/ready responderam 200 após a mudança.
- A migração 0009 reconhece a expansão e só avança a revisão quando a API nova entrar.
- Botão na visão geral: Enviar protocolo para o ESP32, só para administrador e quando
  o diagnóstico indica sem protocolo. POST /rooms/{id}/ir-protocol incrementa apenas a
  revisão IR; o dispositivo recebe no próximo contato, sem mudar o comando do professor.
- Código ainda sem deploy e sem gravação da placa. Falta confirmar fisicamente ligar,
  desligar e temperatura no Samsung cadastrado.

## Pronto

- As etapas 1 a 7 estão implementadas e mescladas na `Devlop` e na `main`.
- A conexão com o Supabase verifica o certificado (`verify-full`) com a CA oficial embutida em `backend/app/certs/`.
- Verificações passando: testes de backend e de frontend, build, lint, lógica da porta, comandos IR e build da imagem. O CI da `main` está verde.
- O firmware está pronto para a montagem real: Wi-Fi no `config.h`, temperatura interna lida do DHT, porta numa tarefa própria (não perde passagens durante o envio) e comando IR no protocolo do fabricante (IRremoteESP8266), com `IR_TESTE` para descobrir o protocolo. O aparelho desliga quando a sala esvazia no modo automático.
- Controle pelo site: professores e administradores fixam a temperatura (16 a 30 °C) ou desligam o aparelho por 2 h, e o ESP32 busca o comando. No automático, o alvo usa o calor do corpo humano (36,5 °C) e a faixa da NR-17 (18 a 25 °C). A temperatura externa vem da Open-Meteo pela cidade da unidade. Isso traz a migração `0006_room_control`, aplicada pelo contêiner ao subir.
- A imagem de produção (`movement:latest`) está publicada no registro do Azure.
- O Supabase está configurado: schema `movement` protegido da API pública, catálogo do Inmetro carregado e nenhum alerta de segurança.

## Produção

- O site está no ar em <https://movement-gxdafrgwcjd9f7gx.westus3-01.azurewebsites.net>: `/api/health` e `/api/ready` respondiam 200 em 07/11/2026.
- Ao subir a versão da `Devlop`, o contêiner leva o Supabase da migração `0005_alerts` para a `0006_room_control`. Se a imagem nova não entrar sozinha, falta ligar o Continuous deployment no portal.
- O ESP32 fala com o site em HTTPS usando a raiz DigiCert Global Root G2 no `MOVEMENT_CA_CERT`.

## Partes manuais pendentes 👤

- **#5:** medir no Wokwi a duração real do envio, que alimenta a energia por envio da Pesquisa Operacional.
- **#7:** montar os circuitos no Logisim Evolution e anexar os prints (`docs/eletronica-digital.md`, seção 11).
- Cadastrar a cidade de cada unidade (tela Unidades e salas) para o ESP32 receber a temperatura externa.
- Gravar o firmware no ESP32 e testar com o ar-condicionado da demonstração: `IR_TESTE` para achar o protocolo, `IR <nome>` para gravar, depois entrar e sair pela porta e ver o aparelho ligar e desligar. O firmware com a IRremoteESP8266 ainda não foi compilado.
- Montar o circuito físico e testar as barreiras reais. O firmware nunca foi gravado num ESP32 de verdade.
- Confirmar com os professores que o Supabase vale como banco gerenciado e o Wokwi como simulação do circuito.

## Problemas conhecidos

- **Segredos no histórico do Git:** o commit `8feb992` incluiu `backend/variaveis-azure.json` com os valores reais (senha do banco, chave de sessão e hash do administrador). O arquivo saiu do repositório em 07/11/2026 e está no `.gitignore` e no `.dockerignore`, mas os valores continuam no histórico. Falta trocar a senha do banco no Supabase e a `MOVEMENT_SESSION_SECRET` no Azure.
- **Issues com texto antigo:** a #3 foi fechada com 8 dos 11 critérios pendentes. As issues #4 a #7 e #11 descrevem estados anteriores (a #6 cita a migração 0004; a #7, o desenho antigo com sensores PIR). Vale o código.
- **Branches antigas:** `feat/5-calculos-fisica`, `feat/6-arquitetura-padroes`, `feat/7-circuito-logisim`, `Test` e `3-etapa-3-deploy-no-azure-com-cicd` já estão inteiras na `main` e podem ser apagadas.
- **Cópia no OneDrive:** a pasta do projeto no OneDrive não funciona com git e está desatualizada. Trabalhe num clone fora do OneDrive.


## Promoção pela Devlop em 12/11/2026

- Integração com a main preserva a geração de novo token do ESP32 junto do envio de protocolo IR.
- O deploy-dev antigo ficava esperando o registro do histórico no SCM, que respondia 503.
  O pipeline passa a configurar a imagem imutável do commit e reiniciar pelo Azure CLI,
  sem depender desse histórico. A prontidão é conferida com prazo limitado.
- Na inspeção, produção respondeu health/ready 200; movement-dev respondeu 503.
