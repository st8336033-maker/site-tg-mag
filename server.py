import os
import random
import requests
import json
import smtplib
import ollama  # Переконайся, що тут ollama, а не genai
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
# Дозволяємо CORS для всіх маршрутів
CORS(app, resources={r"/*": {"origins": "*"}})

# Конфігурація з .env
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_CHAT_ID")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASSWORD")
GEMINI_KEY = os.getenv("GEMINI_KEY")


DATA_FILE = 'products.json'
auth_codes = {}

# --- ДОПОМІЖНІ ФУНКЦІЇ ---

def send_email_code(target_email, code):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = target_email
        msg['Subject'] = "Код підтвердження LUNXET"
        body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; text-align: center;">
                <h2 style="color: #111;">Ваш код входу в LUNXET MART</h2>
                <div style="font-size: 32px; font-weight: bold; color: #cdef2e; background: #111; padding: 20px; display: inline-block; border-radius: 10px;">
                    {code}
                </div>
            </body>
        </html>
        """
        msg.attach(MIMEText(body, 'html'))
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, target_email, msg.as_string())
        return True
    except Exception as e:
        print(f"❌ Помилка Email: {e}")
        return False

# --- МАРШРУТИ ---

@app.route('/')
def index():
    return send_from_directory('static', 'sitr.html')

@app.route('/ai-helper')
def ai_helper():
    return send_from_directory('static', 'ai.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory('uploads', filename)

@app.route('/api/products', methods=['GET'])
def get_products():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            try:
                return jsonify(json.load(f))
            except:
                return jsonify([])
    return jsonify([])

@app.route('/api/generate-look', methods=['POST', 'OPTIONS'])
def generate_look():
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200

    try:
        data = request.json
        height = data.get('height', '170')
        hair = data.get('hair', 'brown')
        selected_cats = data.get('categories', [])

        # Завантажуємо товари
        products = []
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                products = json.load(f)
        
        inventory_text = ", ".join([p.get('name', 'Товар') for p in products])

        # Формуємо промт для Ollama
        prompt = f"""
        Ти стиліст магазину LUNXET. Клієнт: {height}см, волосся {hair}.
        Запит: {selected_cats}. Товари в наявності: {inventory_text}.
        Поверни відповідь ТІЛЬКИ у форматі JSON без зайвих слів:
        {{
          "items": ["назва"],
          "visual_prompt": "fashion photo prompt in English",
          "advice": "порада українською"
        }}
        """

        # --- ТУТ МІНЯЄМО GEMINI НА OLLAMA ---
        response = ollama.chat(model='llama3', messages=[
            {
                'role': 'user',
                'content': prompt,
            },
        ])
        
        res_text = response['message']['content'].strip()
        # ------------------------------------
        
        # Очищення від Markdown
        if "```json" in res_text:
            res_text = res_text.split("```json")[1].split("```")[0].strip()
        elif "```" in res_text:
            res_text = res_text.split("```")[1].split("```")[0].strip()

        final_data = json.loads(res_text)
        return jsonify(final_data)

    except Exception as e:
        print(f"❌ Помилка Ollama: {e}")
        return jsonify({
            "items": ["Помилка моделі"],
            "visual_prompt": "fashion model",
            "advice": f"Помилка: {str(e)}. Переконайтеся, що Ollama запущена."
        }), 200 # Повертаємо 200, щоб фронтенд не "падав"

@app.route('/api/auth/request', methods=['POST', 'OPTIONS'])
def send_auth_code():
    if request.method == 'OPTIONS': return jsonify({"success": True}), 200
    data = request.json
    contact = data.get('contact', '').strip()
    if not contact: return jsonify({"success": False, "message": "Вкажіть контакт"}), 400
    
    code = str(random.randint(1000, 9999))
    auth_codes[contact] = code

    if "@" in contact:
        if send_email_code(contact, code): return jsonify({"success": True})
        else: return jsonify({"success": False, "message": "Помилка Email"}), 500
    else:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            msg = f"🔑 Код LUNXET: {code}\n👤 Користувач: {contact}"
            requests.post(url, json={"chat_id": ADMIN_ID, "text": msg})
            return jsonify({"success": True})
        except:
            return jsonify({"success": False, "message": "Помилка Telegram"}), 500

@app.route('/api/auth/verify', methods=['POST', 'OPTIONS'])
def verify_auth_code():
    if request.method == 'OPTIONS': return jsonify({"success": True}), 200
    data = request.json
    contact = data.get('contact', '').strip()
    code = data.get('code', '').strip()

    if contact in auth_codes and str(auth_codes[contact]) == str(code):
        del auth_codes[contact]
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Невірний код"}), 401

if __name__ == '__main__':
    if not os.path.exists('uploads'): os.makedirs('uploads')
    app.run(debug=True, port=5000)