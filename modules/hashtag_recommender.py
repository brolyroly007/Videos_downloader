"""
Hashtag Recommender Module
Recomienda hashtags basados en tendencias y categorías
"""

import asyncio
import aiohttp
import json
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import sqlite3
import re

logger = logging.getLogger(__name__)


@dataclass
class HashtagData:
    """Datos de un hashtag"""
    tag: str
    views: int
    posts: int
    trending_score: float
    category: str
    last_updated: str

    def to_dict(self) -> dict:
        return asdict(self)


class HashtagDatabase:
    """Cache de hashtags trending"""

    def __init__(self, db_path: str = "hashtags.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hashtags (
                tag TEXT PRIMARY KEY,
                views INTEGER DEFAULT 0,
                posts INTEGER DEFAULT 0,
                trending_score REAL DEFAULT 0,
                category TEXT DEFAULT 'general',
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hashtag_combinations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                hashtags TEXT,
                performance_score REAL DEFAULT 0,
                times_used INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_hashtags_category ON hashtags(category)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_hashtags_score ON hashtags(trending_score DESC)')

        conn.commit()
        conn.close()

        # Poblar con datos iniciales
        self._populate_initial_data()

    def _populate_initial_data(self):
        """Pobla la base de datos con hashtags conocidos.

        IMPORTANTE: los conteos (views/posts/score) son ESTIMACIONES SEMILLA
        estáticas y aproximadas, NO datos en tiempo real de TikTok. Sirven como
        punto de partida para recomendar; no deben presentarse como métricas
        exactas. Las respuestas de la API lo indican con `data_source`.
        """
        initial_hashtags = {
            "general": [
                ("fyp", 500000000000, 100000000, 100),
                ("foryou", 400000000000, 90000000, 98),
                ("viral", 300000000000, 80000000, 95),
                ("trending", 200000000000, 70000000, 90),
                ("parati", 150000000000, 60000000, 88),
                ("foryoupage", 100000000000, 50000000, 85),
                ("viralvideo", 80000000000, 40000000, 80),
                ("explore", 60000000000, 30000000, 75),
                ("tiktok", 50000000000, 25000000, 70),
            ],
            "cats": [
                ("catsoftiktok", 50000000000, 10000000, 95),
                ("cat", 80000000000, 20000000, 90),
                ("cats", 60000000000, 15000000, 88),
                ("kitten", 40000000000, 8000000, 85),
                ("catlover", 30000000000, 6000000, 82),
                ("gato", 20000000000, 4000000, 80),
                ("gatito", 15000000000, 3000000, 78),
                ("meow", 25000000000, 5000000, 75),
                ("catlife", 10000000000, 2000000, 72),
                ("kitty", 20000000000, 4000000, 70),
            ],
            "dogs": [
                ("dogsoftiktok", 60000000000, 12000000, 95),
                ("dog", 90000000000, 22000000, 92),
                ("dogs", 70000000000, 18000000, 90),
                ("puppy", 50000000000, 10000000, 88),
                ("doglover", 40000000000, 8000000, 85),
                ("perro", 25000000000, 5000000, 82),
                ("perrito", 18000000000, 3500000, 80),
                ("doglife", 15000000000, 3000000, 75),
                ("puppylove", 12000000000, 2500000, 72),
            ],
            "funny": [
                ("funny", 200000000000, 50000000, 98),
                ("comedy", 150000000000, 40000000, 95),
                ("humor", 100000000000, 30000000, 92),
                ("lol", 80000000000, 20000000, 90),
                ("memes", 120000000000, 35000000, 88),
                ("gracioso", 30000000000, 8000000, 85),
                ("risas", 20000000000, 5000000, 82),
                ("divertido", 15000000000, 4000000, 80),
                ("jokes", 40000000000, 10000000, 78),
            ],
            "music": [
                ("music", 300000000000, 80000000, 98),
                ("song", 200000000000, 60000000, 95),
                ("dance", 250000000000, 70000000, 93),
                ("musica", 50000000000, 15000000, 90),
                ("singer", 80000000000, 20000000, 88),
                ("cover", 60000000000, 15000000, 85),
                ("musician", 40000000000, 10000000, 82),
                ("newmusic", 30000000000, 8000000, 80),
                ("spotify", 25000000000, 6000000, 78),
            ],
            "fitness": [
                ("fitness", 150000000000, 40000000, 95),
                ("gym", 120000000000, 35000000, 93),
                ("workout", 100000000000, 30000000, 90),
                ("fitnessmotivation", 80000000000, 20000000, 88),
                ("exercise", 60000000000, 15000000, 85),
                ("health", 50000000000, 12000000, 82),
                ("fit", 40000000000, 10000000, 80),
                ("training", 35000000000, 8000000, 78),
                ("bodybuilding", 30000000000, 7000000, 75),
            ],
            "food": [
                ("food", 200000000000, 60000000, 98),
                ("foodtiktok", 80000000000, 25000000, 95),
                ("recipe", 100000000000, 30000000, 93),
                ("cooking", 90000000000, 28000000, 90),
                ("comida", 40000000000, 10000000, 88),
                ("receta", 30000000000, 8000000, 85),
                ("yummy", 50000000000, 15000000, 82),
                ("foodie", 60000000000, 18000000, 80),
                ("delicious", 35000000000, 9000000, 78),
            ],
            "beauty": [
                ("beauty", 180000000000, 50000000, 98),
                ("makeup", 150000000000, 45000000, 95),
                ("skincare", 100000000000, 30000000, 93),
                ("grwm", 80000000000, 25000000, 90),
                ("beautytips", 50000000000, 15000000, 88),
                ("belleza", 30000000000, 8000000, 85),
                ("maquillaje", 25000000000, 6000000, 82),
                ("glow", 40000000000, 10000000, 80),
                ("tutorial", 60000000000, 18000000, 78),
            ],
            "gaming": [
                ("gaming", 200000000000, 55000000, 98),
                ("gamer", 150000000000, 45000000, 95),
                ("videogames", 100000000000, 30000000, 93),
                ("gameplay", 80000000000, 25000000, 90),
                ("twitch", 60000000000, 18000000, 88),
                ("streamer", 50000000000, 15000000, 85),
                ("esports", 40000000000, 12000000, 82),
                ("playstation", 35000000000, 10000000, 80),
                ("xbox", 30000000000, 9000000, 78),
                ("fortnite", 80000000000, 25000000, 85),
            ],
            "travel": [
                ("travel", 180000000000, 50000000, 98),
                ("vacation", 100000000000, 30000000, 95),
                ("traveltiktok", 60000000000, 18000000, 93),
                ("explore", 80000000000, 25000000, 90),
                ("viaje", 30000000000, 8000000, 88),
                ("adventure", 50000000000, 15000000, 85),
                ("wanderlust", 40000000000, 12000000, 82),
                ("tourist", 25000000000, 7000000, 80),
                ("trip", 35000000000, 10000000, 78),
            ],
            "lifestyle": [
                ("lifestyle", 150000000000, 45000000, 98),
                ("aesthetic", 100000000000, 30000000, 95),
                ("dayinmylife", 80000000000, 25000000, 93),
                ("routine", 60000000000, 18000000, 90),
                ("vlog", 70000000000, 20000000, 88),
                ("life", 90000000000, 28000000, 85),
                ("motivation", 50000000000, 15000000, 82),
                ("inspiration", 40000000000, 12000000, 80),
                ("mood", 35000000000, 10000000, 78),
            ],
        }

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for category, hashtags in initial_hashtags.items():
            for tag, views, posts, score in hashtags:
                cursor.execute('''
                    INSERT OR IGNORE INTO hashtags (tag, views, posts, trending_score, category)
                    VALUES (?, ?, ?, ?, ?)
                ''', (tag, views, posts, score, category))

        conn.commit()
        conn.close()

    def get_hashtags_by_category(self, category: str, limit: int = 20) -> List[HashtagData]:
        """Obtiene hashtags por categoría"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT tag, views, posts, trending_score, category, last_updated
            FROM hashtags
            WHERE category = ? OR category = 'general'
            ORDER BY trending_score DESC
            LIMIT ?
        ''', (category, limit))

        results = []
        for row in cursor.fetchall():
            results.append(HashtagData(
                tag=row[0],
                views=row[1],
                posts=row[2],
                trending_score=row[3],
                category=row[4],
                last_updated=row[5]
            ))

        conn.close()
        return results

    def get_top_hashtags(self, limit: int = 30) -> List[HashtagData]:
        """Obtiene los hashtags más trending"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT tag, views, posts, trending_score, category, last_updated
            FROM hashtags
            ORDER BY trending_score DESC
            LIMIT ?
        ''', (limit,))

        results = [HashtagData(*row) for row in cursor.fetchall()]
        conn.close()
        return results

    def update_hashtag(self, tag: str, views: int = None, posts: int = None, score: float = None):
        """Actualiza datos de un hashtag"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        updates = ["last_updated = ?"]
        params = [datetime.now().isoformat()]

        if views is not None:
            updates.append("views = ?")
            params.append(views)
        if posts is not None:
            updates.append("posts = ?")
            params.append(posts)
        if score is not None:
            updates.append("trending_score = ?")
            params.append(score)

        params.append(tag)
        cursor.execute(f'''
            UPDATE hashtags SET {", ".join(updates)} WHERE tag = ?
        ''', params)

        conn.commit()
        conn.close()

    def save_combination(self, category: str, hashtags: List[str], score: float = 0):
        """Guarda una combinación exitosa de hashtags"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO hashtag_combinations (category, hashtags, performance_score)
            VALUES (?, ?, ?)
        ''', (category, json.dumps(hashtags), score))

        conn.commit()
        conn.close()

    def get_best_combinations(self, category: str, limit: int = 5) -> List[Dict]:
        """Obtiene las mejores combinaciones para una categoría"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT hashtags, performance_score, times_used
            FROM hashtag_combinations
            WHERE category = ?
            ORDER BY performance_score DESC
            LIMIT ?
        ''', (category, limit))

        results = []
        for row in cursor.fetchall():
            results.append({
                "hashtags": json.loads(row[0]),
                "score": row[1],
                "times_used": row[2]
            })

        conn.close()
        return results


class HashtagRecommender:
    """Recomendador inteligente de hashtags"""

    def __init__(self, db_path: str = "hashtags.db"):
        self.db = HashtagDatabase(db_path)

    def recommend(self, category: str = "general", video_title: str = "",
                  max_hashtags: int = 15, include_general: bool = True) -> Dict:
        """
        Recomienda hashtags para un video

        Returns:
            Dict con hashtags organizados por tipo
        """
        result = {
            "primary": [],      # 3-5 hashtags principales de alta competencia
            "secondary": [],    # 5-7 hashtags de categoría específica
            "niche": [],        # 3-5 hashtags de nicho (menor competencia)
            "trending": [],     # 2-3 hashtags trending universales
            "all": [],          # Lista combinada
            "formatted": ""     # String listo para copiar
        }

        # Obtener hashtags de la categoría
        category_hashtags = self.db.get_hashtags_by_category(category, limit=30)

        # Separar por score
        high_score = [h for h in category_hashtags if h.trending_score >= 85]
        mid_score = [h for h in category_hashtags if 70 <= h.trending_score < 85]
        low_score = [h for h in category_hashtags if h.trending_score < 70]

        # Primary: hashtags de alto rendimiento
        result["primary"] = [h.tag for h in high_score[:5]]

        # Secondary: hashtags de categoría
        result["secondary"] = [h.tag for h in mid_score[:7]]

        # Niche: hashtags específicos
        result["niche"] = [h.tag for h in low_score[:5]]

        # Trending: siempre incluir estos
        if include_general:
            result["trending"] = ["fyp", "viral", "parati"]

        # Extraer hashtags del título si existe
        if video_title:
            title_tags = self._extract_from_title(video_title)
            # Agregar al principio si son relevantes
            for tag in title_tags[:2]:
                if tag not in result["primary"]:
                    result["primary"].insert(0, tag)

        # Combinar todo (sin duplicados)
        all_tags = []
        seen = set()
        for tag_list in [result["trending"], result["primary"], result["secondary"], result["niche"]]:
            for tag in tag_list:
                if tag.lower() not in seen:
                    all_tags.append(tag)
                    seen.add(tag.lower())
                if len(all_tags) >= max_hashtags:
                    break
            if len(all_tags) >= max_hashtags:
                break

        result["all"] = all_tags[:max_hashtags]
        result["formatted"] = " ".join([f"#{tag}" for tag in result["all"]])

        return result

    def _extract_from_title(self, title: str) -> List[str]:
        """Extrae posibles hashtags del título"""
        # Palabras clave comunes que podrían ser hashtags
        keywords = re.findall(r'\b[a-zA-Z]{3,15}\b', title.lower())

        # Filtrar palabras comunes que no son buenos hashtags
        stopwords = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had',
                     'her', 'was', 'one', 'our', 'out', 'has', 'have', 'been', 'being',
                     'que', 'con', 'por', 'para', 'una', 'este', 'esta', 'como', 'cuando'}

        return [k for k in keywords if k not in stopwords][:5]

    def get_trending_now(self, limit: int = 20) -> List[Dict]:
        """Obtiene los hashtags más trending actualmente"""
        hashtags = self.db.get_top_hashtags(limit)
        return [h.to_dict() for h in hashtags]

    def get_by_category(self, category: str, limit: int = 20) -> List[Dict]:
        """Obtiene hashtags por categoría"""
        hashtags = self.db.get_hashtags_by_category(category, limit)
        return [h.to_dict() for h in hashtags]

    def analyze_hashtags(self, hashtags: List[str]) -> Dict:
        """Analiza una lista de hashtags"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()

        total_views = 0
        total_posts = 0
        avg_score = 0
        found = 0

        for tag in hashtags:
            cursor.execute('''
                SELECT views, posts, trending_score FROM hashtags WHERE tag = ?
            ''', (tag.lower().replace('#', ''),))

            row = cursor.fetchone()
            if row:
                total_views += row[0]
                total_posts += row[1]
                avg_score += row[2]
                found += 1

        conn.close()

        avg_trending = avg_score / found if found > 0 else 0

        return {
            "total_hashtags": len(hashtags),
            "found_in_db": found,
            "estimated_reach": total_views,
            "competition_level": "high" if total_posts > 50000000 else "medium" if total_posts > 10000000 else "low",
            "avg_trending_score": avg_trending,
            "recommendation": "good" if avg_trending > 70 else "moderate" if avg_trending > 50 else "weak",
            "data_source": "static_seed_estimate",
            "note": "Las cifras (alcance/competencia) son estimaciones semilla estáticas, no datos en tiempo real de TikTok.",
        }

    def suggest_improvements(self, current_hashtags: List[str], category: str) -> Dict:
        """Sugiere mejoras a los hashtags actuales"""
        analysis = self.analyze_hashtags(current_hashtags)
        recommended = self.recommend(category, max_hashtags=15)

        # Encontrar hashtags faltantes importantes
        current_set = set(h.lower().replace('#', '') for h in current_hashtags)
        recommended_set = set(recommended["all"])

        missing_important = [h for h in recommended["primary"] if h.lower() not in current_set]
        missing_trending = [h for h in recommended["trending"] if h.lower() not in current_set]

        return {
            "current_analysis": analysis,
            "missing_important": missing_important,
            "missing_trending": missing_trending,
            "suggested_additions": missing_important[:3] + missing_trending,
            "suggested_removals": [],  # Hashtags de bajo rendimiento a remover
            "improved_set": recommended["all"]
        }


# Test
if __name__ == "__main__":
    recommender = HashtagRecommender("test_hashtags.db")

    print("\n🏷️ Recomendador de Hashtags")
    print("=" * 50)

    # Recomendar para video de gatos
    result = recommender.recommend(category="cats", video_title="Gatito jugando con caja")

    print(f"\n📌 Hashtags para video de GATOS:")
    print(f"Primary: {result['primary']}")
    print(f"Secondary: {result['secondary']}")
    print(f"Niche: {result['niche']}")
    print(f"Trending: {result['trending']}")
    print(f"\n✅ Texto para copiar:\n{result['formatted']}")

    # Trending ahora
    print(f"\n🔥 Top 10 Trending:")
    for h in recommender.get_trending_now(10):
        print(f"  #{h['tag']} - Score: {h['trending_score']}")

    # Analizar hashtags
    print(f"\n📊 Análisis de hashtags:")
    analysis = recommender.analyze_hashtags(["fyp", "viral", "cats", "catsoftiktok"])
    print(f"  Reach estimado: {analysis['estimated_reach']:,}")
    print(f"  Nivel competencia: {analysis['competition_level']}")
    print(f"  Recomendación: {analysis['recommendation']}")

    # Limpiar
    import os
    os.remove("test_hashtags.db")
