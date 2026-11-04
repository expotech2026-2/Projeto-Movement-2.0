import { useState } from "react";

import { AC_KINDS, AC_STATUS } from "../config/catalog";

export function ManagementForm({ editing, onSave, onClose }) {
  const isRoom = editing.type === "room";
  const [values, setValues] = useState(() =>
    isRoom
      ? {
          name: editing.item?.name || "",
          location: editing.item?.location || "",
          capacity: editing.item?.capacity || 30,
        }
      : {
          name: "",
          kind: "split",
          brand: "",
          model: "",
          capacity_btu: 12000,
          inverter: false,
          status: "ativo",
          ...editing.item,
        },
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  function field(name, value) {
    setValues((previous) => ({ ...previous, [name]: value }));
  }
  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await onSave(values);
      onClose();
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="modal-backdrop">
      <section
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="form-title"
      >
        <div className="section-heading">
          <h2 id="form-title">
            {editing.item ? "Editar" : "Cadastrar"}{" "}
            {isRoom ? "sala" : "aparelho"}
          </h2>
          <button
            className="icon-button"
            aria-label="Fechar formulário"
            onClick={onClose}
            disabled={busy}
          >
            ×
          </button>
        </div>
        <form onSubmit={submit} className="management-form">
          <label>
            Nome
            <input
              autoFocus
              required
              maxLength={120}
              value={values.name}
              onChange={(e) => field("name", e.target.value)}
            />
          </label>
          {isRoom ? (
            <>
              <label>
                Bloco / localização
                <input
                  maxLength={120}
                  value={values.location}
                  onChange={(e) => field("location", e.target.value)}
                />
              </label>
              <label>
                Capacidade de pessoas
                <input
                  type="number"
                  min="1"
                  max="10000"
                  required
                  value={values.capacity}
                  onChange={(e) => field("capacity", Number(e.target.value))}
                />
              </label>
            </>
          ) : (
            <>
              <div className="form-grid">
                <label>
                  Tipo
                  <select
                    value={values.kind}
                    onChange={(e) => field("kind", e.target.value)}
                  >
                    {Object.entries(AC_KINDS).map(([key, label]) => (
                      <option key={key} value={key}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Capacidade (BTU/h)
                  <input
                    type="number"
                    min="1000"
                    max="500000"
                    required
                    value={values.capacity_btu}
                    onChange={(e) =>
                      field("capacity_btu", Number(e.target.value))
                    }
                  />
                </label>
              </div>
              <div className="form-grid">
                <label>
                  Marca
                  <input
                    maxLength={80}
                    value={values.brand}
                    onChange={(e) => field("brand", e.target.value)}
                  />
                </label>
                <label>
                  Modelo
                  <input
                    maxLength={80}
                    value={values.model}
                    onChange={(e) => field("model", e.target.value)}
                  />
                </label>
              </div>
              <label>
                Situação
                <select
                  value={values.status}
                  onChange={(e) => field("status", e.target.value)}
                >
                  {Object.entries(AC_STATUS).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={values.inverter}
                  onChange={(e) => field("inverter", e.target.checked)}
                />{" "}
                Tecnologia inverter
              </label>
            </>
          )}
          {error && (
            <p role="alert" className="notice error">
              {error}
            </p>
          )}
          <div className="form-actions">
            <button
              type="button"
              className="button secondary"
              onClick={onClose}
              disabled={busy}
            >
              Cancelar
            </button>
            <button className="button primary" disabled={busy}>
              {busy ? "Salvando…" : "Salvar cadastro"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
