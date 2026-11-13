import React, { useState } from "react";

export function IrTransport({ configuration, isAdmin, save }) {
  const [transport, setTransport] = useState(configuration.transport);
  const [url, setUrl] = useState(configuration.gateway_url);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    setError("");
    try {
      await save({ transport, gateway_url: transport === "xiaomi" ? url : "" });
      setMessage(
        "Escolha salva. Aguarde o próximo contato do ESP32 e confira o diagnóstico abaixo.",
      );
    } catch (problem) {
      setError(problem.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="ir-transport">
      <h3>Emissor infravermelho</h3>
      <p className="muted">
        {configuration.revision === 0
          ? "Nenhuma escolha enviada pelo site. Vale a configuração do Arduino."
          : `Escolha do site: ${configuration.transport === "xiaomi" ? "celular Xiaomi (POCO F7)" : "LED do ESP32"}. Confira no diagnóstico se o dispositivo já aplicou.`}
      </p>
      {isAdmin ? (
        <form onSubmit={submit} className="control-actions">
          <label>
            Enviar os comandos pelo
            <select
              value={transport}
              disabled={busy}
              onChange={(event) => setTransport(event.target.value)}
            >
              <option value="esp32">LED infravermelho do ESP32</option>
              <option value="xiaomi">Celular Xiaomi (POCO F7)</option>
            </select>
          </label>
          {transport === "xiaomi" && (
            <label>
              Endereço do Tasker no Wi-Fi da sala
              <input
                type="url"
                required
                maxLength={100}
                placeholder="http://192.168.1.150:8080/ac"
                value={url}
                disabled={busy}
                onChange={(event) => setUrl(event.target.value)}
              />
            </label>
          )}
          <button className="button secondary" disabled={busy}>
            {busy ? "Salvando…" : "Salvar emissor"}
          </button>
        </form>
      ) : (
        <p className="muted">
          Um administrador pode trocar o emissor desta sala.
        </p>
      )}
      {transport === "xiaomi" && (
        <p className="notice">
          Requer Tasker e Android IR Blaster configurados no celular, com os
          sinais reais do ar e o firmware 2.6.0 ou mais recente no ESP32. O
          celular deve ficar na mesma rede do ESP32 e apontado para o aparelho.
          O navegador sozinho não transmite infravermelho. A aceitação do pedido
          pelo celular não confirma que o ar recebeu o sinal. Se o celular
          falhar, o ESP32 não usa o LED automaticamente.
        </p>
      )}
      {message && (
        <p className="notice" role="status">
          {message}
        </p>
      )}
      {error && (
        <p className="notice error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
