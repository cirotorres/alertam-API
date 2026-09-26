export type BottomTab = "maneuvers" | "arrivals" | "departures" | "anchored";

type BottomNavProps = {
  active: BottomTab;
  onChange: (value: BottomTab) => void;
};

const ITEMS: Array<{ value: BottomTab; label: string }> = [
  { value: "maneuvers", label: "Manobras confirmadas" },
  { value: "arrivals", label: "Prev. atracação" },
  { value: "departures", label: "Prev. desatracação" },
  { value: "anchored", label: "Fundeados" },
];

function NavIcon({ type }: { type: BottomTab }) {
  if (type === "anchored") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="5" r="2.2" />
        <path d="M12 7.5v10M7.5 10.5h9M5 15.5c1.6 3 4 4.5 7 4.5s5.4-1.5 7-4.5M5 15.5l-1.8 1.3M19 15.5l1.8 1.3" />
      </svg>
    );
  }

  if (type === "maneuvers") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4 14.5h16l-2.2 4.2H6.2L4 14.5Z" />
        <path d="M7 14.5V9.2h10v5.3M9 9.2V6.5h6v2.7M5.5 20.2c1.2.7 2.4.7 3.6 0 1.2.7 2.4.7 3.6 0 1.2.7 2.4.7 3.6 0" />
      </svg>
    );
  }

  if (type === "arrivals") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4 12h13M13 7l5 5-5 5" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20 12H7M11 7l-5 5 5 5" />
      <path d="M18.5 6.5v11" />
    </svg>
  );
}

export function BottomNav({ active, onChange }: BottomNavProps) {
  return (
    <nav className="bottom-nav" aria-label="Consultas operacionais">
      {ITEMS.map((item) => (
        <button
          key={item.value}
          type="button"
          aria-label={item.label}
          aria-current={active === item.value ? "page" : undefined}
          className={active === item.value ? "bottom-nav__item is-active" : "bottom-nav__item"}
          onClick={() => onChange(item.value)}
        >
          <NavIcon type={item.value} />
          <span>{item.label}</span>
        </button>
      ))}
    </nav>
  );
}
