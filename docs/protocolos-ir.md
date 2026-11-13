# Protocolo IR pelo cadastro

Auditoria em 12/11/2026, somente leitura, sem exposição de credenciais.

| Ambiente | Aparelhos cadastrados | Marca | Modelo | Protocolo candidato |
| --- | ---: | --- | --- | --- |
| Produção | 3 | Samsung | AR24BVFAAWKNAZ | SAMSUNG_AC, variante 1 |
| Teste | 1 | Samsung | AR24BVFAAWKNAZ | SAMSUNG_AC, variante 1 |

## Evidência e limite

A [Samsung identifica o modelo](https://www.samsung.com/br/support/model/AR24BVFAAWKNAZ/)
como WindFree Connect. A [IRremoteESP8266 v2.9.0](https://github.com/crankyoldgit/IRremoteESP8266/blob/v2.9.0/src/ir_Samsung.h)
implementa SAMSUNG_AC para diversos splits Samsung, mas não lista AR24BVFAAWKNAZ.
A associação desse modelo está salva como `family_candidate`, uma inferência por família,
e precisa de teste físico. Não há comprovação de compatibilidade desse modelo exato.
Dos 1.507 modelos do catálogo do Inmetro, só esse tem correspondência exata. Por isso,
sem o modelo exato, o cadastro usa o protocolo mais comum da marca como `brand_candidate`
(`BRAND_PROTOCOLS` em `backend/app/ir_protocols.py`), também sujeito a teste físico.

As associações ficam em `backend/app/data/ir_protocols.json`, com fonte, modelo e variante.
Modelos documentados da LG, Gree e Midea têm correspondência exata; os outros recebem o
candidato da marca, e marcas sem protocolo conhecido ficam pendentes.
A migração 0009 contém sua própria cópia estável das associações para os registros existentes.
Novos cadastros usam a base atual. O formulário permite informar uma configuração testada.

## Fluxo

1. A API salva protocolo, variante e origem no aparelho da sala.
2. O token autentica um dispositivo habilitado e resolve sua sala no servidor.
3. `/api/devices/me/control` inclui `ir_protocols` (pares separados por vírgula) e `ir_pending`.
4. O firmware 2.5.1 aplica a configuração em cada consulta, antes de comparar a versão do comando.
5. Cada par distinto é enviado uma vez por quadro; a repetição existente ocorre 2 s depois.
   Os aparelhos da sala recebem o mesmo estado, sem endereçamento individual.
6. Aparelhos inativos ou em manutenção não entram na configuração. Remover todos os protocolos
   envia uma lista vazia; o firmware 2.5.2 volta ao protocolo gravado por `IR <nome>`.
   Modelos desconhecidos não impedem os conhecidos.

Não se grava a flash a cada consulta. O ESP32 recupera a configuração pelo token após reiniciar.
O protocolo gravado por serial/config.h vale enquanto o site não tiver protocolo para a sala.
`IR_TESTE` ajuda a confirmar o protocolo; salve o resultado no cadastro do aparelho.

## Implantação e teste físico pendentes

As alterações desta branch ainda não foram publicadas. O banco remoto foi expandido em
12/11/2026 pelo script `backend/scripts/prepare_ir_database.py --schema <ambiente> --apply`:
3 aparelhos na produção e 1 em teste receberam SAMSUNG_AC como family_candidate.
A expansão acrescenta as colunas sem avançar alembic_version: a API antiga continua
pronta (health e ready 200). A migração 0009 é idempotente para reconhecer essa expansão
na publicação da API nova; não substitui nem sobrescreve protocolos informados manualmente.
Publicar API e site com a migração 0009 e gravar o firmware 2.5.1 nas duas cópias equivalentes.
O token continua o mesmo: não é necessário gerar outro.

Na placa: consultar a API, conferir o diagnóstico 2.5.1 e o protocolo SAMSUNG_AC, testar ligar,
temperatura e desligar, e confirmar que o aparelho responde. Testar reinício, troca do protocolo
sem novo comando do professor e remoção/inativação do aparelho. O CI testa trechos C++;
não substitui compilar o sketch inteiro no Arduino IDE nem a confirmação do sinal no aparelho.


## Reenvio manual na visão geral

Quando o diagnóstico do dispositivo começa por "sem protocolo", o administrador vê
"Enviar protocolo para o ESP32". A rota POST /api/rooms/{room_id}/ir-protocol exige admin,
um dispositivo habilitado e pelo menos um aparelho ativo com protocolo. Ela incrementa
`rooms.ir_revision` atomicamente; não altera ac_version, modo, alvo nem prazo do professor.
A API sempre devolve essa revisão ao dispositivo, que reaplica a configuração mesmo que
os protocolos não tenham mudado. A mensagem diz preparado, não entregue nem aplicado:
a confirmação de configuração vem do diagnóstico do dispositivo no contato seguinte.
Offline, aguarda reconexão. Aparelhos pendentes e protocolos candidatos aparecem na mensagem.


## Verificação de 12/11/2026

- 119 testes de backend e 38 de frontend passaram; lint, formatação e build passaram.
- Testes C++ da porta, quadros IR, conforto e controle pelo site passaram.
- Sketch completo compilado para ESP32 Dev Module, core 2.0.17, Huge APP,
  IRremoteESP8266 2.9.0, DHT sensor library 1.4.7 e Adafruit Unified Sensor 1.1.15.
  Com config.h de exemplo: 1.055.005 bytes de flash (33%) e 47.572 bytes de RAM (14%).
- Pacote entregue com código, configuração de exemplo e instruções; não contém token,
  senha de Wi-Fi ou binário configurado para uma sala. Preserve o config.h privado existente.
- Sem gravação na placa e sem confirmação física do protocolo Samsung.
