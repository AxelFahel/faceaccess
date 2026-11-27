import React, { useEffect, useState } from "react";
import {
  Users,
  Search,
  Plus,
  ShieldCheck,
  ShieldAlert,
  Camera,
  X,
  Check,
  KeyRound,
  Trash2,
  Upload,
  AlertTriangle,
  RotateCcw,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { EnrollmentCapture } from "@/components/biometrics/EnrollmentCapture";
import { startVoiceGuide } from "@/components/biometrics/useVoiceGuide";
import { Employee } from "@/types";

export function EmployeesPage() {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [enrollModalEmployee, setEnrollModalEmployee] = useState<Employee | null>(null);

  // Form states
  const [fullName, setFullName] = useState("");
  const [regNumber, setRegNumber] = useState("");
  const [email, setEmail] = useState("");
  const [pin, setPin] = useState("");
  const [unitId, setUnitId] = useState("");
  const [schedules, setSchedules] = useState<{ id: string; name: string }[]>([]);
  const [workScheduleId, setWorkScheduleId] = useState("");

  const loadEmployees = () => {
    setLoading(true);
    apiFetch<{ items: Employee[] }>(`/api/v1/employees?q=${search}`)
      .then((res) => setEmployees(res.items))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadEmployees();
    // Load default unit
    apiFetch<{ id: string }[]>("/api/v1/organization/units")
      .then((units) => {
        if (units.length > 0) setUnitId(units[0].id);
      })
      .catch(console.error);
    // Load available schedules
    apiFetch<{ id: string; name: string }[]>("/api/v1/schedules")
      .then(setSchedules)
      .catch(console.error);
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiFetch("/api/v1/employees", {
        method: "POST",
        body: JSON.stringify({
          full_name: fullName,
          registration_number: regNumber,
          email,
          unit_id: unitId,
          work_schedule_id: workScheduleId || undefined,
          pin: pin || undefined,
        }),
      });
      setShowCreateModal(false);
      setFullName("");
      setRegNumber("");
      setEmail("");
      setPin("");
      loadEmployees();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleRevoke = async (emp: Employee) => {
    if (!confirm(`Deseja revogar e eliminar a biometria de ${emp.full_name}?`)) return;
    try {
      await apiFetch(`/api/v1/biometrics/revoke/${emp.id}`, { method: "POST" });
      loadEmployees();
    } catch (err: any) {
      alert(err.message);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Buscar por nome, matrícula ou e-mail..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && loadEmployees()}
            className="w-full rounded-lg border bg-card pl-9 pr-4 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm hover:bg-primary/90 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Novo Funcionário
        </button>
      </div>

      {/* Employees Table */}
      <div className="rounded-xl border bg-card shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm whitespace-nowrap">
            <thead className="border-b bg-muted/50 text-xs font-semibold uppercase text-muted-foreground">
              <tr>
                <th className="px-4 sm:px-6 py-3">Funcionário</th>
                <th className="px-4 sm:px-6 py-3">Matrícula</th>
                <th className="px-4 sm:px-6 py-3">Jornada / Horário</th>
                <th className="px-4 sm:px-6 py-3">Status Funcional</th>
                <th className="px-4 sm:px-6 py-3">Biometria Facial</th>
                <th className="px-4 sm:px-6 py-3 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y text-foreground">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-4 sm:px-6 py-8 text-center text-muted-foreground">
                    Carregando colaboradores...
                  </td>
                </tr>
              ) : employees.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 sm:px-6 py-8 text-center text-muted-foreground">
                    Nenhum funcionário encontrado.
                  </td>
                </tr>
              ) : (
                employees.map((emp) => (
                  <tr key={emp.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 sm:px-6 py-4">
                      <div className="font-medium text-foreground">{emp.full_name}</div>
                      <div className="text-xs text-muted-foreground">{emp.email}</div>
                    </td>
                    <td className="px-4 sm:px-6 py-4 font-mono text-xs text-muted-foreground">
                      {emp.registration_number}
                    </td>
                    <td className="px-4 sm:px-6 py-4 text-xs">
                      {emp.work_schedule_name ? (
                        <span className="font-semibold text-foreground bg-primary/10 text-primary px-2 py-0.5 rounded">
                          {emp.work_schedule_name}
                        </span>
                      ) : (
                        <span className="text-muted-foreground italic text-[11px]">Sem restrição</span>
                      )}
                    </td>
                    <td className="px-4 sm:px-6 py-4">
                      <span className="inline-flex rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
                        {emp.employment_status === "active" ? "Ativo" : emp.employment_status}
                      </span>
                    </td>
                    <td className="px-4 sm:px-6 py-4">
                      {emp.biometric_status === "enrolled" ? (
                        <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary">
                          <ShieldCheck className="h-3.5 w-3.5" />
                          Cadastrada
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/10 px-2.5 py-0.5 text-xs font-medium text-amber-600 dark:text-amber-400">
                          <ShieldAlert className="h-3.5 w-3.5" />
                          Pendente
                        </span>
                      )}
                    </td>
                    <td className="px-4 sm:px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        {emp.biometric_status === "enrolled" ? (
                          <button
                            onClick={() => handleRevoke(emp)}
                            className="rounded-lg p-1.5 text-destructive hover:bg-destructive/10"
                            title="Revogar Biometria"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        ) : (
                          <button
                            onClick={() => {
                              setEnrollModalEmployee(emp);
                              startVoiceGuide();
                            }}
                            className="flex items-center gap-1.5 rounded-lg bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary hover:bg-primary/20"
                          >
                            <Camera className="h-3.5 w-3.5" />
                            Cadastrar Face
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal Criar Funcionário */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md max-h-[90vh] overflow-y-auto rounded-2xl border bg-card p-5 sm:p-6 shadow-xl">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="font-semibold text-foreground">Novo Funcionário</h3>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <form onSubmit={handleCreate} className="mt-4 space-y-4">
              <div>
                <label className="text-xs font-medium text-muted-foreground">Nome Completo</label>
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Matrícula Funcional</label>
                <input
                  type="text"
                  required
                  value={regNumber}
                  onChange={(e) => setRegNumber(e.target.value)}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">E-mail Institucional</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Jornada de Trabalho (Horário de Acesso)</label>
                <select
                  value={workScheduleId}
                  onChange={(e) => setWorkScheduleId(e.target.value)}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground"
                >
                  <option value="">Sem restrição de horário</option>
                  {schedules.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">PIN de Acesso (Alternativa não biométrica)</label>
                <input
                  type="password"
                  maxLength={12}
                  placeholder="Ex: 123456"
                  value={pin}
                  onChange={(e) => setPin(e.target.value)}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm"
                />
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
                  Salvar Funcionário
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {enrollModalEmployee && (
        <EnrollmentCapture
          employee={enrollModalEmployee}
          onClose={() => setEnrollModalEmployee(null)}
          onComplete={loadEmployees}
        />
      )}
    </div>
  );
}
