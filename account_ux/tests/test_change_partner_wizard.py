from odoo import fields
from odoo.tests import TransactionCase, tagged

# Account type constants (match those in models and wizards)
ACCOUNT_TYPE_RECEIVABLE = "asset_receivable"


@tagged("post_install", "-at_install")
class TestChangePartnerWizard(TransactionCase):
    def test_change_partner_multi_moves(self):
        company = self.env.company
        Account = self.env["account.account"]
        Journal = self.env["account.journal"]

        # Ensure a general journal exists for the company
        journal = Journal.search([("type", "=", "general"), ("company_id", "=", company.id)], limit=1)
        if not journal:
            journal = Journal.create(
                {"name": "Test Journal", "code": "TST", "type": "general", "company_id": company.id}
            )

        # Ensure accounts for receivable and a counterpart exist
        receivable = Account.search(
            [("account_type", "=", ACCOUNT_TYPE_RECEIVABLE), ("company_ids", "in", company.id)], limit=1
        )
        if not receivable:
            receivable = Account.create(
                {
                    "name": "Test Receivable",
                    "code": "TR",
                    "account_type": ACCOUNT_TYPE_RECEIVABLE,
                    "company_ids": [(6, 0, [company.id])],
                }
            )

        other = Account.search([("account_type", "=", "income"), ("company_ids", "in", company.id)], limit=1)
        if not other:
            other = Account.create(
                {"name": "Other", "code": "OT", "account_type": "income", "company_ids": [(6, 0, [company.id])]}
            )

        # Partners
        p1 = self.env["res.partner"].create({"name": "P1"})
        p2 = self.env["res.partner"].create({"name": "P2"})
        pdest = self.env["res.partner"].create({"name": "PDest"})

        # Create two simple posted journal entries (one per partner)
        move1 = self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": journal.id,
                "date": fields.Date.context_today(self),
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "m1_p1",
                            "account_id": receivable.id,
                            "partner_id": p1.id,
                            "debit": 0.0,
                            "credit": 100.0,
                        },
                    ),
                    (0, 0, {"name": "m1_cnt", "account_id": other.id, "debit": 100.0, "credit": 0.0}),
                ],
            }
        )
        move1.action_post()

        move2 = self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": journal.id,
                "date": fields.Date.context_today(self),
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "m2_p2",
                            "account_id": receivable.id,
                            "partner_id": p2.id,
                            "debit": 0.0,
                            "credit": 50.0,
                        },
                    ),
                    (0, 0, {"name": "m2_cnt", "account_id": other.id, "debit": 50.0, "credit": 0.0}),
                ],
            }
        )
        move2.action_post()

        # Select the receivable lines from both moves
        lines = (move1.line_ids + move2.line_ids).filtered(lambda l: l.account_id == receivable)

        # Open the wizard with the selected lines and set destination partner
        Wizard = self.env["account.automatic.entry.wizard"].with_context(
            active_model="account.move.line", active_ids=lines.ids, default_action="change_partner"
        )
        wiz = Wizard.create({"partner_id": pdest.id, "journal_id": journal.id, "date": fields.Date.context_today(self)})

        # Execute the wizard action which should create and post the new move
        action = wiz.do_action()
        self.assertIn("res_id", action)
        new_move = self.env["account.move"].browse(action["res_id"])
        self.assertTrue(new_move, "No account.move was created by the wizard")

        # Move must be balanced
        total_debit = sum(new_move.line_ids.mapped("debit"))
        total_credit = sum(new_move.line_ids.mapped("credit"))
        self.assertAlmostEqual(total_debit, total_credit, msg="Generated move is not balanced")

        # Destination partner must appear on receivable account lines (one per original group)
        dest_lines = new_move.line_ids.filtered(lambda l: l.partner_id == pdest and l.account_id == receivable)
        self.assertEqual(
            len(dest_lines), 2, "Expected two destination lines on receivable account for the two source groups"
        )

        # Ensure original partners are represented in the generated move (source lines)
        for orig_p in (p1, p2):
            src = new_move.line_ids.filtered(lambda l: l.partner_id == orig_p and l.account_id == receivable)
            self.assertTrue(src, f"Source partner {orig_p.name} missing in generated move")
