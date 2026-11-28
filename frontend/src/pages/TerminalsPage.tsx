import React, { useEffect, useState } from "react";
import { MonitorDot, Plus, Key, CheckCircle, AlertTriangle, X, ScanFace } from "lucide-react";
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
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [units, setUnits] = useState<{ id: string; name: string }[]>([]);
  const [unitId, setUnitId] = useState("");
  const [activation, setActivation] = useState<{ code: string; activation_code: string } | null>(null);

  const loadTerminals = () => {
    setLoading(true);
    setError("");
    apiFetch<Terminal[]>("/api/v1/terminals")
      .then((data) => setTerminals(data))
      .catch((err) => setError(err.message || "Falha ao carregar terminais."))
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
    if (creating) return;
    setCreating(true);
    try {
      const created = await apiFetch<{ code: string; activation_code: string }>("/api/v1/terminals", {
        method: "POST",
        body: JSON.stringify({ code, name, unit_id: unitId }),
      });
      setActivation(created);
      setShowCreateModal(false);
      setCode("");
      setName("");
      loadTerminals();
    } catch (err: any) {
      alert(err.message);
    } finally { setCreating(false); }
  };

  const renewCode = async (term: Terminal) => {
    try {
      setActivation(await apiFetch(`/api/v1/terminals/${term.id}/activation-code`, { method: "POST" }));
    } catch (err) { alert(err instanceof Error ? err.message : "Falha ao gerar código."); }
  };

  return (
    <div className="space-y-6">
      {error && <p role="alert" className="rounded-xl border border-red-400 p-4 text-sm">{error} <button onClick={loadTerminals} className="underline">Tentar novamente</button></p>}
      <div className="rounded-xl border bg-card p-4 text-sm space-y-2">
        <p className="font-semibold">Um totem, dois fluxos de acesso</p>
        <p className="text-muted-foreground">Funcionários: vínculo, jornada e exceções. Convidados: biometria obrigatória e janela do evento. O reconhecimento não substitui as regras de autorização.</p>
        <p className="text-muted-foreground">Na câmera: verde para enquadramento aprovado, vermelho para ajuste e varredura durante a análise.</p>
      </div>
      {activation && <div className="rounded-xl border border-primary bg-primary/10 p-5 space-y-2">
        <p className="font-semibold">Ativação do terminal {activation.code}</p>
        <p className="font-mono text-2xl tracking-widest">{activation.activation_code}</p>
        <p className="text-sm">Abra /kiosk no dispositivo do totem e informe estes códigos. O código de ativação é temporário e de uso único.</p>
        <button className="rounded-lg border px-3 py-2 text-sm" onClick={() => setActivation(null)}>Fechar</button>
      </div>}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base sm:text-lg font-semibold text-foreground">Terminais e Totens de Acesso</h2>
          <p className="text-xs text-muted-foreground">Dispositivos autorizados a operar em modo kiosk local</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 self-start sm:self-auto"
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
                  {({ active: "Ativo", pending_activation: "Aguardando ativação", inactive: "Inativo", revoked: "Revogado" } as Record<string, string>)[term.status] || term.status}
                </span>
              </div>

              <div className="border-t pt-3 text-xs text-muted-foreground space-y-1">
                <div>Unidade: <span className="text-foreground">{units.find(unit => unit.id === term.unit_id)?.name || "Não informada"}</span></div>
                <div>Tipo: <span className="text-foreground capitalize">{term.terminal_type}</span></div>
                <div>Último IP: <span className="font-mono text-foreground">{term.last_ip || "Nunca conectou"}</span></div>
                <div>Última Comunicação: <span className="text-foreground">{term.last_seen_at ? new Date(term.last_seen_at).toLocaleString("pt-BR") : "Inativo"}</span></div>
              </div>
              {term.status === "pending_activation" && <button onClick={() => renewCode(term)} className="rounded-lg border px-3 py-2 text-sm w-full">Gerar código de ativação</button>}
              {term.status === "active" && (
                <button
                  onClick={() => {
                    if (localStorage.getItem("terminal_code") !== term.code || !localStorage.getItem("terminal_secret")) {
                      setError("Este terminal já foi ativado em outro navegador. Abra no dispositivo original ou cadastre um novo terminal para este dispositivo.");
                      return;
                    }
                    window.location.href = "/kiosk";
                  }}
                  className="w-full flex items-center justify-center gap-2 rounded-lg bg-primary/10 hover:bg-primary/20 text-primary py-2 text-xs font-semibold transition-colors mt-2"
                >
                  <ScanFace className="h-4 w-4" />
                  Abrir Totem neste Dispositivo
                </button>
              )}
            </div>
          ))
        )}
      </div>

      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md max-h-[90vh] overflow-y-auto rounded-2xl border bg-card p-5 sm:p-6 shadow-xl">
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
                  disabled={creating || !unitId}
                  className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
                >
                  {creating ? "Criando…" : "Criar Terminal"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
