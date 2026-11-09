from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """Phase 6: L0 owns the shared settings tab and the Units section.

    `res.config.settings` comes from `base`, so this adds no dependency - L0 stays free of
    `account`, sales and commission.
    """
    _inherit = 'res.config.settings'

    # Company Setup: which side of the product this database runs (Phase 8, G4).
    realestate_company_type = fields.Selection(
        related='company_id.realestate_company_type', readonly=False,
        string='Real Estate Company Type')

    # Units section: the company-level default every new project starts from.
    hierarchy_template_id = fields.Many2one(
        related='company_id.hierarchy_template_id', readonly=False,
        string='Default Unit Hierarchy Template')
