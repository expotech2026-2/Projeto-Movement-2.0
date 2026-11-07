import { useState } from "react";

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
    return `Fixado em ${control.target} °C por ${control.changed_by} até ${hour(control.expires_at)}. Depois volta ao automático.`;
  if (control.mode === "off")
    return `Desligado por ${control.changed_by} até ${hour(control.expires_at)}. Depois volta ao automático.`;
  return "O alvo segue a ocupação, o calor das pessoas e a temperatura externa, dentro da faixa da NR-17 (18 a 25 °C).";
}

export function RoomControl({ state }) {
  const { control, error, loading, send } = state;
  const [target, setTarget] = useState("22");
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

  return (
    <section className="panel chart-panel room-control">
      <div className="section-heading">
        <div>
          <h2>
            Ar-condicionado da sala
            {mode && <span className={`badge ${mode.tone}`}>{mode.label}</span>}
          </h2>
          <p className="muted">
            Professores e administradores podem fixar uma temperatura ou
            desligar. O comando vale por 2 horas. O ESP32 o recebe em até 15
            segundos com a sala ocupada, ou em até 1 minuto com ela vazia.
          </p>
        </div>
      </div>
      {loading ? (
        <p className="muted">Carregando o controle…</p>
      ) : (
        <>
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
              disabled={busy || control?.mode === "off"}
              onClick={() => run({ mode: "off" })}
            >
              Desligar
            </button>
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
