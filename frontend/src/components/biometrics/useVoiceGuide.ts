import { useCallback, useEffect, useRef, useState } from "react";

// Start speech in the gesture that opens enrollment, for browsers that require it.
export function startVoiceGuide() {
  if (!("speechSynthesis" in window)) return;
  const voice = window.speechSynthesis.getVoices().find(v => v.localService && /^pt[-_]BR$/i.test(v.lang));
  if (!voice) return;
  window.speechSynthesis.cancel();
  const speech = new SpeechSynthesisUtterance("Vamos iniciar o cadastro facial. Olhe para a câmera.");
  speech.voice = voice;
  speech.lang = voice.lang;
  window.speechSynthesis.speak(speech);
}

export function useVoiceGuide(instruction: string) {
  const supported = typeof window !== "undefined" && "speechSynthesis" in window;
  const [enabled, setEnabled] = useState(true);
  const [voicesVersion, setVoicesVersion] = useState(0);
  const [error, setError] = useState("");
  const last = useRef("");
  const utterance = useRef<SpeechSynthesisUtterance | null>(null);

  const speak = useCallback((text: string) => {
    if (!supported) return;
    const synth = window.speechSynthesis;
    const voices = synth.getVoices().filter(v => v.localService && /^pt(?:-|_)/i.test(v.lang));
    const voice = voices.find(v => /^pt[-_]BR$/i.test(v.lang)) || voices[0];
    if (!voice) {
      setError("Voz local em português indisponível. Ative uma voz em português nas configurações de fala do dispositivo e tente novamente.");
      return;
    }
    synth.cancel();
    const speech = new SpeechSynthesisUtterance(text);
    utterance.current = speech;
    speech.voice = voice;
    speech.lang = voice.lang;
    speech.rate = 0.95;
    speech.onerror = event => {
      if (utterance.current !== speech || event.error === "interrupted" || event.error === "canceled") return;
      setError(event.error === "not-allowed"
        ? "O navegador bloqueou o áudio automático. Toque em Repetir orientação para liberar a voz."
        : "Não foi possível reproduzir a voz. Você pode continuar pelas orientações na tela.");
    };
    last.current = text;
    setError("");
    synth.speak(speech);
  }, [supported]);

  useEffect(() => {
    // Voices can arrive asynchronously on mobile; retry without requiring activation.
    const voicesChanged = () => { last.current = ""; setVoicesVersion(version => version + 1); };
    if (supported) {
      window.speechSynthesis.getVoices();
      window.speechSynthesis.addEventListener("voiceschanged", voicesChanged);
    }
    return () => {
      utterance.current = null;
      if (supported) {
        window.speechSynthesis.removeEventListener("voiceschanged", voicesChanged);
        window.speechSynthesis.cancel();
      }
    };
  }, [supported]);

  useEffect(() => {
    if (enabled && instruction !== last.current) speak(instruction);
  }, [enabled, instruction, speak, voicesVersion]);

  const toggle = () => {
    if (enabled) {
      utterance.current = null;
      window.speechSynthesis.cancel();
      setEnabled(false);
    } else {
      setEnabled(true);
      speak(instruction);
    }
  };
  return { supported, enabled, error, toggle, repeat: () => speak(instruction) };
}
