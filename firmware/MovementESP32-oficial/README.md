# Firmware ESP32 2.6.2

A 2.6.1 descarta o quadro zerado do DHT11 e só publica com temperatura externa real.
A 2.6.2 faz o IR_TESTE passar também por MIRAGE (Philco) e NEOCLIMA (controles da série ZH,
como ZH/TT-14 e ZH/TY-01). Alguns controles ZH usam uma variante sem suporte na biblioteca.

Agora é possível escolher entre o LED do ESP32 e o emissor do POCO F7 pelo site
ou pelos comandos `EMISSOR ESP32` / `EMISSOR XIAOMI` do monitor serial.
O modo Xiaomi exige Tasker + Android IR Blaster e os sinais reais do ar;
consulte [o guia completo](../../docs/xiaomi-ir.md). Inclua `ir_gateway.h` ao copiar a pasta.

Esta pasta abre diretamente no Arduino IDE. O arquivo .ino tem o mesmo nome da pasta.
As duas copias do firmware sao verificadas pelos testes do projeto.

1. Mantenha seu config.h privado se ja existir. Caso contrario, copie config.h.example
   para config.h e preencha Wi-Fi e o token do ESP32 ja vinculado a sala.
   A URL de producao e o certificado DigiCert Global Root G2 estao no exemplo.
   Nao gere outro token nem compartilhe este arquivo. Nunca envie config.h ao Git.
2. Instale o suporte esp32 2.0.17, DHT sensor library (Adafruit) 1.4.7,
   Adafruit Unified Sensor 1.1.15 e IRremoteESP8266 2.9.0.
3. Escolha ESP32 Dev Module, Partition Scheme: Huge APP (3MB No OTA/1MB SPIFFS),
   a porta COM da placa e Carregar. DHT11 usa GPIO27; emissor IR usa GPIO2.
4. Abra o monitor serial a 115200 baud. A API precisa estar na versao nova com
   /devices/me/control incluindo ir_protocols e ir_revision. O protocolo vem da sala
   identificada pelo token, sem definir manualmente MOVEMENT_AC_PROTOCOLO.
5. Na visao geral da sala, o administrador pode usar Enviar protocolo para o ESP32
   quando aparecer sem protocolo. O envio acontece na proxima consulta: ate 15 s com
   a sala ocupada, ou 1 min vazia. Se offline, aguarda reconexao.
6. Confirme fisicamente ligar, temperatura e desligar. SAMSUNG_AC para AR24BVFAAWKNAZ
   e um candidato por familia, ainda sem confirmacao nesse modelo. Se precisar testar
   outro protocolo, use IR_TESTE e salve o que funcionar no cadastro do aparelho.

O botao prepara um reenvio da configuracao; nao liga o ar nem muda o modo do professor.
O ESP32 confirma seu estado no contato seguinte. O dispositivo precisa receber este
firmware: um firmware antigo nao passa a interpretar novos campos apenas pelo botao.

O ESP32 guarda o ultimo estado enviado a cada protocolo da sala. A biblioteca IR usa
esse estado para mandar a mensagem de ligar/desligar (Samsung) e alternar o turbo
(Midea, Coolix, Fujitsu) so quando muda; depois do IR_TESTE, recomeca de desligado.
Opcionais no config.h: MOVEMENT_DHT_EXTERNO 0 (sem o DHT de fora),
MOVEMENT_BARREIRAS_INVERTIDAS 1 (barreira livre aparece cortada) e MOVEMENT_PINO_*.

Melhorias do equipamento real preservadas da versão 2.5.4:
- A contagem de pessoas fica na memoria RTC e volta depois de um reinicio do ESP32
  (travamento, watchdog). Falta de energia ou o botao EN recomecam do zero.
- Uma vez por dia, as 3 h de Brasilia, a sala e dada como vazia, para um erro de contagem
  nao deixar o ar ligado a noite toda. MOVEMENT_HORA_ZERAR muda a hora; -1 desliga.
- Sem resposta do NTP (rede que bloqueia a porta 123), o relogio e acertado pela hora
  que o site manda em /devices/me/control (server_time).
- O handshake da conexao segura desiste em 8 s (o padrao do ESP32 e 120 s e prenderia
  o loop). Uma leitura que o site recusa de vez (4xx) e descartada, e nao reenviada.
