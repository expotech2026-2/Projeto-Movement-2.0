var movementstatus = 400;
var movementresponse = JSON.stringify({ accepted: false, message: "Pedido inválido" });

(function () {
  function reply(status, message, accepted) {
    movementstatus = status;
    movementresponse = JSON.stringify({ accepted: !!accepted, message: message });
  }

  try {
    var request = JSON.parse(http_request_body);
    var secret = global("MovementGatewayKey");
    if (typeof secret !== "string" || !/^[A-Za-z0-9_-]{24,128}$/.test(secret)) {
      reply(503, "Configure a chave privada no Tasker");
      return;
    }
    if (!request || request.key !== secret) {
      reply(403, "Chave inválida");
      return;
    }
    if (!/^[a-fA-F0-9-]{36}$/.test(request.id || "") ||
        typeof request.power !== "boolean" || request.mode !== "cool" ||
        !Number.isInteger(request.temperature) || request.temperature < 16 || request.temperature > 30 ||
        (request.fan !== "auto" && request.fan !== "max")) {
      reply(400, "Estado do ar inválido");
      return;
    }
    var signature = JSON.stringify([request.power, request.temperature, request.fan]);
    var previous;
    try { previous = JSON.parse(global("MovementLastCommand") || "null"); }
    catch (ignored) { previous = null; }
    if (previous && previous.id === request.id) {
      reply(previous.signature === signature ? 202 : 409,
        previous.signature === signature ? "Pedido já encaminhado" : "Identificador reutilizado",
        previous.signature === signature);
      return;
    }
    var signals;
    try { signals = JSON.parse(global("MovementSignals") || "{}"); }
    catch (ignored) { reply(422, "Mapa de sinais inválido"); return; }
    var key = request.power ? "cool_" + request.temperature + "_" + request.fan : "off";
    var signal = signals && signals[key];
    if (!signal || !Number.isInteger(signal.frequency) || signal.frequency < 10000 || signal.frequency > 100000 ||
        !Array.isArray(signal.pattern) || signal.pattern.length < 1 || signal.pattern.length > 4096) {
      reply(422, "Cadastre o sinal real: " + key);
      return;
    }
    var total = 0;
    for (var i = 0; i < signal.pattern.length; i++) {
      var duration = signal.pattern[i];
      if (!Number.isInteger(duration) || duration < 1 || duration >= 2000000) {
        reply(422, "Duração inválida no sinal: " + key);
        return;
      }
      total += duration;
    }
    var pattern = signal.pattern.join(",");
    if (total >= 2000000 || pattern.length > 32768) {
      reply(422, "Sinal excede o limite do emissor");
      return;
    }
    var now = Date.now();
    var last = Number(global("MovementLastDispatchMs") || 0);
    if (now >= last && now - last < 2500) {
      reply(429, "Aguarde o envio anterior");
      return;
    }
    var queued = sendIntent("org.irblaster.TRANSMIT", "receiver", "org.nslabs.ir_blaster",
      "org.nslabs.ir_blaster.IrAutomationReceiver", undefined, undefined, undefined,
      ["frequency:" + signal.frequency, "pattern:" + pattern]);
    if (!queued) {
      reply(503, "Falha ao encaminhar ao Android IR Blaster");
      return;
    }
    setGlobal("MovementLastCommand", JSON.stringify({ id: request.id, signature: signature }));
    setGlobal("MovementLastDispatchMs", String(now));
    reply(202, "Pedido encaminhado; confira o aparelho", true);
  } catch (ignored) {
    reply(400, "JSON inválido ou automação indisponível");
  }
})();
