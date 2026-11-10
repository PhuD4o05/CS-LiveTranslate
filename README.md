# CS-LiveTranslate

Dịch chat CS2 sang tiếng Anh ngay trong trận, chạy hoàn toàn trên máy (không cần mạng), hiển thị bằng overlay trong suốt. Không đụng vào tiến trình game.

## Cài một lần
1. Steam → CS2 → Properties → Launch Options: thêm `-condebug` (để game ghi chat vào `console.log`).
2. Trong CS2: Settings → Video → Display Mode = **Fullscreen Windowed** (overlay không hiện được ở fullscreen exclusive).
3. Cài thư viện và tải model (PowerShell, trong thư mục repo). Bước chuyển NLLB tải ~2.7 GB một lần, sau đó chỉ giữ ~600 MB:
   ```powershell
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   mkdir models
   Invoke-WebRequest https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz -OutFile models\lid.176.ftz
   .venv\Scripts\pip install torch transformers --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple
   .venv\Scripts\ct2-transformers-converter --model facebook/nllb-200-distilled-600M --quantization int8 --output_dir models\nllb-600m-int8 --copy_files sentencepiece.bpe.model
   .venv\Scripts\pip uninstall -y torch transformers
   ```
   Model gốc tải về nằm trong cache Hugging Face (`%USERPROFILE%\.cache\huggingface`), xóa được sau khi chuyển xong.

Model NLLB của Meta theo giấy phép CC-BY-NC 4.0 (không dùng thương mại); repo này không kèm model.

## Chạy
```
.venv\Scripts\python livetranslate.py
```
Tự tìm `console.log` qua Steam; hoặc truyền đường dẫn làm tham số. Đóng cửa sổ console để thoát.

Chỉnh vị trí/cỡ chữ/thời gian hiện ở đầu `livetranslate.py` (`X, Y, W, H`, `FONT`, `SHOW_SECONDS`).

## Tiếng lóng
`slang/*.txt` thay tiếng lóng trước khi dịch (`太菜 → 太差`, `davai → давай`, `666 → nice`). Sửa file rồi chạy lại tool là có hiệu lực. Cách đóng góp: xem [CONTRIBUTING.md](CONTRIBUTING.md).

## Kiểm tra
```
.venv\Scripts\python test_livetranslate.py
```

## Giới hạn
- Câu Latin ngắn hoặc trộn tiếng Anh (`jeden na B, low hp`) thường không được dịch: fastText không đủ chắc. Tiếng Nga viết không dấu chỉ dịch được khi từ đó có trong `slang/ru.txt`.
- Định dạng dòng chat trong `console.log` chưa kiểm chứng với log thật; nếu không thấy gì, gửi vài dòng chat từ `console.log`.
