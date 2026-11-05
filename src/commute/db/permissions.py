"""Explicit grants for a dedicated, otherwise unprivileged API login.

Provision the login/password in the database host's private settings first. This
helper never creates a password or grants the public API access to raw payloads.
"""
import sqlalchemy as sa

API_TABLES = ("source_resources", "source_snapshots", "import_runs", "delay_records", "incident_codes")


def grant_api_reads(connection, role: str):
    attributes = connection.execute(sa.text("""SELECT rolsuper, rolcreatedb, rolcreaterole,
        rolreplication, rolbypassrls FROM pg_roles WHERE rolname=:role"""), {"role": role}).first()
    if attributes is None or any(attributes):
        raise ValueError("Use an existing dedicated API role without administrative privileges.")
    if connection.scalar(sa.text("SELECT has_schema_privilege(:role, 'public', 'CREATE')"), {"role": role}):
        raise ValueError("API role must not have schema-creation privileges.")
    if connection.scalar(sa.text("""SELECT EXISTS (SELECT FROM pg_tables WHERE schemaname='public'
        AND has_table_privilege(:role, quote_ident(schemaname)||'.'||quote_ident(tablename),
                                'INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER'))"""), {"role": role}):
        raise ValueError("API role already has write privileges; provision a separate unprivileged login.")
    quote = connection.dialect.identifier_preparer.quote_identifier
    identifier = quote(role)
    connection.execute(sa.text(f"GRANT USAGE ON SCHEMA public TO {identifier}"))
    tables = ", ".join("public." + quote(table) for table in API_TABLES)
    connection.execute(sa.text(f"GRANT SELECT ON TABLE {tables} TO {identifier}"))
    # Explicit grants only: a later migration must deliberately review new reads.
    connection.execute(sa.text(f"ALTER ROLE {identifier} SET default_transaction_read_only = on"))
