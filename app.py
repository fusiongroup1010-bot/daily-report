import sys
import threading
import time
import schedule
import os
import json
from flask import Flask, render_template, jsonify, request, send_file
from reporter import job, load_config, load_report_data
from datetime import datetime
import io

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

app = Flask(__name__, 
            template_folder=resource_path('templates'),
            static_folder=resource_path('static'))

# Dung duong dan tuyet doi cho config va data de dam bao ghi duoc file o thu muc hien tai cua exe
BASE_DIR = os.path.abspath(os.path.dirname(sys.executable)) if getattr(sys, 'frozen', False) else os.path.abspath(".")
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')
DATA_FILE = os.path.join(BASE_DIR, 'latest_report.json')
REPORTS_DIR = os.path.join(BASE_DIR, 'reports')
os.makedirs(REPORTS_DIR, exist_ok=True)

# Ghi de duong dan trong reporter de dong bo voi app.py
import reporter
reporter.CONFIG_FILE = CONFIG_FILE
reporter.DATA_FILE = DATA_FILE


def run_scheduler():
    """Vong lap chay ngam de kiem tra lich gui bao cao"""
    print("Background scheduler started.", flush=True)
    current_scheduled_time = None
    while True:
        try:
            config = load_config()
            new_time = config.get('report_time', '08:10')
            if new_time != current_scheduled_time:
                schedule.clear()
                schedule.every().day.at(new_time).do(job)
                current_scheduled_time = new_time
                print(f"Lich gui moi duoc thiet lap: {new_time}", flush=True)
            
            schedule.run_pending()
        except Exception as e:
            print(f"Scheduler Error: {e}", flush=True)
        time.sleep(10)

def get_default_report(date_str):
    default_data = {
        "report_date": date_str,
        "department": "",
        "receiving_depts": "",
        "priority_issue": "",
        "priority_impact": "",
        "priority_deadline": "",
        "check1": False,
        "check2": False,
        "check3": False
    }
    
    # Old legacy keys for backward compatibility
    legacy_keys = [
        "task_online_info", "task_offline_info", "task_cs_info", "task_logistics_info", "task_mkt_hn_info",
        "prep_logistics", "prep_sales_online", "prep_cs", "prep_sales_offline", "prep_mkt_hn"
    ]
    for key in legacy_keys:
        default_data[key] = ""
        
    # Split fields
    target_keys_tasks = ["online", "offline", "cs", "logistics", "mkt_hn"]
    target_keys_prep = ["logistics", "sales_online", "cs", "sales_offline", "mkt_hn"]
    senders = ["sale_online", "sale_offline", "cs", "logistics", "mkt_hn"]
    
    for target in target_keys_tasks:
        for sender in senders:
            default_data[f"task_{target}_from_{sender}"] = ""
    for target in target_keys_prep:
        for sender in senders:
            default_data[f"prep_{target}_from_{sender}"] = ""
            
    return default_data


def ensure_split_fields(data):
    if not data:
        return data
    
    # Ensure all new keys exist
    target_keys_tasks = ["online", "offline", "cs", "logistics", "mkt_hn"]
    target_keys_prep = ["logistics", "sales_online", "cs", "sales_offline", "mkt_hn"]
    senders = ["sale_online", "sale_offline", "cs", "logistics", "mkt_hn"]
    
    for target in target_keys_tasks:
        for sender in senders:
            key = f"task_{target}_from_{sender}"
            if key not in data:
                data[key] = ""
    for target in target_keys_prep:
        for sender in senders:
            key = f"prep_{target}_from_{sender}"
            if key not in data:
                data[key] = ""
                
    # Map old fields to self-owned fields if self-owned is empty but old field has value
    mappings = {
        "task_online_info": "task_online_from_sale_online",
        "task_offline_info": "task_offline_from_sale_offline",
        "task_cs_info": "task_cs_from_cs",
        "task_logistics_info": "task_logistics_from_logistics",
        "task_mkt_hn_info": "task_mkt_hn_from_mkt_hn",
        "prep_logistics": "prep_logistics_from_logistics",
        "prep_sales_online": "prep_sales_online_from_sale_online",
        "prep_cs": "prep_cs_from_cs",
        "prep_sales_offline": "prep_sales_offline_from_sale_offline",
        "prep_mkt_hn": "prep_mkt_hn_from_mkt_hn"
    }
    
    for old_field, new_field in mappings.items():
        if old_field in data and data.get(old_field):
            if not data.get(new_field):
                data[new_field] = data[old_field]
                
    return data


def format_pdf_contributions(data, field_prefix, target_dept):
    senders = [
        ("Sale Online", "sale_online"),
        ("Sale Offline", "sale_offline"),
        ("C.S", "cs"),
        ("Logistics", "logistics"),
        ("Phuc MKT", "mkt_hn")
    ]
    parts = []
    
    display_target_dept = "Phuc MKT" if target_dept in ["MKT HN", "Phuc MKT"] else target_dept
    
    has_any_split_field = False
    for name, key in senders:
        val = data.get(f"{field_prefix}_from_{key}")
        if val and val.strip():
            has_any_split_field = True
            break
            
    if not has_any_split_field:
        legacy_field = f"{field_prefix}_info" if "task" in field_prefix else field_prefix
        legacy_val = data.get(legacy_field)
        if legacy_val and legacy_val.strip():
            if "task" in field_prefix:
                parts.append(f"<b>{display_target_dept} tự phối hợp:</b> {legacy_val.strip()}")
            else:
                parts.append(f"<b>{display_target_dept} tự chuẩn bị:</b> {legacy_val.strip()}")

    for name, key in senders:
        val = data.get(f"{field_prefix}_from_{key}")
        if val and val.strip():
            if name == display_target_dept:
                if "task" in field_prefix:
                    parts.append(f"<b>{name} tự phối hợp:</b> {val.strip()}")
                else:
                    parts.append(f"<b>{name} tự chuẩn bị:</b> {val.strip()}")
            else:
                parts.append(f"<b>{name} yêu cầu:</b> {val.strip()}")
                
    return "<br/>".join(parts) if parts else "—"


@app.route('/')
def index():
    config = load_config()
    today_str = datetime.now().strftime('%Y-%m-%d')
    report_file = os.path.join(REPORTS_DIR, f"report_{today_str}.json")
    
    if os.path.exists(report_file):
        try:
            with open(report_file, 'r', encoding='utf-8') as f:
                report_data = json.load(f)
            report_data = ensure_split_fields(report_data)
        except Exception:
            report_data = ensure_split_fields(load_report_data())
    else:
        report_data = get_default_report(today_str)
    return render_template('index.html', config=config, report_data=report_data)

@app.route('/settings')
def settings():
    config = load_config()
    return render_template('settings.html', config=config)

@app.route('/get_report', methods=['GET'])
def get_report():
    date_str = request.args.get('date')
    if not date_str:
        return jsonify({"status": "error", "message": "Ngay khong hop le!"}), 400
    
    date_str = os.path.basename(date_str)
    report_file = os.path.join(REPORTS_DIR, f"report_{date_str}.json")
    
    if os.path.exists(report_file):
        try:
            with open(report_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            data = ensure_split_fields(data)
            return jsonify({"status": "success", "data": data})
        except Exception as e:
            return jsonify({"status": "error", "message": f"Loi doc file: {str(e)}"}), 500
    else:
        try:
            latest_data = load_report_data()
            if latest_data.get('report_date') == date_str:
                latest_data = ensure_split_fields(latest_data)
                return jsonify({"status": "success", "data": latest_data})
        except Exception:
            pass
            
        default_data = get_default_report(date_str)
        return jsonify({"status": "success", "data": default_data})

@app.route('/save_report', methods=['POST'])
def save_report():
    data = request.json
    try:
        report_date = data.get('report_date')
        if not report_date:
            report_date = datetime.now().strftime('%Y-%m-%d')
            data['report_date'] = report_date
            
        report_date = os.path.basename(report_date)
        report_file = os.path.join(REPORTS_DIR, f"report_{report_date}.json")
        
        logged_in_dept = data.get('logged_in_dept')
        
        if os.path.exists(report_file):
            try:
                with open(report_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except Exception:
                existing_data = {}
        else:
            existing_data = {}
            
        if logged_in_dept and existing_data:
            # Build list of all allowed fields dynamically
            target_keys_tasks = ["online", "offline", "cs", "logistics", "mkt_hn"]
            target_keys_prep = ["logistics", "sales_online", "cs", "sales_offline", "mkt_hn"]
            senders = ["sale_online", "sale_offline", "cs", "logistics", "mkt_hn"]
            
            allowed_fields = [
                "report_date", "receiving_depts", "priority_issue", 
                "priority_impact", "priority_deadline", "check1", "check2", "check3"
            ]
            for target in target_keys_tasks:
                allowed_fields.append(f"task_{target}_info")
                for sender in senders:
                    allowed_fields.append(f"task_{target}_from_{sender}")
            for target in target_keys_prep:
                allowed_fields.append(f"prep_{target}")
                for sender in senders:
                    allowed_fields.append(f"prep_{target}_from_{sender}")
            
            # Update only allowed fields
            for field in allowed_fields:
                if field in data:
                    existing_data[field] = data[field]
            
            # Last updating department
            existing_data["department"] = logged_in_dept
            final_data = existing_data
        else:
            # First save or no department logged-in, save everything
            if logged_in_dept:
                data["department"] = logged_in_dept
            final_data = data
            
        # Save to historical report file
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=4, ensure_ascii=False)
            
        # Update latest_report.json for backward compatibility
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=4, ensure_ascii=False)
            
        # Sync system config
        if 'send_method' in data and 'report_time' in data:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                config = {}
            config['send_method'] = data['send_method']
            config['report_time'] = data['report_time']
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)

        return jsonify({"status": "success", "message": "Da luu bao cao thanh cong!"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Loi luu file: {str(e)}"})


@app.route('/send_test', methods=['POST'])
def send_test():
    try:
        ok, msg = job()
        status = "success" if ok else "error"
        return jsonify({"status": status, "message": msg})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Loi: {str(e)}"})

@app.route('/save_settings', methods=['POST'])
def save_settings():
    """Luu toan bo credentials tu trang Settings"""
    data = request.json
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            config = {}

        config['send_method'] = data.get('send_method', 'email')
        config['report_time'] = data.get('report_time', '08:10')

        # Email config
        if 'email_config' not in config:
            config['email_config'] = {}
        config['email_config']['sender_email'] = data.get('email_sender', '')
        config['email_config']['sender_password'] = data.get('email_password', '')
        raw_receivers = data.get('email_receivers', '')
        config['email_config']['receiver_emails'] = [
            e.strip() for e in raw_receivers.replace('\n', ',').split(',') if e.strip()
        ]

        # Webhook config
        if 'webhook_config' not in config:
            config['webhook_config'] = {}
        config['webhook_config']['webhook_url'] = data.get('webhook_url', '')
        config['webhook_config']['bot_name'] = data.get('webhook_bot_name', 'Daily Sync Bot')

        # Zalo config
        if 'zalo_config' not in config:
            config['zalo_config'] = {}
        config['zalo_config']['access_token'] = data.get('zalo_token', '')
        config['zalo_config']['group_id'] = data.get('zalo_group_id', '')

        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)

        return jsonify({"status": "success", "message": "Da luu cai dat thanh cong!"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Loi: {str(e)}"})

@app.route('/export_pdf', methods=['POST'])
def export_pdf():
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        data   = load_report_data()
        config = load_config()

        # Try to register a Unicode font (falls back gracefully)
        font_name = 'Helvetica'
        try:
            font_path = os.path.join(BASE_DIR, 'static', 'fonts', 'DejaVuSans.ttf')
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
                font_name = 'DejaVuSans'
        except Exception:
            pass

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                leftMargin=18*mm, rightMargin=18*mm,
                                topMargin=18*mm, bottomMargin=18*mm)

        PAGE_W = A4[0] - 36*mm
        COL1   = PAGE_W * 0.35
        COL2   = PAGE_W * 0.65

        NAVY   = colors.HexColor('#1a5276')
        RED    = colors.HexColor('#c0392b')
        BLUE   = colors.HexColor('#2980b9')
        LGRAY  = colors.HexColor('#ebedef')
        WHITE  = colors.white

        def h(txt, bg=NAVY, fg=WHITE, size=11):
            return Paragraph(f'<font color="{fg.hexval() if hasattr(fg,"hexval") else "#ffffff"}" size="{size}"><b>{txt}</b></font>',
                             ParagraphStyle('h', fontName=font_name, leading=14, leftPadding=6))

        def cell(txt, bold=False, size=9):
            style = f'<b>{txt}</b>' if bold else txt
            return Paragraph(style, ParagraphStyle('c', fontName=font_name, fontSize=size, leading=13, leftPadding=4, rightPadding=4))

        def section_table(title_text, rows_data, title_bg=NAVY):
            """rows_data = list of (label, value) tuples"""
            table_data = [[Paragraph(f'<font color="white"><b>{title_text}</b></font>',
                                     ParagraphStyle('t', fontName=font_name, fontSize=10, leading=14, leftPadding=6)),
                           '']]
            for label, val in rows_data:
                table_data.append([cell(label, bold=True, size=9), cell(str(val) if val else '—', size=9)])

            col_widths = [COL1, COL2]
            t = Table(table_data, colWidths=col_widths, repeatRows=0)
            style = TableStyle([
                ('SPAN',        (0,0),(1,0)),
                ('BACKGROUND',  (0,0),(1,0), title_bg),
                ('BACKGROUND',  (0,1),(0,-1), LGRAY),
                ('GRID',        (0,0),(-1,-1), 0.5, colors.HexColor('#dddddd')),
                ('VALIGN',      (0,0),(-1,-1), 'MIDDLE'),
                ('TOPPADDING',  (0,0),(-1,-1), 5),
                ('BOTTOMPADDING',(0,0),(-1,-1), 5),
            ])
            t.setStyle(style)
            return t

        # ---------- Dates ----------
        report_date = data.get('report_date', '')
        if report_date and '-' in report_date:
            try:
                report_date = datetime.strptime(report_date, '%Y-%m-%d').strftime('%d/%m/%Y')
            except Exception:
                pass

        rt = config.get('report_time', '08:10')

        story = []

        # Title
        story.append(Paragraph(
            f'<font color="{NAVY.hexval()}"><b>BAO CAO DAILY – PHOI HOP LIEN BO PHAN</b></font>',
            ParagraphStyle('title', fontName=font_name, fontSize=14, leading=20, alignment=1)))
        story.append(Paragraph(
            f'<font color="grey">DAILY SYNC REPORT &nbsp;|&nbsp; Gui luc {rt} sang</font>',
            ParagraphStyle('sub', fontName=font_name, fontSize=9, leading=13, alignment=1)))
        story.append(Spacer(1, 6*mm))

        # Thong tin chung
        story.append(section_table('THONG TIN CHUNG / GENERAL INFORMATION', [
            ('Ngay bao cao',          report_date),
            ('Bo phan tiep nhan',     data.get('receiving_depts', '')),
            ('Bo phan bao cao',       data.get('department', '')),
        ]))
        story.append(Spacer(1, 4*mm))

        # Uu tien
        story.append(section_table('VAN DE UU TIEN SO 1 HOM NAY / TOP PRIORITY ISSUE', [
            ('Mo ta van de',          data.get('priority_issue', '')),
            ('Tac dong / muc do',     data.get('priority_impact', '')),
            ('Deadline xu ly',        data.get('priority_deadline', '')),
        ], title_bg=RED))
        story.append(Spacer(1, 4*mm))

        # Nhiem vu lien ket
        rec_list  = data.get('receiving_depts', '')
        task_rows = []
        dept_map  = [
            ('Sale Online',  'task_online'),
            ('Sale Offline', 'task_offline'),
            ('C.S',          'task_cs'),
            ('Logistics',    'task_logistics'),
            ('MKT HN',       'task_mkt_hn'),
        ]
        for dept_key, prefix in dept_map:
            if dept_key in rec_list:
                task_rows.append((dept_key, format_pdf_contributions(data, prefix, dept_key)))

        if task_rows:
            story.append(section_table('NHIEM VU LIEN KET GIUA CAC BO PHAN / CROSS-DEPT TASKS', task_rows, title_bg=BLUE))
        else:
            story.append(section_table('NHIEM VU LIEN KET GIUA CAC BO PHAN / CROSS-DEPT TASKS',
                                       [('(Chua co nhiem vu lien ket duoc chon)', '')], title_bg=BLUE))
        story.append(Spacer(1, 4*mm))

        # Chuan bi ngay mai
        story.append(section_table('CHUAN BI TRUOC CHO NGAY MAI / PREPARATION FOR TOMORROW', [
            ('Logistics',   format_pdf_contributions(data, 'prep_logistics', 'Logistics')),
            ('Sale Online', format_pdf_contributions(data, 'prep_sales_online', 'Sale Online')),
            ('C.S',         format_pdf_contributions(data, 'prep_cs', 'C.S')),
            ('Sale Offline',format_pdf_contributions(data, 'prep_sales_offline', 'Sale Offline')),
            ('MKT HN',      format_pdf_contributions(data, 'prep_mkt_hn', 'MKT HN')),
        ]))
        story.append(Spacer(1, 4*mm))

        # Checklist
        chk = lambda v: '[x]' if v else '[ ]'
        story.append(section_table('CHECKLIST 10 GIAY / 10-SECOND CHECKLIST', [
            (chk(data.get('check1')) + '  Da nam van de uu tien so 1',    ''),
            (chk(data.get('check2')) + '  Da xac nhan nhiem vu lien ket', ''),
            (chk(data.get('check3')) + '  Da nam deadline',               ''),
        ]))

        doc.build(story)
        buf.seek(0)

        filename = f"Daily_Report_{datetime.now().strftime('%d-%m-%Y')}.pdf"
        return send_file(buf, mimetype='application/pdf',
                         as_attachment=True, download_name=filename)

    except Exception as e:
        import traceback
        print(f"[PDF ERROR] {traceback.format_exc()}")
        return jsonify({"status": "error", "message": f"Loi PDF: {str(e)}"}), 500


# Start background scheduler thread
threading.Thread(target=run_scheduler, daemon=True).start()

if __name__ == '__main__':
    print("Software started. Open http://127.0.0.1:5000 in your browser.")
    # Chay Flask o port 5000 co dinh cho ban local
    app.run(host='127.0.0.1', port=5000, debug=False)
