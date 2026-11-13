import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import test from "node:test";

const source = readFileSync(new URL("./tasker-gateway.js", import.meta.url), "utf8");
const secret = "test-only-key-1234567890123456";
const request = { id: "12345678-1234-1234-1234-123456789012", key: secret,
  power: true, temperature: 23, mode: "cool", fan: "auto" };
const signal = { frequency: 38000, pattern: [9000, 4500, 560, 560] };
const samsung = JSON.parse(readFileSync(new URL("./signals.samsung-candidate.json", import.meta.url), "utf8"));

function gateway(body = request, options = {}) {
  const variables = options.variables || {
    MovementGatewayKey: secret,
    MovementSignals: JSON.stringify({ cool_23_auto: signal, off: signal }),
  };
  const broadcasts = [];
  const sandbox = {
    http_request_body: typeof body === "string" ? body : JSON.stringify(body),
    global: (name) => variables[name],
    setGlobal: (name, value) => { variables[name] = value; },
    sendIntent: (...args) => { broadcasts.push(args); return options.queued !== false; },
  };
  runInNewContext(source, sandbox);
  return { status: sandbox.movementstatus, body: JSON.parse(sandbox.movementresponse), broadcasts, variables };
}

test("encaminha o sinal exato ao receptor explícito e não repete o mesmo pedido", () => {
  const result = gateway();
  assert.equal(result.status, 202);
  assert.equal(result.body.accepted, true);
  assert.equal(result.broadcasts[0][0], "org.irblaster.TRANSMIT");
  assert.equal(result.broadcasts[0][2], "org.nslabs.ir_blaster");
  assert.deepEqual(Array.from(result.broadcasts[0][7]), ["frequency:38000", "pattern:9000,4500,560,560"]);
  const duplicate = gateway(request, result);
  assert.equal(duplicate.status, 202);
  assert.equal(duplicate.broadcasts.length, 0);
  assert.equal(gateway({ ...request, temperature: 20 }, result).status, 409);
});

test("off usa seu próprio quadro e não um botão que alterna ligar/desligar", () => {
  const result = gateway({ ...request, power: false });
  assert.equal(result.status, 202);
});

test("os 31 sinais Samsung candidatos respeitam o contrato do gateway", () => {
  assert.equal(Object.keys(samsung).length, 31);
  for (const [name, signal] of Object.entries(samsung)) {
    const match = /^cool_(\d+)_(auto|max)$/.exec(name);
    const body = name === "off" ? { ...request, power: false } : {
      ...request, temperature: Number(match[1]), fan: match[2],
    };
    assert.equal(signal.frequency, 38000);
    assert.equal(signal.pattern.length, 350);
    assert.ok(signal.pattern.every((duration) => Number.isInteger(duration) && duration > 0));
    assert.ok(signal.pattern.reduce((sum, duration) => sum + duration, 0) < 2000000);
    const result = gateway(body, { variables: {
      MovementGatewayKey: secret, MovementSignals: JSON.stringify(samsung),
    } });
    assert.equal(result.status, 202, name);
    assert.equal(result.broadcasts[0][7][1], "pattern:" + signal.pattern.join(","));
  }
});

test("recusa chave incorreta, JSON inválido e estados sem sinal cadastrado", () => {
  for (const [body, status] of [
    [{ ...request, key: "wrong" }, 403], ["invalid-json", 400], [null, 403],
    [{ ...request, temperature: 15 }, 400], [{ ...request, power: "true" }, 400],
    [{ ...request, temperature: 20 }, 422], [{ ...request, fan: "max" }, 422],
  ]) {
    const result = gateway(body);
    assert.equal(result.status, status);
    assert.equal(result.body.accepted, false);
    assert.equal(result.broadcasts.length, 0);
  }
});

test("recusa sinais vazios, malformados ou longos sem tentar transmitir", () => {
  for (const invalid of [
    { ...signal, pattern: [] }, { ...signal, pattern: [0] },
    { ...signal, pattern: [2000000] }, { ...signal, pattern: [1000000, 1000000] },
    { ...signal, pattern: Array(4097).fill(1) }, { ...signal, frequency: 9999 },
  ]) {
    const result = gateway(request, { variables: {
      MovementGatewayKey: secret, MovementSignals: JSON.stringify({ cool_23_auto: invalid }),
    } });
    assert.equal(result.status, 422);
    assert.equal(result.broadcasts.length, 0);
  }
});

test("não confirma aceitação quando o encaminhamento falha ou há outra transmissão recente", () => {
  const failed = gateway(request, { queued: false });
  assert.equal(failed.status, 503);
  assert.equal(failed.variables.MovementLastCommand, undefined);
  const accepted = gateway();
  const busy = gateway({ ...request, id: "22345678-1234-1234-1234-123456789012" }, accepted);
  assert.equal(busy.status, 429);
  assert.equal(busy.broadcasts.length, 0);
});
