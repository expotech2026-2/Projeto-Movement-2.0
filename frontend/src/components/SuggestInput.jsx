import { useId, useState } from "react";

// Campo de texto livre com sugestões navegáveis por teclado (setas, Enter e Esc).
export function SuggestInput({
  value,
  onChange,
  options,
  onChoose,
  describe,
  placeholder,
  emptyText,
  hidden = false,
  maxLength = 80,
  label,
}) {
  const listId = useId();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const typed = value.trim().length > 0;
  const show = open && typed && !hidden && (options.length > 0 || Boolean(emptyText));
  const index = Math.min(active, Math.max(options.length - 1, 0));

  function choose(option) {
    onChoose(option);
    setOpen(false);
  }

  function onKeyDown(event) {
    if (!show || !options.length) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((index + 1) % options.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((index - 1 + options.length) % options.length);
    } else if (event.key === "Enter") {
      event.preventDefault();
      choose(options[index]);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div className="city-input suggest-input">
      <input
        role="combobox"
        aria-label={label}
        aria-expanded={show}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={
          show && options.length ? `${listId}-${index}` : undefined
        }
        autoComplete="off"
        maxLength={maxLength}
        placeholder={placeholder}
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
          {options.length ? (
            options.map((option, position) => {
              const { key, label: text, detail } = describe(option);
              return (
                <li
                  key={key}
                  id={`${listId}-${position}`}
                  role="option"
                  aria-selected={position === index}
                  className={position === index ? "active" : undefined}
                  onMouseDown={(event) => {
                    event.preventDefault();
                    choose(option);
                  }}
                  onMouseEnter={() => setActive(position)}
                >
                  <span>{text}</span>
                  {detail && <small>{detail}</small>}
                </li>
              );
            })
          ) : (
            <li className="city-empty" role="option" aria-disabled="true">
              {emptyText}
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
