# Firmware ESP32 2.5.2

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
