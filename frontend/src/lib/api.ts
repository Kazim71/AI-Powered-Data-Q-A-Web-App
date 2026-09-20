import type {
  AskResponse,
  SessionSchema,
  UploadResponse,
  ApiErrorBody,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000/api";

/** A backend error, carrying the same {error, detail} shape the API returns
 * so the UI can show the real message rather than a generic "something
 * went wrong." */
export class ApiError extends Error {
  status: number;
  detail: string | null;

  constructor(status: number, body: ApiErrorBody | null, fallback: string) {
    super(body?.error ?? fallback);
    this.status = status;
    this.detail = body?.detail ?? null;
  }
}

async function parseErrorBody(response: Response): Promise<ApiErrorBody | null> {
  try {
    return (await response.json()) as ApiErrorBody;
  } catch {
    return null;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    // fetch throws a bare TypeError ("Failed to fetch") for a refused
    // connection, DNS failure, or a CORS rejection — none of which have
    // anything to do with the backend's own error responses. Normalising
    // this to an ApiError with status 0 means every caller can tell "never
    // got a response" apart from "got an error response" the same way
    // uploadFiles' XHR path already does.
    throw new ApiError(
      0,
      null,
      `Could not reach the server at ${API_BASE}. Check that it's running, ` +
        `and that NEXT_PUBLIC_API_URL is correct.`
    );
  }
  if (!response.ok) {
    const body = await parseErrorBody(response);
    throw new ApiError(response.status, body, response.statusText);
  }
  return (await response.json()) as T;
}

export function createSession(): Promise<{ session_id: string; created_at: string }> {
  return request("/sessions", { method: "POST" });
}

export function deleteSession(sessionId: string): Promise<void> {
  return fetch(`${API_BASE}/sessions/${sessionId}`, { method: "DELETE" }).then(() => undefined);
}

export function getSchema(sessionId: string): Promise<SessionSchema> {
  return request(`/sessions/${sessionId}/schema`);
}

/**
 * Uploads via XHR rather than fetch specifically for `upload.onprogress` —
 * fetch's request-body streaming isn't reliably observable across browsers
 * yet, and per-file progress is one of the required states in the design
 * brief (docs/09), not a nice-to-have.
 */
export function uploadFiles(
  sessionId: string,
  files: File[],
  onProgress?: (loadedBytes: number, totalBytes: number) => void
): Promise<UploadResponse> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    for (const file of files) form.append("files", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/sessions/${sessionId}/files`);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress?.(event.loaded, event.total);
    };

    xhr.onload = () => {
      let parsed: unknown = null;
      try {
        parsed = JSON.parse(xhr.responseText);
      } catch {
        // fall through to the status check below with parsed === null
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(parsed as UploadResponse);
      } else {
        const body = parsed as ApiErrorBody | null;
        reject(new ApiError(xhr.status, body, xhr.statusText || "Upload failed"));
      }
    };
    xhr.onerror = () =>
      reject(
        new ApiError(
          0,
          null,
          `Could not reach the server at ${API_BASE}. Check that it's running.`
        )
      );
    xhr.send(form);
  });
}

/**
 * `onSlow` fires once if the response hasn't arrived within `slowAfterMs` —
 * used to show a "waking up the server" notice rather than a silent wait
 * during a Render cold start, without cancelling the underlying request.
 */
export async function ask(
  sessionId: string,
  question: string,
  options?: { onSlow?: () => void; slowAfterMs?: number }
): Promise<AskResponse> {
  const timer = setTimeout(() => options?.onSlow?.(), options?.slowAfterMs ?? 4000);
  try {
    return await request<AskResponse>(`/sessions/${sessionId}/ask`, {
      method: "POST",
      body: JSON.stringify({ question }),
    });
  } finally {
    clearTimeout(timer);
  }
}
