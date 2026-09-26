export type BottomTab = "maneuvers" | "arrivals" | "departures" | "anchored";

type BottomNavProps = {
  active: BottomTab;
  onChange: (value: BottomTab) => void;
};

const ITEMS: Array<{ value: BottomTab; label: string; short: string }> = [
  { value: "maneuvers", label: "Manobras confirmadas", short: "Manobras" },
  { value: "arrivals", label: "Prev. atracação", short: "ATR" },
  { value: "departures", label: "Prev. desatracação", short: "DES" },
  { value: "anchored", label: "Fundeados", short: "Fundeados" },
];

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
          <span aria-hidden="true">{item.short}</span>
        </button>
      ))}
    </nav>
  );
}
