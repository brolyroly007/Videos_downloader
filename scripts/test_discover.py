"""
Test TikTokDiscovery module directly
"""
import asyncio
import sys
import logging

logging.basicConfig(level=logging.DEBUG)

# Import only the specific module, not the whole package
sys.path.insert(0, r'D:\proyectojudietha')

# Direct import to avoid moviepy issues
import subprocess
import json
from dataclasses import dataclass, asdict
from typing import List, Optional
from pathlib import Path

@dataclass
class TikTokVideo:
    id: str
    url: str
    title: str
    author: str
    author_url: str
    thumbnail: str
    duration: int
    views: int
    likes: int
    comments: int
    shares: int
    upload_date: str
    viral_score: float
    category: str

    def to_dict(self) -> dict:
        return asdict(self)


async def search_by_account(username: str, limit: int = 5) -> List[TikTokVideo]:
    """Search videos from a specific account"""
    videos = []
    username = username.lstrip('@')
    url = f"https://www.tiktok.com/@{username}"

    cmd = [
        'yt-dlp',
        '--dump-json',
        '--no-download',
        '--flat-playlist',
        '--playlist-items', f'1:{limit}',
        '--no-warnings',
        '--quiet',
        '--ignore-errors',
        url
    ]

    print(f"Searching @{username}...")
    print(f"Command: {' '.join(cmd)}")

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await asyncio.wait_for(
        process.communicate(),
        timeout=60
    )

    print(f"Return code: {process.returncode}")
    print(f"Stdout length: {len(stdout)}")

    if stderr:
        print(f"Stderr: {stderr.decode()[:200]}")

    if stdout:
        for line in stdout.decode().strip().split('\n'):
            if line:
                try:
                    data = json.loads(line)

                    views = data.get('view_count', 0) or 0
                    likes = data.get('like_count', 0) or 0
                    comments = data.get('comment_count', 0) or 0
                    shares = data.get('repost_count', 0) or 0
                    duration = data.get('duration', 0) or 0

                    # Get best thumbnail
                    thumbnail = data.get('thumbnail', '')
                    thumbnails = data.get('thumbnails', [])
                    if thumbnails:
                        for thumb in reversed(thumbnails):
                            if thumb.get('url'):
                                thumbnail = thumb['url']
                                break

                    video = TikTokVideo(
                        id=data.get('id', ''),
                        url=data.get('webpage_url', ''),
                        title=data.get('title', '')[:100],
                        author=f"@{data.get('uploader', 'unknown')}",
                        author_url=data.get('uploader_url', ''),
                        thumbnail=thumbnail,
                        duration=duration,
                        views=views,
                        likes=likes,
                        comments=comments,
                        shares=shares,
                        upload_date=data.get('upload_date', ''),
                        viral_score=50.0,
                        category="test"
                    )
                    videos.append(video)
                    print(f"  Found: {video.title[:40]}... | {video.views} views")
                except json.JSONDecodeError as e:
                    print(f"  JSON error: {e}")
                    continue

    print(f"Total videos found: {len(videos)}")
    return videos


async def main():
    print("=" * 50)
    print("Testing TikTok Discovery")
    print("=" * 50)

    videos = await search_by_account("tiktok", limit=3)

    print("\n" + "=" * 50)
    print("Results:")
    print("=" * 50)

    for v in videos:
        print(f"\nVideo: {v.title}")
        print(f"  Author: {v.author}")
        print(f"  Views: {v.views:,}")
        print(f"  Thumbnail: {v.thumbnail[:60]}...")


if __name__ == "__main__":
    asyncio.run(main())
