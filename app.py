import os
import random
import requests
import time
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, render_template
from geopy.distance import geodesic
from openpyxl import Workbook, load_workbook

app = Flask(__name__, static_folder='static', template_folder='templates')

# ================== ការកំណត់ (CONFIG) ==================
BOT_TOKEN = "8501341500:AAFvNtQIAzELusb_5u6EPgSjGMpBcv0avpo"
CHAT_ID = 8091370821

SHOP_LAT = 11.519929392013168
SHOP_LON = 104.9153656342366
MAX_DISTANCE = 2000 
EXCEL_FILE = "orders.xlsx"

# =================== APP INITIALIZATION ===================
# បង្កើត File Excel ភ្លាមៗពេល Start (មិនប្រើ Threading)
if not os.path.exists(EXCEL_FILE):
    print("📊 Creating Excel file...")
    wb = Workbook()
    ws = wb.active
    ws.append(["Order ID", "Queue Number", "Time", "Items", "Total", "Distance(m)", "Location"])
    wb.save(EXCEL_FILE)
    print("✅ Excel file created")

# ================== HEALTH CHECK ==================
@app.route('/health')
def health():
    return jsonify({"status": "ready"}), 200

# ================== MAIN ROUTES =====================

@app.route("/")
def index():
    # ត្រឡប់ទៅកាន់ទំព័រដើមភ្លាមៗ មិនឆ្លងកាត់ Loading ទេ
    return send_from_directory('.', 'testweb.html')

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

@app.route("/order", methods=["POST"])
def order():
    try:
        data = request.json
        queue_number = data.get("queueNumber")
        items = data.get("items")
        total = data.get("total")
        lat = data.get("location", {}).get("lat") if data.get("location") else None
        lon = data.get("location", {}).get("lng") if data.get("location") else None

        distance = 0
        distance_text = "មិនមាន GPS"
        map_link = "N/A"
        
        if lat and lon:
            user_coords = (lat, lon)
            shop_coords = (SHOP_LAT, SHOP_LON)
            distance = geodesic(shop_coords, user_coords).meters
            distance_text = f"{round(distance, 2)} ម៉ែត្រ"
            map_link = f"https://www.google.com/maps?q={lat},{lon}"
            
            if distance > MAX_DISTANCE:
                return jsonify({"error": f"អ្នកនៅឆ្ងាយពីហាងពេក ({round(distance)}m)"}), 403

        order_id = f"ORD{random.randint(1000, 9999)}"
        time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        items_detail = ""
        items_for_excel = ""

        for item in items:
            name = item.get('name_km', item.get('name_en', 'Unknown'))
            qty = item.get('qty', 1)
            price = item.get('price', 0)
            subtotal = item.get('subtotal', price * qty)
            
            options_text = ""
            if item.get('options'):
                opts = []
                if item['options'].get('sugar'): opts.append(f"ស្ករ: {item['options']['sugar']}")
                if item['options'].get('ice'): opts.append(f"ទឹកកក: {item['options']['ice']}")
                if item['options'].get('note'): opts.append(f"ចំណាំ: {item['options']['note']}")
                if opts: options_text = f" ({', '.join(opts)})"
            
            items_detail += f"• {name} x{qty}{options_text} = ${subtotal:.2f}\n"
            items_for_excel += f"{name}(x{qty}){options_text}, "

        # Telegram Message
        telegram_msg = (
            f"🛎 **ការកុម្ម៉ង់ថ្មី!**\n\n"
            f"🎫 លេខរង់ចាំ: **{queue_number}**\n"
            f"🆔 លេខកុម្ម៉ង់: {order_id}\n"
            f"⏰ ម៉ោង: {time_now}\n\n"
            f"📦 មុខម្ហូប:\n{items_detail}\n"
            f"💰 **សរុប: ${total:.2f}**\n\n"
            f"📍 ចម្ងាយ: {distance_text}\n"
        )
        
        if lat and lon:
            telegram_msg += f"🗺 ទីតាំងភ្ញៀវ: [ចុចមើលផែនទី]({map_link})"

        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": telegram_msg, "parse_mode": "Markdown"}
        )

        # Excel Log
        wb = load_workbook(EXCEL_FILE)
        ws = wb.active
        location_str = f"{lat},{lon}" if lat and lon else "N/A"
        ws.append([order_id, queue_number, time_now, items_for_excel.rstrip(', '), total, round(distance, 2), location_str])
        wb.save(EXCEL_FILE)

        return jsonify({
            "success": True, 
            "order_id": order_id,
            "queue_number": queue_number,
            "message": f"កុម្ម៉ង់បានជោគជ័យ! លេខរង់ចាំ: {queue_number}"
        })

    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"error": "មានបញ្ហាបច្ចេកទេសនៅលើ Server"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)