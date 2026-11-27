import React, { useEffect, useState } from "react";
import { ShieldCheck, Lock, FileText, CheckCircle2 } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface LegalBasis {
  id: string;
  processing_activity: string;
  data_categories: string;
  legal_basis: string;
  purpose: string;
  is_active: boolean;
}

interface AuditEntry {
  seq: number;
  created_at: string;
  action: string;
  actor_label: string;
  result: string;
  prev_hash: string;
  hash: string;
}

export function PrivacyPage() {
  const [legalBases, setLegalBases] = useState<LegalBasis[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiFetch<LegalBasis[]>("/api/v1/privacy/legal-basis"),
      apiFetch<AuditEntry[]>("/api/v1/privacy/audit-logs?limit=15"),
    ])
      .then(([lb, logs]) => {
        setLegalBases(lb);
        setAuditLogs(logs);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div className="rounded-xl border bg-card p-6 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-emerald-500/10 p-2.5 text-emerald-600">
            <ShieldCheck className="h-6 w-6" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-foreground">Conformidade LGPD & Governança de Dados</h2>
            <p className="text-xs text-muted-foreground">
              Tratamento restrito a ambientes locais, sem monitoramento indiscriminado e com descarte imediato de imagens
            </p>
          </div>
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          {legalBases.map((lb) => (
            <div key={lb.id} className="rounded-xl border bg-muted/20 p-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-sm text-foreground">{lb.processing_activity}</span>
                <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-600">
                  Ativa
                </span>
              </div>
              <p className="text-xs text-muted-foreground font-mono bg-background/50 p-2 rounded">
                Base Legal: {lb.legal_basis}
              </p>
              <p className="text-xs text-foreground/80">{lb.purpose}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Trilha de Auditoria Encadeada */}
      <div className="rounded-xl border bg-card p-6 shadow-sm space-y-4">
        <div>
          <h3 className="font-bold text-foreground">Trilha de Auditoria Encadeada (Tamper-Evident)</h3>
          <p className="text-xs text-muted-foreground">
            Registros protegidos criptograficamente com HMAC-SHA-256 e prev_hash
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="border-b bg-muted/40 uppercase text-muted-foreground">
              <tr>
                <th className="py-2.5 px-3">Seq</th>
                <th className="py-2.5 px-3">Data/Hora (UTC)</th>
                <th className="py-2.5 px-3">Ação</th>
                <th className="py-2.5 px-3">Autor</th>
                <th className="py-2.5 px-3">Hash HMAC Atual</th>
              </tr>
            </thead>
            <tbody className="divide-y text-foreground/90">
              {auditLogs.map((log) => (
                <tr key={log.seq} className="hover:bg-muted/20">
                  <td className="py-2.5 px-3 font-bold text-primary">{log.seq}</td>
                  <td className="py-2.5 px-3">{new Date(log.created_at).toLocaleString("pt-BR")}</td>
                  <td className="py-2.5 px-3 font-semibold">{log.action}</td>
                  <td className="py-2.5 px-3">{log.actor_label || "Sistema"}</td>
                  <td className="py-2.5 px-3 text-muted-foreground truncate max-w-xs">{log.hash}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
