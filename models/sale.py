from odoo import models, fields, api, _


class SaleOrde(models.Model):
    _inherit = "sale.order"

    project_ids = fields.Many2many(
        "project.project",
        compute="_compute_project_ids",
        string="Projects",
        copy=False,
        groups="project.group_project_user,project.group_project_milestone",
        help="Projects used in this sales order.",
    )
    project_line_ids = fields.Many2many(
        "project.project",
        "project_project_line_ids",
        "order_id",
        "project_id",
        string="Projects",
    )
    project_count = fields.Integer(
        string="Number of Projects",
        compute="_compute_project_ids",
        groups="project.group_project_user",
    )

    @api.depends("order_line.product_id.project_id", "project_line_ids")
    def _compute_tasks_ids(self):
        for order in self:
            line_ids = order.order_line.ids or []
            domain = [
                ("project_id", "!=", False),
                "|",
                ("sale_line_id", "in", line_ids),
                ("sale_order_id", "=", order.id),
            ]
            tasks = self.env["project.task"].search(domain)
            order.tasks_ids = tasks
            order.tasks_count = len(tasks) + len(order.project_line_ids)

    @api.depends("order_line.product_id", "order_line.project_id", "project_line_ids")
    def _compute_project_ids(self):
        for order in self:
            projects = order.order_line.mapped("product_id.project_id")
            projects |= order.order_line.mapped("project_id")
            projects |= order.project_id
            order.project_ids = projects + order.project_line_ids
            order.project_count = len(projects) + len(order.project_line_ids)

    def action_confirm(self):
        res = super().action_confirm()
        backlog_state_id = self.env["backlog.stages"].search(
            [("stages_type", "=", "to_be_planned")]
        )
        for line in self.order_line:
            line.bklg_state = "to_be_planned"
            line.backlog_state_id = backlog_state_id.id if backlog_state_id else False
            line.date_deadline = False
        return res
