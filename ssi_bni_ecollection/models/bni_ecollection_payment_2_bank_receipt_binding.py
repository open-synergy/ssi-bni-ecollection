# Copyright 2022 OpenSynergy Indonesia
# Copyright 2022 PT. Simetri Sinergi Indonesia
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import json
import logging

from odoo import _, api, fields, models

from odoo.addons.component.core import Component

from ..bni_encryption import BniEnc

_logger = logging.getLogger(__name__)


class BNIeCollectionPayment2BankReceiptBinding(models.Model):
    _name = "bni_ecollection_payment_2_bank_receipt_binding"
    _inherit = [
        "external.binding",
    ]
    _description = "BNI e-Collection Payment to Bank Receipt Binding"

    backend_id = fields.Many2one(
        comodel_name="bni_ecollection_backend",
        string="BNI e-Collection Backend",
        required=True,
        ondelete="restrict",
    )
    odoo_id = fields.Many2one(
        string="# Bank Receipt",
        comodel_name="account.bank_receipt",
        ondelete="set null",
    )
    virtual_account = fields.Char(
        string="virtual_account",
    )
    customer_name = fields.Char(
        string="customer_name",
    )
    trx_id = fields.Char(
        string="trx_id",
    )
    payment_amount = fields.Float(
        string="payment_amount",
    )
    payment_ntb = fields.Char(
        string="payment_ntb",
    )
    datetime_payment = fields.Datetime(
        string="datetime_payment",
    )
    job_id = fields.Many2one(
        string="Job Queue",
        comodel_name="queue.job",
        ondelete="set null",
    )
    job_state = fields.Selection(
        string="Job State",
        related="job_id.state",
    )
    create_ok = fields.Boolean(
        string="Create Ok",
        compute="_compute_create_update",
        store=False,
    )
    update_ok = fields.Boolean(
        string="Update Ok",
        compute="_compute_create_update",
        store=False,
    )

    @api.depends(
        "job_id",
        "odoo_id",
    )
    def _compute_create_update(self):
        for record in self:
            create_ok = update_ok = False
            if not record.job_id and not record.odoo_id:
                create_ok = True
            elif not record.job_id and record.odoo_id:
                update_ok = True
            self.create_ok = create_ok
            self.update_ok = update_ok

    def action_create_bank_receipt(self):
        for record in self.sudo():
            record._create_update_bank_receipt()

    def _create_update_bank_receipt(self):
        self.ensure_one()

        if not self.odoo_id:
            description = "Payment %s" % (self.payment_ntb)
            job = self.with_delay(description=description)._create_bank_receipt()
            QueueJob = self.env["queue.job"]
            criteria = [("uuid", "=", job.uuid)]
            self.write(
                {
                    "job_id": QueueJob.search(criteria, limit=1).id,
                }
            )

    def _create_bank_receipt(self):
        self.ensure_one()
        BankReceipt = self.env["account.bank_receipt"]
        bank_receipt = BankReceipt.create(self._prepare_create_bank_receipt())
        self.write(
            {
                "odoo_id": bank_receipt.id,
                "job_id": False,
            }
        )

    def _prepare_create_bank_receipt(self):
        self.ensure_one()
        payment_date = self.datetime_payment.strftime("%Y-%m-%d")
        receivable_ml = self._get_receivable_move_line()
        description = "Payment for %s Ref: %s" % (self.trx_id, self.payment_ntb)
        backend = self.backend_id
        journal = backend.payment_journal_id
        result = {
            "date_voucher": payment_date,
            "partner_id": receivable_ml.partner_id.id,
            "journal_id": journal.id,
            "type_id": self.env.ref(
                "ssi_voucher_bank_cash.voucher_type_bank_receipt"
            ).id,
            "description": _(description),
            "account_id": journal.default_account_id.id,
            "amount": self.payment_amount,
            "line_cr_ids": [
                (
                    0,
                    0,
                    {
                        "account_id": receivable_ml.account_id.id,
                        "move_line_id": receivable_ml.id,
                        "partner_id": receivable_ml.partner_id.id,
                        "name": description,
                        "amount": self.payment_amount,
                    },
                )
            ],
        }
        return result

    def _get_receivable_move_line(self):
        result = False
        backend = self.backend_id

        if not backend.billing_account_receivable_ids:
            return result

        accounts = backend.billing_account_receivable_ids
        ML = self.env["account.move.line"]

        criteria = [
            ("move_id.name", "=", self.trx_id),
            ("account_id", "in", accounts.ids),
            ("debit", ">", 0.0),
        ]
        move_lines = ML.search(criteria)

        if len(move_lines) > 0:
            result = move_lines[0]

        return result

    @api.model
    def _decrypt_data(self, hashed_string):
        company = self.env.company
        backend = company.bni_ecollection_backend_id
        BNI = BniEnc()
        data = BNI.decrypt(hashed_string, backend.client_id, backend.secret_key)
        return json.loads(data)

    @api.model
    def _create_bank_receipt_binding(self, hashed_string):
        company = self.env.company
        backend = company.bni_ecollection_backend_id

        if not backend:
            return True

        data = self._decrypt_data(hashed_string)

        if data["payment_amount"] == 0.0:
            return True

        Binding = self.env["bni_ecollection_payment_2_bank_receipt_binding"]
        Binding.create(self._prepare_create_bank_receipt_binding(hashed_string))

    @api.model
    def _prepare_create_bank_receipt_binding(self, hashed_string):
        data = self._decrypt_data(hashed_string)
        company = self.env.company
        backend = company.bni_ecollection_backend_id
        return {
            "backend_id": backend.id,
            "virtual_account": data["virtual_account"],
            "customer_name": data["customer_name"],
            "trx_id": data["trx_id"],
            "payment_amount": data["payment_amount"],
            "payment_ntb": data["payment_ntb"],
            "datetime_payment": data["datetime_payment"],
        }


class BNIeCollectionPayment2BankReceiptBindingListener(Component):
    _name = "bni_ecollection_payment_2_bank_receipt_binding_listener"
    _inherit = "base.event.listener"
    _apply_on = ["bni_ecollection_payment_2_bank_receipt_binding_listener"]

    def on_record_create(self, record, fields=None):
        if record.auto_create_bni_ecollection_invoice:
            record._create_update_bank_receipt()


class AccountBankReceipt(models.Model):
    _name = "account.bank_receipt"
    _inherit = "account.bank_receipt"

    bni_ecollection_receipt_bind_ids = fields.One2many(
        string="BNI e-Collection Payment Bind",
        comodel_name="bni_ecollection_payment_2_bank_receipt_binding",
        inverse_name="odoo_id",
    )
