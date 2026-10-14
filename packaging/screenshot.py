"""Take README screenshots of the app (used by the Screenshots workflow).

Runs the real app against a tiny local stand-in for an OpenAI-compatible server
that answers with pre-written Brazilian Portuguese lines, so the screenshot shows
a translation in progress without needing an API key.

    python packaging/screenshot.py docs
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LINES = [
    ("Previously on Night Shift...", "Anteriormente em Plantão Noturno..."),
    ("- Where are you going at this hour?\n- To the hospital.", None),
    ("Where are you going at this hour?", "Aonde você vai a essa hora?"),
    ("To the hospital.", "Para o hospital."),
    ("They called me in for another shift.", "Me chamaram para mais um plantão."),
    ("You haven't slept in two days.", "Você não dorme há dois dias."),
    ("I know. But they need me tonight.", "Eu sei. Mas eles precisam de mim hoje."),
    ("Promise me you'll call when you get there.", "Me promete que vai ligar quando chegar lá."),
    ("I promise.", "Prometo."),
    ("[PHONE RINGING]", "[TELEFONE TOCANDO]"),
    ("Dr. Reyes, we have a problem in room four.", "Dra. Reyes, temos um problema no quarto quatro."),
    ("I'm on my way.", "Estou a caminho."),
]
TRANSLATIONS = {en: pt for en, pt in LINES if pt}


def write_sample(folder: Path) -> list[Path]:
    cues = [LINES[0][0], LINES[1][0]] + [en for en, _ in LINES[4:]]
    blocks = []
    for i, text in enumerate(cues, start=1):
        start, end = 2 * i, 2 * i + 1.6
        fmt = lambda s: f"00:00:{int(s):02d},{int((s % 1) * 1000):03d}"  # noqa: E731
        blocks.append(f"{i}\n{fmt(start)} --> {fmt(end)}\n{text}\n")
    paths = []
    for name in ("Night.Shift.S01E01.en.srt", "Night.Shift.S01E02.en.srt", "Night.Shift.S01E03.en.srt"):
        path = folder / name
        path.write_text("\n".join(blocks), encoding="utf-8")
        paths.append(path)
    return paths


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        lines = json.loads(body["messages"][-1]["content"])["lines"]
        time.sleep(0.9)
        answer = {"translations": [{"id": l["id"], "text": TRANSLATIONS.get(l["text"], l["text"])} for l in lines]}
        data = json.dumps({"choices": [{"message": {"content": json.dumps(answer, ensure_ascii=False)}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> int:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "docs").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp())
    os.environ["SRTAI_HOME"] = str(work / "home")

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_address[1]

    from srtai.settings import Settings, set_api_key

    s = Settings.load()
    # The app is set to Gemini, but the requests go to the local stand-in server.
    s.provider = "gemini"
    s.base_urls["gemini"] = f"http://127.0.0.1:{port}/v1"
    s.workers["gemini"] = 1
    s.batch_sizes["gemini"] = 1
    s.appearance = "dark"
    s.ui_language = os.environ.get("SRTAI_SHOT_LANG", "en")
    s.job.use_cache = False
    s.geometry = "1000x720+0+0"  # GitHub's Windows runners have a 1024x768 screen
    s.save()
    set_api_key("gemini", "demo-key-not-real-0000")

    from PIL import ImageGrab

    from srtai.gui.app import App

    app = App([str(p) for p in write_sample(work)])

    errors: list[str] = []

    def shot(name: str) -> None:
        try:
            app.update()
            x, y = app.winfo_rootx(), app.winfo_rooty()
            w, h = app.winfo_width(), app.winfo_height()
            ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=sys.platform == "win32").save(
                out_dir / f"{name}.png")
            print("saved", out_dir / f"{name}.png", (x, y, w, h), flush=True)
        except Exception as exc:  # report and keep going
            errors.append(f"{name}: {exc!r}")
            print("FAILED", name, repr(exc), flush=True)

    def go_to(page: str) -> None:
        label = app._nav_labels[page]
        app.nav.set(label)
        app._navigate(label)

    app.after(2500, app.translate_page._start)
    app.after(8200, lambda: shot("screenshot"))
    app.after(8600, lambda: go_to("models"))
    app.after(11000, lambda: shot("screenshot-models"))
    app.after(11400, lambda: go_to("settings"))
    app.after(13000, lambda: shot("screenshot-settings"))
    app.after(13500, app.destroy)
    app.mainloop()
    httpd.shutdown()
    return 1 if errors or not (out_dir / "screenshot.png").exists() else 0


if __name__ == "__main__":
    sys.exit(main())
