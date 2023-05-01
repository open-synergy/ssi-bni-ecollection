# Copyright 2022 OpenSynergy Indonesia
# Copyright 2022 PT. Simetri Sinergi Indonesia
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).


from odoo import api, fields, models


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
    # Billing
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
    # Payment
    payment_journal_id = fields.Many2one(
        string="Bank Journal",
        comodel_name="account.journal",
    )
    payment_cron_id = fields.Many2one(
        string="Payment Inquiry Cron",
        comodel_name="ir.cron",
        readonly=True,
    )

    def action_create_payment_cron(self):
        for record in self.sudo():
            record._create_payment_cron()

    def _create_payment_cron(self):
        self.ensure_one()
        Cron = self.env["ir.cron"]
        cron = Cron.create(self._prepare_create_payment_cron())
        self.write(
            {
                "payment_cron_id": cron.id,
            }
        )

    def _prepare_create_payment_cron(self):
        name = "Auto check payment for %s backend" % (self.name)
        code = "model._cron_check_payment(%s)" % (self.id)
        return {
            "name": name,
            "model_id": self.env.ref(
                "ssi_bni_ecollection.model_bni_ecollection_backend"
            ).id,
            "state": "code",
            "interval_number": 1,
            "interval_type": "days",
            "numbercall": -1,
            "code": code,
        }

    def action_delete_payment_cron(self):
        for record in self.sudo():
            record._delete_payment_cron()

    def _delete_payment_cron(self):
        self.ensure_one()
        self.payment_cron_id.unlink()

    @api.model
    def _cron_check_payment(self, backend_id):
        Binding = self.env["bni_ecollection_billing_2_account_move_binding"]
        criteria = [
            ("backend_id", "=", backend_id),
            ("bni_va", "!=", "-"),
            ("receivable_move_line_reconciled", "=", False),
        ]
        bindings = Binding.search(criteria)
        bindings.action_payment_inquiry()
