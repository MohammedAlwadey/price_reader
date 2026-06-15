import logging
import re

import oracledb

from pricing.models import OracleSettings

logger = logging.getLogger(__name__)

_client_initialized = False
_pool = None
_pool_key = None

REQUIRED_TABLES = (
    "IAS_ITM_UNT_BARCODE",
    "IAS_ITM_MST",
    "IAS_ITEM_PRICE",
    "IAS_PRICING_LEVELS",
    "GNR_TAX_ITM",
)


def validate_schema_name(schema_name):
    schema_name = schema_name.upper().strip()

    if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,29}", schema_name):
        raise ValueError("Invalid Oracle schema name")

    return schema_name


def get_active_settings():
    return OracleSettings.objects.filter(is_active=True).first()


def init_client_once(config):
    global _client_initialized

    if _client_initialized:
        return

    if not config.oracle_client_lib_dir:
        raise RuntimeError("Oracle Client path is required for Thick mode")

    oracledb.init_oracle_client(lib_dir=config.oracle_client_lib_dir)
    _client_initialized = True


def get_dsn(config):
    if config.connection_mode == "sid":
        if not config.sid:
            raise RuntimeError("Oracle SID is required")
        return oracledb.makedsn(config.host, config.port, sid=config.sid)

    if not config.service_name:
        raise RuntimeError("Oracle service name is required")

    return oracledb.makedsn(
        config.host,
        config.port,
        service_name=config.service_name,
    )


def get_pool(config):
    global _pool, _pool_key

    init_client_once(config)

    current_key = (
        config.host,
        config.port,
        config.connection_mode,
        config.sid,
        config.service_name,
        config.username,
        config.password,
        config.oracle_client_lib_dir,
    )

    if _pool is None or _pool_key != current_key:
        _pool = oracledb.create_pool(
            user=config.username,
            password=config.password,
            dsn=get_dsn(config),
            min=2,
            max=5,
            increment=1,
        )
        _pool_key = current_key

    return _pool


def rows_to_dicts(cursor, rows):
    columns = [col[0].lower() for col in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def get_oracle_error_code(exc):
    if exc.args:
        return getattr(exc.args[0], "code", None)

    return None


def find_unavailable_tables(connection, schema):
    unavailable_tables = []

    with connection.cursor() as cursor:
        for table_name in REQUIRED_TABLES:
            full_table_name = f"{schema}.{table_name}"

            try:
                cursor.execute(f"SELECT 1 FROM {full_table_name} WHERE 1 = 0")
            except oracledb.DatabaseError as exc:
                if get_oracle_error_code(exc) == 942 or "ORA-00942" in str(exc):
                    unavailable_tables.append(full_table_name)
                else:
                    unavailable_tables.append(f"{full_table_name} - {exc}")

    return unavailable_tables


def find_price_by_barcode(barcode):
    config = get_active_settings()

    if not config:
        raise RuntimeError("Oracle settings are not configured")

    schema = validate_schema_name(config.schema_name)

    sql = f"""
        SELECT
            b.I_CODE,
            b.ITM_UNT,
            b.EXPIRE_DATE,
            b.BATCH_NO,
            m.I_NAME,
            m.I_E_NAME,
            m.ITEM_SIZE,
            m.ITEM_TYPE,
            p.I_PRICE,
            pl.A_CY,
            SUM(NVL(t.TAX_PRCNT, 0)) AS TOTAL_TAX_PRCNT,
            ROUND(p.I_PRICE + (p.I_PRICE * SUM(NVL(t.TAX_PRCNT, 0)) / 100), 2) AS TOTAL_WITH_TAX
        FROM {schema}.IAS_ITM_UNT_BARCODE b
        JOIN {schema}.IAS_ITM_MST m ON m.I_CODE = b.I_CODE
        JOIN {schema}.IAS_ITEM_PRICE p ON p.I_CODE = b.I_CODE
            AND p.ITM_UNT = b.ITM_UNT
            AND p.LEV_NO = :pricing_level
        JOIN {schema}.IAS_PRICING_LEVELS pl ON pl.LEV_NO = p.LEV_NO
        LEFT JOIN {schema}.GNR_TAX_ITM t ON t.I_CODE = b.I_CODE
        WHERE b.BARCODE = :barcode
        GROUP BY
            b.I_CODE, b.ITM_UNT, b.EXPIRE_DATE, b.BATCH_NO,
            m.I_NAME, m.I_E_NAME, m.ITEM_SIZE, m.ITEM_TYPE,
            p.I_PRICE, pl.A_CY
    """

    try:
        pool = get_pool(config)

        with pool.acquire() as connection:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(sql, {
                        "barcode": barcode,
                        "pricing_level": config.pricing_level,
                    })
                    rows = cursor.fetchall()
                    return rows_to_dicts(cursor, rows)

            except oracledb.DatabaseError as exc:
                if get_oracle_error_code(exc) == 942 or "ORA-00942" in str(exc):
                    unavailable_tables = find_unavailable_tables(connection, schema)

                    print("Oracle missing/inaccessible tables:")
                    for table_name in unavailable_tables:
                        print(table_name)

                    logger.error(
                        "Oracle missing/inaccessible tables: %s",
                        ", ".join(unavailable_tables),
                    )

                    if unavailable_tables:
                        unavailable_text = ", ".join(unavailable_tables)
                    else:
                        unavailable_text = "unknown table or view"

                    raise RuntimeError(
                        "Oracle table/view does not exist or SELECT permission is missing: "
                        + unavailable_text
                    ) from exc

                raise

    except Exception:
        logger.exception("Oracle barcode lookup failed")
        raise