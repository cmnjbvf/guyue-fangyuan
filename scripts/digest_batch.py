"""Deterministic source preparation and evidence receipts; no semantic extraction."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

TEXT_EXTENSIONS = {'.txt', '.md', '.markdown', '.json', '.jsonl', '.csv', '.tsv',
                   '.log', '.yaml', '.yml', '.xml', '.html', '.htm'}
SAFE_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$')


def fail(message):
    raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


def absolute(value):
    path = Path(value)
    if not path.is_absolute() or '..' in path.parts:
        fail('Path must be absolute and contain no parent traversal: ' + str(path))
    for candidate in (path, *path.parents):
        if candidate.is_symlink() or (hasattr(candidate, 'is_junction') and candidate.is_junction()):
            fail('Symlink/junction path is not allowed: ' + str(candidate))
    return path


def child(run, relative):
    path = absolute(run / relative)
    if not path.is_relative_to(run):
        fail('Path escapes run directory')
    return path


def atomic(path, data):
    absolute(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def json_file(path):
    return json.loads(absolute(path).read_bytes().decode('utf-8-sig'))


def spans(text, limit):
    start = 0
    while start < len(text):
        end = min(start + limit, len(text))
        if end < len(text):
            newline = text.rfind('\n', start, end)
            if newline >= start:
                end = newline + 1
        yield start, end
        start = end


def prepare(args):
    if not SAFE_ID.fullmatch(args.batch_id) or args.chunk_chars < 1:
        fail('Invalid batch-id or chunk-chars (must be positive)')
    if not args.goal.strip() or not args.domain.strip():
        fail('Goal and domain must be nonempty')
    output = absolute(args.output_root)
    run = absolute(output / '.digest-runs' / args.batch_id)
    if run.exists():
        fail('Run already exists; refusing overwrite')
    extractions = {}
    if args.extractions:
        entries = json_file(args.extractions)
        if not isinstance(entries, list):
            fail('Extractions must be a JSON array')
        for entry in entries:
            source = str(absolute(entry['source']))
            text_path = absolute(entry['text_file'])
            if not isinstance(entry.get('method'), str) or not entry['method'].strip():
                fail('Extraction method is required')
            if source in extractions:
                fail('Duplicate extraction source')
            extractions[source] = (text_path, entry['method'])
    paths = set()
    skipped = []
    for value in args.source:
        root = absolute(value)
        if not root.exists():
            fail('Source does not exist: ' + str(root))
        if root.is_file():
            if root.is_relative_to(output):
                fail('Source file conflicts with output root')
            paths.add(root)
        elif root.is_dir():
            if root == output or root.is_relative_to(output):
                fail('Source directory conflicts with output root')
            for base, dirs, names in os.walk(root, followlinks=False):
                dirs[:] = sorted(d for d in dirs if d != '.git' and
                                  not (Path(base) / d).is_symlink() and
                                  not (hasattr(Path(base) / d, 'is_junction') and (Path(base) / d).is_junction()) and
                                  not (Path(base) / d).is_relative_to(output))
                for name in sorted(names):
                    path = Path(base) / name
                    if path.is_symlink():
                        skipped.append({'path': str(path), 'reason': 'symlink'})
                    elif not path.is_relative_to(output):
                        paths.add(absolute(path))
                if not args.recursive:
                    break
        else:
            fail('Source must be a regular file or directory')
    manifest = {'schema_version': 1, 'batch_id': args.batch_id, 'goal': args.goal,
                'domain': args.domain, 'profile': args.profile, 'chunk_chars': args.chunk_chars,
                'sources': [], 'skipped': skipped,
                'locator_note': 'Offsets refer to saved normalized text, never original PDF page numbers.',
                'semantic_quality': 'not_machine_verified'}
    chunks = []
    saved = []
    for path in sorted(paths, key=str):
        source_id = 's-' + sha(str(path).encode('utf-8'))[:20]
        source = {'source_id': source_id, 'path': str(path),
                  'locator_type': 'normalized_char_offset'}
        try:
            raw = path.read_bytes()
        except OSError as error:
            source.update(status='read_error', reason=str(error), error_stage='original')
            manifest['sources'].append(source)
            continue
        source['original_sha256'] = sha(raw)
        if str(path) in extractions:
            text_path, method = extractions[str(path)]
            if text_path.is_relative_to(output):
                fail('Extraction file conflicts with output root')
            source.update(extraction_path=str(text_path), method=method)
            try:
                text_bytes = text_path.read_bytes()
            except OSError as error:
                source.update(status='read_error', reason=str(error), error_stage='extraction')
                manifest['sources'].append(source)
                continue
            source['extraction_sha256'] = sha(text_bytes)
        elif path.suffix.lower() in TEXT_EXTENSIONS:
            text_bytes = raw
            source['method'] = 'utf8_plain_text_verbatim'
        else:
            source['status'] = 'needs_extraction'
            manifest['sources'].append(source)
            continue
        try:
            text = text_bytes.decode('utf-8')
        except UnicodeDecodeError:
            source['status'] = 'needs_extraction'
            source['reason'] = 'Text is not valid UTF-8'
            manifest['sources'].append(source)
            continue
        relative = 'sources/' + source_id + '.txt'
        source.update(status='empty' if not text else 'ready', saved_text=relative,
                      saved_sha256=sha(text_bytes), characters=len(text))
        saved.append((relative, text_bytes))
        for start, end in spans(text, args.chunk_chars):
            segment = text[start:end]
            chunks.append({'chunk_id': source_id + '-' + str(start) + '-' + str(end),
                           'source_id': source_id, 'start': start, 'end': end,
                           'text_sha256': sha(segment.encode('utf-8'))})
        manifest['sources'].append(source)
    chunk_bytes = b''.join((json.dumps(c, ensure_ascii=False, sort_keys=True) + '\n').encode('utf-8') for c in chunks)
    manifest['chunks_sha256'] = sha(chunk_bytes)
    # Exclusive directory creation makes an existing or interrupted run non-overwritable.
    run.mkdir(parents=True, exist_ok=False)
    for relative, data in saved:
        atomic(child(run, relative), data)
    atomic(child(run, 'chunks.jsonl'), chunk_bytes)
    atomic(child(run, 'manifest.json'), encoded(manifest))
    verify(run)
    read_errors = [s['source_id'] for s in manifest['sources'] if s['status'] == 'read_error']
    return {'run': str(run), 'sources': len(manifest['sources']), 'chunks': len(chunks),
            'status': 'partial' if read_errors else 'prepared', 'read_errors': read_errors,
            'semantic_quality': 'not_machine_verified'}


def verify(run):
    run = absolute(run)
    manifest = json_file(child(run, 'manifest.json'))
    chunk_bytes = child(run, 'chunks.jsonl').read_bytes()
    if sha(chunk_bytes) != manifest['chunks_sha256']:
        fail('Chunk manifest hash drift')
    chunks = [json.loads(line) for line in chunk_bytes.decode('utf-8').splitlines()]
    chunks_by_source = {}
    for chunk in chunks:
        chunks_by_source.setdefault(chunk['source_id'], []).append(chunk)
    texts = {}
    for source in manifest['sources']:
        path = absolute(source['path'])
        # A failed read establishes no hash; its explicit pending status remains
        # auditable without blocking access to successfully prepared sources.
        if 'original_sha256' in source and sha(path.read_bytes()) != source['original_sha256']:
            fail('Original source hash drift: ' + str(path))
        if 'extraction_sha256' in source:
            if sha(absolute(source['extraction_path']).read_bytes()) != source['extraction_sha256']:
                fail('Extraction text hash drift')
        if 'saved_text' in source:
            data = child(run, source['saved_text']).read_bytes()
            if sha(data) != source['saved_sha256']:
                fail('Saved text hash drift')
            text = data.decode('utf-8')
            texts[source['source_id']] = text
            cursor = 0
            for chunk in chunks_by_source.get(source['source_id'], []):
                if chunk['start'] != cursor or not cursor < chunk['end'] <= len(text):
                    fail('Chunk span gap/overlap or invalid boundary')
                if sha(text[cursor:chunk['end']].encode('utf-8')) != chunk['text_sha256']:
                    fail('Chunk text hash drift')
                cursor = chunk['end']
            if cursor != len(text):
                fail('Incomplete source span coverage')
    if len({c['chunk_id'] for c in chunks}) != len(chunks) or any(c['source_id'] not in texts for c in chunks):
        fail('Unknown source or duplicate chunk ID')
    return run, manifest, chunks, texts


def validate_receipt(receipt, chunks, texts, prior):
    chunk_id = receipt.get('chunk_id')
    if not isinstance(chunk_id, str) or not SAFE_ID.fullmatch(chunk_id):
        fail('Invalid chunk ID')
    chunk = next((c for c in chunks if c['chunk_id'] == chunk_id), None)
    if chunk is None:
        fail('Unknown chunk ID')
    disposition = receipt.get('disposition')
    if disposition not in {'extracted', 'duplicate_no_increment', 'no_reusable_knowledge', 'needs_review'}:
        fail('Invalid disposition')
    if not isinstance(receipt.get('reason'), str) or not receipt['reason'].strip():
        fail('A nonempty reason is required')
    claims = receipt.get('claims')
    if not isinstance(claims, list) or (disposition == 'extracted' and not claims):
        fail('Extracted receipt requires claims; claims must be an array')
    ids = set()
    for claim in claims:
        if not isinstance(claim.get('id'), str) or not claim['id'].strip() or claim['id'] in ids:
            fail('Claim IDs must be nonempty and unique within receipt')
        ids.add(claim['id'])
        if not isinstance(claim.get('statement'), str) or not claim['statement'].strip():
            fail('Claim statement is required')
        if claim.get('kind') not in {'fact', 'experience', 'inference', 'preference', 'unknown'}:
            fail('Invalid claim kind')
        for field in ('conditions', 'exceptions', 'uncertainties'):
            if not isinstance(claim.get(field), list) or not all(isinstance(v, str) for v in claim[field]):
                fail('Claim ' + field + ' must be an array of strings')
        evidence = claim.get('evidence')
        if not isinstance(evidence, list) or not evidence:
            fail('Every claim requires evidence')
        for item in evidence:
            start, end = item.get('start'), item.get('end')
            if type(start) is not int or type(end) is not int or not chunk['start'] <= start < end <= chunk['end']:
                fail('Evidence span must lie within its chunk')
            if item.get('quote') != texts[chunk['source_id']][start:end]:
                fail('Evidence quote does not match saved text verbatim')
    if disposition == 'duplicate_no_increment':
        duplicate = receipt.get('duplicate_of', {})
        if duplicate.get('type') == 'chunk_receipt':
            target = duplicate.get('chunk_id')
            if target == chunk_id or target not in prior:
                fail('duplicate_of must reference an existing prior chunk receipt')
        elif duplicate.get('type') == 'existing_knowledge':
            if not all(isinstance(duplicate.get(k), str) and duplicate[k].strip() for k in ('id', 'locator')):
                fail('Existing knowledge reference requires id and locator')
        else:
            fail('duplicate_of.type must be chunk_receipt or existing_knowledge')
    return receipt


def receipts(run, chunks, texts):
    folder = child(run, 'receipts')
    result = {}
    if folder.exists():
        for path in sorted(folder.iterdir()):
            if path.suffix != '.json':
                fail('Unexpected receipt file')
            receipt = json_file(path)
            if path.name != receipt.get('chunk_id', '') + '.json':
                fail('Receipt filename mismatch')
            result[receipt['chunk_id']] = receipt
        for receipt in result.values():
            validate_receipt(receipt, chunks, texts, result)
    return result


def read(args):
    run, manifest, chunks, texts = verify(args.run)
    chunk = next((c for c in chunks if c['chunk_id'] == args.chunk_id), None)
    if chunk is None:
        fail('Unknown chunk ID')
    text = texts[chunk['source_id']]
    start, end = chunk['start'], chunk['end']
    return {'chunk': dict(chunk, text=text[start:end]), 'context_before': {
        'start': max(0, start - 200), 'end': start, 'text': text[max(0, start - 200):start]},
        'context_after': {'start': end, 'end': min(len(text), end + 200), 'text': text[end:end + 200]},
        'context_note': 'Context is separate and is not evidence owned by this chunk.'}


def record(args):
    run, manifest, chunks, texts = verify(args.run)
    prior = receipts(run, chunks, texts)
    receipt = validate_receipt(json_file(args.receipt), chunks, texts, prior)
    chunk_id = receipt['chunk_id']
    destination = child(run, 'receipts/' + chunk_id + '.json')
    replace_sha = args.replace_receipt_sha
    if replace_sha is not None:
        if chunk_id not in prior:
            fail('Cannot replace a receipt that does not exist')
        old_bytes = destination.read_bytes()
        old_sha = sha(old_bytes)
        if replace_sha != old_sha:
            fail('Receipt replacement hash conflict; refusing all writes')
        history = child(run, 'receipt-history/' + chunk_id + '-' + old_sha + '.json')
        if history.exists() and history.read_bytes() != old_bytes:
            fail('Receipt history conflict; refusing all writes')
    if chunk_id in prior:
        if prior[chunk_id] == receipt:
            return {'chunk_id': chunk_id, 'status': 'already_recorded'}
        if replace_sha is None:
            fail('Receipt already exists with different content; refusing overwrite')
        # Archive exact old bytes first. An interrupted replacement retains the
        # current receipt and can safely resume using the same expected hash.
        if not history.exists():
            atomic(history, old_bytes)
        atomic(destination, encoded(receipt))
        return {'chunk_id': chunk_id, 'status': 'revised', 'previous_sha256': old_sha,
                'history': str(history)}
    atomic(destination, encoded(receipt))
    return {'chunk_id': chunk_id, 'status': 'recorded'}


def audit(args):
    run, manifest, chunks, texts = verify(args.run)
    prior = receipts(run, chunks, texts)
    pending = [c['chunk_id'] for c in chunks if c['chunk_id'] not in prior]
    review = [key for key, value in prior.items() if value['disposition'] == 'needs_review']
    extraction = [s['source_id'] for s in manifest['sources'] if s['status'] == 'needs_extraction']
    read_errors = [{'source_id': s['source_id'], 'path': s['path'], 'reason': s['reason'],
                    'error_stage': s['error_stage']}
                   for s in manifest['sources'] if s['status'] == 'read_error']
    covered = sum(c['end'] - c['start'] for c in chunks if c['chunk_id'] in prior)
    total = sum(len(t) for t in texts.values())
    complete = not pending and not review and not extraction and not read_errors and bool(manifest['sources'])
    return {'status': 'mechanically_complete' if complete else 'partial',
            'total_sources': len(manifest['sources']), 'total_chunks': len(chunks),
            'processed_chunks': len(prior), 'unprocessed_chunks': pending, 'needs_review': review,
            'needs_extraction': extraction, 'read_errors': read_errors,
            'empty_sources': [s['source_id'] for s in manifest['sources'] if s['status'] == 'empty'],
            'coverage': {'receipted_characters': covered, 'saved_text_characters': total,
                         'scope': 'Saved text offsets only; unsupported or unreadable originals have no established text coverage'},
            'read_coverage_complete': not pending and not extraction and not read_errors and bool(manifest['sources']),
            'receipts_complete': complete,
            'semantic_quality': 'not_machine_verified',
            'semantic_proof_scope': 'Only literal evidence equality and receipt structure are checked; no proof of reading, semantic completeness, duplicate equivalence or extraction fidelity.'}


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        fail('CLI arguments: ' + message)


def main(argv=None):
    parser = JsonArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('prepare')
    prep.add_argument('--source', action='append', required=True)
    prep.add_argument('--output-root', required=True)
    prep.add_argument('--batch-id', required=True)
    prep.add_argument('--goal', required=True)
    prep.add_argument('--domain', required=True)
    prep.add_argument('--profile', choices=['generic', 'domain-profile'], default='generic')
    prep.add_argument('--chunk-chars', type=int, default=12000)
    prep.add_argument('--recursive', action='store_true')
    prep.add_argument('--extractions')
    for name in ('read', 'record', 'audit'):
        command = commands.add_parser(name)
        command.add_argument('--run', required=True)
        if name == 'read':
            command.add_argument('--chunk-id', required=True)
        elif name == 'record':
            command.add_argument('--receipt', required=True)
            command.add_argument('--replace-receipt-sha', metavar='SHA256')
    try:
        args = parser.parse_args(argv)
        result = globals()[args.command](args)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 2 if result.get('status') == 'partial' else 0
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as error:
        print(json.dumps({'status': 'error', 'error': str(error)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    sys.exit(main())
