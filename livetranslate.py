"""CS2 chat -> English overlay, fully local.

Reads CS2's console.log (launch CS2 with -condebug), detects the language with fastText,
translates non-English chat with NLLB-600M (CTranslate2, CPU) and shows it in a
click-through, always-on-top window. Never touches the game process.

Usage: python livetranslate.py [path\\to\\console.log]
"""
import collections
import ctypes
import queue
import re
import sys
import threading
import time
import tkinter as tk
import winreg
from pathlib import Path

ROOT = Path(__file__).parent
MODELS = ROOT / "models"
CS2_LOG = Path("steamapps/common/Counter-Strike Global Offensive/game/csgo/console.log")

# Overlay placement/look. CS2 chat sits bottom-left, so default to the left edge above it.
X, Y, W, H = 20, 360, 640, 220
FONT = ("Segoe UI", 13, "bold")
SHOW_SECONDS = 15
MAX_LINES = 6
CPU_THREADS = 2  # keep CPU free for the game
MIN_CONFIDENCE = 0.5  # below this fastText is guessing (slang, "gg", ...): show nothing

# Chat made only of these is universal gaming slang; fastText misreads it (e.g. "gg ez" -> Hungarian).
SKIP = set("gg ez ezz wp gl hf glhf nt ns gj lol lmao xd ok ty thx np rush eco save mid a b ct t "
            "go noob noobs bro wtf omg pls plz report hp low lit one".split())

# fastText code -> NLLB code. Languages not listed are not translated.
NLLB = {
    "ru": "rus_Cyrl", "uk": "ukr_Cyrl", "be": "bel_Cyrl", "kk": "kaz_Cyrl", "bg": "bul_Cyrl",
    "sr": "srp_Cyrl", "mk": "mkd_Cyrl", "mn": "khk_Cyrl", "pl": "pol_Latn", "cs": "ces_Latn",
    "sk": "slk_Latn", "sl": "slv_Latn", "hr": "hrv_Latn", "bs": "bos_Latn", "de": "deu_Latn",
    "fr": "fra_Latn", "es": "spa_Latn", "pt": "por_Latn", "it": "ita_Latn", "nl": "nld_Latn",
    "ro": "ron_Latn", "hu": "hun_Latn", "sv": "swe_Latn", "no": "nob_Latn", "da": "dan_Latn",
    "fi": "fin_Latn", "et": "est_Latn", "lv": "lvs_Latn", "lt": "lit_Latn", "tr": "tur_Latn",
    "az": "azj_Latn", "uz": "uzn_Latn", "ka": "kat_Geor", "hy": "hye_Armn", "el": "ell_Grek",
    "ar": "arb_Arab", "fa": "pes_Arab", "he": "heb_Hebr", "hi": "hin_Deva", "zh": "zho_Hans",
    "ja": "jpn_Jpan", "ko": "kor_Hang", "vi": "vie_Latn", "th": "tha_Thai", "id": "ind_Latn",
    "ms": "zsm_Latn", "tl": "tgl_Latn",
}

# e.g. "11/10 21:34:56  [ALL] Name‎: msg" / "[CT] Name‎ [DEAD] @ Bombsite A: msg"
# shortcut: a player name containing ": " is split wrongly; rare enough to ignore.
CHAT_RE = re.compile(
    r"\[(?P<chan>ALL|CT|T)\]\s+(?P<name>.+?)‎?(?:\s*\[DEAD\])?(?:\s*@\s*[^:]*)?:\s(?P<msg>.*\S)"
)


def parse_chat(line):
    """Return (channel, name, message) for a chat line, else None."""
    m = CHAT_RE.search(line)
    return (m["chan"], m["name"].replace("‎", "").strip(), m["msg"]) if m else None


CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯]")
SCRIPTS = [("ja", re.compile(r"[぀-ヿ]")), ("ko", re.compile(r"[가-힯]")),
           ("zh", re.compile(r"[㐀-鿿]"))]  # kana before Han: Japanese also uses Han
# NLLB sometimes emits "Let 's move fast ." for short input
LOOSE_PUNCT = re.compile(r" (?=[.,!?;:]|'(?:s|re|ll|ve|d|m|t)\b)")


def load_slang(folder=ROOT / "slang"):
    """Read slang/*.txt ("slang = meaning" lines) into one function that rewrites a message.

    Longest terms win. Latin/Cyrillic terms match whole words only; CJK has no spaces so it
    matches anywhere. Raises ValueError with file:line on a malformed entry.
    """
    table = {}
    for f in sorted(folder.glob("*.txt")):
        for n, line in enumerate(f.read_text(encoding="utf-8-sig").splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            term, sep, meaning = (s.strip() for s in line.partition("="))
            if not (sep and term and meaning):
                raise ValueError(f"{f.name}:{n}: expected 'slang = meaning', got {line!r}")
            table[term.lower()] = meaning
    if not table:
        return lambda s: s
    rx = re.compile("|".join(
        re.escape(t) if CJK.search(t) else rf"(?<!\w){re.escape(t)}(?!\w)"
        for t in sorted(table, key=len, reverse=True)), re.IGNORECASE)
    return lambda s: rx.sub(lambda m: table[m[0].lower()], s)


class Translator:
    def __init__(self):
        import ctranslate2
        import fasttext
        import sentencepiece

        self.slang = load_slang()
        fasttext.FastText.eprint = lambda *a, **k: None  # silence load_model warning
        self.lid = fasttext.load_model(str(MODELS / "lid.176.ftz"))
        nllb = MODELS / "nllb-600m-int8"
        self.sp = sentencepiece.SentencePieceProcessor(model_file=str(nllb / "sentencepiece.bpe.model"))
        self.tr = ctranslate2.Translator(str(nllb), device="cpu", compute_type="int8",
                                         inter_threads=1, intra_threads=CPU_THREADS)

    def detect(self, text):
        for lang, rx in SCRIPTS:  # script is surer than fastText on short CJK chat
            if rx.search(text):
                return lang, 1.0
        (label,), (prob,) = self.lid.predict(text)
        return label.removeprefix("__label__"), prob

    def translate(self, text):
        """Return (lang, english) or None when no translation is needed/possible."""
        if all(w in SKIP for w in re.findall(r"\w+", text.lower())):
            return None
        fixed = self.slang(text)  # e.g. "davai bistro" -> "давай быстро", "菜" -> "差", "666" -> "nice"
        lang, prob = self.detect(fixed)
        if lang == "en" or prob < MIN_CONFIDENCE or lang not in NLLB:
            # nothing to translate, but if slang was expanded the player still learns something
            return ("slang", fixed) if fixed != text else None
        text = fixed
        src = [NLLB[lang]] + self.sp.encode(text, out_type=str) + ["</s>"]
        res = self.tr.translate_batch([src], target_prefix=[["eng_Latn"]],
                                      beam_size=2, max_decoding_length=128)
        return lang, LOOSE_PUNCT.sub("", self.sp.decode(res[0].hypotheses[0][1:]))


def find_log():
    if len(sys.argv) > 1:
        return Path(sys.argv[1])
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
    steam = Path(winreg.QueryValueEx(key, "SteamPath")[0])
    vdf = (steam / "steamapps/libraryfolders.vdf").read_text(encoding="utf-8", errors="replace")
    libs = [steam] + [Path(p.replace("\\\\", "\\")) for p in re.findall(r'"path"\s+"(.+?)"', vdf)]
    for lib in libs:
        if (lib / CS2_LOG).parent.exists():
            return lib / CS2_LOG
    sys.exit("CS2 not found. Pass the console.log path as an argument.")


def tail(path):
    """Yield new complete lines appended to path; survives CS2 recreating the file."""
    while not path.exists():
        time.sleep(1)
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        f.seek(0, 2)
        buf = ""
        while True:
            chunk = f.readline()
            if not chunk:
                if path.stat().st_size < f.tell():  # CS2 restarted and truncated the log
                    f.seek(0)
                    buf = ""
                time.sleep(0.2)
                continue
            buf += chunk
            if buf.endswith("\n"):
                yield buf.rstrip("\r\n")
                buf = ""


def worker(log, out):
    out.put("Loading models...")
    tr = Translator()
    out.put(f"Ready. Watching {log.name}")
    print("Watching", log)
    for line in tail(log):
        chat = parse_chat(line)
        if not chat:
            continue
        chan, name, msg = chat
        try:
            res = tr.translate(msg)
        except Exception as e:  # one bad message must not kill the reader
            print("translate failed:", e)
            continue
        if res:
            text = f"[{chan}] {name} ({res[0]}): {res[1]}"
            print(text)
            out.put(text)


class Overlay:
    BG = "#010101"  # made fully transparent below

    def __init__(self, q):
        self.q = q
        self.lines = collections.deque(maxlen=MAX_LINES)
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.geometry(f"{W}x{H}+{X}+{Y}")
        self.root.configure(bg=self.BG)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", self.BG)
        self.label = tk.Label(self.root, bg=self.BG, fg="#ffe14d", font=FONT, justify="left",
                              anchor="sw", wraplength=W - 10)
        self.label.pack(fill="both", expand=True)
        self.root.update_idletasks()
        # click-through + never take focus from the game
        hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
        ctypes.windll.user32.SetWindowLongW(
            hwnd, -20, style | 0x80000 | 0x20 | 0x80 | 0x08000000)  # LAYERED|TRANSPARENT|TOOLWINDOW|NOACTIVATE
        self.poll()

    def poll(self):
        now = time.time()
        while not self.q.empty():
            self.lines.append((now, self.q.get()))
        while self.lines and now - self.lines[0][0] > SHOW_SECONDS:
            self.lines.popleft()
        self.label.config(text="\n".join(t for _, t in self.lines))
        self.root.attributes("-topmost", True)  # games sometimes steal topmost
        self.root.after(200, self.poll)


def main():
    log = find_log()
    q = queue.Queue()
    threading.Thread(target=worker, args=(log, q), daemon=True).start()
    print("Close this window to quit.")
    Overlay(q).root.mainloop()


if __name__ == "__main__":
    main()
