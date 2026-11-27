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
  Upload,
  AlertTriangle,
  RotateCcw,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { resizeImageBase64 } from "@/lib/image";
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
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [captures, setCaptures] = useState<string[]>([]);
  const [enrolling, setEnrolling] = useState(false);
  const [enrollMsg, setEnrollMsg] = useState("");
  const [cameraError, setCameraError] = useState("");

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

  // Camera lifecycle for enrollment
  useEffect(() => {
    if (enrollModalEmployee) {
      // Delay slightly to ensure video element is attached to DOM
      const timer = setTimeout(() => {
        startCamera();
      }, 150);
      return () => {
        clearTimeout(timer);
        stopCamera();
      };
    } else {
      stopCamera();
    }
  }, [enrollModalEmployee]);

  const startCamera = async () => {
    setCameraError("");
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setCameraError(
          "Câmera de vídeo contínuo exige conexão segura (HTTPS) no celular. Use o botão azul 'Tirar Foto com Câmera do Celular' abaixo ou acesse via https://."
        );
        return;
      }

      let stream: MediaStream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
          audio: false,
        });
      } catch (e1) {
        // Fallback for devices/browsers that don't support explicit constraints
        stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      }

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.setAttribute("playsinline", "true");
        videoRef.current.muted = true;
        await videoRef.current.play().catch((e) => console.warn("Video play interrupted:", e));
      }
    } catch (err: any) {
      console.error("Erro ao acessar câmera:", err);
      setCameraError(
        "Acesso à câmera bloqueado ou não autorizado pelo navegador. Use o botão 'Tirar Foto com Câmera do Celular' abaixo."
      );
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
      const b64 = canvas.toDataURL("image/jpeg", 0.92);
      setCaptures((prev) => [...prev, b64].slice(0, 3));
    }
  };

  const handleNativeCapture = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    try {
      setEnrollMsg("Otimizando resolução da imagem...");
      for (let i = 0; i < files.length; i++) {
        const b64 = await resizeImageBase64(files[i], 1280);
        setCaptures((prev) => {
          if (prev.length >= 3) return prev;
          return [...prev, b64];
        });
      }
      setEnrollMsg("");
    } catch (err: any) {
      setEnrollMsg(`Erro no processamento da imagem: ${err.message}`);
    } finally {
      if (e.target) e.target.value = "";
    }
  };

  const submitEnrollment = async () => {
    if (!enrollModalEmployee) return;
    if (captures.length === 0) {
      setEnrollMsg("Tire ou anexe ao menos 1 foto com rosto visível.");
      return;
    }
    setEnrolling(true);
    setEnrollMsg("Analisando qualidade, iluminação, vivacidade e gerando biometria...");
    try {
      const legalBases = await apiFetch<{ id: string }[]>("/api/v1/privacy/legal-basis");
      const legalBasisId = legalBases.length > 0 ? legalBases[0].id : undefined;
      if (!legalBasisId) {
        throw new Error("Nenhuma base legal ativa encontrada no sistema.");
      }
      await apiFetch("/api/v1/biometrics/enroll", {
        method: "POST",
        body: JSON.stringify({
          employee_id: enrollModalEmployee.id,
          images_base64: captures,
          legal_basis_record_id: legalBasisId,
        }),
      });
      setEnrollMsg("✓ Biometria cadastrada e criptografada com sucesso!");
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

            {/* Aviso sobre Câmera HTTP vs Celular */}
            {cameraError && (
              <div className="mt-4 rounded-xl bg-amber-500/10 border border-amber-500/20 p-3 text-xs text-amber-700 dark:text-amber-300 flex items-start gap-2.5">
                <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-amber-500" />
                <div className="space-y-1">
                  <p className="font-medium">{cameraError}</p>
                </div>
              </div>
            )}

            <div className="mt-4 flex flex-col items-center">
              {/* Input escondido para acionamento nativo da câmera do smartphone ou seleção de arquivo */}
              <input
                type="file"
                ref={fileInputRef}
                accept="image/*"
                capture="user"
                onChange={handleNativeCapture}
                className="hidden"
              />

              {/* Viewport da Câmera ao vivo (se disponível) */}
              <div className="relative aspect-[4/3] sm:aspect-video w-full max-w-md overflow-hidden rounded-xl border bg-black shadow-inner">
                <video ref={videoRef} autoPlay playsInline muted className="h-full w-full object-cover" />
                <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                  <div className="h-44 w-36 rounded-full border-2 border-dashed border-primary/70 animate-pulse" />
                </div>
              </div>

              {/* Botões de Ação para Captura */}
              <div className="mt-4 flex flex-wrap items-center justify-center gap-2 sm:gap-3">
                <button
                  type="button"
                  onClick={takePhoto}
                  disabled={captures.length >= 3}
                  className="flex items-center gap-2 rounded-lg bg-primary px-3 sm:px-4 py-2 text-xs sm:text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                  title="Capturar da visualização ao vivo acima"
                >
                  <Camera className="h-4 w-4" />
                  Capturar Foto ao Vivo
                </button>

                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={captures.length >= 3}
                  className="flex items-center gap-2 rounded-lg bg-blue-600 px-3 sm:px-4 py-2 text-xs sm:text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50 shadow-sm"
                  title="Abre diretamente a câmera selfie nativa do smartphone"
                >
                  <Upload className="h-4 w-4" />
                  Tirar Foto com Câmera do Celular / Upload
                </button>

                {captures.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setCaptures([])}
                    className="flex items-center gap-1 rounded-lg border px-3 py-2 text-xs text-muted-foreground hover:bg-muted"
                  >
                    <RotateCcw className="h-3.5 w-3.5" />
                    Limpar Fotos
                  </button>
                )}
              </div>

              {/* Miniaturas das fotos prontas */}
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                {captures.map((cap, i) => (
                  <div key={i} className="relative h-16 w-16 sm:h-20 sm:w-20 overflow-hidden rounded-lg border-2 border-emerald-500 shadow-sm">
                    <img src={cap} alt={`Foto ${i + 1}`} className="h-full w-full object-cover" />
                    <span className="absolute bottom-0 inset-x-0 bg-black/70 text-[10px] text-center text-white py-0.5">
                      Foto #{i + 1}
                    </span>
                  </div>
                ))}
              </div>

              {captures.length === 0 && (
                <p className="mt-2 text-xs text-muted-foreground text-center">
                  Nenhuma foto capturada ainda. Tire pelo menos 1 foto nítida frontal.
                </p>
              )}

              {enrollMsg && (
                <div className={`mt-3 rounded-lg p-2.5 text-center text-xs font-medium ${
                  enrollMsg.startsWith("✓")
                    ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                    : enrollMsg.startsWith("Falha")
                    ? "bg-destructive/10 text-destructive font-semibold"
                    : "bg-primary/10 text-primary animate-pulse"
                }`}>
                  {enrollMsg}
                </div>
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
                  Cancelar
                </button>
                <button
                  type="button"
                  disabled={captures.length < 1 || enrolling}
                  onClick={submitEnrollment}
                  className="rounded-lg bg-emerald-600 px-5 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50 shadow-md"
                >
                  {enrolling
                    ? "Processando..."
                    : `Confirmar e Gravar Biometria (${captures.length} foto${captures.length > 1 ? "s" : ""})`}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
