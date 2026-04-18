# Core Feature: Assemblies & STEP Export Hierarchy (v1.0)

## 1. Проблема

В настоящий момент `generator.py` объединяет все сгенерированные детали (`parts`) с помощью `Shape.fuse()`. Это приводит к потере иерархии: сложная машина (например, поршень с шатуном) превращается в монолитный кусок металла. Симуляторы (MuJoCo) не могут рассчитывать кинематику на монолите.

## 2. Решение: CadQuery `Assembly`

Мы переходим от возврата единого `cq.Workplane` к использованию объекта `cq.Assembly`.

**Новый пайплайн генерации:**

1. Парсинг `BlueprintPayload`.
2. Создание пустого `root_assembly = cq.Assembly(None, name="AI_Forge_Project")`.
3. Цикл по `parts`:
   - Генерация `Shape` для детали (используя функции из `core`).
   - Добавление детали в сборку: `root_assembly.add(solid, name=part_id)`.
4. В версии 1.0 позиционирование деталей (локации) задаётся на этапе их генерации (через `position` примитива, если он будет добавлен в схему, или считаем, что они сгенерированы в глобальных координатах «как есть»).

## 3. Обновление экспорта (`export_artifacts`)

Функция принимает `cq.Assembly` вместо одного `Shape`.

- **STEP (`.step`):** `assembly.export(path, exportType="STEP")` сохраняет иерархию (имена деталей как в `part_id`).
- **STL (`.stl`):** STL не поддерживает иерархию. CadQuery для сборки вызывает `toCompound().exportStl(...)` — компаунд только для меша; вьювер остаётся на STL как MVP-фолбэк. Позже возможен переход на `.glb` для цветов.

## 4. Задачи для реализации

1. Рефакторинг `build_shape_from_blueprint` → добавление `build_assembly_from_blueprint` с возвратом `cq.Assembly`; `build_shape_from_blueprint` оставлен как обёртка `assembly.toCompound()` для тестов и обратной совместимости.
2. Обновление `export_artifacts` для работы с объектом `Assembly`.
3. Короткий REPL-туториал по `apply_hole` — см. [developer-experience.md](developer-experience.md).
