import os
import random
import requests
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from geopy.distance import geodesic
from openpyxl import Workbook, load_workbook

app = Flask(__name__, static_folder='static', template_folder='templates')

# ================== ការកំណត់ (CONFIG) ==================
BOT_TOKEN = "8501341500:AAFvNtQIAzELusb_5u6EPgSjGMpBcv0avpo"
CHAT_ID = 8091370821
 
SHOP_LAT = 11.52890104500027
SHOP_LON = 104.9153656342366
MAX_DISTANCE = 2000  # ម៉ែត្រ
EXCEL_FILE = "orders.xlsx"

# =================== APP INITIALIZATION ===================
def init_excel():
    if not os.path.exists(EXCEL_FILE):
        wb = Workbook()
        ws = wb.active
        ws.title = "Orders"
        ws.append(["Order ID", "Queue Number", "Time", "Items", "Total ($)", "Distance (m)", "Map Link"])
        wb.save(EXCEL_FILE)
        print("✅ Excel file initialized.")

init_excel()

# ================== ROUTES =====================

@app.route("/")
def index():
    return send_from_directory('.', 'testweb.html')

@app.route("/order", methods=["POST"])
def order():
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "មិនមានទិន្នន័យបញ្ជូនមក"}), 400

        # ទាញយកទិន្នន័យ
        queue_number = data.get("queueNumber", "N/A")
        items = data.get("items", [])
        total = data.get("total", 0)
        location = data.get("location", {})
        lat = location.get("lat")
        lon = location.get("lng")

        # 1. បង្កើតព័ត៌មានបឋម
        order_id = f"ORD{random.randint(1000, 9999)}"
        time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 2. ពិនិត្យចម្ងាយ (Distance Logic)
        distance_m = 0
        distance_text = "មិនមាន GPS"
        map_link = "N/A"

        if lat and lon:
            user_coords = (lat, lon)
            shop_coords = (SHOP_LAT, SHOP_LON)
            distance_m = geodesic(shop_coords, user_coords).meters
            
            # បើចម្ងាយលើស ២០០០ ម៉ែត្រ គឺបដិសេធភ្លាម (មិនផ្ញើ Telegram)
            if distance_m > MAX_DISTANCE:
                return jsonify({
                    "success": False, 
                    "error": f"ការកុម្ម៉ង់ត្រូវបានបដិសេធ! អ្នកនៅឆ្ងាយពីហាងពេក ({round(distance_m)} ម៉ែត្រ)"
                }), 403
            
            distance_text = f"{round(distance_m, 2)} ម៉ែត្រ"
            map_link = f"https://www.google.com/maps?q={lat},{lon}"

        # 3. រៀបចំបញ្ជីមុខម្ហូប (Item Details)
        if not items:
            return jsonify({"success": False, "error": "សូមជ្រើសរើសមុខម្ហូបមុននឹងបញ្ជារទិញ"}), 400

        items_detail_msg = ""  # សម្រាប់ Telegram
        items_for_excel = ""   # សម្រាប់ Excel
        
        for item in items:
            name = item.get('name_km') or item.get('name_en') or 'Unknown'
            qty = item.get('qty', 1)
            price = item.get('price', 0)
            subtotal = price * qty
            
            # ជម្រើសបន្ថែម (Options)
            opts = []
            if item.get('options'):
                opt = item['options']
                if opt.get('sugar'): opts.append(f"ស្ករ:{opt['sugar']}")
                if opt.get('ice'): opts.append(f"ទឹកកក:{opt['ice']}")
                if opt.get('note'): opts.append(f"ចំណាំ:{opt['note']}")
            
            opt_str = f" ({', '.join(opts)})" if opts else ""
            
            items_detail_msg += f"• {name} x{qty}{opt_str} = ${subtotal:.2f}\n"
            items_for_excel += f"{name}(x{qty}){opt_str}, "

        # 4. រៀបចំសារផ្ញើទៅ Telegram
        telegram_msg = (
            f"🔔 **មានការកុម្ម៉ង់ថ្មី!**\n\n"
            f"🎫 លេខរង់ចាំ: `{queue_number}`\n"
            f"🆔 លេខកុម្ម៉ង់: `{order_id}`\n"
            f"⏰ ម៉ោង: {time_now}\n"
            f"--------------------------\n"
            f"📦 **មុខម្ហូប:**\n{items_detail_msg}\n"
            f"💰 **សរុប: ${total:.2f}**\n"
            f"--------------------------\n"
            f"📍 ចម្ងាយ: {distance_text}\n"
        )
        if lat and lon:
            telegram_msg += f"🔗 ទីតាំងភ្ញៀវ: [មើលលើផែនទី]({map_link})"

        # 5. ផ្ញើទៅ Telegram (ប្រើ Timeout ដើម្បីការពារការគាំង)
        try:
            tel_response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={"chat_id": CHAT_ID, "text": telegram_msg, "parse_mode": "Markdown"},
                timeout=10
            )
            tel_response.raise_for_status()
        except Exception as tel_err:
            print(f"❌ Telegram Error: {tel_err}")
            return jsonify({"success": False, "error": "មិនអាចបញ្ជូនដំណឹងទៅអ្នកលក់បានទេ"}), 500

        # 6. កត់ត្រាចូល Excel (ក្រោយពេលជោគជ័យគ្រប់លក្ខខណ្ឌ)
        try:
            wb = load_workbook(EXCEL_FILE)
            ws = wb.active
            ws.append([
                order_id, 
                queue_number, 
                time_now, 
                items_for_excel.rstrip(', '), 
                total, 
                round(distance_m, 2), 
                map_link
            ])
            wb.save(EXCEL_FILE)
        except Exception as excel_err:
            print(f"❌ Excel Save Error: {excel_err}")
            # បើទោះជាកត់ Excel មិនចូល ក៏យើងនៅតែប្រាប់ User ថាជោគជ័យ ព្រោះ Telegram ទៅដល់ហើយ

        return jsonify({
            "success": True, 
            "order_id": order_id,
            "message": f"ការកុម្ម៉ង់បានជោគជ័យ! លេខរង់ចាំរបស់អ្នកគឺ: {queue_number}"
        })

    except Exception as e:
        print(f"❌ Global Error: {e}")
        return jsonify({"success": False, "error": "មានបញ្ហាបច្ចេកទេសនៅលើ Server"}), 500

if __name__ == "__main__":
    # ប្រើ Port 5000 សម្រាប់ការ Test ក្នុងមូលដ្ឋាន
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)