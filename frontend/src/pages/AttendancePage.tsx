import React, { useEffect, useState } from "react";
import { Clock, Calendar, Download, Filter, Search } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { AttendanceRecord } from "@/types";

export function AttendancePage() {
  const [records, setRecords] = useState<AttendanceRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [dateFilter, setDateFilter] = useState("");

  const loadAttendance = () => {
    setLoading(true);
    const query = dateFilter ? `?target_date=${dateFilter}` : "";
    apiFetch<{ items: AttendanceRecord[] }>(`/api/v1/attendance${query}`)
      .then((res) => setRecords(res.items))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadAttendance();
  }, [dateFilter]);

  const handleDownloadCsv = () => {
    window.open("/api/v1/reports/attendance/csv", "_blank");
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

        <button
          onClick={handleDownloadCsv}
          className="flex items-center gap-2 rounded-lg border bg-card px-4 py-2 text-sm font-medium hover:bg-muted transition-colors"
        >
          <Download className="h-4 w-4" />
          Exportar CSV Auditado
        </button>
      </div>

      <div className="rounded-xl border bg-card shadow-sm overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="border-b bg-muted/50 text-xs font-semibold uppercase text-muted-foreground">
            <tr>
              <th className="px-6 py-3">Data Local</th>
              <th className="px-6 py-3">Horário (UTC)</th>
              <th className="px-6 py-3">Tipo de Registro</th>
              <th className="px-6 py-3">Método</th>
              <th className="px-6 py-3">Resultado</th>
              <th className="px-6 py-3">Origem</th>
            </tr>
          </thead>
          <tbody className="divide-y text-foreground">
            {loading ? (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-muted-foreground">
                  Carregando registros de presença...
                </td>
              </tr>
            ) : records.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-muted-foreground">
                  Nenhum registro de presença encontrado.
                </td>
              </tr>
            ) : (
              records.map((r) => (
                <tr key={r.id} className="hover:bg-muted/30 transition-colors">
                  <td className="px-6 py-4 font-medium">{r.local_date}</td>
                  <td className="px-6 py-4 font-mono text-xs text-muted-foreground">
                    {new Date(r.recorded_at).toLocaleTimeString("pt-BR")}
                  </td>
                  <td className="px-6 py-4">{getRecordBadge(r.record_type)}</td>
                  <td className="px-6 py-4 capitalize text-xs">{r.verification_method}</td>
                  <td className="px-6 py-4">
                    <span className="inline-flex rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-600">
                      {r.result}
                    </span>
                  </td>
                  <td className="px-6 py-4 capitalize text-xs text-muted-foreground">{r.source}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
