import { selectTideView } from "./tideTable";

describe("selectTideView", () => {
  it("usa UTC-03 mesmo quando o instante UTC já virou o dia", () => {
    const view = selectTideView(new Date("2026-10-05T00:30:00Z"));

    expect(view.today.date).toBe("2026-10-04");
    expect(view.today.events.map((event) => event.time)).toEqual([
      "04:49",
      "11:12",
      "17:06",
      "23:36",
    ]);
    expect(view.tomorrow.date).toBe("2026-10-05");
    expect(view.tomorrow.events).toHaveLength(3);
    expect(view.nextEvent).toEqual({
      date: "2026-10-04",
      event: { time: "23:36", height_m: 2.37 },
    });
  });

  it("usa o primeiro evento de amanhã depois do último de hoje", () => {
    const view = selectTideView(new Date("2026-10-05T02:50:00Z"));

    expect(view.today.date).toBe("2026-10-04");
    expect(view.nextEvent).toEqual({
      date: "2026-10-05",
      event: { time: "06:14", height_m: 0.7 },
    });
  });

  it("preserva dia de três eventos e altura negativa", () => {
    const october = selectTideView(new Date("2026-10-05T15:00:00Z"));
    expect(october.today.events).toHaveLength(3);

    const december = selectTideView(new Date("2026-12-24T15:00:00Z"));
    expect(december.today.events).toContainEqual({ time: "23:14", height_m: -0.06 });
  });

  it("não inventa 2027 em 31/12/2026", () => {
    const view = selectTideView(new Date("2026-12-31T15:00:00Z"));

    expect(view.today.available).toBe(true);
    expect(view.today.date).toBe("2026-12-31");
    expect(view.tomorrow).toEqual({
      date: "2027-01-01",
      events: [],
      available: false,
    });
  });
});
