from odoo import models, fields
import socket

import logging
_logger = logging.getLogger(__name__)

class NuprodProductTemplate(models.Model):
    _inherit = "product.product"

    def get_information_for_printing(self, printer_id):
      """
      Récupère les informations nécessaires pour l'impression des étiquettes.

      @param printer_id: ID de l'imprimante configurée
      @param label_quantity: Quantité d'étiquettes à imprimer
      @return: Dictionnaire contenant les informations pour l'impression
      """
      printer_id = self.env['nuprod.config.printer'].browse(printer_id)
      printer_ip = printer_id.ip_address
      printer_port = printer_id.port
      printer_label_height = printer_id.label_height
      printer_label_width = printer_id.label_width

      raspberry_id = self.env['nuprod.config.raspberry'].search([('is_active', '=', True), ('use_for_printer', '=', True)], limit=1)
      raspberry_ip = raspberry_id.ip_address + ":" + str(raspberry_id.port) if raspberry_id else "N/A"

      for record in self:
        product_name = record.name
        product_barcode = record.barcode if record.barcode else ""
        stock_quant_ids = self.env['stock.quant'].search([('product_id', '=', record.id)])
        stock_quant_id = stock_quant_ids.filtered(lambda sq: sq.location_id.is_product_location)
        product_location = stock_quant_id.location_id.complete_name if stock_quant_id else "N/A"
        if printer_id.label_type == 'tspl':
            data_builder = {'printer_label_width': printer_label_width,
                            'printer_label_height': printer_label_height,
                            'product_name': product_name,
                            'barcode': product_barcode,
                            'printer_ip': printer_ip,
                            'printer_port': printer_port,
                            'product_location': product_location,
                            'raspberry_ip': raspberry_ip
                            }
            return data_builder