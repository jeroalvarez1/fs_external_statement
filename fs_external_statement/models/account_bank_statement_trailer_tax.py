from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AccountBankSettlementTrailerTax(models.Model):
    _name = "account.bank.settlement.trailer.tax"

    # Base
    name = fields.Html(
        string='Nombre',
        compute='_compute_name',
        store=True
    )
    total = fields.Float(
        string='Monto total',
        digits=(16, 2),
        help="Monto total de la transacción"
    )

    # Relaciones
    settlement_tax_id = fields.Many2one(
        'settlement.tax',
        string='Impuesto sobre la liquidación',
        required=True,
        ondelete='cascade',
        index=True,
    )
    parent_type = fields.Selection(
        related='settlement_tax_id.type',
        store=True
    )
    statement_id = fields.Many2one(
        'account.bank.statement',
        string='Extracto Bancario',
        ondelete='cascade',
        required=True,
        index=True,
    )
    base_settlement_tax_id = fields.Many2one(
        'settlement.tax', compute='_compute_base_settlement_tax_id', store=True
    )

    @api.constrains('settlement_tax_id', 'statement_id')
    def _check_unique_tax_per_statement(self):
        for record in self:
            others = self.search([
                ('id', '!=', record.id),
                ('settlement_tax_id', '=', record.settlement_tax_id.id),
                ('statement_id', '=', record.statement_id.id),
            ])
            if others:
                raise ValidationError("El impuesto ya existe en este extracto bancario.")

    @api.depends('settlement_tax_id')
    def _compute_name(self):
        for record in self:
            if record.settlement_tax_id.type == 'tax':
                record.name = f"<p style='margin-left:30px'>{record.settlement_tax_id.name}</p>"
            elif record.settlement_tax_id.type == 'net':
                record.name = f'<b>{record.settlement_tax_id.name}</b>'

    @api.depends('settlement_tax_id', 'settlement_tax_id.parent_id')
    def _compute_base_settlement_tax_id(self):
        for record in self:
            parent_settlement_tax_id = record.settlement_tax_id.parent_id
            if parent_settlement_tax_id:
                record.base_settlement_tax_id = parent_settlement_tax_id
            else:
                record.base_settlement_tax_id = record.settlement_tax_id