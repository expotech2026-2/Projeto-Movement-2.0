import { useState } from "react";
import { login } from "../services/movementApi";
import { Icon } from "./Icon";
import { ThermalScale } from "./ThermalScale";

const FACTS = [
  { icon: "people", text: "Conta quem entra e sai pela porta da sala." },
  { icon: "temp", text: "Mede a temperatura e a umidade a cada leitura." },
  { icon: "snow", text: "Liga, ajusta e desliga o ar pelo infravermelho." },
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
        <h1>Ar-condicionado automático para salas de aula.</h1>
        <p>
          A sala fica entre 20 e 23 °C enquanto há gente e o ar desliga quando
          ela esvazia.
        </p>
        <div className="login-demo">
          <div className="login-demo__head">
            <strong>Sala em aula</strong>
            <span className="badge success">Exemplo</span>
          </div>
          <ThermalScale
            inside={22.4}
            outside={31}
            target={22}
            value="22,4"
            detail="Alvo do ar: 22 °C, com 24 pessoas na sala"
          />
        </div>
        <ul className="login-facts">
          {FACTS.map((fact) => (
            <li key={fact.text}>
              <Icon name={fact.icon} size={22} />
              {fact.text}
            </li>
          ))}
        </ul>
      </aside>
      <main className="operator-login__main">
        <form
          className="panel panel--padded operator-login__form"
          onSubmit={handleSubmit}
        >
          <span className="brand">
            <img src="/logo.svg" width={44} height={44} alt="" />
            movement
          </span>
          <h2>Acessar o Movement</h2>
          <p>Entre para acompanhar as salas e comandar o ar-condicionado.</p>
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
          <p className="sr-only" role="status">
            {busy ? "Entrando no painel" : ""}
          </p>
          <button className="btn btn--primary" type="submit" disabled={busy}>
            {busy ? "Entrando..." : "Entrar no painel"}
          </button>
        </form>
      </main>
    </div>
  );
}
