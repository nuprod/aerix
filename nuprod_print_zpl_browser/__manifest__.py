# -*- coding: utf-8 -*-
{
    "name": "nuprod_print_zpl_browser",
    "summary": "Module to print ZPL label from browser to local printer",
    "description": """
        Module to print ZPL label from browser to local printer
    """,
    "author": "NUprod",
    "website": "https://www.nuprod.fr",
    "category": "Uncategorized",
    "version": "19.0.0.0.0",
    "depends": ["base", "product", "stock", "mrp_workorder", "bus"],
    "data": [
        # 'security/ir.model.access.csv',
        "views/product_product.xml",
        "views/product_template.xml",
        "views/stock_quant_package.xml",
        "views/stock_lot_view.xml",
        "views/mrp_workcenter_view.xml",
        "views/mrp_production_view.xml",
        "report/nuprod_zpl_report_view.xml",
        "report/nuprod_zpl_package_template.xml",
        "report/nuprod_zpl_production_template.xml",
        "report/nuprod_zpl_lot_template.xml",
        "report/nuprod_zpl_product_template.xml",
        "views/stock_quant_view.xml",
        "report/nuprod_zpl_quant_template.xml",
        "views/stock_location_view.xml",
        "report/nuprod_zpl_location_template.xml"
    ],
    "assets": {
        "web.assets_backend": [
            "nuprod_print_zpl_browser/static/lib/BrowserPrint-3.1.250.min.js",
            "nuprod_print_zpl_browser/static/lib/BrowserPrint-Zebra-1.1.250.min.js",
            "nuprod_print_zpl_browser/static/src/js/bus_service.js",
            "nuprod_print_zpl_browser/static/src/js/mrp_display_action.js",
            "nuprod_print_zpl_browser/static/src/js/mrp_display_record.js",
            "nuprod_print_zpl_browser/static/src/js/view_button.js",

            # "nuprod_print_zpl_browser/static/src/**/*.js",
            "nuprod_print_zpl_browser/static/src/**/*.xml",
        ],
    },
}
