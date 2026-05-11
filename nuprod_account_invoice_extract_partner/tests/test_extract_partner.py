from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestExtractPartner(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.AccountMove = cls.env["account.move"]
        cls.internal_user = cls.env["res.users"].create({
            "name": "Internal User",
            "login": "internal@aerix.fr",
            "email": "internal@aerix.fr",
        })
        cls.portal_user = cls.env["res.users"].create({
            "name": "Portal User",
            "login": "portal@vendor.com",
            "email": "portal@vendor.com",
            "group_ids": [(6, 0, [cls.env.ref("base.group_portal").id])],
        })
        cls.external_partner = cls.env["res.partner"].create({
            "name": "External Vendor",
            "email": "billing@vendor.com",
        })

    def test_internal_sender_returns_true(self):
        move = self.AccountMove.new({})
        self.assertTrue(move._nu_is_internal_sender("internal@aerix.fr"))

    def test_internal_sender_with_name_wrapper(self):
        move = self.AccountMove.new({})
        self.assertTrue(
            move._nu_is_internal_sender('"Internal" <internal@aerix.fr>')
        )

    def test_portal_user_returns_false(self):
        # share=True users (portal) must not be treated as internal
        self.assertTrue(self.portal_user.share)
        move = self.AccountMove.new({})
        self.assertFalse(move._nu_is_internal_sender("portal@vendor.com"))

    def test_inactive_user_returns_false(self):
        self.internal_user.active = False
        move = self.AccountMove.new({})
        self.assertFalse(move._nu_is_internal_sender("internal@aerix.fr"))

    def test_external_partner_only_returns_false(self):
        # A partner with an email but no res.users must not be internal
        move = self.AccountMove.new({})
        self.assertFalse(move._nu_is_internal_sender("billing@vendor.com"))

    def test_empty_email_returns_false(self):
        move = self.AccountMove.new({})
        self.assertFalse(move._nu_is_internal_sender(""))
        self.assertFalse(move._nu_is_internal_sender(None))

    def test_garbage_email_returns_false(self):
        move = self.AccountMove.new({})
        self.assertFalse(move._nu_is_internal_sender("not an email"))

    # --- message_new tests ---

    def _purchase_journal(self):
        return self.env["account.journal"].search(
            [("type", "=", "purchase")], limit=1,
        )

    def _sale_journal(self):
        return self.env["account.journal"].search(
            [("type", "=", "sale")], limit=1,
        )

    def _make_msg(self, email_from):
        return {
            "email_from": email_from,
            "to": "achats@aerix.odoo.com",
            "subject": "Fwd: facture",
            "body": "",
            "message_id": "<test@example.com>",
        }

    def test_message_new_drops_internal_sender_on_purchase_journal(self):
        journal = self._purchase_journal()
        custom_values = {
            "journal_id": journal.id,
            "move_type": "in_invoice",
            "partner_id": self.internal_user.partner_id.id,
        }
        move = self.AccountMove.message_new(
            self._make_msg("internal@aerix.fr"), custom_values=custom_values,
        )
        self.assertFalse(
            move.partner_id,
            "partner_id should be dropped when an internal user forwards a "
            "bill to the purchase alias",
        )

    def test_message_new_keeps_external_sender_on_purchase_journal(self):
        journal = self._purchase_journal()
        custom_values = {
            "journal_id": journal.id,
            "move_type": "in_invoice",
            "partner_id": self.external_partner.id,
        }
        move = self.AccountMove.message_new(
            self._make_msg("billing@vendor.com"), custom_values=custom_values,
        )
        self.assertEqual(move.partner_id, self.external_partner)

    def test_message_new_keeps_portal_user_partner_on_purchase_journal(self):
        journal = self._purchase_journal()
        custom_values = {
            "journal_id": journal.id,
            "move_type": "in_invoice",
            "partner_id": self.portal_user.partner_id.id,
        }
        move = self.AccountMove.message_new(
            self._make_msg("portal@vendor.com"), custom_values=custom_values,
        )
        self.assertEqual(move.partner_id, self.portal_user.partner_id)

    def test_message_new_keeps_internal_sender_on_sale_journal(self):
        journal = self._sale_journal()
        custom_values = {
            "journal_id": journal.id,
            "move_type": "out_invoice",
            "partner_id": self.internal_user.partner_id.id,
        }
        move = self.AccountMove.message_new(
            self._make_msg("internal@aerix.fr"), custom_values=custom_values,
        )
        self.assertEqual(
            move.partner_id, self.internal_user.partner_id,
            "Sale journal must not strip the partner_id of an internal user "
            "(out of scope for this module)",
        )

    def test_message_new_drops_internal_sender_with_journal_in_context(self):
        # Some mail.alias setups pass the journal via default_journal_id
        # context instead of custom_values
        journal = self._purchase_journal()
        custom_values = {
            "move_type": "in_invoice",
            "partner_id": self.internal_user.partner_id.id,
        }
        move = self.AccountMove.with_context(
            default_journal_id=journal.id,
        ).message_new(
            self._make_msg("internal@aerix.fr"), custom_values=custom_values,
        )
        self.assertFalse(move.partner_id)
