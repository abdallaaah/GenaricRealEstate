import io
import xlsxwriter
from datetime import datetime

from odoo import http
from odoo.http import request, content_disposition


class HandoverReportXlsx(http.Controller):

    @http.route('/handover/report/xlsx', type='http', auth='user')
    def download_handover_report_xlsx(self, **kwargs):
        active_ids = kwargs.get('active_ids', '')
        if active_ids:
            active_ids = [int(x) for x in active_ids.split(',') if x.strip()]
        else:
            active_ids = []

        domain = [('state', 'in', [
            'draft_contract', 'pending_approvals', 'approved',
            'signed_client', 'signed_ceo', 'ready_to_deliver', 'delivered'
        ])]
        if active_ids:
            domain.append(('id', 'in', active_ids))

        proposals = request.env['sale.proposal'].search(domain)

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Handover Report')

        title_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 14,
            'bg_color': '#D9D9D9',
            'border': 1,
        })
        header_format = workbook.add_format({
            'bold': True,
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#4472C4',
            'font_color': 'white',
            'font_size': 11,
            'text_wrap': True,
        })
        cell_format = workbook.add_format({
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 10,
        })
        money_format = workbook.add_format({
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 10,
            'num_format': '#,##0.00',
        })
        date_format = workbook.add_format({
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 10,
            'num_format': 'dd/mm/yyyy',
        })
        regular_format = workbook.add_format({
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 10,
            'bg_color': '#28a745',
            'font_color': 'white',
        })
        installment_regular_format = workbook.add_format({
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 10,
            'bg_color': '#ffc107',
            'font_color': 'black',
        })
        maintenance_regular_format = workbook.add_format({
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 10,
            'bg_color': '#ffc107',
            'font_color': 'black',
        })
        irregular_format = workbook.add_format({
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 10,
            'bg_color': '#dc3545',
            'font_color': 'white',
        })

        unit_type_map = {
            'residential': 'Residential',
            'retail': 'Retail',
            'office': 'Office',
            'medical': 'Medical',
            'clinic': 'Clinic',
            'food_beverage': 'Food & Beverage',
        }
        state_map = {
            'draft': 'Draft Proposal',
            'draft_contract': 'Draft Contract',
            'pending_approvals': 'Pending Approvals',
            'approved': 'Approved',
            'signed_client': 'Signed by Client',
            'signed_ceo': 'Signed by CEO',
            'ready_to_deliver': 'Ready to Deliver',
            'delivered': 'Delivered',
            'cancelled': 'Cancelled',
            'terminated': 'Terminated',
        }
        payment_state_map = {
            'regular': 'منتظم',
            'installment_regular': 'منتظم أقساط',
            'maintenance_regular': 'منتظم صيانة',
            'irregular': 'غير منتظم',
        }

        # Set column widths
        sheet.set_column(0, 0, 5)    # #
        sheet.set_column(1, 1, 22)   # Unit Code
        sheet.set_column(2, 2, 18)   # Building No
        sheet.set_column(3, 3, 14)   # Unit Type
        sheet.set_column(4, 4, 18)   # Contract Status
        sheet.set_column(5, 5, 14)   # Contract Date
        sheet.set_column(6, 6, 18)   # Expected Delivery Date
        sheet.set_column(7, 7, 20)   # Expected After Allowance
        sheet.set_column(8, 8, 16)   # Extra Period Date
        sheet.set_column(9, 9, 20)   # Contracted Sold Price
        sheet.set_column(10, 10, 65) # Customer Name
        sheet.set_column(11, 11, 18) # Payment State


        sheet.merge_range('A1:L1', 'Handover Report', title_format)
        sheet.set_row(0, 30)

        headers = [
            '#',
            'Unit Code',
            'Building No',
            'Unit Type',
            'Contract Status',
            'Contract Date',
            'Expected Delivery Date',
            'Expected After Allowance',
            'Extra Period Date',
            'Contracted Sold Price',
            'Customer Name',
            'Payment State',
        ]
        sheet.set_row(1, 30)
        for col_num, header in enumerate(headers):
            sheet.write(1, col_num, header, header_format)

        row = 2
        for idx, proposal in enumerate(proposals, start=1):
            sheet.write(row, 0, idx, cell_format)
            sheet.write(row, 1, proposal.unit_id.system_code if proposal.unit_id else '', cell_format)
            sheet.write(row, 2, proposal.building_id.name if proposal.building_id else '', cell_format)
            sheet.write(row, 3, unit_type_map.get(proposal.unit_type, proposal.unit_type or ''), cell_format)
            sheet.write(row, 4, state_map.get(proposal.state, proposal.state or ''), cell_format)

            # Date fields
            if proposal.contract_issue_date:
                sheet.write_datetime(row, 5, proposal.contract_issue_date, date_format)
            else:
                sheet.write(row, 5, '', cell_format)

            if proposal.expected_delivery_date:
                sheet.write_datetime(row, 6, proposal.expected_delivery_date, date_format)
            else:
                sheet.write(row, 6, '', cell_format)

            if proposal.expected_after_allowance:
                sheet.write_datetime(row, 7, proposal.expected_after_allowance, date_format)
            else:
                sheet.write(row, 7, '', cell_format)

            if proposal.extra_period_date:
                sheet.write_datetime(row, 8, proposal.extra_period_date, date_format)
            else:
                sheet.write(row, 8, '', cell_format)

            # Money field
            sheet.write(row, 9, proposal.contracted_selling_price or 0, money_format)

            # Customer
            sheet.write(row, 10, proposal.customer_id.name if proposal.customer_id else '', cell_format)

            # Payment state with color coding
            payment_state = proposal.payment_regularity_state
            payment_label = payment_state_map.get(payment_state, '')
            if payment_state == 'regular':
                sheet.write(row, 11, payment_label, regular_format)
            elif payment_state == 'installment_regular':
                sheet.write(row, 11, payment_label, installment_regular_format)
            elif payment_state == 'maintenance_regular':
                sheet.write(row, 11, payment_label, maintenance_regular_format)
            elif payment_state == 'irregular':
                sheet.write(row, 11, payment_label, irregular_format)
            else:
                sheet.write(row, 11, payment_label, cell_format)

            row += 1

        # Summary row
        row += 1
        summary_format = workbook.add_format({
            'bold': True,
            'border': 1,
            'align': 'left',
            'valign': 'vcenter',
            'font_size': 11,
        })
        sheet.merge_range(row, 1, row, 3, 'Total Records: %d' % len(proposals), summary_format)

        workbook.close()
        output.seek(0)

        filename = 'Handover_Report_%s.xlsx' % datetime.now().strftime('%Y%m%d_%H%M%S')
        headers_http = [
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', content_disposition(filename)),
        ]
        return request.make_response(output.read(), headers=headers_http)
