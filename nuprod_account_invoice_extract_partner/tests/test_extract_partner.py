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
