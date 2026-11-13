import { useEffect, useState } from "react";
import { roomAlerts } from "../services/movementApi";
import { Icon } from "./Icon";

const KINDS = {
  conforto: { label: "Conforto", icon: "temp", tone: "heat" },
  umidade: { label: "Umidade", icon: "drop", tone: "cold" },
};

export function RoomAlerts({ roomId, refresh }) {
  const [result, setResult] = useState({
    roomId: null,
    alerts: [],
    error: "",
  });

  useEffect(() => {
    let active = true;
    roomAlerts(roomId)
      .then((alerts) => {
        if (active) setResult({ roomId, alerts, error: "" });
      })
      .catch((error) => {
        if (active) setResult({ roomId, alerts: [], error: error.message });
      });
    return () => {
      active = false;
    };
  }, [roomId, refresh]);

  const { alerts, error } = result;
  // Mostra "carregando" só ao trocar de sala; nas atualizações a lista anterior fica visível.
  const loading = result.roomId !== roomId;

  return (
    <section className="panel chart-panel">
      <div className="section-heading">
        <div>
          <h2>Alertas recentes</h2>
          <p className="muted">
            Gerados pelas leituras do sensor: sala ocupada acima de 28 °C ou
            umidade acima de 70%
          </p>
        </div>
      </div>
      {loading ? (
        <p className="muted">Carregando alertas…</p>
      ) : error ? (
        <p className="notice error">{error}</p>
      ) : alerts.length ? (
        alerts.map((alert) => {
          const kind = KINDS[alert.kind] || KINDS.conforto;
          return (
            <div className="appliance-summary" key={alert.id}>
              <span className={`metric-icon ${kind.tone}`}>
                <Icon name={kind.icon} />
              </span>
              <div>
                <strong>{alert.message}</strong>
                <small>
                  {new Date(alert.created_at).toLocaleString("pt-BR")}
                </small>
              </div>
              <span className="badge warning">{kind.label}</span>
            </div>
          );
        })
      ) : (
        <p className="muted">Nenhum alerta recente.</p>
      )}
    </section>
  );
}
