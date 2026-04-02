from odoo import models, api

from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)

class NuprodStockPicking(models.Model):
    _inherit = "stock.picking"

    
    def find_right_printer_for_workstation(self):
      for record in self:

        user_printer_ids = record.preparator_id.printer_ids 
        carrier_printer_ids = record.carrier_id.printer_ids

        if not user_printer_ids:
          raise UserError("Aucune imprimante n'est configurée pour l'utilisateur.")

        if not carrier_printer_ids:
          raise UserError("Aucune imprimante n'est configurée pour le transporteur.")

        if user_printer_ids and carrier_printer_ids:
          available_printer = user_printer_ids & carrier_printer_ids
          if not available_printer:
            raise UserError("Aucune imprimante commune n'est configurée pour l'utilisateur et le transporteur.")

          return available_printer[0]