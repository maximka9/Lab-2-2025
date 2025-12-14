#!/bin/bash

cleanup() {
    echo "Получен сигнал завершения, останавливаем сервисы..."
    kill $SUBTITLE_PID $VIDEO_PID 2>/dev/null
    wait $SUBTITLE_PID $VIDEO_PID 2>/dev/null
    exit 0
}

trap cleanup SIGTERM SIGINT

echo "Запуск auto_subtitle на порту 8000..."
python auto_subtitle_service.py &
SUBTITLE_PID=$!

sleep 2

echo "Запуск video_processing на порту 8080..."
python video_processing_service.py &
VIDEO_PID=$!

echo "Оба сервиса запущены:"
echo "  - auto_subtitle (PID: $SUBTITLE_PID)"
echo "  - video_processing (PID: $VIDEO_PID)"

wait $SUBTITLE_PID $VIDEO_PID
