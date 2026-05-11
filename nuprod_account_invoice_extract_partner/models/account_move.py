from odoo import api, models, tools


class AccountMove(models.Model):
    _inherit = "account.move"

    def _nu_is_internal_sender(self, email_from):
        """True if email_from belongs to one of the company's internal
        alias domains (mail.alias.domain).

        Detects internal forwarders even when no res.users is linked to
        the email — the partner-coquille case created by mail.alias
        from a generic internal mailbox (e.g. achat@aerix-systems.com).
        """
        if not email_from:
            return False
        parsed = tools.email_normalize(email_from)
        if not parsed:
            return False
        domain = parsed.rsplit("@", 1)[-1]
        if not domain:
            return False
        return bool(self.env["mail.alias.domain"].sudo().search_count(
            [("name", "=ilike", domain)],
        ))

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        move = super().message_new(msg_dict, custom_values=custom_values)
        if (
            move
            and move.journal_id.type == "purchase"
            and move.partner_id
            and self._nu_is_internal_sender(move.partner_id.email)
        ):
            move.partner_id = False
        return move
