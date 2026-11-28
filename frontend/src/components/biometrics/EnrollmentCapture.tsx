import { useEffect, useRef, useState } from "react";
import { CheckCircle2, Loader2, RotateCcw, X, Volume2, VolumeX, Pause, Play } from "lucide-react";
import { useVoiceGuide } from "./useVoiceGuide";
import { apiFetch } from "@/lib/api";
import { Employee } from "@/types";

type CaptureResult = { accepted: boolean; message: string; required_captures: number };

type EnrollmentProps = { onClose: () => void; onComplete: () => void } & (
  { employee: Pick<Employee, "id" | "full_name">; guest?: never } |
  { guest: { id: string; full_name: string }; employee?: never }
);

export function EnrollmentCapture({ employee, guest, onClose, onComplete }: EnrollmentProps) {
  const person = guest || employee!;
  const identity = guest ? { guest_id: person.id } : { employee_id: person.id };
  const captureUrl = guest ? "/api/v1/events/guests/capture-check" : "/api/v1/biometrics/capture-check";
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const alive = useRef(false);
  const busy = useRef(false);
  const controller = useRef<AbortController | null>(null);
  const rejectedCount = useRef(0);
  const actions = useRef({ capture: () => {}, save: () => {} });
  const [ready, setReady] = useState(false);
  const [cameraError, setCameraError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [captures, setCaptures] = useState<string[]>([]);
  const [required, setRequired] = useState(3);
  const [checking, setChecking] = useState(false);
  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState(false);
  const [paused, setPaused] = useState(false);
  const [visible, setVisible] = useState(!document.hidden);
  const [message, setMessage] = useState("Centralize o rosto e olhe diretamente para a câmera.");
  const voice = useVoiceGuide(cameraError || message);

  useEffect(() => {
    const onVisibility = () => setVisible(!document.hidden);
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []);

  // One request at a time, with a fresh frame after each server response.
  // Saving is automatic only after all required frames have been approved.
  useEffect(() => {
    if (!ready || !visible || cameraError || paused || checking || saving || done) return;
    const timer = window.setInterval(() => {
      if (captures.length === required) actions.current.save();
      else actions.current.capture();
    }, captures.length === required ? 800 : 2500);
    return () => window.clearInterval(timer);
  }, [ready, visible, cameraError, paused, checking, saving, done, captures.length, required]);

  const stopCamera = () => {
    stream.current?.getTracks().forEach(track => track.stop());
    stream.current = null;
  };

  useEffect(() => {
    alive.current = true;
    let cancelled = false;
    setReady(false);
    setCameraError("");
    async function openCamera() {
      try {
        if (!navigator.mediaDevices?.getUserMedia) {
          throw new Error("Para usar a câmera, acesse por HTTPS ou localhost.");
        }
        const media = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } }, audio: false,
        });
        if (cancelled) { media.getTracks().forEach(track => track.stop()); return; }
        stream.current = media;
        if (video.current) {
          video.current.srcObject = media;
          await video.current.play();
          if (!cancelled) {
            setReady(true);
            setMessage("Câmera pronta. Centralize o rosto na marcação e olhe para a câmera. As fotos serão capturadas automaticamente.");
          }
        }
      } catch (error) {
        if (!cancelled) {
          stopCamera();
          setCameraError(error instanceof Error && error.message.includes("HTTPS")
            ? error.message : "Não foi possível abrir a câmera. Verifique a permissão no navegador e tente novamente.");
        }
      }
    }
    openCamera();
    return () => { cancelled = true; alive.current = false; controller.current?.abort(); stopCamera(); };
  }, [attempt]);

  async function capture() {
    if (busy.current || paused || !visible || done || !video.current || !ready || captures.length >= required) return;
    const frame = video.current;
    if (frame.readyState < 2 || !frame.videoWidth) return;
    busy.current = true;
    setChecking(true);
    controller.current = new AbortController();
    try {
    const canvas = document.createElement("canvas");
    const scale = Math.min(1, 960 / Math.max(frame.videoWidth, frame.videoHeight));
    canvas.width = Math.round(frame.videoWidth * scale);
    canvas.height = Math.round(frame.videoHeight * scale);
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Não foi possível capturar a imagem. Tente abrir a câmera novamente.");
    context.drawImage(frame, 0, 0, canvas.width, canvas.height);
    const image = canvas.toDataURL("image/jpeg", 0.9);
      const result = await apiFetch<CaptureResult>(captureUrl, {
        method: "POST", signal: controller.current.signal,
        body: JSON.stringify({ ...identity, image_base64: image }),
      });
      if (!alive.current) return;
      setRequired(result.required_captures);
      setMessage(result.accepted
        ? captures.length + 1 >= result.required_captures
          ? "Todas as capturas foram aprovadas. Concluindo seu cadastro automaticamente."
          : `Captura ${captures.length + 1} de ${result.required_captures} aprovada. Continue olhando para a câmera.`
        : result.message);
      if (result.accepted) {
        rejectedCount.current = 0;
        setCaptures(previous => [...previous, image]);
      } else if (++rejectedCount.current >= 15) {
        setPaused(true);
        setMessage(`${result.message} A captura foi pausada. Ajuste a posição e retome quando estiver pronto.`);
      }
    } catch (error) {
      if (alive.current) {
        setPaused(true);
        setMessage(error instanceof Error ? error.message : "Falha na análise. Tente novamente.");
      }
    } finally {
      busy.current = false;
      if (alive.current) setChecking(false);
    }
  }

  async function save() {
    if (busy.current || paused || !visible || done || captures.length !== required) return;
    busy.current = true;
    setSaving(true);
    setMessage("Conferindo as capturas e salvando seu cadastro facial…");
    controller.current = new AbortController();
    const signal = controller.current.signal;
    try {
      if (guest) {
        await apiFetch("/api/v1/events/guests/enroll", {
          method: "POST", signal, timeoutMs: 60_000,
          body: JSON.stringify({ ...identity, images_base64: captures }),
        });
      } else {
        const options = await apiFetch<{ legal_bases: { id: string }[] }>("/api/v1/biometrics/enrollment-options", { signal });
        if (!options.legal_bases.length) throw new Error("Nenhuma base legal ativa disponível para este cadastro.");
        await apiFetch("/api/v1/biometrics/enroll", {
          method: "POST", signal, timeoutMs: 60_000,
          body: JSON.stringify({ ...identity, images_base64: captures, legal_basis_record_id: options.legal_bases[0].id }),
        });
      }
      if (!alive.current) return;
      stopCamera();
      setCaptures([]);
      setDone(true);
      setMessage("Cadastro facial concluído.");
      onComplete();
    } catch (error) {
      if (alive.current) {
        // Do not automatically retry a write that may already have reached the server.
        setPaused(true);
        setMessage(error instanceof Error ? error.message : "Falha ao salvar. Confira o cadastro antes de tentar novamente.");
      }
    } finally {
      busy.current = false;
      if (alive.current) setSaving(false);
    }
  }

  actions.current = { capture, save };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <section role="dialog" aria-modal="true" aria-labelledby="enrollment-title"
        className="w-full max-w-lg max-h-[95dvh] overflow-auto rounded-2xl bg-card p-6 shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <div><h2 id="enrollment-title" className="text-xl font-semibold">Cadastro facial</h2>
            <p className="text-sm text-muted-foreground">{person.full_name}</p></div>
          <button aria-label="Fechar cadastro" disabled={saving} onClick={onClose} className="rounded-lg p-2 hover:bg-muted disabled:opacity-50"><X size={20} /></button>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <button type="button" onClick={voice.toggle} disabled={!voice.supported} aria-pressed={voice.enabled}
            className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm disabled:opacity-50">
            {voice.enabled ? <VolumeX size={18} /> : <Volume2 size={18} />}
            {voice.enabled ? "Silenciar orientação" : "Ativar orientação por voz"}
          </button>
          {voice.enabled && <button type="button" onClick={voice.repeat} className="rounded-lg border px-3 py-2 text-sm">Repetir orientação</button>}
        </div>
        {(!voice.supported || voice.error) && <p role="status" className="mt-2 text-xs text-muted-foreground">{voice.error || "Este navegador não oferece orientação por voz. Siga as instruções na tela."}</p>}
        {done ? (
          <div className="py-10 text-center"><CheckCircle2 className="mx-auto mb-4 h-14 w-14 text-emerald-600" />
            <p role="status" className="text-lg font-medium">{message}</p>
            <button autoFocus onClick={onClose} className="mt-6 rounded-lg bg-primary px-6 py-3 text-primary-foreground">Concluir</button>
          </div>
        ) : <>
          <p className="mt-4 rounded-lg bg-muted p-3 text-sm">{guest
            ? "Convidado: a biometria pertence a este convite. O acesso depende do evento, da unidade e do horário permitido."
            : "Funcionário: o acesso depende do vínculo ativo, da unidade, da jornada e das exceções autorizadas."}</p>
          <p className="mt-5 text-sm">Fique em um local iluminado, retire acessórios que cubram o rosto e mantenha apenas uma pessoa na câmera.</p>
          <p className="mt-2 text-sm font-medium text-primary">Captura e conclusão automáticas. Basta olhar para a câmera.</p>
          <div className="relative mt-5 aspect-[4/3] overflow-hidden rounded-xl bg-slate-950">
            <video ref={video} autoPlay playsInline muted className="h-full w-full object-contain -scale-x-100" />
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
              <div className={`h-[80%] w-[48%] rounded-[50%] border-4 ${captures.length === required ? "border-emerald-400" : "border-white/80"}`} />
            </div>
            {checking && <div className="absolute inset-0 flex items-center justify-center bg-black/30"><Loader2 className="h-10 w-10 animate-spin text-white" /></div>}
          </div>
          <div className="mt-4 flex justify-center gap-2" aria-label={`${captures.length} de ${required} capturas aprovadas`}>
            {Array.from({ length: required }, (_, i) => <span key={i} className={`h-2 w-12 rounded-full ${i < captures.length ? "bg-emerald-500" : "bg-muted"}`} />)}
          </div>
          <p role="status" aria-live="polite" className="mt-3 min-h-12 text-center text-sm">{cameraError || message}</p>
          <p className="text-center text-xs text-muted-foreground">{captures.length} de {required} capturas aprovadas</p>
          <p className="mt-2 text-center text-xs text-muted-foreground">{saving ? "Salvando cadastro…" : checking ? "Analisando captura…" : paused ? "Captura pausada" : !visible ? "Aguardando retorno à tela" : "Aguardando a próxima captura automática"}</p>
          <div className="mt-5 flex flex-wrap justify-center gap-3">
            {cameraError ? <button onClick={() => setAttempt(n => n + 1)} className="rounded-lg border px-4 py-3">Tentar abrir câmera</button>
              : <button disabled={!ready || saving} onClick={() => {
                  rejectedCount.current = 0;
                  setPaused(value => !value);
                  setMessage(paused ? "Retomando a captura automática. Olhe para a câmera." : "Captura pausada.");
                }} className="flex items-center gap-2 rounded-lg border px-4 py-3 disabled:opacity-50">
                  {paused ? <Play size={16} /> : <Pause size={16} />}{paused ? "Retomar" : "Pausar"}
                </button>}
            {captures.length > 0 && <button disabled={checking || saving} onClick={() => { rejectedCount.current = 0; setCaptures([]); setPaused(false); setMessage("Vamos começar novamente. Centralize seu rosto. A captura é automática."); }}
              className="flex items-center gap-2 rounded-lg border px-4 py-3 disabled:opacity-50"><RotateCcw size={16} />Refazer</button>}
          </div>
          <p className="mt-5 text-center text-xs text-muted-foreground">As capturas são processadas pelo FaceAccess para gerar a representação facial criptografada. Se não conseguir concluir, procure o responsável pelo cadastro.</p>
        </>}
      </section>
    </div>
  );
}
