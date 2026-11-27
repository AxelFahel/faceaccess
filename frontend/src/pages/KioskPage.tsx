import React, { useEffect, useState, useRef } from "react";
import {
  ScanFace,
  Clock,
  KeyRound,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  ArrowLeft,
  Volume2,
} from "lucide-react";

export function KioskPage() {
  const [currentTime, setCurrentTime] = useState(new Date());
  const [identifier, setIdentifier] = useState("");
  const [pin, setPin] = useState("");
  const [mode, setMode] = useState<"identify" | "camera" | "pin" | "result">("identify");
  const [recordType, setRecordType] = useState<"entry" | "exit" | "break_start" | "break_end">("entry");
  const [result, setResult] = useState<any>(null);
  const [statusMessage, setStatusMessage] = useState("");

  const videoRef = useRef<HTMLVideoElement>(null);

  // Relógio em tempo real
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: "user" },
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
    } catch (err) {
      console.error(err);
      setStatusMessage("Erro ao acessar câmera local.");
    }
  };

  const stopCamera = () => {
    if (videoRef.current && videoRef.current.srcObject) {
      const stream = videoRef.current.srcObject as MediaStream;
      stream.getTracks().forEach((t) => t.stop());
      videoRef.current.srcObject = null;
    }
  };

  const handleStartFaceVerify = () => {
    if (!identifier.trim()) return;
    setMode("camera");
    setTimeout(startCamera, 100);
  };

  const handleCaptureAndVerify = async () => {
    if (!videoRef.current) return;
    setStatusMessage("Verificando identidade e vivacidade...");
    const canvas = document.createElement("canvas");
    canvas.width = videoRef.current.videoWidth || 640;
    canvas.height = videoRef.current.videoHeight || 480;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
    const b64 = canvas.toDataURL("image/jpeg", 0.9);

    stopCamera();

    try {
      const termCode = localStorage.getItem("terminal_code") || "TERM-01";
      const termSecret = localStorage.getItem("terminal_secret") || "demo-secret";

      const res = await fetch("/api/v1/kiosk/verify", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Terminal-Code": termCode,
          "X-Terminal-Secret": termSecret,
        },
        body: JSON.stringify({
          identifier,
          method: "face",
          image_base64: b64,
          operation_type: "attendance",
          record_type: recordType,
        }),
      });

      const data = await res.json();
      setResult(data);
      setMode("result");
      // Retorno automático após 5 segundos
      setTimeout(resetKiosk, 5000);
    } catch (err: any) {
      setResult({ status: "rejected", message: err.message || "Erro no terminal." });
      setMode("result");
      setTimeout(resetKiosk, 5000);
    }
  };

  const handlePinVerify = async () => {
    try {
      const termCode = localStorage.getItem("terminal_code") || "TERM-01";
      const termSecret = localStorage.getItem("terminal_secret") || "demo-secret";

      const res = await fetch("/api/v1/kiosk/verify", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Terminal-Code": termCode,
          "X-Terminal-Secret": termSecret,
        },
        body: JSON.stringify({
          identifier,
          method: "pin",
          pin,
          operation_type: "attendance",
          record_type: recordType,
        }),
      });

      const data = await res.json();
      setResult(data);
      setMode("result");
      setTimeout(resetKiosk, 5000);
    } catch (err: any) {
      setResult({ status: "rejected", message: err.message || "Erro no terminal." });
      setMode("result");
      setTimeout(resetKiosk, 5000);
    }
  };

  const resetKiosk = () => {
    stopCamera();
    setIdentifier("");
    setPin("");
    setResult(null);
    setStatusMessage("");
    setMode("identify");
  };

  return (
    <div className="flex min-h-screen w-full flex-col bg-slate-950 text-white select-none overflow-x-hidden">
      {/* Top Header */}
      <header className="flex h-16 sm:h-20 shrink-0 items-center justify-between border-b border-slate-800 px-4 sm:px-8 bg-slate-900/50">
        <div className="flex items-center gap-2.5 sm:gap-3">
          <div className="flex h-10 w-10 sm:h-12 sm:w-12 shrink-0 items-center justify-center rounded-xl sm:rounded-2xl bg-blue-600 shadow-lg shadow-blue-500/20">
            <ScanFace className="h-5 w-5 sm:h-7 sm:w-7 text-white" />
          </div>
          <div>
            <h1 className="text-base sm:text-xl font-bold tracking-tight">FaceAccess Terminal</h1>
            <p className="text-[10px] sm:text-xs text-slate-400">Verificação Facial & Presença</p>
          </div>
        </div>

        <div className="text-right">
          <div className="text-xl sm:text-2xl font-mono font-bold tracking-wider text-blue-400">
            {currentTime.toLocaleTimeString("pt-BR")}
          </div>
          <div className="hidden sm:block text-xs text-slate-400 capitalize">
            {currentTime.toLocaleDateString("pt-BR", {
              weekday: "long",
              day: "numeric",
              month: "long",
            })}
          </div>
        </div>
      </header>

      {/* Main Kiosk Area */}
      <main className="flex flex-1 items-center justify-center p-4 sm:p-8">
        {mode === "identify" && (
          <div className="w-full max-w-lg rounded-2xl sm:rounded-3xl border border-slate-800 bg-slate-900/60 p-5 sm:p-8 shadow-2xl backdrop-blur">
            <div className="mb-5 sm:mb-6 text-center">
              <h2 className="text-xl sm:text-2xl font-bold">Identificação Funcional</h2>
              <p className="mt-1 text-xs sm:text-sm text-slate-400">
                Declare sua matrícula ou aproxime seu crachá
              </p>
            </div>

            {/* Seleção do tipo de registro */}
            <div className="mb-5 sm:mb-6 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {[
                { id: "entry", label: "Entrada" },
                { id: "break_start", label: "Saída Int." },
                { id: "break_end", label: "Retorno Int." },
                { id: "exit", label: "Saída" },
              ].map((t) => (
                <button
                  key={t.id}
                  onClick={() => setRecordType(t.id as any)}
                  className={`rounded-xl py-2.5 text-xs font-semibold transition-all ${
                    recordType === t.id
                      ? "bg-blue-600 text-white shadow-md shadow-blue-500/20"
                      : "border border-slate-800 bg-slate-800/50 text-slate-400 hover:text-white"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            <div className="space-y-4">
              <input
                type="text"
                autoFocus
                placeholder="Digite a matrícula ou crachá..."
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleStartFaceVerify()}
                className="w-full rounded-xl sm:rounded-2xl border border-slate-700 bg-slate-800/80 px-4 py-3.5 sm:px-5 sm:py-4 text-center font-mono text-lg sm:text-xl tracking-wider text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none focus:ring-4 focus:ring-blue-500/20"
              />

              <button
                onClick={handleStartFaceVerify}
                disabled={!identifier.trim()}
                className="flex w-full items-center justify-center gap-2 rounded-xl sm:rounded-2xl bg-blue-600 py-3.5 sm:py-4 text-sm sm:text-base font-semibold text-white shadow-lg shadow-blue-500/25 hover:bg-blue-500 disabled:opacity-50 transition-all"
              >
                <ScanFace className="h-5 w-5" />
                Prosseguir com Verificação Facial
              </button>

              <div className="flex items-center justify-center pt-2">
                <button
                  onClick={() => setMode("pin")}
                  className="flex items-center gap-1.5 text-xs font-medium text-slate-400 hover:text-white"
                >
                  <KeyRound className="h-4 w-4" />
                  Alternativa não biométrica (Digitar PIN)
                </button>
              </div>
            </div>
          </div>
        )}

        {mode === "camera" && (
          <div className="flex w-full max-w-xl flex-col items-center">
            <div className="relative aspect-[4/3] sm:aspect-video w-full overflow-hidden rounded-2xl sm:rounded-3xl border-2 border-blue-500/50 bg-black shadow-2xl">
              <video ref={videoRef} autoPlay playsInline muted className="h-full w-full object-cover" />
              <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                <div className="h-44 w-36 sm:h-64 sm:w-52 rounded-full border-4 border-dashed border-blue-400/80 animate-pulse" />
              </div>
            </div>

            <p className="mt-4 text-center text-xs sm:text-sm font-medium text-blue-400 px-2">
              {statusMessage || "Centralize o rosto no visor oval e mantenha os olhos abertos"}
            </p>

            <div className="mt-6 flex w-full flex-col sm:flex-row justify-center gap-3">
              <button
                onClick={resetKiosk}
                className="w-full sm:w-auto rounded-xl border border-slate-700 px-6 py-3 text-sm font-medium hover:bg-slate-800"
              >
                Cancelar
              </button>
              <button
                onClick={handleCaptureAndVerify}
                className="w-full sm:w-auto rounded-xl bg-blue-600 px-8 py-3 font-semibold shadow-lg shadow-blue-500/25 hover:bg-blue-500"
              >
                Confirmar Captura
              </button>
            </div>
          </div>
        )}

        {mode === "pin" && (
          <div className="w-full max-w-sm rounded-2xl sm:rounded-3xl border border-slate-800 bg-slate-900/60 p-5 sm:p-8 shadow-2xl backdrop-blur">
            <h2 className="text-center text-lg sm:text-xl font-bold">Verificação por PIN</h2>
            <p className="mt-1 text-center text-xs text-slate-400">
              Alternativa individual sem biometria
            </p>

            <div className="mt-6 space-y-4">
              <input
                type="password"
                maxLength={12}
                autoFocus
                placeholder="Digite seu PIN..."
                value={pin}
                onChange={(e) => setPin(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handlePinVerify()}
                className="w-full rounded-xl sm:rounded-2xl border border-slate-700 bg-slate-800 px-4 py-3 text-center text-xl sm:text-2xl tracking-widest text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <div className="flex gap-2">
                <button
                  onClick={() => setMode("identify")}
                  className="w-1/2 rounded-xl border border-slate-700 py-3 text-sm font-medium hover:bg-slate-800"
                >
                  Voltar
                </button>
                <button
                  onClick={handlePinVerify}
                  className="w-1/2 rounded-xl bg-blue-600 py-3 text-sm font-semibold hover:bg-blue-500"
                >
                  Confirmar
                </button>
              </div>
            </div>
          </div>
        )}

        {mode === "result" && result && (
          <div className="flex flex-col items-center text-center p-4">
            {result.status === "verified" ? (
              <div className="flex h-20 w-20 sm:h-24 sm:w-24 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400 mb-5 sm:mb-6 shadow-xl shadow-emerald-500/10">
                <CheckCircle2 className="h-10 w-10 sm:h-14 sm:w-14" />
              </div>
            ) : (
              <div className="flex h-20 w-20 sm:h-24 sm:w-24 items-center justify-center rounded-full bg-rose-500/20 text-rose-400 mb-5 sm:mb-6 shadow-xl shadow-rose-500/10">
                <AlertCircle className="h-10 w-10 sm:h-14 sm:w-14" />
              </div>
            )}

            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight">
              {result.employee_name || "Resultado"}
            </h2>
            <p className="mt-2 text-base sm:text-lg text-slate-300 max-w-md">{result.message}</p>

            {result.status === "verified" && (
              <div className="mt-6 inline-flex items-center gap-2 rounded-full bg-emerald-500/10 border border-emerald-500/20 px-4 py-1.5 text-xs sm:text-sm font-medium text-emerald-400">
                <Clock className="h-4 w-4" />
                Presença Registrada em {currentTime.toLocaleTimeString("pt-BR")}
              </div>
            )}

            <button
              onClick={resetKiosk}
              className="mt-8 rounded-xl border border-slate-700 px-6 py-2.5 text-sm text-slate-400 hover:text-white"
            >
              Concluir e Voltar ao Início
            </button>
          </div>
        )}
      </main>

      {/* Footer LGPD Note */}
      <footer className="border-t border-slate-800/80 px-4 sm:px-8 py-3 text-center text-[10px] sm:text-xs text-slate-500">
        Processamento facial estritamente local em tempo real | Nenhuma imagem é gravada ou transmitida para fora deste terminal.
      </footer>
    </div>
  );
}
