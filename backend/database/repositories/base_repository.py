"""
Base Repository with common database operations
"""
import json
import asyncpg
import time
import logging
from datetime import datetime, timezone
from typing import Optional, List, Any, Dict
from ..connection import get_db, dict_from_row, rows_to_dicts

logger = logging.getLogger(__name__)

# Import debug utilities
try:
    from utils.debug import Loggers, log_db_query
    _debug_available = True
except ImportError:
    _debug_available = False


class BaseRepository:
    """Base class for all repositories with common CRUD operations"""

    def __init__(self, table_name: str):
        self.table_name = table_name

    def _quote_identifier(self, identifier: str) -> str:
        """Quote a column/table identifier for PostgreSQL to preserve case"""
        # Double any existing quotes and wrap in quotes
        return f'"{identifier}"'

    async def _get_db(self) -> asyncpg.Pool:
        """Get database connection pool"""
        return await get_db()

    def _serialize_json_fields(self, data: dict, json_fields: List[str]) -> dict:
        """Serialize JSON fields to strings"""
        result = data.copy()
        for field in json_fields:
            if field in result and result[field] is not None:
                if not isinstance(result[field], str):
                    result[field] = json.dumps(result[field])
        return result

    def _deserialize_json_fields(self, data: dict, json_fields: List[str]) -> dict:
        """Deserialize JSON strings to objects"""
        if data is None:
            return None
        result = data.copy()
        for field in json_fields:
            if field in result and result[field] is not None:
                if isinstance(result[field], str):
                    try:
                        result[field] = json.loads(result[field])
                    except json.JSONDecodeError:
                        pass
        return result

    def _convert_datetime_strings(self, data: dict) -> dict:
        """Convert ISO datetime strings to Python datetime objects for asyncpg.

        PostgreSQL TIMESTAMP columns (without timezone) expect naive datetime objects.
        This method converts ISO strings to naive UTC datetimes for compatibility.
        """
        result = data.copy()
        for key, value in result.items():
            if isinstance(value, str) and len(value) >= 19:
                # Check if it looks like an ISO datetime string
                # Format: 2026-01-19T16:33:22.599811+00:00 or 2026-01-19T16:33:22
                if 'T' in value and value[4] == '-' and value[7] == '-':
                    try:
                        # Try parsing with timezone
                        if '+' in value or value.endswith('Z'):
                            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                        else:
                            dt = datetime.fromisoformat(value)
                        # Convert to UTC if timezone-aware, then make naive
                        # PostgreSQL TIMESTAMP columns require naive datetimes
                        if dt.tzinfo is not None:
                            # Convert to UTC first, then remove timezone info
                            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
                        result[key] = dt
                    except (ValueError, TypeError):
                        # Not a valid datetime string, keep as-is
                        pass
            elif isinstance(value, datetime):
                # Handle datetime objects passed directly (not as strings)
                if value.tzinfo is not None:
                    # Convert to UTC and make naive for PostgreSQL TIMESTAMP columns
                    result[key] = value.astimezone(timezone.utc).replace(tzinfo=None)
        return result

    async def find_one(
        self,
        conditions: Dict[str, Any],
        exclude_fields: List[str] = None,
        json_fields: List[str] = None
    ) -> Optional[dict]:
        """Find a single record matching conditions"""
        start_time = time.time()
        pool = await self._get_db()

        where_clauses = []
        values = []
        for i, (key, value) in enumerate(conditions.items(), 1):
            where_clauses.append(f"{self._quote_identifier(key)} = ${i}")
            values.append(value)

        where_sql = " AND ".join(where_clauses)
        query = f"SELECT * FROM {self.table_name} WHERE {where_sql} LIMIT 1"

        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(query, *values)

            duration_ms = (time.time() - start_time) * 1000
            if _debug_available:
                log_db_query("SELECT", self.table_name, duration_ms,
                            rows_affected=1 if row else 0,
                            query_params=conditions)

            if row is None:
                return None

            result = dict_from_row(row)

            # Exclude fields if specified
            if exclude_fields:
                for field in exclude_fields:
                    result.pop(field, None)

            # Deserialize JSON fields
            if json_fields:
                result = self._deserialize_json_fields(result, json_fields)

            return result
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            if _debug_available:
                log_db_query("SELECT", self.table_name, duration_ms, error=str(e))
            raise

    async def find_many(
        self,
        conditions: Dict[str, Any] = None,
        exclude_fields: List[str] = None,
        json_fields: List[str] = None,
        order_by: str = None,
        order_dir: str = "ASC",
        limit: int = None,
        offset: int = None
    ) -> List[dict]:
        """Find multiple records matching conditions"""
        start_time = time.time()
        pool = await self._get_db()

        query = f"SELECT * FROM {self.table_name}"
        values = []

        if conditions:
            where_clauses = []
            param_count = 1

            for key, value in conditions.items():
                quoted_key = self._quote_identifier(key)
                if isinstance(value, dict):
                    # Handle operators like $in, $gte, $lte
                    for op, op_value in value.items():
                        if op == "$in":
                            placeholders = ",".join([f"${param_count + i}" for i in range(len(op_value))])
                            where_clauses.append(f"{quoted_key} IN ({placeholders})")
                            values.extend(op_value)
                            param_count += len(op_value)
                        elif op == "$gte":
                            where_clauses.append(f"{quoted_key} >= ${param_count}")
                            values.append(op_value)
                            param_count += 1
                        elif op == "$lte":
                            where_clauses.append(f"{quoted_key} <= ${param_count}")
                            values.append(op_value)
                            param_count += 1
                        elif op == "$ne":
                            where_clauses.append(f"{quoted_key} != ${param_count}")
                            values.append(op_value)
                            param_count += 1
                        elif op == "$like":
                            where_clauses.append(f"{quoted_key} LIKE ${param_count}")
                            values.append(op_value)
                            param_count += 1
                else:
                    where_clauses.append(f"{quoted_key} = ${param_count}")
                    values.append(value)
                    param_count += 1

            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)

        if order_by:
            query += f" ORDER BY {order_by} {order_dir}"

        if limit:
            query += f" LIMIT {limit}"

        if offset:
            query += f" OFFSET {offset}"

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(query, *values)

            duration_ms = (time.time() - start_time) * 1000
            if _debug_available:
                log_db_query("SELECT_MANY", self.table_name, duration_ms,
                            rows_affected=len(rows),
                            query_params=conditions)

            results = rows_to_dicts(rows)

            # Process each result
            processed = []
            for result in results:
                # Exclude fields
                if exclude_fields:
                    for field in exclude_fields:
                        result.pop(field, None)

                # Deserialize JSON fields
                if json_fields:
                    result = self._deserialize_json_fields(result, json_fields)

                processed.append(result)

            return processed
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            if _debug_available:
                log_db_query("SELECT_MANY", self.table_name, duration_ms, error=str(e))
            raise

    async def insert(
        self,
        data: dict,
        json_fields: List[str] = None
    ) -> dict:
        """Insert a new record"""
        start_time = time.time()
        pool = await self._get_db()

        # Convert datetime strings to datetime objects for asyncpg
        data = self._convert_datetime_strings(data)

        # Serialize JSON fields
        if json_fields:
            data = self._serialize_json_fields(data, json_fields)

        columns = ", ".join([self._quote_identifier(k) for k in data.keys()])
        placeholders = ", ".join([f"${i+1}" for i in range(len(data))])
        values = list(data.values())

        query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"

        try:
            async with pool.acquire() as conn:
                await conn.execute(query, *values)

            duration_ms = (time.time() - start_time) * 1000
            if _debug_available:
                log_db_query("INSERT", self.table_name, duration_ms,
                            rows_affected=1,
                            query_params={"id": data.get("id")})

            return data
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            if _debug_available:
                log_db_query("INSERT", self.table_name, duration_ms, error=str(e))
            raise

    async def update(
        self,
        conditions: Dict[str, Any],
        data: dict,
        json_fields: List[str] = None
    ) -> int:
        """Update records matching conditions"""
        start_time = time.time()
        pool = await self._get_db()

        # Convert datetime strings to datetime objects for asyncpg
        data = self._convert_datetime_strings(data)

        # Serialize JSON fields
        if json_fields:
            data = self._serialize_json_fields(data, json_fields)

        set_clauses = []
        values = []
        param_count = 1

        for key, value in data.items():
            set_clauses.append(f"{self._quote_identifier(key)} = ${param_count}")
            values.append(value)
            param_count += 1

        where_clauses = []
        for key, value in conditions.items():
            where_clauses.append(f"{self._quote_identifier(key)} = ${param_count}")
            values.append(value)
            param_count += 1

        set_sql = ", ".join(set_clauses)
        where_sql = " AND ".join(where_clauses)

        query = f"UPDATE {self.table_name} SET {set_sql} WHERE {where_sql}"

        try:
            async with pool.acquire() as conn:
                result = await conn.execute(query, *values)

            # Parse rowcount from result string (e.g., "UPDATE 1")
            rowcount = int(result.split()[-1]) if result else 0

            duration_ms = (time.time() - start_time) * 1000
            if _debug_available:
                log_db_query("UPDATE", self.table_name, duration_ms,
                            rows_affected=rowcount,
                            query_params=conditions)

            return rowcount
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            if _debug_available:
                log_db_query("UPDATE", self.table_name, duration_ms, error=str(e))
            raise

    async def upsert(
        self,
        conditions: Dict[str, Any],
        data: dict,
        json_fields: List[str] = None
    ) -> dict:
        """Insert or update a record"""
        existing = await self.find_one(conditions)

        if existing:
            await self.update(conditions, data, json_fields)
            return {**existing, **data}
        else:
            full_data = {**conditions, **data}
            await self.insert(full_data, json_fields)
            return full_data

    async def delete(self, conditions: Dict[str, Any]) -> int:
        """Delete records matching conditions"""
        start_time = time.time()
        pool = await self._get_db()

        where_clauses = []
        values = []
        param_count = 1

        for key, value in conditions.items():
            where_clauses.append(f"{self._quote_identifier(key)} = ${param_count}")
            values.append(value)
            param_count += 1

        where_sql = " AND ".join(where_clauses)
        query = f"DELETE FROM {self.table_name} WHERE {where_sql}"

        try:
            async with pool.acquire() as conn:
                result = await conn.execute(query, *values)

            # Parse rowcount from result string (e.g., "DELETE 1")
            rowcount = int(result.split()[-1]) if result else 0

            duration_ms = (time.time() - start_time) * 1000
            if _debug_available:
                log_db_query("DELETE", self.table_name, duration_ms,
                            rows_affected=rowcount,
                            query_params=conditions)

            return rowcount
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            if _debug_available:
                log_db_query("DELETE", self.table_name, duration_ms, error=str(e))
            raise

    async def count(self, conditions: Dict[str, Any] = None) -> int:
        """Count records matching conditions"""
        pool = await self._get_db()

        query = f"SELECT COUNT(*) as count FROM {self.table_name}"
        values = []

        if conditions:
            where_clauses = []
            param_count = 1

            for key, value in conditions.items():
                quoted_key = self._quote_identifier(key)
                if isinstance(value, dict):
                    for op, op_value in value.items():
                        if op == "$ne":
                            where_clauses.append(f"{quoted_key} != ${param_count}")
                            values.append(op_value)
                            param_count += 1
                        elif op == "$gte":
                            where_clauses.append(f"{quoted_key} >= ${param_count}")
                            values.append(op_value)
                            param_count += 1
                        elif op == "$lte":
                            where_clauses.append(f"{quoted_key} <= ${param_count}")
                            values.append(op_value)
                            param_count += 1
                else:
                    where_clauses.append(f"{quoted_key} = ${param_count}")
                    values.append(value)
                    param_count += 1

            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)

        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, *values)

        return row[0] if row else 0

    async def execute_raw(self, query: str, values: List[Any] = None) -> List[dict]:
        """Execute a raw SQL query"""
        pool = await self._get_db()

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *(values or []))

        return rows_to_dicts(rows)
