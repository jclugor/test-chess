from __future__ import annotations
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"   # no real X-server available
import io, math, os, base64
from functools import wraps
from flask import Flask, request, Response, render_template, redirect
import pygame as pg
import chess
from PIL import Image
import io, pygame as pg


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
board       = chess.Board()
last_mv     = None
SEL_SQ      = None
LEGAL_SQS   = []
frame_png   = b""      # cached bytes
frame_stamp = 0 

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

def build_sprite(piece_type: int, color_bool: bool) -> pg.Surface:
    surf = pg.Surface((SQ, SQ), pg.SRCALPHA)
    # simple two-color glyph: white pieces are light-gray, black pieces dark-gray
    fg = (245, 245, 245) if color_bool else (40, 40, 40)
    bg = (0, 0, 0, 0)
    surf.fill(bg)

    # draw very-simple shapes so we stay self-contained
    mid = SQ // 2
    r   = SQ // 2 - 6
    if piece_type == chess.PAWN:
        pg.draw.circle(surf, fg, (mid, mid+6), r-8)
    elif piece_type == chess.ROOK:
        pg.draw.rect(surf, fg, (mid-r+4, mid-r+4, 2*r-8, 2*r-4))
    elif piece_type == chess.KNIGHT:
        pts = [(mid-r+4, mid+r-4), (mid-r+4, mid-2), (mid, mid-r+4),
               (mid+r-4, mid-4), (mid+2, mid+4), (mid+r-6, mid+r-4)]
        pg.draw.polygon(surf, fg, pts)
    elif piece_type == chess.BISHOP:
        pg.draw.ellipse(surf, fg, (mid-r+4, mid-r+4, 2*r-8, 2*r))
    elif piece_type == chess.QUEEN:
        pts = [(mid-r+4, mid+r-4), (mid-r+4, mid-6), (mid-r//2, mid-r+4),
               (mid, mid-10), (mid+r//2, mid-r+4), (mid+r-4, mid-6),
               (mid+r-4, mid+r-4)]
        pg.draw.polygon(surf, fg, pts)
    elif piece_type == chess.KING:
        pg.draw.rect(surf, fg, (mid-r+6, mid-r+4, 2*r-12, 2*r))
        pg.draw.line(surf, fg, (mid, mid-r-4), (mid, mid-r+8), 4)
        pg.draw.line(surf, fg, (mid-8, mid-r), (mid+8, mid-r), 4)
    return surf


def piece_sprite(piece):  # unchanged
    key = (piece.piece_type, piece.color)
    if key not in SPRITE_CACHE:
        SPRITE_CACHE[key] = build_sprite(piece.piece_type, piece.color)
    return SPRITE_CACHE[key]

def rc_to_sq(r,c): return chess.square(c, 7-r)
def sq_to_rc(sq):  return 7-chess.square_rank(sq), chess.square_file(sq)

# ---------- draw_board ------------------------------------------------------
LIGHT = (240, 217, 181)
DARK  = (181, 136,  99)
SEL   = (247, 247, 105)
LEGAL = (186, 202,  68)
LAST  = (255, 195,  77)
ARROW = (255,  90,  90)

def draw_board(dst: pg.Surface,
               board: chess.Board,
               sel_sq: chess.Square|None,
               legal_sqs: list[chess.Square],
               last_move: chess.Move|None):
    # board squares
    for r in range(8):
        for c in range(8):
            pg.draw.rect(dst, LIGHT if (r+c)%2==0 else DARK,
                         pg.Rect(c*SQ, r*SQ, SQ, SQ))

    # last-move highlight + arrow
    if last_move:
        for sq in (last_move.from_square, last_move.to_square):
            rr, cc = 7-chess.square_rank(sq), chess.square_file(sq)
            pg.draw.rect(dst, LAST, pg.Rect(cc*SQ, rr*SQ, SQ, SQ))
        # arrow
        rf, cf = 7-chess.square_rank(last_move.from_square), chess.square_file(last_move.from_square)
        rt, ct = 7-chess.square_rank(last_move.to_square),   chess.square_file(last_move.to_square)
        start = (cf*SQ+SQ//2, rf*SQ+SQ//2)
        end   = (ct*SQ+SQ//2, rt*SQ+SQ//2)
        pg.draw.line(dst, ARROW, start, end, 6)

    # selection + legal
    if sel_sq is not None:
        rs, cs = 7-chess.square_rank(sel_sq), chess.square_file(sel_sq)
        pg.draw.rect(dst, SEL, pg.Rect(cs*SQ, rs*SQ, SQ, SQ))
    for sq in legal_sqs:
        rr, cc = 7-chess.square_rank(sq), chess.square_file(sq)
        pg.draw.rect(dst, LEGAL, pg.Rect(cc*SQ, rr*SQ, SQ, SQ))

    # pieces
    for sq, pc in board.piece_map().items():
        rr, cc = 7-chess.square_rank(sq), chess.square_file(sq)
        dst.blit(piece_sprite(pc), (cc*SQ, rr*SQ))

# ─── naive AI (same as before, depth-3 minimax) ─────────────────────────────
PIECE_VAL = {chess.PAWN:100, chess.KNIGHT:320, chess.BISHOP:330,
             chess.ROOK:500, chess.QUEEN:900, chess.KING:0}
def redraw():
    """Rebuild the PNG buffer & bump the stamp."""
    global frame_png, frame_stamp
    draw_board(surf, board, SEL_SQ, LEGAL_SQS, last_mv)
    raw = pg.image.tostring(surf, "RGBA")
    img = Image.frombytes("RGBA", SIZE, raw)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=75, optimize=True)   # ← JPEG, small
    frame_png = buf.getvalue()
    frame_stamp += 1
    
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
    """Return the current board as a PNG buffer."""
    draw_board(surf, board, SEL_SQ, LEGAL_SQS, last_mv)

    # Convert the Pygame surface to a PNG in-memory
    raw = pg.image.tostring(surf, "RGBA")
    img = Image.frombytes("RGBA", SIZE, raw)
    buf = io.BytesIO()
    img.save(buf, format="PNG")   # real PNG!
    buf.seek(0)
    client_ver = int(request.args.get("v", 0))
    if client_ver == frame_stamp:
        return Response(status=304)          # "Not Modified"
    return Response(frame_png,
                    mimetype="image/jpeg",
                    headers={"Cache-Control": "no-store"})

@app.route("/click", methods=["POST"])
@require_auth
def click():
    """
    Handles one mouse-click coming from the browser.
    The client sends the row/col (0-7) of the square that was clicked.
    """
    global SEL_SQ, LEGAL_SQS, last_mv

    # row / col from JSON
    data = request.get_json(force=True)
    r, c = int(data["row"]), int(data["col"])
    sq = rc_to_sq(r, c)

    # Ignore clicks during AI turn or after game over
    if board.turn != human_color or board.is_game_over():
        return ("AI thinking", 202)

    # ─── first click: select a piece ─────────────────────────────
    if SEL_SQ is None:
        pc = board.piece_at(sq)
        if pc and pc.color == human_color:
            SEL_SQ = sq
            LEGAL_SQS = [m.to_square for m in board.legal_moves
                         if m.from_square == SEL_SQ]
        # respond OK either way so the client can refresh
        return "ok"

    # ─── second click: attempt a move ────────────────────────────
    move = chess.Move(SEL_SQ, sq)

    # handle promotion (default to queen for simplicity)
    if (move in board.legal_moves and
        board.piece_at(SEL_SQ).piece_type == chess.PAWN and
        chess.square_rank(sq) in (0, 7)):
        move = chess.Move(SEL_SQ, sq, promotion=chess.QUEEN)

    if move in board.legal_moves:
        board.push(move)
        last_mv = move

        # let the AI reply immediately
        if not board.is_game_over():
            mv_ai = ai_move(board, not human_color)
            if mv_ai:
                board.push(mv_ai)
                last_mv = mv_ai

    # clear selection / highlights for the next user click
    SEL_SQ = None
    LEGAL_SQS = []

    return "ok"


@app.route("/flip")
@require_auth
def flip():
    global human_color
    human_color = not human_color
    board.reset()
    return redirect("/")

@app.route("/reset", methods=["POST"])
@require_auth
def reset():
    global SEL_SQ, LEGAL_SQS, last_mv, board
    board.reset()
    SEL_SQ = None
    LEGAL_SQS = []
    last_mv = None
    return "ok"
# ─── Run locally (Render uses gunicorn) ─────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True)
