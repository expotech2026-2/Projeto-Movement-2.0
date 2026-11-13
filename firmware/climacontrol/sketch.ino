#include <vector>
// Movement 2.0 — firmware oficial do ESP32: conta as pessoas, calcula o alvo e comanda o ar
// pelo código infravermelho do fabricante (IRremoteESP8266). Bibliotecas: libraries.txt.

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
#define MOVEMENT_AC_PROTOCOLO ""   // vazio = nada é enviado até gravar o protocolo (IR_TESTE)
#endif

String movementPendingPayload;
const char* VERSAO_FIRMWARE = "2.5.2";   // aparece no diagnóstico do site

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

// ── Controle do ar: alvo da sala e ajuste do aparelho (docs/fisica.md, seção 8) ──
const float TEMP_CONFORTO_BASE      = 24.0;   // estado do aparelho antes do primeiro cálculo
const float ALVO_SALA_BASE          = 22.0;   // ajustado pelo dia lá fora, pela umidade e pela lotação
const float ALVO_SALA_MIN           = 20.0;   // faixa da equipe, dentro da NR-17 (18 a 25 °C)
const float ALVO_SALA_MAX           = 23.0;
const float TEMP_CORPO              = 36.5;   // temperatura média do corpo humano
const float CONDUTANCIA_PESSOA      = 5.6;    // W/K: 70 W de calor sensível a 24 °C, pessoa sentada
const float CALOR_COMPUTADOR        = 100.0;  // W: computador de mesa com monitor, em uso
const float PROPORCAO_LABORATORIO   = 0.8;    // computadores >= 80% da capacidade: um por aluno
const float LOTACAO_ALTA            = 0.75;   // 75% dos lugares: calor radiante dos vizinhos
const float USO_ALTO                = 0.8;    // acima de 80% da potência, o ajuste desce 1 °C
const float MARGEM_PARTIDA          = 1.0;    // sala 1 °C acima do alvo: partida forte
const float MARGEM_CHEGADA          = 0.5;    // a partida para antes do alvo para não passar do ponto
const int   AJUSTE_PARTIDA_MIN      = 18;
const unsigned long LIMITE_PARTIDA_MS     = 30UL * 60UL * 1000UL;   // depois disso, falta potência
const unsigned long INTERVALO_CORRECAO_MS = 5UL * 60UL * 1000UL;    // correção pelo DHT
const float TEMP_AC_MIN             = 16.0;   // faixa do aparelho e do comando manual (professor)
const float TEMP_AC_MAX             = 30.0;
const float TOLERANCIA_AC           = 0.5;
// Números da sala que o site manda (cadastro e aparelhos ativos); zero até a primeira resposta.
float potenciaArSala = 0.0;   // W de calor sensível que os aparelhos ativos conseguem tirar
float uaSala         = 0.0;   // W/K: paredes, janela e ar que entra pela porta
float calorFixoSala  = 0.0;   // W: iluminação e sol
enum FaseAr { FASE_MANUTENCAO, FASE_PARTIDA, FASE_SEM_POTENCIA };

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
float alvoSalaAtual    = ALVO_SALA_BASE;   // o que os alunos devem sentir
float usoAr            = 0.0;              // carga para manter o alvo / potência dos aparelhos
FaseAr faseAr          = FASE_MANUTENCAO;
unsigned long inicioFase     = 0;
unsigned long ultimaCorrecao = 0;
int   correcaoAr       = 0;                // ajuste fino pelo DHT, em °C
float tempAlvoAC       = TEMP_CONFORTO_BASE;   // ajuste mandado ao aparelho
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
int capacidadeSala   = 1;            // cadastro da sala no site: pessoas e computadores
int computadoresSala = 0;

// ── Estado que o aparelho já recebeu pelo IR ───────────────────────────────
// Cada quadro leva o estado inteiro (ligado, frio, alvo, ventilação); começa desligado em 24 °C.
bool ventilacaoForte = false;   // partida forte: ventilação no máximo e turbo
bool forteEnviado  = false;
bool ligadoEnviado = false;
int  alvoEnviado   = (int)TEMP_CONFORTO_BASE;

// ── Protocolo do ar-condicionado (IRremoteESP8266) ─────────────────────────
IRac arCondicionado(pinLED_IR);
void aplicarProtocolosSite(const String& configuracao, long revisao);
long versaoProtocolosIR = -1;
String configuracaoIRSite;
bool recebeuConfiguracaoIR = false;
std::vector<decode_type_t> protocolosSala;
std::vector<int> modelosSala;
int quantidadeProtocolos = 0;
decode_type_t protocoloAC = decode_type_t::UNKNOWN;   // UNKNOWN = sem protocolo: nada é enviado
decode_type_t protocoloLocal = decode_type_t::UNKNOWN;   // IR <nome>: vale se o site não tiver nenhum
bool forcarEnvioIR = false;                           // reenvia o estado atual uma vez
bool repetirQuadroIR = false;                         // confirmação do último quadro
unsigned long ultimoQuadroIR = 0;
const unsigned long INTERVALO_MIN_IR = 1000;          // junta mudanças rápidas num só quadro
const unsigned long REPETICAO_IR_MS  = 2000;          // repete o quadro, caso o aparelho não o pegue
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

// ── Alvo da sala e ajuste do ar (modo automático) ──────────────────────────
// Calor sensível de uma pessoa: proporcional à diferença entre o corpo e o ar.
float calorPorPessoa(float tempSala) {
  return max(0.0f, CONDUTANCIA_PESSOA * (TEMP_CORPO - tempSala));
}

// Máquinas ligadas: uma a cada 2 alunos; num laboratório (computadores perto da capacidade), uma por aluno.
int maquinasLigadas(int pessoas, int computadores, int capacidade) {
  if (pessoas <= 0 || computadores <= 0) return 0;
  bool laboratorio = computadores >= PROPORCAO_LABORATORIO * capacidade;
  return min(laboratorio ? pessoas : pessoas / 2, computadores);
}

// O que os alunos devem sentir: 22 °C ajustado pelo dia lá fora, pela umidade e pela lotação.
float alvoSala(float tempExterna, float umidade, int pessoas, int maquinas, int capacidade) {
  float alvo = ALVO_SALA_BASE;
  if (tempExterna >= 30.0)      alvo += 0.5;   // menos choque térmico ao entrar e sair
  else if (tempExterna <= 22.0) alvo += 1.0;
  if (umidade > 70.0)                       alvo -= 1.0;   // ar úmido abafa
  else if (umidade > 60.0)                  alvo -= 0.5;
  else if (umidade > 0.0 && umidade < 40.0) alvo += 0.5;   // 0 = sem leitura
  if (pessoas > 0 && pessoas >= LOTACAO_ALTA * capacidade)     alvo -= 0.5;
  if (pessoas > 0 && maquinas >= PROPORCAO_LABORATORIO * pessoas) alvo -= 0.5;
  return constrain(alvo, ALVO_SALA_MIN, ALVO_SALA_MAX);
}

// Calor que o ar precisa tirar para manter a sala no alvo (W): pessoas, máquinas, sala e paredes.
float cargaTermica(int pessoas, int maquinas, float alvo, float tempExterna) {
  return pessoas * calorPorPessoa(alvo) + maquinas * CALOR_COMPUTADOR + calorFixoSala +
         uaSala * (tempExterna - alvo);
}

// Partida forte até perto do alvo, depois manutenção; 30 min sem chegar indica falta de potência.
FaseAr proximaFase(FaseAr fase, float tempSala, float alvo, unsigned long tempoNaFase) {
  bool chegou = tempSala <= alvo + MARGEM_CHEGADA;
  if (fase == FASE_MANUTENCAO) return tempSala > alvo + MARGEM_PARTIDA ? FASE_PARTIDA : fase;
  if (chegou) return FASE_MANUTENCAO;
  if (fase == FASE_PARTIDA && tempoNaFase >= LIMITE_PARTIDA_MS) return FASE_SEM_POTENCIA;
  return fase;
}

// Ajuste mandado ao aparelho: forte na partida, máximo sem potência e pelo uso na manutenção.
int ajusteAr(FaseAr fase, float alvo, float uso, int correcao) {
  int base = (int)floor(alvo);
  if (fase == FASE_PARTIDA) return max(base - 4, AJUSTE_PARTIDA_MIN);
  if (fase == FASE_SEM_POTENCIA || uso > 1.0) return base - 2;
  int ajuste = uso > USO_ALTO ? base - 1 : base;
  return constrain(ajuste + correcao, base - 2, base + 1);
}

// Correção pelo DHT a cada 5 min: sala acima do alvo baixa o ajuste 1 °C; abaixo, sobe.
int corrigirAjuste(int correcao, float tempSala, float alvo) {
  if (tempSala > alvo + MARGEM_CHEGADA) return max(correcao - 1, -2);
  if (tempSala < alvo - MARGEM_CHEGADA) return min(correcao + 1, 1);
  return correcao;
}

// Regra do circuito combinacional: F = A · not(C) · (M + B).
bool podeResfriar() {
  return modoAtual == MODO_MANUAL || totalPessoas > 0;
}

// O aparelho fica ligado com not(C) · (M + B): no automático, desliga quando a sala esvazia.
bool acDeveFicarLigado() {
  return !acForcadoOff && podeResfriar();
}

// Cada quadro IR leva o estado inteiro; devolve true quando há um estado novo a enviar.
bool estadoNovoParaEnviar() {
  bool ligar = acDeveFicarLigado();
  int alvo = (int)tempAlvoAC;
  bool forte = ligar && ventilacaoForte;
  if (ligar == ligadoEnviado && (!ligar || (alvo == alvoEnviado && forte == forteEnviado)))
    return false;
  ligadoEnviado = ligar;
  alvoEnviado = alvo;
  forteEnviado = forte;
  return true;
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

const char* nomeFase(FaseAr fase) {
  return fase == FASE_PARTIDA ? "partida forte" : fase == FASE_SEM_POTENCIA ? "sem potencia" : "manutencao";
}

// ── Modo automático: pessoas → máquinas → externa → umidade → alvo da sala → ajuste do ar ──
void atualizarAutomatico() {
  if (modoAtual != MODO_AUTOMATICO) return;
  int maquinas = maquinasLigadas(totalPessoas, computadoresSala, capacidadeSala);
  alvoSalaAtual = alvoSala(tempExternaAtual, umidInternaAtual, totalPessoas, maquinas, capacidadeSala);
  float carga = cargaTermica(totalPessoas, maquinas, alvoSalaAtual, tempExternaAtual);
  usoAr = potenciaArSala > 0 ? carga / potenciaArSala : 0.0;
  unsigned long agora = millis();
  if (totalPessoas == 0 || primeiraLeitura) {
    faseAr = FASE_MANUTENCAO;   // sala vazia (ar desligado) ou sem DHT: nada a acompanhar
    correcaoAr = 0;
    inicioFase = ultimaCorrecao = agora;
  } else {
    FaseAr nova = proximaFase(faseAr, tempInterna, alvoSalaAtual, agora - inicioFase);
    if (nova != faseAr) {
      Serial.printf("[AR] %s -> %s (sala %.1f C, alvo %.1f C)\n", nomeFase(faseAr), nomeFase(nova),
                    tempInterna, alvoSalaAtual);
      faseAr = nova;
      correcaoAr = 0;
      inicioFase = ultimaCorrecao = agora;
    } else if (faseAr == FASE_MANUTENCAO && agora - ultimaCorrecao >= INTERVALO_CORRECAO_MS) {
      ultimaCorrecao = agora;
      correcaoAr = corrigirAjuste(correcaoAr, tempInterna, alvoSalaAtual);
    }
  }
  ventilacaoForte = faseAr != FASE_MANUTENCAO;
  definirAlvoAC(ajusteAr(faseAr, alvoSalaAtual, usoAr, correcaoAr), "AUTOMATICO");
}

// Entra no modo manual pelo tempo indicado; depois volta sozinho ao automático.
void entrarManual(unsigned long duracaoMs) {
  modoAtual = MODO_MANUAL;
  ventilacaoForte = false;   // o professor escolhe o ajuste; a ventilação fica no automático
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
  int maquinas = maquinasLigadas(totalPessoas, computadoresSala, capacidadeSala);
  Serial.printf("| Pessoas:     %d  (%.0f W do corpo)\n", totalPessoas,
                totalPessoas * calorPorPessoa(alvoSalaAtual));
  Serial.printf("| Maquinas:    %d de %d ligadas  (%.0f W)\n", maquinas, computadoresSala,
                maquinas * CALOR_COMPUTADOR);
  Serial.printf("| Alvo sala:   %.1f C\n", alvoSalaAtual);
  Serial.printf("| Uso do ar:   %.0f%% de %.0f W  (%s)\n", usoAr * 100, potenciaArSala, nomeFase(faseAr));
  Serial.printf("| Ajuste ar:   %.0f C  (%s)\n", tempAlvoAC, acLigado ? "RESFRIANDO" : "espera");
  Serial.printf("| Aparelho:    %s em %d C%s (%s)\n", ligadoEnviado ? "LIGADO" : "DESLIGADO", alvoEnviado,
                forteEnviado ? ", ventilacao maxima" : "",
                protocoloAC == decode_type_t::UNKNOWN ? "sem protocolo IR" : typeToString(protocoloAC).c_str());
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
  if (protocoloAC == decode_type_t::UNKNOWN) {
    http.addHeader("X-Movement-AC", "sem protocolo IR (rode IR_TESTE)");
    return;
  }
  String ar = ligadoEnviado ? "ligado " + String(alvoEnviado) + " C" : "desligado";
  if (ligadoEnviado && modoAtual == MODO_AUTOMATICO)
    ar += String(", ") + nomeFase(faseAr) + ", sala " + String(alvoSalaAtual, 1) + " C";
  http.addHeader("X-Movement-AC", ar + ", " + typeToString(protocoloAC));
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
  if (corpo.indexOf("\"ir_protocols\":") >= 0)
    aplicarProtocolosSite(campoJson(corpo, "ir_protocols"), campoJson(corpo, "ir_revision").toInt());
  String tExt = campoJson(corpo, "temp_outside");
  externaDoSite = tExt.length() > 0;
  if (externaDoSite) {
    tempExternaAtual = tExt.toFloat();
    String hExt = campoJson(corpo, "humidity_outside");
    if (hExt.length() > 0) umidExternaAtual = hExt.toFloat();
  }
  String capacidade = campoJson(corpo, "capacity");
  if (capacidade.length() > 0) capacidadeSala = capacidade.toInt();
  String computadores = campoJson(corpo, "computers");
  if (computadores.length() > 0) computadoresSala = computadores.toInt();
  String potencia = campoJson(corpo, "ac_power_w");
  if (potencia.length() > 0) potenciaArSala = potencia.toFloat();
  String ua = campoJson(corpo, "ua_w_k");
  if (ua.length() > 0) uaSala = ua.toFloat();
  String fixo = campoJson(corpo, "fixed_heat_w");
  if (fixo.length() > 0) calorFixoSala = fixo.toFloat();
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

// ── Comando infravermelho ao ar-condicionado ───────────────────────────────
// A API envia pares PROTOCOLO:variante distintos dos aparelhos ativos da sala.
void aplicarProtocolosSite(const String& configuracao, long revisao = 0) {
  if (recebeuConfiguracaoIR && configuracao == configuracaoIRSite && revisao == versaoProtocolosIR) return;
  versaoProtocolosIR = revisao;
  recebeuConfiguracaoIR = true;
  configuracaoIRSite = configuracao;
  quantidadeProtocolos = 0;
  protocolosSala.clear();
  modelosSala.clear();
  int inicio = 0;
  while (inicio < (int)configuracao.length()) {
    int fim = configuracao.indexOf(',', inicio);
    if (fim < 0) fim = configuracao.length();
    String par = configuracao.substring(inicio, fim);
    int separador = par.indexOf(':');
    if (separador > 0) {
      decode_type_t protocolo = strToDecodeType(par.substring(0, separador).c_str());
      int modelo = par.substring(separador + 1, par.length()).toInt();
      if (IRac::isProtocolSupported(protocolo) && modelo >= 1 && modelo <= 6) {
        protocolosSala.push_back(protocolo);
        modelosSala.push_back(modelo);
        quantidadeProtocolos++;
      }
    }
    inicio = fim + 1;
  }
  protocoloAC = quantidadeProtocolos ? protocolosSala[0] : protocoloLocal;
  forcarEnvioIR = true;
  repetirQuadroIR = false;
  Serial.printf("[IR] Configuracao da sala recebida: %d protocolos\n", quantidadeProtocolos);
}

// Manda o estado inteiro (ligado em frio no alvo, ou desligado) no protocolo informado.
bool enviarEstadoIR(decode_type_t protocolo, bool ligado, int alvo, bool forte, int modelo = 0) {
  arCondicionado.next.protocol = protocolo;
  // LG e LG2 só diferem pelo modelo do controle (AKB75215403 = LG2); nos outros vale o primeiro.
  arCondicionado.next.model    = modelo > 0 ? modelo : (protocolo == decode_type_t::LG2 ? 2 : 1);
  arCondicionado.next.power    = ligado;
  arCondicionado.next.mode     = stdAc::opmode_t::kCool;
  arCondicionado.next.celsius  = true;
  arCondicionado.next.degrees  = alvo;
  // Partida forte: ventilação no máximo e turbo, nos protocolos que têm turbo.
  arCondicionado.next.fanspeed = forte ? stdAc::fanspeed_t::kMax : stdAc::fanspeed_t::kAuto;
  arCondicionado.next.turbo    = forte;
  return arCondicionado.sendAc();
}

// Escolhe o protocolo pelo nome (GREE, LG2, SAMSUNG_AC...); salvar grava na flash.
void definirProtocoloIR(String nome, bool salvar) {
  nome.trim();
  nome.toUpperCase();
  if (nome.isEmpty() || nome == "SIMULADO") {   // SIMULADO: valor gravado por firmwares antigos
    protocoloLocal = decode_type_t::UNKNOWN;
    if (!quantidadeProtocolos) protocoloAC = protocoloLocal;
    Serial.println(F("[IR] Sem protocolo do aparelho: rode IR_TESTE e grave o que funcionar com IR <nome>."));
    return;
  }
  decode_type_t protocolo = strToDecodeType(nome.c_str());
  if (!IRac::isProtocolSupported(protocolo)) {
    Serial.println("[IR] Protocolo de ar-condicionado desconhecido: " + nome);
    return;
  }
  if (salvar) {
    preferencias.begin("movement", false);
    preferencias.putString("ir_protocolo", nome);
    preferencias.end();
  }
  protocoloLocal = protocolo;
  if (!quantidadeProtocolos) protocoloAC = protocolo;
  forcarEnvioIR = true;   // sincroniza o aparelho com o estado atual
  Serial.printf("[IR] Protocolo: %s\n", nome.c_str());
  if (quantidadeProtocolos)
    Serial.println(F("[IR] O site ja define o protocolo da sala; o gravado vale quando o site nao tiver nenhum."));
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
    enviarEstadoIR(protocolo, true, 22, false);
    for (int i = 0; i < 50; i++) {
      delay(100);
      if (Serial.available()) {
        Serial.readStringUntil('\n');
        Serial.println(F("[IR] Teste interrompido."));
        forcarEnvioIR = protocoloAC != decode_type_t::UNKNOWN;
        return;
      }
    }
    enviarEstadoIR(protocolo, false, 22, false);
    delay(1500);
  }
  Serial.println(F("[IR] Fim do teste. Grave o protocolo que funcionou com IR <nome>, ex.: IR GREE."));
  forcarEnvioIR = protocoloAC != decode_type_t::UNKNOWN;
}

// Manda um quadro quando o estado muda e o repete uma vez 2 s depois; sem protocolo, só avisa.
void processarComandosIR() {
  unsigned long agora = millis();
  if (agora - ultimoQuadroIR < INTERVALO_MIN_IR) return;
  if (protocoloAC == decode_type_t::UNKNOWN) {
    if (estadoNovoParaEnviar())
      Serial.println(F("[IR] Sem protocolo do aparelho: nada enviado (rode IR_TESTE)."));
    return;
  }
  bool novo = estadoNovoParaEnviar() || forcarEnvioIR;
  bool repetir = !novo && repetirQuadroIR && agora - ultimoQuadroIR >= REPETICAO_IR_MS;
  if (!novo && !repetir) return;
  forcarEnvioIR = false;
  repetirQuadroIR = novo;
  ultimoQuadroIR = agora;
  bool enviado = false;
  if (quantidadeProtocolos > 0) {
    for (int i = 0; i < quantidadeProtocolos; i++)
      enviado = enviarEstadoIR(protocolosSala[i], ligadoEnviado, alvoEnviado, forteEnviado, modelosSala[i]) || enviado;
  } else enviado = enviarEstadoIR(protocoloAC, ligadoEnviado, alvoEnviado, forteEnviado);
  Serial.printf("[IR] %s: %s em %d C%s%s%s\n", typeToString(protocoloAC).c_str(),
                ligadoEnviado ? "LIGAR" : "DESLIGAR", alvoEnviado,
                forteEnviado ? ", ventilacao maxima" : "", repetir ? " (repeticao)" : "",
                enviado ? "" : " (falhou)");
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
