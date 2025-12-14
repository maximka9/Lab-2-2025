#!/usr/bin/env python3
import os
import tempfile
from pathlib import Path
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import whisper

app = Flask(__name__)
CORS(app)

model = None

def load_model():
    global model
    if model is None:
        model_size = os.getenv('MODEL_SIZE', 'base')
        device = os.getenv('DEVICE', 'cpu')
        model = whisper.load_model(model_size, device=device)
    return model

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "service": "auto_subtitle"}), 200

@app.route('/transcribe', methods=['POST'])
def transcribe():
    try:
        if 'audio_file' not in request.files:
            return jsonify({"error": "Не найден файл audio_file"}), 400
        
        audio_file = request.files['audio_file']
        if audio_file.filename == '':
            return jsonify({"error": "Файл не выбран"}), 400
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(audio_file.filename).suffix) as tmp_file:
            audio_file.save(tmp_file.name)
            tmp_path = tmp_file.name
        
        try:
            whisper_model = load_model()
            result = whisper_model.transcribe(tmp_path, language="en", task="transcribe", verbose=False)
            
            segments = []
            for segment in result.get("segments", []):
                segments.append({
                    "id": segment.get("id", 0),
                    "start": segment.get("start", 0.0),
                    "end": segment.get("end", 0.0),
                    "text": segment.get("text", "").strip()
                })
            
            return jsonify({
                "text": result.get("text", "").strip(),
                "language": result.get("language", "en"),
                "segments": segments
            }), 200
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    except Exception as e:
        return jsonify({"error": f"Ошибка обработки: {str(e)}"}), 500

@app.route('/transcribe_to_srt', methods=['POST'])
def transcribe_to_srt():
    try:
        if 'audio_file' not in request.files:
            return jsonify({"error": "Не найден файл audio_file"}), 400
        
        audio_file = request.files['audio_file']
        if audio_file.filename == '':
            return jsonify({"error": "Файл не выбран"}), 400
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(audio_file.filename).suffix) as tmp_file:
            audio_file.save(tmp_file.name)
            tmp_path = tmp_file.name
        
        try:
            whisper_model = load_model()
            result = whisper_model.transcribe(tmp_path, language="en", task="transcribe", verbose=False)
            
            srt_content = ""
            segments = result.get("segments", [])
            
            for idx, segment in enumerate(segments, start=1):
                start_time = format_timestamp(segment.get("start", 0.0))
                end_time = format_timestamp(segment.get("end", 0.0))
                text = segment.get("text", "").strip()
                srt_content += f"{idx}\n{start_time} --> {end_time}\n{text}\n\n"
            
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.srt', encoding='utf-8') as srt_file:
                srt_file.write(srt_content)
                srt_path = srt_file.name
            
            return send_file(srt_path, mimetype='text/plain', as_attachment=True, download_name='subtitles.srt')
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    except Exception as e:
        return jsonify({"error": f"Ошибка обработки: {str(e)}"}), 500

def format_timestamp(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

if __name__ == '__main__':
    load_model()
    app.run(host='0.0.0.0', port=8000, debug=False)
