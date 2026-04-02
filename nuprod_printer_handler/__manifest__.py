# -*- coding: utf-8 -*-
{
    "name": "nuprod_printer_handler",
    "summary": "Module to handling printer",
    "description": """
      Module to handling printer
    """,
    "author": "NUprod",
    "website": "https://www.nuprod.fr",
    "category": "Uncategorized",
    "version": "19.0.0.0.0",
    "depends": ["base", "delivery", "stock"],
    "data": [
      "security/ir.model.access.csv",
      "views/nuprod_config_printer_menu.xml",
      "views/nuprod_config_printer_views.xml",
      "views/nuprod_config_raspberry_views.xml",
      "views/delivery_carrier_views.xml",
      "views/hr_employee_views.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
    "installable": True,
    
}