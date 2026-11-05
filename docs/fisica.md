# Física do circuito

Justificativa técnica do comportamento físico do circuito do Movement (corrente, tensão, potência e sinal), com os cálculos aplicados. Atende ao requisito "Física para Sistemas Computacionais" da ExpoTech 2026.2 (issue #5).

## 1. Circuito

O circuito está em [`firmware/climacontrol/diagram.json`](../firmware/climacontrol/diagram.json) e é simulado no Wokwi.

| Componente | Id no diagrama | Ligação | Função |
| --- | --- | --- | --- |
| ESP32 DevKit C v4 | `esp` | — | Controlador, Wi-Fi, lógica de 3,3 V |
| DHT22 externo | `dht1` | dados no GPIO 14 | Temperatura e umidade externas |
| DHT22 interno | `dht2` | dados no GPIO 27 | Temperatura e umidade da sala |
| PIR "entrada" | `pir1` | saída no GPIO 13 | Conta quem entra |
| PIR "saída" | `pir2` | saída no GPIO 12 | Conta quem sai |
| LED vermelho | `led1` | anodo no resistor, catodo no GND | Simula o pulso infravermelho enviado ao ar-condicionado |
| Resistor | `r1` | entre o GPIO 2 e o anodo do LED | Limita a corrente do LED (150 Ω) |

Fluxo do sinal: os sensores entregam níveis lógicos (PIR) ou um sinal serial temporizado (DHT22) aos pinos do ESP32. O firmware converte esses sinais em ocupação, temperatura e umidade e envia as leituras por Wi-Fi à API (`POST /api/telemetry`). O LED, acionado pelo GPIO 2, representa o comando enviado ao ar-condicionado.

## 2. Resistor do LED (lei de Ohm e potência)

O resistor fica em série com o LED. A tensão sobre ele é a do pino menos a queda direta do LED:

$$I = \frac{V_{GPIO} - V_F}{R}, \qquad V_{GPIO} = 3{,}3\ \text{V}, \quad V_F \approx 2{,}0\ \text{V (LED vermelho)}$$

| Resistor | Corrente | Conclusão |
| --- | --- | --- |
| 10 Ω (valor anterior) | $I = \dfrac{1{,}3}{10} = 130\ \text{mA}$ | Muito acima do que o pino entrega com segurança (da ordem de 40 mA no nível de acionamento máximo; recomenda-se até ~20 mA) e da corrente nominal do LED (20 mA). Num circuito real, danificaria o pino ou o LED |
| 150 Ω (valor atual) | $I = \dfrac{1{,}3}{150} \approx 8{,}7\ \text{mA}$ | Dentro dos limites do pino e do LED, com brilho visível |

**Escolha do valor.** Com corrente alvo de 10 mA:

$$R = \frac{V_{GPIO} - V_F}{I} = \frac{3{,}3 - 2{,}0}{0{,}010} = 130\ \Omega$$

O valor comercial da série E12 logo acima é **150 Ω**, que dá uma corrente um pouco menor que o alvo (mais segura).

**Potências** com $I \approx 8{,}7\ \text{mA}$:

$$P_R = I^2 R = (0{,}0087)^2 \times 150 \approx 11\ \text{mW} \qquad P_{LED} = V_F \cdot I = 2{,}0 \times 0{,}0087 \approx 17\ \text{mW}$$

$$P_{total} = V_{GPIO} \cdot I = 3{,}3 \times 0{,}0087 \approx 29\ \text{mW} \;(= P_R + P_{LED})$$

O resistor dissipa 11 mW, bem abaixo dos 250 mW de um resistor comum de 1/4 W.

> O GPIO 2 também é um pino de *strapping* do ESP32 (lido no boot) e, em muitas placas DevKit, já tem um LED da própria placa. Um LED com resistor ligado ao GND não atrapalha o boot normal, mas vale lembrar disso ao trocar o pino.

## 3. Níveis lógicos

O ESP32 interpreta a tensão em um pino de entrada pelos limiares do datasheet, com $V_{DD} = 3{,}3\ \text{V}$:

$$V_{IH} \ge 0{,}75 \cdot V_{DD} = 2{,}48\ \text{V} \;(\text{lido como 1}) \qquad V_{IL} \le 0{,}25 \cdot V_{DD} = 0{,}83\ \text{V} \;(\text{lido como 0})$$

- Saída do PIR em nível alto: ≈ 3,3 V ≥ 2,48 V → **1** (presença detectada).
- Saída do PIR em repouso: ≈ 0 V ≤ 0,83 V → **0**.
- Linha de dados do DHT22 em repouso: puxada a 3,3 V pelo pull-up → **1**.

Tensões entre 0,83 V e 2,48 V são indefinidas; por isso os sensores precisam trabalhar com a mesma referência de 3,3 V do ESP32 nas saídas.

## 4. Pull-up do DHT22 (sinal e constante RC)

A linha de dados do DHT22 é de **dreno aberto**: o sensor só consegue puxá-la para 0, e um resistor de pull-up a devolve para 1. O datasheet recomenda cerca de 5 kΩ para cabos de até 20 m; 4,7 kΩ e 10 kΩ são valores comerciais usuais. Com o caso mais lento, 10 kΩ:

- Corrente com a linha em 0:

$$I = \frac{V_{DD}}{R} = \frac{3{,}3}{10\,000} = 0{,}33\ \text{mA}$$

- Constante de tempo da subida, com capacitância típica de fio curto + entrada $C \approx 100\ \text{pF}$:

$$\tau = R \cdot C = 10\,000 \times 100 \times 10^{-12} = 1\ \mu\text{s}$$

A tensão chega a ~95% do valor final em $3\tau \approx 3\ \mu\text{s}$.

- O DHT22 codifica cada bit pela **duração do pulso alto**: ~26–28 µs = bit 0 e ~70 µs = bit 1.

Como $3\tau \approx 3\ \mu\text{s} \ll 26\ \mu\text{s}$, a borda de subida completa-se muito antes do fim do pulso mais curto, e o ESP32 mede a largura de cada bit corretamente. Com cabos longos (C maior), $\tau$ cresce, e é por isso que o datasheet pede um resistor menor nesse caso.

No Wokwi, o módulo DHT22 já inclui o pull-up. Numa montagem real com o sensor de 4 pinos, o resistor precisa ser colocado entre a linha de dados e 3,3 V; módulos de 3 pinos normalmente já o trazem.

## 5. Consumo do circuito

Potência de cada parte, com $P = V \cdot I$ e correntes típicas de datasheet:

| Componente | Tensão | Corrente típica | Potência |
| --- | --- | --- | --- |
| ESP32 com Wi-Fi conectado, ocioso (modem-sleep) | 3,3 V | 20 a 70 mA | 0,07 a 0,23 W |
| ESP32 transmitindo (pico de TX 802.11b) | 3,3 V | ~240 mA | ~0,79 W |
| DHT22 medindo (×2) | 3,3 V | ~1,5 mA cada | ~5 mW cada |
| PIR HC-SR501 (×2) | 5 V | < 65 µA cada | ~0,3 mW cada |
| LED + resistor de 150 Ω (só durante o pulso) | 3,3 V | 8,7 mA | ~29 mW |

O consumo é dominado pelo **rádio Wi-Fi do ESP32**: os sensores somam cerca de 11 mW, enquanto cada transmissão chega a ~0,8 W de pico. Reduzir o número de transmissões é, portanto, a forma mais eficaz de economizar energia. É exatamente o que a Pesquisa Operacional otimiza ([issue #4](https://github.com/expotech2026-2/Projeto-Movement-2.0/issues/4)).

## 6. Energia por envio (entrada da Pesquisa Operacional)

A energia gasta a mais por um envio é a potência adicional do rádio durante o tempo da transmissão:

$$E_{envio} = V \cdot (I_{envio} - I_{ocioso}) \cdot t_{envio}$$

O firmware mede $t_{envio}$: cada envio imprime no monitor serial `[Movement] HTTP <código> em <N> ms`. O tempo inclui a conexão, o handshake TLS (HTTPS), o envio e a resposta da API.

**Estimativa com valores típicos:** $I_{envio} \approx 150\ \text{mA}$ (média entre transmissão e recepção), $I_{ocioso} \approx 30\ \text{mA}$ e $t_{envio} \approx 0{,}8\ \text{s}$ com HTTPS:

$$E_{envio} \approx 3{,}3 \times (0{,}150 - 0{,}030) \times 0{,}8 \approx 0{,}32\ \text{J}$$

Com o intervalo fixo atual de 16 s:

$$N = \frac{86\,400\ \text{s/dia}}{16\ \text{s}} = 5\,400\ \text{envios/dia} \qquad E_{dia} = 5\,400 \times 0{,}32 \approx 1\,728\ \text{J/dia} \approx 0{,}48\ \text{Wh/dia}$$

| Origem | $t_{envio}$ | $E_{envio}$ | Energia/dia com 16 s |
| --- | --- | --- | --- |
| Estimativa típica | 0,8 s | 0,32 J | 1.728 J (0,48 Wh) |
| Medição no Wokwi (média de 10 envios) | ⏳ medir no Wokwi | ⏳ | ⏳ |

Para preencher a linha medida: rode o firmware no Wokwi, anote 10 valores de `em N ms`, calcule a média $\bar t$ em segundos e use $E_{envio} = 3{,}3 \times 0{,}12 \times \bar t$. Esse valor passa a ser o padrão de `MOVEMENT_ENERGY_PER_SEND_J` na otimização.

## 7. Alimentação real do sensor de presença

O módulo HC-SR501 físico precisa de **4,5 a 20 V** na alimentação. Numa placa real ele deve ser ligado ao pino **VIN/5 V** do ESP32 (alimentado pela USB), e não ao 3V3 como no diagrama. A saída do módulo é de **3,3 V**, compatível com os níveis lógicos do ESP32 (seção 3), então o sinal pode ir direto ao GPIO.

No Wokwi, o PIR funciona em 3,3 V por simplificação da simulação. Essa é a única diferença elétrica entre o diagrama e uma montagem real.

## 8. Modelo térmico da sala (complementar)

O firmware simula o aquecimento causado pelas pessoas na sala (`calcularDeltaTemperatura()` em `sketch.ino`): parte do calor emitido pelas pessoas aquece a massa de ar da sala.

$$\Delta T = \frac{P \cdot t \cdot f}{m \cdot c}, \qquad m = \rho \cdot V_{sala}$$

| Símbolo | Valor | Significado |
| --- | --- | --- |
| $P$ | 150 W por pessoa | Calor emitido por uma pessoa em repouso |
| $t$ | 10 s | Intervalo do cálculo (`intervaloCalor`) |
| $f$ | 0,3 | Fração do calor retida no ar (`FATOR_RETENCAO`) |
| $\rho$ | 1,2 kg/m³ | Densidade do ar |
| $V_{sala}$ | 50 m³ | Volume da sala |
| $m$ | $1{,}2 \times 50 = 60\ \text{kg}$ | Massa de ar |
| $c$ | 1005 J/(kg·K) | Calor específico do ar |

- **1 pessoa:**

$$\Delta T = \frac{150 \times 10 \times 0{,}3}{60 \times 1005} = \frac{450}{60\,300} \approx 0{,}0075\ \text{K a cada 10 s} \;(\approx 0{,}045\ \text{K/min})$$

- **30 pessoas:** $\Delta T \approx 0{,}224\ \text{K}$ a cada 10 s (≈ 1,3 K/min).

**Conclusão:** com a sala cheia, a temperatura muda cerca de 30 vezes mais rápido do que com uma pessoa. Uma sala cheia precisa de leituras mais frequentes, e uma sala vazia pode ser lida com menos frequência. Essa taxa de variação é o parâmetro $r_h$ do modelo de Pesquisa Operacional.

## 9. Fontes

- Espressif, *ESP32 Series Datasheet*: características elétricas (níveis lógicos, corrente dos pinos) e consumo por modo de operação. <https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf>
- Aosong, *AM2302 (DHT22) datasheet*: protocolo de um fio, temporização dos bits, pull-up e consumo. <https://cdn-shop.adafruit.com/datasheets/Digital+humidity+and+temperature+sensor+AM2302.pdf>
- Datasheet do módulo HC-SR501: alimentação de 4,5 a 20 V, saída de 3,3 V, corrente em repouso.
- Firmware do projeto: [`firmware/climacontrol/sketch.ino`](../firmware/climacontrol/sketch.ino) (modelo térmico e medição do envio) e [`diagram.json`](../firmware/climacontrol/diagram.json) (circuito).
