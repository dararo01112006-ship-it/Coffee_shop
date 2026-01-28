import os
import random
import requests
import threading
import time
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, render_template
from geopy.distance import geodesic
from openpyxl import Workbook, load_workbook

# កំណត់ Folder សម្រាប់ Static files (រូបភាព)
app = Flask(__name__, static_folder='static', template_folder='templates')

# ================== ការកំណត់ (CONFIG) ==================
BOT_TOKEN = "8501341500:AAFvNtQIAzELusb_5u6EPgSjGMpBcv0avpo"
CHAT_ID = 8091370821

# ទីតាំងហាងសម្រាប់ផ្ទៀងផ្ទាត់ (Latitude, Longitude)
SHOP_LAT = 11.519929392013168
SHOP_LON = 104.9153656342366
MAX_DISTANCE = 2000  # អនុញ្ញាតក្នុងរង្វង់ ២ គីឡូម៉ែត្រ
EXCEL_FILE = "orders.xlsx"

# =================== APP INITIALIZATION ===================
app_ready = False

def initialize_app():
    """ដំណើរការ initialization ទាំងអស់"""
    global app_ready
    
    print("🚀 Starting application initialization...")
    
    # បង្កើត File Excel បើមិនទាន់មាន
    if not os.path.exists(EXCEL_FILE):
        print("📊 Creating Excel file...")
        wb = Workbook()
        ws = wb.active
        ws.append(["Order ID", "Queue Number", "Time", "Items", "Total", "Distance(m)", "Location"])
        wb.save(EXCEL_FILE)
        print("✅ Excel file created")
    
    # Simulate initialization time
    time.sleep(2)
    
    app_ready = True
    print("✅ Application ready to serve requests!")

# ចាប់ផ្តើម initialization នៅ background
threading.Thread(target=initialize_app, daemon=True).start()

# ================== HEALTH CHECK ==================
@app.route('/health')
def health():
    """Health check endpoint សម្រាប់ Render"""
    if app_ready:
        return jsonify({"status": "ready"}), 200
    else:
        return jsonify({"status": "loading"}), 503

# ================== MAIN ROUTES =====================

@app.route("/")
def index():
    """បង្ហាញ loading page ឬ main page"""
    if not app_ready:
        return render_template('loading.html')
    return send_from_directory('.', 'testweb.html')

# បង្ហាញរូបភាពពី folder static
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

@app.route("/order", methods=["POST"])
def order():
    """ទទួលកុម្ម៉ង់ពីភ្ញៀវ"""
    
    # ពិនិត្យថា app ready ហើយឬនៅ
    if not app_ready:
        return jsonify({"error": "ប្រព័ន្ធកំពុងដំណើរការ សូមរង់ចាំបន្តិច"}), 503
    
    try:
        data = request.json
        queue_number = data.get("queueNumber")
        items = data.get("items")
        total = data.get("total")
        lat = data.get("location", {}).get("lat") if data.get("location") else None
        lon = data.get("location", {}).get("lng") if data.get("location") else None

        # គណនាចម្ងាយ (optional - ប្រសិនមាន GPS)
        distance = 0
        distance_text = "មិនមាន GPS"
        map_link = "N/A"
        
        if lat and lon:
            user_coords = (lat, lon)
            shop_coords = (SHOP_LAT, SHOP_LON)
            distance = geodesic(shop_coords, user_coords).meters
            distance_text = f"{round(distance, 2)} ម៉ែត្រ"
            map_link = f"https://www.google.com/maps?q={lat},{lon}"
            
            # ពិនិត្យចម្ងាយ (optional - អាចលុបបើមិនចង់បាន)
            if distance > MAX_DISTANCE:
                return jsonify({"error": f"អ្នកនៅឆ្ងាយពីហាងពេក ({round(distance)}m)"}), 403

        # រៀបចំទិន្នន័យកុម្ម៉ង់
        order_id = f"ORD{random.randint(1000, 9999)}"
        time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        items_detail = ""
        items_for_excel = ""

        for item in items:
            name = item.get('name_km', item.get('name_en', 'Unknown'))
            qty = item.get('qty', 1)
            price = item.get('price', 0)
            subtotal = item.get('subtotal', price * qty)
            
            # បង្កើតសេចក្តីលម្អិតនៃ options
            options_text = ""
            if item.get('options'):
                opts = []
                if item['options'].get('sugar'):
                    opts.append(f"ស្ករ: {item['options']['sugar']}")
                if item['options'].get('ice'):
                    opts.append(f"ទឹកកក: {item['options']['ice']}")
                if item['options'].get('note'):
                    opts.append(f"កំណត់ចំណាំ: {item['options']['note']}")
                if opts:
                    options_text = f" ({', '.join(opts)})"
            
            items_detail += f"• {name} x{qty}{options_text} = ${subtotal:.2f}\n"
            items_for_excel += f"{name}(x{qty}){options_text}, "

        # ផ្ញើទៅ Telegram
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

        # រក្សាទុកក្នុង Excel
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
        import traceback
        traceback.print_exc()
        return jsonify({"error": "មានបញ្ហាបច្ចេកទេសនៅលើ Server"}), 500

if __name__ == "__main__":
    # ប្រើ Port ដែល Render កំណត់ឱ្យ ឬ Port 5000 ជា Default
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)