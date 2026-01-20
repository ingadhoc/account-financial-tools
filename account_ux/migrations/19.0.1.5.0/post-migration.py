from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    """
    Update account.journal_comp_rule domain_force
    even if the rule is marked as noupdate.
    """

    # XML-ID de la regla original
    rule = env.ref("account.journal_comp_rule", raise_if_not_found=False)

    if not rule:
        return

    new_domain = """[
        '|',
        ('company_id', 'in', company_ids),
        '&',
        ('company_id', 'parent_of', company_ids),
        ('shared_to_branches', '=', True)
    ]"""

    # write ignora noupdate
    rule.write(
        {
            "domain_force": new_domain,
        }
    )
