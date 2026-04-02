from odoo import models, fields

class NuprodHrEmployee(models.Model):
    _inherit = 'hr.employee'

    printer_ids = fields.Many2many('nuprod.config.printer', string='Imprimante(s)')