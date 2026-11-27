import React, { useEffect, useState } from "react";
import { MonitorDot, Plus, Key, CheckCircle, AlertTriangle, X } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface Terminal {
  id: string;
  code: string;
  name: string;
  unit_id: string;
  terminal_type: string;
  status: string;
  last_seen_at?: string;
  last_ip?: string;
}

export function TerminalsPage() {
  const [terminals, setTerminals] = useState<Terminal[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [units, setUnits] = useState<{ id: string; name: string }[]>([]);
  const [unitId, setUnitId] = useState("");

  const loadTerminals = () => {
    setLoading(true);
    apiFetch<Terminal[]>("/api/v1/terminals")
      .then((data) => setTerminals(data))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadTerminals();
    apiFetch<{ id: string; name: string }[]>("/api/v1/organization/units")
      .then((u) => {
        setUnits(u);
        if (u.length > 0) setUnitId(u[0].id);
      })
      .catch(console.error);
  }, []);

  const handleCreateTerminal = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiFetch("/api/v1/terminals", {
        method: "POST",
        body: JSON.stringify({ code, name, unit_id: unitId }),
      });
      setShowCreateModal(false);
      setCode("");
      setName("");
      loadTerminals();
    } catch (err: any) {
      alert(err.message);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Terminais e Totens de Acesso</h2>
          <p className="text-xs text-muted-foreground">Dispositivos autorizados a operar em modo kiosk local</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          Novo Terminal
        </button>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {loading ? (
          <p className="text-sm text-muted-foreground">Carregando terminais...</p>
        ) : terminals.length === 0 ? (
          <div className="col-span-full rounded-xl border bg-card p-8 text-center text-muted-foreground">
            Nenhum terminal cadastrado.
          </div>
        ) : (
          terminals.map((term) => (
            <div key={term.id} className="rounded-xl border bg-card p-5 shadow-sm space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="rounded-lg bg-primary/10 p-2 text-primary">
                    <MonitorDot className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-foreground text-sm">{term.name}</h3>
                    <p className="font-mono text-xs text-muted-foreground">{term.code}</p>
                  </div>
                </div>
                <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                  term.status === "active" ? "bg-emerald-500/10 text-emerald-600" : "bg-amber-500/10 text-amber-600"
                }`}>
                  {term.status === "active" ? "Ativo" : "Pendente"}
                </span>
              </div>

              <div className="border-t pt-3 text-xs text-muted-foreground space-y-1">
                <div>Tipo: <span className="text-foreground capitalize">{term.terminal_type}</span></div>
                <div>Último IP: <span className="font-mono text-foreground">{term.last_ip || "Nunca conectou"}</span></div>
                <div>Última Comunicação: <span className="text-foreground">{term.last_seen_at ? new Date(term.last_seen_at).toLocaleString("pt-BR") : "Inativo"}</span></div>
              </div>
            </div>
          ))
        )}
      </div>

      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-2xl border bg-card p-6 shadow-xl">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="font-semibold text-foreground">Novo Terminal Kiosk</h3>
              <button onClick={() => setShowCreateModal(false)} className="text-muted-foreground hover:text-foreground">
                <X className="h-5 w-5" />
              </button>
            </div>
            <form onSubmit={handleCreateTerminal} className="mt-4 space-y-4">
              <div>
                <label className="text-xs font-medium text-muted-foreground">Código Único (Ex: TERM-PORTARIA)</label>
                <input
                  type="text"
                  required
                  value={code}
                  onChange={(e) => setCode(e.target.value.toUpperCase())}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Nome de Identificação</label>
                <input
                  type="text"
                  required
                  placeholder="Ex: Totem Entrada Principal"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Unidade de Alocação</label>
                <select
                  value={unitId}
                  onChange={(e) => setUnitId(e.target.value)}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm"
                >
                  {units.map((u) => (
                    <option key={u.id} value={u.id}>{u.name}</option>
                  ))}
                </select>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
                >
                  Criar Terminal
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
