# Starglance brand

The Starglance logo, in the Deep Space colours: ice cyan wings and diamond, an amber star, on an ink-blue ground. **The logo isn't MIT**: see [LICENSE](LICENSE) for what you may do with it.

## Colours and type

| | |
|---|---|
| Cyan (lead) | `#5fd4e8`, also the embed colour for bot and webhook posts |
| Amber (star) | `#f0b45c` |
| Ground | `#0e131a` |
| On white | `#0b7f97` cyan, `#a8661a` amber ([masters/starglance-wings-on-light.svg](masters/starglance-wings-on-light.svg)) |

Headings and the wordmark use Chakra Petch; text uses IBM Plex Sans. Both are free on Google Fonts.

## Files

- `masters/`: vector masters: on dark, on light, all white, and the icon tile.
- `site/link-preview-1200x630.png`: a branded link preview, if the docs site ever wants one (today it previews with a cockpit screenshot).
- `discord/`: the Discord server's art, below.

### Discord: day one (no boosts needed)

| File | Where it goes |
|---|---|
| `discord/server-icon-512.png` | Server Settings → Overview → Server icon |
| `discord/release-bot-avatar-512.png` | the #releases webhook or bot avatar |
| `discord/emoji/*.png` (128 × 128) | Server Settings → Emoji; the file name is the emoji name: `:starglance:` `:o7:` `:qt:` `:landed:` `:gforce:` `:stale:` `:fleet:` |
| `discord/welcome-header-1200x400.png` | posted at the top of #welcome |
| `discord/rules-header-1200x400.png` | posted at the top of #rules |

### Discord: needs boosts

| File | Where it goes |
|---|---|
| `discord/invite-background-1920x1080.png` | level 1 (2 boosts): Server Settings → Overview → Invite background |
| `discord/server-banner-960x540.png` | level 2 (7 boosts): Server Settings → Overview → Banner |
| `discord/role-icons/*.png` (64 × 64) | level 2: Server Settings → Roles → (role) → Role icon: developer, tester, hub-host, member |

## Rebuilding

[brand-export.cjs](brand-export.cjs) draws every file here. From the repo root, with `site/` and `web/` npm-installed:

```
node brand/brand-export.cjs
```

It writes into `brand/` (or the folder you give it). The logo also lives in the app and the docs site; change them together:

- `web/src/components/Logo.svelte`, which takes its colours from the app's theme;
- `web/index.html` (the favicon);
- `site/public/logo.svg`, `logo-light.svg` and `favicon.svg`;
- `draw_icon` in `agent/starglance/app.py`: the exe and tray icon.
