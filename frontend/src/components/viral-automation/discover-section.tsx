"use client"

import React, { useState, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import {
  Search,
  Loader2,
  Play,
  Eye,
  Heart,
  MessageCircle,
  TrendingUp,
  Cat,
  Dog,
  Laugh,
  Music,
  Dumbbell,
  Utensils,
  Sparkles,
  Gamepad2,
  Baby,
  Car,
  Plane,
  Home,
  RefreshCw,
  Plus,
  ExternalLink,
  Clock,
  Flame,
  Share2,
  ImageOff
} from "lucide-react"
import { cn } from "@/lib/utils"
import { API_BASE_URL } from "@/lib/api"

// Categorías disponibles
const CATEGORIES = [
  { id: "cats", name: "Gatitos", icon: Cat, hashtags: ["cat", "cats", "catsoftiktok", "kitten", "gato", "gatito"], color: "bg-orange-500" },
  { id: "dogs", name: "Perritos", icon: Dog, hashtags: ["dog", "dogs", "dogsoftiktok", "puppy", "perro", "perrito"], color: "bg-amber-600" },
  { id: "funny", name: "Graciosos", icon: Laugh, hashtags: ["funny", "comedy", "humor", "memes", "lol", "gracioso"], color: "bg-yellow-500" },
  { id: "music", name: "Música", icon: Music, hashtags: ["music", "song", "dance", "musica", "baile"], color: "bg-pink-500" },
  { id: "fitness", name: "Fitness", icon: Dumbbell, hashtags: ["fitness", "gym", "workout", "exercise", "fitnessmotivation"], color: "bg-green-500" },
  { id: "food", name: "Comida", icon: Utensils, hashtags: ["food", "recipe", "cooking", "foodtiktok", "comida", "receta"], color: "bg-red-500" },
  { id: "beauty", name: "Belleza", icon: Sparkles, hashtags: ["beauty", "makeup", "skincare", "grwm", "belleza"], color: "bg-purple-500" },
  { id: "gaming", name: "Gaming", icon: Gamepad2, hashtags: ["gaming", "gamer", "videogames", "twitch", "esports"], color: "bg-blue-600" },
  { id: "babies", name: "Bebés", icon: Baby, hashtags: ["baby", "babies", "kids", "bebe", "niños", "cute"], color: "bg-pink-400" },
  { id: "cars", name: "Autos", icon: Car, hashtags: ["car", "cars", "auto", "autos", "supercar", "carlifestyle"], color: "bg-slate-500" },
  { id: "travel", name: "Viajes", icon: Plane, hashtags: ["travel", "vacation", "viaje", "tourist", "explore"], color: "bg-cyan-500" },
  { id: "lifestyle", name: "Lifestyle", icon: Home, hashtags: ["lifestyle", "aesthetic", "dayinmylife", "routine", "vlog"], color: "bg-indigo-500" },
]

interface DiscoveredVideo {
  id: string
  url: string
  title: string
  author: string
  author_url?: string
  thumbnail: string
  views: number
  likes: number
  comments: number
  shares?: number
  duration: number
  viral_score: number
  platform: string
  category: string
  upload_date?: string
}

interface DiscoverSectionProps {
  onAddToQueue: (url: string) => void
}

export function DiscoverSection({ onAddToQueue }: DiscoverSectionProps) {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [videos, setVideos] = useState<DiscoveredVideo[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const formatCount = (num: number): string => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
    return num.toString()
  }

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const searchCategory = useCallback(async (categoryId: string) => {
    const category = CATEGORIES.find(c => c.id === categoryId)
    if (!category) return

    setSelectedCategory(categoryId)
    setLoading(true)
    setError(null)

    try {
      // Endpoint de discover que usa yt-dlp para datos reales
      const response = await fetch(`${API_BASE_URL}/api/discover/${categoryId}?limit=12`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      })

      if (!response.ok) {
        throw new Error(`El servidor respondió ${response.status}`)
      }

      const data = await response.json()

      if (data.success && Array.isArray(data.videos) && data.videos.length > 0) {
        const mappedVideos: DiscoveredVideo[] = data.videos.map((v: any) => ({
          id: v.id,
          url: v.url,
          title: v.title || 'Sin título',
          author: v.author || 'Desconocido',
          author_url: v.author_url || '',
          thumbnail: v.thumbnail || '',
          views: v.views || 0,
          likes: v.likes || 0,
          comments: v.comments || 0,
          shares: v.shares || 0,
          duration: v.duration || 0,
          viral_score: v.viral_score || 0,
          platform: 'tiktok',
          category: v.category || categoryId
        }))
        setVideos(mappedVideos)
        setError(null)
      } else {
        // No se fabrican videos falsos: sus URLs no existen y romperían "Procesar".
        setVideos([])
        setError('No se encontraron videos para esta categoría.')
      }
    } catch (err) {
      console.error('Error fetching videos:', err)
      setVideos([])
      setError('No se pudieron cargar los videos (backend no disponible o error).')
    } finally {
      setLoading(false)
    }
  }, [])

  const getScoreColor = (score: number) => {
    if (score >= 70) return "text-green-400"
    if (score >= 50) return "text-yellow-400"
    return "text-orange-400"
  }

  const getScoreLabel = (score: number) => {
    if (score >= 70) return "Muy Viral"
    if (score >= 50) return "Viral"
    return "Trending"
  }

  return (
    <div className="flex flex-col h-full">
      {/* Categorías */}
      <div className="mb-4">
        <h3 className="text-sm font-medium text-gray-300 mb-3 flex items-center gap-2">
          <TrendingUp className="size-4" />
          Categorías Trending
        </h3>
        <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2">
          {CATEGORIES.map((cat) => {
            const Icon = cat.icon
            const isSelected = selectedCategory === cat.id
            return (
              <button
                key={cat.id}
                onClick={() => searchCategory(cat.id)}
                disabled={loading}
                className={cn(
                  "flex flex-col items-center gap-1 p-2 md:p-3 border transition-all",
                  isSelected
                    ? "bg-white/10 border-white text-white"
                    : "bg-black/30 border-gray-700 text-gray-400 hover:border-gray-500 hover:text-white"
                )}
              >
                <div className={cn("p-1.5 rounded-full", cat.color, "bg-opacity-20")}>
                  <Icon className={cn("size-4 md:size-5", isSelected ? "text-white" : "")} />
                </div>
                <span className="text-[10px] md:text-xs font-medium">{cat.name}</span>
              </button>
            )
          })}
        </div>
      </div>

      {/* Resultados */}
      <div className="flex-1 min-h-0">
        {!selectedCategory ? (
          <div className="h-full flex flex-col items-center justify-center text-gray-500">
            <Search className="size-12 mb-4 opacity-30" />
            <p className="text-sm">Selecciona una categoría para descubrir videos virales</p>
          </div>
        ) : loading ? (
          <div className="h-full flex flex-col items-center justify-center">
            <Loader2 className="size-8 text-purple-500 animate-spin mb-4" />
            <p className="text-sm text-gray-400">Buscando videos virales...</p>
          </div>
        ) : (
          <div className="h-full flex flex-col">
            {/* Header de resultados */}
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="border-gray-600 text-gray-300">
                  {videos.length} videos encontrados
                </Badge>
                {error && (
                  <span className="text-xs text-yellow-500">{error}</span>
                )}
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => searchCategory(selectedCategory)}
                className="h-7 px-2 text-gray-400 hover:text-white"
              >
                <RefreshCw className="size-3 mr-1" />
                Actualizar
              </Button>
            </div>

            {/* Lista de videos */}
            <ScrollArea className="flex-1">
              <div className="space-y-2 pr-2">
                {videos.map((video) => (
                  <div
                    key={video.id}
                    className="bg-black/30 border border-gray-700 p-3 hover:border-gray-500 transition-colors group"
                  >
                    <div className="flex gap-3">
                      {/* Thumbnail con imagen real */}
                      <div className="w-20 h-28 md:w-24 md:h-32 bg-gray-900 flex-shrink-0 flex items-center justify-center relative overflow-hidden border border-gray-700">
                        {video.thumbnail ? (
                          <img
                            src={video.thumbnail}
                            alt={video.title}
                            className="w-full h-full object-cover"
                            onError={(e) => {
                              const target = e.target as HTMLImageElement
                              target.style.display = 'none'
                              target.nextElementSibling?.classList.remove('hidden')
                            }}
                          />
                        ) : null}
                        <div className={cn(
                          "absolute inset-0 flex items-center justify-center bg-gray-900",
                          video.thumbnail ? "hidden" : ""
                        )}>
                          <ImageOff className="size-8 text-gray-700" />
                        </div>
                        {/* Duración */}
                        <div className="absolute bottom-1 right-1 bg-black/90 px-1.5 py-0.5 text-[10px] text-white font-medium">
                          {formatDuration(video.duration)}
                        </div>
                        {/* Play overlay on hover */}
                        <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                          <Play className="size-8 text-white fill-white" />
                        </div>
                      </div>

                      {/* Info */}
                      <div className="flex-1 min-w-0 flex flex-col justify-between">
                        <div>
                          <p className="text-sm text-white font-medium line-clamp-2 mb-1">
                            {video.title}
                          </p>
                          <p className="text-xs text-gray-500 mb-2">{video.author}</p>
                        </div>

                        {/* Stats */}
                        <div className="flex flex-wrap items-center gap-2 text-[10px] text-gray-400">
                          <span className="flex items-center gap-1">
                            <Eye className="size-3" />
                            {formatCount(video.views)}
                          </span>
                          <span className="flex items-center gap-1">
                            <Heart className="size-3 text-red-400" />
                            {formatCount(video.likes)}
                          </span>
                          <span className="flex items-center gap-1">
                            <MessageCircle className="size-3" />
                            {formatCount(video.comments)}
                          </span>
                          {video.shares && video.shares > 0 && (
                            <span className="flex items-center gap-1">
                              <Share2 className="size-3" />
                              {formatCount(video.shares)}
                            </span>
                          )}
                          <span className={cn("flex items-center gap-1 font-semibold", getScoreColor(video.viral_score))}>
                            <Flame className="size-3" />
                            {video.viral_score.toFixed(0)}
                          </span>
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex flex-col gap-1.5 opacity-70 md:opacity-0 group-hover:opacity-100 transition-opacity">
                        <Button
                          size="sm"
                          onClick={() => onAddToQueue(video.url)}
                          className="h-8 px-3 bg-white hover:bg-gray-200 text-black text-xs font-semibold"
                        >
                          <Plus className="size-3 mr-1" />
                          Procesar
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => window.open(video.url, '_blank')}
                          className="h-8 px-3 border-gray-600 text-gray-300 hover:text-white hover:border-white text-xs"
                        >
                          <ExternalLink className="size-3 mr-1" />
                          Abrir
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </div>
        )}
      </div>
    </div>
  )
}
