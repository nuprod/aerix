import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Wording exact du garde-fou (cf. spec §7.2 — repris de l'existant client).
GUARD_DATE_MESSAGE = (
    "Cette immobilisation provient d'un compte %(code)s (immo en cours).\n\n"
    "Avant de confirmer, vous devez renseigner la Date de prorata = date de "
    "mise en service du bien.\n\n"
    "Si la mise en service est aujourd'hui, mettez la date du jour. Sinon, "
    "mettez la date future prévue."
)


class AccountAsset(models.Model):
    _inherit = 'account.asset'

    nu_transfer_move_id = fields.Many2one(
        'account.move', string="OD de mise en service", copy=False,
        readonly=True,
        help="Écriture de virement 23x → 21x/205x générée à la mise en service. "
             "Sa présence garantit l'idempotence (jamais deux OD).")
    nu_is_in_progress = fields.Boolean(
        string="Issue d'un compte en-cours (23x)",
        compute='_compute_nu_in_progress', store=True,
        help="Vrai si le compte d'origine de l'immobilisation est un compte "
             "d'en-cours (code commençant par 23).")
    nu_in_progress_account_id = fields.Many2one(
        'account.account', string="Compte en-cours d'origine",
        compute='_compute_nu_in_progress', store=True,
        help="Compte 23x d'acquisition détecté comme origine de l'immobilisation.")
    nu_is_force_in_service = fields.Boolean(
        string="Forcer la mise en service",
        copy=False,
        help="Dérogation au garde-fou de date : autorise la confirmation même "
             "lorsque la date de prorata est égale à la date d'acquisition "
             "(cas légitime d'une mise en service le jour de l'acquisition).")

    @api.depends('account_asset_id', 'company_id')
    def _compute_nu_in_progress(self):
        for asset in self:
            account = asset.account_asset_id
            is_in_progress = False
            if account and asset.company_id:
                code = account._nu_code_for_company(asset.company_id)
                is_in_progress = code.startswith('23')
            asset.nu_is_in_progress = is_in_progress
            asset.nu_in_progress_account_id = account if is_in_progress else False

    # ------------------------------------------------------------------
    # Mise en service : génération de l'OD de virement
    # ------------------------------------------------------------------
    def validate(self):
        """Override : pose le virement 23x → 21x/205x après confirmation.

        ``super().validate()`` réalise la transition draft → open, construit le
        tableau d'amortissement et poste les dotations. Le virement de bilan est
        donc posé une fois l'asset confirmé.
        """
        self._nu_check_required_analytic()
        res = super().validate()
        for asset in self:
            if asset.nu_is_in_progress:
                asset._nu_generate_transfer_move()
        return res

    # ------------------------------------------------------------------
    # Axes analytiques obligatoires à la confirmation (paramétrable)
    # ------------------------------------------------------------------
    def _nu_required_analytic_plans(self):
        """Plans analytiques rendus obligatoires à la confirmation.

        Configurés via le paramètre système
        ``nuprod_asset_in_progress.required_analytic_plan_ids`` (ids séparés par
        des virgules). Vide → aucun contrôle."""
        raw = self.env['ir.config_parameter'].sudo().get_param(
            'nuprod_asset_in_progress.required_analytic_plan_ids', default='')
        ids = [int(x) for x in raw.replace(';', ',').split(',') if x.strip().isdigit()]
        return self.env['account.analytic.plan'].browse(ids).exists()

    def _nu_check_required_analytic(self):
        """Bloque la confirmation si un axe analytique obligatoire manque."""
        required = self._nu_required_analytic_plans()
        if not required:
            return
        for asset in self:
            distribution = asset.analytic_distribution or {}
            account_ids = {
                int(aid)
                for key in distribution
                for aid in str(key).split(',') if aid.strip().isdigit()
            }
            covered = self.env['account.analytic.account'].browse(
                account_ids).exists().root_plan_id
            missing = required - covered
            if missing:
                raise UserError(_(
                    "Cette immobilisation ne peut pas être confirmée : les axes "
                    "analytiques suivants sont obligatoires et manquants : %s.",
                    ", ".join(missing.mapped('name'))))

    def _nu_auto_post(self):
        """Booléen : poster automatiquement l'OD ? (défaut False = brouillon)."""
        param = self.env['ir.config_parameter'].sudo().get_param(
            'nuprod_asset_in_progress.auto_post', default='False')
        return param.strip().lower() in ('1', 'true', 'yes', 'on')

    def _nu_get_transfer_map(self):
        """Mapping actif pour cet asset, ou recordset vide.

        Routage : un même compte d'en-cours (ex. 231000) peut cibler plusieurs
        comptes définitifs selon le **modèle** de la fiche. On privilégie la ligne
        dont le modèle correspond à ``model_id`` ; à défaut, on retombe sur la
        ligne « générique » (sans modèle) du compte d'origine."""
        self.ensure_one()
        Map = self.env['nu.asset.transfer.map']
        base = [
            ('nu_company_id', '=', self.company_id.id),
            ('nu_in_progress_account_id', '=', self.account_asset_id.id),
            ('nu_is_active', '=', True),
        ]
        if self.model_id:
            specific = Map.search(
                base + [('nu_asset_model_id', '=', self.model_id.id)], limit=1)
            if specific:
                return specific
        return Map.search(base + [('nu_asset_model_id', '=', False)], limit=1)

    def _nu_generate_transfer_move(self):
        """Génère (et lie) l'OD de virement de l'immobilisation en cours.

        Idempotent, et protégé par le garde-fou de date. Lève un ``UserError``
        explicite plutôt que de planter en silence si la configuration manque.
        """
        self.ensure_one()

        # 1. Idempotence : jamais deux OD pour le même asset.
        if self.nu_transfer_move_id:
            _logger.debug(
                "Asset %s : OD de virement déjà existante (%s), skip.",
                self.id, self.nu_transfer_move_id.id)
            return self.nu_transfer_move_id

        code = self.nu_in_progress_account_id._nu_code_for_company(self.company_id)

        # 2. Garde-fou date (ne JAMAIS vider prorata_date, qui est NOT NULL).
        if not self.nu_is_force_in_service and self.prorata_date == self.acquisition_date:
            raise UserError(GUARD_DATE_MESSAGE % {'code': code})

        # 3. Mapping : compte cible + journal. Pas de plantage silencieux.
        mapping = self._nu_get_transfer_map()
        if not mapping:
            raise UserError(_(
                "Aucun mapping de virement n'est configuré pour le compte "
                "d'en-cours « %(account)s » dans la société « %(company)s ».\n\n"
                "Configurez-le dans Comptabilité → Configuration → "
                "Immobilisations en cours.",
                account=self.nu_in_progress_account_id.display_name,
                company=self.company_id.display_name,
            ))

        # 4. OD de virement : débit compte cible / crédit compte 23x.
        distribution = self.analytic_distribution or False
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': mapping.nu_journal_id.id,
            'company_id': self.company_id.id,
            'date': self.prorata_date,
            'ref': "Mise en service [%s] %s" % (self.id, self.name),
            'line_ids': [
                (0, 0, {
                    'account_id': mapping.nu_target_account_id.id,
                    'debit': self.original_value,
                    'credit': 0.0,
                    'name': self.name,
                    'analytic_distribution': distribution,
                }),
                (0, 0, {
                    'account_id': self.nu_in_progress_account_id.id,
                    'debit': 0.0,
                    'credit': self.original_value,
                    'name': self.name,
                    'analytic_distribution': distribution,
                }),
            ],
        })

        # 5. Lier + tracer.
        self.nu_transfer_move_id = move.id
        posted = self._nu_auto_post()
        if posted:
            move.action_post()
        self.message_post(body=_(
            "Virement d'immobilisation en cours généré (%(state)s) : "
            "%(move)s — %(src)s → %(target)s pour %(amount)s.",
            state=_("posté") if posted else _("brouillon"),
            move=move.display_name,
            src=mapping.nu_in_progress_account_id._nu_code_for_company(self.company_id),
            target=mapping.nu_target_account_id._nu_code_for_company(self.company_id),
            amount=self.original_value,
        ))
        return move

    def action_nu_open_transfer_move(self):
        """Smart button : ouvre l'OD de virement liée."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.nu_transfer_move_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
