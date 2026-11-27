import React, { useEffect, useState } from "react";
import {
  ShieldAlert,
  UserX,
  Search,
  Plus,
  Lock,
  Unlock,
  AlertTriangle,
  X,
  CheckCircle2,
  Clock,
  User,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

interface BlockedPerson {
  id: string;
  full_name: string;
  identifier: string;
  reason: string;
  blocked_by_name?: string;
  is_active: boolean;
  blocked_at: string;
  unblocked_at?: string;
  unblocked_reason?: string;
}

export function BlockedPage() {
  const [blockedList, setBlockedList] = useState<BlockedPerson[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);

  // Modal block states
  const [showBlockModal, setShowBlockModal] = useState(false);
  const [fullName, setFullName] = useState("");
  const [identifier, setIdentifier] = useState("");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Modal unblock states
  const [unblockTarget, setUnblockTarget] = useState<BlockedPerson | null>(null);
  const [unblockReason, setUnblockReason] = useState("");

  const loadBlocked = () => {
    setLoading(true);
    apiFetch<BlockedPerson[]>(`/api/v1/blocked-persons?include_inactive=${includeInactive}`)
      .then((data) => setBlockedList(data))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadBlocked();
  }, [includeInactive]);

  const handleBlock = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName || !identifier || !reason) {
      alert("Preencha todos os campos obrigatórios.");
      return;
    }
    setSubmitting(true);
    try {
      await apiFetch("/api/v1/blocked-persons", {
        method: "POST",
        body: JSON.stringify({
          full_name: fullName.trim(),
          identifier: identifier.trim().toUpperCase(),
          reason: reason.trim(),
        }),
      });
      setShowBlockModal(false);
      setFullName("");
      setIdentifier("");
      setReason("");
      loadBlocked();
    } catch (err: any) {
      alert(err.message || "Falha ao bloquear pessoa.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleUnblock = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!unblockTarget) return;
    setSubmitting(true);
    try {
      await apiFetch(`/api/v1/blocked-persons/${unblockTarget.id}/unblock`, {
        method: "POST",
        body: JSON.stringify({ reason: unblockReason.trim() }),
      });
      setUnblockTarget(null);
      setUnblockReason("");
      loadBlocked();
    } catch (err: any) {
      alert(err.message || "Falha ao desbloquear pessoa.");
    } finally {
      setSubmitting(false);
    }
  };

  const filtered = blockedList.filter((b) => {
    const s = search.toLowerCase();
    return (
      b.full_name.toLowerCase().includes(s) ||
      b.identifier.toLowerCase().includes(s) ||
      b.reason.toLowerCase().includes(s)
    );
  });

  return (
    <div className="space-y-6">
      {/* Top Banner & Title */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="rounded-lg bg-rose-500/10 p-2 text-rose-500">
              <ShieldAlert className="h-6 w-6" />
            </div>
            <div>
              <h2 className="text-base sm:text-lg font-bold text-foreground">
                Lista de Usuários Bloqueados (Blacklist)
              </h2>
              <p className="text-xs text-muted-foreground">
                Bloqueio administrativo com precedência máxima: rejeição imediata em qualquer totem
              </p>
            </div>
          </div>
        </div>

        <button
          onClick={() => setShowBlockModal(true)}
          className="flex items-center gap-2 rounded-lg bg-rose-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-rose-700 transition-colors self-start sm:self-auto"
        >
          <Plus className="h-4 w-4" />
          Bloquear Pessoa
        </button>
      </div>

      {/* Rules Notice */}
      <div className="rounded-xl border border-rose-500/20 bg-rose-500/5 p-4 text-xs text-rose-300 space-y-1">
        <p className="font-semibold flex items-center gap-1.5 text-rose-400">
          <AlertTriangle className="h-4 w-4" />
          Regra de Precedência Absoluta
        </p>
        <p>
          Qualquer indivíduo (funcionário ativo, terceiro ou visitante) cujo documento (CPF, matrícula ou crachá)
          ou correspondência facial constar como <strong>ativo</strong> nesta lista terá seu acesso
          <strong> negado imediatamente no totem</strong> com sinal sonoro e visual vermelho.
        </p>
      </div>

      {/* Search and Filters */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Filtrar por nome, documento ou motivo..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-lg border bg-card pl-9 pr-4 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        <label className="flex items-center gap-2 text-xs font-medium text-muted-foreground cursor-pointer select-none">
          <input
            type="checkbox"
            checked={includeInactive}
            onChange={(e) => setIncludeInactive(e.target.checked)}
            className="rounded border-muted-foreground/30 text-primary focus:ring-primary h-4 w-4"
          />
          Exibir histórico de desbloqueados
        </label>
      </div>

      {/* List / Table */}
      <div className="rounded-xl border bg-card shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm whitespace-nowrap">
            <thead className="border-b bg-muted/50 text-xs font-semibold uppercase text-muted-foreground">
              <tr>
                <th className="px-4 sm:px-6 py-3">Pessoa Bloqueada</th>
                <th className="px-4 sm:px-6 py-3">Documento / ID</th>
                <th className="px-4 sm:px-6 py-3">Motivo do Bloqueio</th>
                <th className="px-4 sm:px-6 py-3">Data Bloqueio</th>
                <th className="px-4 sm:px-6 py-3">Status</th>
                <th className="px-4 sm:px-6 py-3 text-right">Ação</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-muted-foreground text-xs">
                    Carregando lista de bloqueados...
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-muted-foreground text-xs">
                    Nenhuma pessoa bloqueada encontrada.
                  </td>
                </tr>
              ) : (
                filtered.map((item) => (
                  <tr key={item.id} className="hover:bg-muted/40 transition-colors">
                    <td className="px-4 sm:px-6 py-4">
                      <div className="flex items-center gap-2.5">
                        <div
                          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                            item.is_active
                              ? "bg-rose-500/10 text-rose-500"
                              : "bg-muted text-muted-foreground"
                          }`}
                        >
                          <UserX className="h-4 w-4" />
                        </div>
                        <div>
                          <div className="font-medium text-foreground">{item.full_name}</div>
                          {item.blocked_by_name && (
                            <div className="text-[11px] text-muted-foreground">
                              Por: {item.blocked_by_name}
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 sm:px-6 py-4">
                      <span className="font-mono text-xs font-semibold bg-muted px-2 py-1 rounded">
                        {item.identifier}
                      </span>
                    </td>
                    <td className="px-4 sm:px-6 py-4 max-w-xs truncate text-xs text-muted-foreground">
                      <span title={item.reason} className="text-foreground font-medium">
                        {item.reason}
                      </span>
                    </td>
                    <td className="px-4 sm:px-6 py-4 text-xs text-muted-foreground">
                      {new Date(item.blocked_at).toLocaleString("pt-BR")}
                    </td>
                    <td className="px-4 sm:px-6 py-4">
                      {item.is_active ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-rose-500/10 px-2.5 py-1 text-xs font-medium text-rose-500">
                          <Lock className="h-3 w-3" />
                          Bloqueado
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-500">
                          <Unlock className="h-3 w-3" />
                          Desbloqueado
                        </span>
                      )}
                    </td>
                    <td className="px-4 sm:px-6 py-4 text-right">
                      {item.is_active ? (
                        <button
                          onClick={() => setUnblockTarget(item)}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted transition-colors"
                        >
                          <Unlock className="h-3.5 w-3.5 text-muted-foreground" />
                          Desbloquear
                        </button>
                      ) : (
                        <span className="text-[11px] text-muted-foreground italic">
                          {item.unblocked_reason || "Desbloqueado"}
                        </span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal: Bloquear Pessoa */}
      {showBlockModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl border bg-card p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <div className="flex items-center gap-2">
                <div className="rounded-lg bg-rose-500/10 p-1.5 text-rose-500">
                  <UserX className="h-5 w-5" />
                </div>
                <h3 className="font-semibold text-foreground">Bloquear Pessoa</h3>
              </div>
              <button
                onClick={() => setShowBlockModal(false)}
                className="rounded-lg p-1 text-muted-foreground hover:bg-muted"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleBlock} className="space-y-4">
              <div>
                <label className="text-xs font-medium text-muted-foreground">
                  Nome Completo *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Ex: João da Silva"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground focus:ring-2 focus:ring-primary"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground">
                  Documento ou Identificador (CPF / Matrícula / RG) *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Ex: 123.456.789-00 ou MAT-998"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground font-mono focus:ring-2 focus:ring-primary"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground">
                  Justificativa / Motivo do Bloqueio *
                </label>
                <textarea
                  required
                  rows={3}
                  placeholder="Ex: Ex-funcionário em aviso de restrição de acesso / Determinação administrativa"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground focus:ring-2 focus:ring-primary"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowBlockModal(false)}
                  className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-medium text-white hover:bg-rose-700 disabled:opacity-50"
                >
                  {submitting ? "Bloqueando..." : "Confirmar Bloqueio"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Desbloquear Pessoa */}
      {unblockTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl border bg-card p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <div className="flex items-center gap-2">
                <div className="rounded-lg bg-emerald-500/10 p-1.5 text-emerald-500">
                  <Unlock className="h-5 w-5" />
                </div>
                <h3 className="font-semibold text-foreground">Desbloquear Acesso</h3>
              </div>
              <button
                onClick={() => setUnblockTarget(null)}
                className="rounded-lg p-1 text-muted-foreground hover:bg-muted"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <p className="text-xs text-muted-foreground">
              Você está prestes a restabelecer as permissões de acesso para{" "}
              <strong className="text-foreground">{unblockTarget.full_name}</strong> (Doc:{" "}
              <span className="font-mono">{unblockTarget.identifier}</span>).
            </p>

            <form onSubmit={handleUnblock} className="space-y-4">
              <div>
                <label className="text-xs font-medium text-muted-foreground">
                  Motivo da Liberação / Desbloqueio (Opcional)
                </label>
                <input
                  type="text"
                  placeholder="Ex: Regularização de pendência administrativa"
                  value={unblockReason}
                  onChange={(e) => setUnblockReason(e.target.value)}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground focus:ring-2 focus:ring-primary"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setUnblockTarget(null)}
                  className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                >
                  {submitting ? "Liberando..." : "Confirmar Desbloqueio"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
