import logging
from collections import defaultdict

from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools import formatLang

_logger = logging.getLogger(__name__)

# Types de pièces concernés : factures et avoirs fournisseurs uniquement.
NU_ASSET_INVOICE_TYPES = ('in_invoice', 'in_refund')


class AccountMove(models.Model):
    _inherit = 'account.move'

    # ------------------------------------------------------------------
    # Garde-fou : pas d'imputation en immobilisation (21x) sous le seuil
    # ------------------------------------------------------------------
    def _nu_min_asset_amount(self):
        """Seuil (€ HT) sous lequel une imputation en compte 21x est interdite.

        Paramétré via ``nuprod_asset_in_progress.min_asset_amount``.
        0 (ou absent) → aucun contrôle."""
        param = self.env['ir.config_parameter'].sudo().get_param(
            'nuprod_asset_in_progress.min_asset_amount', default='0')
        try:
            return float(param)
        except (TypeError, ValueError):
            return 0.0

    def _nu_check_asset_min_amount(self):
        """Bloque la comptabilisation si un compte d'immo 21x est imputé pour un
        montant HT total (agrégé sur la facture) strictement inférieur au seuil.

        Le montant est **agrégé par compte** sur l'ensemble des lignes de la
        pièce : un bien saisi en plusieurs lignes n'est donc pas faussement
        bloqué tant que le cumul atteint le seuil."""
        threshold = self._nu_min_asset_amount()
        if not threshold:
            return
        for move in self:
            if move.move_type not in NU_ASSET_INVOICE_TYPES:
                continue
            totals = defaultdict(float)
            codes = {}
            for line in move.invoice_line_ids:
                account = line.account_id
                if not account:
                    continue
                code = account._nu_code_for_company(move.company_id)
                if code[:2] != '21':
                    continue
                totals[account.id] += line.price_subtotal
                codes[account.id] = code
            currency = move.company_id.currency_id
            bad = [
                (codes[aid], total)
                for aid, total in totals.items()
                if abs(total) < threshold
            ]
            if bad:
                details = "\n".join(
                    _("- Compte %(code)s : %(amount)s HT",
                      code=code,
                      amount=formatLang(self.env, total, currency_obj=currency))
                    for code, total in bad)
                raise UserError(_(
                    "Imputation en immobilisation (compte 21x) interdite pour un "
                    "montant strictement inférieur à %(threshold)s HT.\n\n"
                    "%(details)s",
                    threshold=formatLang(
                        self.env, threshold, currency_obj=currency),
                    details=details))

    def action_post(self):
        self._nu_check_asset_min_amount()
        return super().action_post()
