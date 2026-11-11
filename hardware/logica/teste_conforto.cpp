// Testa no computador o controle do ar extraído de firmware/climacontrol/sketch.ino:
// máquinas ligadas, alvo da sala, carga térmica, fases (partida forte) e ajuste do aparelho.
// Compile pelo testar_firmware.py, que gera conforto_globais.inc e conforto_funcoes.inc.
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <vector>

using std::max;
using std::min;
#define constrain(amt, low, high) ((amt) < (low) ? (low) : ((amt) > (high) ? (high) : (amt)))

#include "conforto_globais.inc"
#include "conforto_funcoes.inc"

const unsigned long MINUTO = 60UL * 1000UL;

int main() {
  struct Caso {
    const char* nome;
    float obtido;
    float esperado;
  };
  // Sala de 60 m² da tabela de carga térmica: UA 137,6 W/K; iluminação e sol 2 081,4 W.
  uaSala = 137.6f;
  calorFixoSala = 2081.4f;
  const std::vector<Caso> casos = {
      {"calor de uma pessoa com o ar a 24 C (W)", calorPorPessoa(24.0f), 70.0f},
      {"calor com o ar acima do corpo (W)", calorPorPessoa(40.0f), 0.0f},
      // Máquinas: sala comum (10 computadores, 40 lugares), uma a cada 2 alunos.
      {"1 aluno: nenhuma maquina", (float)maquinasLigadas(1, 10, 40), 0.0f},
      {"2 alunos: uma maquina", (float)maquinasLigadas(2, 10, 40), 1.0f},
      {"9 alunos: 4 maquinas", (float)maquinasLigadas(9, 10, 40), 4.0f},
      {"30 alunos: so ha 10 maquinas", (float)maquinasLigadas(30, 10, 40), 10.0f},
      // Laboratório (30 computadores, 35 lugares): uma por aluno.
      {"laboratorio, 2 alunos: 2 maquinas", (float)maquinasLigadas(2, 30, 35), 2.0f},
      {"laboratorio, 35 alunos: todas as 30", (float)maquinasLigadas(35, 30, 35), 30.0f},
      {"28 de 35 (80%) ja e laboratorio", (float)maquinasLigadas(20, 28, 35), 20.0f},
      {"27 de 35 e sala comum", (float)maquinasLigadas(20, 27, 35), 10.0f},
      {"sala sem computadores", (float)maquinasLigadas(20, 0, 35), 0.0f},
      // Alvo da sala: 22 °C, ajustado pelo dia, umidade e lotação, entre 20 e 23 °C.
      {"dia ameno, umidade normal", alvoSala(25.0f, 50.0f, 10, 5, 40), 22.0f},
      {"sem leitura de umidade", alvoSala(25.0f, 0.0f, 10, 5, 40), 22.0f},
      {"dia quente: +0,5", alvoSala(32.0f, 50.0f, 10, 5, 40), 22.5f},
      {"umidade de 60% ainda nao muda", alvoSala(32.0f, 60.0f, 10, 5, 40), 22.5f},
      {"umidade de 65%: -0,5", alvoSala(32.0f, 65.0f, 10, 5, 40), 22.0f},
      {"dia abafado, 72%: -1", alvoSala(27.0f, 72.0f, 10, 5, 40), 21.0f},
      {"dia frio e seco para no maximo", alvoSala(20.0f, 35.0f, 10, 5, 40), 23.0f},
      {"sala lotada (75%): -0,5", alvoSala(25.0f, 50.0f, 30, 15, 40), 21.5f},
      {"laboratorio: -0,5", alvoSala(25.0f, 50.0f, 20, 20, 35), 21.5f},
      {"laboratorio lotado e umido para no minimo", alvoSala(27.0f, 75.0f, 35, 30, 35), 20.0f},
      // Carga: pessoas + máquinas + iluminação e sol + UA x (externa - alvo).
      {"40 alunos e 20 maquinas, 32 C fora (W)", cargaTermica(40, 20, 22.0f, 32.0f), 8705.4f},
      {"10 alunos e 5 maquinas, 32 C fora (W)", cargaTermica(10, 5, 22.5f, 32.0f), 4672.6f},
      {"dia frio: as paredes tiram calor (W)", cargaTermica(0, 0, 22.0f, 18.0f), 1531.0f},
      // Fases: partida forte com a sala 1 °C acima do alvo; para 0,5 °C antes.
      {"manutencao, sala 0,9 acima", (float)proximaFase(FASE_MANUTENCAO, 23.4f, 22.5f, 0), FASE_MANUTENCAO},
      {"manutencao, sala 1,5 acima: partida", (float)proximaFase(FASE_MANUTENCAO, 24.0f, 22.5f, 0), FASE_PARTIDA},
      {"partida chega a 0,5 do alvo", (float)proximaFase(FASE_PARTIDA, 23.0f, 22.5f, 5 * MINUTO), FASE_MANUTENCAO},
      {"partida ha 10 min", (float)proximaFase(FASE_PARTIDA, 25.0f, 22.5f, 10 * MINUTO), FASE_PARTIDA},
      {"partida ha 30 min: sem potencia", (float)proximaFase(FASE_PARTIDA, 25.0f, 22.5f, 30 * MINUTO), FASE_SEM_POTENCIA},
      {"sem potencia continua", (float)proximaFase(FASE_SEM_POTENCIA, 24.0f, 22.5f, 60 * MINUTO), FASE_SEM_POTENCIA},
      {"sem potencia, sala esfriou", (float)proximaFase(FASE_SEM_POTENCIA, 22.9f, 22.5f, 60 * MINUTO), FASE_MANUTENCAO},
      // Ajuste do aparelho (alvo 22,5 °C: base 22 °C).
      {"partida forte: base - 4", (float)ajusteAr(FASE_PARTIDA, 22.5f, 0.5f, 0), 18.0f},
      {"partida nunca abaixo de 18", (float)ajusteAr(FASE_PARTIDA, 20.0f, 0.5f, 0), 18.0f},
      {"sem potencia: base - 2", (float)ajusteAr(FASE_SEM_POTENCIA, 22.5f, 1.3f, 0), 20.0f},
      {"uso de 50%: o alvo", (float)ajusteAr(FASE_MANUTENCAO, 22.5f, 0.5f, 0), 22.0f},
      {"uso de 90%: -1", (float)ajusteAr(FASE_MANUTENCAO, 22.5f, 0.9f, 0), 21.0f},
      {"uso de 120%: -2", (float)ajusteAr(FASE_MANUTENCAO, 22.5f, 1.2f, 0), 20.0f},
      {"potencia desconhecida: o alvo", (float)ajusteAr(FASE_MANUTENCAO, 22.5f, 0.0f, 0), 22.0f},
      {"correcao do DHT -2", (float)ajusteAr(FASE_MANUTENCAO, 22.5f, 0.5f, -2), 20.0f},
      {"correcao do DHT +1", (float)ajusteAr(FASE_MANUTENCAO, 22.5f, 0.5f, 1), 23.0f},
      {"uso alto e correcao nao passam de -2", (float)ajusteAr(FASE_MANUTENCAO, 22.5f, 0.9f, -2), 20.0f},
      // Correção pelo DHT a cada 5 min (alvo 22 °C).
      {"sala 0,6 acima: baixa 1", (float)corrigirAjuste(0, 22.6f, 22.0f), -1.0f},
      {"no maximo -2", (float)corrigirAjuste(-2, 23.0f, 22.0f), -2.0f},
      {"sala 0,6 abaixo: sobe 1", (float)corrigirAjuste(0, 21.4f, 22.0f), 1.0f},
      {"no maximo +1", (float)corrigirAjuste(1, 21.0f, 22.0f), 1.0f},
      {"dentro de 0,5: mantem", (float)corrigirAjuste(-1, 22.3f, 22.0f), -1.0f},
  };
  int falhas = 0;
  for (const auto& caso : casos) {
    if (std::fabs(caso.obtido - caso.esperado) > 0.01f) {
      std::printf("FALHA: %s: %.4f, esperado %.4f\n", caso.nome, caso.obtido, caso.esperado);
      falhas++;
    }
  }
  if (falhas) return 1;
  std::printf("OK: %zu casos do controle do ar (maquinas, alvo, carga, fases e ajuste)\n",
              casos.size());
  return 0;
}
