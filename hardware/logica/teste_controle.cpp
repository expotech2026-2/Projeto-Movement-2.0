// Testa no computador o caminho botão do site → resposta da API → comando IR, com o código de
// firmware/climacontrol/sketch.ino. Compile pelo testar_firmware.py, que extrai as funções e gera
// casos.inc a partir de controle_site.json (o mesmo arquivo que o backend confere).
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <utility>

// ── O mínimo da String e do Serial do Arduino que o trecho extraído usa ────
class String {
 public:
  String(const char* texto = "") : s_(texto) {}
  String(std::string texto) : s_(std::move(texto)) {}
  int length() const { return static_cast<int>(s_.size()); }
  char charAt(int i) const { return i < length() ? s_[i] : '\0'; }
  int indexOf(const String& trecho, int de = 0) const { return achar(s_.find(trecho.s_, de)); }
  int indexOf(char c, int de = 0) const { return achar(s_.find(c, de)); }
  String substring(int inicio, int fim) const { return s_.substr(inicio, fim - inicio); }
  void trim() {
    const char* brancos = " \t\r\n";
    size_t inicio = s_.find_first_not_of(brancos);
    s_ = inicio == std::string::npos ? "" : s_.substr(inicio, s_.find_last_not_of(brancos) - inicio + 1);
  }
  long toInt() const { return std::strtol(s_.c_str(), nullptr, 10); }
  float toFloat() const { return std::strtof(s_.c_str(), nullptr); }
  const char* c_str() const { return s_.c_str(); }
  bool operator==(const char* outro) const { return s_ == outro; }
  friend String operator+(const String& a, const char* b) { return a.s_ + b; }

 private:
  static int achar(size_t posicao) {
    return posicao == std::string::npos ? -1 : static_cast<int>(posicao);
  }
  std::string s_;
};

struct {
  template <typename... T> void printf(const char*, T...) {}
  template <typename T> void print(T) {}
  template <typename T> void println(T) {}
} Serial;
#define F(texto) texto
template <typename T> T constrain(T valor, T minimo, T maximo) {
  return valor < minimo ? minimo : valor > maximo ? maximo : valor;
}
unsigned long millis() { return 0; }

// ── Estado do firmware que o trecho extraído lê e escreve ──────────────────
enum ModoAC { MODO_AUTOMATICO, MODO_MANUAL };
ModoAC modoAtual = MODO_AUTOMATICO;
int totalPessoas = 0;   // sala vazia
bool acForcadoOff = false;
bool acLigado = false;
const float TEMP_CONFORTO_BASE = 24.0;
const float TEMP_AC_MIN = 16.0;
const float TEMP_AC_MAX = 30.0;
float tempAlvoAC = TEMP_CONFORTO_BASE;
int ultimoComandoAC = -1;
unsigned long inicioModoManual = 0;
unsigned long duracaoManual = 0;
long versaoControle = -1;
bool externaDoSite = false;
float tempExternaAtual = 25.0;
float umidExternaAtual = 0.0;

#include "ir_globais.inc"
#include "ir_funcoes.inc"
void atualizarResfriamento() {}
#include "alvo.inc"
#include "manual.inc"
// No firmware, o automático calcula o alvo; aqui basta um alvo fixo de conforto.
void atualizarAutomatico() {
  if (modoAtual == MODO_AUTOMATICO) definirAlvoAC(TEMP_CONFORTO_BASE, "AUTOMATICO");
}
#include "controle.inc"

struct Caso {
  const char* botao;
  const char* resposta;
  const char* quadro;
};
const Caso CASOS[] = {
#include "casos.inc"
};

std::string quadro() {
  if (!estadoNovoParaEnviar()) return "";
  return ligadoEnviado ? "LIGADO " + std::to_string(alvoEnviado) : "DESLIGADO";
}

int main() {
  atualizarAutomatico();   // como no setup(): automático, sala vazia, ar desligado
  int falhas = quadro().empty() ? 0 : 1;
  for (const Caso& caso : CASOS) {
    aplicarControle(String(caso.resposta));
    std::string obtido = quadro();
    if (obtido != caso.quadro) {
      std::printf("FALHA: %s: [%s], esperado [%s]\n", caso.botao, obtido.c_str(), caso.quadro);
      falhas++;
    }
  }
  if (falhas) return 1;
  std::printf("OK: %zu cliques do site lidos pelo firmware viram o comando IR certo\n",
              sizeof(CASOS) / sizeof(CASOS[0]));
  return 0;
}
