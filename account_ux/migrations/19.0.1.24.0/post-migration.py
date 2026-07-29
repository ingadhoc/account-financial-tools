from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    """Recompute branch_order with the fixed compute.

    Values stored before the fix counted archived child companies, so journals
    of sibling companies sat in different tiers and the journal ordering was
    arbitrary. There is no trigger that fixes them, since archiving a company
    never recomputed the field. Recompute every journal, archived included:
    now that the compute filters on active by itself, active_test no longer
    changes the resulting value.
    """
    journals = env["account.journal"].with_context(active_test=False).search([])
    journals.invalidate_recordset(["branch_order"])
    journals._compute_branch_order()
    journals.flush_recordset(["branch_order"])
