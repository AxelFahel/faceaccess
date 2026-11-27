export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = localStorage.getItem("access_token");
  const headers = new Headers(options.headers || {});
  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(endpoint, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    localStorage.removeItem("access_token");
    if (!window.location.pathname.startsWith("/login") && !window.location.pathname.startsWith("/kiosk")) {
      window.location.href = "/login";
    }
  }

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.error?.message || "Erro na requisição.");
  }

  return data as T;
}
