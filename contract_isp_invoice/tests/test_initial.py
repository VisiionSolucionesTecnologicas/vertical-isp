# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 Savoir-faire Linux (<http://www.savoirfairelinux.com>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import fields
from openerp.tests.common import TransactionCase

from openerp.addons.contract_isp.contract import (
    LINE_TYPE_RECURRENT,
)

from ..invoice import (
    PROCESS_INITIAL,
)
from .common import ServiceSetup


class TestInitialInvoice(ServiceSetup, TransactionCase):
    """ Test Initial Invoice and Voucher """

    def setUp(self):
        super(TestInitialInvoice, self).setUp()
        self._common_setup()

    def _create_products(self):
        super(TestInitialInvoice, self)._create_products()
        self.p_unit = self.product_obj.create(self.cr, self.uid, {
            "name": "1$",
            "type": "service",
            "analytic_line_type": LINE_TYPE_RECURRENT,
            "code": "UNIT",
            "list_price": 1.00,
            "taxes_id": [(4, self.tax)],
        })

    def _configure_company(self):
        super(TestInitialInvoice, self)._configure_company()
        self.tax = self.registry("account.tax").create(
            self.cr, self.uid, {
                "name": "QC-Equiv",
                "code": "UNIT_QC",
                "type_tax_use": "all",
                "type": "percent",
                "amount": 1.00,
                "sequence": 1,
                "child_depend": True,
                "child_ids": [
                    (0, 0, {
                        "name": "TX1",
                        "code": "UNIT_S1",
                        "type_tax_use": "all",
                        "type": "percent",
                        "amount": 0.05,
                        "sequence": 1,
                    }),
                    (0, 0, {
                        "name": "TX2",
                        "code": "UNIT_S2",
                        "type_tax_use": "all",
                        "type": "percent",
                        "amount": 0.09975,
                        "sequence": 2,
                    }),
                ],
            })

    def _create_invoice(self):
        cr, uid = self.cr, self.uid
        ctx = {}
        date_today = fields.date.context_today(self.account_obj, cr, uid)
        for line in self.account_obj.browse(
                cr, uid, self.account_id).contract_service_ids:
            line.create_analytic_line(
                mode='subscription',
                date=date_today,
                context=ctx)

        inv = self.account_obj.create_invoice(
            cr, uid, self.account_id,
            source_process=PROCESS_INITIAL,
        )[0]
        return self.invoice_obj.browse(cr, uid, inv)

    def test_rounding_1(self):
        """
        Specific example where we had rounding errors

            1.000   20.00
            1.000   49.95
            1.000   32.95
            -1.000  9.95
            1.000   9.95

        With QC Taxes (5% and 9.975%)

        Invoice is 102.90 + 15.41 = 118.31
        Voucher should have similar initial amount
        """
        cr, uid = self.cr, self.uid
        for qty in (20, 49.95, 32.95, 9.95, -9.95):
            service = self.service_obj.on_change_product_id(
                cr, uid, [], self.p_unit,
            )["value"]
            service.update({
                "product_id": self.p_unit,
                "account_id": self.account_id,
                "qty": qty,
            })
            self.service_obj.create(cr, uid, service)

        voucher = self.account_obj.prepare_voucher(
            cr, uid, [self.account_id])

        invoice = self._create_invoice()
        self.assertEquals(voucher["context"]["default_amount"],
                          invoice.amount_total,
                          "Exepcted default voucher amount to match invoice")
