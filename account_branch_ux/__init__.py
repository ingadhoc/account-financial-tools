from . import models
from odoo.tools.misc import unquote


def to_record_ids(records):
    """Convert recordset to list of IDs."""
    if hasattr(records, "ids"):
        return records.ids
    elif isinstance(records, (list, tuple)):
        return [int(r) if not isinstance(r, int) else r for r in records]
    elif isinstance(records, int):
        return [records]
    return []


def check_company_domain_child_of(self, companies):
    """Return a domain that allows records if:
    - record.company_id = False, or
    - record.company_id is a child of any of the given companies.
    """
    if isinstance(companies, str):
        companies = unquote("main_company_id")
        return ["|", ("company_id", "=", False), ("company_id", "child_of", companies)]

    companies = to_record_ids(companies)
    if not companies:
        return [("company_id", "=", False)]

    return [
        (
            "company_id",
            "in",
            [
                int(parent)
                for rec in self.env["res.company"].sudo().browse(companies)
                for parent in rec.parent_path.split("/")[:-1]
            ]
            + [False],
        )
    ]
