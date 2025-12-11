# Leaf Frontend

Frontend for Leaf, a conversational book recommendation system that provides personalized suggestions through natural language and Goodreads reading history analysis.

## Tech Stack

- **Next.js 16** (App Router)
- **React 19**
- **TypeScript**
- **Tailwind CSS 4**
- **shadcn/ui** components
- **Biome** (linter + formatter)

## Getting Started

Install dependencies:
```bash
npm install
```

Start development server:
```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## Development Commands

```bash
npm run dev      # Start dev server
npm run build    # Production build
npm run start    # Start production server
npm run lint     # Run Biome linter
npm run format   # Format code with Biome
```

## Environment Variables

Create `.env.local`:
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Project Structure

```
src/app/
├── page.tsx              # Input page (query + CSV upload)
├── questions/            # Follow-up questions page
├── recommendations/      # Recommendations display
├── components/           # Reusable UI components
└── globals.css
```

## Backend Integration

Backend API runs at `http://localhost:8000` by default. See `../backend/README.md` for setup instructions.
