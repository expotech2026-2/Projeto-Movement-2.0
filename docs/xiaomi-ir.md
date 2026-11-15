# Emissor selecionável: ESP32 ou POCO F7

O site e o firmware 2.6.0 permitem escolher o LED do ESP32 ou o infravermelho do
POCO F7. No celular usamos Tasker + Android IR Blaster, sem desenvolver aplicativo
em Kotlin/Java. O Tasker é pago; a alternativa gratuita é o Automate, que sozinho
recebe o HTTP e transmite o IR (seção "Alternativa gratuita: Automate").
O navegador continua sendo a interface de controle.

A branch `feat/xiaomi-ir-gateway` parte de `perf/otimizar-site-e-firmware`
(`6b6beac`, PR #66). Preserva o histórico incremental, a compressão/cache do site,
o clima sem bloquear a consulta do ESP32, `server_time`, a memória RTC da contagem
e a rotina de zerar às 3 h da versão 2.5.4. A versão 2.6.0 acrescenta a seleção
do emissor sobre essa base; a integração ainda exige validação antes de publicar.

```text
Site → API → ESP32 → LED IR → ar
                  ↘ HTTP local → Tasker → Android IR Blaster → IR do POCO F7 → ar
                  ↘ HTTP local → Automate ──────────────────→ IR do POCO F7 → ar
```

O ESP32 mantém sensores, contagem de pessoas, alvo automático e comandos manuais.
A API guarda a escolha por sala; a comunicação com o celular parte do ESP32.
O servidor na nuvem e o navegador não acessam o IP privado do celular.

## Preparação do celular

1. **Controle pelo Mi Remote confirmado pelo usuário em 13/11/2026.** Isso valida
   o caminho celular → ar, mas não confirma os sinais do Android IR Blaster.
2. Instale Tasker e uma versão de Android IR Blaster com automação por broadcast.
   Abra o IR Blaster e habilite **Settings → Interaction → Allow automation broadcasts**.
3. Obtenha sinais brutos compatíveis com o modelo real: importe um controle
   compatível ou capture o controle original com um receptor IR externo.
   O emissor do celular não aprende sinais sozinho. O sucesso no Mi Remote não
   transfere os códigos automaticamente para outro aplicativo.
4. Use `hardware/xiaomi/signals.example.json` como mapa. Todos os `pattern: []`
   precisam ser preenchidos com durações reais, em microssegundos; ajuste também
   a frequência. Os campos vazios são recusados, nunca enviados como códigos fictícios.
5. Cadastre `off` como **desligar explícito**. Para cada temperatura de 16 a 30 °C,
   cadastre `cool_N_auto` e `cool_N_max`: ligado, frio, temperatura N, ventilação
   automática ou máxima. Use quadros de estado completo, sem botões de alternância.
   Não substitua um estado ausente por outra temperatura ou ventilação.
   Um mapa atende aos aparelhos que respondem ao mesmo conjunto de sinais;
   uma sala com aparelhos diferentes exige validar um mapa que alcance todos.
6. Mantenha o celular no Wi-Fi do ESP32, com IP reservado no roteador, alimentação
   e posição adequada. Autorize o funcionamento em segundo plano e teste as
   restrições de bateria do HyperOS, inclusive depois de reiniciar e bloquear a tela.

## Configurar o Tasker uma vez

### Sinais Samsung candidatos prontos para teste

Para os Samsung AR24BVFAAWKNAZ cadastrados no projeto, há dois arquivos:

- `hardware/xiaomi/samsung-candidate.ir`: importar no Android IR Blaster para
  testar os botões manualmente antes de ativar a automação.
- `hardware/xiaomi/signals.samsung-candidate.json`: o mesmo mapa no formato da
  variável `%MovementSignals` do Tasker, depois de validar os botões no aparelho.

Os 31 estados foram gerados pelo código oficial da IRremoteESP8266 **v2.9.0**,
usando `SAMSUNG_AC`. Incluem desligar explícito e frio de 16 a 30 °C em ventilação
automática ou partida forte (turbo Samsung), seguindo a lógica do ESP32. Cada
estado foi decodificado no computador, com checksum,
ligar/desligar, temperatura e ventilação conferidos. Isso verifica a codificação,
**não a compatibilidade física com AR24BVFAAWKNAZ**: o protocolo continua candidato
por família, conforme `docs/protocolos-ir.md`.

Não são códigos extraídos do Mi Remote. Se o IR Blaster não comandar o ar com
esse arquivo, será necessário outro conjunto compatível ou uma captura real.
Comece pelos botões `cool_23_auto` e `off`; depois valide o restante do mapa.
O Android determina a modulação física; o campo duty_cycle do arquivo importado
documenta o valor usado na geração e não é um ajuste da API ConsumerIrManager.

Para reproduzir os arquivos, clone a versão oficial 2.9.0 e execute
`python hardware/xiaomi/generate_samsung.py CAMINHO_DA_BIBLIOTECA`. É necessário um
compilador C++ (g++, clang++ ou o pacote Python ziglang); nenhum sinal é transmitido
durante a geração. O exportador e a fonte ficam em `hardware/xiaomi/`.

### Perfil HTTP

Crie as variáveis globais privadas:

| Variável | Conteúdo |
| --- | --- |
| `%MovementGatewayKey` | Chave aleatória de 24 a 128 caracteres, usando letras, números, `_` e `-` |
| `%MovementSignals` | JSON completo do mapa de sinais reais |

Use uma chave própria do gateway, diferente do token da API. Não publique a chave
nem exporte o perfil com ela. O exemplo do Arduino contém somente campo vazio.

Crie um perfil **Event → Net → HTTP Request**, porta **8080**, método **POST**,
caminho **/ac**, **Only On WiFi** habilitado e **Quick Response vazio**. Configure
o timeout em pelo menos 10 s. Não mantenha outro perfil na mesma porta/caminho.

Na tarefa associada, use esta sequência:

1. Ação **JavaScriptlet** com o conteúdo de `hardware/xiaomi/tasker-gateway.js`,
   **Auto Exit ligado**. O evento fornece `%http_request_body`; o script cria
   `%movementstatus` e `%movementresponse`. Configure a colisão da tarefa para
   **Abort New Task**, impedindo execuções simultâneas. O ESP32 tentará novamente
   se a requisição concorrente ficar sem resposta.
2. Ação **HTTP Response**: Request ID `%http_request_id`, Status Code
   `%movementstatus`, Type **Text**, Body `%movementresponse`, MIME Type
   **application/json**.

O script valida a chave, o estado e o sinal, e encaminha o padrão ao receptor
explícito do Android IR Blaster. Respostas 403/422/429/503 indicam recusa; 202 com
`{"accepted":true}` significa **pedido encaminhado ao aplicativo**. Um broadcast
comum não fornece a confirmação da transmissão. Verifique o aplicativo e o ar.
Uma resposta 200 fixa do Tasker não satisfaz o contrato.

O último identificador fica no Tasker para evitar retransmitir a mesma tentativa
se a resposta HTTP se perder. Pedidos diferentes têm intervalo mínimo de 2,5 s.
Falhas posteriores ao broadcast exigem verificar a causa e reenviar a escolha do
emissor pelo site para gerar outro pedido. O gateway não confirma o recebimento
físico do ar e não é um sistema de entrega garantida.

## Alternativa gratuita: Automate

O [Automate](https://llamalab.com/automate/) (LlamaLab) é gratuito e tem os blocos
**HTTP accept** (servidor HTTP local) e **Infrared transmit** (emissor do celular).
Um único fluxo substitui Tasker + Android IR Blaster e atende ao mesmo contrato:
o ESP32 não muda. Use Tasker **ou** Automate, nunca os dois na porta 8080.

Este fluxo foi montado pela documentação dos blocos e ainda não rodou no POCO F7.
Os itens marcados com ⚠️ precisam ser conferidos no primeiro teste.

### Preparar

1. Instale o Automate pela Play Store.
2. Copie `hardware/xiaomi/signals.samsung-candidate.json` (ou o mapa real validado)
   para `Documents/Movement/sinais.json` no celular.
3. Gere a chave do gateway com as mesmas regras do Tasker: 24 a 128 caracteres,
   letras, números, `_` e `-`. Não exporte nem compartilhe o fluxo com a chave.

### Blocos do fluxo

Cada linha segue a anterior pela saída OK. Para digitar uma expressão, toque em **fx**.

| # | Bloco | Configuração |
| --- | --- | --- |
| 1 | Flow beginning | Padrão |
| 2 | Variable set | `chave` = `"SUA_CHAVE"` |
| 3 | File read text | File `/storage/emulated/0/Documents/Movement/sinais.json`; Text content `sinaisTexto` |
| 4 | Variable set | `sinais` = `jsonDecode(sinaisTexto)` |
| 5 | HTTP accept (início do laço) | Network interface **Wi-Fi** (o padrão *Loopback* só aceita o próprio celular); Port `8080`; Request URI `/ac`; Request method **POST**; Save request *Don't save*; Request content `corpo` |
| 6 | Variable set | `req` = `jsonDecode(corpo)` |
| 7 | Expression true | `#chave >= 24 && req["key"] = chave`; NÃO → resposta 403 |
| 8 | Expression true | `#req["id"] = 36 && req["mode"] = "cool" && (req["fan"] = "auto" \|\| req["fan"] = "max")`; NÃO → resposta 400 |
| 9 | Variable set | `nome` = `req["power"] ? "cool_" ++ req["temperature"] ++ "_" ++ req["fan"] : "off"` |
| 10 | Expression true | `req["id"] = ultimoId`; SIM → resposta 202 repetida, sem transmitir |
| 11 | Expression true | `sinais[nome] && #sinais[nome]["pattern"] > 0`; NÃO → resposta 422 |
| 12 | Infrared transmit | Carrier frequency `sinais[nome]["frequency"]`; Command pattern `sinais[nome]["pattern"]` |
| 13 | Variable set | `ultimoId` = `req["id"]` |
| 14 | HTTP response | Status `202`; Content type `application/json`; Body `"{\"accepted\":true,\"message\":\"Enviado: " ++ nome ++ "\"}"` |
| 15 | Delay | 2,5 s; saída de volta ao bloco 5 |

Respostas de recusa: um bloco **HTTP response** para cada caso, com Content type
`application/json` e saída de volta ao bloco 5.

| Status | Body |
| --- | --- |
| 403 | `{"accepted":false,"message":"Chave inválida"}` |
| 400 | `{"accepted":false,"message":"Estado do ar inválido"}` |
| 422 | `"{\"accepted\":false,\"message\":\"Cadastre o sinal: " ++ nome ++ "\"}"` |
| 202 (id repetido) | `{"accepted":true,"message":"Pedido já encaminhado"}` |

Diferenças em relação ao Tasker:

- O sinal é transmitido **antes** da resposta, então o 202 significa que o celular
  emitiu o IR, não só que encaminhou o pedido. Ainda não confirma que o ar recebeu.
  A transmissão leva milissegundos, dentro dos 3 s de espera do ESP32 e dos 5 s
  que o Automate dá entre HTTP accept e HTTP response.
- O laço atende um pedido por vez. Durante o Delay não há HTTP accept pronto e o
  Automate recusa o pedido; o ESP32 repete em 10 s com o mesmo ID. Esse é o
  equivalente ao intervalo de 2,5 s e ao "Abort New Task" do Tasker.
- O id repetido com outro estado não gera 409: o ESP32 nunca reutiliza um ID para
  outro estado, então o fluxo apenas responde 202 sem transmitir.
- O mapa de sinais é lido uma vez, ao iniciar o fluxo. Depois de trocar o
  `sinais.json`, pare e inicie o fluxo de novo.

⚠️ Conferir no primeiro teste:

- Como o `jsonDecode` converte `true`/`false` em `power`: desligar precisa
  responder `Enviado: off`. Se responder `cool_...`, troque a condição do bloco 9.
- Um JSON inválido pode parar o fluxo no bloco 6. Se acontecer, acrescente um
  bloco **Failure catch** no início, apontando para o bloco 5.
- O nome exato da opção Wi-Fi em *Network interface* do HTTP accept.

### Funcionamento em segundo plano

- Automate: ative **Run on system startup** e conceda o acesso a arquivos pedido.
- HyperOS: **Início automático** ligado, bateria **Sem restrições**, Automate
  travado nos recentes e Wi-Fi ligado durante a suspensão.
- Teste com a tela bloqueada e depois de reiniciar o celular.

### Teste pelo computador

Na mesma rede, com o celular apontado para o ar:

```powershell
$corpo = @{ id = [guid]::NewGuid().ToString(); key = "SUA_CHAVE"; power = $true; temperature = 23; mode = "cool"; fan = "auto" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://IP_DO_CELULAR:8080/ac -ContentType application/json -Body $corpo
```

A resposta esperada é `accepted: True` e `Enviado: cool_23_auto`, com o ar ligando
em 23 °C. Repita com `power = $false`: `Enviado: off` e o ar desliga. Se o
Automate responde e o ar não reage, revise os sinais, não o fluxo.

No Arduino e no site nada muda: mesma chave em `MOVEMENT_XIAOMI_KEY` e mesmo
endereço `http://IP_DO_CELULAR:8080/ac`.

## Configurar e escolher no Arduino

Mantenha o `config.h` privado. Acrescente:

```cpp
#define MOVEMENT_IR_TRANSPORT "esp32"  // ou "xiaomi"
#define MOVEMENT_XIAOMI_URL "http://192.168.1.150:8080/ac"
#define MOVEMENT_XIAOMI_KEY "SUA_CHAVE_PRIVADA_DO_GATEWAY"
```

As duas pastas do firmware incluem `ir_gateway.h`. No Arduino IDE, abra
`firmware/MovementESP32-oficial/MovementESP32-oficial.ino` com os demais arquivos
da pasta e grave a placa. As bibliotecas continuam DHT e IRremoteESP8266.

No monitor serial (115200 baud):

```text
XIAOMI_URL http://192.168.1.150:8080/ac
EMISSOR XIAOMI
EMISSOR ESP32
```

A escolha e o endereço ficam gravados no ESP32. `IR_TESTE` só está disponível no
modo ESP32. Não há troca automática para o LED quando o celular falha.

## Escolher no site

Na visão geral da sala, o administrador escolhe **Emissor infravermelho → LED do
ESP32 / Celular Xiaomi (POCO F7)**. No modo Xiaomi, informa o IP local e salva.
Professores continuam usando ligar, desligar, temperatura e automático, e podem
consultar a escolha. A chave do gateway fica somente no Arduino e no Tasker.

O ESP32 recebe a escolha na próxima consulta: até 15 s com ocupação/modo manual,
ou 1 min no automático com a sala vazia. É necessário publicar a API, com a
migração `0011_ir_transport`, e gravar o firmware novo: o site não atualiza a placa.

Antes da primeira escolha salva no site (revisão zero), vale o Arduino. Depois,
uma nova gravação no site prevalece. Um comando serial vale até outra gravação no
site ou reinício da placa; ao reiniciar conectado, o ESP32 reaplica a escolha do
site. O diagnóstico mostra o emissor efetivamente aplicado, que pode diferir da
escolha pendente no site durante desconexão ou intervenção pelo serial.

Falhas HTTP mantêm somente o estado mais recente pendente, com tentativas a cada
10 s e o mesmo ID. O ESP32 não encaminha o token da API ao celular nem segue
redirecionamentos. Somente IPv4 RFC1918, porta 1024–65535 e caminho `/ac` são aceitos.
HTTP local não cifra o tráfego: use uma rede de confiança sem expor a porta à internet.

## Verificação manual pendente

Na integração com a base `6b6beac`, passaram 146 testes de backend, 46 de frontend,
6 de contrato do gateway, lint, build, equações digitais e os testes C++ da porta,
conforto, relógio, zeragem e troca de emissor. As duas cópias do firmware são iguais.
O Python no Windows retornou sucesso, mas imprimiu exceções nativas nos testes
existentes de otimização; confirmar a suíte no CI Linux antes de integrar.
O sketch completo e a comunicação real Android/ESP32 ainda não foram validados
nesta máquina. Os testes de rede usam substitutos de HTTP e Wi-Fi.

- Testar os sinais reais no IR Blaster: off, temperaturas 16/23/30 e ventilação auto/max.
- Validar o perfil Tasker no POCO F7; teste lógico no computador não valida o Android.
- Se usar o Automate: validar o fluxo no POCO F7, incluindo os itens marcados com ⚠️.
- Acionar pelo site com Xiaomi selecionado e conferir fisicamente o aparelho.
- Desconectar/reconectar o celular e verificar diagnóstico, intervalo e recuperação.
- Voltar para ESP32 e conferir que só o LED transmite; repetir a troca pelo serial.
- Repetir com o celular bloqueado e depois de reiniciar, conferindo o HyperOS.

Fontes consultadas em 13/11/2026:
[servidor HTTP do Tasker](https://tasker.joaoapps.com/userguide/en/help/eh_http_request.html),
[JavaScript e sendIntent no Tasker](https://tasker.joaoapps.com/userguide/en/javascript.html),
[automação do Android IR Blaster](https://github.com/iodn/android-ir-blaster#android-automation-broadcasts),
[API IR do Android](https://developer.android.com/reference/android/hardware/ConsumerIrManager),
[HTTP accept do Automate](https://llamalab.com/automate/doc/block/http_accept_tcp.html),
[HTTP response do Automate](https://llamalab.com/automate/doc/block/http_response.html),
[Infrared transmit do Automate](https://llamalab.com/automate/doc/block/infrared_transmit.html),
[expressões do Automate](https://llamalab.com/automate/doc/expression.html).
