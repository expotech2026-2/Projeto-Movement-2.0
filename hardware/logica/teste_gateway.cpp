#include <cassert>
#include <cstdio>
#include <initializer_list>
#include "ir_gateway.h"

int main() {
  for (const char* url : {"http://192.168.1.150:8080/ac", "http://10.0.0.20:1821/ac",
                          "http://172.31.1.1:65535/ac"}) assert(validGatewayUrl(url));
  for (const char* url : {"", "http://127.0.0.1:8080/ac", "http://169.254.169.254:8080/ac",
                          "http://8.8.8.8:8080/ac", "http://xiaomi.local:8080/ac",
                          "https://192.168.1.1:8080/ac", "http://192.168.1.1/ac",
                          "http://192.168.1.1:80/ac", "http://192.168.1.1:65536/ac",
                          "http://192.168.1.1:8080/ac?key=x", "http://user@192.168.1.1:8080/ac",
                          "http://192.168.1.1:8080/ac#test", "http://192.168.1.1:08080/ac",
                          "http://192.168.1.1:8080/ac\n"}) assert(!validGatewayUrl(url));
  assert(validGatewayKey("test-only-key-1234567890123456"));
  assert(!validGatewayKey("short"));
  assert(!validGatewayKey("invalid-quote-key-1234567890\""));
  GatewayQueue queue;
  assert(queue.update(true, 23, false, false));
  assert(queue.ready(0));
  queue.finish(0, false);
  assert(!queue.ready(9999) && queue.ready(10000));
  assert(!queue.update(true, 23, false, false));
  queue.finish(10000, true);
  assert(!queue.ready(20000));
  assert(queue.update(true, 20, true, false));
  assert(queue.target == 20 && queue.strong);
  assert(queue.ready(20000));
  queue.finish(20000, false);
  assert(queue.update(false, 20, false, false));
  assert(!queue.ready(20001));
  assert(!queue.update(false, 25, true, false));
  assert(!queue.power && !queue.strong);
  queue.finish(0xfffffff0U, false);
  assert(queue.ready(10000U));
  assert(queue.update(false, 24, false, true));
  queue = GatewayQueue();
  assert(queue.update(false, 24, false, false) && queue.ready(0));
  std::puts("OK: gateway local, chave privada, fila, coalescencia, retry e rollover");
}
