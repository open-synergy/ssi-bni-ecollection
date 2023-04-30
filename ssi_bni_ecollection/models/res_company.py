# Copyright 2022 OpenSynergy Indonesia
# Copyright 2022 PT. Simetri Sinergi Indonesia
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class ResCompany(models.Model):
    _name = "res.company"
    _inherit = [
        "res.company",
    ]

    bni_ecollection_backend_id = fields.Many2one(
        string="Active BNI e-Collection Backend",
        comodel_name="bni_ecollection_backend",
    )
