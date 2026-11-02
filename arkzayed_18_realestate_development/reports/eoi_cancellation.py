from odoo import api, models, _
from odoo.exceptions import ValidationError



class SaleReservationCancellation(models.AbstractModel):
    _name = "report.arkzayed_18_realestate_development.report_cancel_form"
    _description = "EOI Cancellation Form"


    @api.model
    def _get_report_values(self, docids, data=None):
        records = self.env['eoi.eoi'].browse(docids)
        if records.status not in ['rejected']:
            raise ValidationError(
                _("This report can only be printed in Rejected state. "
                  "Current state: %s") % records.status
            )
        return {
            "doc_ids": docids,
            "doc_model": "eoi.eoi",
            "docs": records,
        }

