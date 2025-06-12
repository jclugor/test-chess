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
const boardImg  = document.getElementById("board");
let   versionID = 0;     // the frame number we already have

function poll() {
  fetch("/frame?v=" + versionID, { credentials: "include" })
    .then(r => {
      if (r.status === 304) return;            // nothing changed
      return r.blob().then(b => {
        versionID++;                           // got a new version
        boardImg.src = URL.createObjectURL(b); // paint it
      });
    });
}
setInterval(poll, 50);                         // 20 FPS ≈ smooth


function squareOf(evt) {
  const rect = boardImg.getBoundingClientRect();
  return {
    row: Math.floor((evt.clientY - rect.top ) / 80),
    col: Math.floor((evt.clientX - rect.left) / 80)
  };
}

boardImg.addEventListener("mousedown", e => {
  fetch("/click", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(squareOf(e))
  });
});

function reset() {
  fetch("/reset", { method: "POST", credentials: "include" });
}

function flip() {
  fetch("/flip", { credentials: "include" }).then(() => location.reload());
}
