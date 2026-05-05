# Rufus Twin — Frontend

Next.js application providing a premium, glassmorphic interface for AEO diagnostics.

## ✨ Features

- **Persona Badge**: Real-time display of the synthesized shopper persona (Budget Tier, Quality Sensitivity, etc.).
- **Stage Stepper**: 4-step visual progress tracker (Profile → Extract → Simulate → Report).
- **Typewriter Streaming**: Natural language recommendations stream word-by-word via SSE.
- **Interactive Market Widget**: Dynamic market size estimation displayed alongside the AEO report.
- **AEO Report Card**: Visual breakdown of Contextual Completeness and Review Sentiment Alignment.

## 🛠 Setup

1. **Install Dependencies**:
   ```bash
   npm install
   ```

2. **Environment**:
   The app defaults to `http://localhost:8000` for the backend. Ensure the backend is running.

3. **Run Development Server**:
   ```bash
   npm run dev
   ```

## 🏗 Key Components

- `components/RufusSimulator.tsx`: Handles the streaming typewriter effect and markdown table rendering with horizontal scroll protection.
- `components/PersonaBadge.tsx`: Displays the shopper's behavioral profile.
- `lib/api.ts`: Typed SSE client that manages the 5-event hydration sequence (`persona` → `query_plan` → `token` → `report_card` → `market_estimate`).

## 🎨 Design System

Built with:
- **Tailwind CSS**: For layout and spacing.
- **Vanilla CSS Modules**: For complex glassmorphic effects and animations.
- **Framer Motion**: For smooth transitions between analysis stages.
