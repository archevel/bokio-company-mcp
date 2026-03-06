# Bokio Company MCP Server

MCP server that exposes the [Bokio Company API](https://docs.bokio.se) as tools for AI agents.

## Setup

**Prerequisites:** [uv](https://docs.astral.sh/uv/) and a Bokio API token.

```sh
git clone <repo>
cd bokio-company-mcp

uv sync

cp .env.example .env
# edit .env and fill in BOKIO_API_TOKEN and BOKIO_COMPANY_ID
```

## Integrating with Claude CLI

Add the server with the `claude mcp add` command:

```sh
claude mcp add bokio \
  -e BOKIO_API_TOKEN=your_token_here \
  -e BOKIO_COMPANY_ID=your_company_uuid_here \
  -- uv run --directory /path/to/bokio-company-mcp bokio-mcp
```

Verify it was added:

```sh
claude mcp list
```

## Available tools

| Area | Tools |
|---|---|
| Journal entries | list, get, create, reverse |
| Customers | list, get, create, update, delete |
| Invoices | list, get, create, update, publish, record |
| Invoice line items | add |
| Invoice attachments | list, get, download, delete |
| Invoice payments | create, get, list, delete, record |
| Invoice settlements | create, get, list, delete, record |
| Credit notes | list, get, update, publish, create from invoice, record |
| Items | list, get, create, update, delete |
| Uploads | list, get, download, add |
| Bank payments | list, get, create |
| Chart of accounts | list, get by account number |
| Fiscal years | list, get |
| SIE files | download |
| Company information | get |

## Development

```sh
uv sync --group dev
uv run pytest
```

To run the server with the MCP inspector:

```sh
uv run mcp dev src/bokio_mcp/server.py
```
