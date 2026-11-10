# Đóng góp tiếng lóng

Tiếng lóng nằm trong `slang/<mã ngôn ngữ>.txt` (vd. `zh.txt`, `ru.txt`, `pl.txt`). Mỗi dòng một mục:

```
slang = nghĩa
```

- **Nghĩa viết bằng chính ngôn ngữ đó** (dễ hiểu, không lóng) → sẽ được dịch máy tiếp. Vd. `太菜 = 太差`, `davai = давай`.
- **Nghĩa viết bằng tiếng Anh** → hiện nguyên văn. Dùng cho câu cảm thán/chửi mà dịch máy làm hỏng. Vd. `cyka blyat = (swearing) damn it`.
- Dòng bắt đầu bằng `#` là ghi chú. Không phân biệt hoa thường.
- Chữ Latin/Cyrillic chỉ khớp **nguyên từ**; chữ Trung/Nhật/Hàn khớp **ở bất kỳ đâu**, nên đừng thêm một chữ Hán đơn lẻ dễ nằm trong từ khác (vd. `菜` sẽ phá `蔬菜`) — thêm cụm `太菜`, `菜鸡` thay vì vậy.
- Cụm dài hơn được ưu tiên, nên `cyka blyat` thắng `cyka`.

## Quy tắc nội dung
- Dịch chửi thề / xúc phạm **đúng nghĩa** là được (người chơi cần biết mình bị chửi), đánh dấu `(insult)` hoặc `(swearing)`.
- **Không** thêm từ miệt thị chủng tộc, tôn giáo, giới tính, xu hướng tính dục. PR có những mục này sẽ bị từ chối.
- Mỗi mục nên là tiếng lóng thật sự hay gặp trong CS2, không phải từ điển chung.

## Trước khi gửi
```
.venv\Scripts\python test_livetranslate.py
```
Test báo lỗi kèm `file:dòng` nếu có mục sai định dạng. Thử nhanh một câu:
```
.venv\Scripts\python -c "from livetranslate import Translator; print(Translator().translate('你们太菜了'))"
```
