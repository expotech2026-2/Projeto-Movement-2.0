import { Icon } from "./Icon";

const plural = (count, singular, many) =>
  `${count} ${count === 1 ? singular : many}`;

export function UnitsView({
  units,
  rooms,
  roomId,
  search,
  onSearch,
  isAdmin,
  busy,
  onSelect,
  onEdit,
  onRemove,
}) {
  const term = search.trim().toLocaleLowerCase();
  const matches = (value) => value.toLocaleLowerCase().includes(term);
  const sections = units
    .map((unit) => {
      const unitRooms = rooms.filter((room) => room.unit_id === unit.id);
      const visible =
        !term || matches(unit.name)
          ? unitRooms
          : unitRooms.filter((room) =>
              matches(`${room.name} ${room.location}`),
            );
      return { unit, rooms: visible, total: unitRooms.length };
    })
    .filter(
      (section) => !term || section.rooms.length || matches(section.unit.name),
    );
  if (!units.length)
    return (
      <div className="empty-state">
        <Icon name="building" size={36} />
        <h2>Organize seus espaços por unidade</h2>
        <p>
          {isAdmin
            ? "Comece cadastrando uma unidade, como Centro ou Polo Sede, e depois as salas de cada uma."
            : "Nenhuma unidade cadastrada ainda. Peça a um administrador para cadastrar unidades e salas."}
        </p>
        {isAdmin && (
          <button
            className="button primary"
            onClick={() => onEdit({ type: "unit" })}
          >
            Cadastrar primeira unidade
          </button>
        )}
      </div>
    );
  return (
    <>
      <div className="section-heading">
        <h2>
          Unidades <span className="count">{units.length}</span>
        </h2>
        <input
          className="search"
          aria-label="Buscar unidade ou sala"
          placeholder="Buscar unidade, sala ou bloco…"
          value={search}
          onChange={(event) => onSearch(event.target.value)}
        />
      </div>
      {!sections.length && (
        <p className="empty-state">
          Nenhuma unidade ou sala corresponde à busca.
        </p>
      )}
      {sections.map(({ unit, rooms: unitRooms, total }) => (
        <section className="unit-section" key={unit.id}>
          <header className="unit-header">
            <span className="tile-icon unit-icon">
              <Icon name="building" />
            </span>
            <div className="unit-title">
              <h3>{unit.name}</h3>
              <p className="muted">
                {[unit.address, plural(total, "sala", "salas")]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
            </div>
            {isAdmin && (
              <div className="unit-actions">
                <button
                  className="button secondary"
                  onClick={() => onEdit({ type: "room", unitId: unit.id })}
                >
                  ＋ Sala
                </button>
                <button
                  className="text-button"
                  aria-label={`Editar unidade ${unit.name}`}
                  onClick={() => onEdit({ type: "unit", item: unit })}
                >
                  Editar
                </button>
                <button
                  className="text-button danger"
                  disabled={busy}
                  aria-label={`Excluir unidade ${unit.name}`}
                  onClick={() => onRemove("unit", unit)}
                >
                  Excluir
                </button>
              </div>
            )}
          </header>
          {unitRooms.length ? (
            <div className="room-grid">
              {unitRooms.map((room) => (
                <article
                  key={room.id}
                  className={`room-card ${room.id === roomId ? "selected" : ""}`}
                >
                  <div className="room-card-top">
                    <span className="tile-icon">
                      <Icon name="room" />
                    </span>
                    <span className="muted">
                      {plural(room.capacity, "pessoa", "pessoas")}
                    </span>
                  </div>
                  <h3>{room.name}</h3>
                  <p>{room.location || "Bloco/andar não informado"}</p>
                  <div className="card-actions">
                    <button onClick={() => onSelect(room.id)}>
                      {room.id === roomId ? "Selecionada ✓" : "Selecionar →"}
                    </button>
                    {isAdmin && (
                      <>
                        <button
                          aria-label={`Editar ${room.name}`}
                          onClick={() => onEdit({ type: "room", item: room })}
                        >
                          Editar
                        </button>
                        <button
                          className="danger"
                          disabled={busy}
                          aria-label={`Excluir ${room.name}`}
                          onClick={() => onRemove("room", room)}
                        >
                          Excluir
                        </button>
                      </>
                    )}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <p className="muted unit-empty">
              {term
                ? "Nenhuma sala desta unidade corresponde à busca."
                : isAdmin
                  ? "Nenhuma sala nesta unidade ainda. Use “＋ Sala” para cadastrar."
                  : "Nenhuma sala nesta unidade ainda."}
            </p>
          )}
        </section>
      ))}
    </>
  );
}
