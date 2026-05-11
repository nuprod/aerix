from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestExtractPartner(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.AccountMove = cls.env["account.move"]
        cls.internal_domain = cls.env["mail.alias.domain"].create({
            "name": "aerix-systems.com",
        })
        cls.coquille_partner = cls.env["res.partner"].create({
            "name": "achat@aerix-systems.com",
            "email": "achat@aerix-systems.com",
        })
        cls.external_partner = cls.env["res.partner"].create({
            "name": "External Vendor",
            "email": "billing@externalvendor.com",
            "supplier_rank": 5,
        })

    # --- _nu_is_internal_sender tests ---

    def test_internal_domain_returns_true(self):
        move = self.AccountMove.new({})
        self.assertTrue(
            move._nu_is_internal_sender("achat@aerix-systems.com")
        )

    def test_external_domain_returns_false(self):
        move = self.AccountMove.new({})
        self.assertFalse(
            move._nu_is_internal_sender("billing@externalvendor.com")
        )

    def test_with_name_wrapper(self):
        move = self.AccountMove.new({})
        self.assertTrue(
            move._nu_is_internal_sender(
                '"Achat AERIX" <achat@aerix-systems.com>'
            )
        )

    def test_case_insensitive_domain(self):
        move = self.AccountMove.new({})
        self.assertTrue(
            move._nu_is_internal_sender("Achat@AERIX-Systems.COM")
        )

    def test_empty_email_returns_false(self):
        move = self.AccountMove.new({})
        self.assertFalse(move._nu_is_internal_sender(""))
        self.assertFalse(move._nu_is_internal_sender(None))

    def test_garbage_email_returns_false(self):
        move = self.AccountMove.new({})
        self.assertFalse(move._nu_is_internal_sender("not an email"))

    def test_subdomain_not_matched(self):
        # mail.alias.domain stores exact domain only; sub.aerix-systems.com
        # is treated as external unless explicitly added.
        move = self.AccountMove.new({})
        self.assertFalse(
            move._nu_is_internal_sender("foo@sub.aerix-systems.com")
        )

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
            "from": email_from,
            "email_from": email_from,
            "to": "achats@aerix.odoo.com",
            "subject": "Fwd: facture",
            "body": "",
            "message_id": "<test@example.com>",
        }

    def test_message_new_clears_internal_partner_on_purchase(self):
        # Native message_new will resolve from='achat@aerix-systems.com'
        # to coquille_partner (no user_ids -> escapes native filter).
        # Our override must clear it because the domain is internal.
        journal = self._purchase_journal()
        move = self.AccountMove.message_new(
            self._make_msg("achat@aerix-systems.com"),
            custom_values={
                "journal_id": journal.id,
                "move_type": "in_invoice",
            },
        )
        self.assertFalse(
            move.partner_id,
            "partner_id should be cleared when resolved to a partner on "
            "an internal alias domain",
        )

    def test_message_new_keeps_external_partner_on_purchase(self):
        # Native message_new will resolve from='billing@externalvendor.com'
        # to external_partner; our override leaves it alone.
        journal = self._purchase_journal()
        move = self.AccountMove.message_new(
            self._make_msg("billing@externalvendor.com"),
            custom_values={
                "journal_id": journal.id,
                "move_type": "in_invoice",
            },
        )
        self.assertEqual(move.partner_id, self.external_partner)

    def test_message_new_internal_sender_on_sale_journal_kept(self):
        # Sale journal: our override does not apply.
        journal = self._sale_journal()
        move = self.AccountMove.message_new(
            self._make_msg("achat@aerix-systems.com"),
            custom_values={
                "journal_id": journal.id,
                "move_type": "out_invoice",
            },
        )
        # Whatever the native resolved (coquille or False), the move
        # should NOT have been cleared by our override. To assert that
        # specifically, verify partner_id is the coquille (set by native).
        self.assertEqual(move.partner_id, self.coquille_partner)

    def test_message_new_no_resolution_is_idempotent(self):
        # If the native cannot resolve any partner, the override should
        # not crash and should leave partner_id False.
        journal = self._purchase_journal()
        move = self.AccountMove.message_new(
            self._make_msg("nobody@unknown.example"),
            custom_values={
                "journal_id": journal.id,
                "move_type": "in_invoice",
            },
        )
        self.assertFalse(move.partner_id)
