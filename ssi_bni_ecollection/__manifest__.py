# Copyright 2023 OpenSynergy Indonesia
# Copyright 2023 PT. Simetri Sinergi Indonesia
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

{
    "name": "BNI e-Collection Integration",
    "version": "14.0.2.2.0",
    "category": "Accounting",
    "website": "https://simetri-sinergi.id",
    "author": "PT. Simetri Sinergi Indonesia, OpenSynergy Indonesia",
    "license": "LGPL-3",
    "installable": True,
    "depends": [
        "ssi_connector_financial_accounting",
        "ssi_voucher_bank_cash",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/queue_job_function_data.xml",
        "menu.xml",
        "views/bni_ecollection_backend_views.xml",
        "views/bni_ecollection_payment_2_bank_receipt_binding_views.xml",
        "views/account_move_views.xml",
        "views/account_journal_views.xml",
        "views/res_company_views.xml",
        "views/account_bank_receipt_views.xml",
    ],
    "demo": [],
    "images": [],
}
