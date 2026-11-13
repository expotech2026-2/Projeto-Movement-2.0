import { useCallback, useEffect, useState } from "react";

import { ROLES } from "../config/catalog";
import { Icon } from "./Icon";
import { request } from "../services/movementApi";
import { ManagementForm } from "./ManagementForms";

export function UsersView({ currentUser, onNotice }) {
  const [users, setUsers] = useState(null);
  const [editing, setEditing] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(
    () =>
      request("/users")
        .then(setUsers)
        .catch((error) => {
          setUsers([]);
          onNotice(error.message);
        }),
    [onNotice],
  );
  useEffect(() => {
    load();
  }, [load]);
  async function save(values) {
    const payload = {
      full_name: values.full_name,
      role: values.role,
      active: values.active,
      ...(values.password ? { password: values.password } : {}),
    };
    if (editing.item) {
      await request(`/users/${editing.item.id}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
    } else {
      await request("/users", {
        method: "POST",
        body: JSON.stringify({ ...payload, username: values.username }),
      });
    }
    await load();
    onNotice("Usuário salvo com sucesso.");
  }
  async function remove(user) {
    if (!window.confirm(`Excluir o acesso de ${user.full_name}?`)) return;
    setBusy(true);
    try {
      await request(`/users/${user.id}`, { method: "DELETE" });
      await load();
      onNotice("Usuário excluído.");
    } catch (error) {
      onNotice(error.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="section-heading">
        <div>
          <h2>
            Usuários <span className="count">{users?.length ?? "…"}</span>
          </h2>
          <p className="muted">
            Professores consultam salas, leituras e relatórios. Administradores
            também alteram cadastros e usuários.
          </p>
        </div>
        <button
          className="button primary"
          onClick={() => setEditing({ type: "user" })}
        >
          <Icon name="plus" size={16} /> Novo usuário
        </button>
      </div>
      <div className="notice info">
        {currentUser.builtin
          ? `Você está usando o administrador principal (${currentUser.username}), definido na configuração do servidor. Ele não aparece nesta lista.`
          : "O administrador principal é definido na configuração do servidor e não aparece nesta lista."}
      </div>
      {users === null ? (
        <div className="empty-state">Carregando usuários…</div>
      ) : !users.length ? (
        <div className="empty-state">
          <h3>Nenhum usuário cadastrado</h3>
          <p>Cadastre professores e outros administradores.</p>
        </div>
      ) : (
        <div className="table-wrap panel">
          <table>
            <thead>
              <tr>
                <th>Nome</th>
                <th>Login</th>
                <th>Perfil</th>
                <th>Situação</th>
                <th>Desde</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td>
                    <strong>{user.full_name}</strong>
                  </td>
                  <td>{user.username}</td>
                  <td>
                    <span className={`role-badge role-badge--${user.role}`}>
                      {ROLES[user.role]}
                    </span>
                  </td>
                  <td>
                    <span
                      className={`badge ${user.active ? "success" : "warning"}`}
                    >
                      {user.active ? "Ativo" : "Inativo"}
                    </span>
                  </td>
                  <td>
                    {new Date(user.created_at).toLocaleDateString("pt-BR")}
                  </td>
                  <td>
                    <button
                      className="text-button"
                      onClick={() => setEditing({ type: "user", item: user })}
                    >
                      Editar
                    </button>
                    <button
                      className="text-button danger"
                      disabled={busy}
                      onClick={() => remove(user)}
                    >
                      Excluir
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {editing && (
        <ManagementForm
          key={editing.item?.id || "novo-usuario"}
          editing={editing}
          onSave={save}
          onClose={() => setEditing(null)}
        />
      )}
    </>
  );
}
