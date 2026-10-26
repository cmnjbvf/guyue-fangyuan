import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import digest_batch as batch


class DigestBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'input'
        self.source.mkdir()
        self.output = self.root / 'chosen-domain'
        self.run = self.output / '.digest-runs' / 'case-1'

    def call(self, *args, code=0):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            result = batch.main([str(a) for a in args])
        data = json.loads(stream.getvalue())
        self.assertEqual(result, code, data)
        return data

    def prepare(self, text='甲乙\n  丙丁\r\n\n尾巴  ', limit=5, extra=()):
        self.file = self.source / 'source.txt'
        self.file.write_bytes(text.encode('utf-8'))
        return self.call('prepare', '--source', self.source, '--output-root', self.output,
                         '--batch-id', 'case-1', '--goal', '法律研究的跨领域目标',
                         '--domain', 'law', '--chunk-chars', limit, *extra)

    def chunks(self):
        return [json.loads(line) for line in (self.run / 'chunks.jsonl').read_text(encoding='utf-8').splitlines()]

    def receipt(self, chunk, disposition='extracted'):
        content = self.call('read', '--run', self.run, '--chunk-id', chunk['chunk_id'])['chunk']['text']
        return {'chunk_id': chunk['chunk_id'], 'disposition': disposition, 'reason': '人工逐段处理',
                'claims': [{'id': 'claim-1', 'statement': '人工语义提取的结论', 'kind': 'fact',
                            'evidence': [{'start': chunk['start'], 'end': chunk['end'], 'quote': content}],
                            'conditions': [], 'exceptions': [], 'uncertainties': []}] if disposition == 'extracted' else []}

    def record(self, data, code=0):
        path = self.root / 'receipt.json'
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        return self.call('record', '--run', self.run, '--receipt', path, code=code)

    def test_all_characters_boundaries_and_separate_context(self):
        text = '甲乙\n  丙丁\r\n\n尾巴  '
        self.prepare(text)
        chunks = self.chunks()
        cursor = 0
        pieces = []
        for chunk in chunks:
            self.assertEqual(chunk['start'], cursor)
            self.assertLessEqual(chunk['end'] - cursor, 5)
            read = self.call('read', '--run', self.run, '--chunk-id', chunk['chunk_id'])
            pieces.append(read['chunk']['text'])
            self.assertEqual(read['context_before']['end'], chunk['start'])
            self.assertEqual(read['context_after']['start'], chunk['end'])
            cursor = chunk['end']
        self.assertEqual(''.join(pieces), text)
        self.assertEqual(cursor, len(text))
        self.assertEqual(chunks[0]['end'], 3)

    def test_cross_domain_target_and_restart_resume(self):
        self.prepare('abcdefghi', 3)
        self.assertFalse((self.root / 'ai').exists())
        manifest = json.loads((self.run / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['domain'], 'law')
        chunks = self.chunks()
        self.record(self.receipt(chunks[0]))
        audit = self.call('audit', '--run', self.run, code=2)
        self.assertEqual(audit['processed_chunks'], 1)
        # A fresh process resumes exclusively from saved state.
        proc = subprocess.run([sys.executable, '-B', str(Path(batch.__file__).resolve()),
                               'read', '--run', str(self.run), '--chunk-id', chunks[1]['chunk_id']],
                              capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)['chunk']['text'], 'def')
        for chunk in chunks[1:]:
            self.record(self.receipt(chunk))
        audit = self.call('audit', '--run', self.run)
        self.assertTrue(audit['receipts_complete'])
        self.assertTrue(audit['read_coverage_complete'])
        self.assertEqual(audit['semantic_quality'], 'not_machine_verified')
        self.assertEqual(audit['coverage']['receipted_characters'], 9)

    def test_fake_quote_cross_boundary_and_missing_reason_rejected(self):
        self.prepare('abcdef', 3)
        chunk = self.chunks()[0]
        data = self.receipt(chunk)
        data['claims'][0]['evidence'][0]['quote'] = 'fake'
        self.assertIn('quote', self.record(data, code=1)['error'])
        data = self.receipt(chunk)
        data['claims'][0]['evidence'][0].update(end=4, quote='abcd')
        self.assertIn('span', self.record(data, code=1)['error'])
        data = self.receipt(chunk, 'no_reusable_knowledge')
        data['reason'] = ' '
        self.assertIn('reason', self.record(data, code=1)['error'])
        data = self.receipt(chunk)
        data['claims'] = []
        self.record(data, code=1)

    def test_original_saved_and_chunk_drift_rejected(self):
        self.prepare()
        chunk_id = self.chunks()[0]['chunk_id']
        original = self.file.read_bytes()
        self.file.write_bytes(b'changed')
        self.assertIn('Original source', self.call('read', '--run', self.run, '--chunk-id', chunk_id, code=1)['error'])
        self.file.write_bytes(original)
        saved_path = next((self.run / 'sources').iterdir())
        saved = saved_path.read_bytes()
        saved_path.write_bytes(b'changed')
        self.assertIn('Saved text', self.call('audit', '--run', self.run, code=1)['error'])
        saved_path.write_bytes(saved)
        with (self.run / 'chunks.jsonl').open('ab') as handle:
            handle.write(b'\n')
        self.assertIn('Chunk manifest', self.call('audit', '--run', self.run, code=1)['error'])

    def test_unsupported_and_empty_explicit(self):
        (self.source / 'scan.pdf').write_bytes(b'%PDF-pretend')
        self.prepare('')
        audit = self.call('audit', '--run', self.run, code=2)
        self.assertEqual(len(audit['needs_extraction']), 1)
        self.assertEqual(len(audit['empty_sources']), 1)
        self.assertFalse(audit['read_coverage_complete'])
        self.assertEqual(audit['total_chunks'], 0)

    def test_empty_only_reports_zero_chunks(self):
        self.prepare('')
        audit = self.call('audit', '--run', self.run)
        self.assertEqual(audit['total_chunks'], 0)
        self.assertEqual(len(audit['empty_sources']), 1)

    def test_run_exists_and_bad_paths(self):
        self.prepare()
        self.call('prepare', '--source', self.source, '--output-root', self.output,
                  '--batch-id', 'case-1', '--goal', 'g', '--domain', 'd', code=1)
        for bad in ('../escape', 'bad/name', 'bad\\name', '.'):
            self.call('prepare', '--source', self.source, '--output-root', self.output,
                      '--batch-id', bad, '--goal', 'g', '--domain', 'd', code=1)
        self.call('audit', '--run', self.run / '..' / 'case-1', code=1)
        self.call('audit', '--run', 'relative', code=1)
        data = self.receipt(self.chunks()[0])
        data['chunk_id'] = '../outside'
        self.record(data, code=1)

    def test_cli_errors_are_json(self):
        self.assertIn('CLI arguments', self.call('prepare', code=1)['error'])

    def test_nonrecursive_is_default(self):
        nested = self.source / 'nested'
        nested.mkdir()
        (nested / 'ignored.txt').write_text('ignored', encoding='utf-8')
        self.prepare('root')
        audit = self.call('audit', '--run', self.run, code=2)
        self.assertEqual(audit['total_sources'], 1)

    def test_idempotent_receipt_and_changes_refused(self):
        self.prepare('abc', 3)
        data = self.receipt(self.chunks()[0])
        self.assertEqual(self.record(data)['status'], 'recorded')
        self.assertEqual(self.record(data)['status'], 'already_recorded')
        data['reason'] = 'different'
        self.assertIn('different', self.record(data, code=1)['error'])

    def test_duplicate_references(self):
        self.prepare('abcdefghi', 3)
        chunks = self.chunks()
        data = self.receipt(chunks[1], 'duplicate_no_increment')
        self.record(data, code=1)
        data['duplicate_of'] = {'type': 'chunk_receipt', 'chunk_id': chunks[0]['chunk_id']}
        self.record(data, code=1)
        self.record(self.receipt(chunks[0]))
        self.record(data)
        data2 = self.receipt(chunks[2], 'duplicate_no_increment')
        data2['duplicate_of'] = {'type': 'existing_knowledge', 'id': 'K-1'}
        self.record(data2, code=1)
        data2['duplicate_of']['locator'] = 'knowledge-base://collection/K-1'
        self.record(data2)
        self.call('audit', '--run', self.run)

    def test_needs_review_is_partial(self):
        self.prepare('abc')
        self.record(self.receipt(self.chunks()[0], 'needs_review'))
        audit = self.call('audit', '--run', self.run, code=2)
        self.assertTrue(audit['read_coverage_complete'])
        self.assertFalse(audit['receipts_complete'])

    def test_authorized_extraction_hashes_and_locator(self):
        pdf = self.source / 'original.pdf'
        pdf.write_bytes(b'%PDF example')
        extracted = self.root / 'extracted.txt'
        extracted.write_bytes('已授权提取正文\r\n'.encode('utf-8'))
        config = self.root / 'extractions.json'
        config.write_text(json.dumps([{'source': str(pdf), 'text_file': str(extracted),
                                      'method': 'authorized-tool-v1'}]), encoding='utf-8-sig')
        self.prepare('', extra=('--extractions', config))
        manifest = json.loads((self.run / 'manifest.json').read_text(encoding='utf-8'))
        source = next(s for s in manifest['sources'] if s['path'] == str(pdf))
        self.assertEqual(source['method'], 'authorized-tool-v1')
        self.assertEqual(source['locator_type'], 'normalized_char_offset')
        self.assertIn('extraction_sha256', source)
        extracted.write_bytes(b'drift')
        self.assertIn('Extraction', self.call('audit', '--run', self.run, code=1)['error'])

    def test_recursive_opt_in_and_output_exclusion(self):
        nested = self.source / 'nested'
        nested.mkdir()
        (nested / 'nested.txt').write_text('nested', encoding='utf-8')
        git = self.source / '.git'
        git.mkdir()
        (git / 'secret.txt').write_text('git', encoding='utf-8')
        self.output = self.source / 'output'
        self.output.mkdir()
        (self.output / 'old.txt').write_text('old', encoding='utf-8')
        self.run = self.output / '.digest-runs' / 'case-1'
        self.prepare('root', extra=('--recursive',))
        manifest = json.loads((self.run / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(len(manifest['sources']), 2)

    def test_symlink_escape_rejected_when_supported(self):
        link = self.root / 'link'
        try:
            link.symlink_to(self.source, target_is_directory=True)
        except OSError:
            self.skipTest('Host does not permit creating symlinks')
        self.call('prepare', '--source', self.source, '--output-root', link / 'output',
                  '--batch-id', 'case-1', '--goal', 'g', '--domain', 'd', code=1)

    def test_read_errors_preserve_other_sources_and_remain_partial(self):
        good = self.source / 'good.txt'
        good.write_text('readable', encoding='utf-8')
        bad = self.source / 'bad.txt'
        bad.write_text('not accessible', encoding='utf-8')
        pdf = self.source / 'original.pdf'
        pdf.write_bytes(b'%PDF')
        extracted = self.root / 'extracted.txt'
        extracted.write_text('extracted', encoding='utf-8')
        mapping = self.root / 'mapping.json'
        mapping.write_text(json.dumps([{'source': str(pdf), 'text_file': str(extracted),
                                       'method': 'authorized-tool'}]), encoding='utf-8-sig')
        original_read = Path.read_bytes

        def intermittent_read(path):
            if path in (bad, extracted):
                raise PermissionError('mock permission denied')
            return original_read(path)

        with patch.object(Path, 'read_bytes', intermittent_read):
            result = self.call('prepare', '--source', self.source, '--output-root', self.output,
                               '--batch-id', 'case-1', '--goal', 'g', '--domain', 'd',
                               '--extractions', mapping, code=2)
            self.assertEqual(result['sources'], 3)
            self.assertEqual(len(result['read_errors']), 2)
            audit = self.call('audit', '--run', self.run, code=2)
            self.assertEqual({s['error_stage'] for s in audit['read_errors']}, {'original', 'extraction'})
            self.assertTrue(all(s['reason'] == 'mock permission denied' for s in audit['read_errors']))
            self.assertFalse(audit['read_coverage_complete'])
            chunks = self.chunks()
            self.assertEqual(len(chunks), 1)
            self.record(self.receipt(chunks[0]))
        # The failure remains explicit even when the transient condition clears.
        audit = self.call('audit', '--run', self.run, code=2)
        self.assertEqual(audit['processed_chunks'], 1)
        self.assertEqual(audit['unprocessed_chunks'], [])
        self.assertEqual(len(audit['read_errors']), 2)
        self.assertFalse(audit['receipts_complete'])

    def test_multiple_source_chunk_grouping(self):
        expected = {}
        for name, text in [('a.txt', 'aaa\n尾  '), ('b.md', '\r\nbbbb\n 结尾'), ('c.csv', 'a,b\n1,2\n')]:
            path = self.source / name
            path.write_bytes(text.encode('utf-8'))
            expected[str(path)] = text
        self.call('prepare', '--source', self.source, '--output-root', self.output,
                  '--batch-id', 'case-1', '--goal', 'g', '--domain', 'd', '--chunk-chars', 3)
        _, manifest, chunks, texts = batch.verify(self.run)
        self.assertEqual(len(texts), 3)
        for source in manifest['sources']:
            parts = [self.call('read', '--run', self.run, '--chunk-id', c['chunk_id'])['chunk']['text']
                     for c in chunks if c['source_id'] == source['source_id']]
            self.assertEqual(''.join(parts), expected[source['path']])

    def test_json_bom_accepted_and_body_bom_preserved(self):
        self.prepare('\ufeff正文', limit=10)
        chunk = self.chunks()[0]
        data = self.receipt(chunk)
        self.assertEqual(data['claims'][0]['evidence'][0]['quote'], '\ufeff正文')
        path = self.root / 'bom-receipt.json'
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8-sig')
        self.call('record', '--run', self.run, '--receipt', path)
        self.call('audit', '--run', self.run)

    def test_review_revision_requires_current_hash_and_preserves_history(self):
        self.prepare('abc')
        chunk = self.chunks()[0]
        self.record(self.receipt(chunk, 'needs_review'))
        stored = self.run / 'receipts' / (chunk['chunk_id'] + '.json')
        old_bytes = stored.read_bytes()
        old_sha = batch.sha(old_bytes)
        revised = self.receipt(chunk)
        request = self.root / 'revised.json'
        request.write_text(json.dumps(revised, ensure_ascii=False), encoding='utf-8-sig')
        conflict = self.call('record', '--run', self.run, '--receipt', request,
                             '--replace-receipt-sha', '0' * 64, code=1)
        self.assertIn('hash conflict', conflict['error'])
        self.assertEqual(stored.read_bytes(), old_bytes)
        self.assertFalse((self.run / 'receipt-history').exists())
        result = self.call('record', '--run', self.run, '--receipt', request,
                           '--replace-receipt-sha', old_sha)
        self.assertEqual(result['status'], 'revised')
        history = self.run / 'receipt-history' / (chunk['chunk_id'] + '-' + old_sha + '.json')
        self.assertEqual(history.read_bytes(), old_bytes)
        new_bytes = stored.read_bytes()
        self.assertNotEqual(new_bytes, old_bytes)
        self.call('audit', '--run', self.run)
        # A stale expected hash fails even if the submitted content is identical.
        self.call('record', '--run', self.run, '--receipt', request,
                  '--replace-receipt-sha', old_sha, code=1)
        self.assertEqual(stored.read_bytes(), new_bytes)
        self.assertEqual(list((self.run / 'receipt-history').iterdir()), [history])

    def test_cli_utf8_bytes_with_utf8_mode_disabled(self):
        source = self.source / '中文资料.txt'
        source.write_bytes('中文正文与空白  \n'.encode('utf-8'))
        output = self.root / '中文输出目录'
        environment = os.environ.copy()
        environment.pop('PYTHONUTF8', None)
        environment.pop('PYTHONIOENCODING', None)
        script = str(Path(batch.__file__).resolve())
        prefix = [sys.executable, '-B', '-X', 'utf8=0', script]
        prepared = subprocess.run(prefix + ['prepare', '--source', str(source),
                                  '--output-root', str(output), '--batch-id', 'utf8-test',
                                  '--goal', '跨领域中文目标', '--domain', '中文研究'],
                                  capture_output=True, env=environment)
        self.assertEqual(prepared.returncode, 0, prepared.stderr.decode('utf-8'))
        result = json.loads(prepared.stdout.decode('utf-8'))
        run = output / '.digest-runs' / 'utf8-test'
        self.assertEqual(result['run'], str(run))
        manifest = json.loads((run / 'manifest.json').read_bytes().decode('utf-8'))
        self.assertEqual(manifest['goal'], '跨领域中文目标')
        self.assertEqual(manifest['sources'][0]['path'], str(source))
        chunk_id = json.loads((run / 'chunks.jsonl').read_text(encoding='utf-8').splitlines()[0])['chunk_id']
        read = subprocess.run(prefix + ['read', '--run', str(run), '--chunk-id', chunk_id],
                              capture_output=True, env=environment)
        self.assertEqual(read.returncode, 0, read.stderr.decode('utf-8'))
        self.assertEqual(json.loads(read.stdout.decode('utf-8'))['chunk']['text'], '中文正文与空白  \n')


if __name__ == '__main__':
    unittest.main()
