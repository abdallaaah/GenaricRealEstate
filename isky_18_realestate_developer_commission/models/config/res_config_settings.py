from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """Phase 6: L3 contributes the Company Setup and Commission sections.

    The two non-sales commission rates were declared in L2 before Phase 6 (P5). They are
    `ir.config_parameter`-backed and read by parameter key, so moving the declaration here moved
    no data; the keys still carry the legacy prefix, which Phase 7 renames (backlog #33).
    """
    _inherit = 'res.config.settings'

    # Company Setup: which document commission is calculated on, by default.
    commission_basis = fields.Selection(
        related='company_id.commission_basis', readonly=False,
        string='Default Commission Basis')

    # Financials: the two tax rates that used to be literals in broker_claim (Phase 7, D4).
    vat_rate = fields.Float(
        related='company_id.vat_rate', readonly=False, string='VAT Rate (%)')
    withholding_tax_rate = fields.Float(
        related='company_id.withholding_tax_rate', readonly=False,
        string='Withholding Tax Rate (%)')

    # Commission: the non-sales rates.
    non_sales_commission_percentage = fields.Float(
        string='Non-Sales Commission %',
        config_parameter='realestate.non_sales_commission_percentage',
        default=0.5,
        help="Base commission percentage shared among non-sales employees. Each employee's "
             "commission category determines what share of this rate they receive."
    )
    non_sales_commission_collection_percentage = fields.Float(
        string='Non-Sales Commission Collection Threshold %',
        config_parameter='realestate.non_sales_commission_collection_percentage',
        help="Minimum collection percentage required on a contract before non-sales "
             "commission claims are generated for it."
    )
