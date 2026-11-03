# -*- coding: utf-8 -*-

from odoo import models, api


class ResCurrencyArabic(models.Model):
    _inherit = 'res.currency'

    def amount_to_text_ar(self, amount):
        """Convert amount to Arabic text"""

        def number_to_arabic(num):
            if num == 0:
                return 'صفر'

            ones = ['', 'واحد', 'اثنان', 'ثلاثة', 'أربعة', 'خمسة', 'ستة', 'سبعة', 'ثمانية', 'تسعة']
            tens = ['', '', 'عشرون', 'ثلاثون', 'أربعون', 'خمسون', 'ستون', 'سبعون', 'ثمانون', 'تسعون']
            hundreds = ['', 'مائة', 'مائتان', 'ثلاثمائة', 'أربعمائة', 'خمسمائة', 'ستمائة', 'سبعمائة', 'ثماني مائة',
                        'تسعمائة']

            eleven_to_nineteen = {
                10: 'عشرة',
                11: 'أحد عشر',
                12: 'اثنا عشر',
                13: 'ثلاثة عشر',
                14: 'أربعة عشر',
                15: 'خمسة عشر',
                16: 'ستة عشر',
                17: 'سبعة عشر',
                18: 'ثمانية عشر',
                19: 'تسعة عشر'
            }

            # Handle numbers 1-9
            if num < 10:
                return ones[num]

            # Handle 10-19
            elif num <= 19:
                return eleven_to_nineteen.get(num, '')

            # Handle 20-99
            elif num < 100:
                ten = num // 10
                one = num % 10
                if one == 0:
                    return tens[ten]
                else:
                    return ones[one] + ' و ' + tens[ten]

            # Handle 100-999
            elif num < 1000:
                hundred = num // 100
                remainder = num % 100
                result = hundreds[hundred]
                if remainder > 0:
                    result += ' و ' + number_to_arabic(remainder)
                return result

            # Handle 1000-999999
            elif num < 1000000:
                thousands = num // 1000
                remainder = num % 1000

                if thousands == 1:
                    result = 'ألف'
                elif thousands == 2:
                    result = 'ألفان'
                elif 3 <= thousands <= 10:
                    result = number_to_arabic(thousands) + ' آلاف'
                else:
                    result = number_to_arabic(thousands) + ' ألف'

                if remainder > 0:
                    result += ' و ' + number_to_arabic(remainder)
                return result

            # Handle millions
            elif num < 1000000000:
                millions = num // 1000000
                remainder = num % 1000000

                if millions == 1:
                    result = 'مليون'
                elif millions == 2:
                    result = 'مليونان'
                elif 3 <= millions <= 10:
                    result = number_to_arabic(millions) + ' ملايين'
                else:
                    result = number_to_arabic(millions) + ' مليون'

                if remainder > 0:
                    result += ' و ' + number_to_arabic(remainder)
                return result

            else:
                # Fallback for very large numbers
                return str(num)

        # Handle negative amounts
        if amount < 0:
            amount = abs(amount)
            prefix = 'سالب '
        else:
            prefix = ''

        # Split into integer and decimal parts
        integer_part = int(amount)
        decimal_part = int(round((amount - integer_part) * 100))

        # Convert integer part
        if integer_part == 0:
            result =  'صفر'
        else:
            result = number_to_arabic(integer_part)

        # Add currency name
        if self.name == 'EGP':
            if integer_part == 0:
                result += ' جنيه'
            elif integer_part == 1:
                result += ' جنيه'
            elif integer_part == 2:
                result += ' جنيهان'
            elif 3 <= integer_part <= 10:
                result += ' جنيهات'
            else:
                result += ' جنيه'
        elif self.name == 'USD':
            if integer_part == 1:
                result += ' دولار'
            elif integer_part == 2:
                result += ' دولاران'
            else:
                result += ' دولار'
        else:
            result += ' ' + self.name

        # Add decimal part if exists
        if decimal_part > 0:
            result += ' و ' + number_to_arabic(decimal_part)
            if self.name == 'EGP':
                result += ' قرش'
            else:
                result += ' سنت'

        return result