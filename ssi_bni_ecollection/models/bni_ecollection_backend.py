# Copyright 2022 OpenSynergy Indonesia
# Copyright 2022 PT. Simetri Sinergi Indonesia
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).


from odoo import fields, models


class BNIeCollectionBackend(models.Model):
    _name = "bni_ecollection_backend"
    _inherit = [
        "mixin.master_data",
        "connector.backend",
    ]
    _description = "BNI e-Collection Backend"

    company_id = fields.Many2one(
        string="Company",
        comodel_name="res.company",
        required=True,
    )
    client_id = fields.Char(
        string="Cliend ID",
        required=True,
    )
    secret_key = fields.Char(
        string="Secret Key",
        required=True,
    )
    prefix_va = fields.Char(
        string="Prefix VA",
        required=True,
    )
    ecollection_url = fields.Char(
        string="BNI e-Collection URL",
        required=True,
    )
    billing_account_receivable_ids = fields.Many2many(
        string="Billing Account Receivables",
        comodel_name="account.account",
        relation="rel_bni_ecollection_backend_2_account_receivable",
        column1="backend_id",
        column2="account_id",
    )
    billing_journal_ids = fields.Many2many(
        string="Billing Journals",
        comodel_name="account.journal",
        relation="rel_bni_ecollection_backend_2_journal",
        column1="backend_id",
        column2="journal_id",
    )
