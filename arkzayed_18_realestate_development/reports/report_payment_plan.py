from odoo import models, api
from datetime import date


class PaymentPlanReportTemplate(models.AbstractModel):
    _name = 'report.arkzayed_18_realestate_development.unit_pay_plan_tmpl'
    _description = 'Custom Payment Plan Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        print("=== Inside Custom Parser ===")
        # print(f"Initial docids: {docids}, data: {data}")

        # Read from the data payload securely
        print_from_model = data.get('print_from_model') if data else False
        print_from_id = data.get('print_from_id') if data else False

        if not docids and print_from_model and print_from_id:
            source_doc = self.env[print_from_model].browse(print_from_id)
            if source_doc.exists() and source_doc.unit_id:
                docids = [source_doc.unit_id.id]

        docs = self.env['real.estate.unit'].browse(docids)
        custom_report_data = []

        for unit in docs:
            record_data = {
                'doc': unit,
                'system_code': unit.system_code,
                'currency_name': unit.company_id.currency_id.name or '',
            }

            source_doc = False

            if print_from_model in ['real.estate.sale.reservation', 'sale.proposal'] and print_from_id:
                source_doc = self.env[print_from_model].browse(print_from_id)

            if source_doc and source_doc.exists():
                if source_doc._name == 'real.estate.sale.reservation':
                    total_price = source_doc.price_after_discount
                    record_data['total_price'] = total_price
                    record_data['maintenance_fees'] = source_doc.maintenance_price
                    record_data['installments'] = self._get_installments_from_source(source_doc, total_price)

                elif source_doc._name == 'sale.proposal':
                    total_price = source_doc.price_after_discount
                    record_data['total_price'] = total_price
                    record_data['maintenance_fees'] = source_doc.maintenance_price
                    record_data['installments'] = self._get_installments_from_source(source_doc, total_price)
            else:
                record_data['total_price'] = unit.price_after_discount
                record_data['maintenance_fees'] = unit.maintenance_fees
                record_data['installments'] = unit._get_installments_grouped_by_date()

            custom_report_data.append(record_data)

        # print(f"Final Report Data: {custom_report_data}")

        return {
            'doc_ids': docids,
            'doc_model': 'real.estate.unit',
            'docs': docs,
            'custom_report_data': custom_report_data,
        }

    def _get_installments_from_source(self, source_doc, total_price):
        """Build exact lines placing maintenance installments at the end."""
        unit_lines = source_doc.installment_ids.sorted(key=lambda l: (l.date or date.min, l.id))
        maint_lines = source_doc.maintenance_installment_ids.sorted(key=lambda l: (l.date or date.min, l.id))

        final_result = []
        dp_count = 1
        inst_count = 1

        # 1. Process Unit Installments
        for line in unit_lines:
            name = str(line.name or '').strip().lower()

            if 'Down Payment 2' in name:
                label = 'Down Payment 2'
            elif 'Down Payment' in name:
                label = f'Down Payment {dp_count}'
                dp_count += 1
            elif 'Delivery' in name:
                label = 'Delivery Payment'
            else:
                label = f'Installment {inst_count}'
                inst_count += 1

            percentage = round((line.amount / total_price) * 100, 2) if total_price > 0 else 0.0

            final_result.append({
                'serial': line.serial,
                'label': label,
                'date': line.date,
                'percentage': percentage,
                'unit_amount': line.amount,
                'maintenance_amount': 0.0,
            })

        # 2. Process Maintenance Installments (Appended AT THE END)
        maint_count = 1
        for m_line in maint_lines:
            label = 'Maintenance Installment' if len(maint_lines) == 1 else f'Maintenance Installment {maint_count}'
            maint_count += 1

            final_result.append({
                'serial': len(final_result) + 1,
                'label': label,
                'date': m_line.date,
                'percentage': 0.0,
                'unit_amount': 0.0,
                'maintenance_amount': m_line.amount,
            })

        return final_result