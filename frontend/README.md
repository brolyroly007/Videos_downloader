# Videos Downloader - Frontend

Modern dashboard for the Videos Downloader automation platform, built with Next.js 16 and React 19.

## Tech Stack

- **Framework**: Next.js 16 (App Router)
- **UI**: React 19, Radix UI primitives, Tailwind CSS v4
- **Icons**: Lucide React
- **Notifications**: Sonner (toast)
- **Theme**: next-themes (dark mode support)

## Project Structure

```
src/
├── app/
│   ├── layout.tsx          # Root layout with theme provider
│   ├── page.tsx            # Main dashboard page
│   └── globals.css         # Global styles & Tailwind
├── components/
│   ├── dashboard/          # Dashboard feature components
│   │   ├── header.tsx      # App header with navigation
│   │   ├── stats-cards.tsx # Statistics overview cards
│   │   ├── file-list.tsx   # Downloaded/processed file list
│   │   └── video-processor.tsx  # Video processing controls
│   ├── viral-automation/   # Viral automation components
│   │   ├── index.tsx       # Main automation view
│   │   ├── input-section.tsx    # URL input & options
│   │   ├── output-section.tsx   # Processing results
│   │   ├── discover-section.tsx # Content discovery
│   │   └── processing-history.tsx # Job history
│   ├── ui/                 # Radix UI component library
│   └── theme-provider.tsx  # Dark/light theme toggle
└── lib/                    # Utilities
```

## Development

```bash
# Install dependencies
npm ci

# Start dev server (requires backend on port 8000)
npm run dev

# Build for production
npm run build

# Run linter
npm run lint
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend API base URL |

## Connection to Backend

The frontend communicates with the FastAPI backend via REST API. During development, the backend must be running on port 8000 (or configure `NEXT_PUBLIC_API_URL`).

For production, use the Docker Compose setup in the project root which handles networking automatically.
