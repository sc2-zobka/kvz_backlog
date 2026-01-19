# from odoo import http


# class KvzBacklog(http.Controller):
#     @http.route('/backlog/backlog', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/backlog/backlog/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('backlog.listing', {
#             'root': '/backlog/backlog',
#             'objects': http.request.env['backlog.backlog'].search([]),
#         })

#     @http.route('/backlog/backlog/objects/<model("backlog.backlog"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('backlog.object', {
#             'object': obj
#         })
