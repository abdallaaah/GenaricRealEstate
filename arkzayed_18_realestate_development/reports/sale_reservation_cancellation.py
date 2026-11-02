from odoo import api, models, _
from odoo.exceptions import ValidationError



class SaleReservationCancellation(models.AbstractModel):
    _name = "report.arkzayed_18_realestate_development.reservation_cancel_form"
    _description = "Reservation Cancellation Form"
    _table = "report_re_dev_reservation_cancel_form"


    @api.model
    def _get_report_values(self, docids, data=None):
        records = self.env['real.estate.sale.reservation'].browse(docids)
        if records.state not in ['cancelled']:
            raise ValidationError(
                _("This report can only be printed in Cancelled state. "
                  "Current state: %s") % records.state
            )
        return {
            "doc_ids": docids,
            "doc_model": "real.estate.sale.reservation",
            "docs": records,
        }

