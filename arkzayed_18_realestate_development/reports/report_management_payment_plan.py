from odoo import models, api, _
from odoo.exceptions import UserError
from datetime import date


class BaseManagementPaymentPlanReport(models.AbstractModel):
    _name = 'report.arkzayed_18_realestate_development.base_mgmt_pay_plan'
    _description = 'Base Management Payment Plan Parser'

    def _get_custom_data(self, docids, data, report_type):
        active_model = self.env.context.get('active_model') or 'real.estate.sale.reservation'
        print(f"active model: {active_model}, docids: {docids}, report_type: {report_type}")

        # Fallback to context active_ids if docids is empty
        if not docids and self.env.context.get('active_ids'):
            docids = self.env.context.get('active_ids')
        if not docids and data and data.get('docids'):
            docids = data.get('docids')

        docs = self.env[active_model].browse(docids)
        custom_report_data = []

        for doc in docs:
            # 1. Validation Check: Ensure installment lines exist
            unit_lines = getattr(doc, 'installment_ids', False)
            maint_lines = getattr(doc, 'maintenance_installment_ids', False)

            if not unit_lines or not maint_lines:
                raise UserError(_("Cannot generate report for '%s': No installment or maintenance lines found.") % doc.display_name)

            unit = getattr(doc, 'unit_id', False)
            if not unit:
                raise UserError(_("Cannot generate report for '%s': No unit linked.") % doc.display_name)

            sold_price = getattr(doc, 'price_after_discount', 0.0)
            maint_fees = getattr(doc, 'maintenance_price', 0.0)
            unit_bua = round(getattr(unit, 'indoor_gross_area', 0.0))
            unit_system_code = getattr(unit, 'system_code', '') or '—'

            unit_type_raw = getattr(unit, 'unit_type', '')
            unit_type_str = dict(unit._fields['unit_type'].selection).get(unit_type_raw, unit_type_raw) if unit_type_raw else '—'

            # 2. Process Unit Installment Lines
            formatted_installments = []
            dp_count = 1
            inst_count = 1

            sorted_unit_lines = unit_lines.sorted(key=lambda l: (l.date or date.min, l.id)) if unit_lines else []
            for line in sorted_unit_lines:
                raw_name = str(line.name or '').strip().lower()

                if 'down payment 2' in raw_name or 'post contract' in raw_name:
                    label = 'Down Payment 2'
                elif 'down payment' in raw_name:
                    label = f'Down Payment {dp_count}' if len(sorted_unit_lines) > 1 else 'Down Payment'
                    dp_count += 1
                elif 'delivery' in raw_name:
                    label = 'Delivery Payment'
                else:
                    label = f'Installment {inst_count}'
                    inst_count += 1

                pct = round((line.amount / sold_price) * 100, 3) if sold_price > 0 else 0.0

                formatted_installments.append({
                    'serial': line.serial,
                    'label': label,
                    'date': line.date.strftime('%d-%b-%y') if line.date else '—',
                    'percentage': pct,
                    'unit_amount': line.amount,
                    'maintenance_amount': 0.0,
                })

            # 3. Process Maintenance Installment Lines (Placed at bottom before totals)
            formatted_maint = []
            sorted_maint_lines = maint_lines.sorted(key=lambda l: (l.date or date.min, l.id)) if maint_lines else []
            maint_count = 1

            for m_line in sorted_maint_lines:
                m_label = 'Maintenance Fees:' if len(sorted_maint_lines) == 1 else f'Maintenance Fees {maint_count}:'
                maint_count += 1

                formatted_maint.append({
                    'serial': len(formatted_maint) + 1,
                    'label': m_label,
                    'date': m_line.date.strftime('%d-%b-%y') if m_line.date else '—',
                    'percentage': 0.0,
                    'unit_amount': 0.0,
                    'maintenance_amount': m_line.amount,
                })

            total_unit_amount = sum(l['unit_amount'] for l in formatted_installments)
            total_maint_amount = sum(l['maintenance_amount'] for l in formatted_maint)
            total_percentage = sum(l['percentage'] for l in formatted_installments)
            if total_percentage > 99.0:
                total_percentage = 100.0

            custom_report_data.append({
                'doc': doc,
                'unit_id': unit_system_code,
                'unit_bua': unit_bua,
                'unit_type': unit_type_str,
                'sold_price': sold_price,
                'maintenance_fees': maint_fees,
                'installments': formatted_installments,
                'maintenance_installments': formatted_maint,
                'total_unit_amount': total_unit_amount,
                'total_maint_amount': total_maint_amount,
                'total_percentage': total_percentage,
            })

        return {
            'doc_ids': docids,
            'doc_model': active_model,
            'docs': docs,
            'custom_report_data': custom_report_data,
            'report_type': report_type,
        }


class DeptPaymentPlanResReport(models.AbstractModel):
    _name = 'report.arkzayed_18_realestate_development.dept_plan_res'
    _inherit = 'report.arkzayed_18_realestate_development.base_mgmt_pay_plan'

    @api.model
    def _get_report_values(self, docids, data=None):
        self = self.with_context(active_model='real.estate.sale.reservation')
        return self._get_custom_data(docids, data, report_type='department')


class CeoPaymentPlanResReport(models.AbstractModel):
    _name = 'report.arkzayed_18_realestate_development.ceo_plan_res'
    _inherit = 'report.arkzayed_18_realestate_development.base_mgmt_pay_plan'

    @api.model
    def _get_report_values(self, docids, data=None):
        print("Generating CEO Payment Plan Report for Reservations")
        self = self.with_context(active_model='real.estate.sale.reservation')
        return self._get_custom_data(docids, data, report_type='ceo')


class DeptPaymentPlanPropReport(models.AbstractModel):
    _name = 'report.arkzayed_18_realestate_development.dept_plan_prop'
    _inherit = 'report.arkzayed_18_realestate_development.base_mgmt_pay_plan'

    @api.model
    def _get_report_values(self, docids, data=None):
        self = self.with_context(active_model='sale.proposal')
        return self._get_custom_data(docids, data, report_type='department')


class CeoPaymentPlanPropReport(models.AbstractModel):
    _name = 'report.arkzayed_18_realestate_development.ceo_plan_prop'
    _inherit = 'report.arkzayed_18_realestate_development.base_mgmt_pay_plan'

    @api.model
    def _get_report_values(self, docids, data=None):
        self = self.with_context(active_model='sale.proposal')
        return self._get_custom_data(docids, data, report_type='ceo')