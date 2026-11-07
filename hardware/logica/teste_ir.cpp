// Testa no computador a escolha dos comandos IR extraída de firmware/climacontrol/sketch.ino.
// Compile pelo testar_firmware.py, que gera ir_globais.inc e ir_funcoes.inc.
#include <cstdio>
#include <string>
#include <vector>

enum ModoAC { MODO_AUTOMATICO, MODO_MANUAL };
ModoAC modoAtual = MODO_AUTOMATICO;
int totalPessoas = 0;
bool acForcadoOff = false;
const float TEMP_CONFORTO_BASE = 24.0;
float tempAlvoAC = TEMP_CONFORTO_BASE;

#include "ir_globais.inc"
#include "ir_funcoes.inc"

// Pulsos que o LED manda até o aparelho chegar ao estado desejado, com a duração de cada um.
std::string pulsos() {
  std::string lista;
  const char* nome = "";
  for (int i = 0; i < 20; i++) {
    unsigned long duracao = proximoComandoIR(nome);
    if (duracao == 0) break;
    lista += (lista.empty() ? "" : " ") + std::string(nome) + "/" + std::to_string(duracao);
  }
  return lista;
}

int main() {
  struct Passo {
    const char* nome;
    ModoAC modo;
    int pessoas;
    bool forcadoOff;
    int alvo;
    const char* esperado;
  };
  // Cada passo parte do anterior; o aparelho começa desligado em 24 °C.
  const std::vector<Passo> passos = {
      {"sala vazia ao ligar o ESP32", MODO_AUTOMATICO, 0, false, 24, ""},
      {"primeira pessoa entra", MODO_AUTOMATICO, 1, false, 24, "LIGAR/800"},
      {"alvo cai 2 graus", MODO_AUTOMATICO, 7, false, 22, "BAIXAR/100 BAIXAR/100"},
      {"alvo sobe 1 grau", MODO_AUTOMATICO, 4, false, 23, "SUBIR/300"},
      {"nada mudou", MODO_AUTOMATICO, 4, false, 23, ""},
      {"ultima pessoa sai", MODO_AUTOMATICO, 0, false, 24, "DESLIGAR/1500"},
      {"manual com a sala vazia", MODO_MANUAL, 0, false, 21, "LIGAR/800 BAIXAR/100 BAIXAR/100"},
      {"AC_OFF", MODO_MANUAL, 0, true, 21, "DESLIGAR/1500"},
      {"alvo muda desligado", MODO_MANUAL, 0, true, 25, ""},
      {"AC_ON", MODO_MANUAL, 0, false, 25, "LIGAR/800 SUBIR/300 SUBIR/300 SUBIR/300 SUBIR/300"},
      {"volta ao automatico vazia", MODO_AUTOMATICO, 0, false, 24, "DESLIGAR/1500"},
      {"entra com o aparelho em 25", MODO_AUTOMATICO, 3, false, 23,
       "LIGAR/800 BAIXAR/100 BAIXAR/100"},
  };
  int falhas = 0;
  for (const auto& passo : passos) {
    modoAtual = passo.modo;
    totalPessoas = passo.pessoas;
    acForcadoOff = passo.forcadoOff;
    tempAlvoAC = passo.alvo;
    std::string obtido = pulsos();
    if (obtido != passo.esperado) {
      std::printf("FALHA: %s: [%s], esperado [%s]\n", passo.nome, obtido.c_str(), passo.esperado);
      falhas++;
    }
  }
  if (falhas) return 1;
  std::printf("OK: %zu passos dos comandos IR\n", passos.size());
  return 0;
}
