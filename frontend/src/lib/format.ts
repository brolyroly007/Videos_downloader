/** Utilidades de formato compartidas por la UI. */

/** Tamaño de archivo legible (B/KB/MB) a partir de bytes. */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/** Fecha/hora local desde un timestamp UNIX en segundos. */
export function formatDate(timestamp: number): string {
  return new Date(timestamp * 1000).toLocaleString()
}

/** Conteo abreviado (1.2K, 3.4M). */
export function formatCount(num: number): string {
  if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`
  if (num >= 1_000) return `${(num / 1_000).toFixed(1)}K`
  return num.toString()
}

/** Duración m:ss a partir de segundos. */
export function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, "0")}`
}
