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

def build_plain_report(data, config):
    if not data: return "Chưa có dữ liệu báo cáo."
    dept = data.get('department', 'N/A')
    report_date = data.get('report_date','')
    if report_date and '-' in report_date:
        try: report_date = datetime.strptime(report_date, '%Y-%m-%d').strftime('%d/%m/%Y')
        except: pass
    rt = config.get('report_time', '08:10')
    lines = [
        f"BAO CAO DAILY – PHOI HOP LIEN BO PHAN | {dept}",
        f"Gui luc {rt} sang",
        "=" * 50,
        f"Ngay: {report_date} | BP Tiep nhan: {data.get('receiving_depts','All')}",
        "",
        "VAN DE UU TIEN SO 1:",
        f"  Mo ta: {data.get('priority_issue','')}",
        f"  Tac dong: {data.get('priority_impact','')}",
        f"  Deadline: {data.get('priority_deadline','')}",
        "",
        "NHIEM VU LIEN KET:",
        f"  Sale Online: {data.get('task_online_info','')}" if 'Sale Online' in data.get('receiving_depts','') else "",
        f"  Sale Offline: {data.get('task_offline_info','')}" if 'Sale Offline' in data.get('receiving_depts','') else "",
        f"  C.S: {data.get('task_cs_info','')}" if 'C.S' in data.get('receiving_depts','') else "",
        f"  Logistics: {data.get('task_logistics_info','')}" if 'Logistics' in data.get('receiving_depts','') else "",
        "",
        "CHUAN BI NGAY MAI:",
        f"  Logistics: {data.get('prep_logistics','')}",
        f"  Sale Online: {data.get('prep_sales_online','')}",
        f"  C.S: {data.get('prep_cs','')}",
        f"  Sale Offline: {data.get('prep_sales_offline','')}",
    ]
    return "\n".join(lines)

def build_html_report(data, config):
    dept = data.get('department', 'N/A')
    rt = config.get('report_time', '08:10')
    S = {
        'body': 'margin:0; padding:0; background-color:#f4f7f9; font-family:"Segoe UI",Helvetica,Arial,sans-serif;',
        'wrap': 'max-width:700px; margin:20px auto; background-color:#ffffff; border:1px solid #dce1e5; border-radius:8px; overflow:hidden;',
        'header': 'background:#1a5276; color:#ffffff; padding:25px; text-align:center;',
        'sect': 'background-color:#f8f9fa; border-left:4px solid #1a5276; padding:10px 15px; margin:20px 0 10px; font-weight:bold; font-size:14px; color:#1a5276;',
        'lbl': 'width:30%; background-color:#f2f4f6; padding:10px 12px; font-weight:bold; font-size:12px; border-right:1px solid #ddd;',
        'val': 'width:70%; padding:10px 15px; font-size:13px; color:#333;',
    }
    def section(vi, en): return f'<div style="{S["sect"]}">{vi} / {en}</div>'
    def row(vi, val):
        val_display = str(val).replace('\n', '<br>') if val else '—'
        return f'<tr style="border-top:1px solid #ddd;"><td style="{S["lbl"]}">{vi}</td><td style="{S["val"]}">{val_display}</td></tr>'

    task_blocks = ''
    rec_list = data.get('receiving_depts', '')
    depts = [('Sale Online','🛒 Sale Online','task_online_info'), ('Sale Offline','🏬 Sale Offline','task_offline_info'), ('C.S','💬 C.S','task_cs_info'), ('Logistics','📦 Logistics','task_logistics_info')]
    for key, title, field in depts:
        if key in rec_list:
            task_blocks += f'<div style="margin:0 0 12px; border:1px solid #ddd;"><div style="background:#2980b9; color:#fff; padding:8px 14px; font-weight:bold;">{title}</div><table width="100%" style="border-collapse:collapse;">{row("Nhiệm vụ cần phối hợp", data.get(field,""))}</table></div>'

    report_date = data.get('report_date','')
    if report_date and '-' in report_date:
        try: report_date = datetime.strptime(report_date, '%Y-%m-%d').strftime('%d/%m/%Y')
        except: pass

    html = f"""<!DOCTYPE html><html><body style="{S['body']}"><div style="{S['wrap']}"><div style="{S['header']}"><h1>Báo Cáo Daily</h1><p>⏰ Gửi lúc {rt} sáng</p></div><div style="padding:16px;">{section('THÔNG TIN CHUNG', 'GENERAL INFO')}<table width="100%" style="border-collapse:collapse; border:1px solid #ddd;">{row('Ngày báo cáo', report_date)}{row('Bộ phận tiếp nhận', data.get('receiving_depts',''))}{row('Bộ phận báo cáo', dept)}</table>{section('NHIỆM VỤ LIÊN KẾT', 'CROSS-DEPT TASKS')}{task_blocks}{section('CHUẨN BỊ TRƯỚC CHO NGÀY MAI', 'PREPARATION')}<table width="100%" style="border-collapse:collapse; border:1px solid #ddd;">{row('Logistics', data.get('prep_logistics',''))}{row('Sale Online', data.get('prep_sales_online',''))}{row('C.S', data.get('prep_cs',''))}{row('Sale Offline', data.get('prep_sales_offline',''))}</table></div></div></body></html>"""
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
    payload = {"text": f"🔔 *BÁO CÁO DAILY - {data.get('department','')}*\n" + build_plain_report(data, config)}
    try: requests.post(url, json=payload, timeout=10); return True
    except: return False

def send_to_zalo(data, config): return True

def job():
    data = load_report_data(); config = load_config()
    if not data: return
    method = config.get('send_method', 'email')
    subject = f"Báo cáo Daily Sync - {data.get('department','')} - {datetime.now().strftime('%d/%m/%Y')}"
    if method == 'email': send_email(build_html_report(data, config), subject, config)
    elif method == 'webhook': send_to_webhook(data, config)
    elif method == 'zalo': send_to_zalo(data, config)
