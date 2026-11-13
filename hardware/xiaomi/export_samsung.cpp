#include <cassert>
#include <iostream>
#include <string>
#include "IRrecv.h"
#include "ir_Samsung.h"

void emit(const std::string& name, bool power, int target, bool strong, bool first) {
  IRSamsungAc ac(0);
  ac.begin();
  ac.setMode(kSamsungAcCool);
  ac.setPower(power);
  ac.setTemp(target);
  ac.setFan(strong ? kSamsungAcFanHigh : kSamsungAcFanAuto);
  ac.setSwing(false);
  ac.setSwingH(false);
  ac.setQuiet(false);
  ac.setPowerful(strong);
  ac.setDisplay(false);
  ac.setEcono(false);
  ac.setIon(false);
  ac.setClean(false);
  ac.setBeep(false);
  ac.setSleepTimer(0);
  ac.setMode(kSamsungAcCool);
  if (power) ac.sendExtended(0);
  else ac.sendOff(0);
  ac._irsend.makeDecodeResult();
  IRrecv receiver(0);
  assert(receiver.decodeSamsungAC(&ac._irsend.capture, kStartOffset, kSamsungAcExtendedBits, true));
  assert(IRSamsungAc::validChecksum(ac._irsend.capture.state, kSamsungAcExtendedStateLength));
  IRSamsungAc decoded(0);
  decoded.setRaw(ac._irsend.capture.state, kSamsungAcExtendedStateLength);
  assert(decoded.getPower() == power);
  if (power) {
    assert(decoded.getMode() == kSamsungAcCool);
    assert(decoded.getTemp() == target);
    assert(decoded.getFan() == (strong ? kSamsungAcFanTurbo : kSamsungAcFanAuto));
    assert(decoded.getPowerful() == strong);
  }
  uint64_t duration = 0;
  assert(ac._irsend.last < 4096);
  std::cout << (first ? "" : ",\n") << "  \"" << name << "\":{\"frequency\":38000,\"duty_cycle\":0.5,\"pattern\":[";
  for (uint16_t i = 0; i <= ac._irsend.last; ++i) {
    assert(ac._irsend.freq[i] == 38000 && ac._irsend.output[i] > 0);
    assert(ac._irsend.duty[i] == 50);
    duration += ac._irsend.output[i];
    std::cout << (i ? "," : "") << ac._irsend.output[i];
  }
  assert(duration < 2000000);
  std::cout << "]}";
}

int main() {
  std::cout << "{\n";
  emit("off", false, 24, false, true);
  for (int target = 16; target <= 30; ++target) {
    emit("cool_" + std::to_string(target) + "_auto", true, target, false, false);
    emit("cool_" + std::to_string(target) + "_max", true, target, true, false);
  }
  std::cout << "\n}\n";
}
