#!/usr/bin/env python3

import os
import tempfile
import subprocess
from pathlib import Path
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import uuid

app = Flask(__name__)
CORS(app)

TEMP_DIR = os.getenv('TEMP_DIR', '/data/temp')
os.makedirs(TEMP_DIR, exist_ok=True)

def run_ffmpeg_command(command, timeout=300, use_shell=True):
    try:
        if isinstance(command, list):
            use_shell = False
        result = subprocess.run(
            command,
            shell=use_shell,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        if result.returncode != 0:
            raise Exception(f"FFmpeg failed: {result.stderr}")
        return result
    except subprocess.TimeoutExpired:
        raise Exception("FFmpeg command timed out")
    except Exception as e:
        raise

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "service": "video_processing"}), 200

@app.route('/extract_audio', methods=['POST'])
def extract_audio():
    try:
        if 'video' not in request.files:
            return jsonify({"error": "Не найден файл video"}), 400
        
        video_file = request.files['video']
        if video_file.filename == '':
            return jsonify({"error": "Файл не выбран"}), 400
        
        file_id = str(uuid.uuid4())
        video_path = os.path.join(TEMP_DIR, f"input_{file_id}.mp4")
        audio_path = os.path.join(TEMP_DIR, f"audio_{file_id}.wav")
        
        try:
            video_file.save(video_path)
            
            command = f"ffmpeg -i {video_path} -y -ar 16000 -ac 1 -f wav -acodec pcm_s16le {audio_path}"
            
            run_ffmpeg_command(command, timeout=300)
            
            if not os.path.exists(audio_path):
                raise Exception("Аудиофайл не был создан")
            
            return send_file(
                audio_path,
                mimetype='audio/wav',
                as_attachment=True,
                download_name='audio.wav'
            )
            
        finally:
            for file_path in [video_path, audio_path]:
                if os.path.exists(file_path):
                    try:
                        os.unlink(file_path)
                    except Exception:
                        pass
    
    except Exception as e:
        return jsonify({"error": f"Ошибка обработки: {str(e)}"}), 500

@app.route('/burn_subtitles', methods=['POST'])
def burn_subtitles():
    try:
        if 'video' not in request.files:
            return jsonify({"error": "Не найден файл video"}), 400
        if 'subtitles' not in request.files:
            return jsonify({"error": "Не найден файл subtitles"}), 400
        
        video_file = request.files['video']
        subtitles_file = request.files['subtitles']
        
        if video_file.filename == '' or subtitles_file.filename == '':
            return jsonify({"error": "Файл не выбран"}), 400
        
        file_id = str(uuid.uuid4())
        video_path = os.path.join(TEMP_DIR, f"input_{file_id}.mp4")
        srt_path = os.path.join(TEMP_DIR, f"subtitles_{file_id}.srt")
        output_path = os.path.join(TEMP_DIR, f"output_{file_id}.mp4")
        
        try:
            video_file.save(video_path)
            
            subtitles_file.seek(0)
            subtitles_content = subtitles_file.read()
            
            if isinstance(subtitles_content, bytes):
                try:
                    subtitles_text = subtitles_content.decode('utf-8')
                except UnicodeDecodeError:
                    subtitles_text = subtitles_content.decode('latin-1')
            else:
                subtitles_text = str(subtitles_content)
            
            with open(srt_path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(subtitles_text)
                try:
                    os.fsync(f.fileno())
                except (AttributeError, OSError):
                    pass
            
            if not os.path.exists(video_path):
                raise Exception(f"Видеофайл не был сохранен: {video_path}")
            if not os.path.exists(srt_path):
                raise Exception(f"Файл субтитров не был сохранен: {srt_path}")
            
            srt_size = os.path.getsize(srt_path)
            
            if srt_size == 0:
                raise Exception(f"Файл субтитров пуст: {srt_path}")
            
            with open(srt_path, 'r', encoding='utf-8') as f:
                srt_content_preview = f.read(200)
            
            if not os.access(srt_path, os.R_OK):
                raise Exception(f"Нет прав на чтение файла субтитров: {srt_path}")
            
            srt_path_absolute = os.path.abspath(srt_path)
            
            with open(srt_path_absolute, 'r', encoding='utf-8') as f:
                test_read = f.read(100)
                if not test_read:
                    raise Exception(f"Файл субтитров пуст или не читается: {srt_path_absolute}")
            
            with open(srt_path_absolute, 'r', encoding='utf-8') as f:
                srt_content_check = f.read(1000)
                if '-->' not in srt_content_check:
                    raise Exception(f"Файл субтитров не в формате SRT (нет временных меток -->). Возможно, LLM вернул не SRT, а размышления. Содержимое: {srt_content_check[:200]}")
                
                srt_content_trimmed = srt_content_check.strip()
                if srt_content_trimmed.startswith('<think>') or '<think>' in srt_content_check:
                    raise Exception(f"Файл субтитров содержит thinking теги LLM вместо SRT. Нужно очистить ответ LLM от тегов <think>. Содержимое: {srt_content_check[:300]}")
            
            if not os.access(srt_path_absolute, os.R_OK):
                raise Exception(f"Нет прав на чтение файла субтитров перед ffmpeg: {srt_path_absolute}")
            
            if not os.path.exists(srt_path_absolute):
                raise Exception(f"Файл субтитров исчез перед запуском ffmpeg: {srt_path_absolute}")
            
            import shlex
            
            video_path_escaped = shlex.quote(video_path)
            srt_path_escaped = shlex.quote(srt_path)
            output_path_escaped = shlex.quote(output_path)
            
            srt_path_for_filter = srt_path_absolute.replace('\\', '/').replace(':', '\\:').replace('[', '\\[').replace(']', '\\]').replace(',', '\\,')
            subtitle_filter = f"subtitles={srt_path_for_filter}"
            
            command = [
                "ffmpeg",
                "-i", video_path,
                "-vf", subtitle_filter,
                "-c:v", "libx264",
                "-c:a", "copy",
                "-preset", "medium",
                "-crf", "23",
                "-y",
                output_path
            ]
            
            run_ffmpeg_command(command, timeout=600, use_shell=False)
            
            if not os.path.exists(output_path):
                raise Exception("Выходной видеофайл не был создан")
            
            return send_file(
                output_path,
                mimetype='video/mp4',
                as_attachment=True,
                download_name='video_with_subtitles.mp4'
            )
            
        finally:
            for file_path in [video_path, srt_path, output_path]:
                if os.path.exists(file_path):
                    try:
                        os.unlink(file_path)
                    except Exception:
                        pass
    
    except Exception as e:
        return jsonify({"error": f"Ошибка обработки: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
