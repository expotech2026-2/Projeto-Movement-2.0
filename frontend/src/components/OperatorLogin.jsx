import { useState } from "react";
import { login } from "../services/movementApi";

const FACTS = [
  "Conta quem entra e sai pela porta da sala.",
  "Mede a temperatura e a umidade a cada leitura.",
  "Liga, ajusta e desliga o ar pelo infravermelho.",
];

export function OperatorLogin({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const user = await login(username, password);
      setPassword("");
      onLogin(user);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="operator-login">
      <aside className="login-story">
        <span className="brand">
          <img src="/logo.svg" width={32} height={32} alt="" />
          movement
        </span>
        <div>
          <h2>Ar-condicionado automático para salas de aula.</h2>
          <p>
            A sala fica entre 20 e 23 °C enquanto há gente e o ar desliga quando
            ela esvazia.
          </p>
        </div>
        <ul className="login-facts">
          {FACTS.map((fact) => (
            <li key={fact}>{fact}</li>
          ))}
        </ul>
      </aside>
      <main className="operator-login__main">
        <form
          className="panel panel--padded operator-login__form"
          onSubmit={handleSubmit}
        >
          <h1>Acessar o Movement</h1>
          <p>Entre para acompanhar seu ambiente.</p>
          <label htmlFor="operator-username">Usuário</label>
          <input
            id="operator-username"
            autoComplete="username"
            required
            maxLength={120}
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
          <label htmlFor="operator-password">Senha</label>
          <input
            id="operator-password"
            type="password"
            autoComplete="current-password"
            required
            maxLength={256}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          {error && <p role="alert">{error}</p>}
          <button className="btn btn--primary" type="submit" disabled={busy}>
            {busy ? "Entrando..." : "Entrar"}
          </button>
        </form>
      </main>
    </div>
  );
}
