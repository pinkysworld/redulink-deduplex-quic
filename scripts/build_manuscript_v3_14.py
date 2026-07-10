from __future__ import annotations
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from pathlib import Path
import csv, json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'paper/submission/ReduLink_journal_ready_v3_14.docx'


def read_csv(name):
    with (ROOT/'results'/name).open(newline='') as fh:
        return list(csv.DictReader(fh))

def read_json(name):
    with (ROOT/'results'/name).open() as fh:
        return json.load(fh)

def fmtx(v):
    try: return f"{float(v):.2f}x"
    except Exception: return str(v)

def fmtn(v):
    try: return f"{int(float(v)):,}"
    except Exception: return str(v)

def f1(v):
    try: return f"{float(v):.1f}"
    except Exception: return str(v)

def f3(v):
    try: return f"{float(v):.3f}"
    except Exception: return str(v)

def add_cell_text(cell, text, size=8, bold=False):
    cell.text = ''
    p = cell.paragraphs[0]; p.paragraph_format.space_after = Pt(0)
    r = p.add_run(str(text)); r.font.size = Pt(size); r.bold = bold
    return cell

def add_table(doc, headers, rows, widths=None, font_size=8):
    t = doc.add_table(rows=1, cols=len(headers))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER; t.style = 'Table Grid'
    for i,h in enumerate(headers):
        add_cell_text(t.rows[0].cells[i], h, size=font_size, bold=True)
    for row in rows:
        cells = t.add_row().cells
        for i,val in enumerate(row):
            add_cell_text(cells[i], val, size=font_size)
    for row_index, row in enumerate(t.rows):
        trPr = row._tr.get_or_add_trPr()
        cant_split = OxmlElement('w:cantSplit'); trPr.append(cant_split)
        if row_index == 0:
            repeat_header = OxmlElement('w:tblHeader')
            repeat_header.set(qn('w:val'), 'true')
            trPr.append(repeat_header)
        for cell in row.cells:
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
            tcPr = cell._tc.get_or_add_tcPr(); tcMar = OxmlElement('w:tcMar')
            for m in ['top','left','bottom','right']:
                mar = OxmlElement(f'w:{m}'); mar.set(qn('w:w'), '40'); mar.set(qn('w:type'), 'dxa'); tcMar.append(mar)
            tcPr.append(tcMar)
    if widths:
        for row in t.rows:
            for idx, width in enumerate(widths):
                row.cells[idx].width = Inches(width)
    doc.add_paragraph('')
    return t

def para(doc, text, size=10, after=4, before=0):
    p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(after); p.paragraph_format.space_before = Pt(before)
    r = p.add_run(text); r.font.size = Pt(size); return p

def bullet(doc, text, size=10):
    p = doc.add_paragraph(); p.style = doc.styles['Normal']
    p.paragraph_format.left_indent = Inches(0.3); p.paragraph_format.first_line_indent = Inches(-0.18)
    p.paragraph_format.space_after = Pt(2)
    p.add_run('- ' + text).font.size = Pt(size); return p

def heading(doc, text, level=1):
    p = doc.add_heading(text, level=level)
    for r in p.runs:
        r.font.color.rgb = None; r.font.name = 'Arial'
    return p

def tcap(doc, text):
    p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(2); p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text); r.font.size = Pt(9); r.bold = True; return p

def figcap(doc, text):
    return para(doc, text, size=9, after=6)

def add_page_numbers(doc):
    sec = doc.sections[0]; fp = sec.footer.paragraphs[0]; fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = fp.add_run()
    fld1 = OxmlElement('w:fldChar'); fld1.set(qn('w:fldCharType'), 'begin')
    instr = OxmlElement('w:instrText'); instr.set(qn('xml:space'), 'preserve'); instr.text = 'PAGE'
    fld2 = OxmlElement('w:fldChar'); fld2.set(qn('w:fldCharType'), 'end')
    run._r.append(fld1); run._r.append(instr); run._r.append(fld2); run.font.size = Pt(9)

def picture(doc, relpath, width, cap):
    try:
        doc.add_picture(str(ROOT/relpath), width=Inches(width))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        figcap(doc, cap)
    except Exception:
        pass

# ---------------- load results ----------------
journal = read_csv('journal_workload_suite.csv')
def mult_for(artifact, method):
    wanted_chunker=None; real=method
    if method=='ReduLink fixed': real='redulink'; wanted_chunker='fixed'
    elif method=='ReduLink CDC': real='redulink'; wanted_chunker='cdc'
    for r in journal:
        if r.get('artifact')!=artifact or r.get('method')!=real: continue
        if wanted_chunker and r.get('chunker')!=wanted_chunker: continue
        if r.get('mode') not in ('warm-update-like','single-object'): continue
        return float(r['effective_multiplier'])
    return None
def bestcomp(artifact):
    vals=[mult_for(artifact,m) for m in ['gzip-6','zstd-3']]
    vals=[v for v in vals if v]; return max(vals) if vals else 0
def unchanged_pct(artifact):
    for r in journal:
        if r.get('artifact')==artifact and r.get('method')=='redulink' and r.get('chunker')=='fixed' and r.get('mode')=='warm-update-like':
            inp=float(r['input_bytes']); chg=float(r['aligned_changed_bytes'] or 0)
            return 100.0*(inp-chg)/inp if inp else 0.0
    return None

ext_public = read_csv('external_public_suite.csv')
rsync_public = {r['label']: r for r in read_csv('rsync_baseline_external_public.csv')}
ext_pos = read_csv('external_positive_suite.csv')
ext_obj = read_csv('external_object_workload_suite.csv')
quic_cases = read_csv('aioquic_workload_cases.csv')
quic_flow = read_csv('quic_flow_comparison.csv')
repeat = read_csv('repeated_quic_trials_summary.csv')
block = read_csv('journal_block_size_sensitivity.csv')
pypi = read_csv('pypi_version_pair_object_study.csv')
empath = read_json('quic_emulated_path.json')
empath_redis = read_json('quic_emulated_path_redis.json')
miss_sweep = read_csv('quic_miss_rate_sensitivity.csv')
quic_stats = read_csv('quic_statistical_evidence.csv')
frdict = read_csv('framing_dictionary_baseline.csv')
frmeta = read_json('framing_dictionary_baseline.json')
comp = read_csv('component_performance.csv')
scaling = read_csv('aioquic_scaling_experiment.csv')
bottleneck = read_csv('quic_bottleneck_emulation.csv')
compflow = read_json('quic_competing_flows.json')
wirefair = read_json('wire_fairness_accounting.json')
netem = read_json('linux_netem_quic_path.json')
semrepair = read_json('semantic_repair_demo.json')
udprepair = read_json('udp_repair_experiment.json')
authudp = read_json('authenticated_udp_experiment.json')

# ---------------- document ----------------
doc = Document()
sec = doc.sections[0]
for m in ('top_margin','bottom_margin','left_margin','right_margin'): setattr(sec, m, Inches(0.6))
styles = doc.styles
styles['Normal'].font.name='Arial'; styles['Normal'].font.size=Pt(10)
for s in ['Title','Heading 1','Heading 2','Heading 3']:
    if s in styles: styles[s].font.name='Arial'; styles[s].font.color.rgb=None
add_page_numbers(doc)

title = doc.add_paragraph(); title.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = title.add_run('ReduLink: Authenticated Reference Substitution for Redundancy-Suppressed Transfers over Encrypted QUIC Streams')
r.bold=True; r.font.size=Pt(15)
a = doc.add_paragraph(); a.alignment = WD_ALIGN_PARAGRAPH.CENTER
a.add_run('Michél Nguyen\nUniversity of the People | ORCID: 0000-0001-6834-4422').font.size=Pt(10)

heading(doc,'Abstract',1)
para(doc,"Encrypted transports such as QUIC deliberately hide payload bytes from the network, which disables the transparent in-network redundancy elimination that wide-area optimizers have historically relied on. ReduLink is an endpoint-controlled representation layer that recovers redundancy savings for receivers that already hold related bytes, without breaking encryption: it replaces repeated payload chunks with compact references that are individually authenticated against epoch, scope, stream identifier, reconstructed offset, length, nonce, and chunk identity. The contribution is not a new chunk-matching algorithm and not a claim of faster physical links; it is authenticated, scoped, QUIC-compatible reference substitution with explicit reconstruction, privacy scoping, and fail-closed semantics.")
para(doc,"The artifact maps bounded compact-binary ReduLink messages into server-authenticated aioquic streams, implements semantic MISS/FULL repair, derives a fresh per-run record key from an exporter surrogate plus random connection context, and independently validates receive sequence and reconstructed offset. It does not expose live QUIC TLS exporter bytes and does not authenticate the client. Exact object experiments reconstruct the ordered mapping of names, boundaries, empty objects, and contents; the secure profile also authenticates object headers. We compare fixed reuse, gzip/zstd, rsync, and a pinned zstd dictionary-delta baseline across deterministic and hash-pinned public bytes, and report local QUIC loss, scale, miss-rate, and path-emulation measurements. The legacy Linux tc/netem run launched raw and ReduLink transfers concurrently, so it is retained only as a contention diagnostic, not isolated single-flow latency or fairness evidence.")
para(doc,"On object-aligned public releases the corrected model reaches 1.92x to 9.31x (1.82x to 7.65x at the 29-byte-scope wire profile), and 21.37x (15.28x wire-priced) on the layer-like case. Baselines delimit the claim: rsync dominates ordinary source-tree updates, while zstd 1.5.7 --patch-from reaches about 66x to 1,801x where an exact prior stream and codec delta are acceptable. This baseline is not RFC 9842 Compression Dictionary Transport; RFC 9842 is an HTTP content-coding protocol with dictionary hashes and origin/availability constraints. QUIC AEAD already protects the on-path channel. ReduLink's additional HMACs instead bind post-TLS reference and dictionary state to epoch, scope, stream, offset, nonce, identifier, and length. The supported result is therefore conditional byte reduction with byte-exact, fail-closed reconstruction, not universal compression, lower latency, or Internet fairness.")
kp=doc.add_paragraph(); kp.paragraph_format.space_before=Pt(2)
kr=kp.add_run('Keywords: '); kr.bold=True; kr.font.size=Pt(9)
kp.add_run('QUIC; HTTP/3; redundancy elimination; data deduplication; content-defined chunking; shared dictionaries; authenticated references; encrypted transport; reproducible evaluation.').font.size=Pt(9)

heading(doc,'1. Introduction',1)
para(doc,"Encrypted transports restrict transparent in-network redundancy elimination. QUIC combines UDP transport, TLS security, stream multiplexing, loss recovery, and congestion control, which makes middlebox rewriting of payloads the wrong abstraction for most public or end-to-end encrypted deployments [6-10]. A WAN optimizer can only suppress redundancy that it can see, and a correctly deployed QUIC connection ensures that it sees only ciphertext. The redundancy, however, has not disappeared: registries, content-delivery networks, software-update services, and backup systems still send byte-stable objects to receivers that already hold closely related bytes from a previous transfer.")
para(doc,"The practical question is therefore not whether repeated bytes can be replaced by references. Fixed-block reuse, rsync, and low-bandwidth file systems already demonstrate that repeated bytes can be avoided [1-5], and HTTP delta and shared-dictionary mechanisms show that receiver-held bytes can be reused as a dictionary on the web [19-22]. The question this paper addresses is whether a reference-substitution mechanism can be made explicit, individually authenticated, privacy-scoped, and compatible with encrypted endpoint streams, without claiming a universal accelerator and without asking the application to become a file-tree synchronization protocol. Figure 1 shows the resulting architecture: cooperating endpoints that already control the plaintext decide, per chunk, whether to send bytes or an authenticated reference, and the receiver reconstructs or fails closed.")
para(doc,"We use one accounting vocabulary throughout. The effective multiplier is reconstructed or input bytes divided by encoded bytes at a stated accounting layer. Stream-payload multipliers exclude UDP/IP/link overhead; UDP-estimated multipliers add a local IPv4/UDP estimate; and congestion fairness, where claimed, applies to encoded bytes, not reconstructed bytes. This separation is deliberate: ReduLink changes how many application bytes a given number of wire bytes can reconstruct, not the physical line rate.")
para(doc,"This paper investigates three questions. RQ1: can reference substitution over encrypted QUIC streams be made explicit, authenticated, and privacy-scoped without custom transport-layer changes? RQ2: under which workload shapes does authenticated reference substitution save bytes, and where do simpler fixed-block reuse, compression, or rsync win? RQ3: what is the component-level cost of the authentication and accounting machinery, and how stable and fair are the native QUIC results across repeated runs, scales, and emulated bottlenecks? Section 7 answers RQ2, Sections 8 and 10 answer RQ3, and Sections 4 and 5 answer RQ1.")

heading(doc,'2. Contributions and Claim Boundary',1)
for item in [
 "An authenticated ReduLink reference format and validation model for endpoint-controlled encrypted streams, with per-frame binding of epoch, scope, stream id, reconstructed offset, length, nonce, and chunk identity.",
 "A compact binary mapping carried inside native aioquic QUIC streams, with byte-exact semantic MISS/FULL repair, repeated trials, and a payload-scaling experiment.",
 "A server-authenticated native path with fresh per-run exporter-surrogate key input, random connection context, independent receive-state checks, and negative tests for wrong secret, scope, epoch, stream, offset, length, replay, and tampering.",
 "A comparison against fixed-block reuse, gzip/zstd, and real rsync, including cases where these baselines win decisively, plus an explicit contrast with HTTP delta and shared-dictionary transport.",
 "External public source-release negative evidence, object-aligned public source-release workloads, and a public Redis-derived layer-like positive case, all hash-pinned and reproducible.",
 "Block-size sensitivity, component-cost measurements, paired local path-emulation diagnostics, and conservative accounting-layer separation without a production-fairness claim.",
]:
    bullet(doc,item)
para(doc,"The central claim is conditional. ReduLink helps when byte-stable chunks recur across warm endpoint state and authenticated reference substitution is preferable to a file-oriented delta protocol or local compression. It is not a replacement for rsync or compression, and the artifact is a native QUIC stream mapping rather than a custom QUIC extension-frame implementation. A practical example is a registry, CDN, backup, or update service that repeatedly sends object records to the same endpoint or tenant while preserving end-to-end QUIC encryption. In that setting the server can reference receiver-known objects or chunks without exposing plaintext to a middlebox; the price is authentication and metadata overhead, and the benefit is explicit context binding, safe miss repair, and a stream-compatible representation.")

heading(doc,'3. Background and Related Work',1)
heading(doc,'3.1 Network redundancy elimination',2)
para(doc,"Spring and Wetherall introduced protocol-independent redundancy elimination, suppressing repeated byte ranges on a link by caching recently seen content at both ends [1]. Subsequent work generalized this to network-wide and coordinated redundancy elimination (SmartRE) and to enterprise and end-system services (EndRE), and measured how much redundancy real traffic contains [2-4]. These systems are powerful but assume a vantage point that can observe or terminate plaintext. ReduLink targets the opposite regime, where the transport is end-to-end encrypted and only the endpoints can act, so the redundancy decision must move into the endpoint stack.")
heading(doc,'3.2 File-delta and low-bandwidth file systems',2)
para(doc,"rsync and the Low-Bandwidth File System (LBFS) show the value of transferring only the differences between file objects that both sides can name and compare [5]. They are the right tool when the workload is genuinely a file tree and both endpoints can run a delta protocol. As our negative results in Section 7.1 confirm, ordinary source-tree updates are better served by rsync than by stream-level reference substitution. ReduLink is not aimed at this case; it is aimed at object or stream delivery where a file-tree delta negotiation is not the serving abstraction.")
heading(doc,'3.3 HTTP delta and shared-dictionary transport',2)
para(doc,"The closest deployed lineage is HTTP receiver-side reuse. RFC 3229 defines delta encoding relative to a prior response, commonly with VCDIFF [19,20]. The 2016 SDCH proposal described shared dictionaries across HTTP responses [21]. RFC 9842 Compression Dictionary Transport lets an HTTPS origin advertise a previously fetched response for Brotli or Zstandard dictionary use [22]. Its dictionary identity is a SHA-256 hash; availability and same-origin constraints govern selection; and decoding failure causes the affected response to be discarded. It therefore has explicit integrity and failure semantics and can operate over HTTP/3 on QUIC.")
para(doc,"ReduLink is not a more secure replacement for RFC 9842. QUIC TLS/AEAD already protects either mechanism against on-path modification, while RFC 9842 validates dictionary identity. ReduLink instead offers a different representation granularity: individually resolved chunk references bound to epoch, scope, stream, reconstructed offset, length, and nonce, with an explicit MISS then FULL state-repair exchange outside HTTP content coding. The per-record HMAC is useful at the post-TLS representation boundary, where implementation bugs, stale or shared dictionary state, and cross-context confusion must fail closed; it is not claimed as a second independent network-adversary barrier. Section 12 therefore compares deployment abstractions, and the zstd --patch-from experiment is labeled a whole-stream dictionary-delta byte baseline rather than an implementation or analog of RFC 9842.")
heading(doc,'3.4 Content-defined chunking and deduplication privacy',2)
para(doc,"Content-defined chunking determines where chunk boundaries fall and strongly affects deduplication ratio and throughput; recent surveys and fast designs analyze the trade-offs in depth [11,12]. Chunking and deduplication also create content-existence side channels: deduplication can leak whether a receiver already holds particular content, and chunk-boundary parameters can themselves be attacked [13,16,17]. These results directly motivate ReduLink's privacy scoping (Section 4) and its exclusion of global cross-user dictionaries. Modern Ethernet line rates continue to increase [14], which is why the paper avoids physical-rate claims and reports only representation-layer savings.")
heading(doc,'3.5 Deployment model',2)
para(doc,"The deployment model has three roles: a sender with access to the new byte stream, a receiver with a scoped warm dictionary, and a policy domain that defines whether dictionary state is per connection, per origin, or per tenant. Public Internet mode defaults to per-connection dictionaries. Public artifact mode may use signed or manifest-controlled per-origin dictionaries. Enterprise mode may use per-tenant dictionaries with audit and quota controls. Global private cross-user dictionaries remain out of scope. Table 1 summarizes when ReduLink is and is not the right tool relative to rsync and compression.")
tcap(doc,'Table 1. ReduLink deployment modes and dictionary scoping.')
add_table(doc, ['Deployment','Dictionary scope','Why ReduLink rather than rsync/compression'], [
    ['CDN or registry objects','Per origin or per client','Objects arrive as encrypted streams; file-tree delta negotiation may not be the serving abstraction.'],
    ['Backup/page streams','Per endpoint or tenant','Page-like chunks recur across snapshots and can be referenced while preserving authenticated reconstruction.'],
    ['Enterprise VPN/admin domain','Per tenant','Policy can allow shared warm state while keeping middleboxes away from plaintext.'],
    ['Source-tree sync','File tree','Usually better served by rsync; ReduLink is not targeted here.'],
], widths=[1.4,1.4,3.5], font_size=8)

heading(doc,'4. Protocol and Security Model',1)
para(doc,"ReduLink is a representation layer for cooperating authorized endpoints. QUIC packetization, packet numbers, ACK processing, TLS, and congestion control remain QUIC responsibilities. The native artifact verifies the server's ephemeral certificate against its local trust anchor; it uses no client certificate and therefore must not be described as mutually authenticated. ReduLink defines how application bytes are represented as authenticated FULL, REF, MISS, and DICT_ACK records and how the receiver validates them. A REF is deliverable only if dictionary membership and content, epoch, scope, stream id, independently expected reconstructed offset, length, nonce, chunk identity, and authentication tag all validate; otherwise the receiver fails closed and requests semantic FULL repair.")
picture(doc,'figures/architecture/redulink_architecture.png',6.7,"Figure 1. ReduLink protocol and deployment architecture. The sender chunks outgoing bytes and emits FULL or authenticated REF records carried as compact binary application data inside an encrypted QUIC stream; the receiver validates each reference against dictionary membership and bound context before byte-exact reconstruction, failing closed and requesting semantic FULL repair on any mismatch.")
heading(doc,'4.1 Frame types and wire model',2)
para(doc,"ReduLink uses four logical frame types. A FULL carries and admits new bytes; a REF names a receiver-held chunk; MISS requests FULL fallback; and DICT_ACK may acknowledge admission. The stream_offset denotes reconstructed application position, never encoded-frame position. The receiver derives the expected offset from its own accepted state; it never validates an offset against the frame's own value. The offline model charges 24 bytes per FULL and 32 per REF. The compact binary artifact instead has a fixed 79-byte per-frame cost plus the UTF-8 scope length: 4-byte message length, 1-byte type, and 74 bytes of fixed fields (including identifier and tag). Thus the native 16-byte scope costs 95 bytes, while the 29-byte repricing profile costs 108. Section 7.6 states the selected profile rather than treating 108 bytes as universal.")
tcap(doc,'Table 2. ReduLink frame types and their authenticated fields.')
add_table(doc, ['Frame','Purpose','Bound / carried fields'], [
    ['FULL','Carry and admit new chunk bytes','epoch, stream id, stream offset, chunk length, chunk id, payload, auth tag'],
    ['REF','Reference a chunk already at the receiver','epoch, stream id, stream offset, original length, chunk id, reference nonce, auth tag'],
    ['MISS','Request FULL fallback (fail-closed)','epoch, stream id, stream offset, chunk id'],
    ['DICT_ACK','Acknowledge dictionary admission','epoch, chunk id, dictionary generation'],
], widths=[1.0,2.3,3.3], font_size=8)
heading(doc,'4.2 Validation and fail-closed reconstruction',2)
para(doc,"The receiver applies a fixed validation order before any byte is delivered, summarized as follows:")
for s in [
 "Reject frames whose epoch does not match the active epoch.",
 "For FULL, validate the authentication tag and chunk identifier, admit the payload to the dictionary, and deliver the bytes at the intended stream offset.",
 "For REF, validate the authentication tag, expansion bound, stream offset, original length, nonce, and dictionary presence; deliver reconstructed bytes only after all checks succeed.",
 "Emit MISS when the referenced chunk is unavailable or policy refuses the reference; a REF that cannot become valid in the current epoch triggers an immediate MISS.",
 "Apply stream ordering and flow control to reconstructed bytes, while applying congestion accounting to transmitted wire bytes.",
]:
    bullet(doc,s)
para(doc,"A reference miss is treated as a synchronization failure, not a corruption event: the receiver delivers no reconstructed bytes, emits MISS, and the sender repairs with a FULL for the same stream id, offset, length, and chunk id. A REF whose original_length disagrees with the stored chunk length, or that would expand beyond the negotiated bound, is a hard validation failure. Section 11 reports prototypes that exercise exactly these miss, tamper, and replay paths.")
heading(doc,'4.3 Dictionaries, epochs, and key schedule',2)
para(doc,"Dictionaries are per connection by default and per origin or tenant only under explicit policy; global private cross-user dictionaries are out of scope. Bounded LRU eviction, quotas, and epochs limit state. Chunk identifiers are keyed MACs over epoch, scope, and the chunk digest; frame tags additionally bind stream, offset, length, and nonce. aioquic's public API does not expose TLS exporter bytes, so the native experiment uses a fresh private random exporter surrogate and independent random connection context for every run, then applies the HKDF schedule over ALPN, epoch, scope, connection, and stream context. Only hashes of the public connection context are recorded. The standalone secure and UDP models retain fixed test keys for deterministic testing. A production profile must replace the surrogate with actual QUIC TLS exporter output.")
heading(doc,'4.4 Threat model',2)
para(doc,"Table 3 separates the specified security design from what the artifact implements and tests. The artifact validates the reference-authentication design and its negative cases; it should not be read as production-grade cryptographic integration. It implements HMAC binding, chunk-id validation, nonce rejection, length and expansion checks, and fail-closed repair, but it does not implement production exporter-derived keys, custom extension-frame parsing, production replay windows, or cross-tenant isolation enforcement. Like other deduplication systems, ReduLink can create a content-existence oracle when an adversary can choose payloads or references and observe transfer size, timing, or MISS behavior; per-connection dictionaries remove the cross-user oracle in public mode, and shared dictionaries are permitted only for public artifacts or explicit trust domains. The security evidence in this paper is artifact-level functional testing plus the reduction-style analysis of Section 4.5; no side-channel mitigations (padding, constant-shape errors, timing equalization) are implemented in the artifact. Dictionary eviction is itself an oracle in shared-dictionary modes: an adversary who can insert FULL traffic can cascade-evict a victim's warm entries (Section 8.2 demonstrates the mechanics under the LRU budget) and then probe REF-versus-MISS behavior to infer content existence, which is why per-connection scoping remains the default and shared dictionaries require explicit policy.")
tcap(doc,'Table 3. Security feature status: specified, implemented, tested, and future work.')
add_table(doc, ['Feature','Specified','Implemented','Tested','Future work'], [
    ['Per-reference integrity','FULL/REF tag binds chunk, length, stream offset, epoch, scope, nonce','HMAC-style tag and chunk-id checks','Tamper, wrong-context, wrong-length, reconstruction tests','Production key management'],
    ['Context binding and replay','Exporter-derived keys, epoch/scope/stream/offset binding, replay window','HKDF-style schedule in aioquic path; fixed-secret model paths bind context in MAC message','Wrong scope/epoch/stream/offset and nonce replay rejection tests','Live QUIC TLS exporter bytes and production replay window'],
    ['Dictionary safety','Authenticated FULL admission, manifest commitment, eviction policy','FULL chunk-id checks and bounded dictionary behavior','Budget overflow/recovery and fail-safe reconstruction tests','Signed-manifest policy and cross-tenant admission enforcement'],
    ['Expansion and repair bounds','Per-frame length, per-stream caps, MISS then FULL repair','Length checks and semantic repair prototypes','MISS/FULL, UDP repair, authenticated-UDP negative probes','Full production flow-control integration'],
    ['Privacy scope','Per-connection default; origin/tenant sharing only by explicit policy','Policy modeled and documented','Negative context-binding tests','Side-channel padding/timing mitigation and tenant isolation'],
], widths=[1.1,1.4,1.5,1.4,1.4], font_size=7)
tcap(doc,'Table 4. Privacy modes and leakage risks.')
add_table(doc, ['Mode','Dictionary scope','Leakage risk','Default'], [
    ['Public Internet','Per connection only','Same-connection access-pattern leakage','Yes'],
    ['Public artifacts','Per-origin signed manifest','Artifact-version / popularity inference','Optional'],
    ['Enterprise VPN','Tenant / admin domain','Intra-tenant content-existence leakage','Optional'],
    ['CDN/update channel','Origin-scoped public versions','Version-possession inference','Optional'],
    ['Global cross-user','Any user','Private content-possession leakage','No (out of scope)'],
], widths=[1.3,1.7,2.4,0.9], font_size=8)

heading(doc,'4.5 Formal security model and analysis',2)
para(doc,"We separate two boundaries. A network adversary may observe, drop, reorder, inject, duplicate, or replay QUIC packets, but QUIC TLS/AEAD already prevents that adversary from creating or modifying accepted stream plaintext [6,7]; ReduLink does not claim an additional independent on-path guarantee. The ReduLink analysis instead models an adversary at the decoded-record boundary who can present chosen records, replay previously authenticated records, and, in policy-authorized shared modes, influence dictionary contents, but does not know the per-connection record key K. Production endpoints derive K from the QUIC TLS exporter via HKDF [24]. The artifact tests this interface with a fresh per-run surrogate on its native path and fixed keys in deterministic model paths.")
para(doc,"We require four properties. Reference unforgeability: no efficient adversary can produce a FULL or REF frame that the receiver accepts and that delivers bytes the sender did not authenticate for the bound context, except with negligible probability. Context binding and replay resistance: a frame authenticated for a given epoch, scope, stream, and offset is rejected in any other context, and a nonce already seen within the epoch window is rejected. Expansion bound: an accepted REF delivers exactly the authenticated chunk length, so a small reference cannot reconstruct unbounded output. Dictionary safety: only authenticated FULL chunks, or signed-manifest chunks, are admitted to the dictionary. The theorem below covers the first two properties, with the replay and expansion bounds following from the same verification checks; manifest-mode dictionary safety is a specification requirement that is not analyzed here because the manifest mechanism is unimplemented (Table 3).")
para(doc,"Concretely (Section 4.1), each chunk identifier is a truncated keyed MAC, cid = HMAC_K(\"cid\", epoch, scope, SHA-256(chunk)), and each frame carries tag = HMAC_K(kind, epoch, scope, stream, offset, length, nonce, cid, SHA-256(payload)) [23]. Verification is authentication-first: the receiver recomputes the tag over the frame's own fields and rejects on mismatch with a single generic error, so an attacker without the key cannot distinguish which field was tampered with; only authentically-tagged frames proceed to the context checks (epoch, scope, stream, offset) and then to replay rejection against a bounded, reorder-tolerant nonce window. In the artifact the window holds the most recent nonces and treats anything at or below its floor as replayed, bounding receiver memory for long-lived sessions.")
para(doc,"Theorem (informal). Model HMAC-SHA-256 as a pseudorandom function (PRF), its 128-bit truncation as a random 128-bit function up to PRF distinguishing advantage, and SHA-256 as collision resistant. Then, after q verification attempts and n distinct identifiers in one key domain, acceptance of a fresh unauthorized frame is bounded by the PRF advantage plus approximately q/2^128 for a tag guess; resolving an authenticated identifier to different bytes is additionally bounded by the SHA-256 collision advantage plus approximately n(n-1)/2^129 for a truncated-identifier collision. EUF-CMA alone supports fresh-message tag unforgeability but does not by itself justify the birthday estimate for collisions between truncated HMAC outputs, hence the explicit PRF/random-function assumption.")
para(doc,"Proof sketch. A fresh accepted frame with no sender-authenticated canonical input either distinguishes HMAC from a random function or guesses its 128-bit tag. If a valid REF resolves to different bytes, the receiver's new content revalidation requires either a SHA-256 collision or equal 128-bit PRF outputs for distinct digests. Context fields are inside the tag and also checked against independently maintained receive state, so authentic cross-context records fail after authentication; repeated or below-window nonces fail replay state. The native path has per-run key/context freshness, while a whole deterministic standalone-model session can be replayed to a new decoder that deliberately reuses its fixed test key. Expansion is bounded because the receiver compares the stored chunk length and reconstructed object boundary before delivery. These are reduction-style arguments, not a machine-checked proof.")
para(doc,"The MAC input is canonical JSON with sorted keys and fixed separators; an interoperating implementation must reproduce this encoding or specify another canonical form. Both identifiers and tags are 128 bits in the artifact. Identifier sizing must therefore consider the total number of entries per key domain; very large or multi-tenant deployments should prefer 192 or 256 bits. The secure-model, native-state, wire-boundary, and authenticated-UDP tests exercise the stated checks, but production exporter integration, key lifecycle, and side-channel defenses remain future work.")
heading(doc,'5. Implementation and Metrics',1)
para(doc,"The artifact is implemented in Python for reproducibility and uses aioquic for native QUIC stream experiments [18]. ReduLink messages are compact binary application-stream records inside QUIC streams; this exercises a real QUIC handshake and encryption but does not implement custom QUIC frame types or transport parameters. The JSON encoding is retained only as a readable baseline, and the default path uses the compact binary format, which encodes frame type, stream id, reconstructed offset, length, chunk id, nonce, authentication tag, and payload only where required.")
para(doc,"Three byte layers are reported. Input bytes are the reconstructed application bytes. Stream-payload bytes are the ReduLink or raw application bytes written into QUIC streams. UDP-estimated bytes add a local IPv4/UDP estimate from the loopback proxy path. The paper avoids treating stream-payload multipliers as full wire-rate measurements; they isolate the representation layer so that raw QUIC, ReduLink, gzip, zstd, fixed reuse, and rsync-style baselines can be compared consistently. Table 5 records, for each evidence layer, what it supports and what it does not prove.")
para(doc,"Two reproducibility notes apply. Byte multipliers are deterministic functions of bytes and chunking parameters. Wall-clock and throughput values are local diagnostics. Component metadata records Python 3.13.0b2 on an arm64 development Mac; some historical transport evidence was produced in a Linux namespace and is labeled separately. Timings should be read as within-host order-of-magnitude costs, not portable guarantees.")
tcap(doc,'Table 5. Evidence hierarchy: what each layer supports and does not prove.')
add_table(doc, ['Evidence','Supports','Does not prove'], [
    ['Model','FULL/REF accounting and reconstruction','Transport behavior'],
    ['Secure model','HMAC binding and replay checks','Live QUIC exporter use'],
    ['aioquic stream','Encrypted QUIC stream mapping','Custom extension frames'],
    ['UDP/IPv4 estimate','Local datagram accounting','Full packet capture'],
    ['Workloads','Workload sensitivity','Universal acceleration'],
    ['Path emulation','Measured shared-bottleneck completion and queueing (userspace)','Kernel netem or Internet-path fairness'],
], widths=[1.3,2.6,2.6])

heading(doc,'6. Evaluation Methodology',1)
para(doc,"Evaluation uses four classes of evidence. First, deterministic journal fixtures (disk snapshot, OCI layer, package metadata, repository snapshot, structured logs, and a compressed negative control) isolate predicted positive and negative workload shapes. Second, public source-release pairs (Click, Redis, nginx) test ordinary source-tree updates where ReduLink should not be assumed to help. Third, object-aligned public release experiments use the same public bytes but model registry/CDN object delivery rather than tarball synchronization. Fourth, native aioquic stream experiments measure the encrypted stream mapping on positive and negative cases, under loss, at scale, and against competing flows and emulated bottlenecks. The journal fixtures are constructed with a chosen unchanged fraction and therefore illustrate workload shapes rather than estimate real-world gains; the only fully external inputs are the public source releases, which are negative for ReduLink, and their object-aligned re-framing, which is the paper's primary external positive signal. An author-independent-overlap version-pair study of real package upgrades is added in Section 7.5, and Section 7.6 re-prices all headline results at the measured wire framing and adds a dictionary-delta baseline.")
para(doc,"For each workload the paper reports ReduLink fixed chunking, ReduLink content-defined chunking where relevant, fixed-block reuse, compression, and rsync where the baseline is structurally applicable. The fixed-block baseline is intentionally strong and simple: if it beats ReduLink, the result is reported rather than hidden, because ReduLink is a security and transport-compatibility layer over reuse, not a superior matching algorithm. All external corpora are hash-pinned, and every figure and table is regenerated from committed result files.")

heading(doc,'7. Workload Results and Baseline Interpretation',1)
para(doc,"Table 6 reports the deterministic warm-state fixtures. On most byte-stable workloads, fixed-block reuse matches or beats ReduLink; the distinct ReduLink contribution is not superior matching but authenticated, scoped, stream-compatible reference substitution with explicit repair and privacy rules. The negative rows (package metadata, logs, and the compressed control) are included precisely because they fail: where repetition is local to one object, compression wins, and where there is no reusable structure, both fixed reuse and ReduLink correctly decline to help. The Unchanged column makes the mechanism explicit: because for aligned whole-chunk reuse the effective multiplier is bounded by roughly one over one minus the unchanged fraction (the fixed-block-reuse column can exceed this bound because its byte-scan alignment also matches moved content), these deterministic fixtures (96 to 100 percent unchanged on the positive rows) are illustrative workload shapes chosen to expose where reference substitution can and cannot help, not estimates of real-world overlap. The repository fixture in particular changes only 210 of 501,760 bytes, so its 24.73x is close to a no-op transfer.")
def bcomp(a): return bestcomp(a)
artifacts=[('scripted-disk-snapshot','disk snap'),('scripted-oci-layer','oci layer'),('scripted-package-metadata','package meta'),('scripted-repository-snapshot','repository snap'),('scripted-structured-logs','logs'),('independent-compressed-negative','compressed neg')]
rows=[]
for art,label in artifacts:
    rl=mult_for(art,'ReduLink fixed') or mult_for(art,'ReduLink CDC') or 0
    fixed=mult_for(art,'fixed-block-reuse') or 0; bc=bcomp(art)
    up=unchanged_pct(art); ups=(f"{up:.1f}%" if up is not None else 'n/a')
    rows.append([label, ups, fmtx(rl), fmtx(fixed), fmtx(bc), f"{rl-fixed:+.2f}x"])
tcap(doc,'Table 6. Warm-state workload results (effective stream-payload multiplier), with the constructed unchanged fraction of each fixture.')
add_table(doc, ['Workload','Unchanged','ReduLink','Fixed reuse','Best compression','RL - fixed'], rows, widths=[1.4,0.9,1.0,1.0,1.2,1.0])

heading(doc,'7.1 External Public Source Releases',2)
para(doc,"Table 7 reports three independent, hash-pinned source-release pairs. The result is negative for ReduLink and strongly positive for rsync. This is an important and deliberately reported finding: ordinary related source trees are better served by file-oriented delta transfer than by stream-level reference substitution, because rsync can exploit fine-grained intra-file similarity that whole-object referencing cannot.")
rows=[]
for r in ext_public:
    rs=rsync_public.get(r['label'],{})
    rows.append([r['label'].replace('-to-',' to '), fmtx(r['redulink_multiplier']), fmtx(r['fixed_block_reuse_multiplier']), fmtx(rs.get('rsync_effective_multiplier_control_plus_data',''))])
tcap(doc,'Table 7. External public source-release pairs: ReduLink and fixed reuse versus real rsync (negative case for ReduLink).')
add_table(doc, ['Public pair','ReduLink','Fixed reuse','rsync total'], rows, widths=[2.6,1.0,1.0,1.0])

heading(doc,'7.2 Object-Aligned Public Release Transfers',2)
para(doc,"Table 8 and Figure 2 use the same public tarballs but change the transfer abstraction: every relative name, object length, empty object, and content byte is encoded and decoded exactly, while chunking restarts at object boundaries and warm state remains shared across objects. The secure profile MACs each name/length boundary and binds frames to an object-derived stream id. Reconstruction success is computed by comparing the complete ordered object mapping, not assigned by accounting logic. Redis and nginx remain positive because many objects are stable; Click is weaker. This is external transfer-model evidence, not a captured registry trace.")
rows=[]
for r in ext_obj:
    label=r['label'].split('-object-sequence')[0]
    files=f"{r['unchanged_file_count']}/{r['new_file_count']} unchanged"
    rows.append([label, files, fmtn(r['input_bytes']), fmtx(r['redulink_multiplier']), fmtx(r['secure_multiplier']), fmtx(r['fixed_object_reuse_multiplier']), fmtx(r['gzip_new_object_stream_multiplier'])])
tcap(doc,'Table 8. Object-aligned public release transfers modeling registry/CDN object delivery.')
add_table(doc, ['Public release','File stability','Bytes','ReduLink','Secure RL','Fixed object reuse','gzip'], rows, widths=[1.2,1.2,0.8,0.8,0.8,1.0,0.8], font_size=7)
picture(doc,'figures/external_object_workload/external_object_workload_multipliers.png',6.4,"Figure 2. Object-aligned public release transfers: effective stream-payload multipliers for ReduLink, the authenticated variant, fixed object reuse, and gzip.")

heading(doc,'7.3 Layer-Like External-Positive Case',2)
para(doc,"Table 9 reports a Redis-derived layer-like case built from included public Redis release bytes and aligned changed blocks. Its role is to test the predicted positive case for layer-like objects where stable chunks remain aligned; it is not a production trace. Here ReduLink reaches 21.37x with the authenticated variant at 18.96x, again close to the fixed-reuse reference.")
r=ext_pos[0]
tcap(doc,'Table 9. Layer-like external-positive case derived from public Redis release bytes.')
add_table(doc, ['Case','Input bytes','ReduLink','Secure RL','Fixed reuse'], [[r['label'], fmtn(r['new_bytes']), fmtx(r['redulink_multiplier']), fmtx(r['secure_multiplier']), fmtx(r['fixed_block_reuse_multiplier'])]], widths=[2.3,1.0,1.0,1.0,1.0])

doc.add_page_break()
heading(doc,'7.4 Block-Size Sensitivity',2)
para(doc,"Table 10 and Figure 3 show that the best block size is workload-dependent: smaller blocks capture more aligned reuse but pay more per-chunk overhead, while larger blocks lose alignment. The artifact therefore treats 4 KiB as a reproducible default rather than a universal optimum, and a production deployment would tune the chunk size per workload class. The content-defined chunker consistently underperforms fixed chunking on these aligned fixtures (at 4 KiB: 10.71x versus 28.49x on the disk snapshot, 4.60x versus 11.05x on the OCI layer), because the fixtures change bytes in place without insertions; CDC's insertion robustness is not exercised here, and its Python implementation is also the slowest component in Table 17.")
arts=['scripted-disk-snapshot','scripted-oci-layer','scripted-repository-snapshot']
rows=[]
for art in arts:
    vals=[]
    for size in ['1024','2048','4096','8192','16384']:
        m=''
        for r in block:
            if r['artifact']==art and r['chunker']=='fixed' and r['chunk_size']==size: m=fmtx(r['effective_multiplier']); break
        vals.append(m)
    rows.append([art.replace('scripted-','').replace('-',' ')]+vals)
tcap(doc,'Table 10. Block-size sensitivity of the effective multiplier (fixed chunking).')
add_table(doc, ['Workload','1 KiB','2 KiB','4 KiB','8 KiB','16 KiB'], rows, widths=[1.5,0.8,0.8,0.8,0.8,0.8])
picture(doc,'figures/block_size/block_size_sensitivity.png',5.6,"Figure 3. Block-size sensitivity of the effective multiplier for fixed chunking across three warm-update fixtures.")

heading(doc,'7.5 Package version-pair study (PyPI)',2)
para(doc,"Table 11 applies the identical exact object encoder/decoder to six hash-pinned pairs of real PyPI wheels. The prior flat concatenation check has been removed because it used different boundaries and did not validate names. Patch releases with high file stability (rich, 77 of 83 objects unchanged; click, 14 of 22) reach about 11x to 12x, whereas jinja2, urllib3, and packaging change enough objects that gzip wins. The package/version selection remains author-chosen, so this is not population-weighted or a client trace. PyPI currently transfers compressed wheel archives rather than per-member objects; realizing these modeled gains would require a different registry serving abstraction. The gzip comparison is over the same uncompressed named-object stream and should not be mapped directly to today's wheel traffic.")
rows=[]
for r in pypi:
    rows.append([r['package'], r['old_version']+"->"+r['new_version'], f"{r['unchanged_file_count']}/{r['new_file_count']}", fmtx(r['redulink_multiplier']), fmtx(r['secure_multiplier']), fmtx(r['fixed_object_reuse_multiplier']), fmtx(r['gzip_new_object_stream_multiplier']), 'OK' if r['reconstruction_ok']=='True' else 'FAIL'])
tcap(doc,'Table 11. PyPI version-pair study: real package upgrades (object-aligned, hash-pinned).')
add_table(doc, ['Package','Versions','Files unch.','ReduLink','Secure RL','Fixed reuse','gzip','Recon.'], rows, widths=[1.0,1.1,0.8,0.8,0.8,0.9,0.7,0.6], font_size=7)
heading(doc,'7.6 Framing sensitivity and a dictionary-delta baseline',2)
para(doc,"Table 12 reports two review-driven checks. First, it re-prices model frames at the compact binary profile selected for this experiment: fixed 79-byte overhead plus a 29-byte scope, or 108 bytes per FULL/REF. This is profile-specific; the native 16-byte scope costs 95 bytes. With exact object headers included, Redis falls from 9.31x to 7.65x and the layer-like case remains 21.37x to 15.28x. Second, zstd 1.5.7 [26] uses the prior serialized object stream with the pinned command zstd -3 --patch-from OLD NEW -o PATCH -f -q. It reaches about 66x to 1,801x and dominates whenever the exact prior stream and codec delta are acceptable. This is a whole-stream dictionary-delta baseline, not RFC 9842: it does not exercise HTTP dictionary advertisement, SHA-256 dictionary identity, availability/same-origin rules, or response failure handling. ReduLink is therefore not byte-optimal; its distinct abstraction is incremental chunk resolution with authenticated post-TLS context and explicit semantic repair.")
rows=[]
for r in frdict:
    rows.append([r['label'].replace('object-','').replace('pypi-','pypi '), fmtn(r['input_bytes']), fmtx(r['model_multiplier']), fmtx(r['repriced_multiplier']), fmtx(r['zstd_patch_multiplier']), fmtx(r['gzip_multiplier'])])
tcap(doc,'Table 12. Framing repricing (79 fixed bytes + 29-byte scope = 108 bytes) and pinned zstd 1.5.7 whole-stream dictionary delta on the same object streams.')
add_table(doc, ['Case','Input bytes','RL (model)','RL (wire-priced)','zstd --patch-from','gzip'], rows, widths=[2.0,1.0,0.9,1.1,1.2,0.7], font_size=7)

heading(doc,'8. Native QUIC Experiments',1)
heading(doc,'8.1 Stream mapping under loss',2)
para(doc,"Table 13 compares raw and ReduLink stream mapping at zero and periodic datagram loss, and Table 14 reports positive and negative workload cases. Every run verifies the ephemeral server certificate, uses a fresh record-key surrogate/context, checks HELLO metadata, and reconstructs exactly. The compressed-negative control correctly yields no gain. The Redis-layered corpus reaches 21.37x in the offline model but about 3.83x over QUIC because the native experiment uses 1 KiB chunks, pays the 95-byte native framing profile (79 + 16-byte scope) rather than the model's 32-byte REF charge, and deliberately withholds every seventh dictionary chunk, forcing 72 payload-bearing repairs. Offline tables isolate representation accounting; QUIC tables are end-to-end stream evidence.")
rows=[]
for r in quic_flow:
    rows.append([r['method'].replace('-quic-stream','').replace('redulink-binary','ReduLink').replace('raw','Raw'), r['loss_every'], fmtx(r['effective_multiplier']), fmtx(r['approx_ipv4_udp_multiplier_seen']), 'OK' if r['reconstruction_ok']=='True' else 'FAIL'])
tcap(doc,'Table 13. Native aioquic stream mapping: raw versus ReduLink under zero and periodic datagram loss.')
add_table(doc, ['Method','Loss every','Stream x','UDP-est x','Recon.'], rows, widths=[1.8,0.9,0.9,0.9,0.8])
rows=[]
for r in quic_cases:
    rows.append([r['label'].replace('independent-compressed-negative','compressed negative').replace('external-positive-redis-layered','Redis layered').replace('demo-positive','demo positive'), fmtn(r['input_bytes']), fmtx(r['stream_payload_multiplier']), fmtx(r['approx_ipv4_udp_multiplier_seen']), r['semantic_misses'], 'OK' if r['reconstruction_ok']=='True' else 'FAIL'])
tcap(doc,'Table 14. Native aioquic stream mapping across positive and negative workload cases.')
add_table(doc, ['Case','Input','Stream x','UDP-est x','Misses','Recon.'], rows, widths=[1.8,0.9,0.9,0.9,0.7,0.7])
picture(doc,'figures/quic_workload_cases.png',6.4,"Figure 4. Native aioquic stream mapping on positive and negative workload cases.")

heading(doc,'8.2 Repeated trials and scaling',2)
para(doc,"Table 15 reports 20 repeated trials of the native demo workload. The ReduLink stream multiplier is near-deterministic for fixed bytes, while elapsed times vary across localhost runs; reporting both avoids selecting one favorable timing. Table 16 scales from 96 to 16,384 blocks (96 KiB to 16 MiB). With the default 8,192-chunk budget, the 16,384-chunk warm set overflows the LRU; sequential FULL admission cascade-evicts remaining warm entries and degrades to a FULL-only 0.92x while still reconstructing exactly. Raising the budget to 24,576 restores 3.96x. Dictionary sizing relative to the warm working set is therefore a provisioning requirement; the single-run elapsed times are host-dependent diagnostics, not a speedup claim.")
sel=[]
for r in repeat:
    if r['metric'] in {'raw_client_ms','redulink_stream_multiplier','redulink_udp_est_multiplier','redulink_client_ms'}:
        sel.append([r['metric'].replace('_',' '), r['n'], r['mean'], r.get('stdev',''), r['min'], r['max']])
tcap(doc,'Table 15. Repeated native QUIC trials (n = 20): run-to-run stability of multipliers and elapsed time.')
add_table(doc, ['Metric','n','Mean','Std. dev.','Min','Max'], sel, widths=[2.0,0.5,1.0,1.0,1.0,1.0], font_size=7)
rows=[]
for r in scaling:
    rows.append([r['payload_blocks'], fmtn(r['input_bytes']), fmtn(r.get('dictionary_budget_chunks','8192')), fmtx(r['stream_payload_multiplier']), r['semantic_misses'], f1(r['client_elapsed_ms']), 'OK' if r['reconstruction_ok']=='True' else 'FAIL'])
tcap(doc,'Table 16. Payload scaling of the native aioquic stream mapping, including the dictionary-budget overflow and recovery at 16 MiB.')
add_table(doc, ['Blocks','Input bytes','Dict budget','Stream x','Misses','Client ms','Recon.'], rows, widths=[0.9,1.1,0.9,0.8,0.8,0.9,0.7], font_size=7)

heading(doc,'9. Component Costs',1)
para(doc,"Table 17 reports component-level throughput on the development Mac identified in results/component_performance.metadata.json. Fixed chunking, HMAC validation, and compact binary encoding are fast in this local run; the Python content-defined chunker is slow. A production implementation would require optimized native chunking and tighter transport integration. These are hardware-dependent diagnostics, not line-rate guarantees.")
components=['fixed_chunking','cdc_chunking','model_fixed_encode_decode','model_cdc_encode_decode','secure_hmac_encode_roundtrip','secure_hmac_decode','binary_wire_encode','binary_wire_decode']
rows=[]
for c in components:
    for r in comp:
        if r['component']==c:
            summary=json.loads(r['result_summary']); ok=summary.get('reconstruction_ok', summary.get('roundtrip_reconstruction_ok',''))
            ok='OK' if ok is True else ('FAIL' if ok is False else 'not applicable')
            label=c.replace('model_fixed_encode_decode','model fixed roundtrip').replace('model_cdc_encode_decode','model CDC roundtrip').replace('secure_hmac_encode_roundtrip','HMAC roundtrip').replace('secure_hmac_decode','HMAC decode').replace('binary_wire_encode','wire encode').replace('binary_wire_decode','wire decode').replace('fixed_chunking','fixed chunking').replace('cdc_chunking','CDC chunking')
            rows.append([label, fmtn(r['input_bytes']), f1(r['throughput_mib_s_local']), ok])
tcap(doc,'Table 17. Component-level cost measurements (local Python artifact timing; not production line-rate).')
add_table(doc, ['Component','Input bytes','MiB/s local','Roundtrip'], rows, widths=[2.1,1.2,1.1,1.2])

heading(doc,'10. Transport Accounting and Local Diagnostics',1)
para(doc,"Scope note: Section 10 provides localhost accounting and emulation evidence, not transport-fairness proof. The userspace shaper has an explicit shared bottleneck; the unshaped concurrent diagnostic does not. The committed Linux tc/netem rows are a legacy v3.13 run in which raw and ReduLink were launched concurrently, so they cannot be interpreted as isolated single-flow latency. None of these results proves WAN performance, Mininet behavior, production congestion fairness, or deployment-population effects.")
para(doc,"The central fairness rule is that ReduLink must not receive congestion credit for reconstructed bytes: congestion control and bottleneck service account encoded wire bytes only. Table 18 reports the wire-byte accounting experiment, in which ReduLink's encoded wire share is "+f3(wirefair['wire_share_redulink'])+" against the raw stream's "+f3(wirefair['wire_share_raw'])+" over "+str(wirefair['rounds'])+" rounds, while still reconstructing the same application bytes; the effective application multiplier on that 48 KiB wire-accounting fixture is "+fmtx(wirefair['redulink_effective_app_multiplier'])+". This confirms that the savings appear as fewer encoded bytes, which is the only place a fair transport should credit them.")
tcap(doc,'Table 18. Wire-byte fairness accounting: ReduLink is charged on encoded bytes, not reconstructed bytes.')
add_table(doc, ['Metric','Value'], [
    ['Fairness rule','Congestion and bottleneck service count encoded wire bytes'],
    ['Raw encoded wire share', f3(wirefair['wire_share_raw'])],
    ['ReduLink encoded wire share', f3(wirefair['wire_share_redulink'])],
    ['ReduLink uses less wire than raw', 'yes' if wirefair['redulink_uses_less_wire_than_raw'] else 'no'],
    ['Effective application multiplier', fmtx(wirefair['redulink_effective_app_multiplier'])],
    ['Rounds', str(wirefair['rounds'])],
], widths=[2.6,3.2])
para(doc,"Table 19 reports "+str(compflow['rounds'])+" concurrent raw/ReduLink localhost rounds with periodic datagram loss. There is no controlled rate limit or bottleneck, and the rate hint is metadata only. The previous artifact computed one Jain value [25] across all observations and called it fairness; v3.14 instead computes a two-flow balance index within each round and reports the mean solely as a concurrency diagnostic. Because the methods intentionally encode different byte volumes, neither encoded-rate nor reconstructed-rate balance is a congestion-fairness measure. Table 20 adds a shared userspace bottleneck, Table 21 varies miss rate, Table 22 reports local repeat variability, and Table 24 is only a closed-form byte-volume illustration.")
tcap(doc,'Table 19. Unshaped concurrent localhost diagnostic (mean of per-round two-flow balance indices; not fairness).')
add_table(doc, ['Metric','Value'], [
    ['Scenario', f"{int(compflow['rounds'])} concurrent rounds, unshaped localhost (no rate limit), loss every {compflow['loss_every']}"],
    ['Encoded-rate balance index (mean)', f3(compflow['encoded_rate_balance_index_mean'])],
    ['Reconstructed-rate balance index (mean)', f3(compflow['reconstructed_rate_balance_index_mean'])],
    ['All flows reconstructed', 'yes' if compflow['all_reconstructed'] else 'no'],
    ['Scope', 'unshaped localhost concurrency diagnostic; no fairness inference'],
], widths=[2.4,3.4], font_size=8)

para(doc,"Table 20 adds a measured full-duplex userspace bottleneck: both flows share one token bucket per direction plus propagation delay, across 5/20 Mbps and 20/80 ms points with 20 rounds each. Completion comparison now uses the mean of within-round ReduLink/raw ratios; the ratio of aggregate means is retained in JSON only as a diagnostic. On the refreshed demo run the paired mean ranges from 0.87x to 1.01x; Redis ranges from 0.82x to 1.30x. Reconstruction is exact throughout. The variation supports only a conditional local result: byte savings may reduce completion time, while MISS/FULL round trips and scheduling may erase or reverse it. Identical NewReno stacks and encoded-byte accounting are necessary conditions for a fair deployment, but this harness does not prove Internet fairness.")
rows=[]
for tag, summ in (('demo', empath['summary']), ('redis', empath_redis['summary'])):
    for sm in summ:
        raw = f"{f1(sm['raw_completion_ms_mean'])}\u00b1{f1(sm['raw_completion_ms_sd'])}"
        rl = f"{f1(sm['redulink_completion_ms_mean'])}\u00b1{f1(sm['redulink_completion_ms_sd'])}"
        rows.append([tag, f1(sm['rate_mbps']), f1(sm['rtt_ms']), raw, rl, f"{float(sm['completion_ratio_paired_mean']):.2f}x", f3(sm['encoded_rate_balance_index']), 'OK' if sm['all_reconstructed'] else 'FAIL'])
tcap(doc,'Table 20. Measured full-duplex userspace shared-bottleneck emulation: mean completion time and mean paired completion ratio (20 local rounds per scenario).')
add_table(doc, ['Payload','Rate Mbps','RTT ms','Raw ms','ReduLink ms','Mean paired RL/raw','Rate balance diag.','Recon.'], rows, widths=[0.7,0.9,0.7,1.0,1.0,1.0,1.0,0.6], font_size=7)

para(doc,"Table 21 turns the qualitative miss-rate claim into a sensitivity check. It uses the same native aioquic stream mapping and full-duplex userspace shaper at the constrained 5 Mbps, 20 ms point, but varies receiver dictionary thinning on the byte-stable demo payload. As the semantic miss fraction rises from about 1 percent to about 49 percent, ReduLink's stream multiplier falls from 5.75x to 1.48x and the completion-time advantage narrows from roughly 0.64-0.74x to 0.85x of the raw flow. This does not replace a broader rate/RTT grid, and the first row has high raw-flow timing dispersion, but it directly supports the mechanism-level explanation: repair payloads and reverse MISS/FULL round trips progressively consume the byte-saving advantage while preserving byte-exact reconstruction.")
rows=[]
for r in miss_sweep:
    raw = f"{f1(r['raw_completion_ms_mean'])}\u00b1{f1(r['raw_completion_ms_sd'])}"
    rl = f"{f1(r['redulink_completion_ms_mean'])}\u00b1{f1(r['redulink_completion_ms_sd'])}"
    rows.append([r['missing_every'], f"{float(r['miss_fraction_mean'])*100:.1f}%", raw, rl, f"{float(r['rl_over_raw_completion_mean']):.2f}x", fmtx(r['redulink_stream_multiplier_mean']), 'OK' if r['all_reconstructed']=='True' else 'FAIL'])
tcap(doc,'Table 21. Native QUIC miss-rate sensitivity at 5 Mbps and 20 ms RTT on byte-stable demo bytes (three rounds per point).')
add_table(doc, ['Dictionary thinning','Miss fraction','Raw ms','ReduLink ms','RL/raw','Stream x','Recon.'], rows, widths=[1.1,0.9,1.1,1.1,0.7,0.8,0.6], font_size=7)

doc.add_page_break()
stat_keys=[
    ('quic_emulated_path','demo; rate=5.0Mbps; rtt=20.0ms; loss_every=0','completion_ratio_redulink_over_raw','Demo constrained completion ratio'),
    ('quic_emulated_path','demo; rate=5.0Mbps; rtt=20.0ms; loss_every=0','encoded_byte_ratio_redulink_over_raw','Demo encoded-byte ratio'),
    ('quic_emulated_path_redis','redis; rate=5.0Mbps; rtt=20.0ms; loss_every=0','completion_ratio_redulink_over_raw','Redis constrained completion ratio'),
    ('quic_emulated_path_redis','redis; rate=5.0Mbps; rtt=20.0ms; loss_every=0','encoded_byte_ratio_redulink_over_raw','Redis encoded-byte ratio'),
    ('quic_competing_flows','localhost concurrent aioquic pair; rate_hint=25Mbps','completion_ratio_redulink_over_raw','Concurrent localhost completion ratio'),
    ('quic_competing_flows','localhost concurrent aioquic pair; rate_hint=25Mbps','encoded_byte_ratio_redulink_over_raw','Concurrent localhost encoded-byte ratio'),
    ('repeated_quic_trials','native aioquic sequential smoke repeats','redulink_udp_est_multiplier','Sequential UDP-estimated multiplier'),
]
by_stat={(r['experiment'],r['scenario'],r['metric']):r for r in quic_stats}
rows=[]
for exp,scenario,metric,label in stat_keys:
    r=by_stat[(exp,scenario,metric)]
    rows.append([label, r['n'], f3(r['mean']), f"[{f3(r['ci95_low'])}, {f3(r['ci95_high'])}]", exp])
para(doc,"Table 22 reports deterministic percentile-bootstrap intervals over repeated local measurements, using within-round raw/ReduLink ratios where available. These intervals describe variability in these particular localhost runs; they are not confidence intervals for WAN paths, machines, deployments, or a sampled population. Byte ratios are stable, while completion intervals show that repair and scheduling can move results around parity. The macOS dummynet path still times out on the development Mac, and Table 23 is retained with an explicit legacy-design warning.")
tcap(doc,'Table 22. Within-run variability for repeated native QUIC measurements (deterministic bootstrap intervals; no population inference).')
add_table(doc, ['Result','n','Mean','95% CI','Source'], rows, widths=[2.0,0.4,0.7,1.0,1.7], font_size=7)

para(doc,"Table 23 preserves the v3.13 Linux tc/netem data for transparency, but the original runner launched raw and ReduLink transfers concurrently under one qdisc. The reported 1.08x to 1.60x demo and 1.30x to 1.36x Redis completion ratios therefore combine method cost with mutual contention and cannot estimate isolated single-flow latency or establish the proposed half-duplex causal mechanism. The old runner also did not capture host, command, tool-version, or active-qdisc snapshots; the only retained provenance is the rootless namespace context and source commit. The v3.14 runner fixes the design by defaulting to isolated, order-alternated pairs and recording command, platform, Python, aioquic, tc, commit, and qdisc state. Until that corrected sweep is rerun on Linux, Table 23 is exploratory contention evidence. Its byte counts and reconstruction checks remain factual for the observed runs.")
rows=[]
for sm in netem['summary']:
    ci=f"[{f3(sm['completion_ratio_ci95_low'])}, {f3(sm['completion_ratio_ci95_high'])}]"
    rows.append([sm['payload'], f1(sm['rate_mbps']), f1(sm['rtt_ms']), f"{float(sm['completion_ratio_mean']):.2f}x {ci}", f3(sm['encoded_byte_ratio_mean']), str(int(sm['rounds'])), 'OK' if sm['all_reconstructed'] else 'FAIL'])
tcap(doc,'Table 23. Legacy v3.13 concurrent Linux tc/netem contention diagnostic (not isolated latency; incomplete environment provenance).')
add_table(doc, ['Payload','Rate Mbps','RTT ms','RL/raw completion (95% CI)','Enc-byte ratio','n','Recon.'], rows, widths=[0.8,0.9,0.7,2.2,1.0,0.5,0.6], font_size=7)

# bottleneck scenarios
scn={}
for r in bottleneck:
    key=(r['rate_mbps'], r['rtt_ms']); scn.setdefault(key,{})[r['method']]=r
rows=[]
for (rate,rtt),d in scn.items():
    raw=d['raw-quic-stream']; rl=d['redulink-binary-quic-stream']
    rows.append([f1(rate), f1(rtt), f1(raw['completion_ms_emulated']), f1(rl['completion_ms_emulated']), f1(raw['reconstructed_goodput_mbps_emulated']), f1(rl['reconstructed_goodput_mbps_emulated'])])
tcap(doc,'Table 24. Analytic fluid-model completion times and implied application rates from measured encoded stream bytes (raw versus ReduLink); computed, not measured.')
add_table(doc, ['Rate Mbps','RTT ms','Raw compl. ms (model)','RL compl. ms (model)','Raw app rate Mbps (model)','RL app rate Mbps (model)'], rows, widths=[0.9,0.7,1.2,1.2,1.3,1.3], font_size=7)
para(doc,"The package includes reviewer-runnable macOS dummynet and Linux tc/netem harnesses. Table 23 is a completed but methodologically concurrent legacy run, while the corrected isolated Linux sweep remains to be executed. A full Mininet or multi-host congestion-control study with independent production-style flows remains future work.")

heading(doc,'11. Repair and Authentication Prototypes',1)
para(doc,"Beyond the in-stream experiments, three prototypes exercise the fail-closed and authentication paths directly. Table 25 summarizes them. The semantic-repair demo forces a 25 percent dictionary-miss fraction and confirms that every miss is repaired with a FULL and that reconstruction is byte-exact. The localhost UDP repair experiment drops every seventh data datagram and uses timeout-based retransmission, again reconstructing fully after "+str(udprepair['repair_full_frames'])+" semantic repairs and "+str(udprepair['client_retransmissions'])+" retransmissions. The authenticated UDP experiment adds explicit negative probes: a tampered authentication tag and a replayed nonce are both rejected ("+str(authudp['tamper_probe_rejections'])+" tamper and "+str(authudp['replay_probe_rejections'])+" replay rejection) before normal authenticated repair traffic is accepted, demonstrating fail-closed behavior under active manipulation.")
tcap(doc,'Table 25. Repair and authentication prototypes (localhost).')
add_table(doc, ['Prototype','Input bytes','Misses / repairs','Negative probes rejected','Recon.'], [
    ['Semantic repair demo', fmtn(semrepair['input_bytes']), f"{semrepair['misses']} / {semrepair['repair_full_frames']}", 'n/a (25% missing)', 'OK' if semrepair['reconstruction_ok'] else 'FAIL'],
    ['UDP repair (drop every 7)', fmtn(udprepair['input_bytes']), f"{udprepair['semantic_misses']} / {udprepair['repair_full_frames']}", f"{udprepair['client_retransmissions']} retransmits", 'OK' if udprepair['reconstruction_ok'] else 'FAIL'],
    ['Authenticated UDP', fmtn(authudp['input_bytes']), f"{authudp['semantic_misses']} / {authudp['repair_full_frames']}", f"{authudp['tamper_probe_rejections']} tamper, {authudp['replay_probe_rejections']} replay", 'OK' if authudp['reconstruction_ok'] else 'FAIL'],
], widths=[1.8,1.0,1.2,1.6,0.7], font_size=8)

heading(doc,'12. Why Not Just Compress or Use rsync?',1)
para(doc,"Compression is best when repetition is local to one object; rsync is best when both endpoints share a file tree and can run a delta protocol; HTTP delta or shared-dictionary transport is best when the application is HTTP and a codec-level dictionary suffices; and whole-stream dictionary delta (zstd --patch-from, Section 7.6) is best on raw bytes whenever the receiver retains the exact prior stream - by one to three orders of magnitude on our corpora. The ReduLink use case is different: encrypted endpoint streams where dictionary state is already available at the receiver, the transfer is not naturally a file-tree synchronization session, and each reconstruction step must be individually authenticated and fail closed. The evaluation confirms the boundary. On source-release trees, rsync dominates (Table 7). On package metadata and logs, compression or fixed-block reuse dominates (Table 6). On object-aligned public releases and layer-like byte-stable objects (Tables 8 and 9), ReduLink provides authenticated reference substitution at modest overhead over a simple fixed-reference baseline.")
para(doc,"The motivating cases are therefore not arbitrary file synchronization. They are stream-serving cases in which the endpoint already knows that a receiver has dictionary state but must still authenticate every reconstruction step and preserve encrypted transport semantics. A CDN edge, registry, backup client, or enterprise service may choose this representation because it avoids exposing plaintext to a WAN optimizer and avoids changing the application protocol into a file-tree delta session, while keeping a stronger per-reference integrity guarantee than a codec-level shared dictionary provides.")
doc.add_page_break()
para(doc,"Table 26 consolidates the positioning without downgrading RFC 9842's protections. CDT has hashed dictionary identity, HTTPS origin/availability policy, and response discard on decoding failure. ReduLink differs by exposing individually bound chunk references and explicit semantic state repair outside HTTP content coding. The comparison is about granularity and serving abstraction, not about replacing QUIC/TLS integrity.")
tcap(doc,'Table 26. Positioning of ReduLink relative to related redundancy-suppression approaches.')
add_table(doc, ['Approach','E2E-encrypted transport','Per-reference auth','Fail-closed repair','Receiver dictionary','Best-fit workload'], [
    ['In-network RE [1-4]','No (needs plaintext vantage)','No','n/a','Network cache','High-redundancy unencrypted links'],
    ['rsync / LBFS [5]','Endpoints only','Transport integrity only','n/a (delta negotiation)','File/object index','File-tree synchronization'],
    ['HTTP CDT [19-22]','Yes (HTTPS / HTTP/3)','SHA-256 dictionary identity + TLS','Discard response on decoding failure','Eligible prior HTTP response','HTTP content coding with prior responses'],
    ['Local compression (gzip/zstd)','Yes','No','n/a','None (intra-object)','Locally repetitive single objects'],
    ['zstd dictionary delta (--patch-from) [26]','Yes (as payload)','No (codec trust)','No','Exact retained prior stream','Full prior stream retained; best byte savings (Sec. 7.6)'],
    ['ReduLink (this work)','Yes (QUIC streams)','Yes (per reference)','Yes (MISS then FULL)','Scoped warm dictionary','Warm-state object / layer transfers'],
], widths=[1.7,1.3,1.0,1.0,1.1,1.6], font_size=8)

heading(doc,'13. Limitations and Future Work',1)
para(doc,"The implementation is an application-stream mapping, uses server-only certificate authentication, and substitutes random exporter input because aioquic does not expose live TLS exporter bytes. The public and PyPI objects are transfer models rather than production traces. Userspace shaping is localhost evidence. The committed Linux netem data are concurrent legacy measurements with incomplete environment provenance; they do not support isolated kernel latency or a causal qdisc explanation. A corrected isolated runner is present but has not yet been rerun on Linux. The macOS dummynet path still times out. Bootstrap intervals describe within-run local variability only. Native experiments reach 16 MiB and expose dictionary-budget overflow, but multi-connection, Internet, migration, and larger-than-memory behavior remain out of scope. The formal argument assumes HMAC PRF/random-function behavior for truncation bounds and SHA-256 collision resistance; it is not machine checked. Model framing is optimistic, zstd 1.5.7 dictionary delta dominates where its assumptions hold, and absolute timings are host-dependent.")
para(doc,"Future work should integrate actual QUIC TLS exporter output, client/application authentication policy, custom frame negotiation if justified, isolated full-duplex kernel experiments with packet capture and complete provenance, production-style competing flows, larger live traces, broader miss-rate grids, machine-checked analysis, side-channel mitigation, and a true HTTP-level RFC 9842 comparison. The current zstd --patch-from baseline must remain labeled whole-stream dictionary delta, not CDT.")

heading(doc,'14. Reproducibility',1)
para(doc,"The package contains source, manifests, benchmark runners, result CSV/JSON, figures, citation checks, and tests [15]. Both python3 scripts/run_smoke_validation.py and python3 scripts/run_full_validation.py generate the gitignored deterministic target corpora before checking them, so they run from a clean clone. Full validation executes all tests; it validates committed network evidence but does not rerun privileged kernel experiments or download every external corpus. requirements-lock.txt pins Python packages. The Dockerfile additionally pins zstd 1.5.7 by source checksum and installs GNU rsync, iproute2/tc, and util-linux/taskset. The active builder is scripts/build_manuscript_v3_14.py. Framing JSON records zstd command/version and host provenance; the corrected netem runner records command, platform, Python, aioquic, tc, commit, and active qdisc. The v3.14 files are currently a reviewer-adapted candidate, not yet a public tag; MANUSCRIPT_SHA256.txt binds the local PDF/DOCX, and scripts/verify_public_release.py is intended for use after publication.")

heading(doc,'15. Conclusion',1)
para(doc,"ReduLink is best understood as authenticated, scoped reference substitution for encrypted endpoint streams. Its byte savings are conditional and are often reproduced or exceeded by simpler fixed-block reuse, compression, or rsync; the contribution is to make reference substitution explicit, individually authenticated, privacy-scoped, repairable, and compatible with native QUIC stream transport, and to position it precisely against both in-network redundancy elimination and HTTP shared-dictionary transport. The evidence supports ReduLink for warm-state object-aligned or layer-like transfers, while negative source-release results show where it should not be used.")

heading(doc,'Data and Code Availability',1)
para(doc,"All source code, public-corpus manifests, generated corpora, benchmark scripts, result CSV/JSON files, figures, the citation checker, public-release verifier, and the test suite are openly available in the ReduLink repository [15] under the MIT License. Every figure and table is regenerated from the committed result files, so the reported numbers can be reproduced from the artifact. Large external public-release corpora are reconstructed from documented public sources rather than redistributed.")

heading(doc,'References',1)
refs=[
"[1] N. T. Spring and D. Wetherall, 'A protocol-independent technique for eliminating redundant network traffic,' ACM SIGCOMM, 2000.",
"[2] A. Anand, V. Sekar, and A. Akella, 'SmartRE: An architecture for coordinated network-wide redundancy elimination,' ACM SIGCOMM, 2009.",
"[3] A. Anand et al., 'Redundancy in network traffic: Findings and implications,' ACM SIGMETRICS, 2009.",
"[4] B. Aggarwal et al., 'EndRE: An end-system redundancy elimination service for enterprises,' USENIX NSDI, 2010.",
"[5] A. Muthitacharoen, B. Chen, and D. Mazieres, 'A low-bandwidth network file system,' ACM SOSP, 2001.",
"[6] J. Iyengar and M. Thomson, 'QUIC: A UDP-based multiplexed and secure transport,' RFC 9000, IETF, 2021.",
"[7] M. Thomson and S. Turner, 'Using TLS to secure QUIC,' RFC 9001, IETF, 2021.",
"[8] J. Iyengar and I. Swett, 'QUIC loss detection and congestion control,' RFC 9002, IETF, 2021.",
"[9] M. Kuehlewind and B. Trammell, 'Applicability of the QUIC transport protocol,' RFC 9308, IETF, 2022.",
"[10] B. Trammell et al., 'Manageability of the QUIC transport protocol,' RFC 9312, IETF, 2022.",
"[11] W. Xia, X. Zou, Y. Zhou, H. Jiang, C. Liu, D. Feng, Y. Hua, Y. Hu, and Y. Zhang, 'The design of fast content-defined chunking for data deduplication based storage systems,' IEEE Transactions on Parallel and Distributed Systems, vol. 31, no. 9, 2020.",
"[12] M. Gregoriadis, L. Balduf, B. Scheuermann, and J. Pouwelse, 'A thorough investigation of content-defined chunking algorithms for data deduplication,' arXiv:2409.06066, 2024.",
"[13] B. Alexeev, C. Percival, and Y. X. Zhang, 'Chunking attacks on file backup services using content-defined chunking,' arXiv:2504.02095, 2025.",
"[14] IEEE 802.3 Ethernet Working Group, 'IEEE 802.3 Ethernet Working Group active projects,' accessed June 2026.",
"[15] M. Nguyen, 'ReduLink artifact and reproducibility package,' version 3.14 reviewer-adapted candidate, GitHub, 2026. https://github.com/pinkysworld/redulink-deduplex-quic",
"[16] D. Harnik, B. Pinkas, and A. Shulman-Peleg, 'Side channels in cloud services: Deduplication in cloud storage,' IEEE Security and Privacy, 2010.",
"[17] M. Bellare, S. Keelveedhi, and T. Ristenpart, 'DupLESS: Server-aided encryption for deduplicated storage,' USENIX Security, 2013.",
"[18] aioquic project contributors, 'aioquic: QUIC and HTTP/3 implementation in Python,' software repository, version 1.3.0, 2026. https://github.com/aiortc/aioquic",
"[19] J. Mogul, B. Krishnamurthy, F. Douglis, A. Feldmann, Y. Goland, A. van Hoff, and D. Hellerstein, 'Delta encoding in HTTP,' RFC 3229, IETF, 2002.",
"[20] D. Korn, J. MacDonald, J. Mogul, and K. Vo, 'The VCDIFF generic differencing and compression data format,' RFC 3284, IETF, 2002.",
"[21] J. Butler, W.-H. Lee, B. McQuade, and K. Mixter, 'A proposal for shared dictionary compression over HTTP (SDCH),' IETF Internet-Draft draft-lee-sdch-spec-00, 2016.",
"[22] P. Meenan and Y. Weiss, 'Compression dictionary transport,' RFC 9842, IETF, 2025.",
"[23] H. Krawczyk, M. Bellare, and R. Canetti, 'HMAC: Keyed-hashing for message authentication,' RFC 2104, IETF, 1997.",
"[24] H. Krawczyk and P. Eronen, 'HMAC-based extract-and-expand key derivation function (HKDF),' RFC 5869, IETF, 2010.",
"[25] R. Jain, D.-M. Chiu, and W. Hawe, 'A quantitative measure of fairness and discrimination for shared computer systems,' DEC Research Report TR-301, 1984.",
"[26] Y. Collet and M. Kucherawy, 'Zstandard compression and the application/zstd media type,' RFC 8878, IETF, 2021.",
]
for ref in refs:
    para(doc, ref, size=8, after=1)

OUT.parent.mkdir(parents=True, exist_ok=True)
doc.core_properties.author='Michél Nguyen'
doc.core_properties.last_modified_by='Michél Nguyen'
doc.core_properties.subject='ORCID: 0000-0001-6834-4422; University of the People'
doc.core_properties.comments='ReduLink journal-ready v3.14 reviewer-adapted candidate; ORCID: 0000-0001-6834-4422; University of the People'
doc.save(OUT)
print('saved', OUT)
