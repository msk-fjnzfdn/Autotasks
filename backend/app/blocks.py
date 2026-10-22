import re
import json
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable
import httpx

#Это всё ещё требует немного тестов. Я возьму тестеров из своих друзей. Пусть повеселяться

@dataclass
class BlockSpec:
    title: str
    description: str
    params: dict
    run: Callable[..., Awaitable[dict]]


BLOCKS: dict[str, BlockSpec] = {}


def block(block_type: str, title: str, description: str, params: dict):
    def decorator(func):
        BLOCKS[block_type] = BlockSpec(
            title=title, description=description, params=params, run=func
        )
        return func
    return decorator


def _missing(params: dict, required: list[str]):
    return [k for k in required if not params.get(k)]


class BlockError(Exception):
    pass


@block("http_request", "HTTP-запрос",
       "Выполняет запрос по URL и сохраняет ответ в контекст.",
       {"url": "Адрес запроса", "method": "GET/POST"})
async def http_request(params: dict, context: dict) -> dict:
    missing = _missing(params, ["url"])
    if missing:
        raise BlockError(f"Не заданы параметры: {', '.join(missing)}")
    method = params.get("method", "GET").upper()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.request(method, params["url"])
    return {"status_code": resp.status_code, "response_text": resp.text[:5000]}


@block("filter_text", "Фильтр текста",
       "Проверяет текст по регулярному выражению; если не совпало — цепочка останавливается.",
       {"field": "Поле контекста", "pattern": "Регулярное выражение"})
async def filter_text(params: dict, context: dict) -> dict:
    value = context.get(params.get("field", ""), "")
    pattern = params.get("pattern", "")
    if not pattern:
        raise BlockError("Не задан шаблон pattern")
    if not re.search(pattern, str(value)):
        raise BlockError(f"Значение не прошло фильтр по шаблону «{pattern}»")
    return {}


@block("replace_text", "Замена текста",
       "Заменяет подстроку в тексте и сохраняет результат в новое поле.",
       {"field": "Откуда взять", "find": "Что заменить", "replace": "Чем заменить", "output": "Куда положить"})
async def replace_text(params: dict, context: dict) -> dict:
    value = str(context.get(params.get("field", ""), ""))
    output = params.get("output", "result")
    return {output: value.replace(params.get("find", ""), params.get("replace", ""))}


@block("log_message", "Лог",
       "Записывает сообщение в лог запуска.",
       {"message": "Текст сообщения"})
async def log_message(params: dict, context: dict) -> dict:
    return {}



@block("set_variable", "Переменная",
       "Записывает значение в контекст под заданным именем.",
       {"key": "Имя переменной", "value": "Значение"})
async def set_variable(params: dict, context: dict) -> dict:
    key = params.get("key")
    if not key:
        raise BlockError("Не задан параметр key")
    return {key: params.get("value")}


@block("json_extract", "Извлечение из JSON",
       "Разбирает JSON из поля контекста и сохраняет значение по пути, например data.items.0.title.",
       {"field": "Поле с JSON", "path": "Путь к значению", "output": "Куда сохранить"})
async def json_extract(params: dict, context: dict) -> dict:
    field = params.get("field", "")
    raw = context.get(field)
    if raw is None:
        raise BlockError(f"В контексте нет поля «{field}»")
    try:
        data = raw if isinstance(raw, (dict, list)) else json.loads(str(raw))
    except json.JSONDecodeError:
        raise BlockError(f"Содержимое поля «{field}» не является JSON")

    current = data
    for part in str(params.get("path", "")).split("."):
        if not part:
            continue
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                raise BlockError(f"Не удалось пройти путь «{params.get('path')}»: нет элемента {part}")
        elif isinstance(current, dict):
            if part not in current:
                raise BlockError(f"Нет ключа «{part}» в пути «{params.get('path')}»")
            current = current[part]
        else:
            raise BlockError("Путь заходит внутрь простого значения")
    return {params.get("output", "result"): current}


@block("format_text", "Шаблон текста",
       "Подставляет значения из контекста в шаблон: {имя_переменной}.",
       {"template": "Шаблон", "output": "Куда сохранить"})
async def format_text(params: dict, context: dict) -> dict:
    template = params.get("template", "")
    if not template:
        raise BlockError("Не задан шаблон")
    try:
        text = template.format(**context)
    except KeyError as e:
        raise BlockError(f"В контексте нет переменной {e}")
    return {params.get("output", "result"): text}


@block("filter_lines", "Фильтр строк",
       "Фильтрует строки текста по регулярному выражению: оставляет совпадения или убирает их.",
       {"field": "Поле с текстом", "pattern": "Регулярное выражение",
        "mode": "keep (оставить совпавшие) или remove (убрать)", "output": "Куда сохранить"})
async def filter_lines(params: dict, context: dict) -> dict:
    value = str(context.get(params.get("field", ""), ""))
    pattern = params.get("pattern", "")
    if not pattern:
        raise BlockError("Не задан шаблон pattern")
    mode = params.get("mode", "keep")
    if mode not in ("keep", "remove"):
        raise BlockError("mode должен быть keep или remove")
    lines = value.splitlines()
    if mode == "keep":
        kept = [line for line in lines if re.search(pattern, line)]
    else:
        kept = [line for line in lines if not re.search(pattern, line)]
    return {params.get("output", "result"): "\n".join(kept)}

