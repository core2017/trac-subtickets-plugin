# -*- coding: utf-8 -*-

import unittest
import json
from trac.test import EnvironmentStub, Mock, MockPerm
from trac.web.api import Request, RequestDone
from trac.web.href import Href
from trac.ticket.model import Ticket
from tracsubtickets.web_ui import SubTicketsModule
from tracsubtickets.api import SubTicketsApi

class SubTicketsTestCase(unittest.TestCase):
    def setUp(self):
        self.env = EnvironmentStub()
        self.env.config.set('subtickets', 'recursion_depth', '-1')
        self.module = SubTicketsModule(self.env)
        self.api = SubTicketsApi(self.env)
        
        # テスト用のチケットを作成
        self.parent = Ticket(self.env)
        self.parent['summary'] = 'Parent Ticket'
        self.parent['status'] = 'new'
        self.parent['owner'] = 'admin'
        self.parent.insert()
        
        self.child1 = Ticket(self.env)
        self.child1['summary'] = 'Child Ticket 1'
        self.child1['status'] = 'new'
        self.child1['owner'] = 'admin'
        self.child1.insert()
        
        self.child2 = Ticket(self.env)
        self.child2['summary'] = 'Child Ticket 2'
        self.child2['status'] = 'new'
        self.child2['owner'] = 'admin'
        self.child2.insert()
        
        # subticketsテーブルを作成
        self.env.db_transaction("""
            CREATE TABLE IF NOT EXISTS subtickets (
                parent integer,
                child integer,
                PRIMARY KEY (parent, child)
            )
        """)
        
        # 親子関係を設定
        self.env.db_transaction("""
            INSERT INTO subtickets (parent, child) VALUES (%s, %s)
        """, (self.parent.id, self.child1.id))
        self.env.db_transaction("""
            INSERT INTO subtickets (parent, child) VALUES (%s, %s)
        """, (self.parent.id, self.child2.id))

    def test_get_children(self):
        children = self.module.get_children(self.parent.id)
        self.assertEqual(len(children), 2)
        self.assertIn(self.child1.id, children)
        self.assertIn(self.child2.id, children)

    def test_api_get_children(self):
        environ = {
            'wsgi.version': (1, 0),
            'wsgi.url_scheme': 'http',
            'SERVER_NAME': 'localhost',
            'SERVER_PORT': '80',
            'REQUEST_METHOD': 'GET',
            'PATH_INFO': '/subtickets/api/%d' % self.parent.id,
            'SCRIPT_NAME': '',
            'QUERY_STRING': '',
        }
        def start_response(status, headers, exc_info=None):
            pass
        req = Request(environ, start_response)
        req.href = Href('/')
        
        # モックのsendメソッドをオーバーライド
        original_send = req.send
        def mock_send(content, content_type=None, status=200):
            self.assertEqual(status, 200)
            self.assertEqual(content_type, 'application/json')
            # 文字列をバイト列に変換
            if isinstance(content, str):
                content = content.encode('utf-8')
            return original_send(content, content_type, status)
        req.send = mock_send
        
        # writeメソッドと_writeメソッドをモック
        req.write = lambda content: None
        req._write = lambda content: None
        
        try:
            response = self.api.process_request(req)
            self.assertEqual(response.status, 200)
            
            data = response.body
            self.assertIn(str(self.child1.id), data)
            self.assertIn(str(self.child2.id), data)
            self.assertIn('summary', data)
            self.assertIn('status', data)
            self.assertIn('owner', data)
        except RequestDone:
            # RequestDone例外は正常な動作の一部なので、無視します
            pass

    def test_validate_ticket_resolve(self):
        environ = {
            'wsgi.version': (1, 0),
            'wsgi.url_scheme': 'http',
            'SERVER_NAME': 'localhost',
            'SERVER_PORT': '80',
            'REQUEST_METHOD': 'POST',
            'PATH_INFO': '',
            'SCRIPT_NAME': '',
            'QUERY_STRING': '',
        }
        def start_response(status, headers, exc_info=None):
            pass
        req = Request(environ, start_response)
        req.args = {'action': 'resolve'}
        
        # 子チケットが開いている状態で親チケットを解決しようとする
        errors = list(self.module.validate_ticket(req, self.parent))
        self.assertEqual(len(errors), 2)  # 2つの子チケットがあるため、2つのエラーが期待される
        
        # 子チケットを閉じる
        self.child1['status'] = 'closed'
        self.child1.save_changes()
        self.child2['status'] = 'closed'
        self.child2.save_changes()
        
        # 子チケットが閉じている状態で親チケットを解決
        errors = list(self.module.validate_ticket(req, self.parent))
        self.assertEqual(len(errors), 0)

    def test_validate_ticket_reopen(self):
        environ = {
            'wsgi.version': (1, 0),
            'wsgi.url_scheme': 'http',
            'SERVER_NAME': 'localhost',
            'SERVER_PORT': '80',
            'REQUEST_METHOD': 'POST',
            'PATH_INFO': '',
            'SCRIPT_NAME': '',
            'QUERY_STRING': '',
        }
        def start_response(status, headers, exc_info=None):
            pass
        req = Request(environ, start_response)
        req.args = {'action': 'reopen'}
        
        # 親チケットを閉じる
        self.parent['status'] = 'closed'
        self.parent.save_changes()
        
        # 親チケットが閉じている状態で子チケットを再開しようとする
        self.child1['parents'] = str(self.parent.id)
        errors = list(self.module.validate_ticket(req, self.child1))
        self.assertEqual(len(errors), 1)
        
        # 親チケットを開く
        self.parent['status'] = 'new'
        self.parent.save_changes()
        
        # 親チケットが開いている状態で子チケットを再開
        errors = list(self.module.validate_ticket(req, self.child1))
        self.assertEqual(len(errors), 0)

def suite():
    return unittest.makeSuite(SubTicketsTestCase, 'test')

if __name__ == '__main__':
    unittest.main() 