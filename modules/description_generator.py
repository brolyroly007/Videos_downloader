"""
Description Generator Module
Genera descripciones automáticas para videos usando IA (OpenAI GPT o alternativas gratuitas)
"""

import os
import json
import logging
import asyncio
import aiohttp
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import re

logger = logging.getLogger(__name__)


@dataclass
class GeneratedDescription:
    """Descripción generada con metadata"""
    description: str
    hashtags: List[str]
    emojis: List[str]
    hook: str  # Primera línea llamativa
    call_to_action: str
    full_text: str  # Descripción completa lista para usar
    category: str
    language: str
    created_at: str

    def to_dict(self) -> dict:
        return asdict(self)


class DescriptionGenerator:
    """
    Generador de descripciones virales usando IA
    Soporta: OpenAI GPT, Ollama (local), o templates predefinidos
    """

    def __init__(self, api_key: Optional[str] = None, use_local: bool = True):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.use_local = use_local
        self.ollama_url = "http://localhost:11434/api/generate"

        # Templates por categoría para generación sin IA
        self.templates = {
            "cats": {
                "hooks": [
                    "Este gatito te va a robar el corazón 🐱",
                    "POV: Tienes un gato en casa 😂",
                    "Los gatos son así de dramáticos 🎭",
                    "Nadie: ... Mi gato a las 3am:",
                    "Tag a alguien que necesita ver esto 🐈",
                ],
                "hashtags": ["catsoftiktok", "cat", "gato", "gatosdetiktok", "catlover", "kitten", "meow", "catlife", "viral", "fyp"],
                "ctas": ["Sígueme para más 🐱", "Dale like si te gustó!", "Comenta el nombre de tu gato 👇", "Comparte con un cat lover!"],
            },
            "dogs": {
                "hooks": [
                    "El mejor amigo del hombre 🐕",
                    "POV: Tu perro cuando llegas a casa",
                    "Los perros son puro amor 💕",
                    "Dime que tienes perro sin decirme que tienes perro",
                    "Este perrito necesita tu like 🐶",
                ],
                "hashtags": ["dogsoftiktok", "dog", "perro", "puppy", "doglover", "perrosdetiktok", "doglife", "cute", "viral", "fyp"],
                "ctas": ["Sígueme para más perritos!", "Like si amas a los perros 🐕", "Comenta: 🐶 si te gustó", "Tag a un dog lover!"],
            },
            "funny": {
                "hooks": [
                    "No puedo dejar de reír 😂😂😂",
                    "Esto es demasiado real 💀",
                    "POV: Tu vida en un video",
                    "Cuando pensabas que lo habías visto todo...",
                    "El video más random que verás hoy 🤣",
                ],
                "hashtags": ["funny", "comedy", "humor", "memes", "lol", "viral", "fyp", "foryou", "gracioso", "risas"],
                "ctas": ["Sígueme para más risas!", "Comenta 😂 si te reíste", "Tag a alguien que necesita reír", "Like = más videos así"],
            },
            "music": {
                "hooks": [
                    "Esta canción está en repeat 🔥",
                    "POV: Encontraste tu nueva canción favorita",
                    "El talento que no sabías que necesitabas",
                    "Esto merece millones de views 🎵",
                    "La vibra de este video 🎶",
                ],
                "hashtags": ["music", "song", "viral", "fyp", "musica", "cover", "singer", "dance", "newmusic", "trending"],
                "ctas": ["Sígueme para más música!", "Guarda este video 🎵", "Comenta tu canción favorita", "Share si te gustó!"],
            },
            "fitness": {
                "hooks": [
                    "Transforma tu cuerpo con esto 💪",
                    "El ejercicio que nadie te enseñó",
                    "POV: Tu yo del futuro te lo agradecerá",
                    "Rutina de 5 minutos que funciona",
                    "No gym? No problem 🏋️",
                ],
                "hashtags": ["fitness", "gym", "workout", "exercise", "fitnessmotivation", "health", "training", "fit", "viral", "fyp"],
                "ctas": ["Guarda para después!", "Sígueme para más rutinas", "Comenta 💪 si lo intentarás", "Tag a tu gym partner"],
            },
            "food": {
                "hooks": [
                    "La receta que te va a cambiar la vida 🍳",
                    "POV: Cocinas esto y todos te aman",
                    "Fácil, rápido y delicioso 😋",
                    "La receta viral que TIENES que probar",
                    "Comida casera nivel restaurante 🍽️",
                ],
                "hashtags": ["food", "recipe", "cooking", "foodtiktok", "receta", "comida", "yummy", "foodie", "viral", "fyp"],
                "ctas": ["Guarda esta receta!", "Comenta qué quieres que cocine", "Like si te dio hambre 🍕", "Sígueme para más recetas"],
            },
            "beauty": {
                "hooks": [
                    "El truco de belleza que necesitabas ✨",
                    "POV: Descubres tu nuevo producto favorito",
                    "Glowup en 5 minutos",
                    "El secreto que nadie te contó 💄",
                    "Antes vs Después 😱",
                ],
                "hashtags": ["beauty", "makeup", "skincare", "grwm", "beautytips", "glow", "tutorial", "viral", "fyp", "belleza"],
                "ctas": ["Guarda para tu rutina!", "Comenta tu producto favorito", "Sígueme para más tips", "Like si lo probarás!"],
            },
            "gaming": {
                "hooks": [
                    "La jugada del año 🎮",
                    "POV: Cuando todo sale perfecto",
                    "Esto es skill puro 🔥",
                    "El clip más épico que verás hoy",
                    "GG EZ 😎",
                ],
                "hashtags": ["gaming", "gamer", "videogames", "gameplay", "esports", "twitch", "streamer", "viral", "fyp", "clutch"],
                "ctas": ["Sígueme para más clips!", "Comenta tu juego favorito", "Like si eres gamer", "Tag a tu squad 🎮"],
            },
            "babies": {
                "hooks": [
                    "La ternura en persona 👶",
                    "POV: Ser papá/mamá en un video",
                    "Este bebé te va a alegrar el día",
                    "La risa más contagiosa 😍",
                    "Momentos que valen oro ❤️",
                ],
                "hashtags": ["baby", "babies", "cute", "adorable", "babytiktok", "momlife", "dadlife", "familia", "viral", "fyp"],
                "ctas": ["Like si te derritió el corazón!", "Tag a una mamá/papá", "Comenta 👶 si te gustó", "Sígueme para más ternura"],
            },
            "cars": {
                "hooks": [
                    "El auto de tus sueños 🚗",
                    "POV: Cuando escuchas el motor",
                    "Esto es pura belleza automotriz",
                    "El sonido que necesitabas hoy 🔥",
                    "Cars que te dejan sin palabras",
                ],
                "hashtags": ["car", "cars", "supercar", "automotive", "carlifestyle", "luxury", "motorsport", "viral", "fyp", "autos"],
                "ctas": ["Sígueme para más autos!", "Comenta tu auto soñado 🚗", "Like si te gusta", "Tag a un car lover"],
            },
            "travel": {
                "hooks": [
                    "Añade esto a tu bucket list ✈️",
                    "POV: Tu próximo destino",
                    "El lugar más increíble del mundo",
                    "Viaja conmigo a...",
                    "Esto es el paraíso 🌴",
                ],
                "hashtags": ["travel", "vacation", "explore", "traveltiktok", "wanderlust", "adventure", "viaje", "viral", "fyp", "trip"],
                "ctas": ["Guarda para tu próximo viaje!", "Comenta a dónde quieres ir", "Sígueme para más destinos", "Tag a tu travel buddy"],
            },
            "lifestyle": {
                "hooks": [
                    "Un día en mi vida ✨",
                    "POV: Vivir tu mejor vida",
                    "La rutina que cambió todo",
                    "Aesthetic vibes only 🌿",
                    "Life hack que necesitas",
                ],
                "hashtags": ["lifestyle", "aesthetic", "dayinmylife", "routine", "vlog", "life", "motivation", "viral", "fyp", "mood"],
                "ctas": ["Sígueme para más contenido!", "Comenta tu rutina", "Like si te inspiró", "Guarda para después ✨"],
            },
            "default": {
                "hooks": [
                    "Esto se volvió viral por una razón 🔥",
                    "POV: El video que necesitabas ver hoy",
                    "No te lo puedes perder",
                    "El contenido que mereces",
                    "Viral incoming 📈",
                ],
                "hashtags": ["viral", "fyp", "foryou", "trending", "parati", "explore", "viralvideo", "content", "tiktok", "video"],
                "ctas": ["Sígueme para más!", "Like si te gustó", "Comenta qué opinas", "Comparte con tus amigos"],
            }
        }

        # Emojis populares por categoría
        self.category_emojis = {
            "cats": ["🐱", "🐈", "😺", "😸", "🐾", "💕"],
            "dogs": ["🐕", "🐶", "🦮", "🐾", "💕", "🥰"],
            "funny": ["😂", "🤣", "💀", "😭", "🤡", "😜"],
            "music": ["🎵", "🎶", "🎤", "🔥", "✨", "💫"],
            "fitness": ["💪", "🏋️", "🔥", "💯", "⚡", "🏃"],
            "food": ["🍳", "🍕", "🍔", "😋", "🤤", "👨‍🍳"],
            "beauty": ["✨", "💄", "💅", "🌟", "💕", "😍"],
            "gaming": ["🎮", "🔥", "💯", "😎", "⚡", "🏆"],
            "babies": ["👶", "🍼", "❤️", "😍", "🥰", "💕"],
            "cars": ["🚗", "🏎️", "🔥", "💨", "⚡", "🖤"],
            "travel": ["✈️", "🌴", "🏝️", "🌍", "📸", "🗺️"],
            "lifestyle": ["✨", "🌿", "☕", "💫", "🌸", "🤍"],
            "default": ["🔥", "✨", "💯", "📈", "⭐", "💕"],
        }

    async def generate_with_openai(self, video_info: Dict, category: str, language: str = "es") -> Optional[GeneratedDescription]:
        """
        Genera descripción usando OpenAI GPT API
        """
        if not self.api_key:
            logger.warning("No OpenAI API key, falling back to templates")
            return None

        prompt = f"""Genera una descripción viral para TikTok en {language}.

Información del video:
- Categoría: {category}
- Título original: {video_info.get('title', 'Video viral')}
- Vistas: {video_info.get('views', 0)}
- Likes: {video_info.get('likes', 0)}

Genera:
1. Hook (frase inicial llamativa de máximo 10 palabras)
2. Descripción corta (2-3 líneas máximo)
3. 10 hashtags relevantes (sin #)
4. Call to action (invitación a interactuar)
5. 3-5 emojis apropiados

Responde en formato JSON:
{{
    "hook": "...",
    "description": "...",
    "hashtags": ["...", "..."],
    "cta": "...",
    "emojis": ["...", "..."]
}}"""

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "gpt-3.5-turbo",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.8,
                        "max_tokens": 500
                    },
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data["choices"][0]["message"]["content"]

                        # Parsear JSON de la respuesta
                        json_match = re.search(r'\{[\s\S]*\}', content)
                        if json_match:
                            result = json.loads(json_match.group())

                            # Construir descripción completa
                            hashtags_str = " ".join([f"#{h}" for h in result["hashtags"][:10]])
                            emojis_str = "".join(result["emojis"][:3])

                            full_text = f"{result['hook']} {emojis_str}\n\n{result['description']}\n\n{result['cta']}\n\n{hashtags_str}"

                            return GeneratedDescription(
                                description=result["description"],
                                hashtags=result["hashtags"],
                                emojis=result["emojis"],
                                hook=result["hook"],
                                call_to_action=result["cta"],
                                full_text=full_text,
                                category=category,
                                language=language,
                                created_at=datetime.now().isoformat()
                            )
                    else:
                        logger.error(f"OpenAI API error: {response.status}")

        except Exception as e:
            logger.error(f"Error generating with OpenAI: {e}")

        return None

    async def generate_with_ollama(self, video_info: Dict, category: str, language: str = "es") -> Optional[GeneratedDescription]:
        """
        Genera descripción usando Ollama (modelo local)
        """
        prompt = f"""Genera una descripción viral para TikTok en español.
Categoría: {category}
Título: {video_info.get('title', 'Video viral')}

Responde SOLO con JSON válido:
{{"hook": "frase corta llamativa", "description": "descripción 2 líneas", "hashtags": ["viral", "fyp"], "cta": "call to action", "emojis": ["🔥", "✨"]}}"""

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.ollama_url,
                    json={
                        "model": "llama2",
                        "prompt": prompt,
                        "stream": False
                    },
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data.get("response", "")

                        json_match = re.search(r'\{[\s\S]*\}', content)
                        if json_match:
                            result = json.loads(json_match.group())

                            hashtags_str = " ".join([f"#{h}" for h in result.get("hashtags", [])[:10]])
                            emojis_str = "".join(result.get("emojis", [])[:3])

                            full_text = f"{result.get('hook', '')} {emojis_str}\n\n{result.get('description', '')}\n\n{result.get('cta', '')}\n\n{hashtags_str}"

                            return GeneratedDescription(
                                description=result.get("description", ""),
                                hashtags=result.get("hashtags", []),
                                emojis=result.get("emojis", []),
                                hook=result.get("hook", ""),
                                call_to_action=result.get("cta", ""),
                                full_text=full_text,
                                category=category,
                                language=language,
                                created_at=datetime.now().isoformat()
                            )
        except Exception as e:
            logger.debug(f"Ollama not available: {e}")

        return None

    def generate_from_template(self, video_info: Dict, category: str, language: str = "es") -> GeneratedDescription:
        """
        Genera descripción usando templates predefinidos (sin IA externa)
        """
        import random

        cat_templates = self.templates.get(category, self.templates["default"])
        cat_emojis = self.category_emojis.get(category, self.category_emojis["default"])

        hook = random.choice(cat_templates["hooks"])
        hashtags = cat_templates["hashtags"][:10]
        cta = random.choice(cat_templates["ctas"])
        emojis = random.sample(cat_emojis, min(3, len(cat_emojis)))

        # Crear descripción basada en el título del video si existe
        title = video_info.get('title', '')
        if title and len(title) > 10:
            description = title[:80] + "..." if len(title) > 80 else title
        else:
            description = hook

        # Construir texto completo
        hashtags_str = " ".join([f"#{h}" for h in hashtags])
        emojis_str = "".join(emojis)

        full_text = f"{hook} {emojis_str}\n\n{cta}\n\n{hashtags_str}"

        return GeneratedDescription(
            description=description,
            hashtags=hashtags,
            emojis=emojis,
            hook=hook,
            call_to_action=cta,
            full_text=full_text,
            category=category,
            language=language,
            created_at=datetime.now().isoformat()
        )

    async def generate(self, video_info: Dict, category: str = "default", language: str = "es", prefer_ai: bool = True) -> GeneratedDescription:
        """
        Genera descripción usando el mejor método disponible
        Orden: OpenAI -> Ollama -> Templates
        """
        if prefer_ai:
            # Intentar OpenAI primero
            if self.api_key:
                result = await self.generate_with_openai(video_info, category, language)
                if result:
                    logger.info("Generated description with OpenAI")
                    return result

            # Intentar Ollama
            if self.use_local:
                result = await self.generate_with_ollama(video_info, category, language)
                if result:
                    logger.info("Generated description with Ollama")
                    return result

        # Fallback a templates
        logger.info("Generated description from templates")
        return self.generate_from_template(video_info, category, language)

    def get_trending_hashtags(self, category: str, limit: int = 20) -> List[str]:
        """
        Obtiene hashtags trending para una categoría
        """
        cat_templates = self.templates.get(category, self.templates["default"])
        base_hashtags = cat_templates["hashtags"]

        # Agregar hashtags universales
        universal = ["viral", "fyp", "foryou", "parati", "trending", "viralvideo"]

        all_hashtags = list(set(base_hashtags + universal))
        return all_hashtags[:limit]


# Función helper para usar desde la API
async def generate_description(video_info: Dict, category: str = "default", language: str = "es") -> Dict:
    """Helper function para la API"""
    generator = DescriptionGenerator()
    result = await generator.generate(video_info, category, language)
    return result.to_dict()


# Test
if __name__ == "__main__":
    async def test():
        generator = DescriptionGenerator()

        video_info = {
            "title": "Gatito jugando con una caja",
            "views": 1500000,
            "likes": 200000,
        }

        print("Generando descripción para video de gatos...")
        result = await generator.generate(video_info, category="cats")

        print(f"\n📝 Descripción generada:")
        print(f"Hook: {result.hook}")
        print(f"Hashtags: {', '.join(result.hashtags)}")
        print(f"CTA: {result.call_to_action}")
        print(f"\n📋 Texto completo:\n{result.full_text}")

    asyncio.run(test())
