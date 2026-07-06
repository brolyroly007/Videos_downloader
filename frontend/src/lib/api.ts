/**
 * Cliente de la API del backend (FastAPI).
 * La URL base se toma de NEXT_PUBLIC_API_URL (con fallback a localhost:8000),
 * para no hardcodear el host y poder desplegar en cualquier entorno.
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000"

// ---- Tipos ----

export interface VideoInfo {
  success: boolean
  title: string
  duration: number
  platform: string
  width: number
  height: number
  thumbnail: string
  uploader: string
  view_count: number
  error?: string
}

export interface FileInfo {
  name: string
  path: string
  size: number
  modified: number
}

export interface ProcessingOptions {
  url: string
  description?: string
  reframe: boolean
  background_type: string
  background_color: string
  apply_mirror: boolean
  apply_speed: boolean
  speed_factor: number
  generate_subtitles: boolean
  subtitle_language: string
  burn_subtitles: boolean
  auto_upload: boolean
}

export interface ProcessResult {
  success: boolean
  task_id?: string
  status?: string
  message?: string
  data?: {
    final_video?: string
    transcription?: string
    [key: string]: unknown
  }
  error?: string
}

export interface TaskStatus {
  status: string // started | completed | failed | error | ...
  progress?: string // mensaje legible del backend
  data?: {
    final_video?: string
    transcription?: string
    [key: string]: unknown
  }
  error?: string
}

interface FileListResponse {
  files: FileInfo[]
}

// ---- Helper de fetch con manejo de errores ----

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || body.message || body.error || detail
    } catch {
      // respuesta sin cuerpo JSON
    }
    throw new Error(`API ${res.status}: ${detail}`)
  }
  return res.json() as Promise<T>
}

// ---- API ----

export const api = {
  getVideoInfo(url: string, signal?: AbortSignal): Promise<VideoInfo> {
    return request<VideoInfo>(`/api/video-info?url=${encodeURIComponent(url)}`, { signal })
  },

  getDownloadedFiles(): Promise<FileListResponse> {
    return request<FileListResponse>("/api/files/downloads")
  },

  getProcessedFiles(): Promise<FileListResponse> {
    return request<FileListResponse>("/api/files/processed")
  },

  processVideo(options: ProcessingOptions): Promise<ProcessResult> {
    return request<ProcessResult>("/api/complete-flow", {
      method: "POST",
      body: JSON.stringify(options),
    })
  },

  getTaskStatus(taskId: string, signal?: AbortSignal): Promise<TaskStatus> {
    return request<TaskStatus>(`/api/task/${encodeURIComponent(taskId)}`, { signal })
  },

  clearSession(): Promise<{ success: boolean; message?: string }> {
    return request("/api/clear-session", { method: "DELETE" })
  },
}
