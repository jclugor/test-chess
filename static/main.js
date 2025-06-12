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
let stamp = 0;                   // board version we last saw

function refresh() {
  fetch("/frame?v=" + stamp, { credentials: "include" })
    .then(r => {
      if (r.status === 304) return;   // nothing new
      return r.blob().then(b => {
        stamp++;                      // on any 200 we bump
        boardImg.src = URL.createObjectURL(b);
      });
    });
}
setInterval(refresh, 50);        // 20 FPS feels instant, yet light
