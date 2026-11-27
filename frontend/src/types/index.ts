export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  all_units: boolean;
  roles: { code: string; name: string }[];
}

export interface Employee {
  id: string;
  full_name: string;
  registration_number: string;
  badge_code?: string;
  email: string;
  phone?: string;
  unit_id: string;
  department_id?: string;
  employment_status: "active" | "inactive" | "on_leave" | "terminated";
  biometric_status: "not_enrolled" | "enrolled" | "revoked" | "opted_out";
  access_profile: string;
  created_at: string;
}

export interface DashboardMetrics {
  total_employees: number;
  active_employees: number;
  inactive_employees: number;
  enrolled_biometrics: number;
  today_attendances: number;
  present_employees: number;
  authorized_accesses_today: number;
  denied_accesses_today: number;
  active_terminals: number;
  system_status: string;
  timestamp: string;
}

export interface AttendanceRecord {
  id: string;
  employee_id: string;
  employee_name?: string;
  record_type: "entry" | "exit" | "break_start" | "break_end";
  recorded_at: string;
  local_date: string;
  verification_method: string;
  result: string;
  source: string;
  status: string;
}
