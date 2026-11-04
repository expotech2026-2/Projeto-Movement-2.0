import { useEffect, useState } from "react";

import { catalog, fetchReport } from "../services/movementApi";

const formatDate = (value) =>
  value ? new Date(`${value}T12:00:00`).toLocaleDateString("pt-BR") : "—";

function saveFile({ blob, filename }) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function ReportsView({ units, rooms, roomId }) {
  const [scope, setScope] = useState(() => (roomId ? `room:${roomId}` : "all"));
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState(null);
  const [info, setInfo] = useState(null);
  useEffect(() => {
    catalog("/catalog")
      .then(setInfo)
      .catch(() => setInfo(null));
  }, []);
  async function generate() {
    const [kind, id] = scope.split(":");
    setBusy(true);
    setStatus(null);
    try {
      const file = await fetchReport(
        kind === "unit"
          ? { unit_id: id }
          : kind === "room"
            ? { room_id: id }
            : {},
      );
      saveFile(file);
      setStatus({ ok: true, text: `Relatório ${file.filename} gerado.` });
    } catch (error) {
      setStatus({ ok: false, text: error.message });
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="reports-grid">
      <section className="panel report-panel">
        <h2>Relatório em PDF</h2>
        <p className="muted">
          Escolha a abrangência e gere um documento pronto para imprimir ou
          compartilhar.
        </p>
        <label className="report-scope">
          Abrangência
          <select value={scope} onChange={(e) => setScope(e.target.value)}>
            <option value="all">Todas as unidades</option>
            <optgroup label="Unidade completa">
              {units.map((unit) => (
                <option key={unit.id} value={`unit:${unit.id}`}>
                  {unit.name} ({unit.room_count}{" "}
                  {unit.room_count === 1 ? "sala" : "salas"})
                </option>
              ))}
            </optgroup>
            {units.map((unit) => {
              const unitRooms = rooms.filter(
                (room) => room.unit_id === unit.id,
              );
              return unitRooms.length ? (
                <optgroup key={unit.id} label={`Salas · ${unit.name}`}>
                  {unitRooms.map((room) => (
                    <option key={room.id} value={`room:${room.id}`}>
                      {room.name}
                    </option>
                  ))}
                </optgroup>
              ) : null;
            })}
          </select>
        </label>
        <button className="button primary" disabled={busy} onClick={generate}>
          {busy ? "Gerando relatório…" : "Gerar relatório PDF"}
        </button>
        {status && (
          <p
            className={`notice ${status.ok ? "" : "error"}`}
            role={status.ok ? "status" : "alert"}
          >
            {status.text}
          </p>
        )}
      </section>
      <section className="panel report-panel">
        <h2>O que o relatório traz</h2>
        <ul className="report-list">
          <li>Resumo com unidades, salas, aparelhos e capacidade instalada.</li>
          <li>Por unidade: cada sala com bloco/andar, capacidade e sensor.</li>
          <li>
            Condições atuais: última leitura de temperatura, umidade, ocupação e
            A/C.
          </li>
          <li>
            Inventário com marca, modelo, BTU/h, tecnologia e classe Inmetro.
          </li>
          <li>Médias mensais dos últimos 12 meses.</li>
        </ul>
        <p className="muted">
          {info
            ? `Catálogo Inmetro: ${info.models.toLocaleString("pt-BR")} modelos de ${info.brands} marcas, tabela de ${formatDate(info.updated_at)}.`
            : "Catálogo Inmetro indisponível no momento."}
        </p>
      </section>
    </div>
  );
}
