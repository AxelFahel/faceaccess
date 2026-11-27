import React, { useEffect, useState } from "react";
import {
  Clock,
  Plus,
  Search,
  Calendar,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  X,
  UserCheck,
  ShieldAlert,
  CalendarCheck,
  CalendarClock,
  Briefcase,
  FileCheck2,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

interface WorkSchedule {
  id: string;
  name: string;
  description?: string;
  days: { weekday: number; start: string; end: string; break_minutes: number }[];
  tolerance_minutes: number;
  is_active: boolean;
  created_at: string;
}

interface ScheduleException {
  id: string;
  employee_id: string;
  employee_name?: string;
  starts_at: string;
  ends_at: string;
  reason: string;
  exception_type: string;
  authorized_by_name?: string;
  is_active: boolean;
  used_at?: string;
  access_count: number;
  created_at: string;
}

interface EmployeeOption {
  id: string;
  full_name: string;
  registration_number: string;
}

const WEEKDAY_NAMES = [
  "Segunda-feira",
  "Terça-feira",
  "Quarta-feira",
  "Quinta-feira",
  "Sexta-feira",
  "Sábado",
  "Domingo",
];

export function SchedulesPage() {
  const [activeTab, setActiveTab] = useState<"exceptions" | "schedules">("exceptions");

  // Exceptions states
  const [exceptions, setExceptions] = useState<ScheduleException[]>([]);
  const [loadingExceptions, setLoadingExceptions] = useState(true);
  const [showExceptionModal, setShowExceptionModal] = useState(false);
  const [searchExc, setSearchExc] = useState("");

  // Exception Form
  const [employees, setEmployees] = useState<EmployeeOption[]>([]);
  const [selectedEmpId, setSelectedEmpId] = useState("");
  const [excStartsAt, setExcStartsAt] = useState("");
  const [excEndsAt, setExcEndsAt] = useState("");
  const [excReason, setExcReason] = useState("");
  const [excType, setExcType] = useState("overtime");
  const [submittingExc, setSubmittingExc] = useState(false);

  // Schedules states
  const [schedules, setSchedules] = useState<WorkSchedule[]>([]);
  const [loadingSchedules, setLoadingSchedules] = useState(true);
  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [schedName, setSchedName] = useState("");
  const [schedDesc, setSchedDesc] = useState("");
  const [schedTol, setSchedTol] = useState(15);
  const [schedStart, setSchedStart] = useState("08:00");
  const [schedEnd, setSchedEnd] = useState("17:00");
  const [schedDays, setSchedDays] = useState<number[]>([0, 1, 2, 3, 4]); // Mon-Fri
  const [submittingSched, setSubmittingSched] = useState(false);

  const loadExceptions = () => {
    setLoadingExceptions(true);
    apiFetch<ScheduleException[]>("/api/v1/schedules/exceptions")
      .then(setExceptions)
      .catch(console.error)
      .finally(() => setLoadingExceptions(false));
  };

  const loadSchedules = () => {
    setLoadingSchedules(true);
    apiFetch<WorkSchedule[]>("/api/v1/schedules")
      .then(setSchedules)
      .catch(console.error)
      .finally(() => setLoadingSchedules(false));
  };

  useEffect(() => {
    loadExceptions();
    loadSchedules();
    apiFetch<{ items: EmployeeOption[] }>("/api/v1/employees?page_size=100")
      .then((res) => {
        setEmployees(res.items);
        if (res.items.length > 0) setSelectedEmpId(res.items[0].id);
      })
      .catch(console.error);
  }, []);

  const handleCreateException = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedEmpId || !excStartsAt || !excEndsAt || !excReason.trim()) {
      alert("Preencha todos os campos obrigatórios (incluindo o motivo da exceção).");
      return;
    }
    setSubmittingExc(true);
    try {
      await apiFetch("/api/v1/schedules/exceptions", {
        method: "POST",
        body: JSON.stringify({
          employee_id: selectedEmpId,
          starts_at: new Date(excStartsAt).toISOString(),
          ends_at: new Date(excEndsAt).toISOString(),
          reason: excReason.trim(),
          exception_type: excType,
        }),
      });
      setShowExceptionModal(false);
      setExcStartsAt("");
      setExcEndsAt("");
      setExcReason("");
      loadExceptions();
    } catch (err: any) {
      alert(err.message || "Falha ao registrar exceção.");
    } finally {
      setSubmittingExc(false);
    }
  };

  const handleCancelException = async (exc: ScheduleException) => {
    const reason = prompt("Informe o motivo do cancelamento da exceção:");
    if (!reason) return;
    try {
      await apiFetch(`/api/v1/schedules/exceptions/${exc.id}/cancel`, {
        method: "POST",
        body: JSON.stringify({ cancel_reason: reason }),
      });
      loadExceptions();
    } catch (err: any) {
      alert(err.message || "Falha ao cancelar exceção.");
    }
  };

  const handleCreateSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!schedName || schedDays.length === 0) {
      alert("Informe o nome da jornada e selecione os dias da semana.");
      return;
    }
    setSubmittingSched(true);
    try {
      const days = schedDays.map((w) => ({
        weekday: w,
        start: schedStart,
        end: schedEnd,
        break_minutes: 60,
      }));
      await apiFetch("/api/v1/schedules", {
        method: "POST",
        body: JSON.stringify({
          name: schedName.trim(),
          description: schedDesc.trim() || undefined,
          days,
          tolerance_minutes: Number(schedTol),
        }),
      });
      setShowScheduleModal(false);
      setSchedName("");
      setSchedDesc("");
      loadSchedules();
    } catch (err: any) {
      alert(err.message || "Falha ao cadastrar jornada.");
    } finally {
      setSubmittingSched(false);
    }
  };

  const toggleDay = (d: number) => {
    if (schedDays.includes(d)) {
      setSchedDays(schedDays.filter((x) => x !== d));
    } else {
      setSchedDays([...schedDays, d].sort());
    }
  };

  const filteredExceptions = exceptions.filter((exc) => {
    const s = searchExc.toLowerCase();
    return (
      (exc.employee_name && exc.employee_name.toLowerCase().includes(s)) ||
      exc.reason.toLowerCase().includes(s) ||
      exc.exception_type.toLowerCase().includes(s)
    );
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2.5">
          <div className="rounded-lg bg-primary/10 p-2 text-primary">
            <CalendarClock className="h-6 w-6" />
          </div>
          <div>
            <h2 className="text-base sm:text-lg font-bold text-foreground">
              Jornadas & Exceções de Acesso
            </h2>
            <p className="text-xs text-muted-foreground">
              Controle estrito de horários de expediente no totem com registro auditável de exceções
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {activeTab === "exceptions" ? (
            <button
              onClick={() => setShowExceptionModal(true)}
              className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm hover:bg-primary/90 transition-colors"
            >
              <Plus className="h-4 w-4" />
              Registrar Exceção
            </button>
          ) : (
            <button
              onClick={() => setShowScheduleModal(true)}
              className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm hover:bg-primary/90 transition-colors"
            >
              <Plus className="h-4 w-4" />
              Nova Jornada
            </button>
          )}
        </div>
      </div>

      {/* Rules Notice */}
      <div className="rounded-xl border border-primary/20 bg-primary/5 p-4 text-xs text-muted-foreground space-y-1">
        <p className="font-semibold flex items-center gap-1.5 text-foreground">
          <FileCheck2 className="h-4 w-4 text-primary" />
          Regra de Acesso dos Funcionários no Totem
        </p>
        <p>
          Funcionários só possuem acesso liberado no totem <strong>dentro do período de trabalho estabelecido</strong> na sua jornada.
          Fora do horário previsto (ou em dias de folga), o totem <strong>rejeita o acesso</strong>,
          <strong> salvo se houver uma exceção registrada e autorizada</strong> (hora extra, plantão ou emergência).
        </p>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border">
        <button
          onClick={() => setActiveTab("exceptions")}
          className={`flex items-center gap-2 px-5 py-2.5 text-xs font-semibold border-b-2 transition-all ${
            activeTab === "exceptions"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <CalendarCheck className="h-4 w-4" />
          Exceções Registradas ({exceptions.length})
        </button>
        <button
          onClick={() => setActiveTab("schedules")}
          className={`flex items-center gap-2 px-5 py-2.5 text-xs font-semibold border-b-2 transition-all ${
            activeTab === "schedules"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Briefcase className="h-4 w-4" />
          Jornadas de Trabalho ({schedules.length})
        </button>
      </div>

      {/* Tab 1: Exceções */}
      {activeTab === "exceptions" && (
        <div className="space-y-4">
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Buscar por funcionário, motivo ou tipo..."
              value={searchExc}
              onChange={(e) => setSearchExc(e.target.value)}
              className="w-full rounded-lg border bg-card pl-9 pr-4 py-2 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>

          <div className="rounded-xl border bg-card shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs whitespace-nowrap">
                <thead className="border-b bg-muted/40 text-muted-foreground uppercase font-semibold">
                  <tr>
                    <th className="px-4 py-3">Funcionário</th>
                    <th className="px-4 py-3">Janela Autorizada</th>
                    <th className="px-4 py-3">Motivo da Exceção</th>
                    <th className="px-4 py-3">Tipo</th>
                    <th className="px-4 py-3">Autorizado Por</th>
                    <th className="px-4 py-3">Status no Totem</th>
                    <th className="px-4 py-3 text-right">Ação</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {loadingExceptions ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                        Carregando exceções...
                      </td>
                    </tr>
                  ) : filteredExceptions.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                        Nenhuma exceção registrada. Clique em <strong>Registrar Exceção</strong>.
                      </td>
                    </tr>
                  ) : (
                    filteredExceptions.map((exc) => {
                      const now = new Date();
                      const start = new Date(exc.starts_at);
                      const end = new Date(exc.ends_at);
                      const isCurrent = now >= start && now <= end && exc.is_active;
                      const isExpired = now > end;

                      return (
                        <tr key={exc.id} className="hover:bg-muted/30 transition-colors">
                          <td className="px-4 py-3 font-medium text-foreground">
                            {exc.employee_name || "Colaborador"}
                          </td>
                          <td className="px-4 py-3 font-mono text-[11px]">
                            {start.toLocaleString("pt-BR", {
                              day: "2-digit",
                              month: "2-digit",
                              hour: "2-digit",
                              minute: "2-digit",
                            })}{" "}
                            às{" "}
                            {end.toLocaleString("pt-BR", {
                              day: "2-digit",
                              month: "2-digit",
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </td>
                          <td className="px-4 py-3 max-w-xs truncate" title={exc.reason}>
                            <span className="font-semibold text-foreground">{exc.reason}</span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="capitalize rounded-md bg-muted px-2 py-0.5 text-[10px] font-semibold text-muted-foreground">
                              {exc.exception_type === "overtime"
                                ? "Hora Extra"
                                : exc.exception_type === "on_call"
                                ? "Plantão"
                                : exc.exception_type === "emergency"
                                ? "Emergência"
                                : exc.exception_type}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-muted-foreground">
                            {exc.authorized_by_name || "Gestão"}
                          </td>
                          <td className="px-4 py-3">
                            {!exc.is_active ? (
                              <span className="inline-flex items-center gap-1 text-rose-500 text-[11px] font-medium">
                                <XCircle className="h-3 w-3" />
                                Cancelada
                              </span>
                            ) : isCurrent ? (
                              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-emerald-500 text-[11px] font-bold">
                                <CheckCircle2 className="h-3 w-3" />
                                Válida Agora {exc.access_count > 0 && `(Usada ${exc.access_count}x)`}
                              </span>
                            ) : isExpired ? (
                              <span className="text-muted-foreground text-[11px]">
                                Expirada {exc.access_count > 0 && `(${exc.access_count}x acessos)`}
                              </span>
                            ) : (
                              <span className="text-blue-500 text-[11px]">Agendada (Futura)</span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-right">
                            {exc.is_active && !isExpired && (
                              <button
                                onClick={() => handleCancelException(exc)}
                                className="rounded px-2 py-1 text-[11px] text-rose-500 hover:bg-rose-500/10"
                              >
                                Cancelar
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Jornadas */}
      {activeTab === "schedules" && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {loadingSchedules ? (
            <p className="col-span-full text-xs text-muted-foreground">Carregando jornadas...</p>
          ) : (
            schedules.map((sched) => (
              <div key={sched.id} className="rounded-xl border bg-card p-5 shadow-sm space-y-3">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <div className="rounded-lg bg-primary/10 p-2 text-primary">
                      <Briefcase className="h-4 w-4" />
                    </div>
                    <div>
                      <h4 className="font-semibold text-sm text-foreground">{sched.name}</h4>
                      <p className="text-[11px] text-muted-foreground">
                        Tolerância: ±{sched.tolerance_minutes} minutos
                      </p>
                    </div>
                  </div>
                </div>

                {sched.description && (
                  <p className="text-xs text-muted-foreground">{sched.description}</p>
                )}

                <div className="rounded-lg bg-muted/40 p-2.5 space-y-1 text-xs">
                  <span className="font-semibold text-[11px] text-foreground uppercase tracking-wide">
                    Expediente Semanal:
                  </span>
                  <div className="grid grid-cols-2 gap-1 text-[11px]">
                    {sched.days.map((d, i) => (
                      <div key={i} className="flex justify-between border-b border-border/40 pb-0.5">
                        <span className="text-muted-foreground">
                          {WEEKDAY_NAMES[d.weekday].slice(0, 3)}:
                        </span>
                        <span className="font-mono font-medium text-foreground">
                          {d.start} - {d.end}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Modal: Registrar Exceção */}
      {showExceptionModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl border bg-card p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <div className="flex items-center gap-2">
                <CalendarCheck className="h-5 w-5 text-primary" />
                <h3 className="font-semibold text-foreground">Registrar Exceção de Horário</h3>
              </div>
              <button
                onClick={() => setShowExceptionModal(false)}
                className="rounded-lg p-1 text-muted-foreground hover:bg-muted"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleCreateException} className="space-y-4">
              <div>
                <label className="text-xs font-medium text-muted-foreground">Funcionário *</label>
                <select
                  required
                  value={selectedEmpId}
                  onChange={(e) => setSelectedEmpId(e.target.value)}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-xs text-foreground"
                >
                  {employees.map((emp) => (
                    <option key={emp.id} value={emp.id}>
                      {emp.full_name} ({emp.registration_number})
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-muted-foreground">Início da Janela *</label>
                  <input
                    type="datetime-local"
                    required
                    value={excStartsAt}
                    onChange={(e) => setExcStartsAt(e.target.value)}
                    className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-xs text-foreground"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground">Término da Janela *</label>
                  <input
                    type="datetime-local"
                    required
                    value={excEndsAt}
                    onChange={(e) => setExcEndsAt(e.target.value)}
                    className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-xs text-foreground"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground">Tipo de Exceção</label>
                <select
                  value={excType}
                  onChange={(e) => setExcType(e.target.value)}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-xs text-foreground"
                >
                  <option value="overtime">Hora Extra Autorizada</option>
                  <option value="on_call">Plantão / Sobreaviso</option>
                  <option value="emergency">Manutenção / Emergência</option>
                  <option value="other">Outra Justificativa</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground">
                  Justificativa / Motivo Obrigatório *
                </label>
                <textarea
                  required
                  rows={2}
                  placeholder="Ex: Hora extra aprovada pelo gestor para fechamento de balanço mensal."
                  value={excReason}
                  onChange={(e) => setExcReason(e.target.value)}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-xs text-foreground"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowExceptionModal(false)}
                  className="rounded-lg border px-4 py-2 text-xs font-medium hover:bg-muted"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={submittingExc}
                  className="rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                  {submittingExc ? "Registrando..." : "Registrar Exceção"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Nova Jornada */}
      {showScheduleModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl border bg-card p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <div className="flex items-center gap-2">
                <Briefcase className="h-5 w-5 text-primary" />
                <h3 className="font-semibold text-foreground">Nova Jornada de Trabalho</h3>
              </div>
              <button
                onClick={() => setShowScheduleModal(false)}
                className="rounded-lg p-1 text-muted-foreground hover:bg-muted"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleCreateSchedule} className="space-y-4">
              <div>
                <label className="text-xs font-medium text-muted-foreground">Nome da Jornada *</label>
                <input
                  type="text"
                  required
                  placeholder="Ex: Comercial 08:00 às 17:00"
                  value={schedName}
                  onChange={(e) => setSchedName(e.target.value)}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-xs text-foreground"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground">Descrição</label>
                <input
                  type="text"
                  placeholder="Ex: Turno comercial regular 40h"
                  value={schedDesc}
                  onChange={(e) => setSchedDesc(e.target.value)}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-xs text-foreground"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-muted-foreground">Entrada Habitual</label>
                  <input
                    type="time"
                    required
                    value={schedStart}
                    onChange={(e) => setSchedStart(e.target.value)}
                    className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-xs text-foreground"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground">Saída Habitual</label>
                  <input
                    type="time"
                    required
                    value={schedEnd}
                    onChange={(e) => setSchedEnd(e.target.value)}
                    className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-xs text-foreground"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground">
                  Tolerância de Entrada/Saída (minutos)
                </label>
                <input
                  type="number"
                  min={5}
                  max={60}
                  value={schedTol}
                  onChange={(e) => setSchedTol(Number(e.target.value))}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-xs text-foreground"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1.5">
                  Dias com Expediente:
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {WEEKDAY_NAMES.map((name, idx) => {
                    const active = schedDays.includes(idx);
                    return (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => toggleDay(idx)}
                        className={`px-2.5 py-1 rounded text-[11px] font-semibold border transition-all ${
                          active
                            ? "bg-primary text-primary-foreground border-primary"
                            : "bg-muted text-muted-foreground border-border hover:bg-muted/80"
                        }`}
                      >
                        {name.slice(0, 3)}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowScheduleModal(false)}
                  className="rounded-lg border px-4 py-2 text-xs font-medium hover:bg-muted"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={submittingSched}
                  className="rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                  {submittingSched ? "Salvando..." : "Salvar Jornada"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
