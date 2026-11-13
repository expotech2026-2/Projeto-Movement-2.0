#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>
#include "ir_gateway.h"

class String {
 public:
  std::string value;
  String(const char* text = "") : value(text) {}
  String(std::string text) : value(text) {}
  String(int number) : value(std::to_string(number)) {}
  bool isEmpty() const { return value.empty(); }
  const char* c_str() const { return value.c_str(); }
  int length() const { return int(value.size()); }
  int indexOf(const String& text) const {
    auto pos = value.find(text.value);
    return pos == std::string::npos ? -1 : int(pos);
  }
  int indexOf(char character, int start) const {
    auto pos = value.find(character, start);
    return pos == std::string::npos ? -1 : int(pos);
  }
  char charAt(int i) const { return i < length() ? value[i] : '\0'; }
  String substring(int begin, int end) const { return value.substr(begin, end - begin); }
  void trim() {
    auto first = value.find_first_not_of(" \r\n\t");
    value = first == std::string::npos ? "" : value.substr(first, value.find_last_not_of(" \r\n\t") - first + 1);
  }
  String& operator+=(const String& text) { value += text.value; return *this; }
  bool operator==(const char* text) const { return value == text; }
  friend String operator+(const String& a, const String& b) { return a.value + b.value; }
};

struct {
  template <typename... T> void printf(const char*, T...) {}
  template <typename T> void println(T) {}
} Serial;

#include "json.inc"
uint32_t now = 0;
unsigned long millis() { return now; }
const int WL_CONNECTED = 3;
struct { int connection = WL_CONNECTED; int status() { return connection; } } WiFi;
struct WiFiClient {};
int attempts = 0, ledFrames = 0, ids = 0;
int responseCode = 202;
String responseBody = "{\"accepted\": true}";
String requestedUrl, requestedBody, requestedHeader;
struct HTTPClient {
  void setConnectTimeout(int) {}
  void setTimeout(int) {}
  bool begin(WiFiClient&, const String& url) { requestedUrl = url; return true; }
  void addHeader(const char* name, const char*) { requestedHeader = name; }
  int POST(const String& body) { ++attempts; requestedBody = body; return responseCode; }
  String getString() { return responseBody; }
  void end() {}
};
#define MOVEMENT_XIAOMI_KEY "test-only-key-1234567890123456"
String movementMessageId() {
  char text[40];
  std::snprintf(text, sizeof(text), "12345678-1234-1234-1234-%012d", ++ids);
  return text;
}
bool desiredPower = true, ventilacaoForte = false;
float tempAlvoAC = 23;
bool acDeveFicarLigado() { return desiredPower; }
bool ligadoEnviado = false, forteEnviado = false;
int alvoEnviado = 24;
bool forcarEnvioIR = true, repetirQuadroIR = false;
String emissorIR = "xiaomi", enderecoXiaomi = "http://10.0.0.4:8080/ac", estadoXiaomi, idComandoXiaomi;
GatewayQueue filaXiaomi;
#include "gateway_sender.inc"
enum class decode_type_t { UNKNOWN, SAMSUNG_AC };
decode_type_t protocoloAC = decode_type_t::UNKNOWN;
std::vector<decode_type_t> protocolosSala;
std::vector<int> modelosSala;
int quantidadeProtocolos = 0;
unsigned long ultimoQuadroIR = 0;
const unsigned long INTERVALO_MIN_IR = 1000, REPETICAO_IR_MS = 2000;
bool estadoNovoParaEnviar() { return false; }
void* ultimoEstadoIR(decode_type_t, int) { return nullptr; }
bool enviarEstadoIR(decode_type_t, bool, int, bool, int, void*) { ++ledFrames; return true; }
String typeToString(decode_type_t) { return "SAMSUNG_AC"; }
#define F(text) text
#include "ir_dispatch.inc"

int main() {
  // Xiaomi funciona sem protocolo IR local e não toca o LED.
  processarComandosIR();
  assert(attempts == 1 && ledFrames == 0 && ligadoEnviado && alvoEnviado == 23);
  assert(requestedUrl == "http://10.0.0.4:8080/ac");
  assert(requestedHeader == "Content-Type");
  assert(campoJson(requestedBody, "key") == MOVEMENT_XIAOMI_KEY);
  assert(campoJson(requestedBody, "power") == "true");
  assert(campoJson(requestedBody, "temperature") == "23");
  assert(campoJson(requestedBody, "fan") == "auto");
  processarComandosIR();
  assert(attempts == 1);
  // 200 não significa aceitação; a próxima tentativa preserva o identificador.
  now = 10000;
  responseCode = 200;
  tempAlvoAC = 20;
  ventilacaoForte = true;
  processarComandosIR();
  assert(attempts == 2 && filaXiaomi.pending && alvoEnviado == 23);
  String failedId = campoJson(requestedBody, "id");
  now = 10001;
  processarComandosIR();
  assert(attempts == 2);
  now = 20000;
  responseCode = 202;
  responseBody = "{\"accepted\":false}";
  processarComandosIR();
  assert(attempts == 3 && filaXiaomi.pending && campoJson(requestedBody, "id").value == failedId.value);
  now = 30000;
  responseBody = "{\"accepted\":true}";
  processarComandosIR();
  assert(!filaXiaomi.pending && alvoEnviado == 20 && forteEnviado);
  // Offline, somente a decisão mais recente fica pendente.
  WiFi.connection = 0;
  desiredPower = false;
  processarComandosIR();
  assert(attempts == 4 && filaXiaomi.pending && !filaXiaomi.power);
  now = 40000;
  WiFi.connection = WL_CONNECTED;
  processarComandosIR();
  assert(attempts == 5 && !ligadoEnviado && ledFrames == 0);
  enderecoXiaomi = "http://8.8.8.8:8080/ac";
  forcarEnvioIR = true;
  now = 50000;
  processarComandosIR();
  assert(attempts == 5 && ledFrames == 0);
  // A seleção explícita do ESP32 volta à saída local.
  emissorIR = "esp32";
  protocoloAC = decode_type_t::SAMSUNG_AC;
  forcarEnvioIR = true;
  processarComandosIR();
  assert(ledFrames == 1 && attempts == 5);
  std::puts("OK: Xiaomi/LED, payload, autenticacao isolada, aceite, retry, offline e troca explicita");
}
