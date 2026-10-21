"""Bounded plugin declarations and safe, actionable configuration failures."""
from __future__ import annotations

import json
from pathlib import Path
import stat

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


class PluginConfigurationError(ValueError):
    """Public diagnostics contain field names and repair instructions, never values."""

    def __init__(self, code, public_message, *, field_path='executor.config.config_file',
                 hint='', plugin_id=None):
        self.code = code
        self.public_message = public_message
        self.field_path = field_path
        self.hint = hint
        self.plugin_id = plugin_id
        super().__init__(public_message)


def configuration_path(value, *, base=None, field_path='executor.config.config_file', plugin_id=None):
    if not isinstance(value, str) or not value.strip():
        raise PluginConfigurationError('plugin_config_path_required', '插件配置文件路径不能为空。',
            field_path=field_path, hint='请填写可读取的 JSON 或 TOML 配置文件路径。', plugin_id=plugin_id)
    try:
        path = Path(value).expanduser()
        return ((Path(base) if base is not None else Path.cwd()) / path).absolute()
    except (OSError, ValueError, RuntimeError):
        raise PluginConfigurationError('plugin_config_path_invalid', '插件配置文件路径无效。',
            field_path=field_path, hint='请修正配置文件路径。', plugin_id=plugin_id) from None


def read_configuration(path, *, field_path='executor.config.config_file', plugin_id=None):
    """Read one regular JSON/TOML object, without constructing plugin services."""
    path = Path(path)
    def fail(code, message, hint):
        return PluginConfigurationError(code, message, field_path=field_path, hint=hint, plugin_id=plugin_id)
    try:
        metadata = path.stat()
        if not stat.S_ISREG(metadata.st_mode):
            raise fail('plugin_config_not_file', '插件配置路径必须指向普通文件。', '请选择 JSON 或 TOML 配置文件。')
        with path.open('rb') as stream:
            raw = stream.read(256_001)
        if len(raw) > 256_000:
            raise fail('plugin_config_too_large', '插件配置文件超过大小限制。', '请将配置文件缩减到 256000 字节以内。')
    except PluginConfigurationError:
        raise
    except FileNotFoundError:
        raise fail('plugin_config_missing', '找不到插件配置文件。', '请创建配置文件或修正文件路径。') from None
    except (OSError, ValueError):
        raise fail('plugin_config_unreadable', '无法读取插件配置文件。', '请检查文件路径和读取权限。') from None
    if path.suffix.lower() not in {'.json', '.toml'}:
        raise fail('plugin_config_format', '插件配置文件格式不受支持。', '请使用 .json 或 .toml 文件。')
    try:
        if path.suffix.lower() == '.toml':
            value = tomllib.loads(raw.decode('utf-8'))
        elif path.suffix.lower() == '.json':
            value = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if not isinstance(value, dict):
            raise ValueError()
    except (UnicodeError, ValueError):
        raise fail('plugin_config_invalid', '插件配置文件不是有效的 JSON/TOML 对象。', '请修正配置文件语法和顶层对象。') from None
    return value


def read_execution_selection(path):
    """Resolve a CLI wrapper's config_file relative to the wrapper itself."""
    source = configuration_path(str(path))
    value = read_configuration(source)
    if 'config_file' in value:
        value['config_file'] = str(configuration_path(value['config_file'], base=source.parent))
    return value
