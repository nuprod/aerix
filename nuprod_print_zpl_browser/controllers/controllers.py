# -*- coding: utf-8 -*-
# from odoo import http


# class PrintZplBrowser(http.Controller):
#     @http.route('/print_zpl_browser/print_zpl_browser', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/print_zpl_browser/print_zpl_browser/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('print_zpl_browser.listing', {
#             'root': '/print_zpl_browser/print_zpl_browser',
#             'objects': http.request.env['print_zpl_browser.print_zpl_browser'].search([]),
#         })

#     @http.route('/print_zpl_browser/print_zpl_browser/objects/<model("print_zpl_browser.print_zpl_browser"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('print_zpl_browser.object', {
#             'object': obj
#         })

