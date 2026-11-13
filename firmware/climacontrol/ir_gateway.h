#pragma once
#include <cstdint>
#include <cstdio>
#include <cstring>

inline bool validGatewayUrl(const char* value) {
  unsigned a, b, c, d, port;
  int length = 0;
  if (std::sscanf(value, "http://%u.%u.%u.%u:%u/ac%n", &a, &b, &c, &d, &port, &length) != 5 ||
      length == 0 || value[length] != '\0' || a > 255 || b > 255 || c > 255 || d > 255 ||
      port < 1024 || port > 65535) return false;
  if (!(a == 10 || (a == 172 && b >= 16 && b <= 31) || (a == 192 && b == 168))) return false;
  char canonical[100];
  std::snprintf(canonical, sizeof(canonical), "http://%u.%u.%u.%u:%u/ac", a, b, c, d, port);
  return std::strcmp(value, canonical) == 0;
}

inline bool validGatewayKey(const char* key) {
  size_t length = std::strlen(key);
  if (length < 24 || length > 128) return false;
  for (size_t i = 0; i < length; ++i) {
    char c = key[i];
    if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
          (c >= '0' && c <= '9') || c == '-' || c == '_')) return false;
  }
  return true;
}

struct GatewayQueue {
  bool initialized = false, pending = true, attempted = false;
  bool power = false, strong = false;
  int target = 24;
  uint32_t lastAttempt = 0;

  bool update(bool nextPower, int nextTarget, bool nextStrong, bool force) {
    nextStrong = nextPower && nextStrong;
    if (initialized && !force && power == nextPower &&
        (!nextPower || (target == nextTarget && strong == nextStrong))) return false;
    initialized = true;
    pending = true;
    power = nextPower;
    target = nextTarget;
    strong = nextStrong;
    return true;
  }

  bool ready(uint32_t now) const {
    return pending && (!attempted || uint32_t(now - lastAttempt) >= 10000U);
  }

  void finish(uint32_t now, bool accepted) {
    attempted = true;
    lastAttempt = now;
    pending = !accepted;
  }
};
