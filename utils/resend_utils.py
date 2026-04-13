"""
utils/resend_utils.py
Monthly recap email via Resend.

Env vars:
    RESEND_API_KEY      — from resend.com dashboard
    RESEND_FROM_EMAIL   — verified sender, e.g. "Game Tracker <noreply@yourdomain.com>"
    NEXT_PUBLIC_APP_URL — used for CTA and footer links
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)


def _client():
    import resend
    resend.api_key = os.getenv("RESEND_API_KEY", "")
    return resend


def _app_url() -> str:
    return os.getenv("NEXT_PUBLIC_APP_URL", "https://video-game-stats-tracker.vercel.app")


def _build_html(stats: dict, month_label: str) -> str:
    gold    = "#D4AF37"
    surface = "#1a1a1a"
    border  = "#2d2d2d"
    muted   = "#9ca3af"
    text    = "#f3f4f6"
    app_url = _app_url()

    mau               = stats.get("mau", 0)
    total_sessions    = stats.get("total_sessions", 0)
    top_game          = stats.get("top_game", "N/A")
    top_game_sessions = stats.get("top_game_sessions", 0)
    player_of_month   = stats.get("player_of_month", "N/A")
    player_sessions   = stats.get("player_sessions", 0)
    new_users         = stats.get("new_users", 0)
    total_users       = stats.get("total_users", 0)

    def stat_row(label: str, value: str) -> str:
        return f"""
        <tr>
          <td style="padding:10px 16px;color:{muted};font-size:13px;
                     border-bottom:1px solid {border};">{label}</td>
          <td style="padding:10px 16px;color:{text};font-size:13px;font-weight:600;
                     text-align:right;border-bottom:1px solid {border};">{value}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>Game Tracker — {month_label} Recap</title>
</head>
<body style="margin:0;padding:0;background:#111111;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0"
         style="background:#111111;padding:32px 16px;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0"
             style="max-width:560px;width:100%;">

        <!-- Header -->
        <tr>
          <td style="background:{surface};border:1px solid {border};
                     border-radius:12px 12px 0 0;padding:28px 32px;text-align:center;">
            <div style="font-size:28px;margin-bottom:8px;">🎮</div>
            <h1 style="margin:0;color:{gold};font-size:22px;font-weight:700;
                       letter-spacing:0.5px;">
              {month_label} Community Recap
            </h1>
            <p style="margin:6px 0 0;color:{muted};font-size:13px;">
              Here's what the Game Tracker community was up to last month.
            </p>
          </td>
        </tr>

        <!-- Stats table -->
        <tr>
          <td style="background:{surface};border-left:1px solid {border};
                     border-right:1px solid {border};padding:0;">
            <table width="100%" cellpadding="0" cellspacing="0">
              {stat_row("Monthly Active Users", f"{mau:,}")}
              {stat_row("Sessions Submitted", f"{total_sessions:,}")}
              {stat_row("New Members This Month", f"+{new_users:,}")}
              {stat_row("Total Community Members", f"{total_users:,}")}
            </table>
          </td>
        </tr>

        <!-- Highlights -->
        <tr>
          <td style="background:{surface};border-left:1px solid {border};
                     border-right:1px solid {border};padding:20px 32px;">

            <div style="background:{border};border-radius:10px;
                        padding:16px 20px;margin-bottom:12px;">
              <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;
                          color:{muted};margin-bottom:6px;">
                🏆 Top Game of the Month
              </div>
              <div style="font-size:18px;font-weight:700;color:{gold};">{top_game}</div>
              <div style="font-size:12px;color:{muted};margin-top:2px;">
                {top_game_sessions:,} sessions played
              </div>
            </div>

            <div style="background:{border};border-radius:10px;padding:16px 20px;">
              <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;
                          color:{muted};margin-bottom:6px;">
                🥇 Player of the Month
              </div>
              <div style="font-size:18px;font-weight:700;color:{text};">
                {player_of_month}
              </div>
              <div style="font-size:12px;color:{muted};margin-top:2px;">
                {player_sessions:,} sessions submitted
              </div>
            </div>

          </td>
        </tr>

        <!-- CTA -->
        <tr>
          <td style="background:{surface};border-left:1px solid {border};
                     border-right:1px solid {border};padding:20px 32px;text-align:center;">
            <a href="{app_url}/leaderboard"
               style="display:inline-block;background:{gold};color:#000;font-weight:700;
                      font-size:14px;padding:12px 28px;border-radius:8px;
                      text-decoration:none;">
              View Leaderboard →
            </a>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:{surface};border:1px solid {border};
                     border-radius:0 0 12px 12px;padding:20px 32px;text-align:center;">
            <p style="margin:0 0 6px;color:{muted};font-size:12px;">
              This is an automated email — please do not reply.
            </p>
            <p style="margin:0 0 8px;color:{muted};font-size:12px;">
              You're receiving this because you opted in to monthly recaps.
            </p>
            <p style="margin:0;font-size:12px;">
              <a href="{app_url}/account"
                 style="color:{gold};text-decoration:none;">
                Manage email preferences
              </a>
              &nbsp;·&nbsp;
              <a href="{app_url}"
                 style="color:{muted};text-decoration:none;">
                Game Tracker
              </a>
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def send_monthly_recap(recipients: list[str], stats: dict, month_label: str) -> dict:
    """
    Send the monthly recap to a list of opted-in addresses.
    Returns {"sent": N, "failed": N}.
    Fails silently per recipient — one bad address won't stop the rest.
    """
    api_key = os.getenv("RESEND_API_KEY", "")
    if not api_key:
        log.warning("[resend] RESEND_API_KEY not set — skipping.")
        return {"sent": 0, "failed": 0, "skipped": True}

    if not recipients:
        log.info("[resend] No opted-in recipients — nothing to send.")
        return {"sent": 0, "failed": 0}

    resend     = _client()
    from_email = os.getenv("RESEND_FROM_EMAIL", "Game Tracker <noreply@resend.dev>")
    subject    = f"🎮 Game Tracker — {month_label} Community Recap"
    html       = _build_html(stats, month_label)

    sent = failed = 0
    for email in recipients:
        try:
            resend.Emails.send({
                "from":    from_email,
                "to":      [email],
                "subject": subject,
                "html":    html,
            })
            sent += 1
            log.info(f"[resend] Sent to {email}")
        except Exception as e:
            failed += 1
            log.error(f"[resend] Failed for {email}: {e}")

    log.info(f"[resend] Monthly recap complete — sent={sent}, failed={failed}")
    return {"sent": sent, "failed": failed}
