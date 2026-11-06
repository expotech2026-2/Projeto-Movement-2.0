// Testa no computador a lógica da porta extraída de firmware/climacontrol/sketch.ino.
// Compile pelo testar_firmware.py, que gera porta_globais.inc e porta_funcoes.inc.
#include <cstdio>
#include <string>
#include <utility>
#include <vector>

const int HIGH = 1, LOW = 0;
int pinos[64];
int digitalRead(int pino) { return pinos[pino]; }

#include "porta_globais.inc"
#include "porta_funcoes.inc"

const int PINO_A = 13, PINO_B = 26;
int total = 0;
unsigned long agora = 0;

// Mantém (a, b) nos pinos por duracao ms, chamando a lógica a cada 10 ms como o loop().
void manter(int a, int b, unsigned long duracao) {
  pinos[PINO_A] = a;
  pinos[PINO_B] = b;
  for (unsigned long fim = agora + duracao; agora < fim; agora += 10) {
    bool mudouA = filtrarBarreira(PINO_A, barreiraA, brutaA, desdeA, agora);
    bool mudouB = filtrarBarreira(PINO_B, barreiraB, brutaB, desdeB, agora);
    if (mudouA || mudouB) total += passoPorta(barreiraA == HIGH, barreiraB == HIGH);
  }
}

int simular(const std::vector<std::pair<int, int>>& sequencia, bool ruido) {
  total = 0;
  estadoPorta = PORTA_LIVRE;
  int anteriorA = 0, anteriorB = 0;
  for (auto [a, b] : sequencia) {
    // Ruído: o contato que mudou oscila duas vezes em 20 ms antes de assentar.
    if (ruido && a != anteriorA)
      for (int i = 0; i < 2; i++) { manter(a, b, 5); manter(anteriorA, b, 5); }
    if (ruido && b != anteriorB)
      for (int i = 0; i < 2; i++) { manter(a, b, 5); manter(a, anteriorB, 5); }
    manter(a, b, 150);  // feixes a ~15 cm: ~150 ms entre os cortes a 1 m/s
    anteriorA = a;
    anteriorB = b;
  }
  return total;
}

int main() {
  struct Caso {
    const char* nome;
    std::vector<std::pair<int, int>> sequencia;
    int esperado;
  };
  const std::vector<Caso> casos = {
      {"entrada completa", {{0, 0}, {1, 0}, {1, 1}, {0, 1}, {0, 0}}, 1},
      {"saida completa", {{0, 0}, {0, 1}, {1, 1}, {1, 0}, {0, 0}}, -1},
      {"entrada rapida", {{0, 0}, {1, 0}, {0, 1}, {0, 0}}, 1},
      {"desistiu na porta", {{0, 0}, {1, 0}, {0, 0}}, 0},
      {"voltou no meio", {{0, 0}, {1, 0}, {1, 1}, {1, 0}, {0, 0}}, 0},
      {"dois feixes juntos", {{0, 0}, {1, 1}, {0, 0}}, 0},
      {"duas entradas", {{0, 0}, {1, 0}, {1, 1}, {0, 1}, {0, 0}, {1, 0}, {1, 1}, {0, 1}, {0, 0}}, 2},
  };
  int cenarios = 0, falhas = 0;
  for (bool ruido : {false, true}) {
    for (const auto& caso : casos) {
      // Cortes simultâneos com ruído não têm ordem confiável (docs/eletronica-digital.md, seção 2).
      if (ruido && std::string(caso.nome) == "dois feixes juntos") continue;
      int obtido = simular(caso.sequencia, ruido);
      cenarios++;
      if (obtido != caso.esperado) {
        std::printf("FALHA: %s (ruido=%d): %d, esperado %d\n", caso.nome, ruido, obtido,
                    caso.esperado);
        falhas++;
      }
    }
  }
  if (falhas) return 1;
  std::printf("OK: %d cenarios da porta (com e sem ruido nos contatos)\n", cenarios);
  return 0;
}
