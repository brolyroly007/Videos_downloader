"use client"

import React from "react"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Trash2, Search, Play, Upload, Loader2 } from "lucide-react"
import { VideoInfo } from "@/lib/api"
import { cn } from "@/lib/utils"
import { MAX_CONCURRENT_JOBS } from "@/lib/constants"

const btnClassName = "w-full h-10 md:h-12 text-sm md:text-base font-semibold bg-white text-black hover:bg-gray-200"

interface InputSectionProps {
  url: string
  setUrl: (url: string) => void
  description: string
  setDescription: (description: string) => void
  videoInfo: VideoInfo | null
  previewLoading: boolean
  reframe: boolean
  setReframe: (value: boolean) => void
  backgroundType: "blur" | "solid"
  setBackgroundType: (type: "blur" | "solid") => void
  backgroundColor: string
  setBackgroundColor: (color: string) => void
  applyMirror: boolean
  setApplyMirror: (value: boolean) => void
  applySpeed: boolean
  setApplySpeed: (value: boolean) => void
  generateSubtitles: boolean
  setGenerateSubtitles: (value: boolean) => void
  subtitleLanguage: string
  setSubtitleLanguage: (lang: string) => void
  burnSubtitles: boolean
  setBurnSubtitles: (value: boolean) => void
  isProcessing: boolean
  processingCount?: number
  onPreview: () => void
  onProcess: (autoUpload: boolean) => void
  onClearAll: () => void
}

function InputSectionBase({
  url,
  setUrl,
  description,
  setDescription,
  videoInfo,
  previewLoading,
  reframe,
  setReframe,
  backgroundType,
  setBackgroundType,
  backgroundColor,
  setBackgroundColor,
  applyMirror,
  setApplyMirror,
  applySpeed,
  setApplySpeed,
  generateSubtitles,
  setGenerateSubtitles,
  subtitleLanguage,
  setSubtitleLanguage,
  burnSubtitles,
  setBurnSubtitles,
  isProcessing,
  processingCount = 0,
  onPreview,
  onProcess,
  onClearAll,
}: InputSectionProps) {
  const hasContent = url.trim() || description.trim()
  const canAddMore = processingCount < MAX_CONCURRENT_JOBS

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="space-y-3 md:space-y-4 min-h-0 flex flex-col">
        {/* URL Input */}
        <div className="space-y-2">
          <div className="flex items-center justify-between mb-2 select-none">
            <label className="text-sm md:text-base font-medium text-gray-300">Video URL</label>
            <Button
              onClick={onClearAll}
              disabled={!hasContent}
              variant="outline"
              size="sm"
              className="h-7 md:h-8 px-2 md:px-3 text-xs bg-transparent border border-gray-600 text-white hover:bg-gray-700 disabled:opacity-50"
            >
              <Trash2 className="size-3 md:size-4 md:mr-1" />
              <span className="hidden md:inline">Clear</span>
            </Button>
          </div>
          <div className="flex gap-2">
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://tiktok.com/... or instagram.com/reels/..."
              className="flex-1 p-2 md:p-3 bg-black/50 border border-gray-600 text-white text-sm focus:outline-none focus:border-white transition-colors"
            />
            <Button
              onClick={onPreview}
              disabled={!url.trim() || previewLoading}
              variant="outline"
              className="h-auto px-3 md:px-4 bg-transparent border border-gray-600 text-white hover:bg-gray-700"
            >
              {previewLoading ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Search className="size-4" />
              )}
            </Button>
          </div>
        </div>

        {/* Video Preview */}
        {videoInfo && videoInfo.success && (
          <div className="bg-black/30 border border-gray-700 p-3 space-y-2">
            <div className="flex gap-3">
              {videoInfo.thumbnail && (
                <img
                  src={videoInfo.thumbnail}
                  alt="Video thumbnail"
                  className="w-20 h-20 md:w-24 md:h-24 object-cover border border-gray-600"
                />
              )}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-white truncate">{videoInfo.title}</p>
                <p className="text-xs text-gray-400 mt-1">
                  {videoInfo.platform} • {Math.floor(videoInfo.duration / 60)}:{String(Math.floor(videoInfo.duration % 60)).padStart(2, "0")}
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  {videoInfo.width}x{videoInfo.height} • {videoInfo.uploader}
                </p>
                {videoInfo.view_count && (
                  <p className="text-xs text-purple-400 mt-1">
                    {videoInfo.view_count.toLocaleString()} views
                  </p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Description for TikTok */}
        <div className="space-y-2">
          <label className="text-sm md:text-base font-medium text-gray-300 select-none">
            TikTok Description
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Add hashtags and description for TikTok upload..."
            className="w-full min-h-[60px] md:min-h-[80px] p-2 md:p-3 bg-black/50 border border-gray-600 text-white text-sm resize-none focus:outline-none focus:border-white transition-colors"
          />
        </div>

        {/* Processing Options */}
        <div className="space-y-3 pt-2 border-t border-white/10">
          <h3 className="text-sm font-medium text-gray-300 select-none">Processing Options</h3>

          {/* Reframe to 9:16 */}
          <div className="flex items-center justify-between">
            <div className="flex flex-col">
              <span className="text-sm text-white">Reframe to 9:16</span>
              <span className="text-xs text-gray-500">Convert to vertical format</span>
            </div>
            <Switch checked={reframe} onCheckedChange={setReframe} />
          </div>

          {/* Background Type */}
          {reframe && (
            <div className="flex items-center justify-between pl-4 border-l-2 border-purple-500/30">
              <span className="text-sm text-gray-300">Background</span>
              <div className="flex items-center gap-2">
                <Select value={backgroundType} onValueChange={(v) => setBackgroundType(v as "blur" | "solid")}>
                  <SelectTrigger className="w-24 h-8 bg-black/50 border-gray-600 text-white text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-black border-gray-600">
                    <SelectItem value="blur" className="text-white text-xs">Blur</SelectItem>
                    <SelectItem value="solid" className="text-white text-xs">Solid</SelectItem>
                  </SelectContent>
                </Select>
                {backgroundType === "solid" && (
                  <input
                    type="color"
                    value={backgroundColor}
                    onChange={(e) => setBackgroundColor(e.target.value)}
                    className="w-8 h-8 cursor-pointer bg-transparent border border-gray-600"
                  />
                )}
              </div>
            </div>
          )}

          {/* Mirror Effect */}
          <div className="flex items-center justify-between">
            <div className="flex flex-col">
              <span className="text-sm text-white">Mirror Effect</span>
              <span className="text-xs text-gray-500">Horizontal flip</span>
            </div>
            <Switch checked={applyMirror} onCheckedChange={setApplyMirror} />
          </div>

          {/* Speed Adjustment */}
          <div className="flex items-center justify-between">
            <div className="flex flex-col">
              <span className="text-sm text-white">Speed Boost</span>
              <span className="text-xs text-gray-500">1.02x faster</span>
            </div>
            <Switch checked={applySpeed} onCheckedChange={setApplySpeed} />
          </div>

          {/* Subtitles */}
          <div className="flex items-center justify-between">
            <div className="flex flex-col">
              <span className="text-sm text-white">Generate Subtitles</span>
              <span className="text-xs text-gray-500">Whisper AI transcription</span>
            </div>
            <Switch checked={generateSubtitles} onCheckedChange={setGenerateSubtitles} />
          </div>

          {generateSubtitles && (
            <>
              <div className="flex items-center justify-between pl-4 border-l-2 border-purple-500/30">
                <span className="text-sm text-gray-300">Language</span>
                <Select value={subtitleLanguage} onValueChange={setSubtitleLanguage}>
                  <SelectTrigger className="w-28 h-8 bg-black/50 border-gray-600 text-white text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-black border-gray-600">
                    <SelectItem value="es" className="text-white text-xs">Spanish</SelectItem>
                    <SelectItem value="en" className="text-white text-xs">English</SelectItem>
                    <SelectItem value="pt" className="text-white text-xs">Portuguese</SelectItem>
                    <SelectItem value="auto" className="text-white text-xs">Auto Detect</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-center justify-between pl-4 border-l-2 border-purple-500/30">
                <span className="text-sm text-gray-300">Burn into video</span>
                <Switch checked={burnSubtitles} onCheckedChange={setBurnSubtitles} />
              </div>
            </>
          )}
        </div>

        {/* Action Buttons */}
        <div className="pt-3 space-y-2">
          {/* Queue Status */}
          {processingCount > 0 && (
            <div className="flex items-center justify-between text-xs text-gray-400 mb-2">
              <span className="flex items-center gap-1">
                <Loader2 className="size-3 animate-spin" />
                {processingCount} video{processingCount > 1 ? 's' : ''} processing
              </span>
              <span className={cn(
                canAddMore ? "text-green-500" : "text-yellow-500"
              )}>
                {canAddMore ? `Add up to ${MAX_CONCURRENT_JOBS - processingCount} more` : "Queue full"}
              </span>
            </div>
          )}
          <Button
            onClick={() => onProcess(false)}
            disabled={!url.trim() || !canAddMore}
            className={cn(btnClassName, "flex items-center justify-center gap-2")}
          >
            {!canAddMore ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Queue Full...
              </>
            ) : (
              <>
                <Play className="size-4" />
                {processingCount > 0 ? "Add to Queue" : "Process Video"}
              </>
            )}
          </Button>
          <Button
            onClick={() => onProcess(true)}
            disabled={!url.trim() || !description.trim() || !canAddMore}
            variant="outline"
            className="w-full h-10 md:h-12 text-sm md:text-base font-semibold bg-purple-600 text-white hover:bg-purple-700 border-purple-500 flex items-center justify-center gap-2"
          >
            <Upload className="size-4" />
            {processingCount > 0 ? "Add & Upload to TikTok" : "Process & Upload to TikTok"}
          </Button>
        </div>
      </div>
    </div>
  )
}

export const InputSection = React.memo(InputSectionBase)
