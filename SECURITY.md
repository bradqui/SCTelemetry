# Security

Please report security problems privately, through a [GitHub security advisory](https://github.com/bradqui/starglance/security/advisories/new), not in a public issue. You'll get an answer within a few days.

Useful to include: what's affected (agent, hub or page), the version, and how to reproduce it.

What's in scope:

- **The agent:** its local page must only answer this PC (the opt-in *Show on other devices* server answers paired devices only, and only with the view: no settings, no sign-in links, nothing that reaches the game), it must never send to anything but the game and the hub you linked (updates only download an official release from this project's GitHub, and are checked before they're installed), and it must never make a path from the network into the game.
- **The hub:** sign-in, sessions, invites, linked PCs' keys, the API keys and the members' data it holds.
- **Release builds:** an exe that wasn't built from this repository, or a signing problem. See [docs/CODE_SIGNING.md](docs/CODE_SIGNING.md).

Only the latest release is supported. Hubs and agents should be updated together.
