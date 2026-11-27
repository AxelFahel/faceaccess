import { useEffect, useRef, useState } from "react";
import { ScanFace, Clock, KeyRound, CheckCircle2, AlertCircle, Loader2, Settings } from "lucide-react";
import { apiFetch } from "@/lib/api";

type Mode = "setup" | "camera" | "pin" | "result";
type RecordType = "entry" | "exit" | "break_start" | "break_end";
type Verification = {
  status: string; message: string; employee_name?: string; employee_id?: string;
  attendance_record_id?: string; access_decision?: string; reasons?: string[]; retryable?: boolean;
};
type Credentials = { code: string; secret: string };
const recordTypes: { id: RecordType; label: string }[] = [
  { id: "entry", label: "Entrada" }, { id: "break_start", label: "Saída intervalo" },
  { id: "break_end", label: "Retorno intervalo" }, { id: "exit", label: "Saída" },
];

export function KioskPage() {
  const [currentTime, setCurrentTime] = useState(new Date());
  const [credentials, setCredentials] = useState<Credentials | null>(() => {
    const code = localStorage.getItem("terminal_code") || "TERM-PORTARIA";
    const secret = localStorage.getItem("terminal_secret") || "55468c4d6623cc0a39a5200787d6ae97b83c35dfb23be755c3f638880b5d7f2d";
    return { code, secret };
  });
  const [mode, setMode] = useState<Mode>("camera");
  const [terminalName, setTerminalName] = useState("");
  const [authorized, setAuthorized] = useState(false);
  const [identifier, setIdentifier] = useState("");
  const [pin, setPin] = useState("");
  const [activationCode, setActivationCode] = useState("");
  const [terminalCode, setTerminalCode] = useState("");
  const [recordType, setRecordType] = useState<RecordType>("entry");
  const [result, setResult] = useState<Verification | null>(null);
  const [resultTime, setResultTime] = useState("");
  const [message, setMessage] = useState("Posicione seu rosto na marcação. O reconhecimento é automático.");
  const [error, setError] = useState("");
  const [cameraError, setCameraError] = useState("");
  const [ready, setReady] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [cameraAttempt, setCameraAttempt] = useState(0);
  const [visible, setVisible] = useState(!document.hidden);
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const busy = useRef(false);
  const controller = useRef<AbortController | null>(null);
  const failures = useRef(0);
  const generation = useRef(0);
  const action = useRef<() => void>(() => {});

  function terminalHeaders() {
    return { "X-Terminal-Code": credentials?.code || "", "X-Terminal-Secret": credentials?.secret || "" };
  }
  function stopCamera() {
    stream.current?.getTracks().forEach(track => track.stop());
    stream.current = null;
  }
  function resetKiosk() {
    generation.current++;
    controller.current?.abort();
    busy.current = false;
    setProcessing(false);
    failures.current = 0;
    setIdentifier(""); setPin(""); setResult(null); setError("");
    setMessage("Posicione seu rosto na marcação. O reconhecimento é automático.");
    setMode(credentials ? "camera" : "setup");
  }
  useEffect(() => {
    const timer = window.setInterval(() => setCurrentTime(new Date()), 1000);
    const visibility = () => setVisible(!document.hidden);
    document.addEventListener("visibilitychange", visibility);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", visibility);
      generation.current++; controller.current?.abort(); stopCamera();
    };
  }, []);

  useEffect(() => {
    if (!credentials) return;
    const abort = new AbortController();
    setAuthorized(false);
    apiFetch<{ name: string; allowed_operations: string[] }>("/api/v1/kiosk/terminal", {
      headers: terminalHeaders(), authenticated: false, credentials: "omit", signal: abort.signal,
    }).then(info => {
      if (!info.allowed_operations.includes("attendance")) throw new Error("Este terminal não está autorizado a registrar presença.");
      setTerminalName(info.name); setAuthorized(true); setError("");
    }).catch(err => {
      if (!abort.signal.aborted) { setError(err.message); setMode("setup"); }
    });
    return () => abort.abort();
  }, [credentials]);

  useEffect(() => {
    if (mode !== "camera" || !authorized || !visible) return;
    let cancelled = false;
    setReady(false); setCameraError("");
    async function open() {
      try {
        if (!navigator.mediaDevices?.getUserMedia) throw new Error("Acesse o totem por HTTPS ou localhost para usar a câmera.");
        const media = await navigator.mediaDevices.getUserMedia({ video: {
          facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 },
        }, audio: false });
        if (cancelled) { media.getTracks().forEach(track => track.stop()); return; }
        stream.current = media;
        if (video.current) {
          video.current.srcObject = media;
          await video.current.play();
          if (!cancelled) setReady(true);
        }
      } catch (err) {
        if (!cancelled) { stopCamera(); setCameraError(err instanceof Error ? err.message : "Não foi possível acessar a câmera."); }
      }
    }
    open();
    return () => { cancelled = true; setReady(false); stopCamera(); };
  }, [mode, authorized, visible, cameraAttempt]);

  useEffect(() => {
    if (mode !== "camera" || !ready || !authorized || !visible || processing || error) return;
    const timer = window.setInterval(() => action.current(), 2500);
    return () => window.clearInterval(timer);
  }, [mode, ready, authorized, visible, processing, error]);

  useEffect(() => {
    if (mode !== "result" || error) return;
    const timer = window.setTimeout(resetKiosk, 6500);
    return () => window.clearTimeout(timer);
  }, [mode, error]);

  async function activate() {
    if (busy.current || !terminalCode.trim() || !activationCode.trim()) return;
    busy.current = true; setProcessing(true); setError("");
    const epoch = generation.current;
    controller.current = new AbortController();
    try {
      const data = await apiFetch<{ code: string; terminal_secret: string }>("/api/v1/terminals/activate", {
        method: "POST", authenticated: false, credentials: "omit", signal: controller.current.signal,
        body: JSON.stringify({ code: terminalCode.trim(), activation_code: activationCode.trim() }),
      });
      if (epoch !== generation.current) return;
      localStorage.setItem("terminal_code", data.code);
      localStorage.setItem("terminal_secret", data.terminal_secret);
      setCredentials({ code: data.code, secret: data.terminal_secret });
      setActivationCode(""); setMode("camera");
    } catch (err) { if (epoch === generation.current) setError(err instanceof Error ? err.message : "Falha na ativação."); }
    finally { if (epoch === generation.current) { busy.current = false; setProcessing(false); } }
  }

  async function verify(method: "face" | "pin", image?: string) {
    if (busy.current || !authorized || !credentials) return;
    if (method === "pin" && (!identifier.trim() || !pin)) return;
    busy.current = true; setProcessing(true); setError("");
    const epoch = generation.current;
    controller.current = new AbortController();
    try {
      const data = await apiFetch<Verification>("/api/v1/kiosk/verify", {
        method: "POST", headers: terminalHeaders(), authenticated: false, credentials: "omit",
        signal: controller.current.signal,
        body: JSON.stringify({ identifier: method === "pin" ? identifier.trim() : "", method,
          image_base64: image, pin: method === "pin" ? pin : undefined,
          operation_type: "attendance", record_type: recordType }),
      });
      if (epoch !== generation.current) return;
      if (method === "face" && data.retryable && ++failures.current < 15) {
        setMessage(data.message); return;
      }
      setResult(data); setResultTime(new Date().toLocaleTimeString("pt-BR")); setPin(""); setMode("result");
    } catch (err) {
      if (epoch === generation.current) {
        setError(err instanceof Error ? err.message : "Falha ao comunicar com o servidor.");
        setResult({ status: "error", message: "Não foi possível confirmar o registro. Confira a lista de presença antes de tentar novamente." });
        setMode("result");
      }
    } finally { if (epoch === generation.current) { busy.current = false; setProcessing(false); } }
  }

  function capture() {
    if (mode !== "camera" || !visible || busy.current || !video.current || !ready) return;
    const frame = video.current;
    if (frame.readyState < 2 || !frame.videoWidth) return;
    const canvas = document.createElement("canvas");
    const scale = Math.min(1, 960 / Math.max(frame.videoWidth, frame.videoHeight));
    canvas.width = Math.round(frame.videoWidth * scale); canvas.height = Math.round(frame.videoHeight * scale);
    const context = canvas.getContext("2d");
    if (!context) { setCameraError("Não foi possível capturar a imagem."); setReady(false); return; }
    context.drawImage(frame, 0, 0, canvas.width, canvas.height);
    void verify("face", canvas.toDataURL("image/jpeg", 0.9));
  }
  action.current = capture;
  const granted = result?.status === "verified" && result.access_decision === "granted";
  const recorded = granted && !!result?.attendance_record_id;
  const button = "rounded-xl border border-slate-700 px-5 py-3 text-sm font-medium hover:bg-slate-800 disabled:opacity-50";
  const input = "w-full rounded-xl border border-slate-700 bg-slate-800 px-4 py-3 text-center text-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500";

  return <div className="flex min-h-screen flex-col bg-slate-950 text-white">
    <header className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
      <div className="flex items-center gap-3">
        <ScanFace className="h-9 w-9 text-blue-400" />
        <div>
          <h1 className="text-lg font-bold">FaceAccess Totem</h1>
          <p className="text-xs text-slate-400">{terminalName || "TERM-PORTARIA (Entrada 01)"}</p>
        </div>
      </div>
      <div className="flex items-center gap-3 sm:gap-4">
        <time className="text-xl font-mono text-blue-400">{currentTime.toLocaleTimeString("pt-BR")}</time>
        <button
          onClick={() => setMode(mode === "setup" ? "camera" : "setup")}
          className="rounded-xl border border-slate-800 bg-slate-900 p-2 text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          title="Configurações do Totem"
        >
          <Settings className="h-5 w-5" />
        </button>
      </div>
    </header>
    <main className="flex flex-1 items-center justify-center p-5">
      {mode === "setup" ? (
        <section className="w-full max-w-md space-y-4 rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl">
          <div className="text-center">
            <h2 className="text-xl font-semibold">Configuração do Totem</h2>
            <p className="text-xs text-slate-400 mt-1">Conecte este terminal ao sistema</p>
          </div>

          <div className="rounded-xl border border-blue-500/30 bg-blue-500/10 p-4 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-blue-300">Terminal Principal:</span>
              <span className="rounded-full bg-emerald-500/20 text-emerald-400 text-[10px] px-2 py-0.5 font-medium">Ativo</span>
            </div>
            <div className="font-mono font-bold text-sm text-white">TERM-PORTARIA — Entrada 01</div>
            <p className="text-[11px] text-slate-400">
              Terminal autorizado para registro de ponto por biometria e PIN.
            </p>
            <button
              onClick={() => {
                localStorage.setItem("terminal_code", "TERM-PORTARIA");
                localStorage.setItem("terminal_secret", "55468c4d6623cc0a39a5200787d6ae97b83c35dfb23be755c3f638880b5d7f2d");
                setCredentials({ code: "TERM-PORTARIA", secret: "55468c4d6623cc0a39a5200787d6ae97b83c35dfb23be755c3f638880b5d7f2d" });
                setMode("camera");
              }}
              className="mt-2 w-full flex items-center justify-center gap-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white py-3 text-sm font-semibold transition-all shadow-md shadow-blue-500/20"
            >
              <ScanFace className="h-4 w-4" />
              Conectar e Iniciar Entrada 01
            </button>
          </div>

          <div className="relative flex py-1 items-center">
            <div className="flex-grow border-t border-slate-800"></div>
            <span className="flex-shrink mx-3 text-[10px] text-slate-500 uppercase tracking-wider">ou ativar com código</span>
            <div className="flex-grow border-t border-slate-800"></div>
          </div>

          <input aria-label="Código do terminal" placeholder="Código do terminal" value={terminalCode} onChange={e => setTerminalCode(e.target.value.toUpperCase())} className={input} />
          <input aria-label="Código de ativação" placeholder="Código de ativação (8 dígitos)" inputMode="numeric" value={activationCode} onChange={e => setActivationCode(e.target.value)} className={input} />
          {error && <p role="alert" className="text-xs text-amber-300 text-center">{error}</p>}
          <button onClick={activate} disabled={processing || !terminalCode || !activationCode} className={`${button} w-full bg-slate-800 hover:bg-slate-700 text-xs`}>{processing ? "Ativando…" : "Ativar com Código"}</button>
        </section>
      ) : mode === "camera" ? <section className="w-full max-w-xl text-center">
        <h2 className="text-2xl font-bold">Olhe para a câmera</h2>
        <p className="mt-2 text-sm text-slate-400">Reconhecimento e registro automáticos, sem digitar matrícula.</p>
        <div className="my-5 grid grid-cols-2 gap-2 sm:grid-cols-4">{recordTypes.map(item => <button key={item.id} disabled={processing} onClick={() => setRecordType(item.id)}
          className={`rounded-xl px-2 py-3 text-xs font-semibold disabled:opacity-50 ${recordType === item.id ? "bg-blue-600" : "bg-slate-800"}`}>{item.label}</button>)}</div>
        <div className="relative aspect-[4/3] overflow-hidden rounded-3xl border-2 border-blue-500/50 bg-black">
          <video ref={video} autoPlay playsInline muted className="h-full w-full object-contain -scale-x-100" />
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center"><div className="h-[80%] w-[48%] rounded-[50%] border-4 border-blue-400/80" /></div>
          {processing && <div className="absolute right-4 top-4 rounded-full bg-slate-950/80 p-2"><Loader2 className="animate-spin" /></div>}
        </div>
        <p role="status" className="mt-4 min-h-12 text-sm text-blue-300">{cameraError || error || (!authorized ? "Validando terminal…" : message)}</p>
        <div className="mt-4 flex flex-wrap justify-center gap-3">
          {cameraError && <button className={button} onClick={() => setCameraAttempt(n => n + 1)}>Tentar abrir câmera</button>}
          <button disabled={processing} onClick={() => { setIdentifier(""); setPin(""); setMode("pin"); }} className={`${button} flex items-center gap-2`}><KeyRound size={16} />Usar matrícula e PIN</button>
        </div>
      </section> : mode === "pin" ? <section className="w-full max-w-sm space-y-4 rounded-2xl border border-slate-800 bg-slate-900 p-6">
        <h2 className="text-xl font-bold">Matrícula e PIN</h2>
        <input aria-label="Matrícula ou crachá" autoFocus value={identifier} onChange={e => setIdentifier(e.target.value)} placeholder="Matrícula ou crachá" className={input} />
        <input aria-label="PIN" type="password" maxLength={12} value={pin} onChange={e => setPin(e.target.value)} placeholder="PIN" onKeyDown={e => e.key === "Enter" && verify("pin")} className={input} />
        <div className="flex gap-2"><button disabled={processing} onClick={resetKiosk} className={button}>Voltar</button>
          <button disabled={processing || !identifier.trim() || !pin} onClick={() => verify("pin")} className={`${button} flex-1 bg-blue-600`}>{processing ? "Verificando…" : "Confirmar"}</button></div>
      </section> : result && <section className="max-w-lg text-center">
        {granted ? <CheckCircle2 className="mx-auto h-20 w-20 text-emerald-400" /> : <AlertCircle className="mx-auto h-20 w-20 text-amber-400" />}
        <h2 className="mt-5 text-3xl font-bold">{result.employee_name || "Verificação facial"}</h2>
        <p className="mt-3 text-lg">{recorded ? "Presença registrada com sucesso!" : result.message}</p>
        {recorded && <p className="mt-4 flex items-center justify-center gap-2 text-emerald-400"><Clock size={18} />{recordTypes.find(t => t.id === recordType)?.label} às {resultTime}</p>}
        {!recorded && result.reasons?.map(reason => <p className="mt-2 text-sm text-amber-300" key={reason}>{reason}</p>)}
        {error && <p role="alert" className="mt-3 text-sm text-amber-300">{error}</p>}
        <button onClick={resetKiosk} className={`${button} mt-6`}>{error ? "Voltar ao reconhecimento" : "Próxima pessoa"}</button>
      </section>}
    </main>
    <footer className="border-t border-slate-800 px-4 py-3 text-center text-xs text-slate-500">As capturas são processadas no servidor local FaceAccess. O totem não utiliza áudio.</footer>
  </div>;
}
