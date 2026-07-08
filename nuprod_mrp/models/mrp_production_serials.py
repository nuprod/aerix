from odoo import api, models


class MrpProductionSerials(models.TransientModel):
    _inherit = 'mrp.production.serials'

    @api.depends('production_id')
    def _compute_lot_name(self):
        super()._compute_lot_name()
        for wizard in self:
            production = wizard.production_id
            # On ne reformate que s'il n'y a pas déjà de lots et qu'on a un nom de base.
            # Le lot_name calculé par le standard sert de numéro de base : il est
            # enrobé avec article / version / année / mois par _get_my_serial_number.
            # generate_lot_names incrémentera ensuite la partie 6 chiffres pour toute la série.
            if production and not production.lot_producing_ids and wizard.lot_name:
                wizard.lot_name = production._get_my_serial_number(
                    production.product_id, wizard.lot_name,
                )
