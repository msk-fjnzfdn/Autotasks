import { useEffect, useState } from "react";
import { api } from "./api";

export default function ChainsPage({ onOpenChain }) {
  const [chains, setChains] = useState([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const loadChains = async () => {
    try {
      setLoading(true);
      setChains(await api("/api/chains/"));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadChains(); }, []);

  const createChain = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await api("/api/chains/", {
        method: "POST",
        body: { name, description: description || null, is_active: true },
      });
      setName("");
      setDescription("");
      await loadChains();
    } catch (err) {
      setError(err.message);
    }
  };

  const renameChain = async (chain) => {
    const newName = prompt("Новое название цепочки:", chain.name);
    if (!newName || newName === chain.name) return;
    try {
      await api(`/api/chains/${chain.id}`, { method: "PATCH", body: { name: newName } });
      await loadChains();
    } catch (err) {
      setError(err.message);
    }
  };

  const deleteChain = async (chain) => {
    if (!confirm(`Удалить цепочку «${chain.name}»? Вместе с ней удалятся все блоки и история запусков.`)) return;
    try {
      await api(`/api/chains/${chain.id}`, { method: "DELETE" });
      await loadChains();
    } catch (err) {
      setError(err.message);
    }
  };

  const toggleActive = async (chain) => {
    try {
      await api(`/api/chains/${chain.id}`, {
        method: "PATCH",
        body: { is_active: !chain.is_active },
      });
      setChains(chains.map((c) =>
        c.id === chain.id ? { ...c, is_active: !c.is_active } : c
      ));
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <main>
      <section className="card">
        <h2>Создать цепочку</h2>
        <form onSubmit={createChain}>
          <input
            type="text"
            placeholder="Название цепочки"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
          <input
            type="text"
            placeholder="Описание (необязательно)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <button type="submit">Создать</button>
        </form>
      </section>

      <section className="card">
        <h2>Мои цепочки</h2>
        {error && <p className="error">{error}</p>}
        {loading ? (
          <p className="empty">Загрузка…</p>
        ) : chains.length === 0 ? (
          <p className="empty">Пока пусто. Создай первую цепочку выше.</p>
        ) : (
          <ul>
            {chains.map((chain) => (
              <li key={chain.id} className={chain.is_active ? "" : "muted"}>
                <strong>{chain.name}</strong>
                {chain.description && <span> — {chain.description}</span>}
                <span className={`badge ${chain.is_active ? "active" : ""}`}>
                  {chain.is_active ? "активна" : "выключена"}
                </span>
                <button
                  className={`switch ${chain.is_active ? "on" : "off"}`}
                  title={chain.is_active ? "Активна — нажмите, чтобы выключить" : "Неактивна — нажмите, чтобы включить"}
                  onClick={() => toggleActive(chain)}
                >
                  <span className="knob" />
                </button>
                <button className="icon-btn" onClick={() => onOpenChain(chain)}>Открыть</button>
                <button className="icon-btn" onClick={() => renameChain(chain)}>✎</button>
                <button className="icon-btn danger" onClick={() => deleteChain(chain)}>✕</button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}

