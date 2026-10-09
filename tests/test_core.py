"""Requested regression coverage, using synthetic isolated archives and local HTTP."""
from pathlib import Path
import json
import queue
import sys
import threading
import unittest
import uuid
import os
import time
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app_config import bootstrap, validate_ai, credential_id, Credentials
from assistant_bridge import AssistantRun, publish_result, SCHEMA
from calendar_plans import create_plan, get_plan, apply_plan, pending_plans, update_plan, dismiss_plan
from codex_connection import model_arguments, find_codex
from file_store import FileStore, parse_dates
from api_assistant import ModelClient, ArchiveTools, run_api, decode_result, connection_check

TASK = dict(day='2026-10-11', title='测试：阅读论文', at_time='09:30', priority=0, notes='这是测试数据')
FINAL = dict(reply='已起草，请确认。', document_title='', document_markdown='', source_ids=[], calendar_tasks=[TASK])

class StoreCase(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / 'work' / 'qa-v17' / uuid.uuid4().hex[:12]
        bootstrap(self.root)
        self.store = FileStore(self.root)

    def tearDown(self):
        self.store.close()

class Regression(StoreCase):
    def test_draft_is_passive_and_durable(self):
        identifier = create_plan(self.store, '安排测试', [TASK])
        self.assertEqual(self.store.tasks(), [])
        self.store.close()
        self.store = FileStore(self.root)
        self.assertEqual(get_plan(self.store, identifier)['tasks'], [TASK])
        self.assertEqual(len(pending_plans(self.store)), 1)

    def test_apply_once_and_duplicate_suppression(self):
        identifier = create_plan(self.store, '安排测试', [TASK, TASK])
        result = apply_plan(self.store, identifier, [TASK, TASK])
        self.assertEqual(len(result['created_ids']), 1)
        self.assertEqual(result['skipped'], 1)
        self.assertTrue(apply_plan(self.store, identifier, [TASK])['already_applied'])
        self.assertEqual(len(self.store.tasks()), 1)
        self.assertEqual(self.store.tasks()[0]['done'], 0)

    def test_existing_task_is_preserved(self):
        original = self.store.save_task(dict(TASK, done=1))
        identifier = create_plan(self.store, '安排测试', [dict(TASK, notes='不要覆盖')])
        result = apply_plan(self.store, identifier, [dict(TASK, notes='不要覆盖')])
        self.assertEqual(result['skipped'], 1)
        self.assertEqual(original, self.store.task(original['id']))

    def test_invalid_draft_and_batch_do_not_partially_write(self):
        invalid = [dict(TASK, day='2026-02-30'), dict(TASK, at_time='25:00'), dict(TASK, at_time=None), dict(TASK, title=' '), dict(TASK, done=1)]
        for task in invalid:
            with self.subTest(task=task), self.assertRaises(ValueError):
                create_plan(self.store, '测试', [task])
        with self.assertRaises(ValueError):
            create_plan(self.store, '测试', [TASK] * 31)
        identifier = create_plan(self.store, '测试', [TASK])
        with self.assertRaises(ValueError):
            apply_plan(self.store, identifier, [TASK, invalid[0]])
        self.assertEqual(self.store.tasks(), [])
        self.assertEqual(get_plan(self.store, identifier)['status'], 'pending')

    def test_transaction_rolls_back_on_second_insert_failure(self):
        identifier = create_plan(self.store, '测试', [TASK])
        self.store.db.execute("CREATE TRIGGER abort_bad BEFORE INSERT ON planner_tasks WHEN NEW.title='fail' BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
        self.store.db.commit()
        with self.assertRaises(Exception):
            apply_plan(self.store, identifier, [TASK, dict(TASK, title='fail')])
        self.assertEqual(self.store.tasks(), [])
        self.assertEqual(get_plan(self.store, identifier)['status'], 'pending')

    def test_two_confirmations_create_one_batch(self):
        identifier = create_plan(self.store, '测试', [TASK])
        barrier, results, errors = threading.Barrier(2), [], []
        def worker():
            store = FileStore(self.root)
            try:
                barrier.wait(timeout=5)
                results.append(apply_plan(store, identifier, [TASK]))
            except Exception as error:
                errors.append(str(error))
            finally:
                store.close()
        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=10)
        self.assertEqual(errors, [])
        self.assertEqual(len(self.store.tasks()), 1)
        self.assertEqual(sum(x['already_applied'] for x in results), 1)

    def test_draft_edit_and_dismiss(self):
        identifier = create_plan(self.store, '测试', [TASK])
        edited = dict(TASK, day='2026-10-12', title='编辑后的测试')
        update_plan(self.store, identifier, [edited])
        self.assertEqual(get_plan(self.store, identifier)['tasks'], [edited])
        dismiss_plan(self.store, identifier)
        self.assertEqual(pending_plans(self.store), [])
        with self.assertRaises(ValueError): apply_plan(self.store, identifier, [edited])

    def test_model_cannot_write_without_opt_in(self):
        with self.assertRaises(ValueError):
            publish_result(self.store, dict(FINAL), TASK['day'], set(), queue.Queue())
        self.assertEqual(self.store.tasks(), [])
        self.assertEqual(pending_plans(self.store), [])

    def test_model_only_publishes_reviewable_plan(self):
        events = queue.Queue()
        publish_result(self.store, dict(FINAL), TASK['day'], set(), events, True, '测试')
        kind, result = events.get_nowait()
        self.assertEqual(kind, 'done')
        self.assertTrue(result['plan_id'])
        self.assertEqual(self.store.tasks(), [])

    def test_sources_checked_before_draft_creation(self):
        with self.assertRaises(ValueError):
            publish_result(self.store, dict(FINAL, source_ids=['missing']), TASK['day'], set(), queue.Queue(), True, '测试')
        self.assertEqual(pending_plans(self.store), [])

    def test_model_sees_existing_task_time(self):
        self.store.save_task(TASK)
        record = next(self.store.records())
        self.assertEqual(record.get('at_time'), '09:30')
        self.assertEqual(record.get('priority'), 0)

    def test_attachment_multidate_and_fuzzy_search(self):
        source = self.root / 'example.txt'
        source.write_text('测试用履历：完成实验报告。', encoding='utf-8')
        spans = parse_dates('2026-10-10', '2026-10-12', '2026-11-01')
        self.store.import_file(source, {'title': '个人资料测试'}, spans)
        self.assertEqual(len(self.store.files_for_day('2026-10-11')), 1)
        self.assertEqual(len(self.store.files_for_day('2026-11-01')), 1)
        self.assertTrue(self.store.search('之前的简历'))
        archive = ArchiveTools(self.store)
        result = archive.call('list_records', {'start': '2026-11-01', 'end': '2026-11-01'})
        self.assertEqual(result['total'], 1)

    def test_backup_contains_drafts_but_no_credentials(self):
        create_plan(self.store, '测试', [TASK])
        (self.root / 'credentials.dpapi').write_text('synthetic-placeholder', encoding='utf-8')
        path = self.root / 'backup.zip'
        self.store.backup(path)
        with zipfile.ZipFile(path) as z:
            self.assertIn('vault/diary.sqlite3', z.namelist())
            self.assertNotIn('credentials.dpapi', z.namelist())

    def test_credentials_encrypted_and_isolated(self):
        one = validate_ai(dict(protocol='openai', provider='测试', base_url='https://example.test/v1', model='test'))
        two = dict(one, base_url='https://different.test/v1')
        key = 'test-only-placeholder-key'
        credentials = Credentials(self.root)
        credentials.set(one, key)
        self.assertEqual(credentials.get(one), key)
        self.assertEqual(credentials.get(two), '')
        self.assertNotIn(key.encode(), credentials.path.read_bytes())
        self.assertEqual(credential_id(one), credential_id(dict(one, protocol='responses')))

    def test_bad_config_and_url(self):
        for url in ['https://user:pass@example.test/v1', 'http://example.test/v1', 'https://example.test/{WorkspaceId}', 'https://example.test/v1?key=123']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_ai(dict(protocol='openai', base_url=url, model='test'))
        config = validate_ai(dict(provider='OpenAI', protocol='openai', base_url='https://api.openai.com/v1/responses', model='gpt-6-luna'))
        self.assertEqual(config['protocol'], 'responses')

    def test_exact_codex_model_arguments(self):
        args = model_arguments(dict(model='gpt-6.1-sol', reasoning_effort='high'))
        self.assertEqual(args, ['--model', 'gpt-6.1-sol', '-c', 'model_reasoning_effort="high"'])

    def test_plain_answer_does_not_become_calendar_action(self):
        result = decode_result('明天可以读论文。')
        self.assertEqual(result.get('calendar_tasks', []), [])
        with self.assertRaises(ValueError): decode_result('["unexpected"]')

    def test_cancel_prevents_network(self):
        event = threading.Event(); event.set()
        client = ModelClient(dict(protocol='openai', base_url='http://localhost:1/v1', model='test'), '', event)
        with self.assertRaises(InterruptedError): client.models()

    def test_desktop_launch_cwd_cannot_shadow_cli(self):
        binary=self.root/'local/OpenAI/Codex/bin/build/codex.exe'
        binary.parent.mkdir(parents=True);binary.write_bytes(b'fixture')
        with patch.dict(os.environ, {'LOCALAPPDATA':str(self.root/'local')}), patch('codex_connection._is_cli',return_value=True), patch('shutil.which',return_value='.\\codex.exe'):
            self.assertEqual(find_codex(),str(binary.resolve()))

    def test_cancel_while_waiting_for_headers_is_prompt(self):
        client=ModelClient(dict(protocol='openai',base_url='http://localhost:1/v1',model='test'),'')
        errors=[]
        def delayed(*args):
            time.sleep(1.5)
            return {}
        def run():
            try: client.request('/models')
            except InterruptedError: errors.append('cancelled')
        with patch.object(client,'_request',side_effect=delayed):
            thread=threading.Thread(target=run);thread.start();time.sleep(.1)
            started=time.monotonic();client.cancel();thread.join(timeout=.6)
            self.assertFalse(thread.is_alive())
            self.assertLess(time.monotonic()-started,.6)
            self.assertEqual(errors,['cancelled'])

    def test_empty_model_response_is_not_success(self):
        for protocol,response in [('openai',{'choices':[{'message':{'content':''}}]}),('responses',{'status':'completed','output':[{'type':'message','content':[]}]}),('anthropic',{'stop_reason':'end_turn','content':[]})]:
            with self.subTest(protocol=protocol),patch.object(ModelClient,'complete',return_value=response),self.assertRaises(ValueError):
                connection_check(dict(protocol=protocol,base_url='http://localhost:1/v1',model='test'),'')


class HTTPProtocols(StoreCase):
    # Synthetic loopback server exercises actual serialization and transport.
    def test_api_tools_to_calendar_draft_all_protocols(self):
        for protocol in ['openai', 'responses', 'anthropic']:
            with self.subTest(protocol=protocol):
                requests = []
                final = dict(FINAL)
                class Handler(BaseHTTPRequestHandler):
                    def log_message(self, *args): pass
                    def do_POST(h):
                        body = json.loads(h.rfile.read(int(h.headers['Content-Length'])))
                        requests.append((h.path, body))
                        if len(requests) == 1:
                            if protocol == 'responses':
                                data = {'status':'completed', 'output':[{'type':'reasoning','id':'r1','encrypted_content':'test-reasoning'}, {'type':'function_call','call_id':'c1','name':'list_records','arguments':'{}'}]}
                            elif protocol == 'anthropic':
                                data = {'stop_reason':'tool_use', 'content':[{'type':'tool_use','id':'c1','name':'list_records','input':{}}]}
                            else:
                                data = {'choices':[{'finish_reason':'tool_calls','message':{'role':'assistant','content':None,'reasoning_content':'test-reasoning','tool_calls':[{'id':'c1','type':'function','function':{'name':'list_records','arguments':'{}'}}]}}]}
                        elif protocol == 'responses':
                            data = {'status':'completed','output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':json.dumps(final)}]}]}
                        elif protocol == 'anthropic':
                            data = {'stop_reason':'end_turn','content':[{'type':'text','text':json.dumps(final)}]}
                        else:
                            data = {'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(final)}}]}
                        payload = json.dumps(data).encode()
                        h.send_response(200); h.send_header('Content-Length',str(len(payload))); h.end_headers(); h.wfile.write(payload)
                server = ThreadingHTTPServer(('127.0.0.1',0), Handler)
                thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
                try:
                    config = validate_ai(dict(protocol=protocol, provider='测试', base_url=f'http://127.0.0.1:{server.server_port}/v1', model='test-model'))
                    self.store.set_setting('ai_config', json.dumps(config))
                    events = queue.Queue()
                    owner = AssistantRun(self.root, '测试安排', TASK['day'], events, True)
                    run_api(owner)
                    output = list(events.queue)
                    self.assertEqual(output[-1][0], 'done', output)
                    self.assertTrue(output[-1][1]['plan_id'])
                    self.assertEqual(len(requests), 2)
                    self.assertEqual(self.store.tasks(), [])
                    if protocol == 'responses':
                        self.assertEqual(requests[0][0], '/v1/responses')
                        self.assertFalse(requests[0][1]['store'])
                        self.assertTrue(any(x.get('encrypted_content')=='test-reasoning' for x in requests[1][1]['input']))
                    elif protocol == 'anthropic':
                        self.assertEqual(requests[0][0], '/v1/messages')
                    else:
                        self.assertEqual(requests[0][0], '/v1/chat/completions')
                        self.assertTrue(any(x.get('reasoning_content')=='test-reasoning' for x in requests[1][1]['messages']))
                finally:
                    server.shutdown(); server.server_close(); thread.join(timeout=2)

if __name__ == '__main__':
    unittest.main(verbosity=2)
