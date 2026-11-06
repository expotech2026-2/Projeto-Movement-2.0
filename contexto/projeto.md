# Projeto

## O que é

O Movement 2.0 gerencia salas de aula e seus aparelhos de ar-condicionado. Em cada sala, um ESP32:
- conta as pessoas que entram e saem pela porta;
- mede temperatura e umidade;
- decide se o resfriamento deve atuar;
- envia as leituras para uma API na nuvem.

Um site mostra o painel de cada sala, o histórico, os aparelhos cadastrados e os relatórios.

É a evolução do Projeto Integrador anterior da equipe ("ClimaControl", que usava ThingSpeak). A versão 2.0 trocou o ThingSpeak por API e banco próprios e acrescentou unidades, usuários, catálogo do Inmetro, relatórios e otimização do envio.

## Para que serve agora

É o projeto da **ExpoTech 2026.2**, categoria **INTERFACE**, do curso de Engenharia da Computação (4º e 5º semestres). Ele precisa demonstrar, num único sistema, os requisitos de cada disciplina:

| Disciplina | O que o projeto entrega | Onde está |
| --- | --- | --- |
| Eletrônica Digital e Analógica | Máquina de estados da porta, contador de ocupação, comparador e acionamento do resfriamento, com circuitos no Logisim e no Wokwi | `docs/eletronica-digital.md`, `hardware/` |
| Física para Sistemas Computacionais | Lei de Ohm, potência, níveis lógicos, constante RC, consumo, energia por envio e modelo térmico da sala | `docs/fisica.md` |
| Software Architecture & Design Patterns | C4 (níveis 1 a 3), UML de sequência e de classes, dois padrões GoF (Strategy e Observer) e SOLID | `docs/arquitetura.md` |
| Cloud Computing | Deploy real em nuvem pública (Azure), banco gerenciado (Supabase), variáveis de ambiente seguras e CI/CD | [infraestrutura.md](infraestrutura.md) |
| Pesquisa Operacional | Programação linear inteira que escolhe o intervalo de envio do ESP32 por hora, economizando energia | `docs/pesquisa-operacional.md` |

## Prazos

| Data | Evento |
| --- | --- |
| 09 a 13/11/2026 | Avaliação individual. **Depois dela o projeto não pode mais mudar.** |
| 28/11/2026 | ExpoTech (apresentação) |

Com o prazo curto, prefira mudanças pequenas, testadas e que não quebrem o que já funciona.

## Quem usa o sistema

| Perfil | Pode |
| --- | --- |
| Administrador | Tudo: unidades, salas, aparelhos, sensores ESP32, usuários e relatórios |
| Professor | Consultar salas, leituras e histórico e gerar relatórios |
| Dispositivo (ESP32) | Só enviar leituras da própria sala e consultar o próprio intervalo de envio |

## Fluxo de trabalho da equipe

- Cada tarefa é uma **issue** do GitHub com especificação, testes e critérios de aceite. A issue de roteiro é a #11.
- O trabalho é feito numa branch `feat/<número>-<descrição>`, que entra na `Devlop` por PR. A `Devlop` é o ambiente de integração e teste.
- Um humano abre o PR `Devlop → main`. A `main` é a produção: cada push nela publica o site no Azure.
- Ações em portais (Azure, Supabase, GitHub Settings) e testes físicos (Wokwi, Logisim, montagem) são feitos por humanos. Nas issues, essas partes têm a marca 👤.
- Comandos, convenções de código e a definição de pronto estão no `AGENTS.md` da raiz.

## Etapas

| Etapa | Issue | Conteúdo |
| --- | --- | --- |
| 1 | #1 | Base: unidades, salas, aparelhos, usuários, catálogo, telemetria e relatórios |
| 2 | #2 | Banco gerenciado no Supabase |
| 3 | #3 | Deploy no Azure com CI/CD |
| 4 | #5 | Cálculos de física |
| 5 | #4 | Pesquisa operacional (inclui o padrão Strategy) |
| 6 | #6 | Arquitetura: Observer, inversão de dependência e C4 |
| 7 | #7 | Circuitos no Logisim e no Wokwi |
