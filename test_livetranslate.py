"""Self-check: python test_livetranslate.py"""
import json
import tempfile
from pathlib import Path

from livetranslate import MODELS, NLLB, Translator, load_slang, parse_chat

# slang: real files parse; whole-word for Latin, substring for CJK, longest wins, case-insensitive
slang = load_slang()
assert slang("Davai bistro") == "давай быстро"
assert slang("davaiii") == "davaiii"
assert slang("你们太菜了") == "你们太差了"
assert slang("蔬菜") == "蔬菜"
assert slang("Cyka Blyat") == "(swearing) damn it"
with tempfile.TemporaryDirectory() as d:
    (Path(d) / "xx.txt").write_text("# ok\nfoo = bar\nbroken line\n", encoding="utf-8")
    try:
        load_slang(Path(d))
        raise AssertionError("malformed slang line not rejected")
    except ValueError as e:
        assert "xx.txt:3" in str(e), e

# parser
assert parse_chat("11/10 21:34:56  [ALL] Vasya‎: привет всем") == ("ALL", "Vasya", "привет всем")
assert parse_chat("[CT] Bob‎ @ Bombsite A: rotate b") == ("CT", "Bob", "rotate b")
assert parse_chat("[T] Ana‎ [DEAD]: nt") == ("T", "Ana", "nt")
assert parse_chat("[ALL] x: a: b") == ("ALL", "x", "a: b")
assert parse_chat("ChangeGameUIState: CSGO_GAME_UI_STATE_INGAME") is None
assert parse_chat("[ALL] Empty‎: ") is None

# every mapped NLLB language token exists in the model vocabulary
vocab = set(json.loads((MODELS / "nllb-600m-int8/shared_vocabulary.json").read_text(encoding="utf-8")))
assert set(NLLB.values()) <= vocab, set(NLLB.values()) - vocab

# translation
tr = Translator()
assert tr.translate("nice shot") is None
assert tr.translate("gg ez") is None  # fastText calls this Hungarian
assert tr.translate("666") == ("slang", "nice")
assert tr.translate("davai bistro")[0] == "ru"
assert tr.translate("别白给了")[0] == "zh"  # short Chinese: script beats fastText
for text in ["привет, как дела?", "uważaj, są na B", "jestem bez kasy", "tamam, B'ye gidiyorum",
             "cuidado, vienen por la A", "我们去A点", "đừng có rush nữa"]:
    print(text, "->", tr.translate(text))
print("ok")
