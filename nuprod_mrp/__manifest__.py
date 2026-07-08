{
    'name': 'Nuprod MRP',
    'version': '19.0.1.0.0',
    'summary': 'Export Excel de la nomenclature (multi-niveaux)',
    'description': """
Nuprod MRP
==========
Ajoute un bouton « Export Excel » sur le formulaire des nomenclatures
(mrp.bom) qui génère un fichier Excel de la nomenclature explosée
multi-niveaux au format :
(niveau, référence interne, désignation, quantité, unité, coût).
""",
    'author': 'Nuprod',
    'website': 'https://www.nuprod.fr',
    'category': 'Manufacturing',
    'depends': ['mrp'],
    'data': [
        'views/mrp_bom_views.xml',
    ],
    'external_dependencies': {
        'python': ['xlsxwriter'],
    },
    'installable': True,
    'application': False,
}
