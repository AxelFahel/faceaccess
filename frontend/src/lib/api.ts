export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit & { timeoutMs?: number; authenticated?: boolean } = {}
): Promise<T> {
  const token = localStorage.getItem("access_token");
  const headers = new Headers(options.headers || {});
  headers.set("Content-Type", "application/json");
  if (token && options.authenticated !== false) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const { timeoutMs = 30_000, authenticated = true, signal, ...requestOptions } = options;
  const controller = new AbortController();
  let timedOut = false;
  const cancel = () => controller.abort();
  if (signal?.aborted) cancel();
  signal?.addEventListener("abort", cancel, { once: true });
  const timer = window.setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
  try {
  const response = await fetch(endpoint, {
    ...requestOptions,
    signal: controller.signal,
    headers,
  });

  if (response.status === 401 && authenticated) {
    localStorage.removeItem("access_token");
    if (!window.location.pathname.startsWith("/login") && !window.location.pathname.startsWith("/kiosk")) {
      window.location.href = "/login";
    }
  }

  const body = await response.text();
  let data;
  try { data = body ? JSON.parse(body) : null; }
  catch { throw new Error(`O servidor não retornou uma resposta válida (HTTP ${response.status}). Tente novamente.`); }
  if (!response.ok) {
    throw new Error(data?.error?.message || "Erro na requisição.");
  }

  return data as T;
  } catch (error) {
    if (timedOut) throw new Error("O servidor demorou demais para responder. A operação pode ainda estar em andamento; confira o cadastro antes de tentar novamente.");
    throw error;
  } finally {
    window.clearTimeout(timer);
    signal?.removeEventListener("abort", cancel);
  }
}
