#include <vector>
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
  bool operator==(const String& outro) const { return s_ == outro.s_; }
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
int capacidadeSala = 0;
int computadoresSala = -1;
float potenciaArSala = -1.0;
float uaSala = -1.0;
float calorFixoSala = -1.0;

#include "ir_globais.inc"
#include "ir_funcoes.inc"
void atualizarResfriamento() {}
#include "alvo.inc"
#include "manual.inc"
// No firmware, o automático calcula o alvo; aqui basta um alvo fixo de conforto.
void atualizarAutomatico() {
  if (modoAtual == MODO_AUTOMATICO) definirAlvoAC(TEMP_CONFORTO_BASE, "AUTOMATICO");
}
enum class decode_type_t { UNKNOWN, GREE, LG2, SAMSUNG_AC };
bool forcarEnvioIR = false;
bool repetirQuadroIR = false;
long versaoProtocolosIR = -1;
String configuracaoIRSite;
bool recebeuConfiguracaoIR = false;
std::vector<decode_type_t> protocolosSala;
std::vector<int> modelosSala;
int quantidadeProtocolos = 0;
decode_type_t protocoloAC = decode_type_t::UNKNOWN;
decode_type_t strToDecodeType(const char* name) {
  std::string value(name);
  if (value == "GREE") return decode_type_t::GREE;
  if (value == "LG2") return decode_type_t::LG2;
  if (value == "SAMSUNG_AC") return decode_type_t::SAMSUNG_AC;
  return decode_type_t::UNKNOWN;
}
struct IRac {
  static bool isProtocolSupported(decode_type_t value) { return value != decode_type_t::UNKNOWN; }
};
#include "protocolos.inc"
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
  if (capacidadeSala != 1 || computadoresSala != 0 || potenciaArSala != 0.0f ||
      uaSala != 18.9f || calorFixoSala != 249.2f) {
    std::printf("FALHA: sala de testes: %d pessoas, %d computadores, %.1f W, %.1f W/K, %.1f W\n",
                capacidadeSala, computadoresSala, potenciaArSala, uaSala, calorFixoSala);
    falhas++;
  }
  // O admin cadastra a sala e um ar de 24 000 BTU/h sem novo comando: a mesma versão já vale.
  aplicarControle(String(
      "{\"version\":5,\"mode\":\"auto\",\"target\":null,\"remaining_seconds\":0,"
      "\"temp_outside\":null,\"humidity_outside\":null,\"capacity\":40,\"computers\":20,"
      "\"ac_power_w\":5275.5,\"ua_w_k\":137.6,\"fixed_heat_w\":2081.4}"));
  if (capacidadeSala != 40 || computadoresSala != 20 || potenciaArSala != 5275.5f ||
      uaSala != 137.6f || calorFixoSala != 2081.4f || !quadro().empty()) {
    std::printf("FALHA: sala cadastrada: %d pessoas, %d computadores, %.1f W, %.1f W/K, %.1f W\n",
                capacidadeSala, computadoresSala, potenciaArSala, uaSala, calorFixoSala);
    falhas++;
  }
  aplicarControle(String("{\"version\":5,\"ir_protocols\":\"LG2:2,SAMSUNG_AC:1\"}"));
  if (quantidadeProtocolos != 2 || modelosSala[0] != 2 ||
      protocolosSala[1] != decode_type_t::SAMSUNG_AC || !forcarEnvioIR) falhas++;
  forcarEnvioIR = false;
  aplicarControle(String("{\"version\":5,\"ir_protocols\":\"LG2:2,SAMSUNG_AC:1\"}"));
  if (forcarEnvioIR) falhas++;
  aplicarControle(String("{\"version\":5,\"ir_protocols\":\"\"}"));
  if (quantidadeProtocolos != 0 || protocoloAC != decode_type_t::UNKNOWN) falhas++;
  aplicarProtocolosSite(String("INVALIDO:1,GREE:0,LG2:7"));
  if (quantidadeProtocolos != 0) falhas++;
  aplicarControle(String("{\"version\":5,\"ir_protocols\":\"SAMSUNG_AC:1\",\"ir_revision\":1}"));
  forcarEnvioIR = false;
  aplicarControle(String("{\"version\":5,\"ir_protocols\":\"SAMSUNG_AC:1\",\"ir_revision\":2}"));
  if (!forcarEnvioIR || versaoProtocolosIR != 2 || versaoControle != 5) falhas++;
  if (falhas) return 1;
  std::printf("OK: %zu cliques do site lidos pelo firmware viram o comando IR certo\n",
              sizeof(CASOS) / sizeof(CASOS[0]));
  return 0;
}
