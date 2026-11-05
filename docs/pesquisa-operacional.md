# Pesquisa Operacional: plano de leitura do sensor

Problema de otimização real do Movement, modelado e resolvido matematicamente. Atende ao requisito "Operations Research" da ExpoTech 2026.2 ([issue #4](https://github.com/expotech2026-2/Projeto-Movement-2.0/issues/4)).

## 1. Problema e motivação

O ESP32 de cada sala enviava uma leitura a cada **16 s, o dia inteiro**, com a sala cheia ou vazia:

$$\frac{86\,400\ \text{s/dia}}{16\ \text{s}} = 5\,400\ \text{envios/dia}$$

O rádio Wi-Fi é o que mais consome energia no circuito (ver [Física, seção 5](fisica.md#5-consumo-do-circuito)). Cada envio gasta cerca de 0,32 J, ou seja, 1.728 J/dia só em transmissões.

Ler com frequência só importa quando há gente na sala: é quando a temperatura muda mais rápido (ver [modelo térmico](fisica.md#8-modelo-térmico-da-sala-complementar)) e quando o painel precisa estar atualizado. Com a sala vazia, uma leitura a cada 5 minutos basta.

**Pergunta:** que intervalo de envio usar em cada hora do dia para perder o mínimo de informação de temperatura com a sala ocupada, sem passar de um orçamento diário de energia e sem deixar a leitura "velha" quando há gente na sala?

## 2. Dados

Os parâmetros vêm do histórico de leituras da própria sala (`sensor_readings`, últimos 30 dias), agrupado por hora do dia no fuso de São Paulo:

- $p_h$: fração das leituras da hora $h$ com `occupancy > 0`, a probabilidade de a sala estar ocupada;
- $r_h$: percentil 95 de $\lvert \Delta T / \Delta t \rvert$ entre leituras consecutivas, em °C/s. É uma taxa de variação "pessimista": 95% das variações observadas são menores que ela.

```sql
WITH ordered AS (
  SELECT measured_at, occupancy, temp_inside,
         lag(temp_inside) OVER w AS prev_temp,
         lag(measured_at) OVER w AS prev_at
  FROM sensor_readings
  WHERE room_id = :room_id
  WINDOW w AS (ORDER BY measured_at)
)
SELECT extract(hour FROM measured_at AT TIME ZONE 'America/Sao_Paulo')::int AS hour,
       avg((occupancy > 0)::int) AS occupancy,
       percentile_cont(0.95) WITHIN GROUP (
         ORDER BY abs(temp_inside - prev_temp) / extract(epoch FROM measured_at - prev_at)
       ) AS temp_rate
FROM ordered
WHERE prev_at IS NOT NULL AND measured_at > prev_at
GROUP BY 1 ORDER BY 1;
```

**Perfil padrão.** Horas sem histórico usam um perfil de horário de aula:

| Horas | $p_h$ | $r_h$ |
| --- | --- | --- |
| 7h–11h, 13h–16h, 19h–21h (aulas) | 0,8 | 0,002 °C/s |
| Demais | 0 | 0,0005 °C/s |

A API informa, hora a hora, se o valor veio do histórico (`history`) ou do perfil padrão (`default`).

## 3. Modelo

**Conjuntos:**

- $H = \{0, \dots, 23\}$: horas do dia;
- $K$: opções de intervalo, com $\Delta_k \in \{15, 30, 60, 90, 120, 300\}$ s.

**Parâmetros:**

- $p_h$ e $r_h$ (seção 2);
- $e$: energia de um envio, em J (padrão 0,32 J; ver [Física, seção 6](fisica.md#6-energia-por-envio-entrada-da-pesquisa-operacional));
- $E_{max}$: orçamento diário, como fração da energia do intervalo fixo de 16 s;
- $\mu = 10^{-4}$: peso de desempate da energia.

**Variáveis de decisão** (24 × 6 = 144 binárias):

$$x_{h,k} \in \{0, 1\} = 1 \text{ se a hora } h \text{ usa o intervalo } \Delta_k$$

**Função objetivo.** Entre duas leituras, a temperatura pode variar até $r_h \Delta_k$. Esse erro só importa se houver gente na sala, então é ponderado por $p_h$. O termo com $\mu$ apenas desempata a favor do intervalo mais econômico:

$$\min \sum_{h \in H} \sum_{k \in K} \left( p_h \, r_h \, \Delta_k \;+\; \mu \, \frac{3600}{\Delta_k} \, e \right) x_{h,k}$$

**Restrições:**

1. Exatamente um intervalo por hora:
$$\sum_{k \in K} x_{h,k} = 1 \qquad \forall h \in H$$
2. Orçamento diário de energia ($3600/\Delta_k$ é o número de envios na hora):
$$\sum_{h \in H} \sum_{k \in K} \frac{3600}{\Delta_k} \, e \, x_{h,k} \le E_{max}$$
3. Leitura fresca com a sala provavelmente ocupada. O painel considera obsoleta uma leitura com mais de 90 s (`MOVEMENT_STALE_AFTER_SECONDS`):
$$x_{h,k} = 0 \qquad \forall h: p_h \ge 0{,}5,\ \forall k: \Delta_k > 90$$
4. Domínio: $x_{h,k} \in \{0, 1\}$.

## 4. Método

É um problema de **programação linear inteira binária** do tipo **mochila de múltipla escolha**: cada hora escolhe exatamente um item (intervalo), cada item tem um peso (energia) e um custo (erro), e a mochila tem capacidade $E_{max}$. Sem a restrição 2, cada hora poderia ser resolvida sozinha; é o orçamento que acopla as horas e exige otimização conjunta.

A solução usa `scipy.optimize.milp`, que chama o solver **HiGHS**. Ele aplica **branch-and-bound**:

1. resolve a relaxação linear (variáveis entre 0 e 1);
2. ramifica nas variáveis que saíram fracionárias, criando subproblemas com $x = 0$ e $x = 1$;
3. descarta (poda) os ramos cujo limite é pior que a melhor solução inteira já encontrada.

Com 144 variáveis, a solução sai em milissegundos.

## 5. Resultado com o perfil padrão e orçamento de 50%

Com $e = 0{,}32$ J e $E_{max} = 0{,}5 \times 1\,728 = 864$ J:

| Hora | 0–6h | 7h | 8h | 9h | 10h | 11h | 12h | 13h | 14h | 15h | 16h | 17–18h | 19h | 20h | 21h | 22–23h |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Intervalo (s) | 300 | 15 | 15 | 30 | 30 | 15 | 300 | 15 | 30 | 15 | 15 | 300 | 15 | 15 | 15 | 300 |

- **Energia:** 852,5 J/dia (2.664 envios), contra 1.728 J/dia do intervalo fixo, ou seja, **50,7% de economia**.
- **Erro esperado:** 0,360 °C, contra 0,307 °C do intervalo fixo.
- As 12 horas vazias usam 300 s; das 12 horas de aula, 9 usam 15 s e 3 usam 30 s, que é onde o orçamento "aperta".

## 6. Análise de sensibilidade

Saída de `python backend/scripts/sensibilidade.py` (perfil padrão, $e = 0{,}32$ J):

| Orçamento (% da energia atual) | Energia (J/dia) | Economia (%) | Erro esperado (°C) |
| --- | --- | --- | --- |
| 20 | 334,1 | 80,7 | 1,008 |
| 30 | 506,9 | 70,7 | 0,576 |
| 40 | 660,5 | 61,8 | 0,480 |
| 50 | 852,5 | 50,7 | 0,360 |
| 60 | 967,7 | 44,0 | 0,288 |
| 70 a 100 | 967,7 | 44,0 | 0,288 |
| Intervalo fixo de 16 s (atual) | 1.728,0 | — | 0,307 |

Leitura da curva (fronteira de Pareto entre energia e erro):

- **Abaixo de ~11,6%** (≈ 199,7 J) o problema é inviável: não há energia nem para manter as horas de aula a 90 s e as vazias a 300 s.
- **Entre 20% e 50%**, cada 10% a mais de orçamento reduz bastante o erro (de 1,008 para 0,360 °C).
- **O joelho fica em ~56%** (967,7 J/dia). A partir daí todas as horas de aula já estão em 15 s e as vazias em 300 s; aumentar o orçamento não melhora mais nada, e o otimizador nem usa o orçamento extra.
- **Com 56% da energia, o plano otimizado tem erro menor que o firmware atual** (0,288 contra 0,307 °C), porque lê a cada 15 s nas aulas, mais rápido que os 16 s fixos, e só economiza onde a sala está vazia. Ele melhora energia e qualidade ao mesmo tempo.

O padrão do sistema é 50% (`MOVEMENT_SAMPLING_BUDGET_RATIO=0.5`), que economiza metade da energia com erro de 0,36 °C. Para priorizar a qualidade, 0,6 já atinge o ótimo.

## 7. Implementação

| Parte | Onde |
| --- | --- |
| Modelo, perfil e solver | `backend/app/optimization.py` (`plan_sampling`, `hourly_profile`, `default_profile`) |
| Padrão Strategy (GoF) | `IntervalPolicy` (interface), `FixedIntervalPolicy` (16 s, comportamento antigo) e `OptimizedIntervalPolicy` (PLI), trocadas em `build_plan` sem mudar quem as usa |
| API | `backend/app/sampling.py`: `GET /rooms/{id}/sampling-plan?budget_ratio=` (painel) e `GET /devices/me/sampling-interval` (ESP32, autenticado pelo token do dispositivo) |
| Painel | `frontend/src/components/SamplingPlan.jsx`: seletor de orçamento, energia otimizada × fixa, economia, erro e gráfico do intervalo por hora |
| Firmware | `atualizarIntervalo()` em `firmware/climacontrol/sketch.ino`: consulta o intervalo da hora atual na partida e a cada 15 minutos e o aplica entre 15 e 300 s |
| Testes | `backend/tests/test_optimization.py` (7 testes do modelo, sem banco) e `backend/tests/test_sampling.py` (7 testes de API) |
| Sensibilidade | `backend/scripts/sensibilidade.py` |

O firmware consulta o plano a cada 15 minutos, e não a cada hora: o intervalo muda na virada da hora, e uma consulta horária poderia manter o intervalo da madrugada (300 s) por até uma hora depois do início das aulas. São 96 consultas por dia (≈ 31 J, 3,6% do orçamento de 864 J), e o atraso máximo cai para 15 minutos. Se a API não responder, o ESP32 mantém o último intervalo recebido. A rota do dispositivo usa a política fixa de 16 s se o orçamento configurado for inviável.

## 8. Limitações

- A energia por envio é estimada; o valor medido no Wokwi ou na placa deve substituir os 0,32 J (`MOVEMENT_ENERGY_PER_SEND_J`).
- Com pouco histórico, o plano usa o perfil padrão de horário de aula, que pode não refletir a sala real. Ele melhora sozinho à medida que as leituras chegam.
- $r_h$ é um percentil das variações observadas, não um limite garantido; picos raros (porta aberta, A/C ligando) podem passar dele.
- O modelo decide por hora; mudanças de ocupação dentro da hora não são antecipadas.
