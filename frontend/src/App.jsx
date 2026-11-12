import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import { DeviceDiagnostics, StatusBadge } from "./components/DeviceDiagnostics";
import { Icon } from "./components/Icon";
import { ManagementForm } from "./components/ManagementForms";
import { OperatorLogin } from "./components/OperatorLogin";
import { ReportsView } from "./components/ReportsView";
import { RoomAlerts } from "./components/RoomAlerts";
import { RoomControl } from "./components/RoomControl";
import { UnitsView } from "./components/UnitsView";
import { UsersView } from "./components/UsersView";
import { AC_KINDS, AC_STATUS, ROLES } from "./config/catalog";
import { useRoomControl } from "./hooks/useRoomControl";
import { useRoomFeed } from "./hooks/useRoomFeed";
import { useTheme } from "./hooks/useTheme";
import { deviceStatus } from "./services/deviceStatus";
import { clearSession, getSessionToken, request } from "./services/movementApi";

const SensorChart = lazy(() => import("./components/SensorChart"));
const SamplingPlan = lazy(() => import("./components/SamplingPlan"));

const number = (value, decimals = 1) =>
  value == null
    ? "—"
    : Number(value).toLocaleString("pt-BR", {
        maximumFractionDigits: decimals,
      });
const monthLabel = (value) =>
  new Date(`${value}T12:00:00`).toLocaleDateString("pt-BR", {
    month: "long",
    year: "numeric",
  });
const initials = (name) =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();

function exportCsv(rows, filename) {
  if (!rows.length) return;
  const fields = Object.keys(rows[0]);
  const quote = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
  const csv = [fields, ...rows.map((row) => fields.map((field) => row[field]))]
    .map((row) => row.map(quote).join(";"))
    .join("\r\n");
  const url = URL.createObjectURL(
    new Blob(["﻿", csv], { type: "text/csv;charset=utf-8;" }),
  );
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export default function App() {
  const [session, setSession] = useState(() =>
    getSessionToken() ? { user: null } : null,
  );
  useEffect(() => {
    const expired = () => setSession(null);
    window.addEventListener("movement:session-expired", expired);
    return () =>
      window.removeEventListener("movement:session-expired", expired);
  }, []);
  useEffect(() => {
    if (!session || session.user) return;
    let active = true;
    request("/auth/me")
      .then((user) => active && setSession({ user }))
      .catch(() => {
        if (!active) return;
        clearSession();
        setSession(null);
      });
    return () => {
      active = false;
    };
  }, [session]);
  if (!session)
    return <OperatorLogin onLogin={(user) => setSession({ user })} />;
  if (!session.user)
    return <div className="boot-screen">Carregando seu acesso…</div>;
  return (
    <Workspace
      user={session.user}
      onLogout={() => {
        clearSession();
        setSession(null);
      }}
    />
  );
}

const HEADINGS = {
  overview: [
    "Cada ambiente, sob controle.",
    "Acompanhe as condições e organize a climatização dos seus espaços.",
  ],
  rooms: [
    "Unidades e salas",
    "Cada unidade com suas salas e o inventário de aparelhos de cada uma.",
  ],
  history: [
    "O clima ao longo dos meses",
    "Consulte as médias de cada sala e acompanhe a evolução do ambiente.",
  ],
  reports: [
    "Relatórios",
    "Gere documentos em PDF de toda a rede, de uma unidade ou de uma sala.",
  ],
  users: [
    "Usuários e perfis",
    "Defina quem administra os cadastros e quem apenas consulta.",
  ],
};
const REMOVAL = {
  unit: "Somente unidades sem salas podem ser excluídas.",
  room: "Salas com aparelhos, dispositivos ou histórico são preservadas.",
  appliance: "O aparelho será removido do inventário.",
};

function Workspace({ user, onLogout }) {
  const isAdmin = user.role === "admin";
  const [units, setUnits] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [roomId, setRoomId] = useState("");
  const [tab, setTab] = useState("overview");
  const [search, setSearch] = useState("");
  const [revision, setRevision] = useState(0);
  const [editing, setEditing] = useState(null);
  const [notice, setNotice] = useState("");
  const [credential, setCredential] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [theme, toggleTheme] = useTheme();
  const feed = useRoomFeed(roomId, revision);
  const ordered = useMemo(
    () =>
      units.flatMap((unit) => rooms.filter((item) => item.unit_id === unit.id)),
    [units, rooms],
  );
  const room = rooms.find((item) => item.id === roomId);
  const unit = units.find((item) => item.id === room?.unit_id);
  const applyDirectory = useCallback((unitList, roomList) => {
    const sorted = unitList.flatMap((item) =>
      roomList.filter((entry) => entry.unit_id === item.id),
    );
    setUnits(unitList);
    setRooms(roomList);
    setRoomId((current) =>
      roomList.some((item) => item.id === current)
        ? current
        : sorted[0]?.id || "",
    );
  }, []);
  const refreshDirectory = useCallback(async () => {
    const [unitList, roomList] = await Promise.all([
      request("/units"),
      request("/rooms"),
    ]);
    applyDirectory(unitList, roomList);
  }, [applyDirectory]);
  useEffect(() => {
    let active = true;
    Promise.all([request("/units"), request("/rooms")])
      .then(([unitList, roomList]) => {
        if (active) applyDirectory(unitList, roomList);
      })
      .catch((error) => {
        if (active) setNotice(error.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [applyDirectory]);
  const base = `/rooms/${encodeURIComponent(roomId)}`;
  async function save(values) {
    const { type, item } = editing;
    const method = item ? "PUT" : "POST";
    if (type === "unit") {
      await request(`/units${item ? `/${item.id}` : ""}`, {
        method,
        body: JSON.stringify({
          name: values.name,
          address: values.address,
          city: values.city,
        }),
      });
      await refreshDirectory();
    } else if (type === "room") {
      const result = await request(`/rooms${item ? `/${item.id}` : ""}`, {
        method,
        body: JSON.stringify(values),
      });
      await refreshDirectory();
      setRoomId(result.id);
    } else {
      const payload = { ...values };
      delete payload.id;
      delete payload.room_id;
      delete payload.ir_source;
      const target = `/rooms/${encodeURIComponent(editing.roomId || roomId)}`;
      await request(`${target}/appliances${item ? `/${item.id}` : ""}`, {
        method,
        body: JSON.stringify(payload),
      });
      await refreshDirectory();
    }
    setRevision((value) => value + 1);
    setNotice("Cadastro salvo com sucesso.");
  }
  async function remove(type, item) {
    if (!window.confirm(`Excluir ${item.name}? ${REMOVAL[type]}`)) return;
    setBusy(true);
    try {
      const path = {
        unit: `/units/${item.id}`,
        room: `/rooms/${item.id}`,
        appliance: `${base}/appliances/${item.id}`,
      }[type];
      await request(path, { method: "DELETE" });
      await refreshDirectory();
      setRevision((value) => value + 1);
      setNotice("Cadastro excluído.");
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy(false);
    }
  }
  async function provision() {
    setBusy(true);
    try {
      setCredential(await request(`${base}/devices`, { method: "POST" }));
      setRevision((value) => value + 1);
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy(false);
    }
  }
  const navigation = [
    { id: "overview", icon: "grid", label: "Visão geral" },
    { id: "rooms", icon: "building", label: "Unidades e salas" },
    { id: "history", icon: "chart", label: "Histórico mensal" },
    { id: "reports", icon: "file", label: "Relatórios" },
    ...(isAdmin ? [{ id: "users", icon: "people", label: "Usuários" }] : []),
  ];
  const roomScoped = ["overview", "rooms", "history"].includes(tab);
  const [title, subtitle] = HEADINGS[tab];
  const newRoom = () =>
    setEditing(units.length ? { type: "room" } : { type: "unit" });
  return (
    <div className="app-shell">
      <a className="skip-link" href="#content">
        Pular para o conteúdo
      </a>
      <aside className="sidebar">
        <a className="brand" href="#content">
          <span className="brand-symbol">
            <img src="/logo.svg" width={42} height={42} alt="" />
          </span>
          <span>
            movement<span className="brand-sub">GESTÃO DE CLIMATIZAÇÃO</span>
          </span>
        </a>
        <div className="nav-label">ESPAÇO DE TRABALHO</div>
        <nav aria-label="Navegação principal">
          {navigation.map((item) => (
            <button
              key={item.id}
              aria-current={tab === item.id ? "page" : undefined}
              className={`nav-item ${tab === item.id ? "active" : ""}`}
              onClick={() => {
                setTab(item.id);
                setNotice("");
              }}
            >
              <Icon name={item.icon} />
              {item.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <span className="status-dot" /> {units.length}{" "}
          {units.length === 1 ? "unidade" : "unidades"} · {rooms.length}{" "}
          {rooms.length === 1 ? "sala" : "salas"}
          <p>
            Dados detalhados · 30 dias
            <br />
            Médias mensais · 12 meses
          </p>
        </div>
        <button className="nav-item logout" onClick={onLogout}>
          Sair da conta <span>↗</span>
        </button>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <span>
            Ambientes <span className="separator">/</span>{" "}
            <strong>{navigation.find((item) => item.id === tab).label}</strong>
          </span>
          <span className="topbar-actions">
            <button
              className="theme-toggle"
              onClick={toggleTheme}
              aria-label={
                theme === "dark" ? "Usar tema claro" : "Usar tema escuro"
              }
            >
              <Icon name={theme === "dark" ? "sun" : "moon"} size={15} />
              <span>{theme === "dark" ? "Tema claro" : "Tema escuro"}</span>
            </button>
            <span className="account">
              <span className="avatar">{initials(user.full_name)}</span>
              <span className="account-text">
                {user.full_name}
                <small className={`role-badge role-badge--${user.role}`}>
                  {ROLES[user.role]}
                </small>
              </span>
            </span>
          </span>
        </header>
        <main id="content" className="content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">MOVEMENT 2.0</div>
              <h1>{title}</h1>
              <p>{subtitle}</p>
            </div>
            {isAdmin && !loading && ["overview", "rooms"].includes(tab) && (
              <div className="heading-actions">
                <button
                  className="button secondary"
                  onClick={() => setEditing({ type: "unit" })}
                >
                  ＋ Nova unidade
                </button>
                <button className="button primary" onClick={newRoom}>
                  ＋ Nova sala
                </button>
              </div>
            )}
          </div>
          {notice && (
            <div className="notice" role="status">
              {notice}
              <button
                aria-label="Dispensar mensagem"
                onClick={() => setNotice("")}
              >
                ×
              </button>
            </div>
          )}
          {roomScoped && feed.error && (
            <div className="notice error" role="alert">
              Falha na atualização: {feed.error}. Nova tentativa em 15 segundos.
            </div>
          )}
          {roomScoped && rooms.length > 0 && (
            <div className="room-toolbar">
              <label className="room-selector">
                <Icon name="room" /> Sala selecionada
                <select
                  aria-label="Sala selecionada"
                  value={roomId}
                  onChange={(event) => {
                    setRoomId(event.target.value);
                    setCredential(null);
                  }}
                >
                  {units.map((item) => {
                    const unitRooms = ordered.filter(
                      (entry) => entry.unit_id === item.id,
                    );
                    return unitRooms.length ? (
                      <optgroup key={item.id} label={item.name}>
                        {unitRooms.map((entry) => (
                          <option key={entry.id} value={entry.id}>
                            {entry.name}
                          </option>
                        ))}
                      </optgroup>
                    ) : null;
                  })}
                </select>
              </label>
              <span className="muted">
                <strong className="unit-chip">{unit?.name}</strong>
                {room?.location && ` · ${room.location}`}
                {room && ` · Até ${room.capacity} pessoas`}
                {room?.computers > 0 && ` · ${room.computers} computadores`}
              </span>
            </div>
          )}
          {loading ? (
            <div className="empty-state">Carregando unidades e salas…</div>
          ) : tab === "reports" ? (
            <ReportsView units={units} rooms={ordered} roomId={roomId} />
          ) : tab === "users" && isAdmin ? (
            <UsersView currentUser={user} onNotice={setNotice} />
          ) : tab === "rooms" ? (
            <>
              <UnitsView
                units={units}
                rooms={ordered}
                roomId={roomId}
                search={search}
                onSearch={setSearch}
                isAdmin={isAdmin}
                busy={busy}
                onSelect={(id) => {
                  setRoomId(id);
                  setCredential(null);
                  window.requestAnimationFrame(() =>
                    document
                      .getElementById("room-inventory")
                      ?.scrollIntoView({ behavior: "smooth", block: "start" }),
                  );
                }}
                onEdit={setEditing}
                onRemove={remove}
              />
              {room && (
                <RoomInventory
                  room={room}
                  unit={unit}
                  feed={feed}
                  isAdmin={isAdmin}
                  busy={busy}
                  credential={credential}
                  onAdd={() =>
                    setEditing({
                      type: "appliance",
                      roomId: room.id,
                      roomName: room.name,
                    })
                  }
                  onEdit={(item) =>
                    setEditing({
                      type: "appliance",
                      item,
                      roomId: room.id,
                      roomName: room.name,
                    })
                  }
                  onEditRoom={() => setEditing({ type: "room", item: room })}
                  onRemove={(item) => remove("appliance", item)}
                  onProvision={provision}
                  onDismissCredential={() => setCredential(null)}
                />
              )}
            </>
          ) : !rooms.length ? (
            <div className="empty-state">
              <Icon name="building" size={36} />
              <h2>Seu primeiro ambiente começa aqui</h2>
              <p>
                {isAdmin
                  ? "Cadastre uma unidade, como Centro ou Polo Sede, e depois as salas e os aparelhos de cada uma."
                  : "Nenhuma sala cadastrada ainda. Peça a um administrador para cadastrar unidades e salas."}
              </p>
              {isAdmin && (
                <button className="button primary" onClick={newRoom}>
                  {units.length
                    ? "Cadastrar primeira sala"
                    : "Cadastrar primeira unidade"}
                </button>
              )}
            </div>
          ) : tab === "overview" ? (
            <Overview
              feed={feed}
              room={room}
              unit={unit}
              isAdmin={isAdmin}
              onManage={() => setTab("rooms")}
            />
          ) : (
            <MonthlyHistory feed={feed} room={room} />
          )}
          <footer>
            Movement <span>Organização hoje. Ambientes melhores amanhã.</span>
            <span>Atualização automática a cada 15 s</span>
          </footer>
        </main>
      </div>
      {editing && (
        <ManagementForm
          key={`${editing.type}-${editing.item?.id || editing.unitId || "new"}-${roomId}`}
          editing={editing}
          units={units}
          onSave={save}
          onClose={() => setEditing((current) => current?.back ?? null)}
          onNavigate={setEditing}
          onChanged={() => {
            refreshDirectory().catch((error) => setNotice(error.message));
            setRevision((value) => value + 1);
          }}
        />
      )}
    </div>
  );
}

function RoomInventory({
  room,
  unit,
  feed,
  isAdmin,
  busy,
  credential,
  onAdd,
  onEdit,
  onEditRoom,
  onRemove,
  onProvision,
  onDismissCredential,
}) {
  return (
    <>
      <div className="section-heading inventory-heading" id="room-inventory">
        <div>
          <h2>
            Aparelhos · {room.name}
            <span className="unit-chip">{unit?.name}</span>
          </h2>
          <p className="muted">
            O status representa o cadastro operacional do aparelho.
          </p>
        </div>
        {isAdmin && (
          <div className="unit-actions">
            <button className="text-button" onClick={onEditRoom}>
              Editar sala
            </button>
            <button
              className="button secondary"
              disabled={feed.loading}
              onClick={onAdd}
            >
              ＋ Adicionar aparelho
            </button>
          </div>
        )}
      </div>
      <Appliances
        items={feed.appliances}
        loading={feed.loading}
        isAdmin={isAdmin}
        onEdit={onEdit}
        onRemove={onRemove}
        busy={busy}
      />
      <section className="panel device-panel">
        <div>
          <h2>Conexão com o sensor</h2>
          <p>
            {feed.devices[0]
              ? `Dispositivo vinculado: ${feed.devices[0].id} · ${deviceStatus(feed.devices[0]).label}`
              : isAdmin
                ? "Vincule um ESP32 para receber as medições desta sala."
                : "Nenhum sensor vinculado a esta sala."}
          </p>
        </div>
        {isAdmin && (
          <button
            className="button secondary"
            disabled={busy || feed.loading || Boolean(feed.devices.length)}
            onClick={onProvision}
          >
            {feed.devices.length
              ? "Dispositivo cadastrado"
              : "Cadastrar dispositivo"}
          </button>
        )}
      </section>
      {credential && (
        <div className="notice credential">
          <strong>
            Guarde a credencial do dispositivo. O token é exibido apenas agora.
          </strong>
          <p>ID: {credential.id}</p>
          <label>
            Token
            <input
              readOnly
              value={credential.token}
              onFocus={(event) => event.target.select()}
            />
          </label>
          <button className="button secondary" onClick={onDismissCredential}>
            Já guardei
          </button>
        </div>
      )}
    </>
  );
}

function Overview({ feed, room, unit, isAdmin, onManage }) {
  const [period, setPeriod] = useState("24");
  const reading = feed.latest?.reading;
  const points = useMemo(
    () =>
      feed.history
        .filter(
          (item) =>
            Date.parse(item.measured_at) >=
            feed.updatedAt - Number(period) * 3600000,
        )
        .map((item) => ({
          ...item,
          time: new Date(item.measured_at).toLocaleString("pt-BR", {
            day: "2-digit",
            month: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
          }),
        })),
    [feed.history, feed.updatedAt, period],
  );
  const control = useRoomControl(room?.id, feed.updatedAt);
  const outside = control.control?.outside;
  const cards = [
    {
      icon: "temp",
      label: "Temperatura interna",
      value: number(reading?.temp_inside),
      unit: "°C",
      detail: reading
        ? `Alvo do ar: ${number(reading.target_temp)} °C`
        : "Aguardando sensor",
      color: "amber",
    },
    {
      icon: "sun",
      label: "Temperatura externa",
      value: number(outside?.temperature),
      unit: "°C",
      detail: outside
        ? `${outside.city} · ${outside.source}`
        : control.loading
          ? "Consultando o clima…"
          : "Cadastre a cidade da unidade",
      color: "amber",
    },
    {
      icon: "drop",
      label: "Umidade relativa",
      value: number(reading?.humidity_inside),
      unit: "%",
      detail: outside
        ? `Externa: ${number(outside.humidity, 0)}%`
        : reading
          ? `Externa: ${number(reading.humidity_outside)}%`
          : "Aguardando sensor",
      color: "blue",
    },
    {
      icon: "people",
      label: "Ocupação atual",
      value: number(reading?.occupancy, 0),
      unit: "pessoas",
      detail: `Capacidade da sala: ${room?.capacity || "—"}`,
      color: "violet",
    },
    {
      icon: "snow",
      label: "Aparelhos cadastrados",
      value: feed.loading ? "—" : feed.appliances.length,
      unit: "unidades",
      detail: `${feed.appliances.filter((item) => item.status === "manutencao").length} em manutenção`,
      color: "teal",
    },
  ];
  return (
    <>
      <div className="section-heading">
        <h2>
          {room?.name}
          <span className="unit-chip">{unit?.name}</span>
          {feed.loading || feed.error ? (
            <span className="badge warning">
              {feed.loading ? "Carregando" : "Sem conexão com a API"}
            </span>
          ) : (
            <StatusBadge device={feed.devices[0]} />
          )}
        </h2>
        <span className="muted">
          {reading
            ? `Última leitura: ${new Date(reading.measured_at).toLocaleString("pt-BR")}`
            : "Aguardando primeira medição"}
        </span>
      </div>
      <div className="metric-grid">
        {cards.map((card) => (
          <article className="metric-card" key={card.label}>
            <div className="metric-top">
              <span>{card.label}</span>
              <span className={`metric-icon ${card.color}`}>
                <Icon name={card.icon} />
              </span>
            </div>
            <div className="metric-value">
              {card.value} <small>{card.unit}</small>
            </div>
            <p>{card.detail}</p>
          </article>
        ))}
      </div>
      {room?.id && (
        <RoomControl
          key={room?.id}
          isAdmin={isAdmin}
          state={control}
          device={feed.devices[0]}
          reading={feed.latest?.reading}
        />
      )}
      <DeviceDiagnostics device={feed.devices[0]} />
      <section className="panel chart-panel">
        <div className="section-heading">
          <div>
            <h2>Temperatura do ambiente</h2>
            <p className="muted">
              {room?.name} · Leituras recebidas dos sensores
            </p>
          </div>
          <select
            aria-label="Período do gráfico"
            value={period}
            onChange={(event) => setPeriod(event.target.value)}
          >
            <option value="24">Últimas 24 horas</option>
            <option value="168">Últimos 7 dias</option>
            <option value="720">Últimos 30 dias</option>
          </select>
        </div>
        {points.length ? (
          <>
            <div className="chart-legend">
              <span>● Interna</span>
              <span>● Externa</span>
            </div>
            <div className="chart">
              <Suspense fallback={<p className="muted">Carregando gráfico…</p>}>
                <SensorChart points={points} />
              </Suspense>
            </div>
            <p className="chart-note">
              Até 2.000 leituras mais recentes. Use a API para consultas
              detalhadas.
            </p>
          </>
        ) : (
          <div className="chart-empty">
            <Icon name="chart" size={40} />
            <h3>
              {feed.loading
                ? "Carregando medições…"
                : "O gráfico começa com a primeira leitura"}
            </h3>
            <p>As medições desta sala aparecerão aqui automaticamente.</p>
          </div>
        )}
      </section>
      {room?.id && (
        <Suspense
          fallback={<p className="muted">Carregando plano de leitura…</p>}
        >
          <SamplingPlan roomId={room.id} />
        </Suspense>
      )}
      {room?.id && <RoomAlerts roomId={room.id} refresh={feed.updatedAt} />}
      <div className="overview-bottom">
        <section className="panel">
          <div className="section-heading">
            <h2>Inventário da sala</h2>
            <button className="text-button" onClick={onManage}>
              {isAdmin ? "Gerenciar →" : "Ver inventário →"}
            </button>
          </div>
          {feed.appliances.length ? (
            feed.appliances.map((item) => (
              <div className="appliance-summary" key={item.id}>
                <span className="tile-icon">
                  <Icon name="snow" />
                </span>
                <div>
                  <strong>{item.name}</strong>
                  <small>
                    {[AC_KINDS[item.kind], item.brand, item.model]
                      .filter(Boolean)
                      .join(" · ")}{" "}
                    · {number(item.capacity_btu, 0)} BTU/h
                    {item.inverter ? " · Inverter" : ""}
                  </small>
                </div>
                <span
                  className={`badge ${item.status === "ativo" ? "success" : "warning"}`}
                >
                  {AC_STATUS[item.status]}
                </span>
              </div>
            ))
          ) : (
            <p className="muted">Nenhum aparelho cadastrado nesta sala.</p>
          )}
        </section>
        <section className="retention-card">
          <span className="eyebrow">HISTÓRICO ORGANIZADO</span>
          <h2>
            Os dados certos,
            <br />
            pelo tempo certo.
          </h2>
          <div>
            <strong>
              30 <small>dias</small>
            </strong>
            <span>de leituras detalhadas</span>
          </div>
          <div>
            <strong>
              12 <small>meses</small>
            </strong>
            <span>de médias mensais</span>
          </div>
          <p>
            Uma média por sala e mês, com temperatura, umidade, ocupação e
            estado do A/C.
          </p>
        </section>
      </div>
    </>
  );
}

function Appliances({ items, loading, isAdmin, onEdit, onRemove, busy }) {
  if (loading) return <div className="empty-state">Carregando aparelhos…</div>;
  if (!items.length)
    return (
      <div className="empty-state">
        <Icon name="snow" size={32} />
        <h3>Nenhum aparelho nesta sala</h3>
        <p>
          {isAdmin
            ? "Adicione os equipamentos escolhendo marca e modelo do catálogo do Inmetro."
            : "Os aparelhos cadastrados pelos administradores aparecerão aqui."}
        </p>
      </div>
    );
  return (
    <div className="table-wrap panel">
      <table>
        <thead>
          <tr>
            <th>Aparelho</th>
            <th>Tipo</th>
            <th>Capacidade</th>
            <th>Tecnologia</th>
            <th>Situação</th>
            {isAdmin && <th>Ações</th>}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                <strong>{item.name}</strong>
                <small>
                  {[item.brand, item.model].filter(Boolean).join(" · ") ||
                    "Marca e modelo não informados"}
                </small>
              </td>
              <td>{AC_KINDS[item.kind]}</td>
              <td>{number(item.capacity_btu, 0)} BTU/h</td>
              <td>{item.inverter ? "Inverter" : "Convencional"}</td>
              <td>
                <span
                  className={`badge ${item.status === "ativo" ? "success" : "warning"}`}
                >
                  {AC_STATUS[item.status]}
                </span>
              </td>
              {isAdmin && (
                <td>
                  <button className="text-button" onClick={() => onEdit(item)}>
                    Editar
                  </button>
                  <button
                    className="text-button danger"
                    disabled={busy}
                    onClick={() => onRemove(item)}
                  >
                    Excluir
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MonthlyHistory({ feed, room }) {
  return (
    <>
      <div className="notice info">
        Médias por amostra, separadas por sala e mês civil. Meses ainda dentro
        da janela de 30 dias aparecem como parciais. Cada mês concluído é
        mantido por 12 meses após seu encerramento.
      </div>
      <div className="section-heading">
        <h2>{room?.name} · Médias mensais</h2>
        <button
          className="button secondary"
          disabled={!feed.monthly.length}
          onClick={() =>
            exportCsv(feed.monthly, `movement-${room?.id}-medias.csv`)
          }
        >
          <Icon name="arrow" size={16} /> Exportar CSV
        </button>
      </div>
      {!feed.monthly.length ? (
        <div className="empty-state">
          <Icon name="chart" size={36} />
          <h2>
            {feed.loading
              ? "Carregando histórico…"
              : "Ainda não há médias para esta sala"}
          </h2>
          <p>O histórico será formado a partir das medições recebidas.</p>
        </div>
      ) : (
        <div className="table-wrap panel">
          <table>
            <thead>
              <tr>
                <th>Mês</th>
                <th>Temp. interna</th>
                <th>Temp. externa</th>
                <th>Umidade int.</th>
                <th>Ocupação</th>
                <th>A/C ligado</th>
                <th>Amostras</th>
                <th>Consolidação</th>
              </tr>
            </thead>
            <tbody>
              {feed.monthly.map((item) => (
                <tr key={item.month}>
                  <td className="capitalize">{monthLabel(item.month)}</td>
                  <td>{number(item.avg_temp_inside)} °C</td>
                  <td>{number(item.avg_temp_outside)} °C</td>
                  <td>{number(item.avg_humidity_inside)}%</td>
                  <td>{number(item.avg_occupancy)}</td>
                  <td>{number(item.ac_on_percent)}%</td>
                  <td>{number(item.sample_count, 0)}</td>
                  <td>
                    <span
                      className={`badge ${item.finalized ? "success" : "warning"}`}
                    >
                      {item.finalized ? "Concluída" : "Parcial"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="muted">
        “A/C ligado” é o percentual de amostras com estado ligado informado pelo
        sensor da sala; não representa consumo de energia nem medição individual
        dos aparelhos.
      </p>
    </>
  );
}
