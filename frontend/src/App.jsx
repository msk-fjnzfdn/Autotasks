import { useState, useEffect } from "react";
import AuthPage from "./AuthPage";
import ChainsPage from "./ChainsPage";
import ChainDetailPage from "./ChainDetailPage"
import { api } from "./api";
import ErrorBoundary from "./ErrorBoundary";

const API_URL = "http://localhost:8000";

export default function App() {
  const [backendStatus, setBackendStatus] = useState("проверяю...");
  const [user, setUser] = useState(null);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [selectedChain, setSelectedChain] = useState(null);
  
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      setCheckingAuth(false);
      return;
    }
    api("/api/chains/")
      .then(() => setUser({}))
      .catch(() => {})
      .finally(() => setCheckingAuth(false));
  }, []);

  useEffect(() => {
    checkBackend();
  }, []);

  async function checkBackend() {
    try {
      const res = await fetch(`${API_URL}/health`);
      if (!res.ok) throw new Error("network");
      const data = await res.json();
      setBackendStatus(`${data.status}`);
    } catch {
      setBackendStatus("недоступен");
    }
  }

  function logout() {
    localStorage.removeItem("token");
    setUser(null);
  }

  if (checkingAuth) {
    return <div className="loading">Проверка сессии...</div>;
  }

  if (!user) {
    return <AuthPage onAuth={() => setUser({})} />;
  }

  return (
    <div className="app">
      <header className="header">
        <h1 style={{ cursor: "pointer" }} onClick={() => setSelectedChain(null)}>
          Autotasks
        </h1>
        <div className="status">
          Бэкенд: <strong>{backendStatus}</strong>
        </div>
        <button onClick={logout} type="button">Выйти</button>
      </header>
      <ErrorBoundary>
        {selectedChain === null ? (
          <ChainsPage onOpenChain={(chain) => {console.log("Открываю цепочку:", chain); setSelectedChain(chain); }} />
        ) : (
          <ChainDetailPage chain={selectedChain} onBack={() => setSelectedChain(null)} />
        )}
      </ErrorBoundary>
    </div>
  );
}
