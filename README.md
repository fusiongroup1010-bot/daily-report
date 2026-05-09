# 📋 Daily Sync Report – Phối Hợp Liên Bộ Phận

Hệ thống báo cáo nội bộ hàng ngày cho các bộ phận **Sale Online, Sale Offline, C.S, Logistics**.

---

## ✨ Tính năng

- ✅ Form báo cáo đầy đủ (Thông tin chung, Vấn đề ưu tiên, Nhiệm vụ liên kết, Chuẩn bị ngày mai, Checklist)
- ✅ Bộ phận tiếp nhận → hiện ô nhiệm vụ động (tick phòng nào, ô đó xuất hiện)
- ✅ Gửi báo cáo qua **Email (Gmail SMTP)** tự động theo giờ
- ✅ Xuất file **PDF** giữ nguyên font và icon
- ✅ Lưu dữ liệu báo cáo cục bộ (JSON)

---

## 🚀 Chạy local

```bash
# 1. Cài dependencies
pip install -r requirements.txt

# 2. Tạo file cấu hình từ template
cp config_template.json config.json
# → Chỉnh sửa config.json: nhập email người gửi, App Password Gmail, email người nhận

# 3. Chạy ứng dụng
python app.py
```

Truy cập: **http://127.0.0.1:5000**

---

## ☁️ Deploy lên Render (miễn phí)

1. Fork repo này lên GitHub của bạn
2. Vào [render.com](https://render.com) → New → Web Service
3. Kết nối GitHub repo
4. Cài đặt:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
5. Thêm **Environment Variables** (thay cho config.json):

| Key | Value |
|-----|-------|
| `SENDER_EMAIL` | your_email@gmail.com |
| `SENDER_PASSWORD` | your_app_password |
| `RECEIVER_EMAILS` | email1@co.com,email2@co.com |
| `REPORT_TIME` | 08:10 |

> ⚠️ **Quan trọng:** Không push `config.json` lên GitHub (đã có trong `.gitignore`). Dùng Environment Variables thay thế khi deploy.

---

## 📁 Cấu trúc dự án

```
Project 11/
├── app.py              # Flask server + routes
├── reporter.py         # Logic tạo & gửi báo cáo
├── requirements.txt    # Python dependencies
├── Procfile            # Gunicorn start command
├── config_template.json # Mẫu cấu hình (không có password)
├── templates/
│   ├── index.html      # Form báo cáo chính
│   └── settings.html   # Trang cài đặt Email
└── static/             # CSS / assets (nếu có)
```

---

## 📧 Cấu hình Gmail App Password

1. Bật **2-Step Verification** trên tài khoản Google
2. Vào [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Tạo App Password → Copy 16 ký tự
4. Dán vào ô **App Password** trong Settings

---

*© 2026 Daily Sync Report System – Fusion Group*
