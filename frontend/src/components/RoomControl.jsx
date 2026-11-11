import { useState } from "react";
import { acIsOn, missingIrProtocol, powerCommand } from "../services/acPower";

const MODES = {
  auto: { label: "Automático", tone: "success" },
  manual: { label: "Manual", tone: "warning" },
  off: { label: "Desligado", tone: "warning" },
};

const hour = (value) =>
  new Date(value).toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
  });

function describe(control) {
  if (control.mode === "manual")
    return `Ligado em ${control.target} °C por ${control.changed_by} até ${hour(control.expires_at)}. Depois volta ao automático.`;
  if (control.mode === "off")
    return `Desligado por ${control.changed_by} até ${hour(control.expires_at)}. Depois volta ao automático.`;
  return "A sala mira de 20 a 23 °C, conforme a temperatura externa, a umidade e a lotação. O ESP32 começa forte até chegar perto do alvo e depois ajusta o ar pela potência dos aparelhos. Com a sala vazia, o ar fica desligado.";
}

export function RoomControl({ state, device, reading }) {
  const { control, error, loading, send } = state;
  const [target, setTarget] = useState("23");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");

  async function run(command) {
    setBusy(true);
    setFailure("");
    try {
      await send(command);
    } catch (problem) {
      setFailure(problem.message);
    } finally {
      setBusy(false);
    }
  }

  function fix(event) {
    event.preventDefault();
    run({ mode: "manual", target: Number(target) });
  }

  const mode = control ? MODES[control.mode] : null;
  const message = failure || error;
  const isOn = acIsOn(control, device, reading);
  const targetValid = Number(target) >= 16 && Number(target) <= 30;

  return (
    <section className="panel chart-panel room-control">
      <div className="section-heading">
        <div>
          <h2>
            Ar-condicionado da sala
            {mode && <span className={`badge ${mode.tone}`}>{mode.label}</span>}
          </h2>
          <p className="muted">
            Professores e administradores podem ligar, desligar ou fixar uma
            temperatura. O comando vale por 2 horas. O ESP32 o recebe em até 15
            segundos com a sala ocupada, ou em até 1 minuto com ela vazia, e o
            manda ao aparelho pelo infravermelho.
          </p>
        </div>
      </div>
      {loading ? (
        <p className="muted">Carregando o controle…</p>
      ) : (
        <>
          <div className="power-row">
            <button
              type="button"
              className={`power-button ${isOn ? "on" : "off"}`}
              aria-pressed={isOn}
              disabled={busy || (!isOn && !targetValid)}
              onClick={() => run(powerCommand(isOn, Number(target)))}
            >
              <span className="power-dot" aria-hidden="true" />
              {busy ? "Enviando…" : isOn ? "Desligar o ar" : "Ligar o ar"}
            </button>
            <span className="muted">
              {isOn
                ? "O ar está ligado."
                : `O ar está desligado. Ligar fixa ${targetValid ? target : "—"} °C.`}
              {device?.ac_state && !missingIrProtocol(device)
                ? ` Último estado do ESP32: ${device.ac_state}.`
                : ""}
            </span>
          </div>
          {missingIrProtocol(device) && (
            <p className="notice error" role="alert">
              O ESP32 ainda não tem o protocolo infravermelho do aparelho, então
              os comandos não chegam ao ar. No monitor serial, rode IR_TESTE e
              grave o que funcionar com IR &lt;nome&gt;.
            </p>
          )}
          {control && <p className="control-status">{describe(control)}</p>}
          <div className="control-actions">
            <form className="control-manual" onSubmit={fix}>
              <label htmlFor="control-target">Temperatura</label>
              <input
                id="control-target"
                type="number"
                min={16}
                max={30}
                step={1}
                required
                value={target}
                onChange={(event) => setTarget(event.target.value)}
              />
              <span className="muted">°C</span>
              <button className="button primary" disabled={busy}>
                Fixar temperatura
              </button>
            </form>
            <button
              className="button secondary"
              disabled={busy || control?.mode === "auto"}
              onClick={() => run({ mode: "auto" })}
            >
              Voltar ao automático
            </button>
          </div>
          {message && (
            <p className="notice error" role="alert">
              {message}
            </p>
          )}
        </>
      )}
    </section>
  );
}
