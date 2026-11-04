import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import { OperatorLogin } from "./components/OperatorLogin";
import { ManagementForm } from "./components/ManagementForms";
import { AC_KINDS, AC_STATUS } from "./config/catalog";
import { useRoomFeed } from "./hooks/useRoomFeed";
import { clearSession, getSessionToken, request } from "./services/movementApi";

const SensorChart = lazy(() => import("./components/SensorChart"));

function Icon({ name, size = 20 }) {
  const paths = {
    grid: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
    room: "M4 21V3h12v18 M16 8h4v13 M1 21h22 M12 11v2",
    snow: "M12 2v20 M3.34 7l17.32 10 M3.34 17L20.66 7 M8 4l4 4 4-4 M8 20l4-4 4 4",
    chart: "M3 3v18h18 M7 15l4-5 4 3 5-8",
    temp: "M9 14V5a3 3 0 016 0v9a5 5 0 11-6 0 M12 8v10",
    drop: "M12 2C9 7 5 11 5 15a7 7 0 0014 0c0-4-4-8-7-13z",
    people:
      "M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2 M9 11a4 4 0 100-8 4 4 0 000 8 M22 21v-2a4 4 0 00-3-3.87 M16 3.13a4 4 0 010 7.75",
    arrow: "M12 5v14 M5 12l7 7 7-7",
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[name] || paths.snow} />
    </svg>
  );
}

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

function exportCsv(rows, filename) {
  if (!rows.length) return;
  const fields = Object.keys(rows[0]);
  const quote = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
  const csv = [fields, ...rows.map((row) => fields.map((field) => row[field]))]
    .map((row) => row.map(quote).join(";"))
    .join("\r\n");
  const url = URL.createObjectURL(
    new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8;" }),
  );
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export default function App() {
  const [authenticated, setAuthenticated] = useState(() =>
    Boolean(getSessionToken()),
  );
  useEffect(() => {
    const expired = () => setAuthenticated(false);
    window.addEventListener("movement:session-expired", expired);
    return () =>
      window.removeEventListener("movement:session-expired", expired);
  }, []);
  if (!authenticated)
    return <OperatorLogin onLogin={() => setAuthenticated(true)} />;
  return (
    <Workspace
      onLogout={() => {
        clearSession();
        setAuthenticated(false);
      }}
    />
  );
}

function Workspace({ onLogout }) {
  const [rooms, setRooms] = useState([]);
  const [roomId, setRoomId] = useState("");
  const [tab, setTab] = useState("overview");
  const [search, setSearch] = useState("");
  const [revision, setRevision] = useState(0);
  const [editing, setEditing] = useState(null);
  const [notice, setNotice] = useState("");
  const [credential, setCredential] = useState(null);
  const [roomsLoading, setRoomsLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const feed = useRoomFeed(roomId, revision);
  const room = rooms.find((item) => item.id === roomId);
  const refreshRooms = useCallback(async () => {
    const result = await request("/rooms");
    setRooms(result);
    setRoomId((current) =>
      result.some((item) => item.id === current)
        ? current
        : result[0]?.id || "",
    );
  }, []);
  useEffect(() => {
    let active = true;
    request("/rooms")
      .then((result) => {
        if (active) {
          setRooms(result);
          setRoomId(result[0]?.id || "");
        }
      })
      .catch((error) => {
        if (active) setNotice(error.message);
      })
      .finally(() => {
        if (active) setRoomsLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  const selectedRooms = rooms.filter((item) =>
    `${item.name} ${item.location}`
      .toLocaleLowerCase()
      .includes(search.toLocaleLowerCase()),
  );
  const base = `/rooms/${encodeURIComponent(roomId)}`;
  async function save(values) {
    const isRoom = editing.type === "room";
    const path = isRoom
      ? `/rooms${editing.item ? `/${editing.item.id}` : ""}`
      : `${base}/appliances${editing.item ? `/${editing.item.id}` : ""}`;
    const payload = { ...values };
    delete payload.id;
    delete payload.room_id;
    const result = await request(path, {
      method: editing.item ? "PUT" : "POST",
      body: JSON.stringify(payload),
    });
    if (isRoom) {
      await refreshRooms();
      setRoomId(result.id);
    }
    setRevision((value) => value + 1);
    setNotice("Cadastro salvo com sucesso.");
  }
  async function remove(type, item) {
    if (
      !window.confirm(
        `Excluir ${item.name}? ${type === "room" ? "Salas com aparelhos, dispositivos ou histórico são preservadas." : "O aparelho será removido do inventário."}`,
      )
    )
      return;
    setBusy(true);
    try {
      await request(
        type === "room" ? `/rooms/${item.id}` : `${base}/appliances/${item.id}`,
        { method: "DELETE" },
      );
      if (type === "room") await refreshRooms();
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
    { id: "rooms", icon: "room", label: "Salas e aparelhos" },
    { id: "history", icon: "chart", label: "Histórico mensal" },
  ];
  return (
    <div className="app-shell">
      <a className="skip-link" href="#content">
        Pular para o conteúdo
      </a>
      <aside className="sidebar">
        <a className="brand" href="#content">
          <span className="brand-symbol">
            <Icon name="snow" size={26} />
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
              onClick={() => setTab(item.id)}
            >
              <Icon name={item.icon} />
              {item.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <span className="status-dot" /> Monitoramento por sala
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
          <span className="account">
            <span className="avatar">OP</span> Operador
          </span>
        </header>
        <main id="content" className="content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">MOVEMENT 2.0</div>
              <h1>
                {tab === "overview"
                  ? "Cada ambiente, sob controle."
                  : tab === "rooms"
                    ? "Salas e aparelhos"
                    : "O clima ao longo dos meses"}
              </h1>
              <p>
                {tab === "overview"
                  ? "Acompanhe as condições e organize a climatização dos seus espaços."
                  : tab === "rooms"
                    ? "Um inventário organizado para cada ambiente."
                    : "Consulte as médias de cada sala e acompanhe a evolução do ambiente."}
              </p>
            </div>
            <button
              className="button primary"
              onClick={() => setEditing({ type: "room" })}
            >
              ＋ Nova sala
            </button>
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
          {feed.error && (
            <div className="notice error" role="alert">
              Falha na atualização: {feed.error}. Nova tentativa em 15 segundos.
            </div>
          )}
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
                {!rooms.length && (
                  <option value="">Nenhuma sala cadastrada</option>
                )}
                {rooms.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <span className="muted">
              {room?.location || "Localização não informada"}
              {room && ` · Até ${room.capacity} pessoas`}
            </span>
          </div>
          {roomsLoading ? (
            <div className="empty-state">Carregando salas…</div>
          ) : !rooms.length ? (
            <div className="empty-state">
              <Icon name="room" size={36} />
              <h2>Seu primeiro ambiente começa aqui</h2>
              <p>
                Cadastre uma sala e adicione os aparelhos de ar-condicionado.
              </p>
              <button
                className="button primary"
                onClick={() => setEditing({ type: "room" })}
              >
                Cadastrar primeira sala
              </button>
            </div>
          ) : (
            <>
              {tab === "overview" && (
                <Overview
                  feed={feed}
                  room={room}
                  onManage={() => setTab("rooms")}
                />
              )}
              {tab === "rooms" && (
                <>
                  <div className="section-heading">
                    <h2>
                      Seus ambientes{" "}
                      <span className="count">{rooms.length}</span>
                    </h2>
                    <input
                      className="search"
                      aria-label="Buscar sala"
                      placeholder="Buscar sala ou localização…"
                      value={search}
                      onChange={(event) => setSearch(event.target.value)}
                    />
                  </div>
                  <div className="room-grid">
                    {selectedRooms.map((item) => (
                      <article
                        key={item.id}
                        className={`room-card ${item.id === roomId ? "selected" : ""}`}
                      >
                        <div className="room-card-top">
                          <span className="tile-icon">
                            <Icon name="room" />
                          </span>
                          <span className="muted">{item.capacity} pessoas</span>
                        </div>
                        <h3>{item.name}</h3>
                        <p>{item.location || "Sem localização"}</p>
                        <div className="card-actions">
                          <button
                            onClick={() => {
                              setRoomId(item.id);
                              setCredential(null);
                            }}
                          >
                            Selecionar →
                          </button>
                          <button
                            aria-label={`Editar ${item.name}`}
                            onClick={() => setEditing({ type: "room", item })}
                          >
                            Editar
                          </button>
                          <button
                            className="danger"
                            disabled={busy}
                            aria-label={`Excluir ${item.name}`}
                            onClick={() => remove("room", item)}
                          >
                            Excluir
                          </button>
                        </div>
                      </article>
                    ))}
                  </div>
                  {!selectedRooms.length && (
                    <p className="empty-state">
                      Nenhuma sala corresponde à busca.
                    </p>
                  )}
                  <div className="section-heading">
                    <div>
                      <h2>Aparelhos · {room?.name}</h2>
                      <p className="muted">
                        O status representa o cadastro operacional do aparelho.
                      </p>
                    </div>
                    <button
                      className="button secondary"
                      disabled={feed.loading}
                      onClick={() => setEditing({ type: "appliance" })}
                    >
                      ＋ Adicionar aparelho
                    </button>
                  </div>
                  <Appliances
                    items={feed.appliances}
                    loading={feed.loading}
                    onEdit={(item) => setEditing({ type: "appliance", item })}
                    onRemove={(item) => remove("appliance", item)}
                    busy={busy}
                  />
                  <section className="panel device-panel">
                    <div>
                      <h2>Conexão com o sensor</h2>
                      <p>
                        {feed.devices[0]
                          ? `Dispositivo vinculado: ${feed.devices[0].id}`
                          : "Vincule um ESP32 para receber as medições desta sala."}
                      </p>
                    </div>
                    <button
                      className="button secondary"
                      disabled={
                        busy || feed.loading || Boolean(feed.devices.length)
                      }
                      onClick={provision}
                    >
                      {feed.devices.length
                        ? "Dispositivo cadastrado"
                        : "Cadastrar dispositivo"}
                    </button>
                  </section>
                  {credential && (
                    <div className="notice credential">
                      <strong>
                        Guarde a credencial do dispositivo. O token é exibido
                        apenas agora.
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
                      <button
                        className="button secondary"
                        onClick={() => setCredential(null)}
                      >
                        Já guardei
                      </button>
                    </div>
                  )}
                </>
              )}
              {tab === "history" && <MonthlyHistory feed={feed} room={room} />}
            </>
          )}
          <footer>
            Movement <span>Organização hoje. Ambientes melhores amanhã.</span>
            <span>Atualização automática a cada 15 s</span>
          </footer>
        </main>
      </div>
      {editing && (
        <ManagementForm
          key={`${editing.type}-${editing.item?.id || "new"}-${roomId}`}
          editing={editing}
          onSave={save}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}

function Overview({ feed, room, onManage }) {
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
  const cards = [
    {
      icon: "temp",
      label: "Temperatura interna",
      value: number(reading?.temp_inside),
      unit: "°C",
      detail: reading
        ? `Externa: ${number(reading.temp_outside)} °C`
        : "Aguardando sensor",
      color: "teal",
    },
    {
      icon: "drop",
      label: "Umidade relativa",
      value: number(reading?.humidity_inside),
      unit: "%",
      detail: reading
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
      color: "amber",
    },
  ];
  return (
    <>
      <div className="section-heading">
        <h2>
          {room?.name}{" "}
          <span
            className={`badge ${feed.latest?.is_stale || feed.error ? "warning" : "success"}`}
          >
            {feed.loading
              ? "Carregando"
              : feed.error
                ? "Sem conexão"
                : feed.latest?.is_stale
                  ? "Sem leitura recente"
                  : "Sensor atualizado"}
          </span>
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
      <div className="overview-bottom">
        <section className="panel">
          <div className="section-heading">
            <h2>Inventário da sala</h2>
            <button className="text-button" onClick={onManage}>
              Gerenciar →
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
                    {AC_KINDS[item.kind]} · {number(item.capacity_btu, 0)} BTU/h
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

function Appliances({ items, loading, onEdit, onRemove, busy }) {
  if (loading) return <div className="empty-state">Carregando aparelhos…</div>;
  if (!items.length)
    return (
      <div className="empty-state">
        <Icon name="snow" size={32} />
        <h3>Nenhum aparelho nesta sala</h3>
        <p>Adicione os equipamentos para organizar seu inventário.</p>
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
            <th>Ações</th>
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
