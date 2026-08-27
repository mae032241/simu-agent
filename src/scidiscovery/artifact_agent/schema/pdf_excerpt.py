"""Control-generated, source-bound excerpts from cached PDF text."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import SchemaModel, canonical_json


PDF_TEXT_EXTRACTOR_PROFILE = "pdftotext-layout-v1"


class PdfExcerptSet(SchemaModel):
    extractor_profile: Literal["pdftotext-layout-v1"] = PDF_TEXT_EXTRACTOR_PROFILE
    first_page: Annotated[int, Field(ge=1, le=100000)]
    last_page: Annotated[int, Field(ge=1, le=100000)]
    available_page_count: Annotated[int, Field(ge=1, le=100000)]
    content: Annotated[str, Field(max_length=524288)]
    truncated: bool

    @model_validator(mode="after")
    def _pages_are_ordered(self) -> PdfExcerptSet:
        if self.last_page < self.first_page:
            raise ValueError("PDF excerpt pages are not ordered")
        if self.last_page > self.available_page_count:
            raise ValueError("PDF excerpt exceeds the available page count")
        return self


def validate_pdf_excerpt_set(value: dict[str, object]) -> dict[str, object]:
    return PdfExcerptSet.model_validate_json(
        canonical_json(value), strict=True
    ).model_dump(mode="json")


__all__ = [
    "PDF_TEXT_EXTRACTOR_PROFILE",
    "PdfExcerptSet",
    "validate_pdf_excerpt_set",
]
