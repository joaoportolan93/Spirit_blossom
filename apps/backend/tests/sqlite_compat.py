"""
Compatibilidade do SQLite com extensões Postgres (apenas para testes locais com SQLite).
Permite que SearchVector, SearchQuery e GinIndex funcionem no SQLite em memória.
Em produção / CI com Postgres real, este módulo não é ativado.
"""

from django.contrib.postgres.indexes import PostgresIndex
from django.contrib.postgres.search import SearchQuery, SearchVector, SearchVectorExact


def patch_sqlite():
    def search_vector_as_sqlite(self, compiler, connection):
        expressions = [
            compiler.compile(expression)[0] for expression in self.get_source_expressions()
        ]
        col = expressions[0] if expressions else "''"
        return f"coalesce({col}, '')", []

    SearchVector.as_sqlite = search_vector_as_sqlite

    def search_query_as_sqlite(self, compiler, connection):
        val = getattr(self, "value", str(self))
        return "%s", [val]

    SearchQuery.as_sqlite = search_query_as_sqlite

    def search_vector_exact_as_sqlite(self, qn, connection):
        lhs, lhs_params = self.process_lhs(qn, connection)
        rhs, rhs_params = self.process_rhs(qn, connection)
        params = lhs_params + rhs_params
        return f"{lhs} LIKE ('%' || {rhs} || '%')", params

    SearchVectorExact.as_sqlite = search_vector_exact_as_sqlite

    orig_create_sql = PostgresIndex.create_sql

    def index_create_sql(self, model, schema_editor, using="", **kwargs):
        if schema_editor.connection.vendor == "sqlite":
            return super(PostgresIndex, self).create_sql(model, schema_editor, using="", **kwargs)
        return orig_create_sql(self, model, schema_editor, using=using, **kwargs)

    PostgresIndex.create_sql = index_create_sql
