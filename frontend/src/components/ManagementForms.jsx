import { useEffect, useState } from "react";

import {
  AC_FUNCTIONS,
  AC_KINDS,
  AC_STATUS,
  CATALOG_KINDS,
  ROLES,
} from "../config/catalog";
import { findBrand, matchBrands, matchModels } from "../services/catalogMatch";
import { catalog, cities, request } from "../services/movementApi";
import { CityInput } from "./CityInput";
import { SuggestInput } from "./SuggestInput";

const TITLES = {
  unit: "unidade",
  room: "sala",
  appliance: "aparelho",
  user: "usuário",
};
const number = (value) => Number(value).toLocaleString("pt-BR");

function initialValues(editing, units) {
  if (editing.draft) return editing.draft;
  const item = editing.item;
  if (editing.type === "unit")
    return {
      name: item?.name || "",
      address: item?.address || "",
      city: item?.city || "",
    };
  if (editing.type === "room")
    return {
      unit_id: item?.unit_id || editing.unitId || units[0]?.id || "",
      name: item?.name || "",
      location: item?.location || "",
      capacity: item?.capacity || 30,
    };
  if (editing.type === "user")
    return {
      username: item?.username || "",
      full_name: item?.full_name || "",
      role: item?.role || "professor",
      active: item?.active ?? true,
      password: "",
    };
  return {
    name: "",
    kind: "split",
    brand: "",
    model: "",
    capacity_btu: 12000,
    inverter: false,
    status: "ativo",
    ...item,
  };
}

export function ManagementForm({
  editing,
  units = [],
  onSave,
  onClose,
  onNavigate,
  onChanged,
}) {
  const [values, setValues] = useState(() => initialValues(editing, units));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const update = (patch) =>
    setValues((previous) => ({ ...previous, ...patch }));
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
  const Fields = {
    unit: UnitFields,
    room: RoomFields,
    appliance: ApplianceFields,
    user: UserFields,
  }[editing.type];
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
            {editing.item ? "Editar" : "Cadastrar"} {TITLES[editing.type]}
            {editing.roomName && (
              <span className="unit-chip">{editing.roomName}</span>
            )}
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
          <Fields
            values={values}
            update={update}
            editing={editing}
            units={units}
          />
          {editing.type === "room" && editing.item && (
            <RoomAppliances
              room={editing.item}
              disabled={busy}
              onOpen={(appliance) =>
                onNavigate({
                  type: "appliance",
                  item: appliance,
                  roomId: editing.item.id,
                  roomName: editing.item.name,
                  back: { ...editing, draft: values },
                })
              }
              onChanged={onChanged}
            />
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
              {busy
                ? "Salvando…"
                : editing.type === "room" && editing.item
                  ? "Salvar sala"
                  : "Salvar cadastro"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

function UnitFields({ values, update }) {
  const [options, setOptions] = useState([]);
  useEffect(() => {
    let active = true;
    cities()
      .then((list) => {
        if (active) setOptions(list);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);
  return (
    <>
      <label>
        Nome da unidade
        <input
          autoFocus
          required
          maxLength={120}
          placeholder="Ex.: Centro, Polo Sede"
          value={values.name}
          onChange={(e) => update({ name: e.target.value })}
        />
      </label>
      <label>
        Endereço ou referência
        <input
          maxLength={160}
          value={values.address}
          onChange={(e) => update({ address: e.target.value })}
        />
      </label>
      <label>
        Cidade
        <CityInput
          value={values.city}
          cities={options}
          onChange={(city) => update({ city })}
        />
      </label>
      <p className="field-hint">
        As sugestões são os municípios do Brasil, da API do IBGE, com os de SP
        primeiro. A temperatura externa das salas vem da Open-Meteo (ou da
        OpenWeatherMap, se ela falhar) para esta cidade; sem cidade, o ESP32
        usa o sensor externo, se houver.
      </p>
    </>
  );
}

function RoomFields({ values, update, units }) {
  return (
    <>
      <label>
        Nome da sala
        <input
          autoFocus
          required
          maxLength={120}
          value={values.name}
          onChange={(e) => update({ name: e.target.value })}
        />
      </label>
      <label>
        Unidade
        <select
          required
          value={values.unit_id}
          onChange={(e) => update({ unit_id: e.target.value })}
        >
          {!units.length && (
            <option value="">Cadastre uma unidade antes</option>
          )}
          {units.map((unit) => (
            <option key={unit.id} value={unit.id}>
              {unit.name}
            </option>
          ))}
        </select>
      </label>
      <div className="form-grid">
        <label>
          Bloco / andar
          <input
            maxLength={120}
            placeholder="Ex.: Bloco B, 2º andar"
            value={values.location}
            onChange={(e) => update({ location: e.target.value })}
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
            onChange={(e) => update({ capacity: Number(e.target.value) })}
          />
        </label>
      </div>
    </>
  );
}

// Aparelhos da sala dentro do formulário dela: abrir um guarda o que já foi digitado na sala.
function RoomAppliances({ room, disabled, onOpen, onChanged }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");
  const [removing, setRemoving] = useState(false);
  const path = `/rooms/${encodeURIComponent(room.id)}/appliances`;
  useEffect(() => {
    let active = true;
    request(path)
      .then((list) => active && setItems(list))
      .catch((failure) => active && setError(failure.message));
    return () => {
      active = false;
    };
  }, [path]);
  async function remove(item) {
    if (!window.confirm(`Excluir ${item.name}? O aparelho será removido do inventário.`))
      return;
    setRemoving(true);
    setError("");
    try {
      await request(`${path}/${item.id}`, { method: "DELETE" });
      setItems((list) => list.filter((entry) => entry.id !== item.id));
      onChanged?.();
    } catch (failure) {
      setError(failure.message);
    } finally {
      setRemoving(false);
    }
  }
  return (
    <fieldset className="room-appliances">
      <legend>
        Aparelhos desta sala
        {items && <span className="count">{items.length}</span>}
      </legend>
      {items === null && !error && <p className="muted">Carregando aparelhos…</p>}
      {items?.length === 0 && (
        <p className="muted">Nenhum aparelho cadastrado nesta sala.</p>
      )}
      {items?.map((item) => (
        <div className="room-appliance" key={item.id}>
          <div>
            <strong>{item.name}</strong>
            <small>
              {[item.brand, item.model].filter(Boolean).join(" · ") ||
                "Marca e modelo não informados"}{" "}
              · {AC_KINDS[item.kind]} · {number(item.capacity_btu)} BTU/h
            </small>
          </div>
          <span
            className={`badge ${item.status === "ativo" ? "success" : "warning"}`}
          >
            {AC_STATUS[item.status]}
          </span>
          <button
            type="button"
            className="text-button"
            disabled={disabled || removing}
            onClick={() => onOpen(item)}
          >
            Editar
          </button>
          <button
            type="button"
            className="text-button danger"
            disabled={disabled || removing}
            onClick={() => remove(item)}
          >
            Excluir
          </button>
        </div>
      ))}
      {error && (
        <p role="alert" className="notice error">
          {error}
        </p>
      )}
      <button
        type="button"
        className="button secondary"
        disabled={disabled || removing || items === null}
        onClick={() => onOpen(null)}
      >
        ＋ Adicionar aparelho
      </button>
    </fieldset>
  );
}

function ApplianceFields({ values, update }) {
  const [brands, setBrands] = useState(null);
  const [models, setModels] = useState({ key: "", items: [] });
  const [catalogError, setCatalogError] = useState("");
  useEffect(() => {
    catalog("/catalog/brands")
      .then(setBrands)
      .catch((error) => {
        setBrands([]);
        setCatalogError(error.message);
      });
  }, []);
  const catalogBrand = brands ? findBrand(brands, values.brand) : undefined;
  const modelsKey = catalogBrand?.brand || "";
  useEffect(() => {
    if (!modelsKey) return;
    const params = new URLSearchParams({ brand: modelsKey, limit: "2000" });
    let active = true;
    catalog(`/catalog/models?${params}`)
      .then((items) => active && setModels({ key: modelsKey, items }))
      .catch((error) => active && setCatalogError(error.message));
    return () => {
      active = false;
    };
  }, [modelsKey]);
  const options = models.key === modelsKey ? models.items : [];
  const loadingModels = Boolean(modelsKey) && models.key !== modelsKey;
  const chosen = options.find(
    (item) => item.model === values.model && item.kind === values.kind,
  );
  const brandOptions = brands ? matchBrands(brands, values.brand) : [];
  const modelOptions = matchModels(options, values.model);
  function chooseModel(item) {
    update({
      model: item.model,
      kind: item.kind,
      capacity_btu: item.capacity_btu,
      inverter: item.inverter,
    });
  }
  return (
    <>
      <label>
        Nome do aparelho
        <input
          autoFocus
          required
          maxLength={120}
          placeholder="Ex.: A/C fundos"
          value={values.name}
          onChange={(e) => update({ name: e.target.value })}
        />
      </label>
      <div className="form-grid">
        <label>
          Tipo
          <select
            value={values.kind}
            onChange={(e) => update({ kind: e.target.value })}
          >
            {Object.entries(AC_KINDS).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Situação
          <select
            value={values.status}
            onChange={(e) => update({ status: e.target.value })}
          >
            {Object.entries(AC_STATUS).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="form-grid">
        <label>
          Marca
          <SuggestInput
            label="Marca"
            value={values.brand}
            onChange={(brand) => update({ brand })}
            options={brandOptions}
            hidden={catalogBrand?.brand === values.brand}
            onChoose={(item) =>
              update({ brand: item.brand, model: "" })
            }
            describe={(item) => ({
              key: item.brand,
              label: item.brand,
              detail: `${number(item.models)} modelos`,
            })}
            placeholder={
              brands === null ? "Carregando catálogo…" : "Comece a digitar, ex.: LG"
            }
            emptyText="Marca fora do catálogo do Inmetro: pode digitar mesmo assim"
          />
        </label>
        <label>
          Modelo
          <SuggestInput
            label="Modelo"
            value={values.model}
            onChange={(model) => update({ model })}
            options={modelOptions}
            hidden={Boolean(chosen)}
            onChoose={chooseModel}
            describe={(item) => ({
              key: item.id,
              label: item.model,
              detail: `${AC_KINDS[item.kind]} · ${number(item.capacity_btu)} BTU/h · ${
                item.inverter ? "inverter" : "convencional"
              } · ${AC_FUNCTIONS[item.function]}`,
            })}
            placeholder={
              loadingModels
                ? "Carregando modelos…"
                : modelsKey
                  ? `Modelo, evaporadora ou BTU (${number(options.length)} no Inmetro)`
                  : "Digite o modelo"
            }
            emptyText={
              modelsKey && !loadingModels
                ? `Nenhum modelo da ${modelsKey} com esse texto: pode digitar mesmo assim`
                : ""
            }
          />
        </label>
      </div>
      {chosen && (
        <p className="field-hint">
          Inmetro: classe {chosen.energy_class} · registro {chosen.registration}{" "}
          · {chosen.voltage} · {chosen.refrigerant}
          {chosen.indoor_unit && ` · evaporadora ${chosen.indoor_unit}`}
        </p>
      )}
      {!CATALOG_KINDS.includes(values.kind) && (
        <p className="field-hint">
          Para portáteis e VRF/VRV, informe o modelo manualmente.
        </p>
      )}
      {catalogError && (
        <p className="field-hint">
          Catálogo indisponível ({catalogError}); preencha manualmente.
        </p>
      )}
      <div className="form-grid">
        <label>
          Capacidade (BTU/h)
          <input
            type="number"
            min="1000"
            max="500000"
            required
            value={values.capacity_btu}
            onChange={(e) => update({ capacity_btu: Number(e.target.value) })}
          />
        </label>
        <label className="checkbox checkbox--aligned">
          <input
            type="checkbox"
            checked={values.inverter}
            onChange={(e) => update({ inverter: e.target.checked })}
          />{" "}
          Tecnologia inverter
        </label>
      </div>
    </>
  );
}

function UserFields({ values, update, editing }) {
  const creating = !editing.item;
  return (
    <>
      <label>
        Nome completo
        <input
          autoFocus
          required
          maxLength={120}
          value={values.full_name}
          onChange={(e) => update({ full_name: e.target.value })}
        />
      </label>
      <div className="form-grid">
        <label>
          Login
          <input
            required
            disabled={!creating}
            minLength={3}
            maxLength={60}
            pattern="[a-zA-Z0-9][a-zA-Z0-9._\-]{2,59}"
            title="De 3 a 60 caracteres: letras, números, ponto, hífen ou sublinhado"
            autoComplete="off"
            value={values.username}
            onChange={(e) => update({ username: e.target.value.toLowerCase() })}
          />
        </label>
        <label>
          Perfil
          <select
            value={values.role}
            onChange={(e) => update({ role: e.target.value })}
          >
            {Object.entries(ROLES).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="field-hint">
        {values.role === "admin"
          ? "Administrador: cadastra unidades, salas, aparelhos, sensores e usuários, além de consultar tudo."
          : "Professor: consulta unidades, salas, leituras, histórico e gera relatórios, sem alterar cadastros."}
      </p>
      <label>
        {creating ? "Senha inicial" : "Nova senha (opcional)"}
        <input
          type="password"
          autoComplete="new-password"
          required={creating}
          minLength={12}
          maxLength={256}
          placeholder="Mínimo de 12 caracteres"
          value={values.password}
          onChange={(e) => update({ password: e.target.value })}
        />
      </label>
      {!creating && (
        <label className="checkbox">
          <input
            type="checkbox"
            checked={values.active}
            onChange={(e) => update({ active: e.target.checked })}
          />{" "}
          Acesso ativo
        </label>
      )}
    </>
  );
}
