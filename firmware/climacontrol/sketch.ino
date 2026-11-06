// SMART AC CONTROLLER — Automático + Manual (TalkBack) Bibliotecas (libraries.txt): DHT sensor library Adafruit Unified Sensor /

#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <esp_system.h>
#include <time.h>
#include "DHT.h"

#if __has_include("config.h")
#include "config.h"
#else
#define MOVEMENT_API_URL "http://192.168.0.10:8000/telemetry"
#define MOVEMENT_DEVICE_TOKEN "PREENCHA_LOCALMENTE"
#define MOVEMENT_CA_CERT ""
#endif

const bool ENABLE_THINGSPEAK_LEGACY = false;
String movementPendingPayload;

// ── WiFi / ThingSpeak ──────────────────────────────────────────────────────
#define WIFI_SSID      "Wokwi-GUEST"
#define WIFI_PASSWORD  ""
#define TS_WRITE_KEY   "PREENCHA_LOCALMENTE"

// TalkBack — pegue em Apps > TalkBack > (seu TalkBack)
#define TALKBACK_ID    "PREENCHA_LOCALMENTE"
#define TALKBACK_KEY   "PREENCHA_LOCALMENTE"

// ── Pinos ──────────────────────────────────────────────────────────────────
const int pinEntrada  = 13;
const int pinSaida    = 26;    // GPIO 12 é pino de partida; ver docs/fisica.md, seção 9.5
const int pinLED_IR   = 2;     // LED simula pulso IR enviado ao AC

#define DHTPIN_EXTERNO 14
#define DHTPIN_INTERNO 27
#ifndef MOVEMENT_DHT_TYPE
#define MOVEMENT_DHT_TYPE DHT22   // modelo do Wokwi; a montagem real usa DHT11 (config.h)
#endif
#define DHTTYPE        MOVEMENT_DHT_TYPE
DHT dhtExterno(DHTPIN_EXTERNO, DHTTYPE);
DHT dhtInterno(DHTPIN_INTERNO, DHTTYPE);

// ── Parâmetros físicos da sala ─────────────────────────────────────────────
const float VOLUME_SALA_M3      = 50.0;
const float DENSIDADE_AR        = 1.2;
const float CALOR_ESPECIFICO_AR = 1005.0;
const float WATTS_POR_PESSOA    = 150.0;
const float FATOR_RETENCAO      = 0.30;

// ── Conforto / AC ──────────────────────────────────────────────────────────
const float TEMP_CONFORTO_BASE      = 24.0;
const float REDUCAO_POR_PESSOA      = 0.3;
const float TEMP_AC_MIN             = 18.0;
const float TEMP_AC_MAX             = 30.0;
const float RESFRIAMENTO_POR_SEGUNDO = 0.05;
const float TOLERANCIA_AC           = 0.5;
float ultimaRawInterna = -1000.0;          // última leitura crua do DHT interno
const float LIMIAR_SALTO_DHT = 2.5;  

// ── Modo de operação ───────────────────────────────────────────────────────
enum ModoAC { MODO_AUTOMATICO, MODO_MANUAL };
ModoAC modoAtual = MODO_AUTOMATICO;

// Quanto tempo o modo manual permanece ativo antes de voltar ao automático
const unsigned long MANUAL_TIMEOUT_MS = 30UL * 60UL * 1000UL; // 30 min
unsigned long inicioModoManual = 0;

// ── Estados ────────────────────────────────────────────────────────────────
int totalPessoas          = 0;
int estadoAnteriorEntrada = LOW;
int estadoAnteriorSaida   = LOW;

float tempInternaAjustada = 0.0;
bool  primeiraLeitura     = true;

float tempExternaAtual = 25.0;
float umidExternaAtual = 0.0;        // umidade relativa externa  -> field6
float umidInternaAtual = 0.0;        // umidade relativa interna  -> field5
float tempRecomendada  = TEMP_CONFORTO_BASE;
float tempAlvoAC       = TEMP_CONFORTO_BASE;
bool  acLigado         = false;
bool  acForcadoOff     = false;      // AC_OFF manual: força o compressor desligado
int   ultimoComandoAC  = -1;

// ── Tempos ─────────────────────────────────────────────────────────────────
unsigned long ultimaLeituraDHT   = 0;
unsigned long ultimoCalculoCalor = 0;
unsigned long ultimoResfriamento = 0;
unsigned long ultimoEnvioTS      = 0;
unsigned long ultimaConsultaTB   = 0;
unsigned long ultimaConsultaPlano = 0;
const unsigned long intervaloDHT      = 2000;
const unsigned long intervaloCalor    = 10000;
const unsigned long intervaloResfr    = 1000;
unsigned long intervaloEnvio          = 16000; // ajustado pelo plano otimizado da API (15 a 300 s)
const unsigned long intervaloTalkBack = 15000; // checa fila a cada 15s
const unsigned long intervaloConsultaPlano = 900000UL; // consulta o plano a cada 15 min

// ── Pulso IR (LED) ─────────────────────────────────────────────────────────
bool          pulsoAtivo      = false;
unsigned long inicioPulso     = 0;
int           pulsosPendentes = 0;
unsigned long proximoPulso    = 0;
const unsigned long DURACAO_PULSO = 100;
const unsigned long PAUSA_PULSO   = 200;

// ════════════════════════════════════════════════════════════════════════════
void setup() {
  Serial.begin(115200);
  delay(300);

  pinMode(pinEntrada, INPUT_PULLUP);   // contato do relé da barreira entre o pino e o GND
  pinMode(pinSaida,   INPUT_PULLUP);
  pinMode(pinLED_IR,  OUTPUT);
  digitalWrite(pinLED_IR, LOW);

  dhtExterno.begin();
  dhtInterno.begin();

  Serial.println(F("\n=== SMART AC CONTROLLER (Auto + Manual) ==="));
  conectarWiFi();
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  atualizarIntervalo();
  ultimaConsultaPlano = millis();
  Serial.println(F("Sistema pronto. Modo inicial: AUTOMATICO\n"));
}

// ── WiFi ────────────────────────────────────────────────────────────────────
void conectarWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print(F("[WiFi] Conectando"));
  int t = 0;
  while (WiFi.status() != WL_CONNECTED && t++ < 40) { delay(300); Serial.print("."); }
  if (WiFi.status() == WL_CONNECTED)
    Serial.println("\n[WiFi] IP: " + WiFi.localIP().toString());
  else
    Serial.println(F("\n[WiFi] Sem conexao (modo offline)."));
}

// ── Temperatura recomendada (modo automático) ──────────────────────────────
float calcularTempRecomendada(float tempExterna) {
  float r = TEMP_CONFORTO_BASE;
  if (tempExterna > 30.0)      r -= 1.0;
  else if (tempExterna < 22.0) r += 1.5;
  if (totalPessoas > 1)        r -= (totalPessoas - 1) * REDUCAO_POR_PESSOA;
  return constrain(r, TEMP_AC_MIN, TEMP_AC_MAX);
}

// ── Define um novo alvo e dispara pulsos IR proporcionais ──────────────────
void definirAlvoAC(float novoAlvo, const char* origem) {
  novoAlvo = constrain(novoAlvo, TEMP_AC_MIN, TEMP_AC_MAX);
  int alvoInt = (int)round(novoAlvo);

  if (alvoInt == ultimoComandoAC) return; // nada mudou

  int diff = (ultimoComandoAC == -1) ? 1 : abs(alvoInt - ultimoComandoAC);
  ultimoComandoAC = alvoInt;
  tempAlvoAC      = alvoInt;

  float desvio = tempInternaAjustada - tempAlvoAC;
  acLigado = !acForcadoOff && (desvio > TOLERANCIA_AC);

  Serial.println(F("\n┌─── COMANDO AO AR-CONDICIONADO ───"));
  Serial.print(F("│ Origem:     ")); Serial.println(origem);
  Serial.print(F("│ Alvo:       ")); Serial.print(alvoInt); Serial.println(F(" °C"));
  Serial.print(F("│ Status:     ")); Serial.println(acLigado ? F("RESFRIANDO") : F("em espera"));
  Serial.print(F("│ Pulsos IR:  ")); Serial.println(diff);
  Serial.println(F("└──────────────────────────────────"));

  pulsosPendentes = diff;     // enfileira pulsos
  proximoPulso    = millis();
}

// ── Atualiza alvo no modo automático ───────────────────────────────────────
void atualizarAutomatico() {
  if (modoAtual != MODO_AUTOMATICO || primeiraLeitura) return;
  tempRecomendada = calcularTempRecomendada(tempExternaAtual);
  definirAlvoAC(tempRecomendada, "AUTOMATICO");
}

// ── Processa comando recebido do TalkBack ──────────────────────────────────
void processarComandoManual(String cmd) {
  cmd.trim();
  cmd.toUpperCase();
  Serial.println("[TalkBack] Comando recebido: " + cmd);

  // Volta ao automático. O dashboard envia MANUAL_OFF; aceitamos AUTO também.
  if (cmd == "AUTO" || cmd == "AUTOMATICO" || cmd == "MANUAL_OFF") {
    modoAtual = MODO_AUTOMATICO;
    acForcadoOff = false;
    Serial.println(F("[MODO] -> AUTOMATICO (manual cancelado)"));
    atualizarAutomatico();
    return;
  }

  // Entra em modo manual sem mexer no alvo (dashboard: MANUAL_ON).
  if (cmd == "MANUAL_ON" || cmd == "MANUAL") {
    modoAtual = MODO_MANUAL; inicioModoManual = millis();
    Serial.println(F("[MODO] -> MANUAL"));
    return;
  }

  // Liga o A/C (retoma o resfriamento até o alvo) — dashboard: AC_ON.
  if (cmd == "AC_ON") {
    modoAtual = MODO_MANUAL; inicioModoManual = millis();
    acForcadoOff = false;
    Serial.println(F("[CMD] AC_ON — resfriamento retomado"));
    return;
  }

  // Desliga o A/C (para de resfriar, mantém modo manual) — dashboard: AC_OFF.
  if (cmd == "AC_OFF") {
    modoAtual = MODO_MANUAL; inicioModoManual = millis();
    acForcadoOff = true;
    acLigado = false;
    Serial.println(F("[CMD] AC_OFF — compressor desligado"));
    return;
  }

  // Ajustes relativos
  if (cmd == "TEMP+" || cmd == "UP") {
    modoAtual = MODO_MANUAL; inicioModoManual = millis();
    acForcadoOff = false;
    definirAlvoAC(tempAlvoAC + 1, "MANUAL (+1)");
    return;
  }
  if (cmd == "TEMP-" || cmd == "DOWN") {
    modoAtual = MODO_MANUAL; inicioModoManual = millis();
    acForcadoOff = false;
    definirAlvoAC(tempAlvoAC - 1, "MANUAL (-1)");
    return;
  }

  // Procura um número no comando (aceita "SET 22", "SET:22", "22", "MANUAL_22")
  int valor = -1000;
  String num = "";
  for (unsigned int i = 0; i < cmd.length(); i++) {
    char c = cmd.charAt(i);
    if (isdigit(c) || (c == '-' && num.length() == 0)) num += c;
    else if (num.length() > 0) break;
  }
  if (num.length() > 0) valor = num.toInt();

  if (valor >= TEMP_AC_MIN && valor <= TEMP_AC_MAX) {
    modoAtual = MODO_MANUAL;
    inicioModoManual = millis();
    acForcadoOff = false;
    Serial.println(F("[MODO] -> MANUAL (automatico suspenso)"));
    definirAlvoAC(valor, "MANUAL (TalkBack)");
  } else {
    Serial.println(F("[TalkBack] Comando ignorado (fora de 18-30 ou invalido)"));
  }
}

// ── Consulta a fila do TalkBack ────────────────────────────────────────────
void consultarTalkBack() {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  String url = "http://api.thingspeak.com/talkbacks/" + String(TALKBACK_ID) + "/commands/execute";
  http.begin(url);
  http.addHeader("Content-Type", "application/x-www-form-urlencoded");
  String body = "api_key=" + String(TALKBACK_KEY);

  int code = http.POST(body);
  if (code == 200) {
    String resp = http.getString();
    resp.trim();
    if (resp.length() > 0) {
      processarComandoManual(resp);   // havia comando na fila
    }
    // se vazio: nada a fazer, segue automático
  } else {
    Serial.printf("[TalkBack] Erro HTTP: %d\n", code);
  }
  http.end();
}

// ── Verifica timeout do modo manual ────────────────────────────────────────
void verificarTimeoutManual() {
  if (modoAtual == MODO_MANUAL &&
      millis() - inicioModoManual >= MANUAL_TIMEOUT_MS) {
    modoAtual = MODO_AUTOMATICO;
    Serial.println(F("\n[MODO] Timeout manual -> retornando ao AUTOMATICO"));
    atualizarAutomatico();
  }
}

// ── Passo de resfriamento gradual ──────────────────────────────────────────
void passoAC() {
  if (primeiraLeitura) return;
  if (acForcadoOff) { acLigado = false; return; }   // AC_OFF manual ativo
  float desvio = tempInternaAjustada - tempAlvoAC;
  if (desvio > TOLERANCIA_AC) {
    acLigado = true;
    tempInternaAjustada -= RESFRIAMENTO_POR_SEGUNDO;
    if (tempInternaAjustada < tempAlvoAC) tempInternaAjustada = tempAlvoAC;
  } else {
    acLigado = false;
  }
}

// ── Calor acumulado pelas pessoas ──────────────────────────────────────────
float calcularDeltaTemperatura(unsigned long deltaMs) {
  if (totalPessoas == 0) return 0.0;
  float pot   = totalPessoas * WATTS_POR_PESSOA;
  float seg   = deltaMs / 1000.0;
  float massa = VOLUME_SALA_M3 * DENSIDADE_AR;
  return (pot * seg * FATOR_RETENCAO) / (massa * CALOR_ESPECIFICO_AR);
}

// ── Leitura dos DHTs ───────────────────────────────────────────────────────
void lerClima() {
  float tExt = dhtExterno.readTemperature();
  float tInt = dhtInterno.readTemperature();
  float hExt = dhtExterno.readHumidity();
  float hInt = dhtInterno.readHumidity();

  if (!isnan(tExt)) tempExternaAtual = tExt;
  if (!isnan(hExt)) umidExternaAtual = hExt;
  if (!isnan(hInt)) umidInternaAtual = hInt;

  if (!isnan(tInt)) {
    if (primeiraLeitura) {
      // Ponto de partida = temperatura medida
      tempInternaAjustada = tInt;
      ultimaRawInterna    = tInt;
      primeiraLeitura     = false;
      atualizarAutomatico();
    }
    else if (fabs(tInt - ultimaRawInterna) > LIMIAR_SALTO_DHT) {
      // Você mexeu no sensor -> novo cenário, a simulação adota o valor
      Serial.printf("[SIM] Novo cenario no DHT interno: %.1f C\n", tInt);
      tempInternaAjustada = tInt;
    }
    ultimaRawInterna = tInt;
    // (sem ancoragem: o AC agora consegue resfriar ate o alvo)
  }

  Serial.println(F("\n+------- LEITURA / STATUS -------+"));
  Serial.printf("| Modo:        %s\n", modoAtual == MODO_AUTOMATICO ? "AUTOMATICO" : "MANUAL");
  Serial.printf("| Externa:     %.1f C\n", tempExternaAtual);
  Serial.printf("| Interna sim: %.1f C\n", tempInternaAjustada);
  Serial.printf("| Umid in/ext: %.0f%% / %.0f%%\n", umidInternaAtual, umidExternaAtual);
  Serial.printf("| Recomendada: %.1f C\n", tempRecomendada);
  Serial.printf("| Alvo AC:     %.1f C  (%s)\n", tempAlvoAC, acLigado ? "ALTERANDO" : "espera");
  Serial.printf("| Pessoas:     %d  (%.0f W)\n", totalPessoas, totalPessoas * WATTS_POR_PESSOA);
  Serial.println(F("+-------------------------------+"));
}

// ── Envio ao ThingSpeak ────────────────────────────────────────────────────
// Mapeamento dos 8 fields (fonte da verdade compartilhada com o dashboard em
// src/config/thingspeak.js e mobile/src/config/thingspeak.js):
//   field1 = ocupacao (pessoas)   field5 = umid_interna
//   field2 = temp_interna         field6 = umid_externa
//   field3 = temp_externa         field7 = ac_ligado   (0/1)
//   field4 = temp_alvo            field8 = modo_manual (0/1)
void enviarThingSpeak() {
  if (WiFi.status() != WL_CONNECTED) { conectarWiFi(); return; }
  HTTPClient http;
  String url = "http://api.thingspeak.com/update?api_key=" + String(TS_WRITE_KEY);
  url += "&field1=" + String(totalPessoas);                       // ocupacao
  url += "&field2=" + String(tempInternaAjustada, 1);             // temp_interna
  url += "&field3=" + String(tempExternaAtual, 1);                // temp_externa
  url += "&field4=" + String(tempAlvoAC, 1);                      // temp_alvo
  url += "&field5=" + String(umidInternaAtual, 1);               // umid_interna
  url += "&field6=" + String(umidExternaAtual, 1);              // umid_externa
  url += "&field7=" + String(acLigado ? 1 : 0);                   // ac_ligado
  url += "&field8=" + String(modoAtual == MODO_MANUAL ? 1 : 0);   // modo_manual
  http.begin(url);
  int code = http.GET();
  if (code == 200) Serial.println("[TS] Enviado. Entry #" + http.getString());
  else             Serial.printf("[TS] Erro HTTP: %d\n", code);
  http.end();
}

String movementMessageId() {
  uint8_t bytes[16];
  esp_fill_random(bytes, sizeof(bytes));
  bytes[6] = (bytes[6] & 0x0F) | 0x40;
  bytes[8] = (bytes[8] & 0x3F) | 0x80;
  char value[37];
  snprintf(value, sizeof(value),
    "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
    bytes[0], bytes[1], bytes[2], bytes[3], bytes[4], bytes[5], bytes[6], bytes[7],
    bytes[8], bytes[9], bytes[10], bytes[11], bytes[12], bytes[13], bytes[14], bytes[15]);
  return String(value);
}

// Abre HTTP ou HTTPS (com o certificado de MOVEMENT_CA_CERT) para a URL informada.
bool abrirMovement(HTTPClient& http, WiFiClient& plain, WiFiClientSecure& secure, const String& url) {
  if (url.startsWith("https://")) {
    if (String(MOVEMENT_CA_CERT).isEmpty()) return false;
    secure.setCACert(MOVEMENT_CA_CERT);
    return http.begin(secure, url);
  }
  return http.begin(plain, url);
}

void enviarMovement() {
  if (WiFi.status() != WL_CONNECTED) { conectarWiFi(); return; }
  if (primeiraLeitura || String(MOVEMENT_DEVICE_TOKEN) == "PREENCHA_LOCALMENTE") return;
  if (movementPendingPayload.isEmpty()) {
    time_t now = time(nullptr);
    if (now < 1700000000) return;
    struct tm utc;
    gmtime_r(&now, &utc);
    char measuredAt[25];
    strftime(measuredAt, sizeof(measuredAt), "%Y-%m-%dT%H:%M:%SZ", &utc);
    movementPendingPayload = "{\"message_id\":\"" + movementMessageId() + "\",\"measured_at\":\"" + String(measuredAt);
    movementPendingPayload += "\",\"occupancy\":" + String(totalPessoas);
    movementPendingPayload += ",\"temp_inside\":" + String(tempInternaAjustada, 1);
    movementPendingPayload += ",\"temp_outside\":" + String(tempExternaAtual, 1);
    movementPendingPayload += ",\"target_temp\":" + String(tempAlvoAC, 1);
    movementPendingPayload += ",\"humidity_inside\":" + String(umidInternaAtual, 1);
    movementPendingPayload += ",\"humidity_outside\":" + String(umidExternaAtual, 1);
    movementPendingPayload += String(",\"ac_on\":") + (acLigado ? "true" : "false");
    movementPendingPayload += String(",\"manual_mode\":") + (modoAtual == MODO_MANUAL ? "true" : "false") + "}";
  }
  HTTPClient http;
  WiFiClient plainClient;
  WiFiClientSecure secureClient;
  if (!abrirMovement(http, plainClient, secureClient, MOVEMENT_API_URL)) return;
  http.setTimeout(5000);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", "Bearer " + String(MOVEMENT_DEVICE_TOKEN));
  unsigned long inicioEnvio = millis();
  int code = http.POST(movementPendingPayload);
  Serial.printf("[Movement] HTTP %d em %lu ms\n", code, millis() - inicioEnvio);
  if (code == 200 || code == 201 || code == 422) movementPendingPayload = "";
  http.end();
}

// Consulta na API o intervalo de envio otimizado para a hora atual (Pesquisa Operacional).
void atualizarIntervalo() {
  if (WiFi.status() != WL_CONNECTED) return;
  if (String(MOVEMENT_DEVICE_TOKEN) == "PREENCHA_LOCALMENTE") return;
  String url = MOVEMENT_API_URL;
  url.replace("/telemetry", "/devices/me/sampling-interval");
  HTTPClient http;
  WiFiClient plainClient;
  WiFiClientSecure secureClient;
  if (!abrirMovement(http, plainClient, secureClient, url)) return;
  http.setTimeout(5000);
  http.addHeader("Authorization", "Bearer " + String(MOVEMENT_DEVICE_TOKEN));
  int code = http.GET();
  if (code == 200) {
    String body = http.getString();
    int inicio = body.indexOf("\"interval_seconds\":");
    long segundos = inicio >= 0 ? body.substring(inicio + 19).toInt() : 0;
    if (segundos > 0) {
      intervaloEnvio = constrain((unsigned long)segundos * 1000UL, 15000UL, 300000UL);
      Serial.printf("[Movement] intervalo de envio: %lu s\n", intervaloEnvio / 1000);
    }
  } else {
    Serial.printf("[Movement] plano indisponivel (HTTP %d); mantendo %lu s\n", code, intervaloEnvio / 1000);
  }
  http.end();
}

// ── Pulsos IR do LED ───────────────────────────────────────────────────────
void processarPulsosIR() {
  unsigned long agora = millis();
  if (pulsoAtivo) {
    if (agora - inicioPulso >= DURACAO_PULSO) {
      digitalWrite(pinLED_IR, LOW);
      pulsoAtivo = false;
      proximoPulso = agora + PAUSA_PULSO;
    }
    return;
  }
  if (pulsosPendentes > 0 && agora >= proximoPulso) {
    digitalWrite(pinLED_IR, HIGH);
    pulsoAtivo = true;
    inicioPulso = agora;
    pulsosPendentes--;
  }
}

// ── Evento de entrada/saída ────────────────────────────────────────────────
void exibirTotal(const char* acao) {
  Serial.print(F("\n[PRESENCA] ")); Serial.print(acao);
  Serial.print(F("  Total: ")); Serial.println(totalPessoas);
}

// ════════════════════════════════════════════════════════════════════════════
void loop() {
  unsigned long agora = millis();

  // 1) Sensores de presença
  int eEnt = digitalRead(pinEntrada);
  int eSai = digitalRead(pinSaida);
  if (eEnt == HIGH && estadoAnteriorEntrada == LOW) {
    totalPessoas++; exibirTotal("ENTRADA (+1)");
    atualizarAutomatico();   // só age se estiver em AUTOMATICO
  }
  if (eSai == HIGH && estadoAnteriorSaida == LOW) {
    if (totalPessoas > 0) { totalPessoas--; exibirTotal("SAIDA (-1)"); atualizarAutomatico(); }
    else Serial.println(F("Aviso: sala vazia."));
  }
  estadoAnteriorEntrada = eEnt;
  estadoAnteriorSaida   = eSai;

  // 2) Calor das pessoas
  if (agora - ultimoCalculoCalor >= intervaloCalor) {
    unsigned long d = agora - ultimoCalculoCalor;
    ultimoCalculoCalor = agora;
    if (!primeiraLeitura && totalPessoas > 0)
      tempInternaAjustada += calcularDeltaTemperatura(d);
  }

  // 3) Resfriamento gradual (vale para auto E manual)
  if (agora - ultimoResfriamento >= intervaloResfr) {
    ultimoResfriamento = agora;
    passoAC();
  }

  // 4) Leitura DHT
  if (agora - ultimaLeituraDHT >= intervaloDHT) {
    ultimaLeituraDHT = agora;
    lerClima();
  }

  // 5) Consulta TalkBack (override manual)
  if (ENABLE_THINGSPEAK_LEGACY && agora - ultimaConsultaTB >= intervaloTalkBack) {
    ultimaConsultaTB = agora;
    consultarTalkBack();
  }

  // 6) Timeout do modo manual
  verificarTimeoutManual();

  // 6b) Plano de leitura otimizado
  if (agora - ultimaConsultaPlano >= intervaloConsultaPlano) {
    ultimaConsultaPlano = agora;
    atualizarIntervalo();
  }

  // 7) Envio ThingSpeak
  if (agora - ultimoEnvioTS >= intervaloEnvio) {
    ultimoEnvioTS = agora;
    enviarMovement();
    if (ENABLE_THINGSPEAK_LEGACY) enviarThingSpeak();
  }

  // 8) Pulsos IR
  processarPulsosIR();

  delay(10);
}
