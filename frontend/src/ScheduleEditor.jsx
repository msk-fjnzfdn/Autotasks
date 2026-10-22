import { useState, useEffect } from "react";

const DAYS = [
  { num: 1, label: "Пн" }, { num: 2, label: "Вт" }, { num: 3, label: "Ср" },
  { num: 4, label: "Чт" }, { num: 5, label: "Пт" }, { num: 6, label: "Сб" },
  { num: 0, label: "Вс" },
];

function parseSchedule(schedule) {
  if (!schedule) return { mode: "manual" };
  const parts = schedule.trim().split(/\s+/);
  if (parts.length !== 5) return { mode: "custom", schedule };

  const [min, hour, dom, mon, dow] = parts;
  if (min === "*" && hour === "*" && dom === "*" && mon === "*" && dow === "*") {
    return { mode: "manual" };
  }
  if (hour === "*" && dom === "*" && mon === "*" && dow === "*" && /^\*\/\d+$/.test(min)) {
    return { mode: "interval", every: min.slice(2) };
  }
  if (dom === "*" && mon === "*" && /^\d+$/.test(hour) && /^\d+$/.test(min)) {
    if (dow === "*") {
      return { mode: "daily", hour, minute: min };
    }
    if (/^[\d,]+$/.test(dow)) {
      return { mode: "weekly", hour, minute: min, days: dow.split(",").map(Number) };
    }
  }
  return { mode: "custom", schedule };
}

const TZ_OFFSET = 3;

export default function ScheduleEditor({ schedule, onChange }) {
  const [state, setState] = useState(() => parseSchedule(schedule));
  const [cronDraft, setCronDraft] = useState(schedule || "");

  useEffect(() => {
    setState(parseSchedule(schedule));
    setCronDraft(schedule || "");
  }, [schedule]);

  const update = (patch) => setState((s) => ({ ...s, ...patch }));

  const buildCron = (s) => {
    switch (s.mode) {
      case "manual": return "";
      case "interval": return `*/${s.every} * * * *`;
      case "daily": return `${s.minute} ${s.hour} * * *`;
      case "weekly": return `${s.minute} ${s.hour} * * ${[...(s.days || [])].sort().join(",")}`;
      default: return s.schedule || "";
    }
  };

  const human = (s) => {
    switch (s.mode) {
      case "manual": return "Запуск только вручную";
      case "interval": return `Каждые ${s.every} мин.`;
      case "daily": {
        const utc = s.hour - TZ_OFFSET < 0 ? s.hour - TZ_OFFSET + 24 : s.hour - TZ_OFFSET;
        return `Каждый день в ${s.hour}:${String(s.minute).padStart(2, "0")} по местному времени (в ${utc}:${String(s.minute).padStart(2, "0")} UTC)`;
      }
      case "weekly": {
        const utc = s.hour - TZ_OFFSET < 0 ? s.hour - TZ_OFFSET + 24 : s.hour - TZ_OFFSET;
        const names = DAYS.filter((d) => (s.days || []).includes(d.num)).map((d) => d.label);
        return `По ${names.join(", ")} в ${s.hour}:${String(s.minute).padStart(2, "0")} по местному времени (в ${utc}:${String(s.minute).padStart(2, "0")} UTC)`;
      }
      case "custom": return `Cron: ${s.schedule}`;
    }
  };

  const isCustom = state.mode === "custom";
  const cron = isCustom ? cronDraft : buildCron(state);

  return (
    <div className="schedule-editor">
      <div className="schedule-modes">
        <label>
          <input type="radio" name={`sch-${schedule || "new"}`}
            checked={state.mode === "interval"}
            onChange={() => update({ mode: "interval", every: state.every || 5 })} />
          Каждые
          {state.mode === "interval" && (
            <select value={state.every}
              onChange={(e) => update({ every: e.target.value })}>
              {[1, 5, 10, 15, 30].map((n) => <option key={n} value={n}>{n} мин.</option>)}
            </select>
          )}
        </label>
        <label>
          <input type="radio" name={`sch-${schedule || "new"}`}
            checked={state.mode === "daily"}
            onChange={() => update({ mode: "daily", hour: 9, minute: 0 })} />
          Ежедневно в
          {state.mode === "daily" && (
            <>
              <select value={state.hour} onChange={(e) => update({ hour: Number(e.target.value) })}>
                {[...Array(24).keys()].map((h) => <option key={h} value={h}>{String(h).padStart(2, "0")}</option>)}
              </select>
              :
              <select value={state.minute} onChange={(e) => update({ minute: Number(e.target.value) })}>
                {[0, 15, 30, 45].map((m) => <option key={m} value={m}>{String(m).padStart(2, "0")}</option>)}
              </select>
            </>
          )}
        </label>
        <label>
          <input type="radio" name={`sch-${schedule || "new"}`}
            checked={state.mode === "weekly"}
            onChange={() => update({ mode: "weekly", hour: 9, minute: 0, days: [1, 2, 3, 4, 5] })} />
          По дням недели
          {state.mode === "weekly" && (
            <>
              <select value={state.hour} onChange={(e) => update({ hour: Number(e.target.value) })}>
                {[...Array(24).keys()].map((h) => <option key={h} value={h}>{String(h).padStart(2, "0")}</option>)}
              </select>
              :
              <select value={state.minute} onChange={(e) => update({ minute: Number(e.target.value) })}>
                {[0, 15, 30, 45].map((m) => <option key={m} value={m}>{String(m).padStart(2, "0")}</option>)}
              </select>
              <span className="day-picker">
                {DAYS.map((d) => (
                  <label key={d.num} className={state.days?.includes(d.num) ? "on" : ""}>
                    <input type="checkbox"
                      checked={state.days?.includes(d.num) || false}
                      onChange={(e) => {
                        const days = e.target.checked
                          ? [...(state.days || []), d.num]
                          : state.days.filter((x) => x !== d.num);
                        update({ days });
                      }} />
                    {d.label}
                  </label>
                ))}
              </span>
            </>
          )}
        </label>
        <label>
          <input type="radio" name={`sch-${schedule || "new"}`}
            checked={isCustom}
            onChange={() => update({ mode: "custom", schedule: schedule || "" })} />
          Свой cron
          {isCustom && (
            <input type="text" placeholder="например */5 * * * *"
              value={cronDraft}
              onChange={(e) => setCronDraft(e.target.value)} />
          )}
        </label>
      </div>

      <div className="schedule-footer">
        <span className="schedule-human">{human(state)}</span>
        <button type="button" className="icon-btn"
          onClick={() => onChange(cron)}>
          Сохранить таймер
        </button>
      </div>
    </div>
  );
}
