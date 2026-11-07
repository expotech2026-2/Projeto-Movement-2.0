import { useId, useMemo, useState } from "react";
import { cityLabel, matchCities, normalize } from "../services/cityMatch";

// Campo de cidade com sugestões dos municípios do Brasil (IBGE), navegável por teclado.
export function CityInput({ value, onChange, cities }) {
  const listId = useId();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const matches = useMemo(() => matchCities(cities, value), [cities, value]);
  const chosen = matches.some(
    (city) => normalize(cityLabel(city)) === normalize(value.trim()),
  );
  const typed = value.trim().length > 0;
  const show = open && typed && !chosen && cities.length > 0;

  function choose(city) {
    onChange(cityLabel(city));
    setOpen(false);
  }

  function onKeyDown(event) {
    if (!show || !matches.length) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((index) => (index + 1) % matches.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((index) => (index - 1 + matches.length) % matches.length);
    } else if (event.key === "Enter") {
      event.preventDefault();
      choose(matches[active]);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div className="city-input">
      <input
        role="combobox"
        aria-expanded={show}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={
          show && matches.length ? `${listId}-${active}` : undefined
        }
        autoComplete="off"
        maxLength={120}
        placeholder="Comece a digitar, ex.: Campinas"
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
          setOpen(true);
          setActive(0);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={onKeyDown}
      />
      {show && (
        <ul id={listId} role="listbox" className="city-options">
          {matches.length ? (
            matches.map((city, index) => (
              <li
                key={city.id}
                id={`${listId}-${index}`}
                role="option"
                aria-selected={index === active}
                className={index === active ? "active" : undefined}
                onMouseDown={(event) => {
                  event.preventDefault();
                  choose(city);
                }}
                onMouseEnter={() => setActive(index)}
              >
                <span>
                  {city.name.slice(0, city.start)}
                  <mark>{city.name.slice(city.start, city.end)}</mark>
                  {city.name.slice(city.end)}
                </span>
                <small>{city.state}</small>
              </li>
            ))
          ) : (
            <li className="city-empty" role="option" aria-disabled="true">
              Nenhum município do Brasil com esse nome
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
