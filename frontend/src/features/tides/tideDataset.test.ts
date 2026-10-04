import dataset from "../../data/tides/pecem-2026.json";

const timePattern = /^([01]\d|2[0-3]):[0-5]\d$/;

describe("dataset DHN Pecém 2026", () => {
  it("preserva metadados, 365 datas e estrutura publicada", () => {
    expect(dataset.schema_version).toBe(1);
    expect(dataset.station).toBe("TERMINAL PORTUÁRIO DO PECÉM");
    expect(dataset.year).toBe(2026);
    expect(dataset.timezone_offset).toBe("-03:00");
    expect(dataset.source).toEqual({
      publisher: "DHN",
      chart: "711",
      mean_level_m: 1.56,
      source_pdf_sha256:
        "dad5ef1a49ddf499c25dce5488612e521c4be614dc1c465a1f6c1ecf2b49b6bd",
    });

    const entries = Object.entries(dataset.days);
    expect(entries).toHaveLength(365);
    expect(new Set(entries.map(([date]) => date)).size).toBe(365);
    expect(entries[0]?.[0]).toBe("2026-01-01");
    expect(entries.at(-1)?.[0]).toBe("2026-12-31");

    for (const [date, events] of entries) {
      expect(date.startsWith("2026-")).toBe(true);
      expect([3, 4]).toContain(events.length);
      const times = events.map((event) => event.time);
      expect(times.every((time) => timePattern.test(time))).toBe(true);
      expect(times).toEqual([...times].sort());
      expect(events.every((event) => typeof event.height_m === "number")).toBe(true);
    }
  });

  it("mantém as amostras normativas da fonte DHN", () => {
    expect(dataset.days["2026-01-01"]).toEqual([
      { time: "02:38", height_m: 2.62 },
      { time: "08:36", height_m: 0.48 },
      { time: "14:57", height_m: 2.89 },
      { time: "21:19", height_m: 0.16 },
    ]);
    expect(dataset.days["2026-10-04"]).toEqual([
      { time: "04:49", height_m: 0.77 },
      { time: "11:12", height_m: 2.12 },
      { time: "17:06", height_m: 0.99 },
      { time: "23:36", height_m: 2.37 },
    ]);
    expect(dataset.days["2026-10-05"]).toEqual([
      { time: "06:14", height_m: 0.70 },
      { time: "12:31", height_m: 2.22 },
      { time: "18:31", height_m: 0.87 },
    ]);
    expect(dataset.days["2026-12-24"]).toContainEqual({
      time: "23:14",
      height_m: -0.06,
    });
    expect(dataset.days["2026-12-31"]).toEqual([
      { time: "04:25", height_m: 0.77 },
      { time: "10:46", height_m: 2.29 },
      { time: "16:51", height_m: 0.86 },
      { time: "23:16", height_m: 2.22 },
    ]);
  });
});
