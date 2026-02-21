import asyncio
import json

async def test():
    cmd = [
        "yt-dlp",
        "--dump-json",
        "--no-download",
        "--flat-playlist",
        "--playlist-items", "1:2",
        "--no-warnings",
        "--quiet",
        "--ignore-errors",
        "https://www.tiktok.com/@tiktok"
    ]

    print("Running command:", " ".join(cmd))

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
        lines = stdout.decode().strip().split('\n')
        print(f"Lines found: {len(lines)}")
        for line in lines:
            if line:
                try:
                    data = json.loads(line)
                    print(f"Video: {data.get('id')} - {data.get('title', '')[:40]}...")
                    print(f"  Thumbnail: {data.get('thumbnails', [{}])[0].get('url', 'N/A')[:60]}...")
                except Exception as e:
                    print(f"Parse error: {e}")

asyncio.run(test())
