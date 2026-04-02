from odoo import models, fields, api

class NuprodPlace(models.Model):
    _name = 'nuprod.place'
    _description = 'Nuprod Place'

    name = fields.Char(string='Place Name', required=True)