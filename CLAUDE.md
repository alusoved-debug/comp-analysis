# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository overview

This working directory contains two distinct areas:

1. **Hebrew real-estate documents** (root level) — Word/PDF files relating to developer comparisons, tender presentations, and resident meetings. These are not code.
2. **`tictactoe/`** — A self-contained vanilla-JS tic-tac-toe web app (Hebrew UI, RTL layout).

## tictactoe app

No build step, no package manager, no dependencies. Open `tictactoe/index.html` directly in a browser to run it.

**Architecture:**
- `index.html` — 3×3 grid of `.cell` divs; Hebrew RTL (`dir="rtl"`).
- `style.css` — dark theme, CSS Grid board, `@keyframes` for win-pulse and piece-pop animations.
- `game.js` — all game logic in a single flat file. Key pieces:
  - `PLAYER = 'X'`, `AI = 'O'`; `board` is a flat 9-element array.
  - `handlePlayerMove` → `aiMove` flow; AI move is delayed 300 ms for UX feel.
  - `getBestMove` / `minimax` — unoptimized minimax (no alpha-beta pruning); fine for 3×3.
  - `endGame(combo, winner)` highlights winning cells via the `.winning` class.

There are no tests or linting configuration.
