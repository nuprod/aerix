import base64
import io

from odoo import _, models
from odoo.exceptions import UserError

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    # ------------------------------------------------------------------
    # Explosion récursive de la nomenclature
    # ------------------------------------------------------------------
    def _nuprod_collect_export_lines(self, qty_needed, level, visited):
        """Retourne la liste des lignes (dict) de la nomenclature explosée.

        :param qty_needed: quantité du produit de cette BOM à produire,
            exprimée dans l'unité du produit de la BOM.
        :param level: niveau courant (0 = produit fini).
        :param visited: set des IDs de BOM déjà traversés dans la branche
            courante (garde-fou anti-récursion infinie).
        """
        self.ensure_one()
        rows = []
        if self.id in visited:
            return rows
        visited = visited | {self.id}

        # Nombre de "lots" de la BOM nécessaires pour couvrir qty_needed.
        batches = qty_needed / self.product_qty if self.product_qty else 0.0

        for line in self.bom_line_ids:
            product = line.product_id
            line_qty = batches * line.product_qty
            unit_cost = product.standard_price
            rows.append({
                'level': level + 1,
                'default_code': product.default_code or '',
                'name': product.display_name,
                'qty': line_qty,
                'uom': line.product_uom_id.name,
                'unit_cost': unit_cost,
                'line_cost': unit_cost * line_qty,
            })

            child = line.child_bom_id
            if child:
                if line.product_uom_id != child.product_uom_id:
                    child_qty = line.product_uom_id._compute_quantity(
                        line_qty, child.product_uom_id, round=False)
                else:
                    child_qty = line_qty
                rows += child._nuprod_collect_export_lines(
                    child_qty, level + 1, visited)
        return rows

    def _nuprod_get_export_rows(self):
        """Lignes complètes de l'export, en-tête produit fini inclus (niveau 0)."""
        self.ensure_one()
        product = self.product_id or self.product_tmpl_id.product_variant_id
        rows = [{
            'level': 0,
            'default_code': product.default_code or '',
            'name': product.display_name or self.product_tmpl_id.display_name,
            'qty': self.product_qty,
            'uom': self.product_uom_id.name,
            'unit_cost': product.standard_price,
            'line_cost': product.standard_price * self.product_qty,
        }]
        rows += self._nuprod_collect_export_lines(
            self.product_qty, level=0, visited=set())
        return rows

    # ------------------------------------------------------------------
    # Génération du fichier Excel
    # ------------------------------------------------------------------
    def _nuprod_build_bom_xlsx(self):
        self.ensure_one()
        rows = self._nuprod_get_export_rows()

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Nomenclature')

        currency = self.company_id.currency_id or self.env.company.currency_id
        money_fmt = '#,##0.00 "%s"' % (currency.symbol or '')

        header_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#D9E1F2', 'border': 1,
            'align': 'center', 'valign': 'vcenter',
        })
        cell_fmt = workbook.add_format({'border': 1})
        qty_fmt = workbook.add_format({'border': 1, 'num_format': '#,##0.###'})
        money_cell_fmt = workbook.add_format({'border': 1, 'num_format': money_fmt})
        total_fmt = workbook.add_format({'bold': True, 'border': 1})
        total_money_fmt = workbook.add_format({
            'bold': True, 'border': 1, 'num_format': money_fmt})

        headers = [
            'Niveau', 'Réf. interne', 'Désignation', 'Quantité',
            'Unité', 'Coût unitaire', 'Coût ligne',
        ]
        widths = [8, 18, 45, 12, 10, 16, 16]
        for col, (title, width) in enumerate(zip(headers, widths)):
            sheet.write(0, col, title, header_fmt)
            sheet.set_column(col, col, width)
        sheet.freeze_panes(1, 0)

        # Un format de désignation indenté par niveau (mis en cache).
        name_formats = {}

        def get_name_fmt(level):
            if level not in name_formats:
                name_formats[level] = workbook.add_format(
                    {'border': 1, 'indent': level})
            return name_formats[level]

        total_cost = 0.0
        line_no = 1
        for row in rows:
            sheet.write_number(line_no, 0, row['level'], cell_fmt)
            sheet.write_string(line_no, 1, row['default_code'], cell_fmt)
            sheet.write_string(line_no, 2, row['name'], get_name_fmt(row['level']))
            sheet.write_number(line_no, 3, row['qty'], qty_fmt)
            sheet.write_string(line_no, 4, row['uom'] or '', cell_fmt)
            sheet.write_number(line_no, 5, row['unit_cost'], money_cell_fmt)
            sheet.write_number(line_no, 6, row['line_cost'], money_cell_fmt)
            # On exclut le niveau 0 (produit fini) du total des composants.
            if row['level'] > 0:
                total_cost += row['line_cost']
            line_no += 1

        sheet.write_string(line_no, 5, 'Total composants', total_fmt)
        sheet.write_number(line_no, 6, total_cost, total_money_fmt)

        workbook.close()
        output.seek(0)
        return output.read()

    def action_nuprod_export_bom_xlsx(self):
        self.ensure_one()
        if xlsxwriter is None:
            raise UserError(_(
                "La librairie Python 'xlsxwriter' est requise pour cet export."))

        file_data = self._nuprod_build_bom_xlsx()
        product = self.product_id or self.product_tmpl_id.product_variant_id
        ref = product.default_code or product.display_name or self.display_name
        filename = "Nomenclature_%s.xlsx" % (ref or self.id)

        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(file_data),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': ('application/vnd.openxmlformats-officedocument.'
                         'spreadsheetml.sheet'),
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }
