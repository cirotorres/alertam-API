import type { MobileSnapshotV1 } from "../api/contract";
import { useShellContext } from "../app/AppShell";

const WEATHER_LABELS: Record<number, string> = {
  0: "Céu limpo",
  1: "Predominantemente limpo",
  2: "Parcialmente nublado",
  3: "Nublado",
  45: "Nevoeiro",
  48: "Nevoeiro com deposição de gelo",
  51: "Garoa leve",
  53: "Garoa moderada",
  55: "Garoa intensa",
  61: "Chuva leve",
  63: "Chuva moderada",
  65: "Chuva forte",
  80: "Pancadas de chuva leves",
  81: "Pancadas de chuva moderadas",
  82: "Pancadas de chuva fortes",
  95: "Trovoada",
  96: "Trovoada com granizo leve",
  99: "Trovoada com granizo forte",
};

function hasWeather(
  block: MobileSnapshotV1["weather"],
): block is Exclude<MobileSnapshotV1["weather"], Record<string, never>> {
  return "air_temperature_c" in block;
}

function hasMarine(
  block: MobileSnapshotV1["marine"],
): block is Exclude<MobileSnapshotV1["marine"], Record<string, never>> {
  return "wave_height_m" in block;
}

function number(value: number | null, unit: string, digits = 1): string {
  if (value === null) return "—";
  return `${new Intl.NumberFormat("pt-BR", {
    maximumFractionDigits: digits,
  }).format(value)} ${unit}`;
}

function direction(value: number | null): string {
  if (value === null) return "—";
  const normalized = ((value % 360) + 360) % 360;
  const labels = ["N", "NE", "L", "SE", "S", "SO", "O", "NO"];
  const label = labels[Math.round(normalized / 45) % 8];
  return `${Math.round(normalized)}° ${label}`;
}

function observed(value: string | null): string {
  if (!value) return "Horário não informado";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `Observado em ${new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date)}`;
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="weather-metric">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

export function WeatherPage() {
  const { snapshotState } = useShellContext();
  const snapshot = snapshotState.data?.snapshot ?? null;
  const weather = snapshot && hasWeather(snapshot.weather) ? snapshot.weather : null;
  const marine = snapshot && hasMarine(snapshot.marine) ? snapshot.marine : null;

  return (
    <section className="page-stack weather-page">
      <header className="weather-page__header">
        <div>
          <div className="weather-page__title-row">
            <h1>Tempo e mar</h1>
            <span className="weather-page__location">Pecém - CE</span>
          </div>
          <p className="page-intro">
            Condições meteorológicas e marítimas recebidas do AlertaM Desktop via API Open-Meteo.
            Valores aproximados; podem diferir das condições locais observadas.
          </p>
        </div>
      </header>

      <section className="weather-section" aria-labelledby="weather-atmosphere-title">
        <div className="weather-section__heading">
          <div>
            <h2 id="weather-atmosphere-title">Atmosfera</h2>
            <small>{weather ? observed(weather.observed_at) : "Sem leitura disponível"}</small>
          </div>
          {weather ? (
            <strong className="weather-section__primary">
              {number(weather.air_temperature_c, "°C")}
            </strong>
          ) : null}
        </div>

        {weather ? (
          <>
            <p className="weather-condition">
              {weather.weather_code === null
                ? "Condição não informada"
                : WEATHER_LABELS[weather.weather_code] ?? `Código meteorológico ${weather.weather_code}`}
            </p>
            <dl className="weather-metrics">
              <Metric label="Umidade" value={number(weather.humidity_pct, "%", 0)} />
              <Metric label="Vento" value={number(weather.wind_speed_kn, "kn")} />
              <Metric label="Direção do vento" value={direction(weather.wind_direction_deg)} />
              <Metric label="Rajada" value={number(weather.wind_gust_kn, "kn")} />
              <Metric label="Visibilidade" value={number(weather.visibility_m === null ? null : weather.visibility_m / 1000, "km")} />
              <Metric label="Precipitação" value={number(weather.precipitation_mm, "mm")} />
            </dl>
          </>
        ) : (
          <p className="empty-state">Dados meteorológicos ainda não estão disponíveis neste snapshot.</p>
        )}
      </section>

      <section className="weather-section" aria-labelledby="weather-marine-title">
        <div className="weather-section__heading">
          <div>
            <h2 id="weather-marine-title">Mar</h2>
            <small>{marine ? observed(marine.observed_at) : "Sem leitura disponível"}</small>
          </div>
          {marine ? (
            <strong className="weather-section__primary">
              {number(marine.wave_height_m, "m")}
            </strong>
          ) : null}
        </div>

        {marine ? (
          <dl className="weather-metrics">
            <Metric label="Altura de onda" value={number(marine.wave_height_m, "m")} />
            <Metric label="Direção da onda" value={direction(marine.wave_direction_deg)} />
            <Metric label="Período da onda" value={number(marine.wave_period_s, "s")} />
            <Metric label="Altura da ondulação" value={number(marine.swell_height_m, "m")} />
            <Metric label="Direção da ondulação" value={direction(marine.swell_direction_deg)} />
            <Metric label="Período da ondulação" value={number(marine.swell_period_s, "s")} />
            <Metric label="Temperatura do mar" value={number(marine.sea_temperature_c, "°C")} />
            <Metric label="Corrente" value={number(marine.current_kn, "kn")} />
            <Metric label="Direção da corrente" value={direction(marine.current_direction_deg)} />
          </dl>
        ) : (
          <p className="empty-state">Dados marítimos ainda não estão disponíveis neste snapshot.</p>
        )}
      </section>
    </section>
  );
}
