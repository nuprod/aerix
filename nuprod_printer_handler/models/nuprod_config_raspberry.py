from odoo import models, fields, api

class NuprodRaspberry(models.Model):
  _name = 'nuprod.config.raspberry'
  _description = 'Raspberry Configuration'

  name = fields.Char(string='Nom du Raspberry', required=True, store=True)
  ip_address = fields.Char(string='Adresse IP', required=True, store=True)
  port = fields.Integer(string='Port', default=3000, store=True)
  description = fields.Text(string='Description', store=True)
  is_active = fields.Boolean(string='Raspberry fonctionnel', default=True, store=True)
  is_printer_server = fields.Boolean(string='Serveur d\'impression', default=False, store=True)
  use_for_printer = fields.Boolean(string="Utiliser pour l'impression", default=False, store=True)