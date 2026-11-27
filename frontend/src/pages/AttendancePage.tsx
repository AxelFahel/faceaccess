import React, { useEffect, useState } from "react";
import { Clock, Download, Plus, X } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { AttendanceRecord, Employee } from "@/types";

export function AttendancePage() {
  const [records, setRecords] = useState<AttendanceRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [dateFilter, setDateFilter] = useState("");
  const [showManualModal, setShowManualModal] = useState(false);

  // Manual record form states
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [selectedEmployeeId, setSelectedEmployeeId] = useState("");
  const [recordType, setRecordType] = useState<"entry" | "exit" | "break_start" | "break_end">("entry");
  const [manualTime, setManualTime] = useState("");
  const [reason, setReason] = useState("Registro manual autorizado por esquecimento ou contingência");
  const [submitting, setSubmitting] = useState(false);

  const loadAttendance = () => {
    setLoading(true);
    const query = dateFilter ? `?target_date=${dateFilter}` : "";
    apiFetch<{ items: AttendanceRecord[] }>(`/api/v1/attendance${query}`)
      .then((res) => setRecords(res.items))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  };

  const loadEmployees = () => {
    apiFetch<{ items: Employee[] }>("/api/v1/employees?page_size=100")
      .then((res) => {
        setEmployees(res.items);
        if (res.items.length > 0) setSelectedEmployeeId(res.items[0].id);
      })
      .catch(console.error);
  };

  useEffect(() => {
    loadAttendance();
  }, [dateFilter]);

  useEffect(() => {
    loadEmployees();
  }, []);

  const handleDownloadCsv = () => {
    window.location.href = "/api/v1/reports/attendance/csv";
  };

  const handleCreateManual = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedEmployeeId) return;
    setSubmitting(true);
    try {
      let recordedAt: string | undefined = undefined;
      if (manualTime) {
        const baseDate = dateFilter || new Date().toISOString().split("T")[0];
        recordedAt = new Date(`${baseDate}T${manualTime}:00`).toISOString();
      }

      await apiFetch("/api/v1/attendance/manual", {
        method: "POST",
        body: JSON.stringify({
          employee_id: selectedEmployeeId,
          record_type: recordType,
          recorded_at: recordedAt,
          reason,
        }),
      });

      setShowManualModal(false);
      setManualTime("");
      loadAttendance();
    } catch (err: any) {
      alert(err.message || "Erro ao registrar presença manual.");
    } finally {
      setSubmitting(false);
    }
  };

  const getRecordBadge = (type: string) => {
    switch (type) {
      case "entry":
        return <span className="rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">Entrada</span>;
      case "exit":
        return <span className="rounded-full bg-blue-500/10 px-2.5 py-0.5 text-xs font-medium text-blue-600 dark:text-blue-400">Saída</span>;
      case "break_start":
        return <span className="rounded-full bg-amber-500/10 px-2.5 py-0.5 text-xs font-medium text-amber-600 dark:text-amber-400">Início Intervalo</span>;
      case "break_end":
        return <span className="rounded-full bg-purple-500/10 px-2.5 py-0.5 text-xs font-medium text-purple-600 dark:text-purple-400">Retorno Intervalo</span>;
      default:
        return <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium">{type}</span>;
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <input
            type="date"
            value={dateFilter}
            onChange={(e) => setDateFilter(e.target.value)}
            className="rounded-lg border bg-card px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          />
          {dateFilter && (
            <button
              onClick={() => setDateFilter("")}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              Limpar filtro
            </button>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowManualModal(true)}
            className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-4 w-4" />
            Lançar Ponto Manual
          </button>
          <button
            onClick={handleDownloadCsv}
            className="flex items-center gap-2 rounded-lg border bg-card px-4 py-2 text-sm font-medium hover:bg-muted transition-colors"
          >
            <Download className="h-4 w-4" />
            Exportar CSV
          </button>
        </div>
      </div>

      <div className="rounded-xl border bg-card shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm whitespace-nowrap">
            <thead className="border-b bg-muted/50 text-xs font-semibold uppercase text-muted-foreground">
              <tr>
                <th className="px-4 sm:px-6 py-3">Funcionário</th>
                <th className="px-4 sm:px-6 py-3">Data Local</th>
                <th className="px-4 sm:px-6 py-3">Horário</th>
                <th className="px-4 sm:px-6 py-3">Tipo de Registro</th>
                <th className="px-4 sm:px-6 py-3">Método</th>
                <th className="px-4 sm:px-6 py-3">Resultado</th>
                <th className="px-4 sm:px-6 py-3">Origem</th>
              </tr>
            </thead>
            <tbody className="divide-y text-foreground">
              {loading ? (
                <tr>
                  <td colSpan={7} className="px-6 py-8 text-center text-muted-foreground">
                    Carregando registros de presença...
                  </td>
                </tr>
              ) : records.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-8 text-center text-muted-foreground">
                    Nenhum registro de presença encontrado.
                  </td>
                </tr>
              ) : (
                records.map((r) => (
                  <tr key={r.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 sm:px-6 py-4 font-medium text-foreground">
                      {r.employee_name || "Colaborador"}
                    </td>
                    <td className="px-4 sm:px-6 py-4">{r.local_date}</td>
                    <td className="px-4 sm:px-6 py-4 font-mono text-xs font-semibold text-primary">
                      {new Date(r.recorded_at).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                    </td>
                    <td className="px-4 sm:px-6 py-4">{getRecordBadge(r.record_type)}</td>
                    <td className="px-4 sm:px-6 py-4 capitalize text-xs">{r.verification_method}</td>
                    <td className="px-4 sm:px-6 py-4">
                      <span className="inline-flex rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-600">
                        {r.result}
                      </span>
                    </td>
                    <td className="px-4 sm:px-6 py-4 capitalize text-xs text-muted-foreground">{r.source}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal Lançamento Manual de Ponto */}
      {showManualModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-2xl border bg-card p-6 shadow-xl">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="font-semibold text-foreground">Lançamento de Ponto Manual</h3>
              <button
                onClick={() => setShowManualModal(false)}
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <form onSubmit={handleCreateManual} className="mt-4 space-y-4">
              <div>
                <label className="text-xs font-medium text-muted-foreground">Funcionário</label>
                <select
                  required
                  value={selectedEmployeeId}
                  onChange={(e) => setSelectedEmployeeId(e.target.value)}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground focus:ring-2 focus:ring-primary"
                >
                  {employees.map((emp) => (
                    <option key={emp.id} value={emp.id}>
                      {emp.full_name} ({emp.registration_number})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground">Tipo de Registro</label>
                <select
                  value={recordType}
                  onChange={(e) => setRecordType(e.target.value as any)}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground focus:ring-2 focus:ring-primary"
                >
                  <option value="entry">Entrada</option>
                  <option value="break_start">Início de Intervalo</option>
                  <option value="break_end">Retorno de Intervalo</option>
                  <option value="exit">Saída</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground">
                  Horário (Opcional - deixe em branco para hora atual do servidor)
                </label>
                <input
                  type="time"
                  step="1"
                  value={manualTime}
                  onChange={(e) => setManualTime(e.target.value)}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground focus:ring-2 focus:ring-primary"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground">Justificativa / Motivo</label>
                <textarea
                  required
                  rows={2}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground focus:ring-2 focus:ring-primary"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t">
                <button
                  type="button"
                  onClick={() => setShowManualModal(false)}
                  className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                  {submitting ? "Gravando..." : "Salvar Registro"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
