export type CameraPhase = "idle" | "checking" | "adjust" | "recognizing";

export function CameraGuide({ phase, active }: { phase: CameraPhase; active: boolean }) {
  const scanning = active && (phase === "checking" || phase === "recognizing");
  const color = phase === "recognizing" ? "text-emerald-400" : phase === "adjust" ? "text-rose-400" : "text-sky-300";
  return <div aria-hidden="true" className={`pointer-events-none absolute inset-0 camera-guide ${color}`}>
    <div className={`camera-face-window ${!active ? "opacity-50" : ""}`}>
      {scanning && <div className="camera-scan-line" />}
    </div>
  </div>;
}
