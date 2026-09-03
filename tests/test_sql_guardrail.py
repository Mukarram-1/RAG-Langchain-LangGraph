"""Deterministic tests for the highest-risk boundary."""

from src.db.schema_loader import ColumnSchema, SchemaCatalog, TableSchema
from src.guardrails.sql_guardrail import SQLGuardrail


def make_catalog() -> SchemaCatalog:
    domain = TableSchema(
        schema="public",
        name="Domain",
        columns={
            "id": ColumnSchema("id", "uuid", False),
            "companyName": ColumnSchema("companyName", "text", True),
            "status": ColumnSchema("status", "text", True),
        },
    )
    login = TableSchema(
        schema="public",
        name="Login",
        columns={
            "id": ColumnSchema("id", "uuid", False),
            "password": ColumnSchema("password", "text", False),
        },
    )
    return SchemaCatalog(
        tables={
            domain.qualified_name: domain,
            login.qualified_name: login,
        }
    )


def test_accepts_scoped_select_and_applies_limit() -> None:
    guardrail = SQLGuardrail(make_catalog(), max_rows=100)

    result = guardrail.validate(
        'SELECT "id", "companyName" FROM "public"."Domain" '
        'WHERE "status" = \'active\''
    )

    assert result.valid is True
    assert "LIMIT 100" in result.sql
    assert result.referenced_tables == ["public.Domain"]


def test_accepts_boolean_or_filters() -> None:
    guardrail = SQLGuardrail(make_catalog(), max_rows=100)

    result = guardrail.validate(
        'SELECT "id" FROM "public"."Domain" '
        'WHERE "companyName" ILIKE \'%Scooter%Coffee%\' '
        'OR "status" = \'active\''
    )

    assert result.valid is True


def test_preserves_lower_requested_limit() -> None:
    guardrail = SQLGuardrail(make_catalog(), max_rows=100)

    result = guardrail.validate(
        'SELECT "id" FROM "public"."Domain" LIMIT 5'
    )

    assert result.valid is True
    assert "LIMIT 5" in result.sql


def test_rejects_mutation_multiple_statements_and_star() -> None:
    guardrail = SQLGuardrail(make_catalog(), max_rows=100)

    assert not guardrail.validate(
        'DELETE FROM "public"."Domain"'
    ).valid
    assert not guardrail.validate(
        'SELECT "id" FROM "public"."Domain"; SELECT 1'
    ).valid
    assert not guardrail.validate(
        'SELECT * FROM "public"."Domain"'
    ).valid


def test_rejects_ctes_and_subqueries() -> None:
    guardrail = SQLGuardrail(make_catalog(), max_rows=100)

    assert not guardrail.validate(
        'WITH "items" AS (SELECT "id" FROM "public"."Domain") '
        'SELECT "id" FROM "items"'
    ).valid
    assert not guardrail.validate(
        'SELECT "id" FROM "public"."Domain" WHERE "id" IN '
        '(SELECT "id" FROM "public"."Domain")'
    ).valid


def test_rejects_unknown_and_sensitive_columns() -> None:
    guardrail = SQLGuardrail(make_catalog(), max_rows=100)

    assert not guardrail.validate(
        'SELECT "missing" FROM "public"."Domain"'
    ).valid
    blocked = guardrail.validate(
        'SELECT "password" FROM "public"."Login"'
    )
    assert blocked.valid is False
    assert "blocked" in blocked.error


def test_requires_quoted_case_sensitive_identifiers() -> None:
    guardrail = SQLGuardrail(make_catalog(), max_rows=100)

    result = guardrail.validate(
        'SELECT id FROM public.Domain'
    )

    assert result.valid is False
    assert "quoted" in result.error
