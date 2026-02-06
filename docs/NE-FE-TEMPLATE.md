# NE-FE-TEMPLATE: SEO Front-End Proposal

## Overview

This document outlines how to reuse the **Spectrum UI** application (`../spectrum/ui`) as a templated front-end for the SEO Analyzer tool. The existing application provides a production-ready foundation with real-time job monitoring, persistent settings, and a modular component architecture.

---

## Current Spectrum UI Architecture

### Technology Stack
| Layer | Technology |
|-------|------------|
| Framework | Next.js 16 (App Router, Turbopack) |
| Language | TypeScript 5 |
| Styling | Tailwind CSS 3.4 + NE Design Tokens |
| State | Zustand 5 (client) + TanStack Query (server) |
| Database | Drizzle ORM (SQLite/PostgreSQL) |
| Real-Time | Server-Sent Events (SSE) |
| Charts | Recharts |

### Key Features to Reuse
1. **Real-time job monitoring** - JobLogPanel with SSE streaming
2. **Settings persistence** - Auto-save to localStorage
3. **Job tracking** - Zustand store with database sync
4. **NE branding** - Design tokens, header/footer, gold accent
5. **Layout shell** - Fixed header + sidebar + flexible content
6. **UI component library** - Cards, forms, badges, alerts, modals

---

## Proposed SEO Front-End Structure

### Left Navigation (Sidebar)

Replace Spectrum's QA-focused nav with SEO workflow:

| Icon | Label | Route | Purpose |
|------|-------|-------|---------|
| Home | Dashboard | `/` | Overview, recent crawls, quick stats |
| Globe | Crawl | `/crawl` | Start new site crawl |
| FileSearch | Reports | `/reports` | View generated reports |
| TrendingUp | Compare | `/compare` | Compare crawls over time |
| Settings | Settings | `/settings` | Crawler configuration |
| HelpCircle | Help | `/help` | Documentation |

### Page Content

#### 1. Dashboard (`/`)
```
┌─────────────────────────────────────────────────────────┐
│ Recent Crawls                                           │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐                    │
│ │ Site A  │ │ Site B  │ │ Site C  │                    │
│ │ 45 pgs  │ │ 120 pgs │ │ 23 pgs  │                    │
│ │ 3 issues│ │ 12 issue│ │ 0 issues│                    │
│ └─────────┘ └─────────┘ └─────────┘                    │
├─────────────────────────────────────────────────────────┤
│ Quick Actions                                           │
│ [Start New Crawl]  [View Latest Report]  [Compare]      │
├─────────────────────────────────────────────────────────┤
│ Active Jobs                    │ Crawl History          │
│ • www.example.com (45%)        │ • www.site1.com 2/2    │
│   └─ Crawling /products...     │ • www.site2.com 2/1    │
│                                │ • www.site3.com 1/31   │
└─────────────────────────────────────────────────────────┘
```

#### 2. Crawl Page (`/crawl`)
```
┌─────────────────────────────────────────────────────────┐
│ Start New Crawl                                         │
├─────────────────────────────────────────────────────────┤
│ Site URL:     [________________________] [https://▼]    │
│                                                         │
│ ┌─ Crawl Settings ────────────────────────────────────┐ │
│ │ Max Pages:        [50____]                          │ │
│ │ Max Depth:        [5_____]                          │ │
│ │ Max Concurrent:   [1_____]                          │ │
│ │ Rate Limit (ms):  [1000__]                          │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ ┌─ Analysis Options ──────────────────────────────────┐ │
│ │ [x] Run PageSpeed Insights    Sample: [100%___▼]    │ │
│ │ [x] Generate AI Recommendations                     │ │
│ │ [ ] Ignore robots.txt                               │ │
│ │ [ ] Headless mode                                   │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│                              [Start Crawl]              │
├─────────────────────────────────────────────────────────┤
│ ┌─ Live Progress ─────────────────────────────────────┐ │
│ │ ● www.example.com                          45%      │ │
│ │ ├─ [L1] Crawling: /about                           │ │
│ │ ├─ [L2] Crawling: /products/item-1                 │ │
│ │ ├─ [L2] Crawling: /products/item-2                 │ │
│ │ └─ Found 23 internal links                         │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

#### 3. Reports Page (`/reports`)
```
┌─────────────────────────────────────────────────────────┐
│ SEO Reports                                    [Filter▼]│
├─────────────────────────────────────────────────────────┤
│ ┌─ www.example.com ───────────────────────────────────┐ │
│ │ Crawled: Feb 2, 2026 at 9:30 PM                     │ │
│ │ Pages: 45  │  Issues: 12  │  Score: 78/100          │ │
│ │                                                     │ │
│ │ [View Report]  [Download HTML]  [Compare]  [Delete] │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ ┌─ www.another-site.com ──────────────────────────────┐ │
│ │ Crawled: Feb 1, 2026 at 3:15 PM                     │ │
│ │ Pages: 120  │  Issues: 3  │  Score: 94/100          │ │
│ │                                                     │ │
│ │ [View Report]  [Download HTML]  [Compare]  [Delete] │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

#### 4. Compare Page (`/compare`)
```
┌─────────────────────────────────────────────────────────┐
│ Compare Crawls                                          │
├─────────────────────────────────────────────────────────┤
│ Site: [www.example.com________________▼]                │
│                                                         │
│ Crawl A: [Feb 2, 2026 (latest)________▼]               │
│ Crawl B: [Jan 15, 2026________________▼]               │
│                                                         │
│                              [Compare]                  │
├─────────────────────────────────────────────────────────┤
│ ┌─ Comparison Results ────────────────────────────────┐ │
│ │              │ Jan 15      │ Feb 2       │ Change   │ │
│ │ ─────────────┼─────────────┼─────────────┼───────── │ │
│ │ Pages        │ 42          │ 45          │ +3       │ │
│ │ Issues       │ 18          │ 12          │ -6 ✓     │ │
│ │ Perf Score   │ 65          │ 78          │ +13 ✓    │ │
│ │ Missing Meta │ 8           │ 3           │ -5 ✓     │ │
│ │ Slow Pages   │ 5           │ 2           │ -3 ✓     │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ ┌─ Trend Chart ───────────────────────────────────────┐ │
│ │    ▲                                    ●───●       │ │
│ │    │                           ●───●               │ │
│ │    │              ●───●───●                        │ │
│ │    │    ●───●                                      │ │
│ │    └───────────────────────────────────────▶       │ │
│ │       Jan    Jan    Jan    Feb    Feb              │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

#### 5. Settings Page (`/settings`)
```
┌─────────────────────────────────────────────────────────┐
│ SEO Crawler Settings                                    │
├─────────────────────────────────────────────────────────┤
│ ┌─ Default Crawl Settings ────────────────────────────┐ │
│ │ Default Max Pages:     [50____]                     │ │
│ │ Default Max Depth:     [5_____]                     │ │
│ │ Default Concurrent:    [1_____]                     │ │
│ │ Default Rate Limit:    [1000__] ms                  │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ ┌─ PageSpeed Insights ────────────────────────────────┐ │
│ │ API Key:  [____________________________] [Test]     │ │
│ │ Default Sample Rate: [100%▼]                        │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ ┌─ AI Recommendations ────────────────────────────────┐ │
│ │ Provider:  [OpenAI▼]                                │ │
│ │ API Key:   [____________________________] [Test]    │ │
│ │ Model:     [gpt-4-turbo▼]                          │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ ┌─ Address Autofill ──────────────────────────────────┐ │
│ │ Street:    [123 Main St________________]            │ │
│ │ City:      [New York___________________]            │ │
│ │ State:     [NY_________________________]            │ │
│ │ Zip:       [10001______________________]            │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│                     [Save Settings]                     │
└─────────────────────────────────────────────────────────┘
```

---

## Backend Integration

### API Endpoints Required

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/crawl/start` | POST | Start new crawl job |
| `/api/crawl/jobs/{id}` | GET | Get job status |
| `/api/crawl/jobs/{id}/stream` | GET (SSE) | Real-time progress |
| `/api/crawl/jobs/{id}/cancel` | POST | Cancel running job |
| `/api/reports` | GET | List all reports |
| `/api/reports/{id}` | GET | Get report details |
| `/api/reports/{id}/html` | GET | Download HTML report |
| `/api/compare` | POST | Compare two crawls |
| `/api/settings` | GET/PUT | User settings |

### SSE Event Types

```typescript
// Progress event
{
  type: 'progress',
  data: {
    jobId: string,
    progress: number,        // 0-100
    currentUrl: string,
    pagesProcessed: number,
    totalPages: number,
    level: number,
    message: string
  }
}

// Complete event
{
  type: 'complete',
  data: {
    jobId: string,
    status: 'completed' | 'failed',
    reportPath: string,
    summary: {
      totalPages: number,
      totalIssues: number,
      criticalIssues: number,
      avgPerformance: number
    }
  }
}
```

### Python Backend (FastAPI)

The existing `async_crawl.py` would be wrapped in a FastAPI server:

```python
# api/server.py
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import StreamingResponse
from seo.async_site_crawler import AsyncSiteCrawler

app = FastAPI()

@app.post("/api/crawl/start")
async def start_crawl(config: CrawlConfig, background_tasks: BackgroundTasks):
    job_id = generate_job_id()
    background_tasks.add_task(run_crawl, job_id, config)
    return {"jobId": job_id, "status": "started"}

@app.get("/api/crawl/jobs/{job_id}/stream")
async def stream_progress(job_id: str):
    async def event_generator():
        async for event in get_job_events(job_id):
            yield f"event: {event.type}\ndata: {event.json()}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

---

## Implementation Approach

### Phase 1: Template Setup
1. Copy `spectrum/ui` to `seo/ui`
2. Remove Spectrum-specific pages (discover, analyze, generate, run, visualize)
3. Update `navigation.tsx` with SEO nav items
4. Update branding/titles

### Phase 2: Core Pages
1. Create `/crawl` page with form + JobLogPanel
2. Create `/reports` page with report listing
3. Update dashboard with SEO metrics

### Phase 3: Backend API
1. Create FastAPI wrapper for `async_crawl.py`
2. Implement SSE streaming for crawler progress
3. Add report management endpoints

### Phase 4: Advanced Features
1. Create `/compare` page with trend charts
2. Add historical data persistence
3. Implement settings sync

---

## File Changes Summary

### Files to Keep (Reuse As-Is)
```
src/app/components/layout/    # LayoutShell, Header, Sidebar, Footer
src/app/components/ui/        # All UI components
src/lib/api/client.ts         # API client pattern
src/stores/jobStore.ts        # Job tracking (adapt types)
src/stores/settingsStore.ts   # Settings persistence
src/config/site.ts            # Site configuration
```

### Files to Modify
```
src/config/navigation.tsx     # Replace nav items
src/app/page.tsx              # Dashboard → SEO dashboard
src/app/settings/page.tsx     # QA settings → SEO settings
src/stores/settingsStore.ts   # Add SEO-specific settings
```

### Files to Create
```
src/app/crawl/page.tsx        # New crawl page
src/app/reports/page.tsx      # Reports listing
src/app/reports/[id]/page.tsx # Single report view
src/app/compare/page.tsx      # Comparison view
src/lib/api/seo.ts            # SEO API endpoints
```

### Files to Remove
```
src/app/discover/             # Spectrum-specific
src/app/analyze/              # Spectrum-specific
src/app/generate/             # Spectrum-specific
src/app/run/                  # Spectrum-specific
src/app/visualize/            # Spectrum-specific
src/lib/api/discover.ts       # Spectrum-specific
src/lib/api/analyze.ts        # etc.
```

---

## Estimated Effort

| Phase | Tasks | Estimate |
|-------|-------|----------|
| Template Setup | Copy, cleanup, rebrand | 2-4 hours |
| Crawl Page | Form, SSE integration, progress | 4-6 hours |
| Reports Page | List, view, download | 3-4 hours |
| Backend API | FastAPI wrapper, SSE | 4-6 hours |
| Compare Page | Diff logic, charts | 4-6 hours |
| Polish | Testing, edge cases | 4-6 hours |
| **Total** | | **21-32 hours** |

---

## Benefits of This Approach

1. **Proven Architecture** - Reuses battle-tested patterns from Spectrum
2. **NE Branding** - Already integrated design tokens and styling
3. **Real-Time UX** - JobLogPanel provides excellent user feedback
4. **Maintainability** - Shared component library across NE tools
5. **Fast Development** - 70% of code is reusable
6. **Consistent Experience** - Same patterns as other NE applications

---

## Questions for Consideration

1. **Multi-tenancy** - Should SEO support multiple clients like Spectrum?
2. **Report Storage** - Keep in filesystem or move to database?
3. **Authentication** - Add user auth or keep it open?
4. **Deployment** - Docker, Vercel, or standalone?
5. **Scheduling** - Add recurring crawl schedules?

---

## Next Steps

1. Review and approve this proposal
2. Decide on questions above
3. Create `seo/ui` directory from template
4. Begin Phase 1 implementation

---

*Document: NE-FE-TEMPLATE.md*
*Created: February 2, 2026*
*Author: Claude Code*
