# Contexto do projeto para IAs

Leia esta pasta antes de começar qualquer tarefa no Movement 2.0. Ela explica o que o projeto é, para que serve, com que equipamentos e serviços funciona e em que ponto está, para que uma IA (Claude Code, Codex, ChatGPT, Gemini…) entenda o que acontece por trás antes de mexer em algo.

A pasta é um panorama. Valores de configuração ficam fora daqui: senhas, tokens, chaves de API e endereços de banco não aparecem nestes arquivos nem devem ser acrescentados. Quando uma tarefa precisar de um segredo, peça-o ao humano responsável.

## Arquivos

| Arquivo | Leia quando a tarefa envolver |
| --- | --- |
| [projeto.md](projeto.md) | Qualquer coisa: propósito, requisitos da ExpoTech, prazos e fluxo de trabalho da equipe |
| [software.md](software.md) | Backend, frontend, banco de dados, perfis de acesso, padrões de projeto ou otimização |
| [hardware.md](hardware.md) | ESP32, sensores, circuito, firmware, Wokwi ou Logisim |
| [infraestrutura.md](infraestrutura.md) | Supabase, Azure, Docker, CI/CD, variáveis de ambiente ou deploy |
| [estado-atual.md](estado-atual.md) | Saber o que está pronto, o que falta e os problemas conhecidos |

## Como usar

- **No repositório** (Claude Code, Codex): o `AGENTS.md` da raiz aponta para esta pasta e traz os comandos e convenções de código. Os detalhes técnicos de cada disciplina estão em `docs/`.
- **Fora do repositório** (ChatGPT, Gemini, outra conversa): envie os arquivos desta pasta junto com o pedido.
- **Fonte da verdade:** o código na branch `Devlop`. Se algo aqui divergir do código, vale o código, e esta pasta deve ser corrigida no mesmo PR.
- **Ao terminar uma tarefa** que mude o que está pronto, pendente ou com problema, atualize `estado-atual.md` e a data no topo dele.
