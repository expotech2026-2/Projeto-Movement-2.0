// Testa no computador o alvo do modo automático extraído de firmware/climacontrol/sketch.ino.
// Compile pelo testar_firmware.py, que gera conforto_globais.inc e conforto_funcoes.inc.
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <vector>

using std::max;
#define constrain(amt, low, high) ((amt) < (low) ? (low) : ((amt) > (high) ? (high) : (amt)))

#include "conforto_globais.inc"
#include "conforto_funcoes.inc"

int main() {
  struct Caso {
    const char* nome;
    float obtido;
    float esperado;
  };
  // Massa de ar x calor específico = 60 kg x 1005 J/(kg.K) = 60 300 J/K.
  const std::vector<Caso> casos = {
      {"calor de uma pessoa com o ar a 24 C (W)", calorPorPessoa(24.0f), 70.0f},
      {"calor com o ar na temperatura do corpo (W)", calorPorPessoa(36.5f), 0.0f},
      {"calor com o ar acima do corpo (W)", calorPorPessoa(40.0f), 0.0f},
      {"10 pessoas aquecem o ar em 10 min a 24 C", aquecimentoPessoas(10, 24.0f, 600.0f), 2.0896f},
      {"sala vazia: alvo de conforto", calcularTempRecomendada(25.0f, 24.0f, 0), 24.0f},
      {"10 pessoas com o ar a 24 C", calcularTempRecomendada(25.0f, 24.0f, 10), 21.9104f},
      {"10 pessoas com o ar a 30 C", calcularTempRecomendada(25.0f, 30.0f, 10), 22.9134f},
      {"30 pessoas param no minimo da NR-17", calcularTempRecomendada(25.0f, 24.0f, 30), 18.0f},
      {"externa acima de 30 C", calcularTempRecomendada(35.0f, 24.0f, 0), 23.0f},
      {"externa abaixo de 22 C, no maximo da NR-17", calcularTempRecomendada(15.0f, 24.0f, 0), 25.0f},
  };
  int falhas = 0;
  for (const auto& caso : casos) {
    if (std::fabs(caso.obtido - caso.esperado) > 0.001f) {
      std::printf("FALHA: %s: %.4f, esperado %.4f\n", caso.nome, caso.obtido, caso.esperado);
      falhas++;
    }
  }
  if (falhas) return 1;
  std::printf("OK: %zu casos do conforto (corpo humano e NR-17)\n", casos.size());
  return 0;
}
