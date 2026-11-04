const PATHS = {
  grid: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  room: "M4 21V3h12v18 M16 8h4v13 M1 21h22 M12 11v2",
  building:
    "M3 21h18 M5 21V7l7-4 7 4v14 M9 9h1 M14 9h1 M9 13h1 M14 13h1 M10 21v-4h4v4",
  snow: "M12 2v20 M3.34 7l17.32 10 M3.34 17L20.66 7 M8 4l4 4 4-4 M8 20l4-4 4 4",
  chart: "M3 3v18h18 M7 15l4-5 4 3 5-8",
  file: "M14 3H6v18h12V7z M14 3v4h4 M9 13h6 M9 17h6",
  temp: "M9 14V5a3 3 0 016 0v9a5 5 0 11-6 0 M12 8v10",
  drop: "M12 2C9 7 5 11 5 15a7 7 0 0014 0c0-4-4-8-7-13z",
  people:
    "M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2 M9 11a4 4 0 100-8 4 4 0 000 8 M22 21v-2a4 4 0 00-3-3.87 M16 3.13a4 4 0 010 7.75",
  arrow: "M12 5v14 M5 12l7 7 7-7",
  sun: "M12 8a4 4 0 100 8 4 4 0 000-8z M12 2v2 M12 20v2 M4.93 4.93l1.41 1.41 M17.66 17.66l1.41 1.41 M2 12h2 M20 12h2 M4.93 19.07l1.41-1.41 M17.66 6.34l1.41-1.41",
  moon: "M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z",
};

export function Icon({ name, size = 20 }) {
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
      <path d={PATHS[name] || PATHS.snow} />
    </svg>
  );
}
