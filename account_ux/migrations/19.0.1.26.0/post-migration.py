from openupgradelib import openupgrade

# Same domain as security/account_ux_security.xml. It lives here too because the rule is a
# core record that can be marked as noupdate, so the data file does not always reach an
# already installed database — the precedent is migrations/19.0.1.5.0.
NEW_DOMAIN = """[
    '|',
    ('company_id', 'in', company_ids),
    '&',
    ('company_id', 'parent_of', company_ids),
    '|',
    ('shared_to_branches', '=', 'all'),
    '&',
    ('shared_to_branches', '=', 'legal_entity'),
    ('legal_entity_root_id', 'in', user.company_id.browse(company_ids).legal_entity_root_id.ids)
]"""


@openupgrade.migrate()
def migrate(env, version):
    """Fill in the scope of the fiscal positions, and teach the journal record rule the scope.

    The field is new on ``account.fiscal.position``, so the positions that already exist have
    it empty, which reads as *not shared* — they would stop autodetecting in the branches
    where they autodetect today. They get *all branches*, which is exactly what they did
    before the field existed; narrowing one to the legal entity is a decision per position.

    And without rewriting the rule it keeps comparing ``shared_to_branches`` against ``True``,
    which after the conversion matches nothing, so a branch user stops seeing the journals its
    parent shares with it.
    """
    openupgrade.logged_query(
        env.cr,
        "UPDATE account_fiscal_position SET shared_to_branches = 'all' WHERE shared_to_branches IS NULL",
    )

    rule = env.ref("account.journal_comp_rule", raise_if_not_found=False)
    if not rule:
        return

    # write ignora noupdate
    rule.write({"domain_force": NEW_DOMAIN})
