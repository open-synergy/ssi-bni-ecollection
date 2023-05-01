# Copyright 2022 OpenSynergy Indonesia
# Copyright 2022 PT. Simetri Sinergi Indonesia
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import json
import logging

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.component.core import Component

from ..bni_encryption import BniEnc

_logger = logging.getLogger(__name__)


class BNIeCollectionBilling2AccountMoveBinding(models.Model):
    _name = "bni_ecollection_billing_2_account_move_binding"
    _inherit = [
        "external.binding",
    ]
    _inherits = {
        "account.move": "odoo_id",
    }
    _description = "BNI e-Collection Billing to Account Move Binding"

    backend_id = fields.Many2one(
        comodel_name="bni_ecollection_backend",
        string="BNI e-Collection Backend",
        required=True,
        ondelete="restrict",
    )
    odoo_id = fields.Many2one(
        string="# Move",
        comodel_name="account.move",
        required=True,
        ondelete="cascade",
    )
    bni_va = fields.Char(
        string="BNI VA",
        required=False,
    )
    auto_create_bni_ecollection_invoice = fields.Boolean(
        string="Auto Create BNI e-Collection Invoice",
        default=False,
    )
    trx_id = fields.Char(
        string="Trx ID",
        required=False,
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
        "bni_va",
    )
    def _compute_create_update(self):
        for record in self:
            create_ok = update_ok = False
            if not record.job_id and record.bni_va == "-":
                create_ok = True
            elif not record.job_id and record.bni_va != "-":
                update_ok = True
            self.create_ok = create_ok
            self.update_ok = update_ok

    def action_create_invoice(self):
        for record in self.sudo():
            record._create_update_billing()

    def action_update_invoice(self):
        for record in self.sudo():
            record._create_update_billing()

    def action_payment_inquiry(self):
        for record in self.sudo():
            record._payment_inquiry()

    def action_requeue(self):
        for record in self.sudo():
            record._requeue()

    def _payment_inquiry(self):
        self.ensure_one()
        description = "Update payment billing for %s" % (self.name)
        job = self.with_delay(description=_(description))._post_payment_inquiry()
        QueueJob = self.env["queue.job"]
        criteria = [("uuid", "=", job.uuid)]
        self.write(
            {
                "job_id": QueueJob.search(criteria, limit=1).id,
            }
        )

    def _post_payment_inquiry(self):
        self.ensure_one()
        backend = self.backend_id
        url = backend.ecollection_url
        prefix = backend.prefix_va
        client_id = backend.client_id
        headers = self._get_headers()

        json_data = self._prepare_payment_inquiry_data()
        data = self._encrypt_billing_data(json_data)

        payload = json.dumps({"client_id": client_id, "prefix": prefix, "data": data})

        try:
            response = requests.request("POST", url, headers=headers, data=payload)
            result = response.json()
            self._process_payment_result(result)
        except Exception as e:
            raise UserError(str(e))

    def _process_payment_result(self, result):
        if result["status"] == "000":
            Binding = self.env["bni_ecollection_payment_2_bank_receipt_binding"]
            hashed_string = result["data"]
            Binding._create_bank_receipt_binding(hashed_string)
            self.write(
                {
                    "job_id": False,
                }
            )
        else:
            raise UserError(result)

    def _prepare_payment_inquiry_data(self):
        self.ensure_one()
        invoice = self.odoo_id
        backend = self.backend_id
        result = {
            "client_id": backend.client_id,
            "trx_id": invoice.name,
            "type": "inquirybilling",
        }
        return result

    def _requeue(self):
        self.ensure_one()

        if not self.job_id:
            return True

        self.job_id.requeue()

    def _create_update_billing(self):
        self.ensure_one()

        if not self._get_receivable_move_line():
            error_msg = _("No receivable move line")
            raise UserError(error_msg)

        if self.bni_va == "-":
            description = "Creating billing for %s" % (self.name)
            job = self.with_delay(description=_(description))._create_invoice()
        else:
            description = "Update billing for %s" % (self.name)
            job = self.with_delay(description=_(description))._update_invoice()

        QueueJob = self.env["queue.job"]
        criteria = [("uuid", "=", job.uuid)]
        self.write(
            {
                "job_id": QueueJob.search(criteria, limit=1).id,
            }
        )

    def _prepare_billing_create_data(self):
        self.ensure_one()
        result = self._prepare_billing_data()
        result.update(
            {
                "type": "createbilling",
                "billing_type": "c",
            }
        )
        return result

    def _prepare_billing_update_data(self):
        self.ensure_one()
        result = self._prepare_billing_data()
        result.update(
            {
                "type": "updatebilling",
            }
        )
        return result

    def _prepare_billing_data(self):
        self.ensure_one()
        invoice = self.odoo_id
        backend = self.backend_id
        ml = self._get_receivable_move_line()
        partner = ml.partner_id.commercial_partner_id
        amount = int(ml.debit)
        result = {
            "client_id": backend.client_id,
            "trx_id": invoice.name,
            "trx_amount": amount,
            "customer_name": partner.name,
            "customer_phone": partner.mobile or "-",
            "description": invoice.name,
        }
        if invoice.partner_id.email:
            result.update(
                {
                    "customer_email": invoice.partner_id.email,
                }
            )
        return result

    def _encrypt_billing_data(self, json_data):
        backend = self.backend_id
        BNI = BniEnc()
        return BNI.encrypt(json_data, backend.client_id, backend.secret_key)

    def _get_headers(self):
        self.ensure_one()
        return {
            "Content-Type": "application/json",
        }

    def _create_invoice(self):
        backend = self.backend_id
        url = backend.ecollection_url
        prefix = backend.prefix_va
        client_id = backend.client_id
        headers = self._get_headers()
        json_data = self._prepare_billing_create_data()
        data = self._encrypt_billing_data(json_data)

        payload = json.dumps({"client_id": client_id, "prefix": prefix, "data": data})

        try:
            response = requests.request("POST", url, headers=headers, data=payload)
            result = response.json()
            self._process_result(result)
        except Exception as e:
            raise UserError(str(e))

    def _update_invoice(self):
        backend = self.backend_id
        url = backend.ecollection_url
        prefix = backend.prefix_va
        client_id = backend.client_id
        headers = self._get_headers()
        json_data = self._prepare_billing_update_data()
        data = self._encrypt_billing_data(json_data)

        payload = json.dumps({"client_id": client_id, "prefix": prefix, "data": data})

        try:
            response = requests.request("POST", url, headers=headers, data=payload)
            result = response.json()
            self._process_result(result)
        except Exception as e:
            raise UserError(str(e))

    def _process_result(self, result):
        if result["status"] == "000":
            self._update_binding(result)
        else:
            raise UserError(result)

    def _update_binding(self, result):
        hashed_string = result["data"]
        backend = self.backend_id
        BNI = BniEnc()
        data = BNI.decrypt(hashed_string, backend.client_id, backend.secret_key)
        data_dict = json.loads(data)
        self.write(
            {
                "bni_va": data_dict["virtual_account"],
                "job_id": False,
                "narration": str(data),
                "trx_id": data_dict["trx_id"],
            }
        )

    def _get_receivable_move_line(self):
        result = False
        invoice = self.odoo_id
        backend = self.backend_id

        if not backend.billing_account_receivable_ids:
            return result

        accounts = backend.billing_account_receivable_ids
        ML = self.env["account.move.line"]
        criteria = [
            ("move_id", "=", invoice.id),
            ("account_id", "in", accounts.ids),
            ("debit", ">", 0.0),
        ]
        move_lines = ML.search(criteria)

        if len(move_lines) > 0:
            result = move_lines[0]

        return result


class BNIeCollectionBilling2AccountMoveBindingListener(Component):
    _name = "bni_ecollection_billing_2_account_move_binding_listener"
    _inherit = "base.event.listener"
    _apply_on = ["bni_ecollection_billing_2_account_move_binding"]

    def on_record_create(self, record, fields=None):
        if record.auto_create_bni_ecollection_invoice:
            record._create_update_billing()


class AccountMove(models.Model):
    _name = "account.move"
    _inherit = "account.move"

    bni_ecollection_billing_bind_ids = fields.One2many(
        string="BNI e-Collection VA Bind",
        comodel_name="bni_ecollection_billing_2_account_move_binding",
        inverse_name="odoo_id",
    )


class BNIeCollectionAccountMoveListener(Component):
    _name = "bni_ecollection_account_move_listener"
    _inherit = "base.event.listener"
    _apply_on = ["account.move"]

    def on_account_move_post(self, record):
        self._create_bni_ecollection_invoice_binding(record)

    def on_account_move_cancel(self, record):
        self._delete_bni_ecollection_invoice_binding(record)

    def on_account_move_draft(self, record):
        self._delete_bni_ecollection_invoice_binding(record)

    def _create_bni_ecollection_invoice_binding(self, record):
        Binding = self.env["bni_ecollection_billing_2_account_move_binding"]

        if not record.company_id.bni_ecollection_backend_id:
            return True

        backend = record.company_id.bni_ecollection_backend_id

        if record.journal_id.id not in backend.billing_journal_ids.ids:
            return True

        auto_create = record.journal_id.auto_create_bni_ecollection_invoice

        criteria = [("odoo_id", "=", record.id), ("backend_id", "=", backend.id)]

        bindings = Binding.search(criteria)

        if len(bindings) == 0:
            Binding.create(
                {
                    "backend_id": record.company_id.bni_ecollection_backend_id.id,
                    "odoo_id": record.id,
                    "bni_va": "-",
                    "auto_create_bni_ecollection_invoice": auto_create,
                }
            )
        else:
            if auto_create:
                bindings[0]._create_update_billing()

    def _delete_bni_ecollection_invoice_binding(self, record):
        if not record.company_id.bni_ecollection_backend_id:
            return True

        backend = record.company_id.bni_ecollection_backend_id
        Binding = self.env["bni_ecollection_billing_2_account_move_binding"]

        criteria = [
            ("backend_id", "=", backend.id),
            ("odoo_id", "=", record.id),
            ("bni_va", "=", "-"),
        ]

        Binding.search(criteria).unlink()
