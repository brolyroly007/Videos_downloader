"use client"

import React, { useState, useEffect, useRef, useCallback, memo, useMemo } from "react"
import { Dithering } from "@paper-design/shaders-react"
import { InputSection } from "./input-section"
import { OutputSection } from "./output-section"
import { ProcessingHistory } from "./processing-history"
import { toast as sonnerToast } from "sonner"
import { DiscoverSection } from "./discover-section"
import { api, ProcessingOptions, VideoInfo, FileInfo } from "@/lib/api"
import { Zap, Compass, Video } from "lucide-react"
import { cn } from "@/lib/utils"
import { MAX_CONCURRENT_JOBS } from "@/lib/constants"

const MemoizedDithering = memo(Dithering)

export interface ProcessingJob {
  id: string
  status: "pending" | "processing" | "complete" | "error"
  url: string
  platform: string
  title: string
  progress: number
  message: string
  result?: {
    videoPath?: string
    transcription?: string
  }
  error?: string
  createdAt: Date
}

export function ViralAutomation() {
  const [url, setUrl] = useState("")
  const [description, setDescription] = useState("")
  const [videoInfo, setVideoInfo] = useState<VideoInfo | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)

  // Processing options
  const [reframe, setReframe] = useState(true)
  const [backgroundType, setBackgroundType] = useState<"blur" | "solid">("blur")
  const [backgroundColor, setBackgroundColor] = useState("#000000")
  const [applyMirror, setApplyMirror] = useState(true)
  const [applySpeed, setApplySpeed] = useState(true)
  const [generateSubtitles, setGenerateSubtitles] = useState(true)
  const [subtitleLanguage, setSubtitleLanguage] = useState("es")
  const [burnSubtitles, setBurnSubtitles] = useState(true)

  // Jobs history
  const [jobs, setJobs] = useState<ProcessingJob[]>([])
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)

  // Files
  const [downloadedFiles, setDownloadedFiles] = useState<FileInfo[]>([])
  const [processedFiles, setProcessedFiles] = useState<FileInfo[]>([])
  const [backendError, setBackendError] = useState<string | null>(null)

  // UI state
  const [leftWidth, setLeftWidth] = useState(50)
  const [isResizing, setIsResizing] = useState(false)
  const [isLargeScreen, setIsLargeScreen] = useState(false)
  const [activeTab, setActiveTab] = useState<"process" | "discover">("process")
  const containerRef = useRef<HTMLDivElement>(null)

  // Handle screen size detection after mount to avoid hydration mismatch
  useEffect(() => {
    const checkScreenSize = () => {
      setIsLargeScreen(window.innerWidth >= 1280)
    }
    checkScreenSize()
    window.addEventListener('resize', checkScreenSize)
    return () => window.removeEventListener('resize', checkScreenSize)
  }, [])

  const selectedJob = jobs.find((j) => j.id === selectedJobId) || jobs[0]
  const processingCount = jobs.filter((j) => j.status === "processing").length
  const isProcessing = processingCount > 0
  const canAddMore = processingCount < MAX_CONCURRENT_JOBS

  // Usa sonner (montado en layout) en vez de un toast casero con setTimeout:
  // maneja el apilado, el cierre y la accesibilidad sin sobrescribirse.
  const showToast = useCallback((message: string, type: "success" | "error" = "success") => {
    if (type === "error") sonnerToast.error(message)
    else sonnerToast.success(message)
  }, [])

  // Fetch files
  const fetchFiles = useCallback(async () => {
    try {
      const [downloads, processed] = await Promise.all([
        api.getDownloadedFiles(),
        api.getProcessedFiles(),
      ])
      setDownloadedFiles(downloads.files)
      setProcessedFiles(processed.files)
      setBackendError(null)
    } catch (error) {
      console.error("Error fetching files:", error)
      setBackendError("No se pudo conectar con el servidor. Reintentando…")
    }
  }, [])

  useEffect(() => {
    // Solo sondear con la pestaña visible: evita peticiones en segundo plano.
    const tick = () => {
      if (document.visibilityState === "visible") fetchFiles()
    }
    tick()
    const interval = setInterval(tick, 10000)
    document.addEventListener("visibilitychange", tick)
    return () => {
      clearInterval(interval)
      document.removeEventListener("visibilitychange", tick)
    }
  }, [fetchFiles])

  // Preview video. Se cancela la request anterior para que una respuesta lenta
  // de una URL previa no sobrescriba el videoInfo de la URL actual (race).
  const previewAbortRef = useRef<AbortController | null>(null)
  // Valida que sea una URL http(s) de una plataforma soportada.
  const isSupportedUrl = useCallback((value: string): boolean => {
    let parsed: URL
    try {
      parsed = new URL(value.trim())
    } catch {
      return false
    }
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return false
    const host = parsed.hostname.toLowerCase()
    return [
      "tiktok.com",
      "instagram.com",
      "youtube.com",
      "youtu.be",
      "facebook.com",
      "fb.watch",
    ].some((d) => host === d || host.endsWith("." + d))
  }, [])

  const handlePreview = useCallback(async () => {
    if (!url.trim()) return
    if (!isSupportedUrl(url)) {
      showToast("URL no válida. Usa TikTok, Instagram, YouTube o Facebook.", "error")
      return
    }

    previewAbortRef.current?.abort()
    const controller = new AbortController()
    previewAbortRef.current = controller

    setPreviewLoading(true)
    try {
      const info = await api.getVideoInfo(url, controller.signal)
      // Si otra preview la reemplazó mientras tanto, ignorar este resultado.
      if (controller.signal.aborted) return
      setVideoInfo(info)
      if (info.success) {
        showToast("Video info loaded", "success")
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return // cancelada por una preview más nueva
      showToast(error instanceof Error ? error.message : "Failed to get video info", "error")
    } finally {
      if (previewAbortRef.current === controller) {
        setPreviewLoading(false)
        previewAbortRef.current = null
      }
    }
  }, [url, showToast, isSupportedUrl])

  // Process video - supports adding multiple videos to queue
  const handleProcess = useCallback(async (autoUpload: boolean = false) => {
    if (!url.trim()) {
      showToast("Please enter a video URL", "error")
      return
    }

    if (!isSupportedUrl(url)) {
      showToast("URL no válida. Usa TikTok, Instagram, YouTube o Facebook.", "error")
      return
    }

    if (autoUpload && !description.trim()) {
      showToast("Please add a description for TikTok", "error")
      return
    }

    if (!canAddMore) {
      showToast(`Máximo ${MAX_CONCURRENT_JOBS} videos procesándose a la vez. Espera a que uno termine.`, "error")
      return
    }

    const jobId = `job_${Date.now()}`
    const currentUrl = url
    const currentDescription = description
    const currentVideoInfo = videoInfo

    const newJob: ProcessingJob = {
      id: jobId,
      status: "processing",
      url: currentUrl,
      platform: currentVideoInfo?.platform || "unknown",
      title: currentVideoInfo?.title || "Processing...",
      progress: 0,
      message: "Starting...",
      createdAt: new Date(),
    }

    setJobs((prev) => [newJob, ...prev])
    setSelectedJobId(jobId)

    // Clear inputs so user can add another video
    setUrl("")
    setDescription("")
    setVideoInfo(null)

    // Process asynchronously
    const processAsync = async () => {
      try {
        const options: ProcessingOptions = {
          url: currentUrl,
          description: currentDescription,
          reframe,
          background_type: backgroundType,
          background_color: backgroundColor,
          apply_mirror: applyMirror,
          apply_speed: applySpeed,
          speed_factor: 1.02,
          generate_subtitles: generateSubtitles,
          subtitle_language: subtitleLanguage,
          burn_subtitles: burnSubtitles,
          auto_upload: autoUpload,
        }

        setJobs((prev) =>
          prev.map((j) =>
            j.id === jobId ? { ...j, progress: 10, message: "Encolando..." } : j
          )
        )

        // El backend arranca el pipeline en segundo plano y devuelve un task_id;
        // el progreso real se consulta por polling en /api/task/{task_id}.
        const started = await api.processVideo(options)
        if (!started.success || !started.task_id) {
          throw new Error(started.error || started.message || "No se pudo iniciar el procesamiento")
        }
        const taskId = started.task_id

        // Mapea el mensaje del backend a un porcentaje aproximado.
        const progressFor = (msg = ""): number => {
          const m = msg.toLowerCase()
          if (m.includes("upload") || m.includes("subiendo")) return 90
          if (m.includes("subtitle") || m.includes("subtítulo")) return 75
          if (m.includes("process") || m.includes("procesando")) return 60
          if (m.includes("download") || m.includes("descarg")) return 35
          return 15
        }

        const controller = new AbortController()
        const POLL_MS = 2000
        const MAX_MS = 15 * 60 * 1000 // no sondear indefinidamente
        const deadline = Date.now() + MAX_MS

        // Bucle de polling
        // eslint-disable-next-line no-constant-condition
        while (true) {
          if (Date.now() > deadline) {
            controller.abort()
            throw new Error("Tiempo de espera agotado esperando el procesamiento")
          }
          await new Promise((r) => setTimeout(r, POLL_MS))
          const st = await api.getTaskStatus(taskId, controller.signal)

          if (st.status === "completed") {
            setJobs((prev) =>
              prev.map((j) =>
                j.id === jobId
                  ? {
                      ...j,
                      status: "complete",
                      progress: 100,
                      message: "Completado!",
                      result: {
                        videoPath: st.data?.final_video,
                        transcription: st.data?.transcription,
                      },
                    }
                  : j
              )
            )
            showToast(`Video procesado: ${currentVideoInfo?.title || "OK"}`, "success")
            fetchFiles()
            break
          }

          if (st.status === "failed" || st.status === "error") {
            throw new Error(st.error || "El procesamiento falló")
          }

          // En progreso: reflejar el mensaje del backend
          setJobs((prev) =>
            prev.map((j) =>
              j.id === jobId
                ? { ...j, progress: progressFor(st.progress), message: st.progress || "Procesando..." }
                : j
            )
          )
        }
      } catch (error) {
        const msg = error instanceof Error ? error.message : "Processing failed"
        setJobs((prev) =>
          prev.map((j) =>
            j.id === jobId
              ? {
                  ...j,
                  status: "error",
                  progress: 0,
                  message: "Failed",
                  error: msg,
                }
              : j
          )
        )
        showToast(msg, "error")
      }
    }

    // Start processing without blocking
    processAsync()

  }, [url, description, videoInfo, reframe, backgroundType, backgroundColor, applyMirror, applySpeed, generateSubtitles, subtitleLanguage, burnSubtitles, showToast, fetchFiles, canAddMore, isSupportedUrl])

  // Clear all
  const handleClearAll = useCallback(() => {
    setUrl("")
    setDescription("")
    setVideoInfo(null)
  }, [])

  // Delete job
  const handleDeleteJob = useCallback((id: string) => {
    setJobs((prev) => {
      const remaining = prev.filter((j) => j.id !== id)
      // Si se borró el job seleccionado, seleccionar el siguiente disponible
      // (o ninguno) para que el resaltado del historial y el panel coincidan.
      if (selectedJobId === id) {
        setSelectedJobId(remaining[0]?.id ?? null)
      }
      return remaining
    })
  }, [selectedJobId])

  // Add video from Discover section
  const handleAddFromDiscover = useCallback((videoUrl: string) => {
    setUrl(videoUrl)
    setActiveTab("process")
    showToast("URL agregada. Haz click en Preview para ver info.", "success")
  }, [showToast])

  // Resizer handlers
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    setIsResizing(true)
  }, [])

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!isResizing || !containerRef.current) return
      const container = containerRef.current
      const containerRect = container.getBoundingClientRect()
      const offsetX = e.clientX - containerRect.left
      const percentage = (offsetX / containerRect.width) * 100
      setLeftWidth(Math.max(30, Math.min(70, percentage)))
    },
    [isResizing]
  )

  const handleMouseUp = useCallback(() => {
    setIsResizing(false)
  }, [])

  useEffect(() => {
    if (isResizing) {
      document.addEventListener("mousemove", handleMouseMove)
      document.addEventListener("mouseup", handleMouseUp)
      document.body.style.cursor = "col-resize"
      document.body.style.userSelect = "none"

      return () => {
        document.removeEventListener("mousemove", handleMouseMove)
        document.removeEventListener("mouseup", handleMouseUp)
        document.body.style.cursor = ""
        document.body.style.userSelect = ""
      }
    }
  }, [isResizing, handleMouseMove, handleMouseUp])

  return (
    <div className="bg-background min-h-screen flex items-center justify-center select-none">

      {/* Aviso de backend caído */}
      {backendError && (
        <div
          role="status"
          aria-live="polite"
          className="fixed top-0 inset-x-0 z-50 bg-red-950/90 border-b border-red-600 text-red-200 text-sm text-center py-2 px-4"
        >
          {backendError}
        </div>
      )}

      {/* Shader Background */}
      <div className="fixed inset-0 z-0 select-none shader-background bg-black">
        <MemoizedDithering
          colorBack="#00000000"
          colorFront="#5B005B"
          speed={0.3}
          shape="wave"
          type="4x4"
          pxSize={3}
          scale={1.13}
          style={{
            backgroundColor: "#000000",
            height: "100vh",
            width: "100vw",
          }}
        />
      </div>

      {/* Main Content */}
      <div className="relative z-10 w-full h-full flex items-center justify-center p-2 md:p-4">
        <div className="w-full max-w-[98vw] lg:max-w-[96vw] 2xl:max-w-[94vw]">
          <div className="w-full mx-auto select-none">
            <div className="bg-black/70 border border-white/10 px-3 py-3 md:px-4 md:py-4 lg:px-6 lg:py-6 flex flex-col rounded-lg backdrop-blur-sm">
              {/* Header */}
              <div className="flex items-start justify-between gap-4 mb-4 md:mb-6 flex-shrink-0">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <Zap className="w-6 h-6 md:w-7 md:h-7 text-purple-500" />
                    <h1 className="text-lg md:text-2xl font-bold text-white select-none leading-none">
                      <span className="hidden md:inline">Viral Content Automation</span>
                      <span className="md:hidden">Viral Auto</span>
                    </h1>
                  </div>
                  <p className="text-[9px] md:text-[11px] text-gray-400 select-none tracking-wide">
                    TikTok • Instagram • YouTube • Facebook
                  </p>
                </div>
                <div className="flex items-center gap-2 text-xs text-gray-500">
                  <span className="hidden md:inline">
                    {downloadedFiles.length} downloaded • {processedFiles.length} processed
                  </span>
                </div>
              </div>

              {/* Tab Navigation */}
              <div className="flex gap-1 mb-4 border-b border-white/10 pb-3">
                <button
                  onClick={() => setActiveTab("process")}
                  className={cn(
                    "flex items-center gap-2 px-4 py-2 text-sm font-medium transition-all",
                    activeTab === "process"
                      ? "bg-white text-black"
                      : "text-gray-400 hover:text-white hover:bg-white/5"
                  )}
                >
                  <Video className="size-4" />
                  Procesar
                </button>
                <button
                  onClick={() => setActiveTab("discover")}
                  className={cn(
                    "flex items-center gap-2 px-4 py-2 text-sm font-medium transition-all",
                    activeTab === "discover"
                      ? "bg-white text-black"
                      : "text-gray-400 hover:text-white hover:bg-white/5"
                  )}
                >
                  <Compass className="size-4" />
                  Descubrir
                </button>
              </div>

              {/* Main Layout */}
              {activeTab === "process" ? (
                <div className="flex flex-col gap-4 xl:gap-0">
                  <div
                    ref={containerRef}
                    className="flex flex-col xl:flex-row gap-4 xl:gap-0 xl:min-h-[60vh] 2xl:min-h-[62vh]"
                  >
                    {/* Input Section */}
                    <div
                      className="flex flex-col xl:pr-4 xl:border-r xl:border-white/10 flex-shrink-0 xl:overflow-y-auto xl:max-h-[80vh]"
                      style={{ width: isLargeScreen ? `${leftWidth}%` : "100%" }}
                    >
                      <InputSection
                        url={url}
                        setUrl={setUrl}
                        description={description}
                        setDescription={setDescription}
                        videoInfo={videoInfo}
                        previewLoading={previewLoading}
                        reframe={reframe}
                        setReframe={setReframe}
                        backgroundType={backgroundType}
                        setBackgroundType={setBackgroundType}
                        backgroundColor={backgroundColor}
                        setBackgroundColor={setBackgroundColor}
                        applyMirror={applyMirror}
                        setApplyMirror={setApplyMirror}
                        applySpeed={applySpeed}
                        setApplySpeed={setApplySpeed}
                        generateSubtitles={generateSubtitles}
                        setGenerateSubtitles={setGenerateSubtitles}
                        subtitleLanguage={subtitleLanguage}
                        setSubtitleLanguage={setSubtitleLanguage}
                        burnSubtitles={burnSubtitles}
                        setBurnSubtitles={setBurnSubtitles}
                        isProcessing={isProcessing}
                        processingCount={processingCount}
                        onPreview={handlePreview}
                        onProcess={handleProcess}
                        onClearAll={handleClearAll}
                      />

                      {/* Desktop History */}
                      <div className="hidden xl:block mt-4 flex-shrink-0">
                        <ProcessingHistory
                          jobs={jobs}
                          selectedId={selectedJobId}
                          onSelect={setSelectedJobId}
                          onDelete={handleDeleteJob}
                        />
                      </div>
                    </div>

                    {/* Resizer */}
                    <div
                      className="hidden xl:flex items-center justify-center cursor-col-resize hover:bg-white/10 transition-colors relative group"
                      style={{ width: "8px", flexShrink: 0 }}
                      onMouseDown={handleMouseDown}
                      onDoubleClick={() => setLeftWidth(50)}
                    >
                      <div className="w-0.5 h-8 bg-white/20 group-hover:bg-white/40 transition-colors rounded-full" />
                    </div>

                    {/* Output Section */}
                    <div
                      className="flex flex-col xl:pl-4 min-h-[400px] xl:min-h-0 flex-shrink-0"
                      style={{ width: isLargeScreen ? `${100 - leftWidth}%` : "100%" }}
                    >
                      <OutputSection
                        selectedJob={selectedJob}
                        downloadedFiles={downloadedFiles}
                        processedFiles={processedFiles}
                      />
                    </div>
                  </div>

                  {/* Mobile History */}
                  <div className="xl:hidden flex-shrink-0">
                    <ProcessingHistory
                      jobs={jobs}
                      selectedId={selectedJobId}
                      onSelect={setSelectedJobId}
                      onDelete={handleDeleteJob}
                    />
                  </div>
                </div>
              ) : (
                <div className="min-h-[60vh] 2xl:min-h-[62vh]">
                  <DiscoverSection onAddToQueue={handleAddFromDiscover} />
                </div>
              )}

              {/* Footer */}
              <div className="mt-4 border-t border-white/10 pt-4 flex flex-col sm:flex-row items-center justify-center gap-2 sm:gap-4 text-xs text-white/40 flex-shrink-0">
                <span>Powered by Whisper AI + FFmpeg + Playwright</span>
                <span className="text-white/20 hidden sm:inline">•</span>
                <span>FastAPI Backend</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ViralAutomation
