// Movement 2.0 — controle de climatização da sala (ESP32). Bibliotecas: libraries.txt.

#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <Preferences.h>
#include <esp_system.h>
#include <time.h>
#include "DHT.h"
#include <IRremoteESP8266.h>
#include <IRac.h>
#include <IRutils.h>

#if __has_include("config.h")
#include "config.h"
#endif
#ifndef MOVEMENT_API_URL
#define MOVEMENT_API_URL "http://192.168.0.10:8000/telemetry"
#define MOVEMENT_DEVICE_TOKEN "PREENCHA_LOCALMENTE"
#define MOVEMENT_CA_CERT ""
#endif
#ifndef MOVEMENT_WIFI_SSID
#define MOVEMENT_WIFI_SSID     "Wokwi-GUEST"   // a montagem real define a rede no config.h
#define MOVEMENT_WIFI_PASSWORD ""
#endif
#ifndef MOVEMENT_AC_PROTOCOLO
#define MOVEMENT_AC_PROTOCOLO ""   // vazio = pulsos simulados no LED (contexto/hardware.md)
#endif

String movementPendingPayload;
const char* VERSAO_FIRMWARE = "2.1.0";   // aparece no diagnóstico do site

// ── Pinos ──────────────────────────────────────────────────────────────────
const int pinBarreiraA = 13;   // barreira do lado de fora da porta
const int pinBarreiraB = 26;   // barreira do lado de dentro; GPIO 12 é pino de partida (docs/fisica.md, 9.5)
const int pinLED_IR   = 2;     // LED IR, pelo BC547, apontado para o ar-condicionado

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
const float FATOR_RETENCAO      = 0.30;

// ── Conforto / AC ──────────────────────────────────────────────────────────
const float TEMP_CONFORTO_BASE      = 24.0;
const float NR17_MIN                = 18.0;   // NR-17, 17.8.4.2: 18 a 25 °C em ambiente climatizado
const float NR17_MAX                = 25.0;
const float TEMP_CORPO              = 36.5;   // temperatura média do corpo humano
const float CONDUTANCIA_PESSOA      = 5.6;    // W/K: 70 W de calor sensível a 24 °C, pessoa sentada
const float HORIZONTE_PREVISAO_S    = 600.0;  // o alvo antecipa o calor dos próximos 10 min
const float TEMP_AC_MIN             = 16.0;   // faixa do comando manual (professor)
const float TEMP_AC_MAX             = 30.0;
const float TOLERANCIA_AC           = 0.5;

// ── Modo de operação ───────────────────────────────────────────────────────
enum ModoAC { MODO_AUTOMATICO, MODO_MANUAL };
ModoAC modoAtual = MODO_AUTOMATICO;

// Quanto tempo o modo manual permanece ativo antes de voltar ao automático
const unsigned long MANUAL_TIMEOUT_MS = 2UL * 60UL * 60UL * 1000UL; // 2 h
unsigned long inicioModoManual = 0;
unsigned long duracaoManual    = MANUAL_TIMEOUT_MS;   // o site manda o tempo que falta

// ── Estados ────────────────────────────────────────────────────────────────
int totalPessoas          = 0;

// Porta com duas barreiras: o sentido vem da ordem dos cortes (docs/eletronica-digital.md).
enum EstadoPorta { PORTA_LIVRE, ENTRANDO_A, ENTRANDO_AB, SAINDO_B, SAINDO_BA };
EstadoPorta estadoPorta = PORTA_LIVRE;
const unsigned long FILTRO_BARREIRA_MS = 30;   // o contato do relé oscila ao comutar
int barreiraA = LOW, barreiraB = LOW;          // estado filtrado: HIGH = feixe interrompido
int brutaA = LOW, brutaB = LOW;
unsigned long desdeA = 0, desdeB = 0;
QueueHandle_t filaPorta;                       // passagens (+1/-1) da tarefa da porta para o loop()

float tempInterna     = 0.0;         // última leitura válida do DHT da sala
bool  primeiraLeitura = true;
bool  falhaDhtInterno = false;       // última leitura sem resposta (diagnóstico)
bool  falhaDhtExterno = false;

float tempExternaAtual = 25.0;
float umidExternaAtual = 0.0;        // umidade relativa externa
float umidInternaAtual = 0.0;        // umidade relativa interna
float tempRecomendada  = TEMP_CONFORTO_BASE;
float tempAlvoAC       = TEMP_CONFORTO_BASE;
bool  acLigado         = false;      // estimativa de compressor resfriando (F)
bool  acForcadoOff     = false;      // AC_OFF manual: força o aparelho desligado
int   ultimoComandoAC  = -1;

// ── Tempos ─────────────────────────────────────────────────────────────────
unsigned long ultimaLeituraDHT   = 0;
unsigned long ultimoEnvio         = 0;
unsigned long ultimaConsultaPlano = 0;
const unsigned long intervaloDHT      = 2000;
unsigned long intervaloEnvio          = 16000; // ajustado pelo plano otimizado da API (15 a 300 s)
const unsigned long intervaloConsultaPlano = 900000UL; // consulta o plano a cada 15 min

// ── Comando do professor e temperatura externa (site) ──────────────────────
unsigned long ultimaConsultaControle = 0;
long versaoControle = -1;            // último comando do site já aplicado
bool externaDoSite  = false;         // temperatura externa da Open-Meteo, pela cidade da unidade

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

// ── Protocolo real do ar-condicionado (IRremoteESP8266) ────────────────────
IRac arCondicionado(pinLED_IR);
decode_type_t protocoloAC = decode_type_t::UNKNOWN;   // UNKNOWN = pulsos simulados
bool forcarEnvioIR = false;                           // reenvia o estado atual uma vez
unsigned long ultimoQuadroIR = 0;
const unsigned long INTERVALO_MIN_IR = 1000;          // junta mudanças rápidas num só quadro
Preferences preferencias;
// Protocolos das marcas mais comuns no Brasil, na ordem do IR_TESTE (contexto/hardware.md).
const decode_type_t PROTOCOLOS_TESTE[] = {
  decode_type_t::LG2,          decode_type_t::LG,           decode_type_t::SAMSUNG_AC,
  decode_type_t::MIDEA,        decode_type_t::COOLIX,       decode_type_t::GREE,
  decode_type_t::KELVINATOR,   decode_type_t::TCL112AC,     decode_type_t::WHIRLPOOL_AC,
  decode_type_t::DAIKIN,       decode_type_t::FUJITSU_AC,   decode_type_t::HITACHI_AC,
  decode_type_t::ELECTRA_AC,   decode_type_t::CARRIER_AC64,
};

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
  // A porta roda numa tarefa própria no núcleo 0, então um envio HTTP lento não perde passagens.
  filaPorta = xQueueCreate(16, sizeof(int));
  xTaskCreatePinnedToCore(tarefaPorta, "porta", 4096, nullptr, 1, nullptr, 0);
  carregarProtocoloIR();
  conectarWiFi();
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  atualizarIntervalo();
  ultimaConsultaPlano = millis();
  consultarControle();
  ultimaConsultaControle = millis();
  atualizarAutomatico();
  Serial.println(F("Sistema pronto. Modo inicial: AUTOMATICO\n"));
}

// ── WiFi ────────────────────────────────────────────────────────────────────
void conectarWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(MOVEMENT_WIFI_SSID, MOVEMENT_WIFI_PASSWORD);
  Serial.printf("[WiFi] Conectando em %s", MOVEMENT_WIFI_SSID);
  int t = 0;
  while (WiFi.status() != WL_CONNECTED && t++ < 40) { delay(300); Serial.print("."); }
  if (WiFi.status() == WL_CONNECTED)
    Serial.println("\n[WiFi] IP: " + WiFi.localIP().toString());
  else
    Serial.println(F("\n[WiFi] Sem conexao; o ESP32 segue tentando sem parar a contagem."));
}

// ── Temperatura recomendada (modo automático) ──────────────────────────────
// Calor sensível de uma pessoa: proporcional à diferença entre o corpo e o ar.
float calorPorPessoa(float tempSala) {
  return max(0.0f, CONDUTANCIA_PESSOA * (TEMP_CORPO - tempSala));
}

// Quanto as pessoas aquecem o ar em "segundos" (só a fração do calor que fica no ar).
float aquecimentoPessoas(int pessoas, float tempSala, float segundos) {
  float massa = VOLUME_SALA_M3 * DENSIDADE_AR;
  return pessoas * calorPorPessoa(tempSala) * segundos * FATOR_RETENCAO /
         (massa * CALOR_ESPECIFICO_AR);
}

// Alvo: conforto pela temperatura externa menos o aquecimento previsto, dentro da NR-17.
float calcularTempRecomendada(float tempExterna, float tempSala, int pessoas) {
  float r = TEMP_CONFORTO_BASE;
  if (tempExterna > 30.0)      r -= 1.0;
  else if (tempExterna < 22.0) r += 1.5;
  r -= aquecimentoPessoas(pessoas, tempSala, HORIZONTE_PREVISAO_S);
  return constrain(r, NR17_MIN, NR17_MAX);
}

// Temperatura da sala para o cálculo: a do DHT ou, antes da primeira leitura, a de conforto.
float tempSalaParaCalculo() {
  return primeiraLeitura ? TEMP_CONFORTO_BASE : tempInterna;
}

// Regra do circuito combinacional: F = A · not(C) · (M + B).
bool podeResfriar() {
  return modoAtual == MODO_MANUAL || totalPessoas > 0;
}

// O aparelho fica ligado com not(C) · (M + B): no automático, desliga quando a sala esvazia.
bool acDeveFicarLigado() {
  return !acForcadoOff && podeResfriar();
}

// Protocolo real: cada quadro leva o estado inteiro; devolve true quando há um estado novo a enviar.
bool estadoNovoParaEnviar() {
  bool ligar = acDeveFicarLigado();
  int alvo = (int)tempAlvoAC;
  if (ligar == ligadoEnviado && (!ligar || alvo == alvoEnviado)) return false;
  ligadoEnviado = ligar;
  alvoEnviado = alvo;
  return true;
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

// F = A · not(C) · (M + B): estima se o compressor resfria; quem controla de fato é o aparelho.
void atualizarResfriamento() {
  acLigado = !primeiraLeitura && acDeveFicarLigado() && (tempInterna - tempAlvoAC > TOLERANCIA_AC);
}

// ── Define um novo alvo; processarComandosIR leva o aparelho até ele ───────
void definirAlvoAC(float novoAlvo, const char* origem) {
  novoAlvo = constrain(novoAlvo, TEMP_AC_MIN, TEMP_AC_MAX);
  int alvoInt = (int)round(novoAlvo);

  if (alvoInt == ultimoComandoAC) return; // nada mudou

  ultimoComandoAC = alvoInt;
  tempAlvoAC      = alvoInt;
  atualizarResfriamento();

  Serial.println(F("\n┌─── COMANDO AO AR-CONDICIONADO ───"));
  Serial.print(F("│ Origem:     ")); Serial.println(origem);
  Serial.print(F("│ Alvo:       ")); Serial.print(alvoInt); Serial.println(F(" °C"));
  Serial.print(F("│ Status:     ")); Serial.println(acLigado ? F("RESFRIANDO") : F("em espera"));
  Serial.println(F("└──────────────────────────────────"));
}

// ── Atualiza alvo no modo automático ───────────────────────────────────────
void atualizarAutomatico() {
  if (modoAtual != MODO_AUTOMATICO) return;
  tempRecomendada = calcularTempRecomendada(tempExternaAtual, tempSalaParaCalculo(), totalPessoas);
  definirAlvoAC(tempRecomendada, "AUTOMATICO");
}

// Entra no modo manual pelo tempo indicado; depois volta sozinho ao automático.
void entrarManual(unsigned long duracaoMs) {
  modoAtual = MODO_MANUAL;
  inicioModoManual = millis();
  duracaoManual = duracaoMs;
}

// ── Comando manual digitado no monitor serial ──────────────────────────────
// AUTO, MANUAL, AC_ON, AC_OFF, TEMP+, TEMP-, a temperatura alvo (16 a 30), IR <protocolo> ou IR_TESTE.
void processarComandoManual(String cmd) {
  cmd.trim();
  cmd.toUpperCase();
  if (cmd.isEmpty()) return;
  Serial.println("[Manual] Comando recebido: " + cmd);

  if (cmd == "IR_TESTE") { testarProtocolosIR(); return; }
  if (cmd.startsWith("IR ")) { definirProtocoloIR(cmd.substring(3), true); return; }

  if (cmd == "AUTO" || cmd == "AUTOMATICO" || cmd == "MANUAL_OFF") {
    modoAtual = MODO_AUTOMATICO;
    acForcadoOff = false;
    Serial.println(F("[MODO] -> AUTOMATICO (manual cancelado)"));
    atualizarAutomatico();
    return;
  }

  // Entra em modo manual sem mexer no alvo.
  if (cmd == "MANUAL_ON" || cmd == "MANUAL") {
    entrarManual(MANUAL_TIMEOUT_MS);
    Serial.println(F("[MODO] -> MANUAL"));
    return;
  }

  // Liga o A/C (retoma o resfriamento até o alvo).
  if (cmd == "AC_ON") {
    entrarManual(MANUAL_TIMEOUT_MS);
    acForcadoOff = false;
    Serial.println(F("[CMD] AC_ON — aparelho ligado"));
    return;
  }

  // Desliga o A/C (mantém modo manual).
  if (cmd == "AC_OFF") {
    entrarManual(MANUAL_TIMEOUT_MS);
    acForcadoOff = true;
    acLigado = false;
    Serial.println(F("[CMD] AC_OFF — aparelho desligado"));
    return;
  }

  // Ajustes relativos
  if (cmd == "TEMP+" || cmd == "UP") {
    entrarManual(MANUAL_TIMEOUT_MS);
    acForcadoOff = false;
    definirAlvoAC(tempAlvoAC + 1, "MANUAL (+1)");
    return;
  }
  if (cmd == "TEMP-" || cmd == "DOWN") {
    entrarManual(MANUAL_TIMEOUT_MS);
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
    entrarManual(MANUAL_TIMEOUT_MS);
    acForcadoOff = false;
    Serial.println(F("[MODO] -> MANUAL (automatico suspenso)"));
    definirAlvoAC(valor, "MANUAL (serial)");
  } else {
    Serial.println(F("[Manual] Comando ignorado (fora de 16-30 ou invalido)"));
  }
}

// ── Verifica timeout do modo manual ────────────────────────────────────────
void verificarTimeoutManual() {
  if (modoAtual == MODO_MANUAL &&
      millis() - inicioModoManual >= duracaoManual) {
    modoAtual = MODO_AUTOMATICO;
    acForcadoOff = false;   // um "desligar" também vence junto com o manual
    Serial.println(F("\n[MODO] Timeout manual -> retornando ao AUTOMATICO"));
    atualizarAutomatico();
  }
}

// ── Leitura dos DHTs ───────────────────────────────────────────────────────
void lerClima() {
  float tExt = dhtExterno.readTemperature();
  float tInt = dhtInterno.readTemperature();
  float hExt = dhtExterno.readHumidity();
  float hInt = dhtInterno.readHumidity();
  falhaDhtInterno = isnan(tInt) || isnan(hInt);
  falhaDhtExterno = isnan(tExt) || isnan(hExt);

  // O sensor externo só vale quando o site não tem a temperatura da cidade.
  if (!isnan(tExt) && !externaDoSite) tempExternaAtual = tExt;
  if (!isnan(hExt) && !externaDoSite) umidExternaAtual = hExt;
  if (!isnan(hInt)) umidInternaAtual = hInt;
  if (!isnan(tInt)) {
    tempInterna = tInt;
    primeiraLeitura = false;
  } else if (primeiraLeitura) {
    Serial.println(F("[DHT] Sem leitura do sensor da sala (GPIO 27): confira o fio e o pull-up."));
  }
  atualizarAutomatico();   // a temperatura externa também muda o alvo
  atualizarResfriamento();

  Serial.println(F("\n+------- LEITURA / STATUS -------+"));
  Serial.printf("| Modo:        %s\n", modoAtual == MODO_AUTOMATICO ? "AUTOMATICO" : "MANUAL");
  Serial.printf("| Externa:     %.1f C (%s)\n", tempExternaAtual, externaDoSite ? "Open-Meteo" : "sensor");
  if (primeiraLeitura) Serial.println(F("| Interna:     sem leitura"));
  else Serial.printf("| Interna:     %.1f C\n", tempInterna);
  Serial.printf("| Umid in/ext: %.0f%% / %.0f%%\n", umidInternaAtual, umidExternaAtual);
  Serial.printf("| Recomendada: %.1f C\n", tempRecomendada);
  Serial.printf("| Alvo AC:     %.1f C  (%s)\n", tempAlvoAC, acLigado ? "RESFRIANDO" : "espera");
  Serial.printf("| Aparelho:    %s em %d C (%s)\n", ligadoEnviado ? "LIGADO" : "DESLIGADO", alvoEnviado,
                protocoloAC == decode_type_t::UNKNOWN ? "IR simulado" : typeToString(protocoloAC).c_str());
  float tempSala = tempSalaParaCalculo();
  Serial.printf("| Pessoas:     %d  (%.0f W do corpo, +%.2f C/min)\n", totalPessoas,
                totalPessoas * calorPorPessoa(tempSala), aquecimentoPessoas(totalPessoas, tempSala, 60));
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

// Token e diagnóstico em toda chamada: o site mostra online/offline, sinal, sensores e o ar.
void cabecalhosMovement(HTTPClient& http) {
  http.addHeader("Authorization", "Bearer " + String(MOVEMENT_DEVICE_TOKEN));
  http.addHeader("X-Movement-Firmware", VERSAO_FIRMWARE);
  http.addHeader("X-Movement-RSSI", String(WiFi.RSSI()));
  http.addHeader("X-Movement-Uptime", String(millis() / 1000UL));
  String falhas = "";
  if (falhaDhtInterno) falhas = "DHT da sala (GPIO 27)";
  if (falhaDhtExterno) falhas += String(falhas.isEmpty() ? "" : ", ") + "DHT externo (GPIO 14)";
  http.addHeader("X-Movement-Sensors", falhas.isEmpty() ? "ok" : falhas);
  String protocolo = protocoloAC == decode_type_t::UNKNOWN ? "IR simulado" : typeToString(protocoloAC);
  String ar = ligadoEnviado ? "ligado " + String(alvoEnviado) + " C" : "desligado";
  http.addHeader("X-Movement-AC", ar + ", " + protocolo);
}

void enviarMovement() {
  if (WiFi.status() != WL_CONNECTED) { WiFi.reconnect(); return; }   // não bloqueia o loop
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
    movementPendingPayload += ",\"temp_inside\":" + String(tempInterna, 1);
    movementPendingPayload += ",\"temp_outside\":" + String(tempExternaAtual, 1);
    movementPendingPayload += ",\"target_temp\":" + String(tempAlvoAC, 1);
    movementPendingPayload += ",\"humidity_inside\":" + String(umidInternaAtual, 1);
    movementPendingPayload += ",\"humidity_outside\":" + String(umidExternaAtual, 1);
    movementPendingPayload += String(",\"ac_on\":") + (ligadoEnviado ? "true" : "false");
    movementPendingPayload += String(",\"manual_mode\":") + (modoAtual == MODO_MANUAL ? "true" : "false") + "}";
  }
  HTTPClient http;
  WiFiClient plainClient;
  WiFiClientSecure secureClient;
  if (!abrirMovement(http, plainClient, secureClient, MOVEMENT_API_URL)) return;
  http.setTimeout(5000);
  http.addHeader("Content-Type", "application/json");
  cabecalhosMovement(http);
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
  cabecalhosMovement(http);
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

// ── Comando do professor (site) ────────────────────────────────────────────
// Valor de um campo do JSON plano da API, sem aspas ("" se faltar ou for null).
String campoJson(const String& corpo, const char* nome) {
  String chave = String("\"") + nome + "\":";
  int i = corpo.indexOf(chave);
  if (i < 0) return "";
  i += chave.length();
  if (corpo.charAt(i) == '"') {
    int fim = corpo.indexOf('"', i + 1);
    return fim < 0 ? "" : corpo.substring(i + 1, fim);
  }
  int fim = i;
  while (fim < (int)corpo.length() && corpo.charAt(fim) != ',' && corpo.charAt(fim) != '}') fim++;
  String valor = corpo.substring(i, fim);
  valor.trim();
  return valor == "null" ? "" : valor;
}

// Aplica cada comando do site uma vez (pela versão) e guarda a temperatura externa da cidade.
void aplicarControle(const String& corpo) {
  String tExt = campoJson(corpo, "temp_outside");
  externaDoSite = tExt.length() > 0;
  if (externaDoSite) {
    tempExternaAtual = tExt.toFloat();
    String hExt = campoJson(corpo, "humidity_outside");
    if (hExt.length() > 0) umidExternaAtual = hExt.toFloat();
  }
  long versao = campoJson(corpo, "version").toInt();
  if (versao == versaoControle) return;
  versaoControle = versao;
  String modo = campoJson(corpo, "mode");
  long restante = campoJson(corpo, "remaining_seconds").toInt();
  Serial.printf("\n[SITE] Comando %ld do professor: %s\n", versao, modo.c_str());
  if (modo == "auto" || restante <= 0) {
    modoAtual = MODO_AUTOMATICO;
    acForcadoOff = false;
    atualizarAutomatico();
    return;
  }
  entrarManual((unsigned long)restante * 1000UL);
  acForcadoOff = modo == "off";
  if (acForcadoOff) acLigado = false;
  else definirAlvoAC(campoJson(corpo, "target").toFloat(), "SITE (professor)");
}

// Sala ocupada ou em manual: consulta a cada 15 s; vazia, a cada 1 min (gasta menos energia).
unsigned long intervaloControle() {
  return totalPessoas > 0 || modoAtual == MODO_MANUAL ? 15000UL : 60000UL;
}

void consultarControle() {
  if (WiFi.status() != WL_CONNECTED) return;
  if (String(MOVEMENT_DEVICE_TOKEN) == "PREENCHA_LOCALMENTE") return;
  String url = MOVEMENT_API_URL;
  url.replace("/telemetry", "/devices/me/control");
  HTTPClient http;
  WiFiClient plainClient;
  WiFiClientSecure secureClient;
  if (!abrirMovement(http, plainClient, secureClient, url)) return;
  http.setTimeout(5000);
  cabecalhosMovement(http);
  int code = http.GET();
  if (code == 200) aplicarControle(http.getString());
  else Serial.printf("[SITE] comando indisponivel (HTTP %d)\n", code);
  http.end();
}

// ── Pulsos IR simulados no LED ─────────────────────────────────────────────
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

// ── Protocolo real do ar-condicionado ──────────────────────────────────────
// Manda o estado inteiro (ligado em frio no alvo, ou desligado) no protocolo informado.
bool enviarEstadoIR(decode_type_t protocolo, bool ligado, int alvo) {
  arCondicionado.next.protocol = protocolo;
  // LG e LG2 só diferem pelo modelo do controle (AKB75215403 = LG2); nos outros vale o primeiro.
  arCondicionado.next.model    = protocolo == decode_type_t::LG2 ? 2 : 1;
  arCondicionado.next.power    = ligado;
  arCondicionado.next.mode     = stdAc::opmode_t::kCool;
  arCondicionado.next.celsius  = true;
  arCondicionado.next.degrees  = alvo;
  arCondicionado.next.fanspeed = stdAc::fanspeed_t::kAuto;
  return arCondicionado.sendAc();
}

// Escolhe o protocolo pelo nome (GREE, LG2, SAMSUNG_AC...) ou SIMULADO; salvar grava na flash.
void definirProtocoloIR(String nome, bool salvar) {
  nome.trim();
  nome.toUpperCase();
  decode_type_t protocolo = decode_type_t::UNKNOWN;
  if (nome.length() > 0 && nome != "SIMULADO") {
    protocolo = strToDecodeType(nome.c_str());
    if (!IRac::isProtocolSupported(protocolo)) {
      Serial.println("[IR] Protocolo de ar-condicionado desconhecido: " + nome);
      return;
    }
  }
  if (salvar) {
    preferencias.begin("movement", false);
    preferencias.putString("ir_protocolo", protocolo == decode_type_t::UNKNOWN ? "SIMULADO" : nome);
    preferencias.end();
  }
  protocoloAC = protocolo;
  pulsoAtivo = false;
  digitalWrite(pinLED_IR, LOW);
  forcarEnvioIR = protocoloAC != decode_type_t::UNKNOWN;   // sincroniza o aparelho com o estado atual
  Serial.printf("[IR] Protocolo: %s\n",
                protocoloAC == decode_type_t::UNKNOWN ? "SIMULADO (pulsos no LED)" : nome.c_str());
}

// O protocolo gravado pelo comando IR vale mais que o do config.h.
void carregarProtocoloIR() {
  preferencias.begin("movement", false);
  String nome = preferencias.getString("ir_protocolo", MOVEMENT_AC_PROTOCOLO);
  preferencias.end();
  definirProtocoloIR(nome, false);
}

// Liga e desliga o aparelho em cada protocolo da lista; qualquer tecla no serial interrompe.
void testarProtocolosIR() {
  Serial.println(F("[IR] Teste: aponte o LED para o aparelho e anote o protocolo que ele obedecer."));
  for (decode_type_t protocolo : PROTOCOLOS_TESTE) {
    Serial.printf("[IR] Testando %s: ligar em 22 C, frio\n", typeToString(protocolo).c_str());
    enviarEstadoIR(protocolo, true, 22);
    for (int i = 0; i < 50; i++) {
      delay(100);
      if (Serial.available()) {
        Serial.readStringUntil('\n');
        Serial.println(F("[IR] Teste interrompido."));
        forcarEnvioIR = protocoloAC != decode_type_t::UNKNOWN;
        return;
      }
    }
    enviarEstadoIR(protocolo, false, 22);
    delay(1500);
  }
  Serial.println(F("[IR] Fim do teste. Grave o protocolo que funcionou com IR <nome>, ex.: IR GREE."));
  forcarEnvioIR = protocoloAC != decode_type_t::UNKNOWN;
}

// Sem protocolo, pisca os pulsos simulados; com protocolo, manda um quadro quando o estado muda.
void processarComandosIR() {
  if (protocoloAC == decode_type_t::UNKNOWN) { processarPulsosIR(); return; }
  if (millis() - ultimoQuadroIR < INTERVALO_MIN_IR) return;
  if (!estadoNovoParaEnviar() && !forcarEnvioIR) return;
  forcarEnvioIR = false;
  ultimoQuadroIR = millis();
  bool enviado = enviarEstadoIR(protocoloAC, ligadoEnviado, alvoEnviado);
  Serial.printf("[IR] %s: %s em %d C%s\n", typeToString(protocoloAC).c_str(),
                ligadoEnviado ? "LIGAR" : "DESLIGAR", alvoEnviado, enviado ? "" : " (falhou)");
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

// Lê as barreiras a cada 10 ms e manda cada passagem ao loop() pela fila.
void tarefaPorta(void* parametro) {
  for (;;) {
    unsigned long agora = millis();
    bool mudouA = filtrarBarreira(pinBarreiraA, barreiraA, brutaA, desdeA, agora);
    bool mudouB = filtrarBarreira(pinBarreiraB, barreiraB, brutaB, desdeB, agora);
    if (mudouA) Serial.printf("[BARREIRA] A %s\n", barreiraA == HIGH ? "cortada" : "livre");
    if (mudouB) Serial.printf("[BARREIRA] B %s\n", barreiraB == HIGH ? "cortada" : "livre");
    if (mudouA || mudouB) {
      int evento = passoPorta(barreiraA == HIGH, barreiraB == HIGH);
      if (evento != 0) xQueueSend(filaPorta, &evento, 0);
    }
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}

// ════════════════════════════════════════════════════════════════════════════
void loop() {
  unsigned long agora = millis();

  // 1) Passagens contadas pela tarefa da porta
  int evento;
  while (xQueueReceive(filaPorta, &evento, 0) == pdTRUE) {
    if (evento > 0) {
      totalPessoas++; exibirTotal("ENTRADA (+1)");
    } else if (totalPessoas > 0) {
      totalPessoas--; exibirTotal("SAIDA (-1)");
    } else {
      Serial.println(F("Aviso: sala vazia."));
      continue;
    }
    atualizarAutomatico();   // só age se estiver em AUTOMATICO
  }

  // 2) Leitura DHT
  if (agora - ultimaLeituraDHT >= intervaloDHT) {
    ultimaLeituraDHT = agora;
    lerClima();
  }

  // 3) Comando manual pelo monitor serial
  if (Serial.available()) processarComandoManual(Serial.readStringUntil('\n'));

  // 4) Timeout do modo manual
  verificarTimeoutManual();

  // 5) Plano de leitura otimizado
  if (agora - ultimaConsultaPlano >= intervaloConsultaPlano) {
    ultimaConsultaPlano = agora;
    atualizarIntervalo();
  }

  // 5b) Comando do professor e temperatura externa, pelo site
  if (agora - ultimaConsultaControle >= intervaloControle()) {
    ultimaConsultaControle = agora;
    consultarControle();
  }

  // 6) Envio da leitura para a API do Movement
  if (agora - ultimoEnvio >= intervaloEnvio) {
    ultimoEnvio = agora;
    enviarMovement();
  }

  // 7) Comando IR ao ar-condicionado
  processarComandosIR();

  delay(10);
}
