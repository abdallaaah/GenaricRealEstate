from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SaleProposalChequeWizard(models.TransientModel):
    _name = 'sale.proposal.cheque.wizard'
    _description = 'Select Starting Cheque Line'

    sale_proposal_id = fields.Many2one('sale.proposal')

    starting_line_id = fields.Many2one(
        'sale.proposal.cheque.wizard.line',
        string='Start From Line',
        # Removed required=True from here to allow initial creation!
        domain="[('wizard_id', '=', id)]"
    )

    def action_confirm(self):
        """Called when the user clicks 'Generate Cheques' inside the wizard popup"""
        self.ensure_one()

        # Add the requirement validation here instead!
        if not self.starting_line_id:
            raise ValidationError(_("Please select the line you want to start from."))

        # Build the exact key that _generate_cheques expects
        wl = self.starting_line_id
        if wl.line_type == 'installment':
            key = f"installment_{wl.installment_id.id}"
        else:
            key = f"maintenance_{wl.maintenance_id.id}"

        # Trigger the generation
        return self.sale_proposal_id._generate_cheques(key)

class SaleProposalChequeWizardLine(models.TransientModel):
    _name = 'sale.proposal.cheque.wizard.line'
    _description = 'Wizard Line for Cheques'

    wizard_id = fields.Many2one('sale.proposal.cheque.wizard', ondelete='cascade')
    name = fields.Char(string='Display Name')
    line_type = fields.Selection([('installment', 'Installment'), ('maintenance', 'Maintenance')])
    installment_id = fields.Many2one('installment.lines')
    maintenance_id = fields.Many2one('maintenance.installment.lines')