import React, { useEffect, useRef, useState } from "react";
import {
  CalendarDays,
  Plus,
  Users,
  Clock,
  MapPin,
  Camera,
  Trash2,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Search,
  X,
  UserPlus,
  ShieldCheck,
  ShieldAlert,
  Upload,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

interface EventItem {
  id: string;
  unit_id: string;
  name: string;
  description?: string;
  location_name?: string;
  starts_at: string;
  ends_at: string;
  early_entry_minutes: number;
  late_entry_minutes: number;
  is_active: boolean;
  guest_count?: number;
  created_at: string;
}

interface EventGuest {
  id: string;
  event_id: string;
  full_name: string;
  identifier: string;
  email?: string;
  phone?: string;
  organization_represented?: string;
  biometric_status: string;
  status: string;
  first_access_at?: string;
  last_access_at?: string;
  access_count: number;
  created_at: string;
}

interface Unit {
  id: string;
  name: string;
}

export function EventsPage() {
  const [events, setEvents] = useState<EventItem[]>([]);
  const [units, setUnits] = useState<Unit[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  // Create Event Modal state
  const [showEventModal, setShowEventModal] = useState(false);
  const [eventName, setEventName] = useState("");
  const [unitId, setUnitId] = useState("");
  const [locationName, setLocationName] = useState("");
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [earlyMinutes, setEarlyMinutes] = useState(30);
  const [lateMinutes, setLateMinutes] = useState(60);
  const [description, setDescription] = useState("");
  const [submittingEvent, setSubmittingEvent] = useState(false);

  // Selected Event & Guests state
  const [selectedEvent, setSelectedEvent] = useState<EventItem | null>(null);
  const [guests, setGuests] = useState<EventGuest[]>([]);
  const [loadingGuests, setLoadingGuests] = useState(false);

  // Add Guest Modal state
  const [showGuestModal, setShowGuestModal] = useState(false);
  const [guestName, setGuestName] = useState("");
  const [guestIdent, setGuestIdent] = useState("");
  const [guestEmail, setGuestEmail] = useState("");
  const [guestPhone, setGuestPhone] = useState("");
  const [guestOrg, setGuestOrg] = useState("");
  const [guestPin, setGuestPin] = useState("");
  const [autoOpenEnroll, setAutoOpenEnroll] = useState(true);
  const [submittingGuest, setSubmittingGuest] = useState(false);

  // Biometric Enroll Modal state for Guest
  const [enrollGuest, setEnrollGuest] = useState<EventGuest | null>(null);
  const [enrollImages, setEnrollImages] = useState<string[]>([]);
  const [submittingEnroll, setSubmittingEnroll] = useState(false);
  const [cameraActive, setCameraActive] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const loadEvents = () => {
    setLoading(true);
    apiFetch<EventItem[]>("/api/v1/events")
      .then((data) => {
        setEvents(data);
        if (selectedEvent) {
          const updated = data.find((e) => e.id === selectedEvent.id);
          if (updated) setSelectedEvent(updated);
        }
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadEvents();
    apiFetch<Unit[]>("/api/v1/organization/units")
      .then((u) => {
        setUnits(u);
        if (u.length > 0) setUnitId(u[0].id);
      })
      .catch(console.error);
  }, []);

  const loadGuests = (eventId: string) => {
    setLoadingGuests(true);
    apiFetch<EventGuest[]>(`/api/v1/events/${eventId}/guests`)
      .then((data) => setGuests(data))
      .catch((err) => console.error(err))
      .finally(() => setLoadingGuests(false));
  };

  const handleSelectEvent = (ev: EventItem) => {
    setSelectedEvent(ev);
    loadGuests(ev.id);
  };

  const handleCreateEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!eventName || !unitId || !startsAt || !endsAt) {
      alert("Preencha todos os campos obrigatórios.");
      return;
    }
    setSubmittingEvent(true);
    try {
      const created = await apiFetch<EventItem>("/api/v1/events", {
        method: "POST",
        body: JSON.stringify({
          name: eventName.trim(),
          unit_id: unitId,
          location_name: locationName.trim() || undefined,
          starts_at: new Date(startsAt).toISOString(),
          ends_at: new Date(endsAt).toISOString(),
          early_entry_minutes: Number(earlyMinutes),
          late_entry_minutes: Number(lateMinutes),
          description: description.trim() || undefined,
        }),
      });
      setShowEventModal(false);
      setEventName("");
      setLocationName("");
      setStartsAt("");
      setEndsAt("");
      setDescription("");
      loadEvents();
      handleSelectEvent(created);
    } catch (err: any) {
      alert(err.message || "Falha ao criar evento.");
    } finally {
      setSubmittingEvent(false);
    }
  };

  const handleAddGuest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedEvent || !guestName || !guestIdent) {
      alert("Preencha nome e documento do convidado.");
      return;
    }
    setSubmittingGuest(true);
    try {
      const createdGuest = await apiFetch<EventGuest>(`/api/v1/events/${selectedEvent.id}/guests`, {
        method: "POST",
        body: JSON.stringify({
          full_name: guestName.trim(),
          identifier: guestIdent.trim().toUpperCase(),
          email: guestEmail.trim() || undefined,
          phone: guestPhone.trim() || undefined,
          organization_represented: guestOrg.trim() || undefined,
          pin: guestPin.trim() || undefined,
        }),
      });
      setShowGuestModal(false);
      setGuestName("");
      setGuestIdent("");
      setGuestEmail("");
      setGuestPhone("");
      setGuestOrg("");
      setGuestPin("");
      loadGuests(selectedEvent.id);
      loadEvents();

      if (autoOpenEnroll) {
        setEnrollGuest(createdGuest);
        setEnrollImages([]);
        startCamera();
      }
    } catch (err: any) {
      alert(err.message || "Falha ao cadastrar convidado.");
    } finally {
      setSubmittingGuest(false);
    }
  };

  const handleRemoveGuest = async (guest: EventGuest) => {
    if (!confirm(`Remover o convidado ${guest.full_name} deste evento?`)) return;
    try {
      await apiFetch(`/api/v1/events/guests/${guest.id}`, { method: "DELETE" });
      if (selectedEvent) {
        loadGuests(selectedEvent.id);
        loadEvents();
      }
    } catch (err: any) {
      alert(err.message || "Falha ao remover convidado.");
    }
  };

  // Camera capture logic for Guest Enrollment
  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setCameraActive(true);
      }
    } catch (err: any) {
      alert("Não foi possível acessar a câmera: " + (err.message || err));
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    setCameraActive(false);
  };

  const captureFrame = () => {
    if (!videoRef.current) return;
    const canvas = document.createElement("canvas");
    canvas.width = videoRef.current.videoWidth || 640;
    canvas.height = videoRef.current.videoHeight || 480;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.9);
    setEnrollImages((prev) => [...prev, dataUrl]);
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    Array.from(files).forEach((file) => {
      const reader = new FileReader();
      reader.onload = () => {
        if (typeof reader.result === "string") {
          setEnrollImages((prev) => [...prev, reader.result as string]);
        }
      };
      reader.readAsDataURL(file);
    });
  };

  const handleSaveEnrollment = async () => {
    if (!enrollGuest || enrollImages.length === 0) {
      alert("Capture ou selecione ao menos uma foto do convidado.");
      return;
    }
    setSubmittingEnroll(true);
    try {
      await apiFetch("/api/v1/events/guests/enroll", {
        method: "POST",
        body: JSON.stringify({
          guest_id: enrollGuest.id,
          images_base64: enrollImages,
        }),
      });
      stopCamera();
      setEnrollGuest(null);
      setEnrollImages([]);
      if (selectedEvent) loadGuests(selectedEvent.id);
      alert("Biometria do convidado cadastrada com sucesso!");
    } catch (err: any) {
      alert(err.message || "Falha ao cadastrar biometria do convidado.");
    } finally {
      setSubmittingEnroll(false);
    }
  };

  const getEventScheduleStatus = (event: EventItem) => {
    const now = new Date();
    const start = new Date(event.starts_at);
    const end = new Date(event.ends_at);
    const earlyLimit = new Date(start.getTime() - event.early_entry_minutes * 60000);
    const lateLimit = new Date(end.getTime() + event.late_entry_minutes * 60000);

    if (now < earlyLimit) {
      return {
        label: "Acesso Futuro",
        desc: `Entrada liberada às ${earlyLimit.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`,
        color: "bg-blue-500/10 text-blue-500 border-blue-500/20",
      };
    } else if (now > lateLimit) {
      return {
        label: "Encerrado",
        desc: `Limite de saída expirou às ${lateLimit.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`,
        color: "bg-zinc-500/10 text-zinc-400 border-zinc-500/20",
      };
    } else {
      return {
        label: "Acesso Liberado no Totem",
        desc: "Dentro da janela de horário permitida",
        color: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
      };
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="rounded-lg bg-primary/10 p-2 text-primary">
              <CalendarDays className="h-6 w-6" />
            </div>
            <div>
              <h2 className="text-base sm:text-lg font-bold text-foreground">
                Eventos & Convidados
              </h2>
              <p className="text-xs text-muted-foreground">
                Gestão de acesso para visitantes externos com validação estrita do horário do evento
              </p>
            </div>
          </div>
        </div>

        <button
          onClick={() => setShowEventModal(true)}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm hover:bg-primary/90 transition-colors self-start sm:self-auto"
        >
          <Plus className="h-4 w-4" />
          Novo Evento
        </button>
      </div>

      {/* Info notice */}
      <div className="rounded-xl border border-primary/20 bg-primary/5 p-4 text-xs text-muted-foreground flex items-start gap-3">
        <ShieldCheck className="h-5 w-5 text-primary shrink-0 mt-0.5" />
        <div className="space-y-1">
          <p className="font-semibold text-foreground">Regra Obrigatória de Biometria Facial para Convidados:</p>
          <p>
            Para ter o acesso liberado no totem, o convidado <strong>DEVE possuir cadastro biométrico facial</strong> e
            comparecer <strong>dentro do período permitido do evento</strong>.
            Convidados sem biometria cadastrada ou fora da janela do evento são <strong>estritamente rejeitados</strong> pelo totem.
          </p>
        </div>
      </div>

      {/* Events and Guests 2-Column Split */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Events List */}
        <div className="lg:col-span-5 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
              <CalendarDays className="h-4 w-4 text-muted-foreground" />
              Eventos Cadastrados ({events.length})
            </h3>
          </div>

          {loading ? (
            <div className="rounded-xl border bg-card p-6 text-center text-xs text-muted-foreground">
              Carregando eventos...
            </div>
          ) : events.length === 0 ? (
            <div className="rounded-xl border bg-card p-8 text-center text-xs text-muted-foreground">
              Nenhum evento registrado. Clique em <strong>Novo Evento</strong> para começar.
            </div>
          ) : (
            <div className="space-y-3">
              {events.map((ev) => {
                const schedule = getEventScheduleStatus(ev);
                const isSelected = selectedEvent?.id === ev.id;
                return (
                  <div
                    key={ev.id}
                    onClick={() => handleSelectEvent(ev)}
                    className={`cursor-pointer rounded-xl border p-4 transition-all ${
                      isSelected
                        ? "border-primary bg-primary/5 shadow-md"
                        : "border-border bg-card hover:border-primary/40 hover:bg-muted/30"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h4 className="font-semibold text-sm text-foreground">{ev.name}</h4>
                        {ev.location_name && (
                          <div className="flex items-center gap-1 text-xs text-muted-foreground mt-0.5">
                            <MapPin className="h-3 w-3" />
                            {ev.location_name}
                          </div>
                        )}
                      </div>
                      <span
                        className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold ${schedule.color}`}
                      >
                        {schedule.label}
                      </span>
                    </div>

                    <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                      <div className="flex items-center gap-1 font-mono">
                        <Clock className="h-3.5 w-3.5 text-primary" />
                        {new Date(ev.starts_at).toLocaleTimeString("pt-BR", {
                          hour: "2-digit",
                          minute: "2-digit",
                          day: "2-digit",
                          month: "2-digit",
                        })}{" "}
                        às{" "}
                        {new Date(ev.ends_at).toLocaleTimeString("pt-BR", {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </div>
                      <div className="flex items-center gap-1">
                        <Users className="h-3.5 w-3.5 text-muted-foreground" />
                        {ev.guest_count || 0} convidados
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Column: Selected Event Details & Guest List */}
        <div className="lg:col-span-7">
          {selectedEvent ? (
            <div className="rounded-xl border bg-card shadow-sm overflow-hidden">
              {/* Event Header Banner */}
              <div className="border-b bg-muted/40 p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-base text-foreground">{selectedEvent.name}</h3>
                    <span
                      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${
                        getEventScheduleStatus(selectedEvent).color
                      }`}
                    >
                      {getEventScheduleStatus(selectedEvent).label}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    {getEventScheduleStatus(selectedEvent).desc} • Tolerância: -{selectedEvent.early_entry_minutes}m / +
                    {selectedEvent.late_entry_minutes}m
                  </p>
                </div>

                <button
                  onClick={() => setShowGuestModal(true)}
                  className="flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors self-start sm:self-auto"
                >
                  <UserPlus className="h-4 w-4" />
                  Convidar Pessoa
                </button>
              </div>

              {/* Guests Table */}
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs whitespace-nowrap">
                  <thead className="border-b bg-muted/30 text-muted-foreground uppercase font-semibold">
                    <tr>
                      <th className="px-4 py-3">Convidado</th>
                      <th className="px-4 py-3">Documento</th>
                      <th className="px-4 py-3">Biometria</th>
                      <th className="px-4 py-3">Acesso</th>
                      <th className="px-4 py-3 text-right">Ações</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {loadingGuests ? (
                      <tr>
                        <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                          Carregando lista de convidados...
                        </td>
                      </tr>
                    ) : guests.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                          Nenhum convidado adicionado para este evento. Clique em <strong>Convidar Pessoa</strong>.
                        </td>
                      </tr>
                    ) : (
                      guests.map((g) => (
                        <tr key={g.id} className="hover:bg-muted/30 transition-colors">
                          <td className="px-4 py-3">
                            <div className="font-medium text-foreground">{g.full_name}</div>
                            {g.organization_represented && (
                              <div className="text-[11px] text-muted-foreground">
                                {g.organization_represented}
                              </div>
                            )}
                          </td>
                          <td className="px-4 py-3 font-mono font-semibold">
                            {g.identifier}
                          </td>
                          <td className="px-4 py-3">
                            {g.biometric_status === "enrolled" ? (
                              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-bold text-emerald-500 border border-emerald-500/20">
                                <CheckCircle2 className="h-3 w-3" />
                                Biometria Ativa
                              </span>
                            ) : (
                              <div className="flex flex-col sm:flex-row items-start sm:items-center gap-1.5">
                                <span className="inline-flex items-center gap-1 rounded-full bg-rose-500/10 px-2 py-0.5 text-[10px] font-bold text-rose-500 border border-rose-500/20">
                                  <AlertCircle className="h-3 w-3" />
                                  Sem Biometria (Bloqueado)
                                </span>
                                <button
                                  onClick={() => {
                                    setEnrollGuest(g);
                                    setEnrollImages([]);
                                    startCamera();
                                  }}
                                  className="inline-flex items-center gap-1 rounded-lg bg-primary px-2.5 py-1 text-[11px] font-semibold text-primary-foreground hover:bg-primary/90 shadow-sm"
                                >
                                  <Camera className="h-3 w-3" />
                                  Cadastrar Foto
                                </button>
                              </div>
                            )}
                          </td>
                          <td className="px-4 py-3">
                            {g.access_count > 0 ? (
                              <span className="inline-flex items-center gap-1 text-[11px] text-emerald-500 font-medium">
                                <CheckCircle2 className="h-3 w-3" />
                                Presente ({g.access_count}x)
                              </span>
                            ) : (
                              <span className="text-[11px] text-muted-foreground">
                                Não compareceu ainda
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-right">
                            <button
                              onClick={() => handleRemoveGuest(g)}
                              title="Remover convidado"
                              className="rounded-lg p-1.5 text-muted-foreground hover:bg-rose-500/10 hover:text-rose-500 transition-colors"
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="rounded-xl border bg-card p-12 text-center text-xs text-muted-foreground space-y-2">
              <CalendarDays className="h-10 w-10 text-muted-foreground/40 mx-auto" />
              <p className="font-semibold text-foreground text-sm">Nenhum evento selecionado</p>
              <p>Selecione um evento da lista ao lado para gerenciar convidados e capturas biométricas.</p>
            </div>
          )}
        </div>
      </div>

      {/* Modal: Criar Evento */}
      {showEventModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="w-full max-w-lg rounded-2xl border bg-card p-6 shadow-xl space-y-4 my-8">
            <div className="flex items-center justify-between border-b pb-3">
              <div className="flex items-center gap-2">
                <CalendarDays className="h-5 w-5 text-primary" />
                <h3 className="font-semibold text-foreground">Novo Evento</h3>
              </div>
              <button
                onClick={() => setShowEventModal(false)}
                className="rounded-lg p-1 text-muted-foreground hover:bg-muted"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleCreateEvent} className="space-y-4">
              <div>
                <label className="text-xs font-medium text-muted-foreground">Nome do Evento *</label>
                <input
                  type="text"
                  required
                  placeholder="Ex: Treinamento Corporativo Q4"
                  value={eventName}
                  onChange={(e) => setEventName(e.target.value)}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground focus:ring-2 focus:ring-primary"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-muted-foreground">Unidade / Localidade *</label>
                  <select
                    required
                    value={unitId}
                    onChange={(e) => setUnitId(e.target.value)}
                    className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground"
                  >
                    {units.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="text-xs font-medium text-muted-foreground">Sala / Espaço</label>
                  <input
                    type="text"
                    placeholder="Ex: Auditório Master, 2º Andar"
                    value={locationName}
                    onChange={(e) => setLocationName(e.target.value)}
                    className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground"
                  >
                  </input>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-muted-foreground">Início do Evento *</label>
                  <input
                    type="datetime-local"
                    required
                    value={startsAt}
                    onChange={(e) => setStartsAt(e.target.value)}
                    className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground"
                  />
                </div>

                <div>
                  <label className="text-xs font-medium text-muted-foreground">Término do Evento *</label>
                  <input
                    type="datetime-local"
                    required
                    value={endsAt}
                    onChange={(e) => setEndsAt(e.target.value)}
                    className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-muted-foreground">
                    Entrada Antecipada (minutos)
                  </label>
                  <input
                    type="number"
                    min={0}
                    max={240}
                    value={earlyMinutes}
                    onChange={(e) => setEarlyMinutes(Number(e.target.value))}
                    className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground"
                  />
                  <span className="text-[11px] text-muted-foreground">
                    Libera acesso no totem {earlyMinutes}m antes do início
                  </span>
                </div>

                <div>
                  <label className="text-xs font-medium text-muted-foreground">
                    Tolerância de Saída (minutos)
                  </label>
                  <input
                    type="number"
                    min={0}
                    max={360}
                    value={lateMinutes}
                    onChange={(e) => setLateMinutes(Number(e.target.value))}
                    className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground"
                  />
                  <span className="text-[11px] text-muted-foreground">
                    Permite saída até {lateMinutes}m após o término
                  </span>
                </div>
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground">Descrição / Observações</label>
                <textarea
                  rows={2}
                  placeholder="Informações adicionais para a portaria ou recepção..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowEventModal(false)}
                  className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={submittingEvent}
                  className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                  {submittingEvent ? "Criando..." : "Salvar Evento"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Adicionar Convidado */}
      {showGuestModal && selectedEvent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl border bg-card p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <div className="flex items-center gap-2">
                <UserPlus className="h-5 w-5 text-primary" />
                <h3 className="font-semibold text-foreground">Convidar para {selectedEvent.name}</h3>
              </div>
              <button
                onClick={() => setShowGuestModal(false)}
                className="rounded-lg p-1 text-muted-foreground hover:bg-muted"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleAddGuest} className="space-y-4">
              <div>
                <label className="text-xs font-medium text-muted-foreground">Nome Completo *</label>
                <input
                  type="text"
                  required
                  placeholder="Ex: Carlos Oliveira"
                  value={guestName}
                  onChange={(e) => setGuestName(e.target.value)}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground">
                  Documento de Identificação (CPF / RG / Crachá) *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Ex: 123.456.789-00 ou RG 1234567"
                  value={guestIdent}
                  onChange={(e) => setGuestIdent(e.target.value)}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground font-mono"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-muted-foreground">E-mail</label>
                  <input
                    type="email"
                    placeholder="carlos@empresa.com"
                    value={guestEmail}
                    onChange={(e) => setGuestEmail(e.target.value)}
                    className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground">Telefone / WhatsApp</label>
                  <input
                    type="tel"
                    placeholder="(11) 99999-9999"
                    value={guestPhone}
                    onChange={(e) => setGuestPhone(e.target.value)}
                    className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground">
                  Empresa / Organização Representada
                </label>
                <input
                  type="text"
                  placeholder="Ex: Tech Solutions Ltda"
                  value={guestOrg}
                  onChange={(e) => setGuestOrg(e.target.value)}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground">
                  PIN Alternativo (Opcional)
                </label>
                <input
                  type="password"
                  maxLength={8}
                  placeholder="Ex: 1234"
                  value={guestPin}
                  onChange={(e) => setGuestPin(e.target.value)}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground"
                />
              </div>

              <div className="rounded-lg bg-primary/10 border border-primary/20 p-2.5 text-xs text-primary flex items-start gap-2">
                <Camera className="h-4 w-4 shrink-0 mt-0.5" />
                <span>
                  <strong>Biometria Facial Obrigatória:</strong> Todo convidado deve ter biometria facial
                  cadastrada para que o totem libere seu acesso durante o evento.
                </span>
              </div>

              <label className="flex items-center gap-2 text-xs font-medium text-foreground cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={autoOpenEnroll}
                  onChange={(e) => setAutoOpenEnroll(e.target.checked)}
                  className="rounded text-primary focus:ring-primary h-4 w-4"
                />
                Capturar biometria facial imediatamente após salvar
              </label>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowGuestModal(false)}
                  className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={submittingGuest}
                  className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                  {submittingGuest ? "Salvando..." : "Confirmar Convidado"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Cadastro Biométrico do Convidado */}
      {enrollGuest && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg rounded-2xl border bg-card p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <div>
                <h3 className="font-semibold text-foreground flex items-center gap-2">
                  <Camera className="h-5 w-5 text-primary" />
                  Cadastro Facial: {enrollGuest.full_name}
                </h3>
                <p className="text-xs text-muted-foreground">
                  Doc: {enrollGuest.identifier} • Evento: {selectedEvent?.name}
                </p>
              </div>
              <button
                onClick={() => {
                  stopCamera();
                  setEnrollGuest(null);
                  setEnrollImages([]);
                }}
                className="rounded-lg p-1 text-muted-foreground hover:bg-muted"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Camera Viewport */}
            <div className="relative aspect-video w-full overflow-hidden rounded-xl bg-black flex items-center justify-center">
              <video
                ref={videoRef}
                playsInline
                muted
                autoPlay
                className="h-full w-full object-cover -scale-x-100"
              />
              <div className="absolute inset-0 pointer-events-none border-2 border-primary/40 rounded-xl m-4 border-dashed" />
              {!cameraActive && (
                <div className="absolute inset-0 flex items-center justify-center bg-zinc-900/80">
                  <button
                    onClick={startCamera}
                    className="rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground shadow"
                  >
                    Ativar Câmera
                  </button>
                </div>
              )}
            </div>

            {/* Action Bar */}
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={captureFrame}
                  disabled={!cameraActive}
                  className="flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                  <Camera className="h-4 w-4" />
                  Capturar Foto ({enrollImages.length})
                </button>

                <label className="flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium cursor-pointer hover:bg-muted">
                  <Upload className="h-3.5 w-3.5 text-muted-foreground" />
                  Upload Arquivo
                  <input
                    type="file"
                    accept="image/*"
                    multiple
                    onChange={handleFileUpload}
                    className="hidden"
                  />
                </label>
              </div>

              {enrollImages.length > 0 && (
                <button
                  onClick={() => setEnrollImages([])}
                  className="text-xs text-rose-500 hover:underline"
                >
                  Limpar ({enrollImages.length})
                </button>
              )}
            </div>

            {/* Thumbnails of captures */}
            {enrollImages.length > 0 && (
              <div className="flex gap-2 overflow-x-auto py-2">
                {enrollImages.map((img, idx) => (
                  <div key={idx} className="relative h-14 w-14 shrink-0 rounded-lg overflow-hidden border">
                    <img src={img} alt="Captura" className="h-full w-full object-cover" />
                    <span className="absolute bottom-0 right-0 bg-black/70 text-[9px] text-white px-1">
                      #{idx + 1}
                    </span>
                  </div>
                ))}
              </div>
            )}

            <div className="flex justify-end gap-2 border-t pt-3">
              <button
                type="button"
                onClick={() => {
                  stopCamera();
                  setEnrollGuest(null);
                  setEnrollImages([]);
                }}
                className="rounded-lg border px-4 py-2 text-xs font-medium hover:bg-muted"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleSaveEnrollment}
                disabled={submittingEnroll || enrollImages.length === 0}
                className="rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
              >
                {submittingEnroll ? "Processando e Criptografando..." : "Salvar Biometria"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
