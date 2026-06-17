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
    "IAS_QUT_PRM_MST",
    "IAS_QUT_PRM_DTL",
)

PROMO_FREE_COLUMNS = (
    "FREE_QTY",
    "FREE_ITM_QTY",
    "F_QTY",
    "GIFT_QTY",
    "BONUS_QTY",
    "FREE_I_CODE",
    "F_I_CODE",
    "FREE_ITM",
    "FREE_ITM_UNT",
)

PROMO_DISCOUNT_COLUMNS = (
    "DISC_PRCNT",
    "DISC_PERCENT",
    "DISC_PER",
    "DIS_PER",
    "DIS_PRCNT",
    "DISC_AMT",
    "DIS_AMT",
    "DISC_VALUE",
    "DISCOUNT_PER",
    "DISCOUNT_AMT",
    "DSCNT_PRCNT",
    "DSCNT_AMT",
    "QT_PRM_DISC_PRCNT",
    "QT_PRM_DISC_AMT",
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


def get_table_columns(cursor, schema, table_name):
    cursor.execute("""
        SELECT column_name
        FROM all_tab_columns
        WHERE owner = :owner
          AND table_name = :table_name
    """, {
        "owner": schema,
        "table_name": table_name,
    })

    return {row[0] for row in cursor.fetchall()}


def optional_selects(alias, available_columns, candidate_columns):
    return [
        f"{alias}.{column_name} AS {column_name}"
        for column_name in candidate_columns
        if column_name in available_columns
    ]


def has_positive_value(row, column_names):
    for column_name in column_names:
        value = row.get(column_name.lower())

        if value in (None, ""):
            continue

        try:
            if float(value) > 0:
                return True
        except (TypeError, ValueError):
            continue

    return False


def has_text_value(row, column_names):
    for column_name in column_names:
        value = row.get(column_name.lower())

        if value not in (None, ""):
            return True

    return False

def to_positive_number(value):
    if value in (None, ""):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    return number if number > 0 else None


def classify_promotion(row):
    free_item_code = row.get("qt_i_code")
    free_qty = to_positive_number(row.get("free_qty"))
    qt_qty = to_positive_number(row.get("qt_qty"))

    discount_value = to_positive_number(row.get("disc_amt_per"))
    discount_type = row.get("disc_type")

    if free_item_code or free_qty or qt_qty:
        return "free_quantity", "كمية مجانية"

    if discount_value or discount_type not in (None, ""):
        return "discount", "خصم"

    return "promotion", "عرض ترويجي"


def find_active_promotion(cursor, schema, i_code, itm_unt, barcode=None):
    sql = f"""
        SELECT *
        FROM (
            SELECT
                m.QUOT_NO,
                m.QUOT_SER,
                m.A_DESC,
                m.F_DATE,
                m.T_DATE,
                m.QT_PRM_TYPE,
                m.QT_PRM_METHOD,
                m.APPROVED,
                m.INACTIVE,

                d.I_CODE AS PROMO_I_CODE,
                d.ITM_UNT AS PROMO_ITM_UNT,
                d.BARCODE AS PROMO_BARCODE,
                d.F_QTY,
                d.T_QTY,
                d.F_AMT,
                d.T_AMT,
                d.DISC_TYPE,
                d.DISC_AMT_PER,
                d.QT_I_CODE,
                d.FREE_QTY,
                d.QT_QTY
            FROM {schema}.IAS_QUT_PRM_MST m
            JOIN {schema}.IAS_QUT_PRM_DTL d
                ON d.QUOT_SER = m.QUOT_SER
               AND d.QUOT_NO = m.QUOT_NO
            WHERE (
                    d.I_CODE = :i_code
                 OR (:barcode IS NOT NULL AND d.BARCODE = :barcode)
            )
              AND (:itm_unt IS NULL OR d.ITM_UNT = :itm_unt OR d.ITM_UNT IS NULL)
              AND NVL(m.INACTIVE, 0) = 0
              AND NVL(m.APPROVED, 0) = 1
              AND TRUNC(SYSDATE) BETWEEN TRUNC(NVL(m.F_DATE, SYSDATE))
                                      AND TRUNC(NVL(m.T_DATE, SYSDATE))
            ORDER BY m.T_DATE DESC, m.QUOT_NO DESC
        )
        WHERE ROWNUM <= 1
    """

    cursor.execute(sql, {
        "i_code": i_code,
        "itm_unt": itm_unt,
        "barcode": barcode,
    })

    rows = cursor.fetchall()

    if not rows:
        return None

    promotion = rows_to_dicts(cursor, rows)[0]
    promotion_type, promotion_label = classify_promotion(promotion)

    promotion["promotion_type"] = promotion_type
    promotion["promotion_label"] = promotion_label

    return promotion


def calculate_discount_prices(product, promotion):
    if not promotion:
        return

    try:
        price = float(product.get("i_price") or 0)
        tax_percent = float(product.get("total_tax_prcnt") or 0)
        discount_value = float(promotion.get("disc_amt_per") or 0)
    except (TypeError, ValueError):
        return

    if discount_value <= 0:
        return

    # نفترض هنا أن DISC_AMT_PER نسبة خصم
    discount_amount = round(price * discount_value / 100, 2)
    price_after_discount = round(max(price - discount_amount, 0), 2)
    total_after_discount = round(
        price_after_discount + (price_after_discount * tax_percent / 100),
        2,
    )

    product["discount_percent"] = discount_value
    product["discount_amount"] = discount_amount
    product["price_after_discount"] = price_after_discount
    product["total_after_discount"] = total_after_discount
    


def attach_promotions(cursor, schema, products, barcode):
    for product in products:
        promotion = find_active_promotion(
            cursor,
            schema,
            product.get("i_code"),
            product.get("itm_unt"),
            barcode=barcode,
        )

        product["has_promotion"] = promotion is not None
        product["promotion_type"] = promotion["promotion_type"] if promotion else None
        product["promotion_label"] = promotion["promotion_label"] if promotion else None
        product["promotion"] = promotion
        if promotion and product["promotion_type"] == "discount":
            calculate_discount_prices(product, promotion)
        

    return products


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
                    products = rows_to_dicts(cursor, rows)

                    return attach_promotions(cursor, schema, products, barcode)
                

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