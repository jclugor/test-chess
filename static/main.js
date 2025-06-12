const board = document.getElementById("board");
let dragging = false;

function refresh() { board.src = "/frame?ts=" + Date.now(); }
setInterval(refresh, 200);

board.addEventListener("mousedown", e => { dragging = true; click(e); });
board.addEventListener("mouseup",   () => dragging = false);
board.addEventListener("mousemove", e => { if (dragging) click(e); });

function click(e) {
  const rect = board.getBoundingClientRect();
  const x = e.clientX - rect.left, y = e.clientY - rect.top;
  fetch("/click", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ row: Math.floor(y/80), col: Math.floor(x/80) })
  }).then(refresh);
}

function flip() { fetch("/flip").then(()=>location.reload()); }

function reset() {
  fetch("/reset", { method: "POST", credentials: "include" })
      .then(()=> refresh());
}
