from odoo import api, fields, models
from odoo.exceptions import ValidationError


class NuAssetTransferMap(models.Model):
    _name = 'nu.asset.transfer.map'
    _description = "Mapping immobilisation en cours → immobilisation définitive"
    _order = 'nu_company_id, nu_in_progress_account_id'

    name = fields.Char(
        string="Libellé", compute='_compute_name', store=True)
    nu_company_id = fields.Many2one(
        'res.company', string="Société", required=True,
        default=lambda self: self.env.company)
    nu_in_progress_account_id = fields.Many2one(
        'account.account', string="Compte en-cours (23x)", required=True,
        help="Compte d'immobilisation en cours (classe 23) servant à la "
             "détection de l'origine.")
    nu_target_account_id = fields.Many2one(
        'account.account', string="Compte définitif (21x/205x)", required=True,
        help="Compte d'immobilisation définitif sur lequel virer le bien à la "
             "mise en service.")
    nu_journal_id = fields.Many2one(
        'account.journal', string="Journal d'OD", required=True,
        domain="[('type', '=', 'general')]",
        help="Journal d'opérations diverses utilisé pour l'écriture de virement.")
    nu_asset_model_id = fields.Many2one(
        'account.asset', string="Modèle d'immobilisation",
        domain="[('state', '=', 'model'), ('company_id', '=', nu_company_id)]",
        help="Optionnel. Permet de router un même compte d'en-cours (ex. 231000) "
             "vers plusieurs comptes définitifs selon la nature du bien : la fiche "
             "dont le modèle correspond utilise ce couple. Laisser vide pour la "
             "ligne « générique » utilisée quand aucun modèle ne correspond.")
    nu_is_active = fields.Boolean(string="Actif", default=True)

    @api.depends('nu_in_progress_account_id', 'nu_target_account_id',
                 'nu_in_progress_account_id.code', 'nu_target_account_id.code',
                 'nu_asset_model_id')
    def _compute_name(self):
        for mapping in self:
            source = mapping.nu_in_progress_account_id
            target = mapping.nu_target_account_id
            if source and target:
                company = mapping.nu_company_id or self.env.company
                name = "%s → %s" % (
                    source._nu_code_for_company(company),
                    target._nu_code_for_company(company))
                if mapping.nu_asset_model_id:
                    name += " (%s)" % mapping.nu_asset_model_id.name
                mapping.name = name
            else:
                mapping.name = ""

    @api.constrains('nu_company_id', 'nu_in_progress_account_id',
                    'nu_asset_model_id', 'nu_is_active')
    def _check_unique_active_mapping(self):
        """Un seul mapping actif par (société, compte en-cours, modèle).

        Un même compte d'en-cours (ex. 231000) peut donc avoir plusieurs lignes
        actives, à condition qu'elles ciblent des modèles différents — plus au
        plus une ligne « générique » (sans modèle)."""
        for mapping in self:
            if not mapping.nu_is_active:
                continue
            duplicate = self.search_count([
                ('id', '!=', mapping.id),
                ('nu_company_id', '=', mapping.nu_company_id.id),
                ('nu_in_progress_account_id', '=',
                 mapping.nu_in_progress_account_id.id),
                ('nu_asset_model_id', '=', mapping.nu_asset_model_id.id),
                ('nu_is_active', '=', True),
            ])
            if duplicate:
                detail = (
                    "le modèle « %s »" % mapping.nu_asset_model_id.name
                    if mapping.nu_asset_model_id else "aucun modèle (ligne générique)")
                raise ValidationError(
                    "Un mapping actif existe déjà pour le compte « %s » et %s "
                    "dans la société « %s »." % (
                        mapping.nu_in_progress_account_id.display_name,
                        detail,
                        mapping.nu_company_id.display_name))

    @api.constrains('nu_in_progress_account_id', 'nu_company_id')
    def _check_in_progress_account_is_23x(self):
        """Le compte source doit être un compte d'en-cours (code commençant par 23)."""
        for mapping in self:
            account = mapping.nu_in_progress_account_id
            if not account:
                continue
            code = account._nu_code_for_company(mapping.nu_company_id)
            if not code.startswith('23'):
                raise ValidationError(
                    "Le compte « %s » (code %s) n'est pas un compte "
                    "d'immobilisation en cours : son code doit commencer par "
                    "« 23 »." % (account.display_name, code or '∅'))
