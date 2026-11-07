from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """Phase 6: L0 owns the shared settings tab and the Units section.

    `res.config.settings` comes from `base`, so this adds no dependency - L0 stays free of
    `account`, sales and commission.
    """
    _inherit = 'res.config.settings'

    # Units section: the company-level default every new project starts from.
    hierarchy_template_id = fields.Many2one(
        related='company_id.hierarchy_template_id', readonly=False,
        string='Default Unit Hierarchy Template')
