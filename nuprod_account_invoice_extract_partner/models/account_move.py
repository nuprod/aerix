import re

from odoo import api, models, tools


SIREN_FROM_VAT_FR_RE = re.compile(r"^FR[0-9A-Z]{2}([0-9]{9})$")


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

    def _nu_find_partner_by_siren_from_vat(self, vat_number_ocr):
        """If the OCR VAT is French (FRXX#########), extract the SIREN
        (the trailing 9 digits) and return the partner whose siret starts
        with that SIREN. In multi-établissement cases, prefer the highest
        supplier_rank. Returns an empty res.partner() recordset if no match.
        """
        if not vat_number_ocr:
            return self.env["res.partner"]
        cleaned = re.sub(r"\s", "", vat_number_ocr.upper())
        match = SIREN_FROM_VAT_FR_RE.match(cleaned)
        if not match:
            return self.env["res.partner"]
        siren = match.group(1)
        return self.env["res.partner"].search(
            [
                *self.env["res.partner"]._check_company_domain(self.company_id),
                ("siret", "=like", f"{siren}%"),
            ],
            order="supplier_rank desc",
            limit=1,
        )

    def _get_partner(self, ocr_results):
        vat_number_ocr = self._get_ocr_selected_value(
            ocr_results, "VAT_Number", "",
        )
        if vat_number_ocr:
            partner_vat = self._find_partner_id_with_vat(vat_number_ocr)
            if partner_vat:
                return partner_vat, False
            partner_siren = self._nu_find_partner_by_siren_from_vat(
                vat_number_ocr,
            )
            if partner_siren:
                return partner_siren, False
        return super()._get_partner(ocr_results)

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
