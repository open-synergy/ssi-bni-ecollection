# Copyright 2022 OpenSynergy Indonesia
# Copyright 2022 PT. Simetri Sinergi Indonesia
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class AccountJournal(models.Model):
    _name = "account.journal"
    _inherit = [
        "account.journal",
    ]

    is_bni_ecollection_billing = fields.Boolean(
        string="BNI e-Collection Billing",
    )
    auto_create_bni_ecollection_invoice = fields.Boolean(
        string="Auto Create BNI e-Collection Billing",
    )
