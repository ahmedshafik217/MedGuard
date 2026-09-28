"""A small, hand-drawn set of inline SVG line icons -- replaces the emoji
that used to sit inside every icon-badge/feature chip/button label across
the app. Emoji render as a different colored picture per operating system
(and can't pick up the icon-badge's own accent color), which is what made
the UI feel inconsistent/less polished next to the hospital's own AmanBio
design mockup -- these render as a single-color stroke path via
`stroke="currentColor"`, so each icon automatically matches whatever color
the surrounding .icon-badge/.theme-* class already sets, exactly like the
mockup's own icon system.

Usage in a template: {{ icon('pill') }} -- see the `icon` Jinja global
registered in app/__init__.py. Every icon shares the same 24x24 viewBox and
2px rounded stroke, and is rendered at `width/height: 1em` (see style.css),
so it automatically scales with whatever font-size its container already
has (an .icon-badge, a button, a small pill-badge, ...) with no extra sizing
arguments needed.
"""
from markupsafe import Markup

# Each value is the INNER content of a 24x24 viewBox <svg> (no outer tag).
# Kept to simple primitives (line/circle/rect/polyline/path-with-straight-
# or-arc-segments) rather than freehand bezier curves, both so they're easy
# to review/tweak by eye and so nothing here resembles any specific existing
# icon set's exact artwork -- these are generic geometric line-icon shapes.
_ICONS = {
    "plus": '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
    "x": '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
    "check": '<polyline points="4,13 9,18 20,6"/>',
    "check-circle": '<circle cx="12" cy="12" r="9"/><polyline points="8,12.5 11,15.5 16,9"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4,20 C4,15.6 7.6,13 12,13 C16.4,13 20,15.6 20,20"/>',
    "users": ('<circle cx="9" cy="8" r="3.2"/><path d="M3,20 C3,16.4 5.7,14 9,14 C12.3,14 15,16.4 15,20"/>'
               '<circle cx="17" cy="9.5" r="2.6"/><path d="M15.3,14.3 C17.9,14.7 19.7,16.7 19.7,20"/>'),
    "pill": ('<rect x="3" y="9" width="18" height="6" rx="3" transform="rotate(-40 12 12)"/>'
              '<line x1="12" y1="7.5" x2="12" y2="16.5" transform="rotate(-40 12 12)"/>'),
    "clipboard-list": ('<rect x="5" y="4" width="14" height="17" rx="2"/>'
                        '<rect x="9" y="2" width="6" height="4" rx="1"/>'
                        '<line x1="8" y1="11" x2="16" y2="11"/><line x1="8" y1="15" x2="16" y2="15"/>'
                        '<line x1="8" y1="19" x2="13" y2="19"/>'),
    "shield-alert": ('<path d="M12,3 L19,6 V11 C19,16 16,19.5 12,21 C8,19.5 5,16 5,11 V6 Z"/>'
                      '<line x1="12" y1="8" x2="12" y2="13"/>'
                      '<circle cx="12" cy="16.2" r="0.9" fill="currentColor" stroke="none"/>'),
    "clock": '<circle cx="12" cy="12" r="9"/><line x1="12" y1="7" x2="12" y2="12"/><line x1="12" y1="12" x2="15.5" y2="14"/>',
    "search": '<circle cx="10.5" cy="10.5" r="6.5"/><line x1="15.5" y1="15.5" x2="20" y2="20"/>',
    "id-badge": ('<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="11" r="2.2"/>'
                 '<line x1="6.3" y1="16.2" x2="11.7" y2="16.2"/>'
                 '<line x1="14" y1="9" x2="18" y2="9"/><line x1="14" y1="12.5" x2="18" y2="12.5"/>'),
    "alert-triangle": ('<path d="M12,3 L22,20 H2 Z"/><line x1="12" y1="9" x2="12" y2="14"/>'
                        '<circle cx="12" cy="17" r="0.9" fill="currentColor" stroke="none"/>'),
    "bandage": ('<rect x="3" y="8" width="18" height="8" rx="4" transform="rotate(-35 12 12)"/>'
                '<circle cx="8.3" cy="10" r="1" fill="currentColor" stroke="none" transform="rotate(-35 12 12)"/>'
                '<circle cx="15.7" cy="14" r="1" fill="currentColor" stroke="none" transform="rotate(-35 12 12)"/>'),
    "building": ('<rect x="4" y="3" width="16" height="18" rx="1"/>'
                 '<line x1="12" y1="8" x2="12" y2="14"/><line x1="9" y1="11" x2="15" y2="11"/>'
                 '<line x1="8" y1="21" x2="8" y2="18"/><line x1="16" y1="21" x2="16" y2="18"/>'),
    "camera": ('<path d="M4,8 H7 L8.5,6 H15.5 L17,8 H20 A1,1 0 0 1 21,9 V19 A1,1 0 0 1 20,20 H4 '
               'A1,1 0 0 1 3,19 V9 A1,1 0 0 1 4,8 Z"/><circle cx="12" cy="14" r="3.5"/>'),
    "mic": ('<rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5,11 A7,7 0 0 0 19,11"/>'
            '<line x1="12" y1="18" x2="12" y2="22"/><line x1="8" y1="22" x2="16" y2="22"/>'),
    "flask": ('<path d="M10,3 H14 M10,3 V9 L5,19 A1,1 0 0 0 6,20.5 H18 A1,1 0 0 0 19,19 L14,9 V3"/>'
              '<line x1="8" y1="15" x2="16" y2="15"/>'),
    "qr-code": ('<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>'
                '<rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="3" height="3"/>'
                '<rect x="18" y="18" width="3" height="3"/><rect x="14" y="18" width="1.4" height="1.4"/>'
                '<rect x="18" y="14" width="1.4" height="1.4"/>'),
    "file-text": ('<path d="M6,2 H14 L19,7 V22 H6 Z"/><path d="M14,2 V7 H19"/>'
                  '<line x1="8.5" y1="12" x2="15.5" y2="12"/><line x1="8.5" y1="16" x2="15.5" y2="16"/>'),
    "inbox": ('<path d="M3,13 H8 L10,16 H14 L16,13 H21"/>'
              '<path d="M5.5,5 H18.5 L21,13 V19 A1,1 0 0 1 20,20 H4 A1,1 0 0 1 3,19 V13 Z"/>'),
    "link": ('<path d="M9,15 L15,9"/><path d="M11,7 L13,5 A3.5,3.5 0 0 1 18,10 L16,12"/>'
             '<path d="M13,17 L11,19 A3.5,3.5 0 0 1 6,14 L8,12"/>'),
    "history": ('<rect x="4" y="4" width="16" height="16" rx="2"/>'
                '<line x1="8" y1="9" x2="16" y2="9"/><line x1="8" y1="13" x2="16" y2="13"/>'
                '<line x1="8" y1="17" x2="13" y2="17"/>'),
    "settings": ('<line x1="4" y1="6" x2="20" y2="6"/><circle cx="9" cy="6" r="2"/>'
                 '<line x1="4" y1="12" x2="20" y2="12"/><circle cx="16" cy="12" r="2"/>'
                 '<line x1="4" y1="18" x2="20" y2="18"/><circle cx="10" cy="18" r="2"/>'),
    "house": '<path d="M4,11 L12,4 L20,11 V20 H4 Z"/><rect x="9.5" y="14" width="5" height="7"/>',
    "lock": ('<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8,11 V7 A4,4 0 0 1 16,7 V11"/>'
             '<line x1="12" y1="15" x2="12" y2="17"/>'),
    "printer": '<path d="M7,9 V3 H17 V9"/><rect x="4" y="9" width="16" height="8" rx="1"/><rect x="7" y="14" width="10" height="7"/>',
    "phone": ('<path d="M6,3 H9 L11,8 L8.5,10 A12,12 0 0 0 15,16.5 L17,14 L22,16 V19 '
              'A2,2 0 0 1 19.8,21 A17,17 0 0 1 4,5.2 A2,2 0 0 1 6,3 Z"/>'),
    "chevron": '<polyline points="9,5 16,12 9,19"/>',
    "ban": '<circle cx="12" cy="12" r="9"/><line x1="5.8" y1="18.2" x2="18.2" y2="5.8"/>',
    "info": ('<circle cx="12" cy="12" r="9"/><line x1="12" y1="11" x2="12" y2="16"/>'
              '<circle cx="12" cy="7.5" r="0.9" fill="currentColor" stroke="none"/>'),
    "hourglass": ('<line x1="6" y1="3" x2="18" y2="3"/><line x1="6" y1="21" x2="18" y2="21"/>'
                  '<path d="M7,3 C7,9 11,10.5 12,12 C13,10.5 17,9 17,3"/>'
                  '<path d="M7,21 C7,15 11,13.5 12,12 C13,13.5 17,15 17,21"/>'),
    "stethoscope": ('<path d="M6,3 V10 A4,4 0 0 0 14,10 V3"/><line x1="6" y1="3" x2="4.5" y2="3"/>'
                     '<line x1="14" y1="3" x2="15.5" y2="3"/><path d="M10,14 V16 A5,5 0 0 0 20,16 V14"/>'
                     '<circle cx="20" cy="12.3" r="1.7"/>'),
}


def render_icon(name, css_class=None):
    """Returns a Markup-safe inline <svg> for the given icon name (see
    _ICONS above). Falls back to a plain circle if an unknown name is ever
    passed, so a typo shows up as an odd little dot in testing rather than
    silently swallowing the whole page render."""
    inner = _ICONS.get(name, '<circle cx="12" cy="12" r="8"/>')
    cls = f' class="{css_class}"' if css_class else ""
    return Markup(
        f'<svg{cls} viewBox="0 0 24 24" width="1em" height="1em" fill="none" '
        f'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
        f'stroke-linejoin="round" aria-hidden="true" focusable="false">{inner}</svg>'
    )
