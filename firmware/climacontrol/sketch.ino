// Movement 2.0 — controle de climatização da sala (ESP32). Bibliotecas: libraries.txt.

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

String movementPendingPayload;

// ── WiFi ───────────────────────────────────────────────────────────────────
#define WIFI_SSID      "Wokwi-GUEST"
#define WIFI_PASSWORD  ""

// ── Pinos ──────────────────────────────────────────────────────────────────
const int pinBarreiraA = 13;   // barreira do lado de fora da porta
const int pinBarreiraB = 26;   // barreira do lado de dentro; GPIO 12 é pino de partida (docs/fisica.md, 9.5)
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

// Porta com duas barreiras: o sentido vem da ordem dos cortes (docs/eletronica-digital.md).
enum EstadoPorta { PORTA_LIVRE, ENTRANDO_A, ENTRANDO_AB, SAINDO_B, SAINDO_BA };
EstadoPorta estadoPorta = PORTA_LIVRE;
const unsigned long FILTRO_BARREIRA_MS = 30;   // o contato do relé oscila ao comutar
int barreiraA = LOW, barreiraB = LOW;          // estado filtrado: HIGH = feixe interrompido
int brutaA = LOW, brutaB = LOW;
unsigned long desdeA = 0, desdeB = 0;

float tempInternaAjustada = 0.0;
bool  primeiraLeitura     = true;

float tempExternaAtual = 25.0;
float umidExternaAtual = 0.0;        // umidade relativa externa
float umidInternaAtual = 0.0;        // umidade relativa interna
float tempRecomendada  = TEMP_CONFORTO_BASE;
float tempAlvoAC       = TEMP_CONFORTO_BASE;
bool  acLigado         = false;
bool  acForcadoOff     = false;      // AC_OFF manual: força o compressor desligado
int   ultimoComandoAC  = -1;

// ── Tempos ─────────────────────────────────────────────────────────────────
unsigned long ultimaLeituraDHT   = 0;
unsigned long ultimoCalculoCalor = 0;
unsigned long ultimoResfriamento = 0;
unsigned long ultimoEnvio         = 0;
unsigned long ultimaConsultaPlano = 0;
const unsigned long intervaloDHT      = 2000;
const unsigned long intervaloCalor    = 10000;
const unsigned long intervaloResfr    = 1000;
unsigned long intervaloEnvio          = 16000; // ajustado pelo plano otimizado da API (15 a 300 s)
const unsigned long intervaloConsultaPlano = 900000UL; // consulta o plano a cada 15 min

// ── Pulsos IR (LED) ────────────────────────────────────────────────────────
// Um pulso por comando, e a duração diz qual é; o alvo muda 1 °C por pulso.
const unsigned long PULSO_BAIXAR   = 100;
const unsigned long PULSO_SUBIR    = 300;
const unsigned long PULSO_LIGAR    = 800;
const unsigned long PULSO_DESLIGAR = 1500;
const unsigned long PAUSA_PULSO    = 200;
bool          pulsoAtivo   = false;
unsigned long inicioPulso  = 0;
unsigned long duracaoPulso = 0;
unsigned long proximoPulso = 0;
// O que o aparelho já recebeu pelo LED; ele começa desligado em 24 °C.
bool ligadoEnviado = false;
int  alvoEnviado   = (int)TEMP_CONFORTO_BASE;

// ════════════════════════════════════════════════════════════════════════════
void setup() {
  Serial.begin(115200);
  Serial.setTimeout(100);   // comandos manuais chegam por linha no monitor serial
  delay(300);

  pinMode(pinBarreiraA, INPUT_PULLUP);   // contato do relé da barreira entre o pino e o GND
  pinMode(pinBarreiraB, INPUT_PULLUP);
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

// Regra do circuito combinacional: F = A · not(C) · (M + B).
bool podeResfriar() {
  return modoAtual == MODO_MANUAL || totalPessoas > 0;
}

// O aparelho fica ligado com not(C) · (M + B): no automático, desliga quando a sala esvazia.
bool acDeveFicarLigado() {
  return !acForcadoOff && podeResfriar();
}

// Próximo pulso para o aparelho chegar ao estado desejado (0 = nenhum); ligar/desligar vem antes.
unsigned long proximoComandoIR(const char*& nome) {
  bool ligar = acDeveFicarLigado();
  if (ligar != ligadoEnviado) {
    ligadoEnviado = ligar;
    nome = ligar ? "LIGAR" : "DESLIGAR";
    return ligar ? PULSO_LIGAR : PULSO_DESLIGAR;
  }
  int alvo = (int)tempAlvoAC;
  if (!ligadoEnviado || alvo == alvoEnviado) return 0;
  bool subir = alvo > alvoEnviado;
  alvoEnviado += subir ? 1 : -1;
  nome = subir ? "SUBIR" : "BAIXAR";
  return subir ? PULSO_SUBIR : PULSO_BAIXAR;
}

// ── Define um novo alvo; processarPulsosIR leva o aparelho até ele ─────────
void definirAlvoAC(float novoAlvo, const char* origem) {
  novoAlvo = constrain(novoAlvo, TEMP_AC_MIN, TEMP_AC_MAX);
  int alvoInt = (int)round(novoAlvo);

  if (alvoInt == ultimoComandoAC) return; // nada mudou

  ultimoComandoAC = alvoInt;
  tempAlvoAC      = alvoInt;

  float desvio = tempInternaAjustada - tempAlvoAC;
  acLigado = acDeveFicarLigado() && (desvio > TOLERANCIA_AC);

  Serial.println(F("\n┌─── COMANDO AO AR-CONDICIONADO ───"));
  Serial.print(F("│ Origem:     ")); Serial.println(origem);
  Serial.print(F("│ Alvo:       ")); Serial.print(alvoInt); Serial.println(F(" °C"));
  Serial.print(F("│ Status:     ")); Serial.println(acLigado ? F("RESFRIANDO") : F("em espera"));
  Serial.println(F("└──────────────────────────────────"));
}

// ── Atualiza alvo no modo automático ───────────────────────────────────────
void atualizarAutomatico() {
  if (modoAtual != MODO_AUTOMATICO || primeiraLeitura) return;
  tempRecomendada = calcularTempRecomendada(tempExternaAtual);
  definirAlvoAC(tempRecomendada, "AUTOMATICO");
}

// ── Comando manual digitado no monitor serial ──────────────────────────────
// AUTO, MANUAL, AC_ON, AC_OFF, TEMP+, TEMP- ou a temperatura alvo (18 a 30).
void processarComandoManual(String cmd) {
  cmd.trim();
  cmd.toUpperCase();
  if (cmd.isEmpty()) return;
  Serial.println("[Manual] Comando recebido: " + cmd);

  if (cmd == "AUTO" || cmd == "AUTOMATICO" || cmd == "MANUAL_OFF") {
    modoAtual = MODO_AUTOMATICO;
    acForcadoOff = false;
    Serial.println(F("[MODO] -> AUTOMATICO (manual cancelado)"));
    atualizarAutomatico();
    return;
  }

  // Entra em modo manual sem mexer no alvo.
  if (cmd == "MANUAL_ON" || cmd == "MANUAL") {
    modoAtual = MODO_MANUAL; inicioModoManual = millis();
    Serial.println(F("[MODO] -> MANUAL"));
    return;
  }

  // Liga o A/C (retoma o resfriamento até o alvo).
  if (cmd == "AC_ON") {
    modoAtual = MODO_MANUAL; inicioModoManual = millis();
    acForcadoOff = false;
    Serial.println(F("[CMD] AC_ON — resfriamento retomado"));
    return;
  }

  // Desliga o A/C (para de resfriar, mantém modo manual).
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
    definirAlvoAC(valor, "MANUAL (serial)");
  } else {
    Serial.println(F("[Manual] Comando ignorado (fora de 18-30 ou invalido)"));
  }
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
  if (desvio > TOLERANCIA_AC && podeResfriar()) {
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
  Serial.printf("| Aparelho:    %s em %d C (pelo IR)\n", ligadoEnviado ? "LIGADO" : "DESLIGADO", alvoEnviado);
  Serial.printf("| Pessoas:     %d  (%.0f W)\n", totalPessoas, totalPessoas * WATTS_POR_PESSOA);
  Serial.println(F("+-------------------------------+"));
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
    if (agora - inicioPulso >= duracaoPulso) {
      digitalWrite(pinLED_IR, LOW);
      pulsoAtivo = false;
      proximoPulso = agora + PAUSA_PULSO;
    }
    return;
  }
  if (agora < proximoPulso) return;
  const char* nome = "";
  duracaoPulso = proximoComandoIR(nome);
  if (duracaoPulso == 0) return;
  digitalWrite(pinLED_IR, HIGH);
  pulsoAtivo = true;
  inicioPulso = agora;
  Serial.printf("[IR] %s (%lu ms) -> aparelho %s em %d C\n", nome, duracaoPulso,
                ligadoEnviado ? "ligado" : "desligado", alvoEnviado);
}

// ── Evento de entrada/saída ────────────────────────────────────────────────
void exibirTotal(const char* acao) {
  Serial.print(F("\n[PRESENCA] ")); Serial.print(acao);
  Serial.print(F("  Total: ")); Serial.println(totalPessoas);
}

// Aceita a leitura do pino só depois de FILTRO_BARREIRA_MS estável; devolve true se mudou.
bool filtrarBarreira(int pino, int& estavel, int& bruta, unsigned long& desde, unsigned long agora) {
  int lida = digitalRead(pino);
  if (lida != bruta) { bruta = lida; desde = agora; }
  if (bruta == estavel || agora - desde < FILTRO_BARREIRA_MS) return false;
  estavel = bruta;
  return true;
}

// Máquina de estados da porta (A = fora, B = dentro); devolve +1 (entrada), -1 (saída) ou 0.
int passoPorta(bool a, bool b) {
  if (!a && !b) {
    int evento = estadoPorta == ENTRANDO_AB ? 1 : estadoPorta == SAINDO_BA ? -1 : 0;
    estadoPorta = PORTA_LIVRE;
    return evento;
  }
  switch (estadoPorta) {
    case PORTA_LIVRE:
      if (a != b) estadoPorta = a ? ENTRANDO_A : SAINDO_B;
      break;
    case ENTRANDO_A:
    case ENTRANDO_AB:
      estadoPorta = b ? ENTRANDO_AB : ENTRANDO_A;
      break;
    case SAINDO_B:
    case SAINDO_BA:
      estadoPorta = a ? SAINDO_BA : SAINDO_B;
      break;
  }
  return 0;
}

// ════════════════════════════════════════════════════════════════════════════
void loop() {
  unsigned long agora = millis();

  // 1) Barreiras da porta: o sentido vem da ordem dos cortes
  bool mudouA = filtrarBarreira(pinBarreiraA, barreiraA, brutaA, desdeA, agora);
  bool mudouB = filtrarBarreira(pinBarreiraB, barreiraB, brutaB, desdeB, agora);
  if (mudouA || mudouB) {
    int evento = passoPorta(barreiraA == HIGH, barreiraB == HIGH);
    if (evento > 0) {
      totalPessoas++; exibirTotal("ENTRADA (+1)");
      atualizarAutomatico();   // só age se estiver em AUTOMATICO
    } else if (evento < 0) {
      if (totalPessoas > 0) { totalPessoas--; exibirTotal("SAIDA (-1)"); atualizarAutomatico(); }
      else Serial.println(F("Aviso: sala vazia."));
    }
  }

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

  // 5) Comando manual pelo monitor serial
  if (Serial.available()) processarComandoManual(Serial.readStringUntil('\n'));

  // 6) Timeout do modo manual
  verificarTimeoutManual();

  // 6b) Plano de leitura otimizado
  if (agora - ultimaConsultaPlano >= intervaloConsultaPlano) {
    ultimaConsultaPlano = agora;
    atualizarIntervalo();
  }

  // 7) Envio da leitura para a API do Movement
  if (agora - ultimoEnvio >= intervaloEnvio) {
    ultimoEnvio = agora;
    enviarMovement();
  }

  // 8) Pulsos IR
  processarPulsosIR();

  delay(10);
}
