import React, { useEffect, useState } from "react";
import { Users, Clock, ShieldCheck, MonitorDot, ArrowUpRight, ArrowDownRight } from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from "recharts";
import { apiFetch } from "@/lib/api";
import { DashboardMetrics } from "@/types";

const mockAttendanceHistory = [
  { hour: "07:00", presencas: 12 },
  { hour: "08:00", presencas: 68 },
  { hour: "09:00", presencas: 95 },
  { hour: "10:00", presencas: 24 },
  { hour: "11:00", presencas: 18 },
  { hour: "12:00", presencas: 45 },
  { hour: "13:00", presencas: 72 },
  { hour: "14:00", presencas: 30 },
  { hour: "15:00", presencas: 15 },
  { hour: "16:00", presencas: 10 },
  { hour: "17:00", presencas: 80 },
  { hour: "18:00", presencas: 55 },
];

export function DashboardPage() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<DashboardMetrics>("/api/v1/dashboard/metrics")
      .then((data) => setMetrics(data))
      .catch((err) => console.error("Erro ao carregar métricas:", err))
      .finally(() => setLoading(false));
  }, []);

  const stats = [
    {
      label: "Total de Funcionários",
      value: metrics?.total_employees ?? 0,
      sub: `${metrics?.active_employees ?? 0} ativos / ${metrics?.inactive_employees ?? 0} inativos`,
      icon: Users,
    },
    {
      label: "Biometria Facial Cadastrada",
      value: metrics?.enrolled_biometrics ?? 0,
      sub: `${metrics?.total_employees ? Math.round(((metrics.enrolled_biometrics / metrics.total_employees) * 100)) : 0}% de cobertura voluntária`,
      icon: ShieldCheck,
    },
    {
      label: "Presenças Hoje",
      value: metrics?.today_attendances ?? 0,
      sub: `${metrics?.present_employees ?? 0} colaboradores presentes`,
      icon: Clock,
    },
    {
      label: "Terminais Conectados",
      value: metrics?.active_terminals ?? 0,
      sub: "Operando em modo kiosk local",
      icon: MonitorDot,
    },
  ];

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {stats.map((s) => {
          const Icon = s.icon;
          return (
            <div
              key={s.label}
              className="rounded-xl border bg-card p-5 shadow-sm transition-all hover:shadow"
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-muted-foreground">{s.label}</span>
                <div className="rounded-lg bg-primary/10 p-2 text-primary">
                  <Icon className="h-5 w-5" />
                </div>
              </div>
              <div className="mt-3">
                <div className="text-2xl font-bold tracking-tight text-foreground">
                  {loading ? "..." : s.value}
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{s.sub}</p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Gráficos */}
      <div className="grid gap-6 md:grid-cols-2">
        <div className="rounded-xl border bg-card p-5 shadow-sm">
          <div className="mb-4">
            <h3 className="font-semibold text-foreground">Fluxo de Presença por Horário (Hoje)</h3>
            <p className="text-xs text-muted-foreground">Registros biométricos 1:1 e PIN autorizados</p>
          </div>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={mockAttendanceHistory}>
                <defs>
                  <linearGradient id="colorPresenca" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
                <XAxis dataKey="hour" stroke="hsl(var(--muted-foreground))" fontSize={12} />
                <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} />
                <Tooltip />
                <Area type="monotone" dataKey="presencas" stroke="#3b82f6" fillOpacity={1} fill="url(#colorPresenca)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-xl border bg-card p-5 shadow-sm">
          <div className="mb-4">
            <h3 className="font-semibold text-foreground">Decisões de Controle de Acesso</h3>
            <p className="text-xs text-muted-foreground">Acessos físicos autorizados vs restrições de escala</p>
          </div>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={[
                  { name: "Autorizados", total: metrics?.authorized_accesses_today ?? 0, fill: "#10b981" },
                  { name: "Negados/Restritos", total: metrics?.denied_accesses_today ?? 0, fill: "#ef4444" },
                ]}
              >
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
                <XAxis dataKey="name" stroke="hsl(var(--muted-foreground))" fontSize={12} />
                <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} />
                <Tooltip />
                <Bar dataKey="total" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}
