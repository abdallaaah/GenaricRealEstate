# -*- coding: utf-8 -*-
from odoo import models


class HrPayslipEmployees(models.TransientModel):
    _inherit = 'hr.payslip.employees'

    def compute_sheet(self):
        #After generating payslips, apply the batch's 'other inputs' to each one and recompute the affected payslips.
        res = super().compute_sheet()
        active_id = self.env.context.get('active_id')
        if not active_id:
            return res
        payslip_run = self.env['hr.payslip.run'].browse(active_id)
        batch_inputs = payslip_run.input_line_ids
        if not batch_inputs:
            return res

        slips_to_recompute = self.env['hr.payslip']
        for slip in payslip_run.slip_ids.filtered(
                lambda s: s.state in ('draft', 'verify')):
            existing_types = slip.input_line_ids.input_type_id
            new_lines = []
            for line in batch_inputs:
                # don't duplicate an input the payslip already has
                if line.input_type_id in existing_types:
                    continue
                new_lines.append((0, 0, {
                    'input_type_id': line.input_type_id.id,
                    'name': line.name or line.input_type_id.name,
                    'amount': line.amount,
                }))
            if new_lines:
                slip.write({'input_line_ids': new_lines})
                slips_to_recompute |= slip

        if slips_to_recompute:
            slips_to_recompute.compute_sheet()
        return res
