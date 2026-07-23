import json
import os
import yaml

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(BASE_DIR, "config")


def _load_yaml(filename):
    path = os.path.join(CONFIG_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_json(filename):
    path = os.path.join(CONFIG_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_sources():
    return _load_yaml("sources.yaml")


def load_keywords():
    return _load_yaml("keywords.yaml")


def load_estados():
    return _load_yaml("estados.yaml")["estados"]


def load_settings():
    return _load_yaml("settings.yaml")


def load_ubicaciones_detalle():
    return _load_json("ubicaciones_detalle.json")
