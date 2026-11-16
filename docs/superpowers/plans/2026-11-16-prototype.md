# Apartment prototype Implementation Plan

**Goal:** Запускаемый локально универсальный viewer квартиры из JSON.
**Architecture:** Python producer и TypeScript consumer разделяют JSON Schema; геометрия не зависит от UI.
**Tech Stack:** Python 3.12, OpenCV, Shapely, JSON Schema, TypeScript, Three.js, Vite.
**Spec:** docs/superpowers/specs/2026-11-16-prototype-design.md

## Порядок выполнения
- [x] Контракт: schema/apartment.schema.json, viewer/src/model.ts, тестовая квартира; проверить неизвестный масштаб, ссылки и выход проёмов за стену.
- [x] Геометрия: viewer/src/geometry.ts; проверить площадь стены за вычетом дверей/окон и диагональные стены.
- [x] CLI: recognizer/cli.py; validate, calibrate по известному отрезку; unittest проверяет масштабирование и запрет перезаписи исходника.
- [x] UI: viewer/src/main.ts и style.css; orbit, top, walk, JSON import/edit/export, метрики и ошибки.
- [x] Запуск: npm test, npm run build, Python unittest, браузерная проверка и README с фактическими ограничениями.

Работа выполняется в текущей сессии. Git недоступен: каталог .git не содержит рабочего репозитория; коммиты не выполняются.

Проверено 16.11.2026: mise setup/test/build/validate пройдены, 11 тестов; Chromium smoke проверяет основные режимы и JSON-коррекцию. Автораспознавание и GLB-файлы вне первого среза.
