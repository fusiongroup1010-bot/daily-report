import json
import os
import requests
from datetime import datetime
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

DATA_FILE = 'latest_report.json'
CONFIG_FILE = 'config.json'

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {"send_method": "email", "report_time": "08:10"}
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_report_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def format_plain_contributions(data, field_prefix, target_dept):
    senders = [
        ("Sale Online", "sale_online"),
        ("Sale Offline", "sale_offline"),
        ("C.S", "cs"),
        ("Logistics", "logistics"),
        ("MKT", "mkt_hn")
    ]
    parts = []
    display_target_dept = "MKT" if target_dept in ["MKT HN", "Phuc MKT", "MKT"] else target_dept
    
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
                parts.append(f"  - {display_target_dept} tự phối hợp: {legacy_val.strip()}")
            else:
                parts.append(f"  - {display_target_dept} tự chuẩn bị: {legacy_val.strip()}")

    for name, key in senders:
        val = data.get(f"{field_prefix}_from_{key}")
        if val and val.strip():
            if name == display_target_dept:
                if "task" in field_prefix:
                    parts.append(f"  - {name} tự phối hợp: {val.strip()}")
                else:
                    parts.append(f"  - {name} tự chuẩn bị: {val.strip()}")
            else:
                parts.append(f"  - {name} yêu cầu: {val.strip()}")
                
    return "\n".join(parts) if parts else "  - —"


def format_html_contributions(data, field_prefix, target_dept):
    senders = [
        ("Sale Online", "sale_online"),
        ("Sale Offline", "sale_offline"),
        ("C.S", "cs"),
        ("Logistics", "logistics"),
        ("MKT", "mkt_hn")
    ]
    parts = []
    display_target_dept = "MKT" if target_dept in ["MKT HN", "Phuc MKT", "MKT"] else target_dept
    
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
            esc_val = str(legacy_val).replace('\n', '<br>').strip()
            if "task" in field_prefix:
                parts.append(f"• <b>{display_target_dept} tự phối hợp:</b> {esc_val}")
            else:
                parts.append(f"• <b>{display_target_dept} tự chuẩn bị:</b> {esc_val}")

    for name, key in senders:
        val = data.get(f"{field_prefix}_from_{key}")
        if val and val.strip():
            esc_val = str(val).replace('\n', '<br>').strip()
            if name == display_target_dept:
                if "task" in field_prefix:
                    parts.append(f"• <b>{name} tự phối hợp:</b> {esc_val}")
                else:
                    parts.append(f"• <b>{name} tự chuẩn bị:</b> {esc_val}")
            else:
                parts.append(f"• <b>{name} yêu cầu:</b> {esc_val}")
                
    return "<br>".join(parts) if parts else "—"


def build_plain_report(data, config):
    if not data: return "Chưa có dữ liệu báo cáo."
    dept = data.get('department', 'N/A')
    if dept in ['MKT HN', 'Phuc MKT', 'MKT']:
        dept = 'MKT'
    report_date = data.get('report_date','')
    if report_date and '-' in report_date:
        try: report_date = datetime.strptime(report_date, '%Y-%m-%d').strftime('%d/%m/%Y')
        except: pass
    rt = config.get('report_time', '08:10')
    
    rec_depts = data.get('receiving_depts', '')
    task_parts = []
    if 'Sale Online' in rec_depts:
        task_parts.append(f"  Sale Online:\n{format_plain_contributions(data, 'task_online', 'Sale Online')}")
    if 'Sale Offline' in rec_depts:
        task_parts.append(f"  Sale Offline:\n{format_plain_contributions(data, 'task_offline', 'Sale Offline')}")
    if 'C.S' in rec_depts:
        task_parts.append(f"  C.S:\n{format_plain_contributions(data, 'task_cs', 'C.S')}")
    if 'Logistics' in rec_depts:
        task_parts.append(f"  Logistics:\n{format_plain_contributions(data, 'task_logistics', 'Logistics')}")
    if any(alias in rec_depts for alias in ['MKT', 'MKT HN', 'Phuc MKT']):
        task_parts.append(f"  MKT:\n{format_plain_contributions(data, 'task_mkt_hn', 'MKT')}")
        
    tasks_str = "\n".join(task_parts) if task_parts else "  (Không có nhiệm vụ liên kết)"
    
    prep_parts = []
    if 'Sale Online' in rec_depts:
        prep_parts.append(f"  Sale Online:\n{format_plain_contributions(data, 'prep_sales_online', 'Sale Online')}")
    if 'Sale Offline' in rec_depts:
        prep_parts.append(f"  Sale Offline:\n{format_plain_contributions(data, 'prep_sales_offline', 'Sale Offline')}")
    if 'C.S' in rec_depts:
        prep_parts.append(f"  C.S:\n{format_plain_contributions(data, 'prep_cs', 'C.S')}")
    if 'Logistics' in rec_depts:
        prep_parts.append(f"  Logistics:\n{format_plain_contributions(data, 'prep_logistics', 'Logistics')}")
    if any(alias in rec_depts for alias in ['MKT', 'MKT HN', 'Phuc MKT']):
        prep_parts.append(f"  MKT:\n{format_plain_contributions(data, 'prep_mkt_hn', 'MKT')}")

    prep_str = "\n".join(prep_parts) if prep_parts else "  (Không có chuẩn bị cho ngày mai)"

    lines = [
        f"BAO CAO DAILY – PHOI HOP LIEN BO PHAN | {dept}",
        f"Gui luc {rt} sang",
        "=" * 50,
        f"Ngay: {report_date} | BP Tiep nhan: {rec_depts or 'All'}",
        "",
        "VAN DE UU TIEN SO 1:",
        f"  Mo ta: {data.get('priority_issue','')}",
        f"  Tac dong: {data.get('priority_impact','')}",
        f"  Deadline: {data.get('priority_deadline','')}",
        "",
        "NHIEM VU LIEN KET:",
        tasks_str,
        "",
        "CHUAN BI NGAY MAI:",
        prep_str,
    ]
    return "\n".join(lines)


def build_html_report(data, config):
    dept = data.get('department', 'N/A')
    if dept in ['MKT HN', 'Phuc MKT', 'MKT']:
        dept = 'MKT'
    rt = config.get('report_time', '08:10')
    S = {
        'body': 'margin:0; padding:0; background-color:#f4f7f9; font-family:"Segoe UI",Helvetica,Arial,sans-serif;',
        'wrap': 'max-width:700px; margin:20px auto; background-color:#ffffff; border:1px solid #dce1e5; border-radius:8px; overflow:hidden;',
        'header': 'background:#1a5276; color:#ffffff; padding:25px; text-align:center;',
        'sect': 'background-color:#f8f9fa; border-left:4px solid #1a5276; padding:10px 15px; margin:25px 0 12px; font-weight:bold; font-size:14px; color:#1a5276;',
        'lbl': 'width:28%; background-color:#f8fafc; padding:12px 14px; font-weight:bold; font-size:12px; border-right:1px solid #e2e8f0; color:#475569; text-transform:uppercase; letter-spacing:0.5px; vertical-align:middle;',
        'val': 'width:72%; padding:12px 16px; font-size:13px; color:#334155; line-height:1.5; vertical-align:middle;',
    }
    def section(vi, en): return f'<div style="{S["sect"]}">{vi} / {en}</div>'
    def row(vi, val):
        return f'<tr style="border-top:1px solid #e2e8f0;"><td style="{S["lbl"]}">{vi}</td><td style="{S["val"]}">{val}</td></tr>'

    task_blocks = ''
    prep_blocks = ''
    rec_list = data.get('receiving_depts', '')
    
    depts = [
        ('Sale Online', '🛒 Sale Online', 'task_online', 'prep_sales_online', '#5c6bc0', ['Sale Online']),
        ('Sale Offline', '🏬 Sale Offline', 'task_offline', 'prep_sales_offline', '#00897b', ['Sale Offline']),
        ('C.S', '💬 C.S', 'task_cs', 'prep_cs', '#fb8c00', ['C.S']),
        ('Logistics', '📦 Logistics', 'task_logistics', 'prep_logistics', '#1e88e5', ['Logistics']),
        ('MKT', '📢 MKT', 'task_mkt_hn', 'prep_mkt_hn', '#ab47bc', ['MKT', 'MKT HN', 'Phuc MKT']),
    ]
    
    for key, title, task_prefix, prep_prefix, color, aliases in depts:
        if any(alias in rec_list for alias in aliases):
            # Tasks
            task_content = format_html_contributions(data, task_prefix, key)
            task_blocks += f"""
            <div style="margin:0 0 16px; border:1.5px solid {color}40; border-radius:8px; overflow:hidden; box-shadow:0 2px 5px rgba(0,0,0,0.02);">
                <div style="background:{color}; color:#ffffff; padding:10px 14px; font-weight:bold; font-size:14px;">{title}</div>
                <table width="100%" style="border-collapse:collapse;">{row("Nhiệm vụ phối hợp", task_content)}</table>
            </div>
            """
            
            # Prep
            prep_content = format_html_contributions(data, prep_prefix, key)
            prep_blocks += f"""
            <div style="margin:0 0 16px; border:1.5px solid {color}40; border-radius:8px; overflow:hidden; box-shadow:0 2px 5px rgba(0,0,0,0.02);">
                <div style="background:{color}; color:#ffffff; padding:10px 14px; font-weight:bold; font-size:14px;">{title} (Chuẩn bị ngày mai)</div>
                <table width="100%" style="border-collapse:collapse;">{row("Nhiệm vụ chuẩn bị", prep_content)}</table>
            </div>
            """

    if not task_blocks:
        task_blocks = '<div style="padding:15px; border:1px dashed #cbd5e1; border-radius:8px; color:#64748b; text-align:center; font-style:italic;">(Chưa có nhiệm vụ liên kết được chọn)</div>'
    if not prep_blocks:
        prep_blocks = '<div style="padding:15px; border:1px dashed #cbd5e1; border-radius:8px; color:#64748b; text-align:center; font-style:italic;">(Chưa có chuẩn bị cho ngày mai được chọn)</div>'

    report_date = data.get('report_date','')
    if report_date and '-' in report_date:
        try: report_date = datetime.strptime(report_date, '%Y-%m-%d').strftime('%d/%m/%Y')
        except: pass

    html = f"""<!DOCTYPE html><html><body style="{S['body']}"><div style="{S['wrap']}"><div style="{S['header']}"><h1 style="margin:0 0 10px; font-size:24px; font-weight:800; text-transform:uppercase; letter-spacing:1px;">Báo Cáo Daily</h1><p style="margin:0; font-size:14px; opacity:0.9;">⏰ Gửi lúc {rt} sáng</p></div><div style="padding:20px;">{section('THÔNG TIN CHUNG', 'GENERAL INFO')}<table width="100%" style="border-collapse:collapse; border:1px solid #e2e8f0; border-radius:8px; overflow:hidden;">{row('Ngày báo cáo', report_date)}{row('Bộ phận tiếp nhận', data.get('receiving_depts',''))}{row('Bộ phận báo cáo', dept)}</table>{section('NHIỆM VỤ LIÊN KẾT', 'CROSS-DEPT TASKS')}{task_blocks}{section('CHUẨN BỊ TRƯỚC CHO NGÀY MAI', 'PREPARATION FOR TOMORROW')}{prep_blocks}</div></div></body></html>"""
    return html


def send_email(html_content, subject, config):
    try:
        msg = MIMEMultipart(); msg['Subject'] = subject; msg['From'] = config.get('email_sender'); msg['To'] = config.get('email_receiver')
        msg.attach(MIMEText(html_content, 'html'))
        with smtplib.SMTP(config.get('smtp_server'), int(config.get('smtp_port', 587))) as server:
            server.starttls(); server.login(config.get('email_sender'), config.get('email_password')); server.send_message(msg)
        return True
    except: return False


def send_to_webhook(data, config):
    url = config.get('webhook_url')
    if not url: return False
    dept = data.get('department','')
    if dept in ['MKT HN', 'Phuc MKT', 'MKT']:
        dept = 'MKT'
    payload = {"text": f"🔔 *BÁO CÁO DAILY - {dept}*\n" + build_plain_report(data, config)}
    try: requests.post(url, json=payload, timeout=10); return True
    except: return False


def send_to_zalo(data, config): return True


def job():
    data = load_report_data(); config = load_config()
    if not data: return
    method = config.get('send_method', 'email')
    dept = data.get('department','')
    if dept in ['MKT HN', 'Phuc MKT', 'MKT']:
        dept = 'MKT'
    subject = f"Báo cáo Daily Sync - {dept} - {datetime.now().strftime('%d/%m/%Y')}"
    if method == 'email': send_email(build_html_report(data, config), subject, config)
    elif method == 'webhook': send_to_webhook(data, config)
    elif method == 'zalo': send_to_zalo(data, config)
