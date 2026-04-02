from odoo import models, fields

class NuprodDeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    printer_ids = fields.Many2many('nuprod.config.printer', string='Imprimante(s)')