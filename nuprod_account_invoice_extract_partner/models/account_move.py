from odoo import api, models, tools


class AccountMove(models.Model):
    _inherit = "account.move"

    def _nu_is_internal_sender(self, email_from):
        """True if email_from resolves to an active, non-portal employee.

        Used both at message_new (drop the forwarder partner_id) and at
        _save_form (force OCR re-match when the current partner_id is an
        internal user).
        """
        if not email_from:
            return False
        parsed = tools.email_normalize(email_from)
        if not parsed:
            return False
        user = self.env["res.users"].sudo().search(
            [
                ("active", "=", True),
                ("share", "=", False),
                ("partner_id.email_normalized", "=", parsed),
            ],
            limit=1,
        )
        return bool(user)
