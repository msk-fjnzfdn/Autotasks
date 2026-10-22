import { useEffect, useState } from "react";
import { api } from "./api";
import ScheduleEditor from "./ScheduleEditor";

export default function ChainDetailPage({ chain, onBack }) {
  const [blocks, setBlocks] = useState([]);
  const [catalog, setCatalog] = useState([]);
  const [runs, setRuns] = useState([]);
  const [schedule, setSchedule] = useState(chain.schedule || "");
  const [selectedType, setSelectedType] = useState("");
  const [newBlockName, setNewBlockName] = useState("");
  const [params, setParams] = useState({});
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [lastRun, setLastRun] = useState(null);
  const [testResults, setTestResults] = useState({});
  const [activeRunId, setActiveRunId] = useState(null);
  const [liveRun, setLiveRun] = useState(null);
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [selectedRun, setSelectedRun] = useState(null);

  const loadAll = async () => {
    try {
      const [b, cat, r] = await Promise.all([
        api(`/api/chains/${chain.id}/blocks`),
        api(`/api/chains/blocks/catalog`),
        api(`/api/chains/${chain.id}/runs`),
      ]);
      setBlocks(b);
      setCatalog(cat);
      setRuns(r);
      if (r.length > 0) setLastRun(r[0]);
    } catch (e) {
      setError(e.message);
    }
  };

  useEffect(() => { loadAll(); }, [chain.id]);

  const selectedSpec = catalog.find((c) => c.type === selectedType);

  const addBlock = async (e) => {
    e.preventDefault();
    setError("");
    if (!selectedType) return setError("Выберите блок из каталога");
    if (!newBlockName.trim()) return setError("Дайте блоку название");
    try {
      await api(`/api/chains/${chain.id}/blocks`, {
        method: "POST",
        body: { type: selectedType, name: newBlockName, params, position: blocks.length },
      });
      setNewBlockName("");
      setParams({});
      await loadAll();
    } catch (err) {
      setError(err.message);
    }
  };

  const deleteBlock = async (block) => {
    if (!confirm(`Удалить блок «${block.name}»?`)) return;
    try {
      await api(`/api/chains/${chain.id}/blocks/${block.id}`, { method: "DELETE" });
      await loadAll();
    } catch (err) {
      setError(err.message);
    }
  };

  const runChain = async () => {
    setError("");
    setMessage("");
    try {
      const run = await api(`/api/chains/${chain.id}/run`, { method: "POST" });
      setLastRun(run);
      setMessage(run.status === "success" ? "Цепочка выполнена ✅" : "Цепочка упала — смотрите лог");
      await loadAll();
    } catch (err) {
      setError(err.message);
    }
  };

  const testBlock = async (block) => {
    setError("");
    try {
      const res = await api(`/api/chains/${chain.id}/blocks/${block.id}/test`, {
        method: "POST",
        body: { input: {} },
      });
      setTestResults((prev) => ({ ...prev, [block.id]: res.output }));
    } catch (err) {
      setError(`Тест «${block.name}» упал: ${err.message}`);
    }
};

  
  const saveSchedule = async (cron) => {
    setError("");
    try {
      await api(`/api/chains/${chain.id}`, {
        method: "PATCH",
        body: { schedule: cron.trim() || null },
      });
      setMessage(cron.trim() ? `Расписание сохранено: ${cron}` : "Расписание удалено");
    } catch (err) {
      setError(err.message);
    }
  };

  const openRun = async (r) => {
    setError("");
    try {
      const full = await api(`/api/chains/${chain.id}/runs/${r.id}`);
      setSelectedRunId(r.id);
      setSelectedRun(full);
    } catch (err) {
      setError(err.message);
    }
  };

  const launchChain = async () => {
    setError("");
    try {
      const { run_id } = await api(`/api/chains/${chain.id}/run`, { method: "POST" });
      setActiveRunId(run_id);
      setLiveRun(null);
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    if (activeRunId === null) return;
    let stop = false;
    const poll = async () => {
      try {
        const r = await api(`/api/chains/${chain.id}/runs/${activeRunId}`);
        if (stop) return;
        setLiveRun(r);
        if (r.status !== "running") {
          setActiveRunId(null);
          loadAll();
        }
      } catch (e) {
        setActiveRunId(null);
        setError(e.message);
      }
    };
    poll();
    const timer = setInterval(poll, 1000);
    return () => { stop = true; clearInterval(timer); };
  }, [activeRunId]);

  const blockStatus = (blockId) => {
    if (!liveRun) return "pending";
    const logs = (liveRun.logs || []).filter((l) => l.block_id === blockId);
    if (!logs.length) return "pending";
    const last = logs[logs.length - 1];
    return last.stage;
  };

  return (
    <main>
      <button className="icon-btn" onClick={onBack}>← Назад к цепочкам</button>

      <section className="card">
        <h2>{chain.name}</h2>
        {chain.description && <p className="empty">{chain.description}</p>}
        <ScheduleEditor schedule={chain.schedule || ""} onChange={saveSchedule} />
        <p className="empty" style={{ fontSize: 12 }}>
          Примеры: <code>*/5 * * * *</code> — каждые 5 минут,{" "}
          <code>0 9 * * *</code> — ежедневно в 9:00,{" "}
          <code>0 9 * * 1-5</code> — по будням в 9:00. Оставьте пустым, чтобы цепочка
          запускалась только вручную.
        </p>  
      </section>

      <section className="card">
        <h2>Блоки цепочки</h2>
        {error && <p className="error">{error}</p>}
        {message && <p className="empty">{message}</p>}

        {blocks.length === 0 ? (
          <p className="empty">Блоков пока нет — добавьте первый ниже.</p>
        ) : (
          blocks.map((block, i) => (
            <div key={block.id} className="chain-row">
              <div>
                <strong>{i + 1}. {block.name}</strong>
                <span className="empty"> ({block.type})</span>
                <pre className="block-params">{JSON.stringify(block.params, null, 2)}</pre>
                {testResults[block.id] !== undefined && (
                  <details className="test-result">
                    <summary>Результат теста — нажмите, чтобы развернуть</summary>
                    <pre>{JSON.stringify(testResults[block.id], null, 2)}</pre>
                  </details>
                )}
              </div>
              <div>
                <button className="icon-btn" onClick={() => testBlock(block)}>Тест</button>
                <button className="icon-btn danger" onClick={() => deleteBlock(block)}>✕</button>
              </div>
            </div>
          ))
        )}

        <form onSubmit={addBlock} className="add-block-form">
          <h3>Добавить блок</h3>
          <select
            value={selectedType}
            onChange={(e) => { setSelectedType(e.target.value); setParams({}); }}
          >
            <option value="">— выберите из каталога —</option>
            {catalog.map((spec) => (
              <option key={spec.type} value={spec.type}>{spec.title}</option>
            ))}
          </select>
          {selectedSpec && (
            <>
              <p className="hint">{selectedSpec.description}</p>
              <input
                type="text"
                placeholder="Название блока"
                value={newBlockName}
                onChange={(e) => setNewBlockName(e.target.value)}
              />
              {Object.entries(selectedSpec.params).map(([key, label]) => (
                <input
                  key={key}
                  type="text"
                  placeholder={`${label} (${key})`}
                  value={params[key] || ""}
                  onChange={(e) => setParams({ ...params, [key]: e.target.value })}
                />
              ))}
              <button type="submit">Добавить блок</button>
            </>
          )}
        </form>

        <button onClick={launchChain} style={{ marginTop: 16, width: "100%" }}>
          ▶ Запустить цепочку
        </button>
      </section>
      {liveRun && (
        <section className="card">
          <h3>Выполнение {liveRun.status === "running" ? "…" : `— ${liveRun.status}`}</h3>
          {blocks.map((b) => {
            const st = blockStatus(b.id);
            const log = (liveRun.logs || []).filter((l) => l.block_id === b.id).pop();
            return (
              <div key={b.id} className={`live-step ${st}`}>
                <span className="step-status">
                  {st === "start" ? "⏳ выполняется" : st === "done" ? "✓ готово" : st === "error" ? "✕ ошибка" : "○ ожидает"}
                </span>
                <strong>{b.name}</strong>
                {st === "done" && log && <pre className="step-output">{log.message}</pre>}
                {st === "error" && log && <pre className="step-output err">{log.message}</pre>}
              </div>
            );
          })}
        </section>
      )}
      {lastRun && (
        <section className="card">
          <h2>Последний запуск — {lastRun.status === "success" ? "успех" : lastRun.status === "failed" ? "ошибка" : "выполняется"}</h2>
          <pre className="run-logs">
            {lastRun.logs.map((l) => `[${l.time}] ${l.level.toUpperCase()} ${l.block}: ${l.message}`).join("\n")}
          </pre> 
        </section>
      )}  

      {runs.length > 0 && (
        <section className="card">
          <h2>История запусков</h2>
          <ul>    
            {runs.map((r) => (
              <li key={r.id} className={`run-item ${r.id === selectedRunId ? "selected" : ""}`}
                  onClick={() => openRun(r)}>
                #{r.id} — {r.status === "success" ? "✅" : "❌"}{" "}
                {new Date(r.started_at).toLocaleString()}
              </li>
            ))}
          </ul>
          {selectedRun && (
            <details className="test-result" open>
              <summary>Логи запуска #{selectedRun.id} ({selectedRun.status})</summary>
              <pre className="run-logs">
                {(selectedRun.logs || [])
                  .map((l) => `[${l.time}] ${l.level.toUpperCase()} ${l.block}: ${l.message}`)
                  .join("\n")}
              </pre>
            </details>
          )}
        </section>
      )}
    </main>
  );
}
