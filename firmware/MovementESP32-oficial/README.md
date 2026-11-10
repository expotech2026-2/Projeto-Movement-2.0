# Firmware oficial para o Arduino IDE

Esta pasta abre direto no Arduino IDE, que exige o `.ino` com o mesmo nome da pasta. O código é uma cópia do `firmware/climacontrol/sketch.ino`, e o CI (`hardware/logica/testar_firmware.py`) falha se as duas cópias ficarem diferentes. Mude o `sketch.ino` e copie-o para cá.

1. Copie `config.h.example` para `config.h` e preencha a URL da API, o token do dispositivo, o certificado, o Wi-Fi e o tipo do DHT. O `config.h` fica fora do Git.
2. Instale as bibliotecas **DHT sensor library** (Adafruit) e **IRremoteESP8266**.
3. Placa **ESP32 Dev Module**, porta COM da placa, **Carregar**.
4. No monitor serial (115200 baud), aponte o LED para o ar e rode `IR_TESTE`. Grave o protocolo que funcionar com `IR <nome>`, por exemplo `IR GREE`.

Os comandos do monitor serial e a tabela de protocolos por marca estão em [contexto/hardware.md](../../contexto/hardware.md#comando-ir-ao-ar-condicionado).
