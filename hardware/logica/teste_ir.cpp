// Testa no computador a escolha dos quadros IR extraída de firmware/climacontrol/sketch.ino.
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

// No máximo um quadro por mudança, com o estado inteiro (ligado e alvo, ou desligado).
std::string quadros() {
  if (!estadoNovoParaEnviar()) return "";
  std::string quadro = ligadoEnviado ? "LIGADO " + std::to_string(alvoEnviado) : "DESLIGADO";
  if (forteEnviado) quadro += " FORTE";
  return estadoNovoParaEnviar() ? quadro + " REPETIDO" : quadro;
}

struct Passo {
  const char* nome;
  ModoAC modo;
  int pessoas;
  bool forcadoOff;
  int alvo;
  bool forte;
  const char* esperado;
};

int main() {
  // Cada passo parte do anterior; o aparelho começa desligado em 24 °C.
  const std::vector<Passo> passos = {
      {"sala vazia ao ligar o ESP32", MODO_AUTOMATICO, 0, false, 24, false, ""},
      {"primeira pessoa entra", MODO_AUTOMATICO, 1, false, 24, false, "LIGADO 24"},
      {"alvo cai 2 graus", MODO_AUTOMATICO, 7, false, 22, false, "LIGADO 22"},
      {"alvo sobe 1 grau", MODO_AUTOMATICO, 4, false, 23, false, "LIGADO 23"},
      {"nada mudou", MODO_AUTOMATICO, 4, false, 23, false, ""},
      {"ultima pessoa sai", MODO_AUTOMATICO, 0, false, 24, false, "DESLIGADO"},
      {"site liga com a sala vazia", MODO_MANUAL, 0, false, 21, false, "LIGADO 21"},
      {"site desliga", MODO_MANUAL, 0, true, 21, false, "DESLIGADO"},
      {"alvo muda desligado", MODO_MANUAL, 0, true, 25, false, ""},
      {"site liga de novo", MODO_MANUAL, 0, false, 25, false, "LIGADO 25"},
      {"volta ao automatico vazia", MODO_AUTOMATICO, 0, false, 24, false, "DESLIGADO"},
      {"entra com o aparelho desligado", MODO_AUTOMATICO, 3, false, 23, false, "LIGADO 23"},
      // Partida forte: ajuste baixo e ventilação no máximo no mesmo quadro.
      {"sala quente: partida forte", MODO_AUTOMATICO, 3, false, 18, true, "LIGADO 18 FORTE"},
      {"chega perto do alvo: manutencao", MODO_AUTOMATICO, 3, false, 22, false, "LIGADO 22"},
      {"so a ventilacao muda", MODO_AUTOMATICO, 3, false, 22, true, "LIGADO 22 FORTE"},
      {"sala esvazia na partida", MODO_AUTOMATICO, 0, false, 22, true, "DESLIGADO"},
      {"desligado, ventilacao nao manda quadro", MODO_AUTOMATICO, 0, false, 22, false, ""},
  };
  int falhas = 0;
  for (const auto& passo : passos) {
    modoAtual = passo.modo;
    totalPessoas = passo.pessoas;
    acForcadoOff = passo.forcadoOff;
    tempAlvoAC = passo.alvo;
    ventilacaoForte = passo.forte;
    std::string obtido = quadros();
    if (obtido != passo.esperado) {
      std::printf("FALHA: %s: [%s], esperado [%s]\n", passo.nome, obtido.c_str(), passo.esperado);
      falhas++;
    }
  }
  if (falhas) return 1;
  std::printf("OK: %zu passos dos quadros IR (um por mudanca, com o estado inteiro)\n",
              passos.size());
  return 0;
}
