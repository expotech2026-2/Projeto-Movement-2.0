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
| PIR "saída" | `pir2` | saída no GPIO 26 | Conta quem sai |
| LED vermelho | `led1` | anodo no resistor, catodo no GND | Simula o pulso infravermelho enviado ao ar-condicionado |
| Resistor | `r1` | entre o GPIO 2 e o anodo do LED | Limita a corrente do LED (150 Ω) |

Fluxo do sinal: os sensores entregam níveis lógicos (PIR) ou um sinal serial temporizado (DHT22) aos pinos do ESP32. O firmware converte esses sinais em ocupação, temperatura e umidade e envia as leituras por Wi-Fi à API (`POST /api/telemetry`). O LED, acionado pelo GPIO 2, representa o comando enviado ao ar-condicionado.

A montagem física usa outros componentes (barreiras infravermelhas iPEC, DHT11 e LED infravermelho acionado por transistor). Os cálculos dela estão na [seção 9](#9-montagem-real); as seções 2 a 8 tratam do circuito simulado.

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

A linha de dados do DHT22 é de **dreno aberto**: o sensor só consegue puxá-la para 0, e um resistor de pull-up a devolve para 1. Os manuais da Aosong indicam um pull-up da ordem de 5 kΩ: o do DHT11 (V1.3) recomenda 4,7 kΩ para cabos de até 5 m, no lugar dos 5,1 kΩ das versões antigas. 4,7 kΩ e 10 kΩ são valores comerciais usuais. Com o caso mais lento, 10 kΩ:

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
| ESP32 com Wi-Fi conectado, ocioso (modem-sleep) | 3,3 V | 20 a 68 mA | 0,07 a 0,22 W |
| ESP32 transmitindo (pico de TX 802.11b) | 3,3 V | ~240 mA | ~0,79 W |
| DHT22 medindo (×2) | 3,3 V | 1 a 1,5 mA cada | ~5 mW cada |
| PIR HC-SR501 (×2) | 5 V | < 50 µA cada | ~0,25 mW cada |
| LED + resistor de 150 Ω (só durante o pulso) | 3,3 V | 8,7 mA | ~29 mW |

Origem de cada valor, conferida nos datasheets da [seção 10](#10-fontes):
- **ESP32:** Espressif v5.3. O modem-sleep, tabela 4-2, vai de 20 mA (80 MHz) a 68 mA (240 MHz). A transmissão em 802.11b a 1 Mbps e +19,5 dBm, tabela 5-4, consome 240 mA, e a recepção, de 95 a 100 mA.
- **DHT22:** AM2302, de 1 a 1,5 mA medindo e de 40 a 50 µA em repouso.
- **HC-SR501:** corrente estática menor que 50 µA. A tabela de especificações do módulo escreve "65mA", um erro de unidade.

O consumo é dominado pelo **rádio Wi-Fi do ESP32**: os sensores somam cerca de 10 mW, enquanto cada transmissão chega a ~0,8 W de pico. Reduzir o número de transmissões é, portanto, a forma mais eficaz de economizar energia. É exatamente o que a Pesquisa Operacional otimiza ([issue #4](https://github.com/expotech2026-2/Projeto-Movement-2.0/issues/4)).

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

No Wokwi, o PIR funciona em 3,3 V por simplificação da simulação. Na montagem da equipe, os PIR são substituídos por barreiras infravermelhas (seção 9.2).

## 8. Modelo térmico da sala (complementar)

O firmware estima o aquecimento causado pelas pessoas na sala (`calcularDeltaTemperatura()` em `sketch.ino`): parte do calor emitido pelas pessoas aquece a massa de ar da sala. A estimativa aparece no monitor serial em °C/min; a temperatura interna enviada à API é a medida pelo DHT.

$$\Delta T = \frac{P \cdot t \cdot f}{m \cdot c}, \qquad m = \rho \cdot V_{sala}$$

| Símbolo | Valor | Significado |
| --- | --- | --- |
| $P$ | 150 W por pessoa | Calor emitido por uma pessoa em repouso |
| $t$ | 10 s | Intervalo de tempo do exemplo |
| $f$ | 0,3 | Fração do calor retida no ar (`FATOR_RETENCAO`) |
| $\rho$ | 1,2 kg/m³ | Densidade do ar |
| $V_{sala}$ | 50 m³ | Volume da sala |
| $m$ | $1{,}2 \times 50 = 60\ \text{kg}$ | Massa de ar |
| $c$ | 1005 J/(kg·K) | Calor específico do ar |

- **1 pessoa:**

$$\Delta T = \frac{150 \times 10 \times 0{,}3}{60 \times 1005} = \frac{450}{60\,300} \approx 0{,}0075\ \text{K a cada 10 s} \;(\approx 0{,}045\ \text{K/min})$$

- **30 pessoas:** $\Delta T \approx 0{,}224\ \text{K}$ a cada 10 s (≈ 1,3 K/min).

**Conclusão:** com a sala cheia, a temperatura muda cerca de 30 vezes mais rápido do que com uma pessoa. Uma sala cheia precisa de leituras mais frequentes, e uma sala vazia pode ser lida com menos frequência. Essa taxa de variação é o parâmetro $r_h$ do modelo de Pesquisa Operacional.

## 9. Montagem real

Componentes da montagem física da equipe e o papel de cada um:

| Componente | Qtd. | Função | Seção |
| --- | --- | --- | --- |
| ESP32 DevKit | 1 | Controlador | 9.5 |
| Barreira infravermelha iPEC IR15 Mini | 2 | Detecta a passagem na porta (barreira A, do lado de fora, e B, do lado de dentro) | 9.2 |
| DHT11 | 1 | Temperatura e umidade | 9.4 |
| LED infravermelho 940 nm | 1 | Emite o comando ao ar-condicionado | 9.1 |
| Transistor NPN BC547 | 1 | Chave do LED infravermelho | 9.1 |
| Resistor 1 kΩ | 1 | Base do BC547 | 9.1 |
| Resistor 10 kΩ | 1 | Pull-up da linha de dados do DHT11 | 9.4 |
| Resistor do LED infravermelho | 1 | Limita a corrente do LED: **68 Ω** | 9.1 |
| Fonte de 12 V | 1 | Alimenta as barreiras: **0,5 A ou mais** | 9.3 |
| Fonte de 5 V para o LED | 0 | Dispensável: o LED usa o pino VIN (5 V da USB) | 9.1 |
| Conversor de nível ou optoacoplador | 0 | Dispensável: a saída da barreira é um contato seco de relé | 9.2 |

### 9.1 LED infravermelho com transistor BC547

O LED infravermelho precisa de dezenas de miliamperes para ter alcance, mais do que o pino do ESP32 entrega com segurança (até ~20 mA). Por isso o pino só aciona a base de um transistor, que funciona como chave:

```text
5 V (VIN) ── R_LED 68 Ω ── LED IR (anodo → catodo) ── coletor BC547
GPIO 2 ── R_B 1 kΩ ── base BC547          emissor BC547 ── GND
```

**Resistor do LED.** Com $V_F \approx 1{,}3\ \text{V}$ (LED de 940 nm; confira no datasheet, costuma ficar entre 1,2 e 1,5 V), $V_{CE(sat)} \approx 0{,}2\ \text{V}$ e corrente alvo de 50 mA (metade do máximo de coletor do BC547, de 100 mA):

$$R_{LED} = \frac{V_{CC} - V_F - V_{CE(sat)}}{I_{LED}} = \frac{5 - 1{,}3 - 0{,}2}{0{,}050} = 70\ \Omega \;\Rightarrow\; 68\ \Omega \text{ (E12)}$$

$$I_{LED} = \frac{3{,}5}{68} \approx 51\ \text{mA} \qquad P_R = I^2 R = (0{,}051)^2 \times 68 \approx 0{,}18\ \text{W}$$

Um resistor de 1/4 W (250 mW) atende; como o LED só fica aceso durante os pulsos, a potência média é bem menor. Com $V_F = 1{,}5\ \text{V}$, a corrente cai para ~49 mA, ainda dentro do esperado.

**Resistor de base e saturação.**

$$I_B = \frac{V_{GPIO} - V_{BE}}{R_B} = \frac{3{,}3 - 0{,}7}{1\,000} = 2{,}6\ \text{mA}$$

O ganho mínimo do BC547 é $h_{FE} = 110$ (grupo A, de 110 a 220; o B vai de 200 a 450 e o C, de 420 a 800, com $I_C = 2$ mA). A base precisa de pelo menos $I_C / h_{FE} = 51 / 110 \approx 0{,}46\ \text{mA}$; com 2,6 mA o ganho forçado é $\beta_F = 51 / 2{,}6 \approx 20$, e o transistor satura com folga (regra prática: $\beta_F$ entre 10 e 20). O pino fornece só 2,6 mA.

**Dissipação no transistor:** $P = V_{CE(sat)} \cdot I_C = 0{,}2 \times 0{,}051 \approx 10\ \text{mW}$. É muito abaixo do limite do BC547: 625 mW a 25 °C na onsemi, ou 500 mW em outros fabricantes. A onsemi também dá a referência para o $V_{CE(sat)}$: no máximo 0,25 V com 10 mA e 0,6 V com 100 mA, então os 0,2 V adotados para 51 mA são uma estimativa razoável.

> Para comandar um ar-condicionado de verdade, o LED precisa enviar o protocolo do fabricante modulado numa portadora de 38 kHz. O firmware atual só pisca o LED (simulação herdada). O circuito acima já suporta a modulação; falta só o software.

### 9.2 Barreiras iPEC IR15 Mini (saída a relé)

Segundo os anúncios do produto, cada par emissor/receptor é alimentado com 12 a 24 V, consome cerca de 60 mA e tem saída por **relé com contatos C/NA/NF** para até 1 A. Confira esses valores no manual que acompanha o sensor.

Como a saída é um **contato seco** (só fecha ou abre um circuito), ele é isolado eletricamente dos 12 V. A ligação ao ESP32 dispensa conversor de nível e optoacoplador:

```text
Contato C  da barreira ── GND do ESP32
Contato NF da barreira ── GPIO (13 para a barreira A, 26 para a B), com pull-up
```

- **Níveis lógicos:** feixe livre → contato NF fechado → GPIO em 0 V → **0**. Feixe interrompido → contato aberto → o pull-up leva o GPIO a 3,3 V → **1**. Se no seu modelo o NF abrir com o feixe livre, use o contato NA.
- **Corrente no contato:** com o pull-up interno do ESP32 (~45 kΩ), $I = 3{,}3 / 45\,000 \approx 73\ \mu\text{A}$; com um resistor externo de 10 kΩ, 0,33 mA.
- **Segurança contra falhas:** usando o NF, um fio cortado também lê **1** ("feixe bloqueado"), então a falha aparece em vez de passar despercebida.
- **Ruído (bounce):** o contato de um relé oscila por alguns milissegundos (tipicamente 1 a 5 ms) ao mudar de estado. O firmware só aceita uma mudança que se mantenha estável por 30 ms, senão uma passagem poderia ser contada mais de uma vez.
- **Proteção do ESP32:** as entradas do ESP32 suportam no máximo $V_{DD} + 0{,}3 \approx 3{,}6\ \text{V}$. Nunca ligue uma saída de 12 V direto num GPIO; com o contato seco isso não acontece.

**Duas barreiras na mesma porta.** Cada pessoa interrompe os dois feixes, então a direção vem da **ordem** dos cortes: A antes de B é uma entrada; B antes de A é uma saída. Essa lógica é uma máquina de estados, documentada em [Eletrônica digital](eletronica-digital.md).

### 9.3 Fonte de 12 V

$$I = 2 \times 60\ \text{mA} = 120\ \text{mA} \qquad P = 12 \times 0{,}120 = 1{,}44\ \text{W}$$

Uma fonte de **12 V com 0,5 A ou mais** dá mais de 4 vezes de folga para a partida dos sensores. Como o contato do relé é isolado, o GND da fonte de 12 V não precisa ser ligado ao GND do ESP32.

### 9.4 DHT11

O DHT11 usa o mesmo protocolo de um fio do DHT22. No manual da Aosong, o pulso alto dura de 23 a 27 µs no bit 0 e de 68 a 74 µs no bit 1. Por isso a análise de pull-up e constante RC da [seção 4](#4-pull-up-do-dht22-sinal-e-constante-rc) vale igual, com o resistor de **10 kΩ** da lista. A Aosong recomenda 4,7 kΩ, mas com o cabo curto da protoboard os 10 kΩ ainda dão $3\tau \approx 3\ \mu\text{s}$, bem abaixo dos 23 µs do bit mais curto.

| Característica | DHT11 (Aosong V1.3) | DHT22 (simulação) |
| --- | --- | --- |
| Alimentação | 3,3 a 5,5 V | 3,3 a 6 V |
| Corrente | até 1,0 mA medindo; 0,06 mA em repouso | 1 a 1,5 mA medindo; 40 a 50 µA em repouso |
| Temperatura | −20 a 60 °C, ±2 °C | −40 a 80 °C, ±0,5 °C |
| Umidade | 5 a 95%, ±5% | 0 a 100%, ±2 a 5% |
| Intervalo mínimo entre leituras | mais de 2 s | 2 s |

O DHT11 de versões anteriores à V1.3 (2017) mede de 0 a 50 °C e de 20 a 90%. Algumas traduções do datasheet antigo indicam até 2,5 mA e leitura a cada 1 s.

O firmware lê os sensores a cada 2 s: é o mínimo do DHT22 e fica no limite do DHT11. Se o DHT11 falhar leituras, aumente `intervaloDHT` no `sketch.ino` para 2500 ms. O tipo do sensor é configurável no `config.h` (`MOVEMENT_DHT_TYPE DHT11`); sem ele, o firmware usa DHT22, que é o modelo disponível no Wokwi.

A lista tem **um** DHT11, mas o firmware lê dois (interno e externo). Sem o sensor externo, o firmware mantém os últimos valores externos (25 °C e 0% no início). Para medir a temperatura externa de verdade, inclua um segundo DHT11 no GPIO 14.

### 9.5 Pinos do ESP32 que afetam a partida

O ESP32 lê alguns pinos (*strapping pins*) no momento em que liga:

- **GPIO 12:** se estiver em nível alto na partida, o ESP32 configura a memória flash para 1,8 V e, nas placas com flash de 3,3 V, **não inicia**. Uma barreira com pull-up nesse pino pode deixar o nível alto (feixe bloqueado ou fio solto). Por isso a barreira B passou do GPIO 12 para o **GPIO 26**, no firmware e no diagrama.
- **GPIO 2:** precisa estar em 0 ou flutuando para o modo de gravação. Ligado à base do BC547 pelo resistor de 1 kΩ, a junção base-emissor mantém o pino em nível baixo, sem atrapalhar.
- **GPIO 13, 14, 26 e 27:** não são de partida e podem ser usados livremente.

### 9.6 Consumo da montagem real

| Parte | Tensão | Corrente | Potência |
| --- | --- | --- | --- |
| ESP32 com Wi-Fi (seção 5) | 3,3 V | 20 a 68 mA ocioso; ~240 mA em pico de TX | 0,07 a 0,22 W ocioso |
| Duas barreiras iPEC | 12 V | 120 mA | 1,44 W, contínuo |
| LED IR + BC547 (só nos pulsos) | 5 V | 51 mA | 0,26 W |
| DHT11 | 3,3 V | até 1,0 mA | ~3 mW |

Na montagem real, o maior consumo contínuo é o das barreiras (1,44 W), e não o do ESP32. A otimização da Pesquisa Operacional reduz a parte que o software controla: as transmissões Wi-Fi do ESP32.

## 10. Fontes

Valores conferidos em 06/11/2026 nos documentos abaixo:

- **ESP32:** Espressif, *ESP32 Series Datasheet* v5.3. <https://documentation.espressif.com/esp32_datasheet_en.pdf>
  - Tabela 5-3: $V_{IH} \ge 0{,}75\,V_{DD}$ e $V_{IL} \le 0{,}25\,V_{DD}$.
  - Tabela 4-2: modem-sleep de 20 a 68 mA.
  - Tabela 5-4: transmissão em 802.11b a 240 mA e recepção de 95 a 100 mA.
  - Tabela 3-1: o MTDI (GPIO 12) tem pull-down como padrão.
- **DHT22:** Aosong, *AM2302 (DHT22) datasheet*. <https://cdn-shop.adafruit.com/datasheets/Digital+humidity+and+temperature+sensor+AM2302.pdf>
  - Alimentação de 3,3 a 6 V.
  - De 1 a 1,5 mA medindo e de 40 a 50 µA em repouso.
  - Coleta a cada 2 s.
- **DHT11:** Aosong, *DHT11 Product Manual* V1.3, de 31/03/2017. <https://akizukidenshi.com/goodsaffix/DHT11_20180119.pdf>
  - Alimentação de 3,3 a 5,5 V.
  - Até 1,0 mA medindo e 0,06 mA em repouso.
  - Leitura a cada mais de 2 s.
  - Pull-up de 4,7 kΩ.
  - Pulso alto do bit 0 de 23 a 27 µs, e do bit 1 de 68 a 74 µs.
- **BC547:** onsemi, *BC546, BC547, BC548*. <https://www.onsemi.com/pdf/datasheet/bc546-d.pdf>
  - $I_C$ máximo de 100 mA.
  - $P_D$ de 625 mW a 25 °C.
  - $h_{FE}$ com 2 mA: grupo A de 110 a 220, B de 200 a 450 e C de 420 a 800.
  - $V_{CE(sat)}$ no máximo 0,25 V com 10 mA e 0,6 V com 100 mA.
- **iPEC IR15 Mini:** manual do sensor e anúncios do produto, com alimentação, consumo e contatos do relé. <https://www.cftvclube.com.br/alarmes/mini-sensor-de-barreira-ipec-ir-15-feixe-simples-infravermelho-15-metros>
- **HC-SR501:** datasheet do módulo, distribuído por MPJA e Electrodragon. <https://courses.ece.cornell.edu/ece5990/ECE5725_Spring2020_Projects/May_15_Demo/Smart%20Lock/W_pp445_yl656/datasheet/31227sc.pdf>
  - Alimentação de 4,5 a 20 V, saída de 3,3 V e corrente estática menor que 50 µA.
  - A tabela de especificações escreve "65mA", um erro de unidade.
- Firmware do projeto: [`firmware/climacontrol/sketch.ino`](../firmware/climacontrol/sketch.ino) (modelo térmico e medição do envio) e [`diagram.json`](../firmware/climacontrol/diagram.json) (circuito).
