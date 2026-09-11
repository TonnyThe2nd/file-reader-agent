from io import BytesIO

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import SecretStr, ValidationError
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.core.config import Settings, settings
from app.core.security import current_owner
from app.services.document_service import split_document
from evaluation.run import evaluate


def test_pdf_extracts_page_and_rejects_scans_or_passwords():
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {
                    NameObject("/F1"): DictionaryObject(
                        {
                            NameObject("/Type"): NameObject("/Font"),
                            NameObject("/Subtype"): NameObject("/Type1"),
                            NameObject("/BaseFont"): NameObject("/Helvetica"),
                        }
                    )
                }
            )
        }
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 50 700 Td (O total e 42.) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    assert split_document(output.getvalue(), "application/pdf") == [("Pagina 1", "O total e 42.")]
    writer.encrypt("password")
    encrypted = BytesIO()
    writer.write(encrypted)
    with pytest.raises(HTTPException) as error:
        split_document(encrypted.getvalue(), "application/pdf")
    assert error.value.status_code == 422
    blank = PdfWriter()
    blank.add_blank_page(width=612, height=792)
    output = BytesIO()
    blank.write(output)
    with pytest.raises(HTTPException):
        split_document(output.getvalue(), "application/pdf")


def test_auth_invalid_unicode_and_weak_config(monkeypatch):
    monkeypatch.setattr(settings, "api_tokens", {"user": SecretStr("x" * 32)})
    with pytest.raises(HTTPException) as error:
        current_owner(HTTPAuthorizationCredentials(scheme="Bearer", credentials="inválida"))
    assert error.value.status_code == 401
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, api_tokens={"user": "private-short-token"})
    assert "private-short-token" not in str(error.value)


def test_evaluation_detects_missing_answers_and_sources():
    dataset = [{"id": "one", "expected_terms": ["42"], "expected_source_terms": ["42"]}]
    assert evaluate(dataset, [])["pass_rate"] == 0
    assert evaluate(dataset, [{"id": "one", "answer": "42", "sources": []}])["pass_rate"] == 0
    assert (
        evaluate(dataset, [{"id": "one", "answer": "42", "sources": [{"content": "Total: 42"}]}])[
            "pass_rate"
        ]
        == 1
    )
