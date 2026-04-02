from odoo import models, fields, api
from odoo.exceptions import ValidationError

class NuprodPrinter(models.Model):
  _name = 'nuprod.config.printer'
  _description = 'Printer Configuration'

  name = fields.Char(string='Nom de l\'imprimante', required=True, store=True)
  network_type = fields.Selection([('usb', 'USB'), ('ip', 'IP')], string='Type de connexion', default="ip", required=True, store=True)
  ip_address = fields.Char(string='Adresse IP', store=True)
  port = fields.Integer(string='Port', store=True)
  location_id = fields.Many2one('nuprod.place', string='Emplacement', store=True)
  description = fields.Text(string='Description', store=True)
  is_active = fields.Boolean(string='Imprimante fonctionnelle', default=True, store=True)
  label_type = fields.Selection([('zpl', 'ZPL'), ('tspl', 'TSPL'), ('pdf', 'PDF')], string='Type d\'étiquette', default='zpl', required=True, store=True)
  label_height= fields.Integer(string='Hauteur étiquette (mm)',store=True)
  label_width = fields.Integer(string='Largeur étiquette (mm)', store=True)
  cn23_printer = fields.Boolean(string='Imprimante CN23', default=False, store=True)

  @api.constrains("label_type", "label_height", "label_width")
  def _check_label_dimensions(self):
    for record in self:
      if record.label_type == "tspl":
        if record.label_height <= 0 or record.label_width <= 0:
          raise ValidationError(
              "La hauteur et la largeur doivent être supérieures à 0 "
              "lorsque le type d'étiquette est TSPL."
              "Exemple : 100x50 (hauteur x largeur en mm)."
          )