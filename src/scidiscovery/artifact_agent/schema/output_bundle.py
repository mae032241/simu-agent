"""可选多文件输出的领域无关清单格式。"""

from __future__ import annotations

from pydantic import Field

from .common import SchemaModel


class OutputBundleItem(SchemaModel):
    collection: str = Field(min_length=1, max_length=128)
    item: str = Field(min_length=1, max_length=256)
    media_type: str = Field(min_length=1, max_length=128)
    relative_path: str = Field(min_length=1, max_length=1024)


class OutputBundle(SchemaModel):
    items: tuple[OutputBundleItem, ...] = Field(min_length=1, max_length=1024)


__all__ = ["OutputBundle", "OutputBundleItem"]
