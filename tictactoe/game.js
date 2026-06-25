const PLAYER = 'X';
const AI = 'O';

const WIN_COMBOS = [
  [0, 1, 2], [3, 4, 5], [6, 7, 8],
  [0, 3, 6], [1, 4, 7], [2, 5, 8],
  [0, 4, 8], [2, 4, 6],
];

let board = Array(9).fill(null);
let gameOver = false;

const cells = document.querySelectorAll('.cell');
const status = document.getElementById('status');
const restartBtn = document.getElementById('restart');

cells.forEach(cell => cell.addEventListener('click', handlePlayerMove));
restartBtn.addEventListener('click', resetGame);

function handlePlayerMove(e) {
  const idx = parseInt(e.target.dataset.index);
  if (gameOver || board[idx]) return;

  placeSymbol(idx, PLAYER);

  const win = checkWinner(board);
  if (win) { endGame(win, PLAYER); return; }
  if (isDraw(board)) { endGame(null, null); return; }

  status.textContent = 'המחשב חושב...';
  setTimeout(aiMove, 300);
}

function aiMove() {
  const idx = getBestMove(board);
  placeSymbol(idx, AI);

  const win = checkWinner(board);
  if (win) { endGame(win, AI); return; }
  if (isDraw(board)) { endGame(null, null); return; }

  status.textContent = 'תורך לשחק!';
}

function placeSymbol(idx, symbol) {
  board[idx] = symbol;
  const cell = cells[idx];
  cell.textContent = symbol;
  cell.classList.add(symbol.toLowerCase(), 'taken', 'pop');
}

function endGame(combo, winner) {
  gameOver = true;
  if (winner === PLAYER) {
    status.textContent = 'ניצחת! כל הכבוד!';
    status.className = 'status winner';
  } else if (winner === AI) {
    status.textContent = 'המחשב ניצח. נסה שוב!';
    status.className = 'status winner';
  } else {
    status.textContent = 'תיקו!';
    status.className = 'status draw';
  }
  if (combo) {
    combo.forEach(i => cells[i].classList.add('winning'));
  }
}

function resetGame() {
  board = Array(9).fill(null);
  gameOver = false;
  status.textContent = 'תורך לשחק!';
  status.className = 'status';
  cells.forEach(cell => {
    cell.textContent = '';
    cell.className = 'cell';
  });
}

function checkWinner(b) {
  for (const combo of WIN_COMBOS) {
    const [a, c, d] = combo;
    if (b[a] && b[a] === b[c] && b[a] === b[d]) return combo;
  }
  return null;
}

function isDraw(b) {
  return b.every(cell => cell !== null);
}

function score(b) {
  const win = checkWinner(b);
  if (!win) return 0;
  return b[win[0]] === AI ? 10 : -10;
}

function minimax(b, isMaximizing) {
  const s = score(b);
  if (s !== 0) return s;
  if (isDraw(b)) return 0;

  if (isMaximizing) {
    let best = -Infinity;
    for (let i = 0; i < 9; i++) {
      if (!b[i]) {
        b[i] = AI;
        best = Math.max(best, minimax(b, false));
        b[i] = null;
      }
    }
    return best;
  } else {
    let best = Infinity;
    for (let i = 0; i < 9; i++) {
      if (!b[i]) {
        b[i] = PLAYER;
        best = Math.min(best, minimax(b, true));
        b[i] = null;
      }
    }
    return best;
  }
}

function getBestMove(b) {
  let bestVal = -Infinity;
  let bestIdx = -1;
  for (let i = 0; i < 9; i++) {
    if (!b[i]) {
      b[i] = AI;
      const val = minimax(b, false);
      b[i] = null;
      if (val > bestVal) {
        bestVal = val;
        bestIdx = i;
      }
    }
  }
  return bestIdx;
}
