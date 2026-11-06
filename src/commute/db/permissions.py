"""Create an ordinary API login and grant only its explicit reporting reads.

Callers generate/store the password privately. Existing logins are never reset,
and the API receives no raw/rejected-table or write privileges.
"""
import sqlalchemy as sa
from psycopg import sql

API_TABLES = ("source_resources", "source_snapshots", "import_runs", "delay_records", "incident_codes")


def create_api_login(connection, role: str, password: str) -> bool:
    """Create only a missing ordinary login. Existing passwords are never reset."""
    if connection.scalar(sa.text("SELECT EXISTS (SELECT FROM pg_roles WHERE rolname=:role)"), {"role": role}):
        return False
    # psycopg quotes the utility statement's identifier/literal. Do not interpolate
    # a password into a logged SQLAlchemy statement or command-line argument.
    with connection.connection.driver_connection.cursor() as cursor:
        cursor.execute(sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD {}").format(sql.Identifier(role), sql.Literal(password)))
    return True


def verify_api_role(connection):
    """Fail closed when a hosted app is accidentally given a writer credential."""
    admin = connection.execute(sa.text("""SELECT rolsuper, rolcreatedb, rolcreaterole,
        rolreplication, rolbypassrls FROM pg_roles WHERE rolname=current_user""")).one()
    writes = connection.scalar(sa.text("""SELECT EXISTS (SELECT FROM pg_tables WHERE schemaname='public'
        AND has_table_privilege(quote_ident(schemaname)||'.'||quote_ident(tablename),
                                'INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER'))"""))
    creates = connection.scalar(sa.text("SELECT has_schema_privilege('public', 'CREATE')"))
    if any(admin) or writes or creates:
        raise ValueError("The API credential has write or administrative privileges. Configure a dedicated read-only API login.")


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
    database = quote(connection.scalar(sa.text("SELECT current_database()")))
    connection.execute(sa.text(f"GRANT CONNECT ON DATABASE {database} TO {identifier}"))
    connection.execute(sa.text(f"GRANT USAGE ON SCHEMA public TO {identifier}"))
    tables = ", ".join("public." + quote(table) for table in API_TABLES)
    connection.execute(sa.text(f"GRANT SELECT ON TABLE {tables} TO {identifier}"))
    # Explicit grants only: a later migration must deliberately review new reads.
    connection.execute(sa.text(f"ALTER ROLE {identifier} SET default_transaction_read_only = on"))
