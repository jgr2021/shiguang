"""Offline UI translations. Only application text, never user content, is translated."""
from translations import ENGLISH, TRADITIONAL
from github_translations import ENGLISH as GITHUB_ENGLISH, TRADITIONAL as GITHUB_TRADITIONAL

ENGLISH.update(GITHUB_ENGLISH)
TRADITIONAL.update(GITHUB_TRADITIONAL)

LANGUAGES = {"zh-CN": "简体中文", "zh-TW": "繁體中文", "en": "English"}
_language = "zh-CN"


def set_language(code):
    global _language
    _language = code if code in LANGUAGES else "zh-CN"


def get_language():
    return _language


def tr(source, *args):
    catalog = ENGLISH if _language == "en" else TRADITIONAL if _language == "zh-TW" else {}
    value = catalog.get(source, source)
    return value.format(*args) if args else value


def assistant_language():
    language = {"zh-CN": "Simplified Chinese", "zh-TW": "Traditional Chinese", "en": "English"}[_language]
    return "Default response and generated-document language: " + language + ". If the user explicitly requests another language, follow their request. Preserve quotations and source record IDs.\n"


def file_status(value):
    prefix = "原文件已保存，正文提取失败："
    if value.startswith(prefix):
        return tr(prefix) + tr(value[len(prefix):])
    return tr(value)


def month_title(day):
    if _language == "en":
        return MONTHS[day.month - 1] + " " + str(day.year)
    return f"{day.year} 年 {day.month} 月"


def day_title(day):
    if _language == "en":
        return MONTHS[day.month - 1] + " " + str(day.day)
    return f"{day.month} 月 {day.day} 日"


MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
