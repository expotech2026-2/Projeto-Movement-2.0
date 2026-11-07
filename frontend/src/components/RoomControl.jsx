import { useEffect, useState } from "react";
import { roomControl, setRoomControl } from "../services/movementApi";

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
const decimal = (value) =>
  Number(value).toLocaleString("pt-BR", { maximumFractionDigits: 1 });

function describe(control) {
  if (control.mode === "manual")
    return `Fixado em ${control.target} °C por ${control.changed_by} até ${hour(control.expires_at)}. Depois volta ao automático.`;
  if (control.mode === "off")
    return `Desligado por ${control.changed_by} até ${hour(control.expires_at)}. Depois volta ao automático.`;
  return "O alvo segue a ocupação, o calor das pessoas e a temperatura externa, dentro da faixa da NR-17 (18 a 25 °C).";
}

export function RoomControl({ roomId, refresh }) {
  const [result, setResult] = useState({
    roomId: null,
    control: null,
    error: "",
  });
  const [target, setTarget] = useState("22");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    roomControl(roomId)
      .then((control) => {
        if (active) setResult({ roomId, control, error: "" });
      })
      .catch((error) => {
        if (active) setResult({ roomId, control: null, error: error.message });
      });
    return () => {
      active = false;
    };
  }, [roomId, refresh]);

  async function send(command) {
    setBusy(true);
    try {
      const control = await setRoomControl(roomId, command);
      setResult({ roomId, control, error: "" });
    } catch (error) {
      setResult((previous) => ({ ...previous, error: error.message }));
    } finally {
      setBusy(false);
    }
  }

  function fix(event) {
    event.preventDefault();
    send({ mode: "manual", target: Number(target) });
  }

  const { control, error } = result;
  const loading = result.roomId !== roomId;
  const mode = control ? MODES[control.mode] : null;

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
              onClick={() => send({ mode: "off" })}
            >
              Desligar
            </button>
            <button
              className="button secondary"
              disabled={busy || control?.mode === "auto"}
              onClick={() => send({ mode: "auto" })}
            >
              Voltar ao automático
            </button>
          </div>
          <p className="muted">
            {control?.outside
              ? `Externa agora em ${control.outside.city}: ${decimal(control.outside.temperature)} °C e ${decimal(control.outside.humidity)}% de umidade (Open-Meteo).`
              : "Sem temperatura externa: cadastre a cidade da unidade."}
          </p>
          {error && (
            <p className="notice error" role="alert">
              {error}
            </p>
          )}
        </>
      )}
    </section>
  );
}
