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

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        custom_values = dict(custom_values or {})
        journal_id = (
            custom_values.get("journal_id")
            or self.env.context.get("default_journal_id")
        )
        journal = (
            self.env["account.journal"].browse(journal_id)
            if journal_id else self.env["account.journal"]
        )
        if (
            journal.type == "purchase"
            and self._nu_is_internal_sender(msg_dict.get("email_from"))
        ):
            custom_values.pop("partner_id", None)
        return super().message_new(msg_dict, custom_values=custom_values)
