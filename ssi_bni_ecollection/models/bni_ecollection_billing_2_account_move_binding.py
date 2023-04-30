# Copyright 2022 OpenSynergy Indonesia
# Copyright 2022 PT. Simetri Sinergi Indonesia
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import json
import logging

import requests

from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.component.core import Component

from ..lib.bni_encryption import BniEnc

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

    def action_create_invoice(self):
        for record in self.sudo():
            record.with_delay()._create_invoice()

    def _create_invoice(self):
        self.ensure_one()

        if not self._get_receivable_move_line():
            error_msg = _("No receivable move line")
            raise UserError(error_msg)

        self._post_data()

    def _prepare_billing_data(self):
        self.ensure_one()
        invoice = self.odoo_id
        backend = self.backend_id
        partner = invoice.partner_id.commercial_partner_id
        ml = self._get_receivable_move_line()
        return {
            "type": "createbilling",
            "client_id": backend.client_id,
            "trx_id": invoice.name,
            "trx_amount": ml.debit,
            "billing_type": "c",
            "customer_name": partner.name,
            "customer_email": partner.email or "-",
            "customer_phone": partner.mobile or "-",
            "description": invoice.payment_reference,
        }

    def _encrypt_billing_data(self):
        backend = self.backend_id
        json_data = self._prepare_billing_data()
        BNI = BniEnc()
        return BNI.encrypt(json_data, backend.client_id, backend.secret_key)

    def _post_data(self):
        backend = self.backend_id
        url = backend.ecollection_url
        prefix = backend.prefix_va
        client_id = backend.client_id

        headers = {
            "Content-Type": "application/json",
        }

        data = self._encrypt_billing_data()

        payload = json.dumps({"client_id": client_id, "prefix": prefix, "data": data})

        try:
            response = requests.request("POST", url, headers=headers, data=payload)
            result = response.json()
            self._process_result(result)
        except Exception:
            raise UserError(response.text)

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
        self.write(
            {
                "trx_id": data["trx_id"],
                "va": data["virtual_account"],
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
            record.with_delay()._create_invoice()


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

        Binding.create(
            {
                "backend_id": record.company_id.bni_ecollection_backend_id.id,
                "odoo_id": record.id,
                "bni_va": "-",
                "auto_create_bni_ecollection_invoice": auto_create,
            }
        )

    def _delete_bni_ecollection_invoice_binding(self, record):
        if not record.company_id.bni_ecollection_backend_id:
            return True

        backend = record.company_id.bni_ecollection_backend_id
        Binding = self.env["bni_ecollection_billing_2_account_move_binding"]

        criteria = [("backend_id", "=", backend.id), ("odoo_id", "=", record.id)]

        Binding.search(criteria).unlink()
