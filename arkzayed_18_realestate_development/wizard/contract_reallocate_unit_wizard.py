from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ContractReallocateUnitWizard(models.TransientModel):
    _name = 'contract.reallocate.unit.wizard'
    _description = 'Contract Reallocate Unit Wizard'

    contract_id = fields.Many2one(
        'sale.proposal',
        string='Contract',
        required=True,
        readonly=True
    )
    old_unit_id = fields.Many2one(
        'real.estate.unit',
        string='Current Unit',
        readonly=True
    )
    new_unit_id = fields.Many2one(
        'real.estate.unit',
        string='New Unit',
        required=True
    )

    def action_confirm_reallocate(self):
        self.ensure_one()

        if not self.new_unit_id:
            raise UserError(_("Please select a new unit."))

        if self.new_unit_id == self.old_unit_id:
            raise UserError(_("You must select a different unit than the current one."))

        if self.new_unit_id.unit_status not in ('available', 'available_for_sale'):
            raise UserError(_("Selected unit is no longer available for sale."))

        if self.new_unit_id.unit_purpose != 'to_sale':
            raise UserError(_("Selected unit is not for sale."))

        reallocation_reason = self.env['block.reason'].search([
            ('for_reallocation', '=', True)
        ], limit=1)

        if not reallocation_reason:
            raise ValidationError(
                _("No block reason is configured for 'Blocked for Reallocation'. Please configure one in Block Reasons.")
            )

        try:
            # 1. Update old unit (block it for reallocation)
            self.old_unit_id.write({
                'unit_status': 'blocked',
                'reason_id': reallocation_reason.id,
            })

            # 2. Update new unit
            self.new_unit_id.write({
                'unit_status': 'reserved',
                'reason_id': False,
            })

            # 3. Update contract
            self.contract_id.write({
                'unit_id': self.new_unit_id.id,
            })

            # 4. Update cheques linked to the contract
            if self.contract_id.cheque_ids:
                self.contract_id.cheque_ids.write({
                    'unit_id': self.new_unit_id.id,
                })

            # 5. Post chatter notifications
            old_code = self.old_unit_id.system_code or ''
            new_code = self.new_unit_id.system_code or ''

            self.contract_id.message_post(
                body=_(
                    "Unit reallocated from %(old_unit)s (%(old_code)s) to %(new_unit)s (%(new_code)s) by %(user)s.",
                    old_unit=self.old_unit_id.name,
                    old_code=old_code,
                    new_unit=self.new_unit_id.name,
                    new_code=new_code,
                    user=self.env.user.name,
                ),
                subject=_("Unit Reallocation")
            )

            self.old_unit_id.message_post(
                body=_(
                    "Unit relocated to %(new_unit)s (%(new_code)s) under contract %(contract)s. Unit is now blocked for reallocation.",
                    new_unit=self.new_unit_id.name,
                    new_code=new_code,
                    contract=self.contract_id.name,
                ),
                subject=_("Unit Blocked - Reallocated")
            )

            self.new_unit_id.message_post(
                body=_(
                    "Unit assigned to contract %(contract)s via relocation from %(old_unit)s (%(old_code)s). Unit is now reserved.",
                    old_unit=self.old_unit_id.name,
                    old_code=old_code,
                    contract=self.contract_id.name,
                ),
                subject=_("Unit Assignment - Reallocated")
            )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Unit Reallocated Successfully'),
                    'message': _('Unit has been changed from %s to %s. Existing installments and cheques remain intact.') % (
                        self.old_unit_id.name,
                        self.new_unit_id.name
                    ),
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }

        except Exception as e:
            if isinstance(e, (UserError, ValidationError)):
                raise e
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Failed to relocate unit: %s') % str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }
