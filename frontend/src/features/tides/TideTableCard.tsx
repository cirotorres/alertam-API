import { selectTideView, tideTableMetadata, type TideDay, type TideView } from "./tideTable";

const MONTHS = [
  "",
  "jan",
  "fev",
  "mar",
  "abr",
  "mai",
  "jun",
  "jul",
  "ago",
  "set",
  "out",
  "nov",
  "dez",
];

function dayHeading(prefix: string, date: string): string {
  const [, month, day] = date.split("-").map(Number);
  return `${prefix} · ${String(day).padStart(2, "0")} ${MONTHS[month]}`;
}

function height(value: number): string {
  return `${value.toFixed(2).replace(".", ",")} m`;
}

function TideDayBlock({
  prefix,
  day,
  view,
}: {
  prefix: string;
  day: TideDay;
  view: TideView;
}) {
  return (
    <section className="tide-day" aria-labelledby={`tide-${prefix.toLowerCase()}-title`}>
      <h3 id={`tide-${prefix.toLowerCase()}-title`}>{dayHeading(prefix, day.date)}</h3>
      {day.available ? (
        <ul className="tide-day__events">
          {day.events.map((event) => {
            const isNext =
              view.nextEvent?.date === day.date &&
              view.nextEvent.event.time === event.time &&
              view.nextEvent.event.height_m === event.height_m;
            return (
              <li className={isNext ? "tide-event tide-event--next" : "tide-event"} key={event.time}>
                <time>{event.time}</time>
                <span>{height(event.height_m)}</span>
                {isNext ? <strong>Próxima</strong> : null}
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="tide-day__unavailable">
          Tábua de maré de {day.date.slice(0, 4)} ainda não disponível.
        </p>
      )}
    </section>
  );
}

export function TideTableCard({ now = new Date() }: { now?: Date }) {
  const view = selectTideView(now);

  return (
    <section className="weather-section tide-card" aria-labelledby="tide-table-title">
      <div className="weather-section__heading">
        <div>
          <h2 id="tide-table-title">Tábua de maré · DHN</h2>
          <small>Previsão anual oficial · dados estáticos</small>
        </div>
      </div>
      <div className="tide-card__days">
        <TideDayBlock prefix="Hoje" day={view.today} view={view} />
        <TideDayBlock prefix="Amanhã" day={view.tomorrow} view={view} />
      </div>
      <p className="tide-card__source">
        {tideTableMetadata.publisher} · {tideTableMetadata.year} · Carta {tideTableMetadata.chart} · UTC−03
      </p>
    </section>
  );
}
