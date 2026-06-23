from odoo import fields, api, models

class NuprodMrpProduction(models.Model):
    _inherit = 'mrp.production'

    def _prepare_stock_lot_values(self):
        """
        Override : Modifier la séquence du numéro de Lot
        """
        self.ensure_one()
        vals = super()._prepare_stock_lot_values()
        vals['name'] = self._get_my_serial_number(self.product_id, vals['name'])
        print(vals['name'])
        return vals


    def _get_my_serial_number(self, pid, base_name):

        month_letter = ""
        years = ""

        if self.date_start:
            month_letter = chr(ord('A') + self.date_start.month - 1)
            years = str(self.date_start.year % 100).zfill(2)
        article_number = pid.default_code
        version = pid.version

        serie_number = str(base_name).zfill(6)

        return f"{article_number or 'SN'}-{version}{years}{month_letter}{serie_number}"