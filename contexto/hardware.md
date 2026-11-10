# Hardware

## Equipamentos da montagem real

| Componente | Qtd. | Função |
| --- | --- | --- |
| ESP32 DevKit V1 | 1 | Lê os sensores, decide o resfriamento e envia as leituras por Wi-Fi |
| Barreira infravermelha iPEC IR15 Mini | 2 | Detecta a passagem na **mesma porta**: A do lado de fora, B do lado de dentro |
| DHT11 | 1 | Temperatura e umidade da sala |
| LED infravermelho 940 nm | 1 | Manda ao ar-condicionado o código infravermelho do fabricante |
| Transistor NPN BC547 | 1 | Chave do LED (o pino do ESP32 não fornece a corrente do LED) |
| Resistor 1 kΩ | 1 | Base do BC547 |
| Resistor 68 Ω | 1 | Limita a corrente do LED a ~51 mA, a partir dos 5 V do pino VIN |
| Resistor 10 kΩ | 1 | Pull-up da linha de dados do DHT11 |
| Fonte de 12 V, 0,5 A ou mais | 1 | Alimenta as duas barreiras (cerca de 60 mA cada) |
| Protoboard e jumpers | 1 | Montagem |

Não é preciso conversor de nível nem optoacoplador. A saída das barreiras é um contato seco de relé: o comum (C ou CM) vai ao GND, e ao GPIO com pull-up vai o contato que fica **fechado com o feixe livre** (NF ou NA, conforme o modelo). A ordem dos bornes muda entre os modelos: a placa verde tem `NF NA C` e a laranja (A2924), `NA NF CM`. Se, com a porta vazia, o monitor serial mostrar `[BARREIRA] A cortada` logo depois de ligar, troque o fio para o outro contato. Assim os 12 V nunca chegam ao ESP32, e o GND da fonte de 12 V não precisa ser ligado ao do ESP32.

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
- No modo automático, o aparelho só fica ligado com a sala ocupada. O alvo parte de 24 °C (23 °C com mais de 30 °C lá fora, 25,5 °C com menos de 22 °C), desconta o aquecimento que as pessoas causam em 10 minutos, calculado pela temperatura do corpo (36,5 °C), e fica entre 18 e 25 °C, a faixa da NR-17 (`docs/fisica.md`, seção 8).
- O LED IR liga o aparelho quando alguém entra (ou no modo manual) e o desliga quando a sala esvazia no modo automático ou com `AC_OFF`. O alvo vai no mesmo comando (seção "Comando IR ao ar-condicionado").
- O modo manual permite resfriar mesmo com a sala vazia e volta ao automático depois de 2 h. Ele vem do site (professor ou administrador) ou do monitor serial.
  - Os comandos são digitados no monitor serial: `AUTO`, `MANUAL`, `AC_ON`, `AC_OFF`, `TEMP+`, `TEMP-`, a temperatura alvo, `IR <protocolo>` ou `IR_TESTE`.
  - O ThingSpeak/TalkBack do projeto original foi removido.

Equações lógicas, tabela de estados, contador e circuito do Logisim estão em `docs/eletronica-digital.md`. Cálculos elétricos (Ohm, potência, consumo, RC, energia por envio) e a seção "Montagem real" estão em `docs/fisica.md`.

## Firmware

- Fica em `firmware/climacontrol/sketch.ino` (Arduino C++). As bibliotecas externas são a do DHT e a IRremoteESP8266.
- As configurações privadas ficam em `config.h`, fora do Git e copiado de `config.h.example`: URL da API, token do dispositivo, certificado CA, rede Wi-Fi, tipo do DHT e protocolo IR.
- Sem `MOVEMENT_DHT_TYPE DHT11` no `config.h`, o firmware usa DHT22, que é o modelo do Wokwi.
- Lê os sensores a cada 2 s e envia ao `POST /api/telemetry` com o token Bearer. O intervalo de envio vem do plano otimizado, consultado a cada 15 min.
- Usa NTP para o horário e um UUID por mensagem. O reenvio mantém o mesmo conteúdo até a confirmação. A fila guarda uma mensagem na RAM.
- As barreiras são lidas a cada 10 ms numa tarefa própria, no núcleo 0. Um envio HTTP ou a reconexão do Wi-Fi não fazem perder passagens.
- A temperatura interna enviada à API é a medida pelo DHT. A externa vem do site (Open-Meteo, pela cidade da unidade); sem cidade, do DHT externo, se houver.
- A cada 15 s com a sala ocupada (1 min com ela vazia), o ESP32 busca em `GET /api/devices/me/control` o comando do professor e a temperatura externa. Cada comando tem uma versão e é aplicado uma vez; o monitor serial mostra `[SITE] Comando N do professor`.
- Toda chamada à API leva, além do token, o diagnóstico em cabeçalhos `X-Movement-*`: versão do código (`VERSAO_FIRMWARE`), sinal Wi-Fi, tempo ligado, DHT sem resposta e estado do ar. O painel da sala mostra o ESP32 online até 2,5 min sem contato, com esses dados para a manutenção.
- O LED manda o código infravermelho do fabricante (IRremoteESP8266): cada quadro leva o estado inteiro (ligado em frio no alvo, ou desligado) e é repetido uma vez 2 s depois. Sem protocolo configurado, nada é enviado: o serial e o diagnóstico do site mostram "sem protocolo IR".
- O botão **Ligar o ar / Desligar o ar** do site chega ao ESP32 como modo manual (ligado na temperatura escolhida) ou desligado, por 2 h.

O CI não compila o firmware. Ele extrai do `sketch.ino` a lógica da porta e a escolha dos comandos IR e as testa em C++ com 13 cenários da porta, 12 passos dos quadros IR e 10 casos do conforto (corpo humano e NR-17) (`hardware/logica/testar_firmware.py`), além de verificar as equações (`hardware/logica/verificar_logica.py`). Mudanças no firmware precisam de teste manual na placa, descrito no PR.

## Comando IR ao ar-condicionado

O firmware usa a biblioteca **IRremoteESP8266** (v2.9.0 ou mais nova, pelo Library Manager do Arduino IDE) para mandar pelo LED o código do fabricante, modulado em 38 kHz. Cada quadro leva o estado inteiro: ligado, em modo frio, no alvo, com ventilação automática, ou desligado. Mudanças seguidas (várias pessoas entrando) viram um quadro só, com pelo menos 1 s entre quadros. Ao ligar, o ESP32 manda o estado atual para sincronizar o aparelho.

Para escolher o protocolo:

1. No `config.h`: `#define MOVEMENT_AC_PROTOCOLO "GREE"`.
2. Ou no monitor serial: `IR GREE`. O nome fica gravado na flash e vale mais que o `config.h`.
3. Sem saber o protocolo, aponte o LED para o aparelho e digite `IR_TESTE`. O ESP32 liga (22 °C, frio) e desliga o aparelho em cada protocolo da lista, um a cada 6,5 s, e mostra o nome antes de cada um. Grave com `IR <nome>` o que fez o aparelho responder. Qualquer tecla interrompe o teste.

| Marca | Protocolo para começar |
| --- | --- |
| LG | `LG2` (controles AKB, linha Dual Inverter) ou `LG` |
| Samsung | `SAMSUNG_AC` |
| Springer Midea, Midea, Carrier | `MIDEA` ou `COOLIX` |
| Gree | `GREE` ou `KELVINATOR` |
| TCL | `TCL112AC` |
| Daikin | `DAIKIN` |
| Fujitsu | `FUJITSU_AC` |
| Hitachi | `HITACHI_AC` |
| Consul (Whirlpool) | `WHIRLPOOL_AC`; se não responder, `IR_TESTE` |
| Electrolux, Elgin, Philco, Agratto | Fabricados por terceiros, variam por modelo: `IR_TESTE` |

- A tabela é um ponto de partida. O protocolo só se confirma no aparelho, porque a mesma marca usa fabricantes diferentes conforme o modelo.
- O LED precisa estar de frente para o receptor do aparelho, a poucos metros.
- A biblioteca ocupa bastante flash. Se o Arduino IDE acusar "Sketch too big", escolha em Ferramentas → Partition Scheme a opção **Huge APP (3MB No OTA/1MB SPIFFS)**.
- O site continua sem mandar comandos ao aparelho: quem decide é o ESP32.

## Simulação no Wokwi

`firmware/climacontrol/diagram.json` é o circuito no Wokwi. Como o Wokwi não tem a barreira iPEC, dois sensores PIR fazem o papel das barreiras A e B (GPIO 13 e 26). Ele usa DHT22 e um LED com resistor no lugar do conjunto BC547 + LED IR. Para o Wokwi falar com a API, ela precisa estar acessível na internet (o site do Azure) ou passar por um túnel.
