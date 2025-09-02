# registrations/views_flat.py
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.html import escape
from django.conf import settings
from django.db import connection
import datetime
import html
import urllib.parse

# --- Configuration ---
FEE_USD   = 45
FEE_CENTS = 4500

# Do NOT default to a “safe-local” advisor; new users shouldn’t see others’ rows
SAFE_DEFAULT_ADVISOR = ""

# ---------- DB helpers ----------

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
    Prefer existing app tables if present.
    If not, create ultra-simple fallback tables to avoid 500s:
      - registrations_pending_user_fallback
      - registrations_participant_fallback
    """
    pending_ok = _try_select("SELECT 1 FROM registrations_pendinguser LIMIT 1") is not None
    participant_ok = _try_select("SELECT 1 FROM registrations_participant LIMIT 1") is not None

    if not pending_ok:
        _try_exec(
            """
            CREATE TABLE IF NOT EXISTS registrations_pending_user_fallback (
                id SERIAL PRIMARY KEY,
                first_name TEXT NOT NULL,
                last_name  TEXT NOT NULL,
                email      TEXT NOT NULL UNIQUE,
                category   TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
    if not participant_ok:
        _try_exec(
            """
            CREATE TABLE IF NOT EXISTS registrations_participant_fallback (
                id SERIAL PRIMARY KEY,
                first_name TEXT NOT NULL,
                last_name  TEXT NOT NULL,
                student_organization TEXT,
                tee_shirt_size TEXT,
                college_company TEXT,
                tour TEXT,
                role TEXT,
                fee_cents INTEGER NOT NULL DEFAULT 4500,
                advisor_email TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
    return pending_ok, participant_ok


# ----- Row key helpers (works for either table) -----

def _rowkey(table_tag, row_id):
    # table_tag: 'p' for real participant table, 'pf' for fallback
    return f"{table_tag}:{row_id}"


def _parse_rowkey(rk):
    # returns (table_tag, id_int) or (None, None)
    try:
        tag, sid = (rk or "").split(":", 1)
        iid = int(sid)
        if tag in ("p", "pf"):
            return tag, iid
    except Exception:
        pass
    return None, None


def _fetch_participant_by_rowkey(rk):
    tag, iid = _parse_rowkey(rk)
    if not tag:
        return None
    if tag == "p":
        rows = _try_select(
            """
            SELECT id, first_name, last_name, student_organization, tee_shirt_size,
                   college_company, tour, role, fee_cents, advisor_email
            FROM registrations_participant
            WHERE id=%s
            """,
            [iid],
        )
        if rows:
            (rid, f, l, org, size, col, tour, role, fee, adv) = rows[0]
            return {
                "rowkey": _rowkey("p", rid),
                "first": f,
                "last": l,
                "org": org or "",
                "size": size or "",
                "college": col or "",
                "tour": tour or "",
                "role": role or "",
                "fee": fee or 0,
                "advisor": adv or "",
            }
    else:
        rows = _try_select(
            """
            SELECT id, first_name, last_name, student_organization, tee_shirt_size,
                   college_company, tour, role, fee_cents, advisor_email
            FROM registrations_participant_fallback
            WHERE id=%s
            """,
            [iid],
        )
        if rows:
            (rid, f, l, org, size, col, tour, role, fee, adv) = rows[0]
            return {
                "rowkey": _rowkey("pf", rid),
                "first": f,
                "last": l,
                "org": org or "",
                "size": size or "",
                "college": col or "",
                "tour": tour or "",
                "role": role or "",
                "fee": fee or 0,
                "advisor": adv or "",
            }
    return None


def _delete_participant(rk, advisor_email):
    tag, iid = _parse_rowkey(rk)
    if not tag:
        return False, "Bad row key"
    # Only allow delete if row belongs to this advisor
    if tag == "p":
        ok, msg = _try_exec(
            """
            DELETE FROM registrations_participant
            WHERE id=%s AND LOWER(advisor_email)=LOWER(%s)
            """,
            [iid, advisor_email],
        )
    else:
        ok, msg = _try_exec(
            """
            DELETE FROM registrations_participant_fallback
            WHERE id=%s AND LOWER(advisor_email)=LOWER(%s)
            """,
            [iid, advisor_email],
        )
    return ok, msg


def _update_participant(rk, first, last, org, size, college, tour, role, fee_cents, advisor_email):
    tag, iid = _parse_rowkey(rk)
    if not tag:
        return False, "Bad row key"
    if tag == "p":
        return _try_exec(
            """
            UPDATE registrations_participant
               SET first_name=%s, last_name=%s, student_organization=%s,
                   tee_shirt_size=%s, college_company=%s, tour=%s, role=%s, fee_cents=%s
             WHERE id=%s AND LOWER(advisor_email)=LOWER(%s)
            """,
            [first, last, org, size, college, tour, role, fee_cents, iid, advisor_email],
        )
    else:
        return _try_exec(
            """
            UPDATE registrations_participant_fallback
               SET first_name=%s, last_name=%s, student_organization=%s,
                   tee_shirt_size=%s, college_company=%s, tour=%s, role=%s, fee_cents=%s
             WHERE id=%s AND LOWER(advisor_email)=LOWER(%s)
            """,
            [first, last, org, size, college, tour, role, fee_cents, iid, advisor_email],
        )


def _insert_participant(first, last, org, size, college, tour, role, fee_cents, advisor_email):
    _, participant_ok = _ensure_flat_tables_if_missing()

    if participant_ok:
        ok, msg = _try_exec(
            """
            INSERT INTO registrations_participant
                (first_name, last_name, student_organization, tee_shirt_size,
                 college_company, tour, role, fee_cents, advisor_email)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            [first, last, org, size, college, tour, role, fee_cents, advisor_email],
        )
        if ok:
            return ok, msg

    # fallback
    return _try_exec(
        """
        INSERT INTO registrations_participant_fallback
            (first_name, last_name, student_organization, tee_shirt_size,
             college_company, tour, role, fee_cents, advisor_email)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        [first, last, org, size, college, tour, role, fee_cents, advisor_email],
    )

# ----- selectors -----

def _select_participants_for_advisor(advisor_email, limit=500):
    rows = _try_select(
        """
        SELECT 'p' AS tag, id, first_name, last_name, advisor_email,
               student_organization, tee_shirt_size, college_company, tour, role, fee_cents
        FROM registrations_participant
        WHERE LOWER(advisor_email)=LOWER(%s)
        ORDER BY created_at ASC, id ASC
        LIMIT %s
        """,
        [advisor_email, limit],
    )
    source = "registrations_participant"
    if rows is None:
        rows = _try_select(
            """
            SELECT 'pf' AS tag, id, first_name, last_name, advisor_email,
                   student_organization, tee_shirt_size, college_company, tour, role, fee_cents
            FROM registrations_participant_fallback
            WHERE LOWER(advisor_email)=LOWER(%s)
            ORDER BY created_at ASC, id ASC
            LIMIT %s
            """,
            [advisor_email, limit],
        )
        source = "registrations_participant_fallback" if rows is not None else None
    if not rows:
        return [], source
    out = []
    for (tag, iid, f, l, adv, org, size, col, tour, role, fee) in rows:
        out.append((_rowkey(tag, iid), f or "", l or "", adv or "", org or "", size or "", col or "", tour or "", role or "", int(fee or 0)))
    return out, source


def _select_participants_all(limit=2000):
    rows = _try_select(
        """
        SELECT 'p' AS tag, id, first_name, last_name, advisor_email,
               student_organization, tee_shirt_size, college_company, tour, role, fee_cents
        FROM registrations_participant
        ORDER BY created_at ASC, id ASC
        LIMIT %s
        """,
        [limit],
    )
    if rows is None:
        rows = _try_select(
            """
            SELECT 'pf' AS tag, id, first_name, last_name, advisor_email,
                   student_organization, tee_shirt_size, college_company, tour, role, fee_cents
            FROM registrations_participant_fallback
            ORDER BY created_at ASC, id ASC
            LIMIT %s
            """,
            [limit],
        )
    if not rows:
        return []
    out = []
    for (tag, iid, f, l, adv, org, size, col, tour, role, fee) in rows:
        out.append((_rowkey(tag, iid), f or "", l or "", adv or "", org or "", size or "", col or "", tour or "", role or "", int(fee or 0)))
    return out


# ----- tables & CSV -----

def _build_table_and_csv(rows):
    """
    rows: list of tuples (rowkey, first, last, advisor, org, size, college, tour, role, fee_cents)
    Returns (html_table, csv_text, count, total_dollars)
    """
    if not rows:
        # no table, but still return a CSV header (empty data)
        header = "First,Last,Advisor,Org,Size,College/Company,Tour,Role,Rate\n"
        return "", header, 0, 0

    items = []
    total_cents = 0
    for (rk, f, l, adv, org, size, col, tour, role, fee) in rows:
        total_cents += int(fee or 0)
        items.append(
            "<tr>"
            f"<td>{escape(f)}</td>"
            f"<td>{escape(l)}</td>"
            f"<td>{escape(adv)}</td>"
            f"<td>{escape(org)}</td>"
            f"<td>{escape(size)}</td>"
            f"<td>{escape(col)}</td>"
            f"<td>{escape(tour)}</td>"
            f"<td>{escape(role)}</td>"
            f"<td>$ {FEE_USD}</td>"
            "</tr>"
        )
    table_html = (
        "<table aria-label=\"Recently added participants\" class=\"recent-table\">"
        "<thead><tr>"
        "<th>First</th><th>Last</th><th>Advisor</th>"
        "<th>Org</th><th>Size</th><th>College/Company</th><th>Tour</th><th>Role</th><th>Rate</th>"
        "</tr></thead>"
        f"<tbody>{''.join(items)}</tbody>"
        "</table>"
    )

    # CSV
    lines = ["First,Last,Advisor,Org,Size,College/Company,Tour,Role,Rate"]
    for (_, f, l, adv, org, size, col, tour, role, fee) in rows:
        def q(x):
            x = (x or "").replace('"', '""')
            return f"\"{x}\""
        lines.append(",".join([
            q(f), q(l), q(adv), q(org), q(size), q(col), q(tour), q(role), f"\"$ {FEE_USD}\""
        ]))
    csv_text = "\n".join(lines) + "\n"
    return table_html, csv_text, len(rows), (total_cents // 100)


# ---------- HTML shell ----------

def _html_page(title, body):
    return HttpResponse(f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root {{ --gap: 12px; }}
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 1rem; }}
    .container {{ max-width: 980px; margin: 0 auto; }}
    .card {{ border: 1px solid #ddd; border-radius: 12px; padding: 1rem; margin: 1rem 0; }}
    .row {{ display: grid; grid-template-columns: 1fr 1fr; gap: var(--gap); }}
    .field {{ margin-bottom: .5em; }} /* requested .5em vertical spacing */
    label {{ display: block; font-weight: 600; margin-bottom: .25rem; }}
    input, select, button, a.button {{ width: 100%; padding: .6rem; border: 1px solid #bbb; border-radius: 8px; }}
    button, a.button {{ cursor: pointer; }}
    .sr-only {{ position: absolute; left: -9999px; top: auto; width: 1px; height: 1px; overflow: hidden; }}
    .success {{ background: #f0fff4; border-color: #a7f3d0; }}
    .warn {{ background: #fffaf0; border-color: #fde68a; }}
    .error {{ background: #fff5f5; border-color: #fecaca; }}
    .muted {{ color:#666; font-size:.9rem; }}

    .topbox {{ display:flex; align-items:center; justify-content:space-between; gap:1rem; }}
    .topbox-text {{ margin:0; }}

    .btn-primary {{ background:#2563EB; color:#fff; border:1px solid #1D4ED8; }}
    .btn-muted {{ background:#f2f2f2; border:1px solid #ddd; }}
    .btn-danger {{ background:#B91C1C; color:#fff; border:1px solid #991B1B; }}

    .recent-table {{ width:100%; border-collapse:collapse; font-size:.92rem; }}
    .recent-table th, .recent-table td {{ border-top:1px solid #eee; padding:.5rem .4rem; text-align:left; }}

    .actions form.inline {{ display:inline-block; margin:0 4px; }}
  </style>
</head>
<body>
  <a href="#main" class="sr-only">Skip to content</a>
  <main id="main" role="main" class="container" aria-labelledby="pageTitle">
    {body}
  </main>
</body>
</html>""", content_type="text/html")

# ---------- Views ----------

@csrf_exempt
def sanity_view(request):
    body = f"""
      <h1 id="pageTitle">Sanity Check</h1>
      <div class="card success" role="status" aria-live="polite">
        <p>OK {escape(datetime.datetime.utcnow().isoformat())}Z</p>
      </div>
      <div class="muted">/registrations/sanity/</div>
    """
    return _html_page("Sanity", body)


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
            ok, msg = _try_exec(
                """
                INSERT INTO registrations_pendinguser (first_name,last_name,email,category)
                VALUES (%s,%s,%s,%s)
                ON CONFLICT (email) DO NOTHING
                """,
                [first, last, email, category],
            )
            if not ok:
                ok, msg = _try_exec(
                    """
                    INSERT INTO registrations_pending_user_fallback (first_name,last_name,email,category)
                    VALUES (%s,%s,%s,%s)
                    ON CONFLICT (email) DO NOTHING
                    """,
                    [first, last, email, category],
                )
            post_status = ('<div class="card success" role="status">Seeded/ensured '
                           f'{escape(email)}</div>') if ok else (f'<div class="card error" role="alert">'
                           f'Could not seed {escape(email)}. {escape(msg)}</div>')

    rows = _try_select(
        "SELECT first_name,last_name,email,category FROM registrations_pendinguser ORDER BY created_at DESC NULLS LAST LIMIT 50"
    )
    source = "registrations_pendinguser"
    if rows is None:
        rows = _try_select(
            "SELECT first_name,last_name,email,category FROM registrations_pending_user_fallback ORDER BY created_at DESC LIMIT 50"
        )
        source = "registrations_pending_user_fallback" if rows is not None else None

    table_html = "<p class='muted'>No pending users.</p>"
    if rows:
        items = "".join(
            f"<tr><td>{escape(f)}</td><td>{escape(l)}</td><td>{escape(e)}</td><td>{escape(c)}</td></tr>"
            for (f, l, e, c) in rows
        )
        table_html = f"""
        <table aria-label="Pending users list" class="recent-table">
          <thead><tr>
            <th>First</th><th>Last</th><th>Email</th><th>Category</th>
          </tr></thead>
          <tbody>{items}</tbody>
        </table>
        <p class="muted">Source: {escape(source or 'unknown')}</p>
        """

    body = f"""
      <h1 id="pageTitle">Manage Pending Users</h1>
      {post_status}
      <form class="card" method="post" aria-label="Add Pending User">
        <div class="row">
          <div class="field"><label for="first_name">First Name</label><input id="first_name" name="first_name" required /></div>
          <div class="field"><label for="last_name">Last Name</label><input id="last_name" name="last_name" required /></div>
        </div>
        <div class="row">
          <div class="field"><label for="email">Email</label><input id="email" name="email" type="email" required /></div>
          <div class="field">
            <label for="category">Category</label>
            <select id="category" name="category" required>
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
          <button type="submit" class="btn-primary" aria-label="Add pending user">Add/Ensure</button>
        </div>
      </form>

      <div class="card" aria-live="polite">
        <h2 style="margin-top:0;">Recently Added</h2>
        {table_html}
      </div>
    """
    return _html_page("Manage Pending Users", body)


@csrf_exempt
def form_view(request):
    advisor_email_url = _safe_get(request.GET, "email", SAFE_DEFAULT_ADVISOR).strip().lower()
    editing_rowkey = _safe_get(request.GET, "edit", "").strip()

    status_block = ""
    summary_html = ""
    advisor_for_list = advisor_email_url

    # if editing via GET, prefill (only if advisor matches link)
    edit_data = _fetch_participant_by_rowkey(editing_rowkey) if editing_rowkey else None
    if edit_data and (not advisor_email_url or advisor_email_url != (edit_data.get("advisor") or "").lower()):
        edit_data = None
        status_block = '<div class="card warn" role="alert">Edit blocked: advisor mismatch. Use your advisor link.</div>'

    if request.method == "POST":
        # delete?
        delete_rowkey = _safe_get(request.POST, "delete_row").strip()
        if delete_rowkey:
            typed_advisor = _safe_get(request.POST, "advisor_email").strip().lower() or advisor_email_url
            ok, msg = _delete_participant(delete_rowkey, typed_advisor)
            status_block = ('<div class="card success" role="status">Participant deleted.</div>'
                            if ok else f'<div class="card error" role="alert">Delete failed: {escape(msg)}</div>')

        # finish summary?
        elif request.POST.get("finish"):
            admin_mode = _safe_get(request.GET, "all", "").lower() in ("1", "true", "yes")
            if admin_mode:
                rows = _select_participants_all(2000)
                report_tag = "ALL"
                advisor_label = "All participants"
            else:
                typed_adv = _safe_get(request.POST, "advisor_email").strip().lower()
                effective_adv = typed_adv or advisor_email_url
                if not (effective_adv and "@" in effective_adv):
                    status_block = '<div class="card warn" role="alert">Enter your advisor email, then press Finish.</div>'
                    rows, report_tag = [], "MISSING"
                    advisor_label = "Advisor: (missing)"
                else:
                    rows, _src = _select_participants_for_advisor(effective_adv, 500)
                    report_tag = effective_adv
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
                   href={"data:text/csv;charset=utf-8," + urllib.parse.quote(csv_text)}>Download CSV</a>
                <button type="button" class="btn-primary" style="width:auto;max-width:none;" onclick="window.print()">Print Summary</button>
              </div>
            </div>
            """
            return _html_page("Finish Summary", summary_html)

        # SHOW ENTRIES (no validation)
        elif request.POST.get("show_entries"):
            typed_advisor = _safe_get(request.POST, "advisor_email").strip().lower()
            advisor_for_list = typed_advisor or advisor_email_url
            if typed_advisor and "@" in typed_advisor:
                status_block = f'<div class="card success" role="status">Showing entries for {escape(typed_advisor)}</div>'
            else:
                status_block = '<div class="card warn" role="alert">Enter a valid advisor email to see previous entries.</div>'

        # SAVE / UPDATE
        else:
            first   = _safe_get(request.POST, "first_name").strip()
            last    = _safe_get(request.POST, "last_name").strip()
            org     = _safe_get(request.POST, "student_organization").strip()
            size    = _safe_get(request.POST, "tee_shirt_size").strip()
            college = _safe_get(request.POST, "college_company").strip()
            tour    = _safe_get(request.POST, "tour").strip()
            role    = _safe_get(request.POST, "role").strip()
            typed_advisor = _safe_get(request.POST, "advisor_email").strip().lower()
            advisor_for_list = typed_advisor or advisor_email_url

            if not (typed_advisor and "@" in typed_advisor):
                status_block = '<div class="card warn" role="alert">Advisor email is required for each entry.</div>'
            elif not first or not last:
                status_block = '<div class="card warn" role="alert">Please provide First and Last name.</div>'
            else:
                # Update if editing, else insert
                edit_rowkey = _safe_get(request.POST, "edit_row").strip()
                if edit_rowkey:
                    ok, msg = _update_participant(edit_rowkey, first, last, org, size, college, tour, role, FEE_CENTS, typed_advisor)
                else:
                    ok, msg = _insert_participant(first, last, org, size, college, tour, role, FEE_CENTS, typed_advisor)

                status_block = (
                    f'<div class="card success" role="status" aria-live="polite">Saved {escape(first)} {escape(last)} (fee $ {FEE_USD})</div>'
                    if ok else f'<div class="card error" role="alert">DB write failed. Details: {escape(msg)}</div>'
                )

    # Build advisor-scoped table (only if we have an advisor)
    rows = []
    if advisor_for_list:
        rows, source = _select_participants_for_advisor(advisor_for_list, limit=200)
    else:
        source = None

    # Live estimate (top box)
    advisor_count = len(rows) if rows else 0
    total_est = FEE_USD * advisor_count

    top_box = f"""
      <div class="card warn topbox" role="note">
        <p class="topbox-text"><strong>Estimated total:</strong> $ {FEE_USD} × {advisor_count} = $ {total_est}</p>
        <div></div>
        <button type="submit" form="flcform" name="finish" value="1"
                class="btn-primary" style="max-width:260px;" formnovalidate
                aria-label="Finish">Finish</button>
      </div>
    """

    # Prefill for edit mode
    ef   = (edit_data or {}).get("first", "") if edit_data else ""
    el   = (edit_data or {}).get("last", "") if edit_data else ""
    eorg = (edit_data or {}).get("org", "") if edit_data else ""
    esize= (edit_data or {}).get("size", "") if edit_data else ""
    ecol = (edit_data or {}).get("college", "") if edit_data else ""
    etour= (edit_data or {}).get("tour", "") if edit_data else ""
    erole= (edit_data or {}).get("role", "") if edit_data else ""
    eadv = (edit_data or {}).get("advisor", "") if edit_data else advisor_for_list
    erow = (edit_data or {}).get("rowkey", "") if edit_data else ""

    def _sel(cur, opt):
        return " selected" if (cur or "") == opt else ""

    # Build recent table with actions (only if rows)
    table_html = ""
    if rows:
        items = []
        for (rk, f, l, adv, org, size, col, tour, role, fee) in rows:
            items.append(
                "<tr>"
                f"<td>{escape(f)}</td>"
                f"<td>{escape(l)}</td>"
                f"<td>{escape(adv)}</td>"
                f"<td>{escape(org)}</td>"
                f"<td>{escape(size)}</td>"
                f"<td>{escape(col)}</td>"
                f"<td>{escape(tour)}</td>"
                f"<td>{escape(role)}</td>"
                f"<td>$ {FEE_USD}</td>"
                "<td class='actions'>"
                "<form class='inline' method='get'>"
                f"  <input type='hidden' name='email' value='{escape(adv)}'/>"
                f"  <input type='hidden' name='edit' value='{escape(rk)}'/>"
                "  <button type='submit' class='btn-muted' aria-label='Edit'>Edit</button>"
                "</form>"
                "<form class='inline' method='post'>"
                f"  <input type='hidden' name='advisor_email' value='{escape(adv)}'/>"
                f"  <input type='hidden' name='delete_row' value='{escape(rk)}'/>"
                "  <button type='submit' class='btn-danger' aria-label='Delete'>Delete</button>"
                "</form>"
                "</td>"
                "</tr>"
            )
        table_html = (
            "<table aria-label=\"Recently added participants\" class=\"recent-table\">"
            "<thead><tr>"
            "<th>First</th><th>Last</th><th>Advisor</th>"
            "<th>Org</th><th>Size</th><th>College/Company</th><th>Tour</th><th>Role</th><th>Rate</th><th>Actions</th>"
            "</tr></thead>"
            f"<tbody>{''.join(items)}</tbody>"
            "</table>"
        )

    # Advisor input help
    placeholder_advisor = "Advisor email (required to view/save)"

    body = f"""
      <h1 id="pageTitle">Fall Leadership Conference Registration</h1>

      {top_box}
      {status_block}
      {summary_html}

      <form id="flcform" class="card" method="post" aria-label="Participant add form">
        <input type="hidden" name="edit_row" value="{escape(erow)}" />

        <div class="row" role="group" aria-label="Row 1">
          <div class="field">
            <label for="first_name">First Name</label>
            <input id="first_name" name="first_name" value="{escape(ef)}" required aria-required="true" style="max-width:22rem;"/>
          </div>
          <div class="field">
            <label for="last_name">Last Name</label>
            <input id="last_name" name="last_name" value="{escape(el)}" required aria-required="true" style="max-width:22rem;" />
          </div>
        </div>

        <div class="row" role="group" aria-label="Row 2">
          <div class="field">
            <label for="student_organization">Student Organization</label>
            <select id="student_organization" name="student_organization">
              <option value="">(select)</option>
              <option{_sel(eorg,'DECA')}>DECA</option>
              <option{_sel(eorg,'FBLA')}>FBLA</option>
              <option{_sel(eorg,'SkillsUSA')}>SkillsUSA</option>
              <option{_sel(eorg,'HOSA')}>HOSA</option>
              <option{_sel(eorg,'Mississippi Postsecondary Student Organization')}>Mississippi Postsecondary Student Organization</option>
            </select>
          </div>
          <div class="field">
            <label for="tee_shirt_size">T-Shirt Size</label>
            <select id="tee_shirt_size" name="tee_shirt_size">
              <option value="">(select)</option>
              <option{_sel(esize,'XSmall')}>XSmall</option>
              <option{_sel(esize,'Small')}>Small</option>
              <option{_sel(esize,'Medium')}>Medium</option>
              <option{_sel(esize,'Large')}>Large</option>
              <option{_sel(esize,'XLarge')}>XLarge</option>
              <option{_sel(esize,'2XLarge')}>2XLarge</option>
              <option{_sel(esize,'3XLarge')}>3XLarge</option>
              <option{_sel(esize,'4XLarge')}>4XLarge</option>
            </select>
          </div>
        </div>

        <div class="row" role="group" aria-label="Row 3">
          <div class="field">
            <label for="college_company">College/Chapter</label>
            <select id="college_company" name="college_company">
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
          <div class="field">
            <label for="tour">Tour</label>
            <select id="tour" name="tour">
              <option value="">(select)</option>
              <option{_sel(etour,'Haley Barbour Center for Manufacturing Excellence')}>Haley Barbour Center for Manufacturing Excellence</option>
              <option{_sel(etour,'The Jim and Thomas Duff Center for Science and Technology Innovation')}>The Jim and Thomas Duff Center for Science and Technology Innovation</option>
              <option{_sel(etour,'No Tour')}>No Tour</option>
            </select>
          </div>
        </div>

        <div class="row" role="group" aria-label="Row 4">
          <div class="field">
            <label for="role">Role</label>
            <select id="role" name="role">
              <option value="">(select)</option>
              <option{_sel(erole,'Advisor')}>Advisor</option>
              <option{_sel(erole,'Student')}>Student</option>
              <option{_sel(erole,'Other')}>Other</option>
            </select>
          </div>
          <div class="field">
            <label for="advisor_email">Advisor Email <span class="muted">required to view or save</span></label>
            <input id="advisor_email" name="advisor_email" placeholder="{escape(placeholder_advisor)}" value="{escape(eadv)}" style="max-width:26rem;" />
          </div>
        </div>

        <!-- Actions -->
        <div class="actions-row" style="display:flex; gap:.5rem; flex-wrap:wrap; margin-top:12px;">
          <button type="submit" name="save" value="1" class="btn-primary" aria-label="Save participant">
            Save Participant
          </button>

          <button type="submit" name="show_entries" value="1"
                  class="btn-muted"
                  form="flcform" formnovalidate
                  aria-label="Enter email to see previous entries">
            Enter email to see previous entries
          </button>

          <button type="submit" name="finish" value="1"
                  class="btn-primary"
                  form="flcform" formnovalidate
                  aria-label="Finish">
            Finish
          </button>
        </div>
      </form>

      <div class="card" aria-live="polite">
        <h2 style="margin-top:0;">Recently Added Participants</h2>
        {table_html}
        <p class="muted">To see Edit/Delete take effect, refresh the page after saving.</p>
        <p><a class="btn-muted" href="/registrations/form/">Reload form</a></p>
      </div>
    """
    return _html_page("Fall Leadership Conference Registration", body)
