import logging

from odoo.upgrade import util
from openupgradelib import openupgrade

_logger = logging.getLogger(__name__)

# La crea pre_upgrade_scripts/180_190/stock_account_ux.py antes del ``-u``.
BACKUP_TABLE = "stock_move_account_move_id_bu"


@openupgrade.migrate()
def migrate(env, version):
    """Limpiar ``account_stock_expense_id`` en bases ya instaladas"""
    openupgrade.logged_query(
        env.cr,
        "UPDATE account_account SET account_stock_expense_id = NULL WHERE account_stock_expense_id IS NOT NULL",
    )

    _logger.info("Running 'stock_account_ux' post-migration for version %s", version)

    if not util.table_exists(env.cr, BACKUP_TABLE):
        _logger.warning(
            "No existe la tabla backup %s: no se reenganchó el asiento histórico "
            "a stock.move. Revisar el riesgo de doble valorización en el cierre "
            "periódico.",
            BACKUP_TABLE,
        )
        return

    # Reenganchar el asiento de valorización histórico (v18) a ``stock.move``.

    # El pre-upgrade script respaldó en ``stock_move_account_move_id_bu`` el mapa
    # movimiento -> asiento tomado de ``stock.valuation.layer`` (v18), justo antes
    # de que el core dropeara esa tabla. Acá, ya con la columna
    # ``stock_move.account_move_id`` creada por el upgrade de ``stock_account``,
    # volcamos ese asiento al movimiento (sólo si quedó sin asiento).

    # Con eso ``related_account_move_id`` (stock_account_ux) vuelve a apuntar al
    # asiento que valoró el movimiento y el cierre periódico deja de re-valorizar
    # esos movimientos, evitando la doble contabilización.
    if not util.column_exists(env.cr, "stock_move", "account_move_id"):
        _logger.warning("stock_move.account_move_id no existe; se omite el reenganche del " "asiento histórico.")
        return

    env.cr.execute(
        """
        UPDATE stock_move sm
           SET account_move_id = bu.account_move_id
          FROM %s bu
         WHERE bu.stock_move_id = sm.id
           AND sm.account_move_id IS NULL
        """
        % BACKUP_TABLE
    )
    _logger.info(
        "Reenganchados %s asientos históricos en stock_move.account_move_id",
        env.cr.rowcount,
    )

    # Volcar el valor del asiento histórico al movimiento. En v19 el valor vive
    # en ``stock_move.value`` (stored); reenganchar ``account_move_id`` no lo
    # recalcula, así que lo seteamos desde la partida de valorización del asiento.
    # Filtramos por ``product_id`` para aislar la pata de débito de ESTE producto
    # (así funciona aunque un asiento agrupe varios movimientos de distinto producto).
    env.cr.execute(
        """
        UPDATE stock_move sm
           SET value = sub.value
          FROM (
                SELECT bu.stock_move_id,
                       SUM(aml.debit) AS value
                  FROM %s bu
                  JOIN stock_move m2 ON m2.id = bu.stock_move_id
                  JOIN account_move_line aml
                    ON aml.move_id = bu.account_move_id
                   AND aml.product_id = m2.product_id
                 GROUP BY bu.stock_move_id
               ) sub
         WHERE sm.id = sub.stock_move_id
        """
        % BACKUP_TABLE
    )
    _logger.info(
        "Actualizado value en %s movimientos desde el asiento histórico",
        env.cr.rowcount,
    )

    # Marcar TODOS los movimientos que tenían valorización en la v18 (los del
    # backup), tengan o no ``account_move_id`` ya seteado. La valorización de
    # esos movimientos ya se contabilizó en la versión anterior, así que al
    # facturarlos en v19 no debe re-generarse el COGS anglosajón. Lo consume la
    # override de ``account.move._stock_account_prepare_realtime_out_lines_vals``.
    env.cr.execute(
        """
        UPDATE stock_move sm
           SET stock_valuation_migrated = TRUE
          FROM %s bu
         WHERE bu.stock_move_id = sm.id
        """
        % BACKUP_TABLE
    )
    _logger.info(
        "Marcados %s movimientos con stock_valuation_migrated=True",
        env.cr.rowcount,
    )

    env.cr.execute("DROP TABLE IF EXISTS %s" % BACKUP_TABLE)
    _logger.info("Eliminada la tabla backup %s", BACKUP_TABLE)
