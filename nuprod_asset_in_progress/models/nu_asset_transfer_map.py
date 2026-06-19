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
    nu_is_active = fields.Boolean(string="Actif", default=True)

    @api.depends('nu_in_progress_account_id', 'nu_target_account_id',
                 'nu_in_progress_account_id.code', 'nu_target_account_id.code')
    def _compute_name(self):
        for mapping in self:
            source = mapping.nu_in_progress_account_id
            target = mapping.nu_target_account_id
            if source and target:
                company = mapping.nu_company_id or self.env.company
                mapping.name = "%s → %s" % (
                    source._nu_code_for_company(company),
                    target._nu_code_for_company(company))
            else:
                mapping.name = ""

    @api.constrains('nu_company_id', 'nu_in_progress_account_id', 'nu_is_active')
    def _check_unique_active_mapping(self):
        """Un seul mapping actif par (société, compte en-cours)."""
        for mapping in self:
            if not mapping.nu_is_active:
                continue
            duplicate = self.search_count([
                ('id', '!=', mapping.id),
                ('nu_company_id', '=', mapping.nu_company_id.id),
                ('nu_in_progress_account_id', '=',
                 mapping.nu_in_progress_account_id.id),
                ('nu_is_active', '=', True),
            ])
            if duplicate:
                raise ValidationError(
                    "Un mapping actif existe déjà pour le compte « %s » dans la "
                    "société « %s ». Il ne peut y en avoir qu'un seul." % (
                        mapping.nu_in_progress_account_id.display_name,
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
