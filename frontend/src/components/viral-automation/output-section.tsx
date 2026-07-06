"use client"

import React, { useState } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { ProcessingJob } from "./index"
import { FileInfo, API_BASE_URL } from "@/lib/api"
import {
  Play,
  Download,
  Copy,
  Check,
  Video,
  FileText,
  FolderOpen,
  Loader2,
  AlertCircle
} from "lucide-react"
import { cn } from "@/lib/utils"
import { formatFileSize, formatDate } from "@/lib/format"

interface OutputSectionProps {
  selectedJob?: ProcessingJob
  downloadedFiles: FileInfo[]
  processedFiles: FileInfo[]
}

function OutputSectionBase({
  selectedJob,
  downloadedFiles,
  processedFiles,
}: OutputSectionProps) {
  const [copied, setCopied] = useState(false)
  const [activeTab, setActiveTab] = useState("preview")

  // La transcripción pertenece al job seleccionado (no a un estado global que
  // el último job en completar sobrescribiría).
  const transcription = selectedJob?.result?.transcription ?? ""

  const copyTranscription = async () => {
    if (transcription) {
      await navigator.clipboard.writeText(transcription)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }


  return (
    <div className="flex flex-col h-full">
      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col">
        <TabsList className="grid grid-cols-3 bg-black/50 border border-gray-700 mb-3">
          <TabsTrigger
            value="preview"
            className="text-xs md:text-sm data-[state=active]:bg-white data-[state=active]:text-black"
          >
            <Video className="size-3 md:size-4 mr-1 md:mr-2" />
            Vista previa
          </TabsTrigger>
          <TabsTrigger
            value="transcription"
            className="text-xs md:text-sm data-[state=active]:bg-white data-[state=active]:text-black"
          >
            <FileText className="size-3 md:size-4 mr-1 md:mr-2" />
            Transcripción
          </TabsTrigger>
          <TabsTrigger
            value="files"
            className="text-xs md:text-sm data-[state=active]:bg-white data-[state=active]:text-black"
          >
            <FolderOpen className="size-3 md:size-4 mr-1 md:mr-2" />
            Archivos
          </TabsTrigger>
        </TabsList>

        <TabsContent value="preview" className="flex-1 mt-0">
          <div className="h-full bg-black/30 border border-gray-700 flex flex-col">
            {selectedJob ? (
              <div className="flex-1 flex flex-col">
                {/* Status Header */}
                <div className="p-3 border-b border-gray-700">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className={cn(
                        "w-2 h-2 rounded-full",
                        selectedJob.status === "complete" && "bg-green-500",
                        selectedJob.status === "processing" && "bg-yellow-500 animate-pulse",
                        selectedJob.status === "error" && "bg-red-500",
                        selectedJob.status === "pending" && "bg-gray-500"
                      )} />
                      <span className="text-sm font-medium text-white capitalize">
                        {selectedJob.status}
                      </span>
                    </div>
                    <span className="text-xs text-gray-500">
                      {selectedJob.platform}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400 mt-1 truncate">
                    {selectedJob.title}
                  </p>
                </div>

                {/* Progress or Video */}
                <div className="flex-1 flex items-center justify-center p-4">
                  {selectedJob.status === "processing" ? (
                    <div className="text-center space-y-4">
                      <Loader2 className="size-12 mx-auto text-purple-500 animate-spin" />
                      <div className="space-y-2">
                        <p className="text-sm text-white">{selectedJob.message}</p>
                        <div className="w-48 mx-auto h-2 bg-gray-700 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-purple-500 transition-all duration-500 progress-animate"
                            style={{ width: `${selectedJob.progress}%` }}
                          />
                        </div>
                        <p className="text-xs text-gray-500">{selectedJob.progress}%</p>
                      </div>
                    </div>
                  ) : selectedJob.status === "complete" && selectedJob.result?.videoPath ? (
                    <div className="w-full h-full flex flex-col items-center justify-center gap-4">
                      <div className="relative w-full max-w-[280px] aspect-[9/16] bg-black border border-gray-600 overflow-hidden">
                        <video
                          src={`${API_BASE_URL}/files/processed/${selectedJob.result.videoPath.split('/').pop()}`}
                          controls
                          className="w-full h-full object-contain"
                        />
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        className="bg-transparent border-gray-600 text-white hover:bg-gray-700"
                        onClick={() => {
                          const link = document.createElement('a')
                          link.href = `${API_BASE_URL}/files/processed/${selectedJob.result?.videoPath?.split('/').pop()}`
                          link.download = selectedJob.result?.videoPath?.split('/').pop() || 'video.mp4'
                          link.click()
                        }}
                      >
                        <Download className="size-4 mr-2" />
                        Descargar
                      </Button>
                    </div>
                  ) : selectedJob.status === "error" ? (
                    <div className="text-center space-y-2">
                      <AlertCircle className="size-12 mx-auto text-red-500" />
                      <p className="text-sm text-red-400">{selectedJob.error}</p>
                    </div>
                  ) : (
                    <div className="text-center text-gray-500">
                      <Play className="size-12 mx-auto mb-2 opacity-30" />
                      <p className="text-sm">Esperando para procesar...</p>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center text-gray-500">
                <div className="text-center">
                  <Video className="size-16 mx-auto mb-4 opacity-20" />
                  <p className="text-sm">Ingresa una URL de video para empezar</p>
                </div>
              </div>
            )}
          </div>
        </TabsContent>

        <TabsContent value="transcription" className="flex-1 mt-0">
          <div className="h-full bg-black/30 border border-gray-700 flex flex-col">
            <div className="flex items-center justify-between p-3 border-b border-gray-700">
              <span className="text-sm font-medium text-gray-300">Transcripción</span>
              <Button
                variant="ghost"
                size="sm"
                onClick={copyTranscription}
                disabled={!transcription}
                aria-label="Copiar transcripción"
                className="h-7 px-2 text-gray-400 hover:text-white"
              >
                {copied ? (
                  <Check className="size-4 text-green-500" />
                ) : (
                  <Copy className="size-4" />
                )}
              </Button>
            </div>
            <ScrollArea className="flex-1 p-3">
              {transcription ? (
                <p className="text-sm text-gray-300 whitespace-pre-wrap">{transcription}</p>
              ) : (
                <p className="text-sm text-gray-500 italic">
                  La transcripción aparecerá aquí después de procesar...
                </p>
              )}
            </ScrollArea>
          </div>
        </TabsContent>

        <TabsContent value="files" className="flex-1 mt-0">
          <div className="h-full bg-black/30 border border-gray-700 flex flex-col">
            <ScrollArea className="flex-1">
              {/* Downloaded Files */}
              <div className="p-3 border-b border-gray-700">
                <h4 className="text-xs font-medium text-gray-400 mb-2">
                  Downloaded ({downloadedFiles.length})
                </h4>
                {downloadedFiles.length > 0 ? (
                  <div className="space-y-1">
                    {downloadedFiles.slice(0, 5).map((file) => (
                      <div
                        key={file.path}
                        className="flex items-center justify-between p-2 bg-black/30 hover:bg-black/50 transition-colors"
                      >
                        <div className="flex-1 min-w-0">
                          <p className="text-xs text-white truncate">{file.name}</p>
                          <p className="text-[10px] text-gray-500">
                            {formatFileSize(file.size)}
                          </p>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          aria-label={`Abrir ${file.name}`}
                          className="h-6 w-6 p-0 text-gray-400 hover:text-white"
                          onClick={() => {
                            window.open(`${API_BASE_URL}/files/downloads/${file.name}`, '_blank', 'noopener,noreferrer')
                          }}
                        >
                          <Download className="size-3" />
                        </Button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-gray-500 italic">Sin archivos descargados</p>
                )}
              </div>

              {/* Processed Files */}
              <div className="p-3">
                <h4 className="text-xs font-medium text-gray-400 mb-2">
                  Processed ({processedFiles.length})
                </h4>
                {processedFiles.length > 0 ? (
                  <div className="space-y-1">
                    {processedFiles.slice(0, 5).map((file) => (
                      <div
                        key={file.path}
                        className="flex items-center justify-between p-2 bg-black/30 hover:bg-black/50 transition-colors"
                      >
                        <div className="flex-1 min-w-0">
                          <p className="text-xs text-white truncate">{file.name}</p>
                          <p className="text-[10px] text-gray-500">
                            {formatFileSize(file.size)}
                          </p>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          aria-label={`Abrir ${file.name}`}
                          className="h-6 w-6 p-0 text-gray-400 hover:text-white"
                          onClick={() => {
                            window.open(`${API_BASE_URL}/files/processed/${file.name}`, '_blank', 'noopener,noreferrer')
                          }}
                        >
                          <Download className="size-3" />
                        </Button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-gray-500 italic">Sin archivos procesados</p>
                )}
              </div>
            </ScrollArea>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}

export const OutputSection = React.memo(OutputSectionBase)
