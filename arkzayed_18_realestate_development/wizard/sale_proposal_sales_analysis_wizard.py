from odoo import models, fields, api
from datetime import datetime
from collections import defaultdict
import io
import base64


class SaleProposalSalesAnalysisWizard(models.TransientModel):
    _name = 'sale.proposal.sales.analysis.wizard'
    _description = 'Sale Proposal Sales Analysis Wizard'

    date_from = fields.Date(
        string='Date From',
        required=True,
        default=lambda self: datetime(datetime.now().year, 1, 1).date()
    )
    date_to = fields.Date(
        string='Date To',
        required=True,
        default=lambda self: datetime(datetime.now().year, 12, 31).date()
    )
    business_unit_type_ids = fields.Many2many(
        'business.unit.type',
        'sale_proposal_sales_analysis_wizard_business_unit_type_rel',
        'wizard_id',
        'business_unit_type_id',
        string='Business Unit Types',
        help='Select business unit types to include in the report'
    )

    def _get_filtered_proposals(self):
        """Get sale.proposal records based on wizard filters"""
        excluded_states = ['draft', 'draft_contract', 'pending_approvals', 'cancelled', 'terminated']
        proposals = self.env['sale.proposal'].search([
            ('contract_issue_date', '>=', self.date_from),
            ('contract_issue_date', '<=', self.date_to),
            ('state', 'not in', excluded_states),
            ('unit_id', '!=', False),
        ])
        return proposals

    def _get_month_order(self, month_str):
        """Get month number for sorting"""
        months = {
            'January': 1, 'February': 2, 'March': 3, 'April': 4,
            'May': 5, 'June': 6, 'July': 7, 'August': 8,
            'September': 9, 'October': 10, 'November': 11, 'December': 12
        }
        return months.get(month_str, 13)

    def _aggregate_data(self):
        """Aggregate data for the report"""
        proposals = self._get_filtered_proposals()

        residential_monthly = defaultdict(lambda: {'units': 0, 'price': 0})
        residential_by_type = defaultdict(lambda: {'units': 0, 'price': 0})

        business_monthly = defaultdict(lambda: {'units': 0, 'price': 0})
        business_by_type = defaultdict(lambda: {'units': 0, 'price': 0})

        contract_details = []

        # Get selected business unit type names
        selected_business_types = [bt.name for bt in self.business_unit_type_ids]

        for proposal in proposals:
            if not proposal.unit_id or not proposal.contract_issue_date:
                continue

            price = proposal.price_after_discount or 0
            month = proposal.contract_issue_date.strftime('%B')

            # Determine if residential or business
            if proposal.unit_id.residential_type:
                # Residential
                residential_monthly[month]['units'] += 1
                residential_monthly[month]['price'] += price

                unit_type = proposal.unit_id.residential_type or 'Unknown'
                residential_by_type[unit_type]['units'] += 1
                residential_by_type[unit_type]['price'] += price
            else:
                # Business - only include if in selected types or if no types selected (include all)
                unit_type = proposal.unit_id.unit_type or 'Unknown'
                if not selected_business_types or unit_type in selected_business_types:
                    business_monthly[month]['units'] += 1
                    business_monthly[month]['price'] += price
                    business_by_type[unit_type]['units'] += 1
                    business_by_type[unit_type]['price'] += price

            # Collect contract details for detail sheet
            contract_details.append({
                'name': proposal.name,
                'date': proposal.contract_issue_date,
                'unit': proposal.unit_id.display_name or '',
                'customer': proposal.customer_id.display_name or '',
                'discount_percentage': proposal.discount_percentage or 0.0,
                'price_before_discount': proposal.contracted_selling_price or 0.0,
                'price': price,
                'discount_approved_by': proposal.discount_approved_by.name if proposal.discount_approved_by else '',
            })

        # Calculate totals and percentages
        residential_data = self._calculate_percentages(residential_monthly, residential_by_type)
        business_data = self._calculate_percentages(business_monthly, business_by_type)

        return {
            'residential': residential_data,
            'business': business_data,
            'contract_details': contract_details,
        }

    def _calculate_percentages(self, monthly_dict, by_type_dict):
        """Calculate percentages for monthly and by_type data"""
        total_price = sum(data['price'] for data in monthly_dict.values())

        monthly_list = []
        for month, values in monthly_dict.items():
            percentage = (values['price'] / total_price * 100) if total_price > 0 else 0
            monthly_list.append({
                'month': month,
                'units': values['units'],
                'price': values['price'],
                'percentage': round(percentage, 2)
            })

        by_type_list = []
        for unit_type, values in by_type_dict.items():
            percentage = (values['price'] / total_price * 100) if total_price > 0 else 0
            by_type_list.append({
                'type': unit_type,
                'units': values['units'],
                'price': values['price'],
                'percentage': round(percentage, 2)
            })

        # Sort monthly by month order
        monthly_list.sort(key=lambda x: self._get_month_order(x['month']))

        return {
            'monthly': monthly_list,
            'by_type': by_type_list,
            'total_units': sum(m['units'] for m in monthly_list),
            'total_price': total_price,
        }

    def action_generate_pdf(self):
        """Generate PDF report"""
        self.ensure_one()
        return self.env.ref('arkzayed_18_realestate_development.action_sale_proposal_sales_analysis_report').report_action(self)

    def action_generate_excel(self):
        """Generate Excel report"""
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        data = self._aggregate_data()
        wb = Workbook()
        ws = wb.active
        ws.title = "Sales Analysis"

        # Set column widths
        ws.column_dimensions['A'].width = 15
        ws.column_dimensions['B'].width = 15
        ws.column_dimensions['C'].width = 18
        ws.column_dimensions['D'].width = 10
        ws.column_dimensions['E'].width = 5  # Gap
        ws.column_dimensions['F'].width = 15
        ws.column_dimensions['G'].width = 15
        ws.column_dimensions['H'].width = 18
        ws.column_dimensions['I'].width = 10

        # Title
        ws['A1'] = f"Sales Analysis Report ({self.date_from.year})"
        ws['A1'].font = Font(bold=True, size=14)
        ws.merge_cells('A1:D1')
        ws['A1'].alignment = Alignment(horizontal='center')

        ws['F1'] = f"Sales Analysis Report ({self.date_from.year})"
        ws['F1'].font = Font(bold=True, size=14)
        ws.merge_cells('F1:I1')
        ws['F1'].alignment = Alignment(horizontal='center')

        # Styling
        header_fill = PatternFill(start_color='D3D3D3', end_color='D3D3D3', fill_type='solid')
        header_font = Font(bold=True)
        total_fill = PatternFill(start_color='F0F0F0', end_color='F0F0F0', fill_type='solid')
        total_font = Font(bold=True)
        border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )

        row = 3

        # ===== RESIDENTIAL MONTHLY =====
        ws[f'A{row}'] = "Residential - Monthly Sales"
        ws[f'A{row}'].font = Font(bold=True, size=11)
        row += 1

        # Headers
        headers = ['Month', 'Sum of Units', 'Price', '%']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col)
            cell.value = header
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center')
            cell.border = border

        row += 1

        # Data
        for item in data['residential']['monthly']:
            ws.cell(row=row, column=1).value = item['month']
            ws.cell(row=row, column=2).value = item['units']
            ws.cell(row=row, column=3).value = item['price']
            ws.cell(row=row, column=4).value = f"{item['percentage']:.0f}%"
            row += 1

        # Grand Total
        ws.cell(row=row, column=1).value = "Grand Total"
        ws.cell(row=row, column=1).font = total_font
        ws.cell(row=row, column=1).fill = total_fill

        ws.cell(row=row, column=2).value = data['residential']['total_units']
        ws.cell(row=row, column=2).font = total_font
        ws.cell(row=row, column=2).fill = total_fill

        ws.cell(row=row, column=3).value = data['residential']['total_price']
        ws.cell(row=row, column=3).font = total_font
        ws.cell(row=row, column=3).fill = total_fill

        ws.cell(row=row, column=4).value = "100%"
        ws.cell(row=row, column=4).font = total_font
        ws.cell(row=row, column=4).fill = total_fill

        row += 3

        # ===== BUSINESS MONTHLY =====
        row_biz = 3
        ws[f'F{row_biz}'] = "Business District - Monthly Sales"
        ws[f'F{row_biz}'].font = Font(bold=True, size=11)
        row_biz += 1

        # Headers
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=row_biz, column=col+5)
            cell.value = header
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center')
            cell.border = border

        row_biz += 1

        # Data
        for item in data['business']['monthly']:
            ws.cell(row=row_biz, column=6).value = item['month']
            ws.cell(row=row_biz, column=7).value = item['units']
            ws.cell(row=row_biz, column=8).value = item['price']
            ws.cell(row=row_biz, column=9).value = f"{item['percentage']:.0f}%"
            row_biz += 1

        # Grand Total
        ws.cell(row=row_biz, column=6).value = "Grand Total"
        ws.cell(row=row_biz, column=6).font = total_font
        ws.cell(row=row_biz, column=6).fill = total_fill

        ws.cell(row=row_biz, column=7).value = data['business']['total_units']
        ws.cell(row=row_biz, column=7).font = total_font
        ws.cell(row=row_biz, column=7).fill = total_fill

        ws.cell(row=row_biz, column=8).value = data['business']['total_price']
        ws.cell(row=row_biz, column=8).font = total_font
        ws.cell(row=row_biz, column=8).fill = total_fill

        ws.cell(row=row_biz, column=9).value = "100%"
        ws.cell(row=row_biz, column=9).font = total_font
        ws.cell(row=row_biz, column=9).fill = total_fill

        # ===== RESIDENTIAL BY TYPE =====
        row += 2
        ws[f'A{row}'] = "Residential - Sales by Unit Type"
        ws[f'A{row}'].font = Font(bold=True, size=11)
        row += 1

        headers = ['Unit Type', 'Sum of Units', 'Sum of Sold Price', '%']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col)
            cell.value = header
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center')
            cell.border = border

        row += 1

        # Data
        for item in data['residential']['by_type']:
            ws.cell(row=row, column=1).value = item['type']
            ws.cell(row=row, column=2).value = item['units']
            ws.cell(row=row, column=3).value = item['price']
            ws.cell(row=row, column=4).value = f"{item['percentage']:.0f}%"
            row += 1

        # Grand Total
        ws.cell(row=row, column=1).value = "Grand Total"
        ws.cell(row=row, column=1).font = total_font
        ws.cell(row=row, column=1).fill = total_fill

        ws.cell(row=row, column=2).value = data['residential']['total_units']
        ws.cell(row=row, column=2).font = total_font
        ws.cell(row=row, column=2).fill = total_fill

        ws.cell(row=row, column=3).value = data['residential']['total_price']
        ws.cell(row=row, column=3).font = total_font
        ws.cell(row=row, column=3).fill = total_fill

        ws.cell(row=row, column=4).value = "100%"
        ws.cell(row=row, column=4).font = total_font
        ws.cell(row=row, column=4).fill = total_fill

        # ===== BUSINESS BY TYPE =====
        row_biz += 2
        ws[f'F{row_biz}'] = "Business District - Sales by Type"
        ws[f'F{row_biz}'].font = Font(bold=True, size=11)
        row_biz += 1

        headers = ['Type', 'Sum of Units', 'Sum of Sold Price', '%']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=row_biz, column=col+5)
            cell.value = header
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center')
            cell.border = border

        row_biz += 1

        # Data
        for item in data['business']['by_type']:
            ws.cell(row=row_biz, column=6).value = item['type']
            ws.cell(row=row_biz, column=7).value = item['units']
            ws.cell(row=row_biz, column=8).value = item['price']
            ws.cell(row=row_biz, column=9).value = f"{item['percentage']:.0f}%"
            row_biz += 1

        # Grand Total
        ws.cell(row=row_biz, column=6).value = "Grand Total"
        ws.cell(row=row_biz, column=6).font = total_font
        ws.cell(row=row_biz, column=6).fill = total_fill

        ws.cell(row=row_biz, column=7).value = data['business']['total_units']
        ws.cell(row=row_biz, column=7).font = total_font
        ws.cell(row=row_biz, column=7).fill = total_fill

        ws.cell(row=row_biz, column=8).value = data['business']['total_price']
        ws.cell(row=row_biz, column=8).font = total_font
        ws.cell(row=row_biz, column=8).fill = total_fill

        ws.cell(row=row_biz, column=9).value = "100%"
        ws.cell(row=row_biz, column=9).font = total_font
        ws.cell(row=row_biz, column=9).fill = total_fill

        # ===== CONTRACT DETAILS SHEET =====
        detail_sheet = wb.create_sheet("Contract Details")
        detail_sheet.column_dimensions['A'].width = 13
        detail_sheet.column_dimensions['B'].width = 12
        detail_sheet.column_dimensions['C'].width = 22
        detail_sheet.column_dimensions['D'].width = 18
        detail_sheet.column_dimensions['E'].width = 12
        detail_sheet.column_dimensions['F'].width = 18
        detail_sheet.column_dimensions['G'].width = 18
        detail_sheet.column_dimensions['H'].width = 20

        # Title
        detail_sheet['A1'] = f"Contract Details ({self.date_from.year})"
        detail_sheet['A1'].font = Font(bold=True, size=14)
        detail_sheet.merge_cells('A1:H1')
        detail_sheet['A1'].alignment = Alignment(horizontal='center')

        detail_row = 3
        headers = ['Contract', 'Issue Date', 'Customer', 'Unit', 'Discount %', 'Price Before Discount', 'Value', 'Discount Approved By']
        for col, header in enumerate(headers, 1):
            cell = detail_sheet.cell(row=detail_row, column=col)
            cell.value = header
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center')
            cell.border = border

        detail_row += 1

        # Data
        for detail_line in data['contract_details']:
            detail_sheet.cell(row=detail_row, column=1).value = detail_line['name']
            detail_sheet.cell(row=detail_row, column=2).value = detail_line['date']
            detail_sheet.cell(row=detail_row, column=2).number_format = 'dd/mm/yyyy'
            detail_sheet.cell(row=detail_row, column=3).value = detail_line['customer']
            detail_sheet.cell(row=detail_row, column=4).value = detail_line['unit']
            detail_sheet.cell(row=detail_row, column=5).value = detail_line['discount_percentage']
            detail_sheet.cell(row=detail_row, column=5).number_format = '0.00"%"'
            detail_sheet.cell(row=detail_row, column=6).value = detail_line['price_before_discount']
            detail_sheet.cell(row=detail_row, column=6).number_format = '#,##0'
            detail_sheet.cell(row=detail_row, column=7).value = detail_line['price']
            detail_sheet.cell(row=detail_row, column=7).number_format = '#,##0'
            detail_sheet.cell(row=detail_row, column=8).value = detail_line['discount_approved_by']
            detail_row += 1

        # Save and download
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        attachment = self.env['ir.attachment'].create({
            'name': f'Sales_Analysis_{self.date_from.year}.xlsx',
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'res_model': 'sale.proposal.sales.analysis.wizard',
            'res_id': self.id,
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }