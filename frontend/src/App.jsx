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
import { ThermalScale } from "./components/ThermalScale";
import { UnitsView } from "./components/UnitsView";
import { UsersView } from "./components/UsersView";
import { AC_KINDS, AC_STATUS, ROLES } from "./config/catalog";
import { useRoomControl } from "./hooks/useRoomControl";
import { useRoomFeed } from "./hooks/useRoomFeed";
import { useTheme } from "./hooks/useTheme";
import { deviceStatus } from "./services/deviceStatus";
import {
  clearSession,
  getSessionToken,
  regenerateDeviceToken,
  request,
} from "./services/movementApi";
import { chartPoints } from "./services/readings";

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
    "Painel da sala",
    "Temperatura, umidade e ocupação ao vivo, e o comando do ar-condicionado.",
  ],
  rooms: [
    "Unidades e salas",
    "Cada unidade com suas salas e o inventário de aparelhos de cada uma.",
  ],
  history: [
    "Histórico mensal",
    "As médias de cada sala mês a mês, para acompanhar a evolução do ambiente.",
  ],
  reports: [
    "Relatórios em PDF",
    "Documentos de toda a rede, de uma unidade ou de uma sala.",
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
  const [menuOpen, setMenuOpen] = useState(false);
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
  async function renewToken(device) {
    const question =
      `Gerar um novo token para ${device.id}? O token atual para de funcionar ` +
      "e o ESP32 só volta a enviar depois de gravado com o novo.";
    if (!window.confirm(question)) return;
    setBusy(true);
    try {
      setCredential(await regenerateDeviceToken(roomId, device.id));
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy(false);
    }
  }
  const navigation = [
    { id: "overview", icon: "grid", label: "Painel" },
    { id: "rooms", icon: "building", label: "Salas" },
    { id: "history", icon: "chart", label: "Histórico" },
    { id: "reports", icon: "file", label: "Relatórios" },
    ...(isAdmin ? [{ id: "users", icon: "people", label: "Usuários" }] : []),
  ];
  const roomScoped = ["overview", "rooms", "history"].includes(tab);
  const [title, subtitle] = HEADINGS[tab];
  const newRoom = () =>
    setEditing(units.length ? { type: "room" } : { type: "unit" });
  return (
    <div className="app-shell">
      <header className="site-header">
        <div className="header-inner">
          <a className="skip-link" href="#content">
            Pular para o conteúdo
          </a>
          <a className="brand" href="#content">
            <img src="/logo.svg" width={32} height={32} alt="" />
            movement
          </a>
          <button
            className="menu-toggle"
            aria-expanded={menuOpen}
            aria-controls="main-menu"
            aria-label={menuOpen ? "Fechar menu" : "Abrir menu"}
            onClick={() => setMenuOpen((open) => !open)}
          >
            <Icon name={menuOpen ? "close" : "menu"} />
          </button>
          <div
            id="main-menu"
            className={`header-menu ${menuOpen ? "open" : ""}`}
          >
            <nav aria-label="Navegação principal">
              {navigation.map((item) => (
                <button
                  key={item.id}
                  aria-current={tab === item.id ? "page" : undefined}
                  className={`nav-item ${tab === item.id ? "active" : ""}`}
                  onClick={() => {
                    setTab(item.id);
                    setNotice("");
                    setMenuOpen(false);
                  }}
                >
                  <Icon name={item.icon} size={18} />
                  {item.label}
                </button>
              ))}
            </nav>
            <div className="header-tools">
              <button
                className="theme-toggle"
                onClick={toggleTheme}
                aria-label={
                  theme === "dark" ? "Usar tema claro" : "Usar tema escuro"
                }
              >
                <Icon name={theme === "dark" ? "sun" : "moon"} size={18} />
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
              <button className="logout" onClick={onLogout}>
                <Icon name="logout" size={18} />
                Sair da conta
              </button>
            </div>
          </div>
        </div>
      </header>
      <div className="main-shell">
        <main id="content" className="content">
          <div className="page-heading">
            <div>
              <h1>{title}</h1>
              <p>{subtitle}</p>
            </div>
            {isAdmin && !loading && ["overview", "rooms"].includes(tab) && (
              <div className="heading-actions">
                <button
                  className="button secondary"
                  onClick={() => setEditing({ type: "unit" })}
                >
                  <Icon name="plus" size={18} /> Cadastrar unidade
                </button>
                <button
                  className={`button ${tab === "rooms" ? "primary" : "secondary"}`}
                  onClick={newRoom}
                >
                  <Icon name="plus" size={18} /> Cadastrar sala
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
              <span className="room-facts">
                <strong className="unit-chip">{unit?.name}</strong>
                {room?.location && <span>{room.location}</span>}
                {room && <span>Até {room.capacity} pessoas</span>}
                {room?.computers > 0 && (
                  <span>{room.computers} computadores</span>
                )}
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
                  onRenewToken={renewToken}
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
            <p>
              <strong>movement</strong> Organização hoje. Ambientes melhores
              amanhã.
            </p>
            <p>
              <span className="status-dot" /> {units.length}{" "}
              {units.length === 1 ? "unidade" : "unidades"}, {rooms.length}{" "}
              {rooms.length === 1 ? "sala" : "salas"}. Leituras detalhadas por
              30 dias e médias mensais por 12 meses.
            </p>
            <p>Atualização automática a cada 15 s</p>
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
  onRenewToken,
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
              <Icon name="plus" size={18} /> Adicionar aparelho
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
        {isAdmin &&
          (feed.devices[0] ? (
            <button
              className="button secondary"
              disabled={busy || feed.loading}
              onClick={() => onRenewToken(feed.devices[0])}
            >
              Gerar novo token
            </button>
          ) : (
            <button
              className="button secondary"
              disabled={busy || feed.loading}
              onClick={onProvision}
            >
              Cadastrar dispositivo
            </button>
          ))}
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
    () => chartPoints(feed.history, feed.updatedAt, Number(period)),
    [feed.history, feed.updatedAt, period],
  );
  const control = useRoomControl(room?.id, feed.updatedAt);
  const outside = control.control?.outside;
  const insideDetail = reading
    ? `Alvo do ar: ${number(reading.target_temp)} °C`
    : "Aguardando sensor";
  const cards = [
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
    },
    {
      icon: "people",
      label: "Ocupação atual",
      value: number(reading?.occupancy, 0),
      unit: "pessoas",
      detail: `Capacidade da sala: ${room?.capacity || "—"}`,
      meter:
        reading && room?.capacity
          ? Math.min(100, (100 * reading.occupancy) / room.capacity)
          : 0,
    },
    {
      icon: "snow",
      label: "Aparelhos cadastrados",
      value: feed.loading ? "—" : feed.appliances.length,
      unit: "unidades",
      detail: `${feed.appliances.filter((item) => item.status === "manutencao").length} em manutenção`,
    },
  ];
  return (
    <>
      <div className="room-deck">
        <section className="room-state">
          <div className="section-heading">
            <div className="heading-line">
              <h2>{room?.name}</h2>
              <span className="unit-chip">{unit?.name}</span>
              {feed.loading || feed.error ? (
                <span className="badge warning">
                  {feed.loading ? "Carregando" : "Sem conexão com a API"}
                </span>
              ) : (
                <StatusBadge device={feed.devices[0]} />
              )}
            </div>
            <span className="muted">
              {reading
                ? `Última leitura: ${new Date(reading.measured_at).toLocaleString("pt-BR")}`
                : "Aguardando primeira medição"}
            </span>
          </div>
          <ThermalScale
            inside={reading?.temp_inside}
            outside={outside?.temperature}
            target={reading?.target_temp}
            value={number(reading?.temp_inside)}
            detail={insideDetail}
          />
          <dl className="readouts">
            {cards.map((card) => (
              <div className="readout" key={card.label}>
                <dt>
                  <Icon name={card.icon} size={18} />
                  {card.label}
                </dt>
                <dd className="readout-value">
                  {card.value} <small>{card.unit}</small>
                </dd>
                {card.meter != null && (
                  <dd className="readout-meter" aria-hidden="true">
                    <span style={{ width: `${card.meter}%` }} />
                  </dd>
                )}
                <dd className="readout-detail">{card.detail}</dd>
              </div>
            ))}
          </dl>
        </section>
        {room?.id && (
          <RoomControl
            key={room?.id}
            isAdmin={isAdmin}
            state={control}
            device={feed.devices[0]}
            reading={feed.latest?.reading}
          />
        )}
      </div>
      <DeviceDiagnostics device={feed.devices[0]} />
      <section className="panel chart-panel">
        <div className="section-heading">
          <div>
            <h2>Temperatura do ambiente</h2>
            <p className="muted">
              {room?.name} · Leituras recebidas dos sensores
            </p>
          </div>
          <label className="field-inline">
            Período
            <select
              value={period}
              onChange={(event) => setPeriod(event.target.value)}
            >
              <option value="24">Últimas 24 horas</option>
              <option value="168">Últimos 7 dias</option>
              <option value="720">Últimos 30 dias</option>
            </select>
          </label>
        </div>
        {points.length ? (
          <>
            <div className="chart-legend">
              <span className="legend-inside">Interna</span>
              <span className="legend-outside">Externa</span>
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
              {isAdmin ? "Gerenciar aparelhos" : "Ver inventário"}
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
              <td data-label="Aparelho">
                <strong>{item.name}</strong>
                <small>
                  {[item.brand, item.model].filter(Boolean).join(" · ") ||
                    "Marca e modelo não informados"}
                </small>
              </td>
              <td data-label="Tipo">{AC_KINDS[item.kind]}</td>
              <td data-label="Capacidade">
                {number(item.capacity_btu, 0)} BTU/h
              </td>
              <td data-label="Tecnologia">
                {item.inverter ? "Inverter" : "Convencional"}
              </td>
              <td data-label="Situação">
                <span
                  className={`badge ${item.status === "ativo" ? "success" : "warning"}`}
                >
                  {AC_STATUS[item.status]}
                </span>
              </td>
              {isAdmin && (
                <td data-label="Ações">
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
                  <td data-label="Mês" className="capitalize">
                    {monthLabel(item.month)}
                  </td>
                  <td data-label="Temp. interna">
                    {number(item.avg_temp_inside)} °C
                  </td>
                  <td data-label="Temp. externa">
                    {number(item.avg_temp_outside)} °C
                  </td>
                  <td data-label="Umidade int.">
                    {number(item.avg_humidity_inside)}%
                  </td>
                  <td data-label="Ocupação">{number(item.avg_occupancy)}</td>
                  <td data-label="A/C ligado">{number(item.ac_on_percent)}%</td>
                  <td data-label="Amostras">{number(item.sample_count, 0)}</td>
                  <td data-label="Consolidação">
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
