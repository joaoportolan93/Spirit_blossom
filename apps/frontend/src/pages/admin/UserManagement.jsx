import { useCallback, useEffect, useState } from "react";
import {
  Search,
  User,
  Eye,
  Ban,
  Check,
  Trash2,
  X,
  ChevronLeft,
  ChevronRight,
  ShieldAlert,
  Calendar,
  Clock,
} from "lucide-react";
import { useAuth } from "../../hooks/useAuth";
import {
  getAdminUserDetail,
  getAdminUsers,
  permanentlyDeleteAdminUser,
  updateAdminUserStatus,
} from "../../services/api";
import { ConfirmModal } from "../../components/admin/ConfirmModal";
import { BanUserModal } from "../../components/admin/BanUserModal";
import { PermanentDeleteModal } from "../../components/admin/PermanentDeleteModal";

export function UserManagement() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [hasNextPage, setHasNextPage] = useState(false);
  const [loading, setLoading] = useState(true);

  const [selectedUser, setSelectedUser] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalLoading, setModalLoading] = useState(false);

  const [banModalUser, setBanModalUser] = useState(null);
  const [deleteModalUser, setDeleteModalUser] = useState(null);
  const [confirmState, setConfirmState] = useState({
    open: false,
    title: "",
    message: "",
    onConfirm: null,
    variant: "default",
  });

  const fetchUsers = useCallback(async (searchTerm = "", statusVal = "", pageNum = 1) => {
    setLoading(true);
    try {
      const data = await getAdminUsers({
        search: searchTerm,
        status: statusVal,
        page: pageNum,
      });
      const list = Array.isArray(data) ? data : data?.results || [];
      setUsers(list);
      setHasNextPage(Boolean(data?.has_next));
    } catch (err) {
      console.error("Erro ao buscar usuários:", err);
      setUsers([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers(search, statusFilter, page);
  }, [statusFilter, page]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSearch = (e) => {
    e.preventDefault();
    setPage(1);
    fetchUsers(search, statusFilter, 1);
  };

  const openInspectModal = async (userId) => {
    setModalOpen(true);
    setModalLoading(true);
    setSelectedUser(null);
    try {
      const detail = await getAdminUserDetail(userId);
      setSelectedUser(detail);
    } catch (err) {
      console.error("Erro ao inspecionar usuário:", err);
    } finally {
      setModalLoading(false);
    }
  };

  const handleConfirmBan = async (userId, reason, durationDays, preserveForAuthorities) => {
    const res = await updateAdminUserStatus(userId, {
      status: "suspended",
      reason,
      duration_days: durationDays,
      preserve_for_authorities: preserveForAuthorities,
    });
    const updatedUser = res?.user;
    setUsers((prev) =>
      prev.map((u) =>
        u.id === userId ? updatedUser || { ...u, status: "suspended", ban_reason: reason } : u
      )
    );
    if (selectedUser?.id === userId && updatedUser) {
      setSelectedUser((prev) => ({ ...prev, ...updatedUser }));
    }
    setBanModalUser(null);
  };

  const handleRequestUnban = (u) => {
    setConfirmState({
      open: true,
      title: "Reativar Usuário",
      message: `Deseja restaurar a conta @${u.username}? O acesso e visibilidade serão restaurados imediatamente.`,
      variant: "default",
      onConfirm: async () => {
        try {
          const res = await updateAdminUserStatus(u.id, { status: "active" });
          const updatedUser = res?.user;
          setUsers((prev) =>
            prev.map((item) =>
              item.id === u.id
                ? updatedUser || { ...item, status: "active", ban_reason: "" }
                : item
            )
          );
          if (selectedUser?.id === u.id && updatedUser) {
            setSelectedUser((prev) => ({ ...prev, ...updatedUser }));
          }
        } catch (err) {
          console.error("Erro ao desbanir usuário:", err);
        } finally {
          setConfirmState((s) => ({ ...s, open: false }));
        }
      },
    });
  };

  const handleConfirmPermanentDelete = async (userId, username) => {
    await permanentlyDeleteAdminUser(userId, username);
    setUsers((prev) => prev.filter((u) => u.id !== userId));
    if (selectedUser?.id === userId) {
      setSelectedUser(null);
      setModalOpen(false);
    }
    setDeleteModalUser(null);
  };

  const renderStatusBadge = (u) => {
    if (!u) return null;
    if (u.status === "active") {
      return (
        <span className="px-2 py-0.5 text-xs font-medium bg-emerald-500/15 text-emerald-400 rounded-full">
          Ativo
        </span>
      );
    }
    if (u.status === "suspended") {
      return (
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="px-2 py-0.5 text-xs font-medium bg-rose-500/15 text-rose-400 rounded-full">
            {u.appeal_days_remaining !== null && u.appeal_days_remaining !== undefined
              ? `Banido (${u.appeal_days_remaining}d)`
              : "Suspenso"}
          </span>
          {u.preserve_for_authorities && (
            <span className="px-1.5 py-0.5 text-[10px] font-bold bg-amber-500/20 text-amber-300 rounded border border-amber-500/30">
              AUTORIDADES
            </span>
          )}
        </div>
      );
    }
    return (
      <span className="px-2 py-0.5 text-xs font-medium bg-zinc-700 text-zinc-300 rounded-full">
        Desativado
      </span>
    );
  };

  const statusTabs = [
    { value: "", label: "Todos" },
    { value: "active", label: "Ativos" },
    { value: "suspended", label: "Suspensos" },
    { value: "deactivated", label: "Desativados" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white">Gestão de Usuários</h1>
        <p className="text-zinc-400 mt-1 text-sm">{users.length} usuário(s) exibido(s)</p>
      </div>

      <form onSubmit={handleSearch} className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-500" size={16} />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por username, e-mail ou nome..."
            className="w-full bg-zinc-900 border border-zinc-800 rounded-xl pl-10 pr-4 py-2.5 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-pink-500"
          />
        </div>
        <button
          type="submit"
          className="bg-pink-600 hover:bg-pink-500 text-white font-semibold px-5 py-2.5 rounded-xl text-sm transition"
        >
          Buscar
        </button>
      </form>

      <div className="flex gap-1 bg-zinc-900 rounded-xl p-1 border border-zinc-800 w-fit">
        {statusTabs.map((tab) => (
          <button
            key={tab.value}
            type="button"
            onClick={() => {
              setStatusFilter(tab.value);
              setPage(1);
            }}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition ${
              statusFilter === tab.value
                ? "bg-pink-600 text-white"
                : "text-zinc-400 hover:text-white hover:bg-zinc-800"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="bg-zinc-900 rounded-2xl border border-zinc-800 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-zinc-800 text-xs text-zinc-400 uppercase">
                <th className="p-4">Usuário</th>
                <th className="p-4">E-mail</th>
                <th className="p-4">Status</th>
                <th className="p-4">Cadastro</th>
                <th className="p-4">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/70">
              {loading ? (
                <tr>
                  <td colSpan="5" className="p-8 text-center">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pink-500 mx-auto" />
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan="5" className="p-8 text-center text-zinc-500 text-sm">
                    Nenhum usuário encontrado.
                  </td>
                </tr>
              ) : (
                users.map((u) => {
                  const isSelf =
                    currentUser &&
                    (String(u.id) === String(currentUser.id) ||
                      u.username === currentUser.username);
                  return (
                    <tr key={u.id} className="hover:bg-zinc-800/40 transition">
                      <td className="p-4">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-full bg-zinc-800 flex items-center justify-center text-zinc-300 overflow-hidden shrink-0">
                            {u.avatar ? (
                              <img src={u.avatar} alt="" className="w-full h-full object-cover" />
                            ) : (
                              <User size={15} />
                            )}
                          </div>
                          <div>
                            <div className="flex items-center gap-1.5">
                              <p className="text-sm font-medium text-white">
                                {u.display_name || `@${u.username}`}
                              </p>
                              {isSelf && (
                                <span className="px-1.5 py-0.5 text-[10px] font-semibold bg-sky-500/20 text-sky-400 rounded">
                                  Você
                                </span>
                              )}
                            </div>
                            <p className="text-xs text-zinc-500">@{u.username}</p>
                          </div>
                        </div>
                      </td>
                      <td className="p-4 text-xs font-mono text-zinc-400">{u.email}</td>
                      <td className="p-4">{renderStatusBadge(u)}</td>
                      <td className="p-4 text-xs font-mono text-zinc-400">
                        {new Date(u.date_joined).toLocaleDateString("pt-BR")}
                      </td>
                      <td className="p-4">
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => openInspectModal(u.id)}
                            className="p-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-lg transition"
                            title="Inspecionar"
                          >
                            <Eye size={14} />
                          </button>
                          {isSelf ? (
                            <span className="text-[11px] text-zinc-500 italic px-2">Sua conta</span>
                          ) : u.status === "active" ? (
                            <button
                              type="button"
                              data-testid={`ban-btn-${u.username}`}
                              onClick={() => setBanModalUser(u)}
                              className="p-2 bg-rose-500/15 hover:bg-rose-500/25 text-rose-400 rounded-lg transition"
                              title="Suspender / Banir"
                            >
                              <Ban size={14} />
                            </button>
                          ) : (
                            <>
                              <button
                                type="button"
                                data-testid={`unban-btn-${u.username}`}
                                onClick={() => handleRequestUnban(u)}
                                className="p-2 bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-400 rounded-lg transition"
                                title="Reativar usuário"
                              >
                                <Check size={14} />
                              </button>
                              {u.status === "suspended" && (
                                <button
                                  type="button"
                                  data-testid={`delete-user-btn-${u.username}`}
                                  onClick={() => setDeleteModalUser(u)}
                                  className="p-2 bg-rose-600/20 hover:bg-rose-600/35 text-rose-400 rounded-lg transition"
                                  title="Excluir definitivamente"
                                >
                                  <Trash2 size={14} />
                                </button>
                              )}
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {!loading && (users.length > 0 || page > 1) && (
        <div className="flex items-center justify-between">
          <span className="text-zinc-500 text-sm">Página {page}</span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="p-2 bg-zinc-900 border border-zinc-800 text-zinc-300 rounded-lg disabled:opacity-30"
            >
              <ChevronLeft size={14} />
            </button>
            <button
              type="button"
              onClick={() => setPage((p) => p + 1)}
              disabled={!hasNextPage}
              className="p-2 bg-zinc-900 border border-zinc-800 text-zinc-300 rounded-lg disabled:opacity-30"
            >
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      )}

      {/* Modal de inspeção */}
      {modalOpen && (
        <div
          className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4"
          onClick={() => setModalOpen(false)}
        >
          <div
            className="bg-zinc-900 rounded-2xl border border-zinc-800 w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-center p-4 border-b border-zinc-800">
              <h2 className="text-lg font-bold text-white">Detalhes da Conta</h2>
              <button
                type="button"
                aria-label="Fechar"
                onClick={() => setModalOpen(false)}
                className="text-zinc-400 hover:text-white"
              >
                <X size={18} />
              </button>
            </div>
            <div className="p-6 overflow-y-auto space-y-5">
              {modalLoading ? (
                <div className="flex justify-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pink-500" />
                </div>
              ) : selectedUser ? (
                <>
                  <div className="flex items-center gap-4">
                    <div className="w-16 h-16 rounded-full bg-zinc-800 flex items-center justify-center overflow-hidden">
                      {selectedUser.avatar ? (
                        <img
                          src={selectedUser.avatar}
                          alt=""
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <User size={24} className="text-zinc-400" />
                      )}
                    </div>
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="text-lg font-bold text-white">
                          {selectedUser.display_name || `@${selectedUser.username}`}
                        </h3>
                        {renderStatusBadge(selectedUser)}
                        {selectedUser.is_staff && (
                          <span className="px-2 py-0.5 text-xs bg-pink-500/20 text-pink-400 rounded-full flex items-center gap-1">
                            <ShieldAlert size={11} /> Staff
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-zinc-400">@{selectedUser.username} · {selectedUser.email}</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="bg-zinc-950 rounded-xl p-3 border border-zinc-800">
                      <p className="text-xs text-zinc-500">Posts</p>
                      <p className="text-xl font-bold text-white font-mono">{selectedUser.posts_count ?? 0}</p>
                    </div>
                    <div className="bg-zinc-950 rounded-xl p-3 border border-zinc-800">
                      <p className="text-xs text-zinc-500">Seguidores</p>
                      <p className="text-xl font-bold text-white font-mono">{selectedUser.followers_count ?? 0}</p>
                    </div>
                    <div className="bg-zinc-950 rounded-xl p-3 border border-zinc-800">
                      <p className="text-xs text-zinc-500">Seguindo</p>
                      <p className="text-xl font-bold text-white font-mono">{selectedUser.following_count ?? 0}</p>
                    </div>
                    <div className="bg-zinc-950 rounded-xl p-3 border border-zinc-800">
                      <p className="text-xs text-zinc-500">Denúncias</p>
                      <p className="text-xl font-bold text-white font-mono">{selectedUser.reports_received ?? 0}</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                    <div className="bg-zinc-950 rounded-xl p-3 border border-zinc-800 flex items-center gap-2.5">
                      <Calendar size={14} className="text-zinc-500" />
                      <div>
                        <p className="text-zinc-500">Cadastro</p>
                        <p className="text-white font-mono">
                          {new Date(selectedUser.date_joined).toLocaleDateString("pt-BR")}
                        </p>
                      </div>
                    </div>
                    <div className="bg-zinc-950 rounded-xl p-3 border border-zinc-800 flex items-center gap-2.5">
                      <Clock size={14} className="text-zinc-500" />
                      <div>
                        <p className="text-zinc-500">Último login</p>
                        <p className="text-white font-mono">
                          {selectedUser.last_login
                            ? new Date(selectedUser.last_login).toLocaleString("pt-BR")
                            : "—"}
                        </p>
                      </div>
                    </div>
                  </div>

                  {selectedUser.status === "suspended" && (
                    <div className="bg-rose-950/30 border border-rose-500/30 rounded-xl p-4 text-xs space-y-1">
                      <p className="font-bold text-rose-400">Informações da Suspensão / Banimento</p>
                      <p className="text-zinc-300">Motivo: {selectedUser.ban_reason || "—"}</p>
                      {selectedUser.banned_by && (
                        <p className="text-zinc-400">Aplicado por: @{selectedUser.banned_by}</p>
                      )}
                      {selectedUser.ban_expires_at && (
                        <p className="text-zinc-400">
                          Expira em: {new Date(selectedUser.ban_expires_at).toLocaleString("pt-BR")}
                        </p>
                      )}
                    </div>
                  )}
                </>
              ) : null}
            </div>
          </div>
        </div>
      )}

      <ConfirmModal
        variant={confirmState.variant}
        title={confirmState.title}
        message={confirmState.message}
        isOpen={confirmState.open}
        onConfirm={confirmState.onConfirm}
        onCancel={() => setConfirmState((s) => ({ ...s, open: false }))}
      />

      <BanUserModal
        isOpen={!!banModalUser}
        user={banModalUser}
        onConfirm={handleConfirmBan}
        onCancel={() => setBanModalUser(null)}
      />

      <PermanentDeleteModal
        isOpen={!!deleteModalUser}
        user={deleteModalUser}
        onConfirm={handleConfirmPermanentDelete}
        onCancel={() => setDeleteModalUser(null)}
      />
    </div>
  );
}

export default UserManagement;
