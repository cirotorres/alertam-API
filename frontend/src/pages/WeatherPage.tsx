import type { MobileSnapshotV1, MobileSnapshotV2 } from "../api/contract";
import { useShellContext } from "../app/AppShell";
import { TideTableCard } from "../features/tides/TideTableCard";

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

function observedDirection(
  degrees: number | null,
  cardinal: string | null,
): string {
  if (degrees === null) return cardinal ?? "—";
  const normalized = ((degrees % 360) + 360) % 360;
  if (cardinal) return `${Math.round(normalized)}° ${cardinal}`;
  return direction(degrees);
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

function statusText(status: "fresh" | "stale" | "unavailable"): string {
  if (status === "fresh") return "Atualizado";
  if (status === "stale") return "Desatualizado";
  return "Dados indisponíveis";
}

function weatherCondition(code: number | null): string {
  if (code === null) return "Condição não informada";
  return WEATHER_LABELS[code] ?? `Código meteorológico ${code}`;
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="weather-metric">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function LegacyWeather({ snapshot }: { snapshot: MobileSnapshotV1 }) {
  const weather = hasWeather(snapshot.weather) ? snapshot.weather : null;
  const marine = hasMarine(snapshot.marine) ? snapshot.marine : null;

  return (
    <>
      <p className="page-intro">
        Condições meteorológicas e marítimas recebidas do AlertaM Desktop via API Open-Meteo.
        Valores aproximados; podem diferir das condições locais observadas.
      </p>

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
            <p className="weather-condition">{weatherCondition(weather.weather_code)}</p>
            <dl className="weather-metrics">
              <Metric label="Umidade" value={number(weather.humidity_pct, "%", 0)} />
              <Metric label="Vento" value={number(weather.wind_speed_kn, "kn")} />
              <Metric label="Direção do vento" value={direction(weather.wind_direction_deg)} />
              <Metric label="Rajada" value={number(weather.wind_gust_kn, "kn")} />
              <Metric
                label="Visibilidade"
                value={number(
                  weather.visibility_m === null ? null : weather.visibility_m / 1000,
                  "km",
                )}
              />
              <Metric label="Precipitação" value={number(weather.precipitation_mm, "mm")} />
            </dl>
          </>
        ) : (
          <p className="empty-state">Dados meteorológicos ainda não estão disponíveis neste snapshot.</p>
        )}
      </section>

      <LegacyMarine marine={marine} />
    </>
  );
}

function LegacyMarine({
  marine,
}: {
  marine: Exclude<MobileSnapshotV1["marine"], Record<string, never>> | null;
}) {
  return (
    <section className="weather-section" aria-labelledby="weather-marine-title">
      <div className="weather-section__heading">
        <div>
          <h2 id="weather-marine-title">Mar</h2>
          <small>{marine ? observed(marine.observed_at) : "Sem leitura disponível"}</small>
        </div>
        {marine ? (
          <strong className="weather-section__primary">{number(marine.wave_height_m, "m")}</strong>
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
  );
}

function V2Weather({ snapshot }: { snapshot: MobileSnapshotV2 }) {
  const primary = snapshot.atmosphere.primary;
  const complementary = snapshot.atmosphere.complementary;
  const marine = snapshot.marine;

  return (
    <>
      <p className="page-intro">
        Atmosfera observada pela Estação Pecém quando disponível, com Open-Meteo identificado
        separadamente como complemento ou fallback. Condições marítimas via Open-Meteo Marine.
      </p>

      {primary.status === "unavailable" ? (
        <section className="weather-section" aria-labelledby="weather-atmosphere-title">
          <div className="weather-section__heading">
            <div>
              <h2 id="weather-atmosphere-title">Atmosfera</h2>
              <small>{statusText(primary.status)}</small>
            </div>
          </div>
          <p className="empty-state">Dados indisponíveis</p>
        </section>
      ) : primary.source === "webpilot" ? (
        <section className="weather-section" aria-labelledby="weather-atmosphere-title">
          <div className="weather-section__heading">
            <div>
              <h2 id="weather-atmosphere-title">Estação Pecém · observação</h2>
              <small>{observed(primary.observed_at)}</small>
            </div>
            <strong className="weather-section__primary">
              {number(primary.air_temperature_c, "°C")}
            </strong>
          </div>
          <p className="weather-condition">
            <strong>WebPilot</strong> · {statusText(primary.status)}
          </p>
          <dl className="weather-metrics">
            <Metric label="Vento atual" value={number(primary.wind_speed_current_kn, "kn")} />
            <Metric label="Vento médio" value={number(primary.wind_speed_mean_kn, "kn")} />
            <Metric label="Vento máximo" value={number(primary.wind_speed_max_kn, "kn")} />
            <Metric
              label="Direção do vento"
              value={observedDirection(
                primary.wind_direction_deg,
                primary.wind_direction_cardinal,
              )}
            />
            <Metric label="Temperatura" value={number(primary.air_temperature_c, "°C")} />
            <Metric label="Sensação térmica" value={number(primary.apparent_temperature_c, "°C")} />
            <Metric label="Umidade" value={number(primary.humidity_pct, "%", 0)} />
            <Metric label="Pressão" value={number(primary.pressure_hpa, "hPa", 2)} />
            <Metric label="Pressão 6h" value={number(primary.pressure_6h_hpa, "hPa", 2)} />
            <Metric label="Precipitação" value={number(primary.precipitation_mm, "mm")} />
          </dl>
        </section>
      ) : (
        <section className="weather-section" aria-labelledby="weather-atmosphere-title">
          <div className="weather-section__heading">
            <div>
              <h2 id="weather-atmosphere-title">Atmosfera</h2>
              <small>{observed(primary.observed_at)}</small>
            </div>
            <strong className="weather-section__primary">
              {number(primary.air_temperature_c, "°C")}
            </strong>
          </div>
          <p className="weather-condition">
            <strong>Open-Meteo · fallback/modelo</strong> · {statusText(primary.status)}
          </p>
          <p className="weather-condition">{weatherCondition(primary.weather_code)}</p>
          <dl className="weather-metrics">
            <Metric label="Umidade" value={number(primary.humidity_pct, "%", 0)} />
            <Metric label="Vento" value={number(primary.wind_speed_kn, "kn")} />
            <Metric label="Direção do vento" value={direction(primary.wind_direction_deg)} />
            <Metric label="Rajada" value={number(primary.wind_gust_kn, "kn")} />
            <Metric
              label="Visibilidade"
              value={number(
                primary.visibility_m === null ? null : primary.visibility_m / 1000,
                "km",
              )}
            />
            <Metric label="Precipitação" value={number(primary.precipitation_mm, "mm")} />
          </dl>
        </section>
      )}

      <section className="weather-section" aria-labelledby="weather-complementary-title">
        <div className="weather-section__heading">
          <div>
            <h2 id="weather-complementary-title">Complementar / previsão</h2>
            <small>
              {complementary.status === "unavailable"
                ? statusText(complementary.status)
                : observed(complementary.observed_at)}
            </small>
          </div>
        </div>
        {complementary.status === "unavailable" ? (
          <p className="empty-state">Dados indisponíveis</p>
        ) : (
          <>
            <p className="weather-condition">
              <strong>Open-Meteo</strong> · {statusText(complementary.status)}
            </p>
            <dl className="weather-metrics">
              <Metric label="Condição" value={weatherCondition(complementary.weather_code)} />
              <Metric
                label="Visibilidade"
                value={number(
                  complementary.visibility_m === null
                    ? null
                    : complementary.visibility_m / 1000,
                  "km",
                )}
              />
            </dl>
          </>
        )}
      </section>

      <section className="weather-section" aria-labelledby="weather-marine-title">
        <div className="weather-section__heading">
          <div>
            <h2 id="weather-marine-title">Condições marítimas</h2>
            <small>
              {marine.status === "unavailable"
                ? statusText(marine.status)
                : observed(marine.observed_at)}
            </small>
          </div>
        </div>
        {marine.status === "unavailable" ? (
          <p className="empty-state">Dados indisponíveis</p>
        ) : (
          <>
            <p className="weather-condition">
              <strong>Open-Meteo Marine</strong> · {statusText(marine.status)}
            </p>
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
          </>
        )}
      </section>
    </>
  );
}

export function WeatherPage() {
  const { snapshotState } = useShellContext();
  const snapshot = snapshotState.data?.snapshot ?? null;

  return (
    <section className="page-stack weather-page">
      <header className="weather-page__header">
        <div className="weather-page__title-row">
          <h1>Tempo e mar</h1>
          <span className="weather-page__location">Pecém - CE</span>
        </div>
      </header>
      {snapshot === null ? (
        <p className="empty-state">Aguardando snapshot meteorológico.</p>
      ) : snapshot.schema_version === 1 ? (
        <LegacyWeather snapshot={snapshot} />
      ) : (
        <V2Weather snapshot={snapshot} />
      )}
      <TideTableCard />
    </section>
  );
}
