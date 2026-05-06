# Copyright 2025 ForgeFlow S.L. (https://www.forgeflow.com)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

def migrate(cr, version):

  cr.execute("""
        SELECT id 
        FROM ir_ui_view
        WHERE model = 'res.partner'
        AND arch_prev ILIKE '%ape%'  -- ← Manquait le guillemet fermant
    """)
    
  if cr.fetchone():
      cr.execute("""
          DELETE FROM ir_ui_view 
          WHERE model = 'res.partner' 
          AND arch_prev ILIKE '%ape%'
      """)
  

