# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running

Open `index.html` directly in a browser — no server, build step, or package manager needed.

## Architecture

Three files, no modules:

- `index.html` — nine `.cell` divs with `data-index` 0–8; Hebrew RTL (`lang="he" dir="rtl"`).
- `style.css` — CSS Grid board, dark theme, `@keyframes` `win-pulse` and `piece-pop`.
- `game.js` — all logic in a single flat script, runs on page load via direct DOM queries.

## game.js internals

**State:** `board` (flat 9-element array, `null`/`'X'`/`'O'`) and `gameOver` boolean are the only mutable globals.

**Turn flow:** `handlePlayerMove` → `placeSymbol` → check winner/draw → 300 ms `setTimeout(aiMove)` → `placeSymbol` → check winner/draw. The delay is purely cosmetic.

**AI:** `getBestMove` runs full minimax (no alpha-beta pruning, no depth weighting). The score function returns ±10 for a terminal win/loss regardless of depth, so the AI plays optimally (never loses) but does not prefer faster wins. Acceptable for 3×3.

**RTL board layout:** `data-index="0"` is the first div in source order, which CSS Grid renders as the **top-right** cell on screen (RTL). Index 2 is top-left, index 8 is bottom-left.

**Gotcha in `checkWinner`:** the combo is destructured as `[a, c, d]` (not `[a, b, c]`), which is non-standard naming but functionally correct since only the values are used.

**CSS classes applied by `placeSymbol`:** `x` or `o` (lowercase symbol), `taken`, and `pop`. Winning cells get `winning` added by `endGame`. `resetGame` resets every cell's `className` to `'cell'` directly.
