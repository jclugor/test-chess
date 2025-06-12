from __future__ import annotations
import io, math, os, base64
from functools import wraps
from flask import Flask, request, Response, render_template, redirect
import pygame as pg
import chess

# ─── basic HTTP auth ────────────────────────────────────────────────────────
USERNAME = os.getenv("CHESS_USER", "friend")
PASSWORD = os.getenv("CHESS_PASS", "letmein")

def check_auth(auth_header: str|None) -> bool:
    if not auth_header or not auth_header.startswith("Basic "):
        return False
    user_pass = base64.b64decode(auth_header[6:]).decode()
    return user_pass == f"{USERNAME}:{PASSWORD}"

def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not check_auth(request.headers.get("Authorization")):
            return Response(
                "Unauthorized", 401,
                {"WWW-Authenticate": 'Basic realm="WebChess"'}
            )
        return f(*args, **kwargs)
    return wrapper

# ─── game state (single shared board) ───────────────────────────────────────
board  = chess.Board()
last_mv: chess.Move|None = None
human_color = chess.WHITE      # can flip on demand
SEL_SQ: chess.Square|None = None

# ─── Pygame off-screen context ──────────────────────────────────────────────
SQ = 80
SIZE = SQ*8, SQ*8
pg.init()
surf = pg.Surface(SIZE)
FONT = pg.font.Font(None, 54)  # used only by sprite generator

# sprite cache from your previous code  … (exact same build_sprite / piece_sprite) …
#  ⬇️  copy the entire sprite + arrow + board-drawing helpers unchanged  ⬇️

# … START of helper section (identical to previous Pygame version) …
import pygame as pg
SPRITE_CACHE: dict[tuple[int,bool], pg.Surface] = {}
WHITE_PIECE  = (245, 245, 245)
BLACK_PIECE  = (30, 30, 30)
EDGE_COLOR   = (0, 0, 0)
LIGHT_COLOR  = (240, 217, 181)
DARK_COLOR   = (181, 136,  99)
SEL_COLOR    = (247, 247, 105)
LEGAL_COLOR  = (186, 202,  68)
LAST_COLOR   = (255, 195,  77)
ARROW_COLOR  = (255, 90,  90)

def build_sprite(piece_type, color_bool):
    # … (exact function body copied from the canvas file) …
    #  🔸 keep everything exactly the same 🔸
    pass  # <-- replace with real body!

def piece_sprite(piece):  # unchanged
    key = (piece.piece_type, piece.color)
    if key not in SPRITE_CACHE:
        SPRITE_CACHE[key] = build_sprite(piece.piece_type, piece.color)
    return SPRITE_CACHE[key]

def rc_to_sq(r,c): return chess.square(c, 7-r)
def sq_to_rc(sq):  return 7-chess.square_rank(sq), chess.square_file(sq)

def draw_board(surface, board, sel_sq, legal, last_move):
    # … (identical drawing logic from the canvas file) …
    pass  # <-- replace with real body!
# … END helper section …

# ─── naive AI (same as before, depth-3 minimax) ─────────────────────────────
PIECE_VAL = {chess.PAWN:100, chess.KNIGHT:320, chess.BISHOP:330,
             chess.ROOK:500, chess.QUEEN:900, chess.KING:0}

def evaluate(bd, ai_c):
    if bd.is_checkmate():
        return -1e6 if bd.turn==ai_c else 1e6
    return sum((1 if pc.color==ai_c else -1)*PIECE_VAL[pc.piece_type]
               for pc in bd.piece_map().values())

def minimax(bd, d, a, be, maxing, ai_c):
    if d==0 or bd.is_game_over():
        return evaluate(bd, ai_c), None
    best = None
    if maxing:
        val = -math.inf
        for mv in bd.legal_moves:
            bd.push(mv); score,_ = minimax(bd,d-1,a,be,False,ai_c); bd.pop()
            if score>val: val,best = score,mv
            a = max(a, score);  be = be
            if be<=a: break
        return val,best
    else:
        val = math.inf
        for mv in bd.legal_moves:
            bd.push(mv); score,_ = minimax(bd,d-1,a,be,True,ai_c); bd.pop()
            if score<val: val,best = score,mv
            be = min(be, score)
            if be<=a: break
        return val,best

def ai_move(bd, ai_c):
    return minimax(bd, 3, -math.inf, math.inf, bd.turn==ai_c, ai_c)[1]

# ─── Flask app ──────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder="static", template_folder="templates")

@app.route("/")
@require_auth
def index():
    return render_template("index.html")

@app.route("/frame")
@require_auth
def frame():
    """Return the current board as PNG."""
    draw_board(surf, board, SEL_SQ, [], last_mv)
    buf = pg.image.tostring(surf, "RGB")
    img = pg.image.fromstring(buf, SIZE, "RGB")
    f = io.BytesIO()
    pg.image.save(img, f)
    f.seek(0)
    return Response(f.getvalue(), mimetype="image/png",
                    headers={"Cache-Control": "no-cache"})

@app.route("/click", methods=["POST"])
@require_auth
def click():
    global SEL_SQ, last_mv
    data = request.json
    r,c = int(data["row"]), int(data["col"])
    sq  = rc_to_sq(r,c)

    if board.turn != human_color or board.is_game_over():
        return "AI thinking", 202

    if SEL_SQ is None:
        pc = board.piece_at(sq)
        if pc and pc.color == human_color:
            SEL_SQ = sq
    else:
        mv = chess.Move(SEL_SQ, sq)
        if mv in board.legal_moves:
            board.push(mv); last_mv = mv
            SEL_SQ = None
            # ---- AI reply
            if not board.is_game_over():
                mv_ai = ai_move(board, not human_color)
                if mv_ai:
                    board.push(mv_ai); last_mv = mv_ai
        else:
            SEL_SQ = None
    return "ok"

@app.route("/flip")
@require_auth
def flip():
    global human_color
    human_color = not human_color
    board.reset()
    return redirect("/")

# ─── Run locally (Render uses gunicorn) ─────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True)
