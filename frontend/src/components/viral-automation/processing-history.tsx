"use client"

import React from "react"
import { ProcessingJob } from "./index"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Trash2, Check, Loader2, AlertCircle, Clock } from "lucide-react"
import { cn } from "@/lib/utils"

interface ProcessingHistoryProps {
  jobs: ProcessingJob[]
  selectedId: string | null
  onSelect: (id: string) => void
  onDelete: (id: string) => void
}

function ProcessingHistoryBase({
  jobs,
  selectedId,
  onSelect,
  onDelete,
}: ProcessingHistoryProps) {
  if (jobs.length === 0) {
    return (
      <div className="bg-black/30 border border-gray-700 p-4">
        <div className="flex items-center gap-2 mb-2">
          <Clock className="size-4 text-gray-500" />
          <span className="text-sm font-medium text-gray-400">Trabajos recientes</span>
        </div>
        <p className="text-xs text-gray-500 italic">Aún no hay historial de procesamiento</p>
      </div>
    )
  }

  const getStatusIcon = (status: ProcessingJob["status"]) => {
    switch (status) {
      case "complete":
        return <Check className="size-3 text-green-500" />
      case "processing":
        return <Loader2 className="size-3 text-yellow-500 animate-spin" />
      case "error":
        return <AlertCircle className="size-3 text-red-500" />
      default:
        return <Clock className="size-3 text-gray-500" />
    }
  }

  const formatTime = (date: Date) => {
    return new Date(date).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
  }

  return (
    <div className="bg-black/30 border border-gray-700">
      <div className="flex items-center justify-between p-3 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <Clock className="size-4 text-gray-500" />
          <span className="text-sm font-medium text-gray-400">Trabajos recientes</span>
        </div>
        <span className="text-xs text-gray-600">{jobs.length} elementos</span>
      </div>
      <ScrollArea className="max-h-[200px] xl:max-h-[180px]">
        <div className="p-2 space-y-1">
          {jobs.map((job) => (
            <div
              key={job.id}
              role="button"
              tabIndex={0}
              aria-pressed={selectedId === job.id}
              onClick={() => onSelect(job.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault()
                  onSelect(job.id)
                }
              }}
              className={cn(
                "flex items-center gap-2 p-2 cursor-pointer transition-colors group focus:outline-none focus:ring-1 focus:ring-purple-500",
                selectedId === job.id
                  ? "bg-white/10 border-l-2 border-purple-500"
                  : "hover:bg-white/5 border-l-2 border-transparent"
              )}
            >
              <div className="flex-shrink-0">
                {getStatusIcon(job.status)}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs text-white truncate">{job.title}</p>
                <div className="flex items-center gap-2 text-[10px] text-gray-500">
                  <span>{job.platform}</span>
                  <span>•</span>
                  <span>{formatTime(job.createdAt)}</span>
                </div>
              </div>
              {job.status === "processing" && (
                <span className="text-[10px] text-yellow-500 flex-shrink-0">
                  {job.progress}%
                </span>
              )}
              <Button
                variant="ghost"
                size="sm"
                aria-label="Eliminar trabajo"
                className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-500 flex-shrink-0"
                onClick={(e) => {
                  e.stopPropagation()
                  onDelete(job.id)
                }}
              >
                <Trash2 className="size-3" />
              </Button>
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}

export const ProcessingHistory = React.memo(ProcessingHistoryBase)
