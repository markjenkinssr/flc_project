from django.http import HttpResponse
import urllib.parse
from django.views.decorators.csrf import csrf_exempt
from django.utils.html import escape
from django.conf import settings
from django.db import connection

import datetime, html, io, csv, urllib.parse

# No default advisor: show nothing unless provided
SAFE_DEFAULT_ADVISOR = ""  # require explicit advisor
FEE_USD = 45
FEE_CENTS = FEE_USD * 100

def _html_page(title: str, body: str) -> HttpResponse:
    return HttpResponse(f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root {{ --gap:12px; --radius:12px; --border:#ddd; --muted:#666; --primary:#2563eb; --ring:#93c5fd; }}
    * {{ box-sizing: border-box; }}
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 1.1rem; }}
    .container {{ max-width: 1040px; margin: 0 auto; padding: .25rem; }}
    .card {{ border: 1px solid var(--border); border-radius: var(--radius); padding: 1rem; margin: .9rem 0; }}
    .row {{ display: grid; grid-template-columns: 1fr 1fr; gap: var(--gap); align-items: start; }}
    .row > div {{ display: flex; flex-direction: column; }}
    @media (max-width: 760px) {{ .row {{ grid-template-columns: 1fr; }} }}
    label {{ display: block; font-weight: 600; margin: 0 0 .35rem; }}
    input, select, button, textarea {{ width: 100%; padding: .65rem .75rem; border: 1px solid #bbb; border-radius: 10px; }}
    input[readonly] {{ background: #f7f7f7; }}
    input:focus, select:focus, button:focus, textarea:focus {{ outline: 2px solid var(--ring); outline-offset: 2px; }}
    button {{ cursor: pointer; font-weight: 700; }}
    .btn-primary {{ background: var(--primary); color: #fff; border-color: transparent; }}
    .btn-left {{ width: 100%; max-width: 360px; }}
    .btn-danger {{ background:#b91c1c; color:#fff; border-color:transparent; }}
    .btn-muted {{ background:#e5e7eb; color:#111; border-color:transparent; }}
    .success {{ background: #f0fff4; border-color: #a7f3d0; }}
    .warn {{ background: #fffaf0; border-color: #fde68a; }}
    .error {{ background: #fff5f5; border-color: #fecaca; }}
    .muted {{ color: var(--muted); font-size: .9rem; }}
    table {{ width:100%; border-collapse: collapse; }}
    th, td {{ text-align:left; padding:8px 10px; border-bottom:1px solid #eee; vertical-align: top; }}
    thead th {{ background: #f7f7f7; }}
    tbody tr:nth-child(odd) td {{ background:#fafafa; }}
    .print-actions {{ display:flex; gap:12px; margin:.5rem 0 0; }}
    .topbox {{ display:flex; align-items:center; gap:12px; }}
    .topbox-text {{ margin:0; color:#333; }}
    .topbox-spacer {{ margin-left:auto; }}
    .btn-finish {{ width:360px; max-width:50%; }}
    form.inline {{ display:inline; margin:0; }}
    .actions {{ white-space:nowrap; display:flex; gap:8px; }}
    /* space between form rows */
    form.card .row + .row {{ margin-top: .5rem; }}
  </style>
</head>
<body>
  <main id="main" role="main" class="container" aria-labelledby="pageTitle">
    {body}
  </main>
</body>
</html>""", content_type="text/html")

def _safe_get(d, k, default=""):
    try:
        v = d.get(k, default)
        return v if v is not None else default
    except Exception:
        return default

def _try_select(sql, params=None):
    try:
        with connection.cursor() as cur:
            cur.execute(sql, params or [])
            return cur.fetchall()
    except Exception:
        return None

def _try_exec(sql, params=None):
    try:
        with connection.cursor() as cur:
            cur.execute(sql, params or [])
        return True, ""
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

def _ensure_flat_tables_if_missing():
    """
    Prefer real app tables if present; always ensure fallback tables/columns exist.
    """
    pending_ok = _try_select("SELECT 1 FROM registrations_pendinguser LIMIT 1") is not None
    participant_ok = _try_select("SELECT 1 FROM registrations_participant LIMIT 1") is not None

    _try_exec("""
        CREATE TABLE IF NOT EXISTS registrations_pending_user_fallback (
            id SERIAL PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name  TEXT NOT NULL,
            email      TEXT NOT NULL UNIQUE,
            category   TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    _try_exec("""
        CREATE TABLE IF NOT EXISTS registrations_participant_fallback (
            id SERIAL PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name  TEXT NOT NULL,
            student_organization TEXT,
            tee_shirt_size TEXT,
            college_company TEXT,
            tour TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    # Ensure newer columns exist (idempotent)
    def _ensure_col(table, col, ddl):
        got = _try_select(
            "SELECT 1 FROM information_schema.columns WHERE table_name=%s AND column_name=%s LIMIT 1;",
            [table, col],
        )
        if not got:
            _try_exec(ddl)

    _ensure_col("registrations_participant_fallback", "dietary_restrictions",
                "ALTER TABLE registrations_participant_fallback ADD COLUMN dietary_restrictions TEXT;")
    _ensure_col("registrations_participant_fallback", "ada",
                "ALTER TABLE registrations_participant_fallback ADD COLUMN ada TEXT;")
    _ensure_col("registrations_participant_fallback", "fee_cents",
                "ALTER TABLE registrations_participant_fallback ADD COLUMN fee_cents INTEGER;")
    _ensure_col("registrations_participant_fallback", "advisor_email",
                "ALTER TABLE registrations_participant_fallback ADD COLUMN advisor_email TEXT;")

    return pending_ok, participant_ok

# ---------- Edit/Delete helpers ----------

def _build_table_and_csv(rows):
    """
    rows: list of either 8-tuple (f,l,a,org,sz,col,tr,rate)
          or 9-tuple (rk,f,l,a,org,sz,col,tr,rate)
    Returns: (html_table, csv_text, count, total_dollars)
    """
    out = []
    csv_lines = ["First,Last,Advisor,Organization,Size,College/Company,Tour,Rate"]
    count = 0
    for tup in rows or []:
        if isinstance(tup, (list, tuple)) and len(tup) == 9:
            _, f, l, a, org, sz, col, tr, rate = tup
        else:
            f, l, a, org, sz, col, tr, rate = tup
        rate = int(rate) if str(rate).isdigit() else FEE_USD
        out.append(
            "<tr>"
            f"<td>{escape(f)}</td><td>{escape(l)}</td><td>{escape(a)}</td>"
            f"<td>{escape(org or '')}</td><td>{escape(sz or '')}</td>"
            f"<td>{escape(col or '')}</td><td>{escape(tr or '')}</td>"
            f"<td>$ {rate}</td>"
            "</tr>"
        )
        csv_lines.append(",".join([
            f.replace(","," "), l.replace(","," "), a.replace(","," "),
            (org or "").replace(","," "), (sz or "").replace(","," "),
            (col or "").replace(","," "), (tr or "").replace(","," "),
            str(rate)
        ]))
        count += 1
    total = FEE_USD * count
    table = (
        "<table aria-label='Summary' style='font-size:.92rem;'>"
        "<thead><tr>"
        "<th>First</th><th>Last</th><th>Advisor</th><th>Org</th>"
        "<th>Size</th><th>College/Company</th><th>Tour</th><th>Rate</th>"
        "</tr></thead>"
        f"<tbody>{''.join(out) or '<tr><td colspan=8 class=muted>None</td></tr>'}</tbody>"
        f"<tfoot><tr><td colspan=8 class='muted'>Total: $ {total}</td></tr></tfoot>"
        "</table>"
    )
    return table, "\n".join(csv_lines) + "\n", count, total


def _select_participants_for_advisor(advisor_email, limit=50):
    """Returns rows with a stable rowkey so we can Edit/Delete safely."""
    if not advisor_email:
        return []
    # Try real table
    rows = _try_select("""
      SELECT 'p:'||id AS rk, first_name, last_name, advisor_email,
             COALESCE(student_organization,''), COALESCE(tee_shirt_size,''), COALESCE(college_company,''), COALESCE(tour,''),
             (fee_cents/100)
      FROM registrations_participant
      WHERE LOWER(advisor_email)=LOWER(%s)
      ORDER BY created_at ASC, id ASC
      LIMIT %s
    """, [advisor_email, limit])
    if rows is not None:
        return rows

    # Fallback
    rows = _try_select("""
      SELECT 'pf:'||id AS rk, first_name, last_name, advisor_email,
             COALESCE(student_organization,''), COALESCE(tee_shirt_size,''), COALESCE(college_company,''), COALESCE(tour,''),
             (fee_cents/100)
      FROM registrations_participant_fallback
      WHERE LOWER(advisor_email)=LOWER(%s)
      ORDER BY created_at ASC, id ASC
      LIMIT %s
    """, [advisor_email, limit])
    return rows or []


def _select_participants_all(limit=2000):
    rows = _try_select("""
      SELECT 'p:'||id AS rk, first_name, last_name, advisor_email,
             COALESCE(student_organization,''), COALESCE(tee_shirt_size,''), COALESCE(college_company,''), COALESCE(tour,''),
             (fee_cents/100)
      FROM registrations_participant
      ORDER BY created_at ASC, id ASC
      LIMIT %s
    """, [limit])
    if rows is not None:
        return rows
    rows = _try_select("""
      SELECT 'pf:'||id AS rk, first_name, last_name, advisor_email,
             COALESCE(student_organization,''), COALESCE(tee_shirt_size,''), COALESCE(college_company,''), COALESCE(tour,''),
             (fee_cents/100)
      FROM registrations_participant_fallback
      ORDER BY created_at ASC, id ASC
      LIMIT %s
    """, [limit])
    return rows or []


def _parse_rowkey(rk):
    """Returns ('p' or 'pf', integer id)."""
    if not rk or ':' not in rk:
        return None, None
    prefix, sid = rk.split(':', 1)
    try:
        return prefix, int(sid)
    except Exception:
        return None, None


def _delete_participant(rowkey, advisor_email):
    prefix, sid = _parse_rowkey(rowkey)
    if not sid or not advisor_email:
        return False, "bad rowkey/advisor"
    if prefix == 'p':
        return _try_exec(
            "DELETE FROM registrations_participant WHERE id=%s AND LOWER(advisor_email)=LOWER(%s)",
            [sid, advisor_email]
        )
    elif prefix == 'pf':
        return _try_exec(
            "DELETE FROM registrations_participant_fallback WHERE id=%s AND LOWER(advisor_email)=LOWER(%s)",
            [sid, advisor_email]
        )
    return False, "unknown table prefix"


def _fetch_participant_by_rowkey(rowkey):
    prefix, sid = _parse_rowkey(rowkey)
    if not sid:
        return None
    if prefix == 'p':
        rows = _try_select("""
          SELECT first_name,last_name,advisor_email,student_organization,tee_shirt_size,college_company,tour
          FROM registrations_participant WHERE id=%s
        """,[sid])
    else:
        rows = _try_select("""
          SELECT first_name,last_name,advisor_email,student_organization,tee_shirt_size,college_company,tour
          FROM registrations_participant_fallback WHERE id=%s
        """,[sid])
    if not rows:
        return None
    f,l,a,org,sz,col,tr = rows[0]
    return {"first":f,"last":l,"advisor":a,"org":org,"size":sz,"college":col,"tour":tr}


def _rowkey(src_char, pid):
    return f"{src_char}:{int(pid)}"  # src_char = 'p' or 'f'

def _parse_rowkey(s):
    try:
        src, sid = (s or "").split(":", 1)
        sid = int(sid)
        if src in ("p", "f"):
            return src, sid
    except Exception:
        pass
    return None, None

def _fetch_participant_by_rowkey(rowkey):
    src, pid = _parse_rowkey(rowkey)
    if not pid:
        return None
    if src == "p":
        row = _try_select("""SELECT id, first_name,last_name,student_organization,tee_shirt_size,college_company,tour,fee_cents,advisor_email
                             FROM registrations_participant WHERE id=%s LIMIT 1;""", [pid])
    else:
        row = _try_select("""SELECT id, first_name,last_name,student_organization,tee_shirt_size,college_company,tour,fee_cents,advisor_email,
                                    dietary_restrictions, ada
                             FROM registrations_participant_fallback WHERE id=%s LIMIT 1;""", [pid])
    if not row:
        return None
    if src == "p":
        (rid, f, l, org, sz, col, tr, fee, adv) = row[0]
        return {"src":"p","id":rid,"first":f,"last":l,"org":org,"size":sz,"college":col,"tour":tr,"fee":fee,"advisor":(adv or "")}
    else:
        (rid, f, l, org, sz, col, tr, fee, adv, diet, ada) = row[0]
        return {"src":"f","id":rid,"first":f,"last":l,"org":org,"size":sz,"college":col,"tour":tr,"fee":fee,"advisor":(adv or ""),"dietary":(diet or ""),"ada":(ada or "")}

def _update_participant(rowkey, guard_advisor, first, last, org, size, college, tour, dietary, ada, advisor_new):
    # Only allow if the row's advisor matches the current advisor (typed or URL)
    data = _fetch_participant_by_rowkey(rowkey)
    if not data:
        return False, "Row not found"
    if not (guard_advisor and guard_advisor == (data.get("advisor") or "")):
        return False, "Advisor mismatch"
    if data["src"] == "p":
        # primary table doesn't have dietary/ada in this app
        return _try_exec("""UPDATE registrations_participant
                            SET first_name=%s,last_name=%s,student_organization=%s,tee_shirt_size=%s,
                                college_company=%s,tour=%s,advisor_email=%s
                            WHERE id=%s AND advisor_email=%s;""",
                         [first,last,org,size,college,tour,advisor_new,data["id"],guard_advisor])
    else:
        return _try_exec("""UPDATE registrations_participant_fallback
                            SET first_name=%s,last_name=%s,student_organization=%s,tee_shirt_size=%s,
                                college_company=%s,tour=%s,dietary_restrictions=%s,ada=%s,advisor_email=%s
                            WHERE id=%s AND advisor_email=%s;""",
                         [first,last,org,size,college,tour,dietary,ada,advisor_new,data["id"],guard_advisor])

def _delete_participant(rowkey, guard_advisor):
    data = _fetch_participant_by_rowkey(rowkey)
    if not data:
        return False, "Row not found"
    if not (guard_advisor and guard_advisor == (data.get("advisor") or "")):
        return False, "Advisor mismatch"
    if data["src"] == "p":
        return _try_exec("DELETE FROM registrations_participant WHERE id=%s AND advisor_email=%s;", [data["id"], guard_advisor])
    else:
        return _try_exec("DELETE FROM registrations_participant_fallback WHERE id=%s AND advisor_email=%s;", [data["id"], guard_advisor])

# ---------- Query/build helpers ----------

def _select_participants_for_advisor(advisor_email, limit=200):
    if not (advisor_email and "@" in advisor_email):
        return []
    real = _try_select("""SELECT 'p' as src, id, first_name,last_name,advisor_email,student_organization,tee_shirt_size,college_company,tour,created_at
        FROM registrations_participant
        WHERE advisor_email=%s
        ORDER BY created_at DESC NULLS LAST, id DESC LIMIT %s;""", [advisor_email, limit]) or []
    fb = _try_select("""SELECT 'f' as src, id, first_name,last_name,advisor_email,student_organization,tee_shirt_size,college_company,tour,created_at
        FROM registrations_participant_fallback
        WHERE advisor_email=%s
        ORDER BY created_at DESC, id DESC LIMIT %s;""", [advisor_email, limit]) or []
    rows = real + fb
    rows.sort(key=lambda r: (r[-1] or datetime.datetime.min))  # oldest → newest
    rate = f"$ {FEE_USD}"
    # return tuples including rowkey for actions
    return [(_rowkey(src, pid), f, l, a, org, sz, col, tr, rate) for (src, pid, f, l, a, org, sz, col, tr, _) in rows]

def _select_participants_all(limit=2000):
    real = _try_select("""SELECT 'p' as src, id, first_name,last_name,advisor_email,student_organization,tee_shirt_size,college_company,tour,created_at
                          FROM registrations_participant
                          ORDER BY created_at DESC NULLS LAST, id DESC LIMIT %s;""", [limit]) or []
    fb   = _try_select("""SELECT 'f' as src, id, first_name,last_name,advisor_email,student_organization,tee_shirt_size,college_company,tour,created_at
                          FROM registrations_participant_fallback
                          ORDER BY created_at DESC, id DESC LIMIT %s;""", [limit]) or []
    rows = real + fb
    rows.sort(key=lambda r: (r[-1] or datetime.datetime.min))
    rate = f"$ {FEE_USD}"
    return [(_rowkey(src, pid), f, l, a, org, sz, col, tr, rate) for (src, pid, f, l, a, org, sz, col, tr, _) in rows]

def _build_table_and_csv(rows):
    buf = io.StringIO()
    cw = csv.writer(buf)
    cw.writerow(["First","Last","Advisor","Org","Size","College/Company","Tour","Rate"])
    for (_, f,l,a,org,sz,col,tr,rate) in rows: cw.writerow([f,l,a,org,sz,col,tr,rate])
    csv_text = buf.getvalue()

    if rows:
        items = "".join(
            f"<tr><td>{escape(f)}</td><td>{escape(l)}</td><td>{escape(a)}</td>"
            f"<td>{escape(org or '')}</td><td>{escape(sz or '')}</td><td>{escape(col or '')}</td>"
            f"<td>{escape(tr or '')}</td><td>{escape(rate)}</td></tr>"
            for (_, f,l,a,org,sz,col,tr,rate) in rows
        )
        table_html = f"""
        <table aria-label="Participants (sorted oldest→newest)">
          <thead><tr>
            <th>First</th><th>Last</th><th>Advisor</th>
            <th>Org</th><th>Size</th><th>College/Company</th><th>Tour</th><th>Rate</th>
          </tr></thead>
          <tbody>{items}</tbody>
          <tfoot><tr><td colspan="8" class="muted">Total participants: {len(rows)} · Total fees: $ {len(rows)*FEE_USD}</td></tr></tfoot>
        </table>
        """
    else:
        table_html = "<p class='muted'>No participants found.</p>"

    return table_html, csv_text, len(rows), len(rows)*FEE_USD

def _send_admin_email(subject, html_body, csv_text, to_addr="studentorgs@mccb.edu"):
    # Email disabled (stub) to avoid runtime failures
    return True, "(email disabled)"

def _insert_pending_user(first, last, email, category):
    pending_ok, _ = _ensure_flat_tables_if_missing()
    if pending_ok:
        return _try_exec("""INSERT INTO registrations_pendinguser
            (first_name,last_name,email,category) VALUES (%s,%s,%s,%s)
            ON CONFLICT (email) DO NOTHING;""", [first,last,email,category])
    return _try_exec("""INSERT INTO registrations_pending_user_fallback
        (first_name,last_name,email,category) VALUES (%s,%s,%s,%s)
        ON CONFLICT (email) DO NOTHING;""", [first,last,email,category])

def _insert_participant(first, last, org, size, college, tour, dietary, ada, fee_cents, advisor_email):
    _, participant_ok = _ensure_flat_tables_if_missing()
    if participant_ok:
        ok, msg = _try_exec("""INSERT INTO registrations_participant
            (first_name,last_name,student_organization,tee_shirt_size,college_company,tour,fee_cents,advisor_email)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s);""",
            [first,last,org,size,college,tour,fee_cents,advisor_email])
        if ok:
            return ok, msg
    return _try_exec("""INSERT INTO registrations_participant_fallback
        (first_name,last_name,student_organization,tee_shirt_size,college_company,tour,dietary_restrictions,ada,fee_cents,advisor_email)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);""",
        [first,last,org,size,college,tour,dietary,ada,fee_cents,advisor_email])

@csrf_exempt
def sanity_view(request):
    body = f"""
      <h1 id="pageTitle">Sanity Check</h1>
      <div class="card success" role="status" aria-live="polite">
        <p>OK {escape(datetime.datetime.utcnow().isoformat())}Z</p>
      </div>
    """
    return _html_page("Sanity", body)

@csrf_exempt
def form_view(request):
    advisor_email_url = _safe_get(request.GET, "email", "").strip().lower()

    status_block = ""
    summary_html = ""
    advisor_for_list = advisor_email_url  # which advisor’s rows to show

    if request.method == "POST":
        # 1) DELETE comes first so it doesn't fall through to finish/save
        delete_rowkey = _safe_get(request.POST, "delete_row").strip()
        if delete_rowkey:
            typed_advisor = _safe_get(request.POST, "advisor_email").strip().lower() or advisor_email_url
            ok, msg = _delete_participant(delete_rowkey, typed_advisor)
            status_block = (
                '<div class="card success" role="status">Participant deleted.</div>'
                if ok else f'<div class="card error" role="alert">Delete failed: {escape(msg)}</div>'
            )
            # after a delete, show that advisor's updated list
            advisor_for_list = typed_advisor or advisor_email_url

        # 2) FINISH summary (typed advisor preferred; fallback to URL ?email=...)
        elif request.POST.get("finish"):
            admin_mode = _safe_get(request.GET, "all", "").lower() in ("1", "true", "yes")
            if admin_mode:
                rows = _select_participants_all(2000)
                advisor_label = "All participants"
            else:
                typed_adv = _safe_get(request.POST, "advisor_email").strip().lower()
                effective_adv = typed_adv or advisor_email_url
                if not (effective_adv and "@" in effective_adv):
                    status_block = '<div class="card warn" role="alert">Enter your advisor email, then press Finish.</div>'
                    rows = []
                    advisor_label = "Advisor: (missing)"
                else:
                    rows = _select_participants_for_advisor(effective_adv, 500)
                    advisor_label = f"Advisor: {escape(effective_adv)}"

            table_html, csv_text, cnt, total = _build_table_and_csv(rows)
            summary_html = f"""
            <div class="card success" role="region" aria-label="Finish summary">
              <h2 style="margin-top:0;">Summary (print this for your records)</h2>
              <p class="muted topbox-text">{advisor_label} · Count: {cnt} · Total: $ {total}</p>
              {table_html}
              <div class="print-actions">
                <a class="btn-primary" style="display:inline-block;padding:.6rem .9rem;border-radius:10px;text-decoration:none;"
                   download="flc_summary.csv"
                   href={{"data:text/csv;charset=utf-8," + urllib.parse.quote(csv_text)}}>Download CSV</a>
                <button type="button" class="btn-primary" style="width:auto;max-width:none;" onclick="window.print()">Print Summary</button>
              </div>
            </div>
            """

        # 3) SAVE / SHOW ENTRIES (normal flow)
        else:
            first   = _safe_get(request.POST, "first_name").strip()
            last    = _safe_get(request.POST, "last_name").strip()
            org     = _safe_get(request.POST, "student_organization").strip()
            size    = _safe_get(request.POST, "tee_shirt_size").strip()
            college = _safe_get(request.POST, "college_company").strip()
            tour    = _safe_get(request.POST, "tour").strip()
            dietary = _safe_get(request.POST, "dietary_restrictions").strip()
            ada     = _safe_get(request.POST, "ada").strip()
            role    = _safe_get(request.POST, "role").strip()  # read-only for now
            typed_advisor = _safe_get(request.POST, "advisor_email").strip().lower()

            # whose list to show after POST
            advisor_for_list = typed_advisor or advisor_email_url

            # Just show previous entries (no validation)
            if request.POST.get("show_entries"):
                if typed_advisor and "@" in typed_advisor:
                    status_block = f'<div class="card success" role="status">Showing entries for {escape(typed_advisor)}</div>'
                else:
                    status_block = '<div class="card warn" role="alert">Enter a valid advisor email to see previous entries.</div>'

            # Insert a new participant
            else:
                if not (typed_advisor and "@" in typed_advisor):
                    status_block = '<div class="card warn" role="alert">Advisor email is required for each entry.</div>'
                elif not first or not last:
                    status_block = '<div class="card warn" role="alert">Please provide First and Last name.</div>'
                else:
                    ok, msg = _insert_participant(
                        first, last, org, size, college, tour, dietary, ada, FEE_CENTS, typed_advisor
                    )
                    status_block = (
                        f'<div class="card success" role="status" aria-live="polite">Saved {escape(first)} {escape(last)} (fee $ {FEE_USD})</div>'
                        if ok else f'<div class="card error" role="alert">DB write failed. Details: {escape(msg)}</div>'
                    )


    # Build advisor-scoped table (simple & stable; supports 8- or 9-tuples)
    rows = _select_participants_for_advisor(advisor_for_list, limit=50) if advisor_for_list else []

    if not rows:
        part_html = "<p class='muted'>No participants found.</p>"
    else:
        body_rows = []
        for tup in rows:
            # 9-tuple with rowkey
            rk, f, l, a, org, sz, col, tr, rate = tup
            body_rows.append(
                "<tr>"
                f"<td>{escape(f)}</td><td>{escape(l)}</td><td>{escape(a)}</td>"
                f"<td>{escape(org or '')}</td><td>{escape(sz or '')}</td>"
                f"<td>{escape(col or '')}</td><td>{escape(tr or '')}</td>"
                f"<td>$ {FEE_USD}</td>"
                "<td class='actions'>"
                "<form class='inline' method='get' style='display:inline-block;margin:0 4px;'>"
                f"  <input type='hidden' name='email' value='{escape(advisor_for_list or '')}'/>"
                f"  <input type='hidden' name='edit' value='{escape(rk)}'/>"
                "  <button type='submit' class='btn-muted' aria-label='Edit'>Edit</button>"
                "</form>"
                "<form class='inline' method='post' style='display:inline-block;margin:0 4px;'>"
                f"  <input type='hidden' name='advisor_email' value='{escape(advisor_for_list or '')}'/>"
                f"  <input type='hidden' name='delete_row' value='{escape(rk)}'/>"
                "  <button type='submit' class='btn-danger' aria-label='Delete'>Delete</button>"
                "</form>"
                "</td>"
                "</tr>"
            )

        part_html = f"""
        <table aria-label="Recently added participants" style="font-size:.92rem;">
          <thead>
            <tr>
              <th>First</th><th>Last</th><th>Advisor</th>
              <th>Org</th><th>Size</th><th>College/Company</th><th>Tour</th><th>Rate</th><th>Actions</th>
            </tr>
          </thead>
          <tbody>{''.join(body_rows)}</tbody>
          <tfoot><tr><td colspan="9" class="muted">Oldest at top, newest at bottom</td></tr></tfoot>
        </table>
        """


    # Live estimate banner
    advisor_count = len(rows) if rows else 0
    total_est = FEE_USD * advisor_count
    top_box = f"""
      <div class="card warn topbox" role="note">
        <p class="topbox-text"><strong>Estimated total:</strong> $ {FEE_USD} x {advisor_count} = $ {total_est}</p>
        <div class="topbox-spacer"></div>
        <button type="submit" form="flcform" name="finish" value="1"
                class="btn-primary btn-finish" aria-label="Finish">Finish</button>
      </div>
    """

    # Prefill (no edit mode right now)
    ef = el = eorg = esize = ecol = etour = ediet = eada = erole = ""
    eadv = advisor_for_list

    def _sel(cur, opt):
        return ' selected' if (cur or '') == opt else ''

    body = f"""
      <h1 id="pageTitle">Fall Leadership Conference Registration</h1>

      {top_box}
      {status_block}
      {summary_html}

      <form id="flcform" class="card" method="post" aria-label="Participant add form">

        <!-- Row 1 -->
        <div class="row">
          <div><label for="first_name">First Name</label><input id="first_name" name="first_name" value="{escape(ef)}" required aria-required="true" /></div>
          <div><label for="last_name">Last Name</label><input id="last_name" name="last_name" value="{escape(el)}" required aria-required="true" /></div>
        </div>

        <!-- Row 2 -->
        <div class="row">
          <div>
            <label for="student_organization">Student Organization</label>
            <select id="student_organization" name="student_organization" aria-label="Student Organization">
              <option value="">(select)</option>
              <option{_sel(eorg,'DECA')}>DECA</option><option{_sel(eorg,'FBLA')}>FBLA</option>
              <option{_sel(eorg,'SkillsUSA')}>SkillsUSA</option><option{_sel(eorg,'HOSA')}>HOSA</option>
              <option{_sel(eorg,'Mississippi Postsecondary Student Organization')}>Mississippi Postsecondary Student Organization</option>
            </select>
          </div>
          <div>
            <label for="tee_shirt_size">T-Shirt Size</label>
            <select id="tee_shirt_size" name="tee_shirt_size" aria-label="Tee Shirt Size">
              <option value="">(select)</option>
              <option{_sel(esize,'XSmall')}>XSmall</option><option{_sel(esize,'Small')}>Small</option>
              <option{_sel(esize,'Medium')}>Medium</option><option{_sel(esize,'Large')}>Large</option>
              <option{_sel(esize,'XLarge')}>XLarge</option><option{_sel(esize,'2XLarge')}>2XLarge</option>
              <option{_sel(esize,'3XLarge')}>3XLarge</option><option{_sel(esize,'4XLarge')}>4XLarge</option>
            </select>
          </div>
        </div>

        <!-- Row 3 -->
        <div class="row">
          <div>
            <label for="college_company">College/Chapter</label>
            <select id="college_company" name="college_company" aria-label="College or Company">
              <option value="">(select)</option>
              <option{_sel(ecol,'Coahoma Community College')}>Coahoma Community College</option>
              <option{_sel(ecol,'Copiah-Lincoln Community College')}>Copiah-Lincoln Community College</option>
              <option{_sel(ecol,'Delta State University')}>Delta State University</option>
              <option{_sel(ecol,'East Central Community College')}>East Central Community College</option>
              <option{_sel(ecol,'East Mississippi Community College - Mayhew')}>East Mississippi Community College - Mayhew</option>
              <option{_sel(ecol,'East Mississippi Community College - Scooba')}>East Mississippi Community College - Scooba</option>
              <option{_sel(ecol,'Hinds Community College - Raymond')}>Hinds Community College - Raymond</option>
              <option{_sel(ecol,'Hinds Community College - Utica')}>Hinds Community College - Utica</option>
              <option{_sel(ecol,'Holmes Community College')}>Holmes Community College</option>
              <option{_sel(ecol,'Jones College')}>Jones College</option>
              <option{_sel(ecol,'Mississippi Delta Community College')}>Mississippi Delta Community College</option>
              <option{_sel(ecol,'Mississippi Gulf Coast Community College - Harrison')}>Mississippi Gulf Coast Community College - Harrison</option>
              <option{_sel(ecol,'Mississippi State University College of Business')}>Mississippi State University College of Business</option>
              <option{_sel(ecol,'Mississippi University for Women')}>Mississippi University for Women</option>
              <option{_sel(ecol,'Northeast Mississippi Community College')}>Northeast Mississippi Community College</option>
              <option{_sel(ecol,'Southwest Mississippi Community College')}>Southwest Mississippi Community College</option>
              <option{_sel(ecol,'Tougaloo College')}>Tougaloo College</option>
              <option{_sel(ecol,'University of Mississippi - Desoto')}>University of Mississippi - Desoto</option>
              <option{_sel(ecol,'Mississippi Community College Board')}>Mississippi Community College Board</option>
              <option{_sel(ecol,'Other')}>Other</option>
            </select>
          </div>
          <div>
            <label for="tour">Tour</label>
            <select id="tour" name="tour" aria-label="Tour selection">
              <option value="">(select)</option>
              <option{_sel(etour,'Haley Barbour Center for Manufacturing Excellence')}>Haley Barbour Center for Manufacturing Excellence</option>
              <option{_sel(etour,'The Jim and Thomas Duff Center for Science and Technology Innovation')}>The Jim and Thomas Duff Center for Science and Technology Innovation</option>
              <option{_sel(etour,'No Tour')}>No Tour</option>
            </select>
          </div>
        </div>

        <!-- Row 4 -->
        <div class="row">
          <div>
            <label for="dietary_restrictions">Dietary Restrictions</label>
            <input id="dietary_restrictions" name="dietary_restrictions" value="{escape(ediet)}" placeholder="e.g., vegetarian, gluten-free" />
          </div>
          <div>
            <label for="ada">ADA Accommodations</label>
            <input id="ada" name="ada" value="{escape(eada)}" placeholder="e.g., mobility assistance, interpreter" />
          </div>
        </div>

        <!-- Row 5 (Role + Advisor Email) -->
        <div class="row">
          <div>
            <label for="role">Role</label>
            <select id="role" name="role" aria-label="Role">
              <option value="">(select)</option>
              <option{_sel(erole,'Advisor')}>Advisor</option>
              <option{_sel(erole,'Student')}>Student</option>
              <option{_sel(erole,'Other')}>Other</option>
            </select>
          </div>
          <div>
            <label for="advisor_email">Advisor Email</label>
            <input id="advisor_email" name="advisor_email" value="{escape(eadv)}"
                   placeholder="Advisor email REQUIRED for each entry." required />
          </div>
        </div>

        <div style="margin-top:8px; display:flex; gap:12px; flex-wrap:wrap;">
          <button type="submit" class="btn-primary btn-left" aria-label="Save participant">Save Participant</button>
          <button type="submit" name="show_entries" value="1" formnovalidate aria-label="Show previous entries">
            Enter email to see previous entries
          </button>
        </div>
      </form>

      <div class="card" aria-live="polite">
        <h2 style="margin-top:0;">Recently Added Participants</h2>
        {part_html}
      </div>
    """
    return _html_page("Fall Leadership Conference Registration", body)



@csrf_exempt
def manage_pending_users_view(request):
    post_status = ""
    if request.method == "POST":
        first = _safe_get(request.POST, "first_name").strip()
        last = _safe_get(request.POST, "last_name").strip()
        email = _safe_get(request.POST, "email").strip().lower()
        category = _safe_get(request.POST, "category").strip()
        if not (first and last and email and category):
            post_status = '<div class="card warn" role="alert">All fields are required.</div>'
        else:
            ok, msg = _insert_pending_user(first, last, email, category)
            post_status = (f'<div class="card success" role="status" aria-live="polite">Seeded/ensured {escape(email)}</div>'
                           if ok else f'<div class="card error" role="alert">Could not seed {escape(email)}. Details: {escape(msg)}</div>')

    rows = _try_select("""SELECT first_name,last_name,email,category
                          FROM registrations_pendinguser
                          ORDER BY created_at DESC NULLS LAST LIMIT 50;""")
    if rows is None:
        rows = _try_select("""SELECT first_name,last_name,email,category
                              FROM registrations_pending_user_fallback
                              ORDER BY created_at DESC LIMIT 50;""")

    table_html = "<p class='muted'>No pending users found (or DB unavailable).</p>"
    if rows:
        items = "".join(f"<tr><td>{escape(f)}</td><td>{escape(l)}</td><td>{escape(e)}</td><td>{escape(c)}</td></tr>"
                        for (f,l,e,c) in rows)
        table_html = f"""
        <table aria-label="Pending users list">
          <thead><tr><th>First</th><th>Last</th><th>Email</th><th>Category</th></tr></thead>
          <tbody>{items}</tbody>
        </table>
        """

    body = f"""
      <h1 id="pageTitle">Manage Pending Users</h1>
      {post_status}
      <form class="card" method="post" aria-label="Add Pending User">
        <div class="row">
          <div><label for="first_name">First Name</label><input id="first_name" name="first_name" required aria-required="true" /></div>
          <div><label for="last_name">Last Name</label><input id="last_name" name="last_name" required aria-required="true" /></div>
        </div>
        <div class="row">
          <div><label for="email">Email</label><input id="email" name="email" type="email" required aria-required="true" /></div>
          <div>
            <label for="category">Category</label>
            <select id="category" name="category" required aria-required="true">
              <option value="">(select)</option>
              <option>Mississippi Community College Board</option>
              <option>Advisor</option>
              <option>Vendor</option>
              <option>Speaker</option>
              <option>Guest</option>
              <option>Other</option>
            </select>
          </div>
        </div>
        <div style="margin-top:12px;">
          <button type="submit" class="btn-primary btn-left" aria-label="Add pending user">Add/Ensure</button>
        </div>
      </form>

      <div class="card" aria-live="polite">
        <h2 style="margin-top:0;">Recently Added</h2>
        {table_html}
      </div>
    """
    return _html_page("Manage Pending Users", body)
