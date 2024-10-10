# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class service_team(models.Model):
    _name = 'service.team'

    name = fields.Char(string='Team Name', required=True)
    team_leader_id = fields.Many2one('res.users', string='Team Leader', required=True)
    team_member_ids = fields.Many2many('res.users', string='Team Members')
    
class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_booking_order = fields.Boolean(string='Is Booking Order')
    service_team_id = fields.Many2one('service.team', string='Team')
    team_leader_id = fields.Many2one('res.users', string='Team Leader')
    team_member_ids = fields.Many2many('res.users', string='Team Members')
    work_order_id = fields.Many2one('work.order', string="Work Order")
    booking_start = fields.Datetime(string='Booking Start')
    booking_end = fields.Datetime(string='Booking End')
    
    def action_view_work_order(self):
        return {
            'name': _('Work Order'),
            'view_mode': 'form',
            'res_model': 'work.order',
            'type': 'ir.actions.act_window',
            'res_id': self.work_order_id.id,
        }
    
    @api.multi
    def action_confirm(self):
        work_orders = self.env['work.order'].search([
            ('team_id', '=', self.team_id.id),
            ('state', 'not in', ('cancelled','done')),
            ('planned_start', '<=', self.booking_end),
            ('planned_end', '>=', self.booking_start)
        ])
        if work_orders:
            raise UserError("Team is not available during this period, already booked on %s, Please book on another date." % work_orders.sale_order_id.name)
        
        res = super(SaleOrder, self).action_confirm()
        if res:
            work_order_vals = {
                'name': self.env['ir.sequence'].next_by_code('work.order'),
                'sale_order_id': self.id,
                'team_id': self.team_id.id,
                'team_leader_id': self.team_leader_id.id,
                'team_member_ids': [(6, 0, self.team_member_ids.ids)],
                'planned_start': self.booking_start,
                'planned_end': self.booking_end,
                'state': 'pending'
            }
            work_order = self.env['work.order'].create(work_order_vals)
            self.work_order_id = work_order.id
        return res
    
    @api.multi
    def action_check_availability(self):
        for order in self:
            work_orders = self.env['work.order'].search([
                ('team_id', '=', order.team_id.id),
                ('state', 'not in', ('cancelled','done')),
                ('planned_start', '<=', order.booking_end),
                ('planned_end', '>=', order.booking_start)
            ])

            if work_orders:
                raise UserError("Team already has work order during that period on %s" % work_orders.sale_order_id.name)
            else:
                raise ValidationError("Team is available for booking")
        
    @api.onchange('service_team_id')
    def _onchange_service_team_id(self):
        if self.service_team_id:
            self.team_leader_id = self.service_team_id.team_leader_id.id
            self.team_member_ids = self.service_team_id.team_member_ids.ids
    
class WorkOrder(models.Model):
    _name = 'work.order'
    _description = 'Work Order'
    _order = 'planned_start desc'

    name = fields.Char(string='WO Number', required=True, copy=False, readonly=True, default=lambda self: ('New'))
    sale_order_id = fields.Many2one('sale.order', string='Booking Order Reference', readonly=True)
    team_id = fields.Many2one('service.team', string='Team', required=True)
    team_leader_id = fields.Many2one('res.users', string='Team Leader', required=True)
    team_member_ids = fields.Many2many('res.users', string='Team Members')
    planned_start = fields.Datetime(string='Planned Start', required=True)
    planned_end = fields.Datetime(string='Planned End', required=True)
    date_start = fields.Datetime(string='Date Start', readonly=True)
    date_end = fields.Datetime(string='Date End', readonly=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled')
    ], string='State', default='pending', readonly=False)
    notes = fields.Text(string='Notes')
    
    @api.model
    def create(self, vals):
        res = super(WorkOrder, self).create(vals)
        print("Masuk")
        print(res.name)
        if res and res.name == 'New':
            res.name = self.env['ir.sequence'].next_by_code('work.order')
        return res
    
    @api.multi
    def action_start_work(self):
        self.state = 'in_progress'
        self.date_start = fields.Datetime.now()

    @api.multi
    def action_end_work(self):
        self.state = 'done'
        self.date_end = fields.Datetime.now()

    @api.multi
    def action_reset_work(self):
        self.state = 'pending'
        self.date_start = False

    @api.multi
    def action_cancel_work(self):
        return {
            'name': 'Reason for Cancellation',
            'type': 'ir.actions.act_window',
            'res_model': 'work.order.cancel',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
        }
        
class WorkOrderCancel(models.TransientModel):
    _name = 'work.order.cancel'

    reason = fields.Text('Reason')

    def action_cancel_confirm(self):
        work_order = self.env['work.order'].browse(self.env.context.get('active_id'))
        work_order.state = 'cancelled'
        work_order.notes = (work_order.notes or '') + "\nAlasan Cancel: " + self.reason
