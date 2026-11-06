# Hardware

## Equipamentos da montagem real

| Componente | Qtd. | Função |
| --- | --- | --- |
| ESP32 DevKit V1 | 1 | Lê os sensores, decide o resfriamento e envia as leituras por Wi-Fi |
| Barreira infravermelha iPEC IR15 Mini | 2 | Detecta a passagem na **mesma porta**: A do lado de fora, B do lado de dentro |
| DHT11 | 1 | Temperatura e umidade da sala |
| LED infravermelho 940 nm | 1 | Simula o comando IR enviado ao ar-condicionado |
| Transistor NPN BC547 | 1 | Chave do LED (o pino do ESP32 não fornece a corrente do LED) |
| Resistor 1 kΩ | 1 | Base do BC547 |
| Resistor 68 Ω | 1 | Limita a corrente do LED a ~51 mA, a partir dos 5 V do pino VIN |
| Resistor 10 kΩ | 1 | Pull-up da linha de dados do DHT11 |
| Fonte de 12 V, 0,5 A ou mais | 1 | Alimenta as duas barreiras (cerca de 60 mA cada) |
| Protoboard e jumpers | 1 | Montagem |

Não é preciso conversor de nível nem optoacoplador. A saída das barreiras é um contato seco de relé: o comum vai ao GND e o NF ao GPIO com pull-up. Assim os 12 V nunca chegam ao ESP32, e o GND da fonte de 12 V não precisa ser ligado ao do ESP32.

## Pinos do ESP32

| GPIO | Ligação |
| --- | --- |
| 13 | Barreira A (fora), `INPUT_PULLUP` |
| 26 | Barreira B (dentro), `INPUT_PULLUP` |
| 27 | DHT da sala (interno) |
| 14 | DHT externo (opcional; a lista tem um só DHT11, e sem ele o firmware mantém o último valor externo) |
| 2 | Base do BC547 pelo resistor de 1 kΩ (LED IR) |

**Não use o GPIO 12** para sensores com pull-up: nível alto nele na partida impede o ESP32 de iniciar. Por isso a barreira B fica no GPIO 26.

## Como a contagem funciona

- Feixe livre → contato fechado → GPIO em 0. Feixe cortado → GPIO em 1.
- O firmware filtra a oscilação do contato do relé por 30 ms.
- Uma máquina de estados de 5 estados deduz o sentido pela ordem dos cortes:
  - corta A, depois B, e libera = **entrada** (ocupação +1);
  - corta B, depois A, e libera = **saída** (ocupação −1).
- As barreiras devem ficar a **15 cm ou mais** uma da outra. Mais perto que isso, uma pessoa corta as duas ao mesmo tempo e o sentido fica ambíguo.
- No modo automático, o resfriamento só atua com a sala ocupada e a temperatura mais de 0,5 °C acima do alvo. O alvo cai 0,3 °C por pessoa, partindo de 24 °C, entre 18 e 30 °C.
- O modo manual permite resfriar mesmo com a sala vazia e volta ao automático depois de 30 min.

Equações lógicas, tabela de estados, contador e circuito do Logisim estão em `docs/eletronica-digital.md`. Cálculos elétricos (Ohm, potência, consumo, RC, energia por envio) e a seção "Montagem real" estão em `docs/fisica.md`.

## Firmware

- Fica em `firmware/climacontrol/sketch.ino` (Arduino C++). A única biblioteca externa é a do DHT.
- As configurações privadas ficam em `config.h`, fora do Git e copiado de `config.h.example`: URL da API, token do dispositivo, certificado CA e tipo do DHT.
- Sem `MOVEMENT_DHT_TYPE DHT11` no `config.h`, o firmware usa DHT22, que é o modelo do Wokwi.
- Lê os sensores a cada 2 s e envia ao `POST /api/telemetry` com o token Bearer. O intervalo de envio vem do plano otimizado, consultado a cada 15 min.
- Usa NTP para o horário e um UUID por mensagem. O reenvio mantém o mesmo conteúdo até a confirmação. A fila guarda uma mensagem na RAM.
- O LED IR só simula pulsos; não implementa o protocolo real dos fabricantes de ar-condicionado.

O CI não compila o firmware. Ele extrai a lógica da porta do `sketch.ino` e a testa em C++ com 13 cenários (`hardware/logica/testar_firmware.py`), além de verificar as equações (`hardware/logica/verificar_logica.py`). Mudanças no firmware precisam de teste manual no Wokwi, descrito no PR.

## Simulação no Wokwi

`firmware/climacontrol/diagram.json` é o circuito no Wokwi. Como o Wokwi não tem a barreira iPEC, dois sensores PIR fazem o papel das barreiras A e B (GPIO 13 e 26). Ele usa DHT22 e um LED com resistor no lugar do conjunto BC547 + LED IR. Para o Wokwi falar com a API, ela precisa estar acessível na internet (o site do Azure) ou passar por um túnel.
