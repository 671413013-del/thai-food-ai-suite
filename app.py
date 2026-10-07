import os
import base64
import requests
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Max 16MB

AIFORTHAI_API_KEY = os.getenv("AIFORTHAI_API_KEY", "bg5BvBzm5FaIIQMzbRKjDIYCj3uGRr3l")
AIFORTHAI_URL = "https://api.aiforthai.in.th/thaifood"
THAI_LLM_API_KEY = os.getenv("THAI_LLM_API_KEY", "ibY2jxvjwtke1Q3k9SeEUj0BldNR121o")
THAI_LLM_URL = "http://thaillm.or.th/api/v1/chat/completions"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/nutrition-advisor', methods=['POST'])
def nutrition_advisor():
    try:
        data = request.json or {}
        food_name = data.get('food_name', '').strip()
        if not food_name:
            return jsonify({'OK': False, 'error': 'กรุณาระบุชื่ออาหาร'}), 400

        prompt = (
            f"คุณเป็นนักโภชนาการผู้เชี่ยวชาญด้านอาหารไทย ช่วยวิเคราะห์คุณค่าทางโภชนาการของเมนู '{food_name}' "
            "โดยให้ข้อมูลสรุปดังต่อไปนี้อย่างกระชับ ชัดเจน และอ่านเข้าใจง่าย:\n"
            "1. ⚡ พลังงานโดยประมาณ (kcal ต่อ 1 จาน/ชาม)\n"
            "2. 🥩 สารอาหารหลัก (คาร์โบไฮเดรต, โปรตีน, ไขมัน, โซเดียม)\n"
            "3. ⚠️ ข้อควรระวังต่อสุขภาพ (เช่น โซเดียมสูง, ผู้ป่วยเบาหวาน/ไต/ความดันควรระวัง)\n"
            "4. 💡 คำแนะนำในการรับประทานเพื่อสุขภาพ (เช่น ทานคู่ผักสด, ลดการซดน้ำแกง)\n"
            "ตอบเป็นภาษาไทย ให้กระชับ สุภาพ เป็นกันเอง โดยไม่ต้องใส่แท็ก <think> ใดๆ"
        )

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {THAI_LLM_API_KEY}'
        }
        payload = {
            'model': 'openthaigpt-thaillm-8b-instruct-v7.2',
            'messages': [
                {'role': 'user', 'content': prompt}
            ],
            'max_tokens': 1024,
            'temperature': 0.3
        }

        response = requests.post(THAI_LLM_URL, headers=headers, json=payload, timeout=40)
        if response.status_code != 200:
            return jsonify({'OK': False, 'error': f'ThaiLLM API Error: {response.text}'}), response.status_code

        res_data = response.json()
        raw_content = res_data['choices'][0]['message']['content']

        # Remove <think>...</think> reasoning tags if present
        import re
        clean_content = re.sub(r'<think>[\s\S]*?</think>', '', raw_content).strip()

        return jsonify({
            'OK': True,
            'food_name': food_name,
            'advice': clean_content
        })

    except requests.exceptions.Timeout:
        return jsonify({'OK': False, 'error': 'การเชื่อมต่อไปยัง ThaiLLM หมดเวลา'}), 504
    except Exception as e:
        return jsonify({'OK': False, 'error': str(e)}), 500

# แท็บที่ 3: AIForThai - VAJA (Text-to-Speech)
@app.route('/api/vaja', methods=['POST'])
def vaja_tts():
    try:
        data = request.json or {}
        text = data.get('text', '').strip()
        speaker = data.get('speaker', 'nana').strip() or 'nana'

        if not text:
            return jsonify({'msg': 'error', 'error': 'กรุณาระบุข้อความที่ต้องการสังเคราะห์เสียง'}), 400

        url = "https://api.aiforthai.in.th/vaja"
        headers = {
            'Apikey': AIFORTHAI_API_KEY,
            'Content-Type': 'application/json'
        }
        payload = {
            "text": text,
            "speaker": speaker
        }

        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code != 200:
            return jsonify({'msg': 'error', 'error': f'VAJA API Error: {response.text}'}), response.status_code

        res_json = response.json()
        return jsonify(res_json)

    except requests.exceptions.Timeout:
        return jsonify({'msg': 'error', 'error': 'การเชื่อมต่อไปยัง VAJA API หมดเวลา (Timeout)'}), 504
    except Exception as e:
        return jsonify({'msg': 'error', 'error': str(e)}), 500

@app.route('/api/vaja/proxy', methods=['GET'])
def vaja_proxy():
    audio_url = request.args.get('url', '')
    if not audio_url:
        return "Missing url parameter", 400
    try:
        r = requests.get(audio_url, headers={'Apikey': AIFORTHAI_API_KEY}, timeout=30)
        from flask import Response
        return Response(r.content, mimetype='audio/wav')
    except Exception as e:
        return str(e), 500

@app.route('/api/recognize', methods=['POST'])
def recognize_food():
    try:
        b64_str = None
        
        # Check if file was uploaded via multipart/form-data
        if 'file' in request.files:
            uploaded_file = request.files['file']
            if uploaded_file.filename == '':
                return jsonify({'OK': False, 'error': 'ไม่มีไฟล์ที่ถูกเลือก'}), 400
            file_bytes = uploaded_file.read()
            b64_str = base64.b64encode(file_bytes).decode('utf-8')
            
        # Check if base64 string was sent via JSON
        elif request.is_json and 'image_base64' in request.json:
            raw_b64 = request.json['image_base64']
            # Remove data URL prefix if present (e.g. data:image/jpeg;base64,...)
            if ',' in raw_b64:
                raw_b64 = raw_b64.split(',', 1)[1]
            b64_str = raw_b64
        else:
            return jsonify({'OK': False, 'error': 'กรุณาอัปโหลดรูปภาพอาหาร'}), 400

        # Prepare request to AIForThai API
        headers = {
            'Content-Type': 'application/json',
            'Apikey': AIFORTHAI_API_KEY
        }
        data = {
            'file': b64_str
        }

        # Call AIForThai Thai Food Recognition API
        response = requests.post(AIFORTHAI_URL, headers=headers, json=data, timeout=30)
        
        if response.status_code != 200:
            return jsonify({
                'OK': False,
                'status_code': response.status_code,
                'error': f'AIForThai API Error: {response.text}'
            }), response.status_code

        res_json = response.json()
        return jsonify(res_json)

    except requests.exceptions.Timeout:
        return jsonify({'OK': False, 'error': 'การเชื่อมต่อไปยัง AIForThai API หมดเวลา (Timeout)'}), 504
    except requests.exceptions.RequestException as e:
        return jsonify({'OK': False, 'error': f'เกิดข้อผิดพลาดในการเชื่อมต่อเครือข่าย: {str(e)}'}), 502
    except Exception as e:
        return jsonify({'OK': False, 'error': f'เกิดข้อผิดพลาดภายในระบบ: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    print(f"Starting Thai Food Recognition Web App on http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
