# Wall recognition Implementation Plan

**Goal:** Получить кандидаты стен и наложение из изображения без заданных координат.
**Architecture:** OpenCV-модуль не зависит от CLI и viewer. Новый документ кандидатов хранит неизвестный масштаб и не загружается как готовая квартира.
**Tech Stack:** Python, OpenCV, NumPy, JSON Schema; уже установлены.
**Spec:** docs/superpowers/specs/2026-11-16-wall-recognition.md

- [x] Создать tests/test_recognition.py: синтетические линии, шум/мебель, дверной разрыв, масштабирование, пустой/испорченный ввод и существующий вывод. Запустить и убедиться, что модуль отсутствует.
- [x] Создать recognizer/walls.py с распознаванием, группировкой и записью наложения, schema/wall-candidates.schema.json с пиксельным контрактом. Пройти тесты.
- [x] Добавить recognize в существующий recognizer/cli.py, сохранив validate/calibrate и их проверки перезаписи. Запуск: `mise exec -- uv run python -m recognizer.cli recognize plan.jpg --output artifacts/plan-walls`.
- [x] Выполнить recognize для реального файла, проверить схему и наложение, весь набор mise run test и mise run build; записать результаты в README.

Работа в текущей сессии, без дополнительных агентов. Git в этом каталоге не инициализирован.

Результат: 27 кандидатов на plan.jpg, overlay.png просмотрен; 20 тестов и build/validate пройдены. Сохраняются дубли двойных контуров, возможные ложные срабатывания и пропуски тонких участков. Новые зависимости не установлены; уже используемый NumPy объявлен прямой зависимостью.
