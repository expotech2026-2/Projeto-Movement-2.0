// Régua térmica: sala, rua, alvo do ar e faixa de conforto na mesma escala de 14 a 36 °C.
const MIN = 14;
const MAX = 36;
const LABELS = [16, 20, 24, 28, 32];

const position = (value) =>
  `${(100 * (Math.min(MAX, Math.max(MIN, value)) - MIN)) / (MAX - MIN)}%`;

export function ThermalScale({ inside, outside, target, value, detail }) {
  const hasInside = inside != null;
  const hasOutside = outside != null;
  const hasTarget = target != null && target > 0;
  const summary = [
    hasInside ? `Temperatura interna ${value} °C` : "Sem leitura interna",
    hasOutside ? `externa ${outside} °C` : "",
    hasTarget ? `alvo do ar ${target} °C` : "",
    "faixa de conforto de 20 a 23 °C",
  ]
    .filter(Boolean)
    .join(", ");
  return (
    <figure className="thermal">
      <div className="thermal-reading">
        <span>Temperatura interna</span>
        <strong className={hasInside ? undefined : "empty"}>
          {value}
          <small>°C</small>
        </strong>
        <span>{detail}</span>
      </div>
      <div className="thermal-scale" role="img" aria-label={summary}>
        <div className="thermal-track">
          <span
            className="thermal-comfort"
            style={{
              left: position(20),
              right: `calc(100% - ${position(23)})`,
            }}
          />
          {hasInside && (
            <span
              className="thermal-fill"
              style={{ width: position(inside) }}
            />
          )}
          {hasTarget && (
            <span
              className="thermal-target"
              style={{ left: position(target) }}
            />
          )}
          {hasOutside && (
            <span
              className="thermal-outside"
              style={{ left: position(outside) }}
            />
          )}
          {hasInside && (
            <span
              className="thermal-inside"
              style={{ left: position(inside) }}
            />
          )}
        </div>
        <div className="thermal-labels" aria-hidden="true">
          {LABELS.map((label) => (
            <span key={label} style={{ left: position(label) }}>
              {label}°
            </span>
          ))}
        </div>
      </div>
      <figcaption className="thermal-legend">
        <span className="legend-comfort">Conforto de 20 a 23 °C</span>
        <span className="legend-inside">Sala</span>
        <span className="legend-outside">Rua</span>
        <span className="legend-target">Alvo do ar</span>
      </figcaption>
    </figure>
  );
}
