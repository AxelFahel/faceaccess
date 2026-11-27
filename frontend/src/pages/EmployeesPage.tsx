import React, { useEffect, useState, useRef } from "react";
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
} from "lucide-react";
import { apiFetch } from "@/lib/api";
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

  // Biometrics camera states
  const videoRef = useRef<HTMLVideoElement>(null);
  const [captures, setCaptures] = useState<string[]>([]);
  const [enrolling, setEnrolling] = useState(false);
  const [enrollMsg, setEnrollMsg] = useState("");

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

  // Camera start for enrollment
  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: "user" },
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
    } catch (err) {
      console.error("Erro ao acessar câmera:", err);
    }
  };

  const stopCamera = () => {
    if (videoRef.current && videoRef.current.srcObject) {
      const stream = videoRef.current.srcObject as MediaStream;
      stream.getTracks().forEach((track) => track.stop());
      videoRef.current.srcObject = null;
    }
  };

  const takePhoto = () => {
    if (!videoRef.current) return;
    const canvas = document.createElement("canvas");
    canvas.width = videoRef.current.videoWidth || 640;
    canvas.height = videoRef.current.videoHeight || 480;
    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
      const b64 = canvas.toDataURL("image/jpeg", 0.9);
      setCaptures((prev) => [...prev, b64]);
    }
  };

  const submitEnrollment = async () => {
    if (!enrollModalEmployee) return;
    setEnrolling(true);
    setEnrollMsg("Processando enquadramento, vivacidade e extração de embedding...");
    try {
      const legalBases = await apiFetch<{ id: string }[]>("/api/v1/privacy/legal-basis");
      await apiFetch("/api/v1/biometrics/enroll", {
        method: "POST",
        body: JSON.stringify({
          employee_id: enrollModalEmployee.id,
          images_base64: captures,
          legal_basis_record_id: legalBases[0].id,
        }),
      });
      setEnrollMsg("Cadastro biométrico concluído com sucesso!");
      setTimeout(() => {
        stopCamera();
        setEnrollModalEmployee(null);
        setCaptures([]);
        setEnrollMsg("");
        loadEmployees();
      }, 1500);
    } catch (err: any) {
      setEnrollMsg(`Falha: ${err.message}`);
    } finally {
      setEnrolling(false);
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
                <th className="px-4 sm:px-6 py-3">Status Funcional</th>
                <th className="px-4 sm:px-6 py-3">Biometria Facial</th>
                <th className="px-4 sm:px-6 py-3 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y text-foreground">
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-4 sm:px-6 py-8 text-center text-muted-foreground">
                    Carregando colaboradores...
                  </td>
                </tr>
              ) : employees.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 sm:px-6 py-8 text-center text-muted-foreground">
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
                              setCaptures([]);
                              startCamera();
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

      {/* Modal Cadastro Biométrico com Câmera */}
      {enrollModalEmployee && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-xl max-h-[90vh] overflow-y-auto rounded-2xl border bg-card p-5 sm:p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b pb-3">
              <div>
                <h3 className="font-semibold text-foreground text-sm sm:text-base">
                  Cadastro Facial — {enrollModalEmployee.full_name}
                </h3>
                <p className="text-xs text-muted-foreground">
                  Verificação 1:1 voluntária | Modelos locais UniFace
                </p>
              </div>
              <button
                onClick={() => {
                  stopCamera();
                  setEnrollModalEmployee(null);
                }}
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="mt-4 flex flex-col items-center">
              <div className="relative aspect-[4/3] sm:aspect-video w-full max-w-md overflow-hidden rounded-xl border bg-black">
                <video ref={videoRef} autoPlay playsInline muted className="h-full w-full object-cover" />
                <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                  <div className="h-44 w-36 rounded-full border-2 border-dashed border-primary/70" />
                </div>
              </div>

              {/* Botões de Captura */}
              <div className="mt-4 flex flex-wrap items-center justify-center gap-2 sm:gap-3">
                <button
                  onClick={takePhoto}
                  disabled={captures.length >= 3}
                  className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                  <Camera className="h-4 w-4" />
                  Capturar Foto ({captures.length}/3)
                </button>
                {captures.length > 0 && (
                  <button
                    onClick={() => setCaptures([])}
                    className="rounded-lg border px-3 py-2 text-xs text-muted-foreground hover:bg-muted"
                  >
                    Limpar
                  </button>
                )}
              </div>

              {/* Miniaturas de Capturas */}
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                {captures.map((cap, i) => (
                  <div key={i} className="relative h-14 w-14 sm:h-16 sm:w-16 overflow-hidden rounded-lg border">
                    <img src={cap} alt={`Cap ${i}`} className="h-full w-full object-cover" />
                  </div>
                ))}
              </div>

              {enrollMsg && (
                <p className="mt-3 text-center text-xs font-medium text-primary animate-pulse">
                  {enrollMsg}
                </p>
              )}

              <div className="mt-6 flex w-full flex-col sm:flex-row justify-end gap-2 border-t pt-4">
                <button
                  type="button"
                  onClick={() => {
                    stopCamera();
                    setEnrollModalEmployee(null);
                  }}
                  className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted"
                >
                  Fechar
                </button>
                <button
                  type="button"
                  disabled={captures.length < 2 || enrolling}
                  onClick={submitEnrollment}
                  className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
                >
                  {enrolling ? "Processando..." : "Confirmar e Criptografar Biometria"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
